#!/usr/bin/env python3
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
#
# summarize-probe: turn the output of nfs-lock-probe.py from several hosts into
# one table per shared directory and a verdict: was the collision reproduced,
# and in which lock modes.
#
# Inputs, in any mix: the lock-probe-<host>.tgz tarballs, the ~/lock-probe
# directories, or single stdout.txt / nfs-lock-probe-*.jsonl files. Pass the
# files of ALL hosts in one call: a cross-host violation is only visible when
# the hosts are compared.
#
#   python3 summarize-probe.py lock-probe-*.tgz
#
# Exit status: 1 reproduced in any run (violations or stale lock files), else
# 2 if a run cannot answer the question (e.g. only one host per mode), else 0.
#
# Only the Python standard library is used.

import argparse
import json
import os
import re
import statistics
import sys
import tarfile
import time

MODES = ("flock", "posix", "bitbake", "bitbake-shared", "bitbake-shared-fresh",
         "bitbake-shared-nounlink", "nolock")
OPS = ("LOCK", "LOCKU", "OPEN", "REMOVE", "LOOKUP", "GETATTR", "DELEGRETURN")


def host_of(who):
    return who.rsplit(":", 1)[0]


def lines_from(path):
    """(name, line) for every probe log line found in path."""
    def wanted(name):
        base = os.path.basename(name)
        return base == "stdout.txt" or (base.startswith("nfs-lock-probe-") and base.endswith(".jsonl"))

    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for f in sorted(files):
                if wanted(f):
                    yield from lines_from(os.path.join(root, f))
    elif tarfile.is_tarfile(path):
        with tarfile.open(path) as tar:
            for m in tar.getmembers():
                if m.isfile() and wanted(m.name):
                    for line in tar.extractfile(m).read().decode(errors="replace").splitlines():
                        yield "%s:%s" % (path, m.name), line
    else:
        with open(path, errors="replace") as f:
            for line in f:
                yield path, line.rstrip("\n")


def load(paths):
    # stdout.txt repeats the summary/violation/env lines of the .jsonl logs
    # byte for byte, so identical lines are counted once.
    seen, events = set(), []
    for p in paths:
        if not os.path.exists(p):
            sys.exit("%s: no such file or directory" % p)
        for _, line in lines_from(p):
            if not line.startswith("{") or line in seen:
                continue
            seen.add(line)
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
    return events


def split_runs(events):
    """Map each process to (shared dir, run start): one key per probe run.

    The same directory is usually probed several times (other options, other
    days). Processes of one run end each mode at the same wall-clock time, so
    two processes belong to the same run when any of their mode end times are
    within a few seconds; a host that joined late still shares the later ones.
    """
    ends, dir_of = {}, {}
    for e in events:
        if e.get("kind") == "summary":
            ends.setdefault(e["who"], []).append(e["t"])
            dir_of[e["who"]] = e["dir"]
    parent = {w: w for w in ends}

    def find(w):
        while parent[w] != w:
            parent[w] = parent[parent[w]]
            w = parent[w]
        return w

    whos = sorted(ends)
    for i, a in enumerate(whos):
        for b in whos[i + 1:]:
            if dir_of[a] == dir_of[b] and any(abs(x - y) <= 5 for x in ends[a] for y in ends[b]):
                parent[find(a)] = find(b)
    first = {}
    for w in whos:
        r = find(w)
        first[r] = min(first.get(r, float("inf")), min(ends[w]))
    return {w: (dir_of[w], first[find(w)]) for w in whos}


def main():
    p = argparse.ArgumentParser(description="Summarize nfs-lock-probe.py results from several hosts.")
    p.add_argument("paths", nargs="+", help="tarballs, directories, stdout.txt or .jsonl files")
    p.add_argument("--show", type=int, default=5, help="example violation lines to print per mode")
    args = p.parse_args()

    events = load(args.paths)
    if not events:
        sys.exit("no nfs-lock-probe output found in %s" % " ".join(args.paths))

    # The env records carry no "dir": they belong to the run of their process.
    run_of = split_runs(events)
    source = {}
    for e in events:
        if e.get("kind") == "env" and e.get("when") == "start" and e["who"] in run_of:
            m = re.search(r"\n\S+\s+(\S+)\s+(\S+)\s+(\S+)", e.get("findmnt", ""))
            if m:
                source[run_of[e["who"]]] = "%s (%s) %s" % (m.group(1), m.group(2), m.group(3))

    status = 0
    for key in sorted(set(run_of.values())):
        d, first_end = key
        ev = [e for e in events if run_of.get(e.get("who")) == key]
        hosts = sorted({host_of(e["who"]) for e in ev})
        print("=" * 100)
        hold = sorted({e.get("hold_ms") for e in ev if e.get("kind") == "summary"})
        print("shared dir: %s" % d)
        print("run:        first mode ended %s, hold-ms %s" % (
            time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(first_end)), "/".join("%g" % h for h in hold)))
        if key in source:
            print("mount:      %s" % source[key])
        print("hosts:      %d  %s" % (len(hosts), " ".join(hosts)))
        print()
        print("%-24s %5s %6s %9s %9s %9s %8s %10s %10s  %s" % (
            "mode", "hosts", "procs", "iters", "cross-hv", "same-hv", "stale-lf", "wait p50ms", "wait maxms", "check"))

        verdict = {}
        for mode in MODES:
            sm = [e for e in ev if e.get("kind") == "summary" and e.get("mode") == mode]
            if not sm:
                continue
            vio = [e for e in ev if e.get("kind") == "violation" and e.get("mode") == mode]
            cross = [v for v in vio if host_of(v.get("holder", "?:").split()[0]) != host_of(v["who"])]
            stale = sum(e.get("stale_lockfile", 0) for e in sm)
            mhosts = {host_of(e["who"]) for e in sm}
            iters = sum(e["iterations"] for e in sm)
            p50 = statistics.median(e["wait_ms_median"] for e in sm if e.get("wait_ms_median") is not None)
            mx = max(e["wait_ms_max"] or 0 for e in sm)
            # Every host ends a mode at the same wall-clock time when the
            # schedules matched; a spread of more than a few seconds means the
            # hosts did not run this mode together.
            ends = [e["t"] for e in sm]
            spread = max(ends) - min(ends)
            notes = []
            if len(mhosts) < 2:
                notes.append("ONLY ONE HOST: cannot test cross-host locking")
            if spread > 5:
                notes.append("hosts ended %.0fs apart: different --start-at?" % spread)
            # The locks are not fair, so a low median wait does not mean no
            # contention; a host that barely got in does.
            per_host = {}
            for e in sm:
                per_host[host_of(e["who"])] = per_host.get(host_of(e["who"]), 0) + e["iterations"]
            for h, n in sorted(per_host.items()):
                if len(mhosts) >= 2 and n < 0.05 * iters:
                    notes.append("%s got only %d of %d iterations" % (h, n, iters))
            ok = len(mhosts) >= 2 and spread <= 5
            verdict[mode] = (ok, len(vio), len(cross), stale)
            print("%-24s %5d %6d %9d %9d %9d %8d %10.1f %10.1f  %s" % (
                mode, len(mhosts), len(sm), iters, len(cross), len(vio) - len(cross), stale, p50, mx,
                "; ".join(notes) or "ok"))
            for v in vio[:args.show]:
                print("    %s  %s  inside while  %s" % (v.get("ts", ""), v["who"], v.get("holder", "?")))
            if len(vio) > args.show:
                print("    ... %d more" % (len(vio) - args.show))

        # NFS operation counts of each process during the whole run
        print()
        print("NFS ops during the run (end - start, per host):")
        envs = {}
        for e in ev:
            if e.get("kind") == "env":
                envs.setdefault(e["who"], {})[e["when"]] = e.get("nfs_ops", {})
        print("    %-28s %s" % ("host", " ".join("%11s" % o for o in OPS)))
        deleg = 0
        for who, w in sorted(envs.items()):
            if "start" in w and "end" in w:
                delta = {o: w["end"].get(o, {}).get("ops", 0) - w["start"].get(o, {}).get("ops", 0) for o in OPS}
                deleg += delta["DELEGRETURN"]
                print("    %-28s %s" % (host_of(who), " ".join("%11d" % delta[o] for o in OPS)))
            else:
                print("    %-28s (no end record: run interrupted?)" % host_of(who))
        for e in ev:
            if e.get("kind") == "env" and e.get("when") == "end":
                msgs = [l for l in e.get("dmesg_nfs", "").splitlines()
                        if re.search(r"\b(nfs\w*|lockd|sunrpc|rpc)\b", l, re.I) and "apparmor=" not in l]
                if msgs:
                    print("    NFS kernel messages on %s:\n      %s" % (host_of(e["who"]), "\n      ".join(msgs[-10:])))

        # Verdict, as in probe/README.md "Reading the result"
        print()
        print("VERDICT for %s, run of %s:" % (d, time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(first_end))))
        real = {m: v for m, v in verdict.items() if m != "nolock"}
        tested = [m for m, v in real.items() if v[0]]
        bad = [m for m, v in real.items() if v[1] or v[3]]
        if "nolock" in verdict:
            _, n, cross, _ = verdict["nolock"]
            print("  - detector self test (nolock): %s" % (
                "works across hosts, %d cross-host violations seen" % cross if cross else
                "NO cross-host violations: the hosts did not overlap, the results below are not meaningful"))
        if not real:
            print("  - no lock modes in this input (self test only)")
        elif not tested:
            print("  - INCONCLUSIVE: no mode ran on two or more hosts at the same time")
            status = status or 2
        elif not bad:
            print("  - NOT REPRODUCED: 0 violations and 0 stale lock files in %s" % ", ".join(tested))
            print("    next: --hold-ms 200 --workers 4, then one mount option change per run (see README)")
        else:
            status = 1
            print("  - REPRODUCED in: %s" % ", ".join(
                "%s (%d violations, %d cross-host, %d stale-lockfile)" % (m, real[m][1], real[m][2], real[m][3])
                for m in bad))
            plain = [m for m in ("flock", "posix") if m in bad]
            if plain:
                print("  - plain flock/lockf fails: the NFS locks themselves do not exclude across hosts (AWS side)")
            elif any(m.startswith("bitbake") for m in bad):
                print("  - plain flock/lockf clean, BitBake protocol fails: the lock-file protocol"
                      " (unlink + re-create + stat) is what breaks on this mount")
                for fix, why in (("bitbake-shared-fresh", "stat() answered from the client cache"),
                                 ("bitbake-shared-nounlink", "never unlinking the lock file is a sufficient fix")):
                    if "bitbake-shared" in bad and fix in real and fix not in bad and real[fix][0]:
                        print("  - %s clean while bitbake-shared fails: %s" % (fix, why))
        if deleg:
            print("  - DELEGRETURN grew by %d: the server hands out delegations" % deleg)
        print()
    sys.exit(status)


if __name__ == "__main__":
    main()
