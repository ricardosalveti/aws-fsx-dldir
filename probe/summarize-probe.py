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


def other_inside(v, enters):
    """(host, lock inode) of the participant that was inside during violation v.

    With --verbose every entry is logged with the inode of the lock file it
    holds: use the entry named in the marker, else the latest entry of any
    other process of the same mode in the second before the violation (the
    marker is often still empty when two hosts enter together).
    """
    first = (v.get("holder") or "").split()
    if first and ":" in first[0]:
        m = re.search(r" it=(\d+)", v["holder"])
        for t, it, ino in enters.get((v["mode"], first[0]), []):
            if m and it == int(m.group(1)):
                return host_of(first[0]), ino
    best = None
    for (mode, who), lst in enters.items():
        if mode != v["mode"] or who == v["who"]:
            continue
        before = [e for e in lst if 0 <= v["t"] - e[0] < 1.0]
        if before and (best is None or before[-1][0] > best[0]):
            best = (before[-1][0], host_of(who), before[-1][2])
    if best:
        return best[1], best[2]
    return holder_host(v), None


def holder_host(violation):
    """Host named in the marker found by a violation, None if unreadable."""
    first = (violation.get("holder") or "").split(" ", 1)[0]
    return host_of(first) if ":" in first and not first.startswith("unreadable") else None


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
        enters = {}
        for e in ev:
            if e.get("kind") == "enter":
                enters.setdefault((e["mode"], e["who"]), []).append((e["t"], e["it"], e["lock"].get("ino")))
        for lst in enters.values():
            lst.sort()
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
        print("%-24s %5s %6s %9s %7s %7s %7s %8s %8s %10s %10s  %s" % (
            "mode", "hosts", "procs", "iters", "cross", "same", "unknown", "stale-lf", "vanished",
            "wait p50ms", "wait maxms", "check"))
        print("%-24s %5s %6s %9s %23s" % ("", "", "", "", "<----- violations ---->"))

        verdict, mode_ops = {}, {}
        for mode in MODES:
            sm = [e for e in ev if e.get("kind") == "summary" and e.get("mode") == mode]
            vio = [e for e in ev if e.get("kind") == "violation" and e.get("mode") == mode]
            if not sm and not vio:
                continue
            # The holder is what the other participant wrote into the marker;
            # it can be empty when the marker was created but not yet written.
            other = [other_inside(v, enters) for v in vio]
            cross = [v for v, (h, _) in zip(vio, other) if h not in (None, host_of(v["who"]))]
            unknown = [v for v, (h, _) in zip(vio, other) if h is None]
            ino_same = sum(1 for v, (_, i) in zip(vio, other) if i is not None and i == v["lock"].get("ino"))
            ino_diff = sum(1 for v, (_, i) in zip(vio, other) if i is not None and i != v["lock"].get("ino"))
            stale = sum(e.get("stale_lockfile", 0) for e in sm)
            vanished = sum(e.get("marker_vanished", 0) for e in sm)
            # A cross-host violation proves the other host took part even when
            # its own files are missing.
            mhosts = {host_of(e["who"]) for e in sm} | {h for h, _ in other if h}
            iters = sum(e["iterations"] for e in sm)
            waits = [e["wait_ms_median"] for e in sm if e.get("wait_ms_median") is not None]
            p50 = statistics.median(waits) if waits else 0
            mx = max([e["wait_ms_max"] or 0 for e in sm] or [0])
            # Every host ends a mode at the same wall-clock time when the
            # schedules matched; a spread of more than a few seconds means the
            # hosts did not run this mode together.
            ends = [e["t"] for e in sm]
            spread = max(ends) - min(ends) if ends else 0
            notes = []
            if len(mhosts) < 2:
                notes.append("ONLY ONE HOST: cannot test cross-host locking")
            if spread > 5:
                notes.append("hosts ended %.0fs apart: different --start-at or a stuck lock" % spread)
            # The locks are not fair, so a low median wait does not mean no
            # contention; a host that barely got in does.
            per_host = {}
            for e in sm:
                per_host[host_of(e["who"])] = per_host.get(host_of(e["who"]), 0) + e["iterations"]
            for h, n in sorted(per_host.items()):
                if len(per_host) >= 2 and n < 0.05 * iters:
                    notes.append("%s got only %d of %d iterations" % (h, n, iters))
            missing = sorted(mhosts - set(per_host))
            if missing:
                notes.append("no summary from %s: pass its files too" % " ".join(missing))
            errors = [e for e in ev if e.get("kind") == "error" and e.get("mode") == mode]
            if errors:
                notes.append("%d process(es) died: %s" % (len(errors), errors[0].get("error", "?")))
            ok = (len(mhosts) >= 2 and spread <= 5) or bool(cross)
            verdict[mode] = (ok, len(vio), len(cross), stale, iters, vanished, ino_same, ino_diff)
            print("%-24s %5d %6d %9d %7d %7d %7d %8d %8d %10.1f %10.1f  %s" % (
                mode, len(mhosts), len(sm), iters, len(cross), len(vio) - len(cross) - len(unknown),
                len(unknown), stale, vanished, p50, mx, "; ".join(notes) or "ok"))
            for v in vio[:args.show]:
                print("    %s  %s  inside while  %s" % (v.get("ts", ""), v["who"], v.get("holder") or "(empty marker)"))
            if len(vio) > args.show:
                print("    ... %d more" % (len(vio) - args.show))
            for e in sm:
                if e.get("nfs_ops"):
                    mode_ops.setdefault(mode, {})[host_of(e["who"])] = (e["nfs_ops"], per_host.get(host_of(e["who"]), 0))

        # NFS operations per mode, counted by the first process of each host
        # (the counters are per mount, so they include all its workers).
        if mode_ops:
            print()
            print("NFS ops per mode and host (per iteration of that host):")
            print("    %-24s %-18s %s" % ("mode", "host", " ".join("%11s" % o for o in OPS)))
            for mode in MODES:
                for h, (ops, n) in sorted(mode_ops.get(mode, {}).items()):
                    print("    %-24s %-18s %s" % (mode, h, " ".join(
                        "%5d %5s" % (ops.get(o, 0), "(%.1f)" % (ops.get(o, 0) / n) if n else "") for o in OPS)))

        # NFS operation counts of each process during the whole run
        envs = {}
        for e in ev:
            if e.get("kind") == "env":
                envs.setdefault(e["who"], {})[e["when"]] = e.get("nfs_ops", {})
        if envs:
            print()
            print("NFS ops during the run (end - start, per host):")
            print("    %-28s %s" % ("host", " ".join("%11s" % o for o in OPS)))
        deleg = 0
        for who, w in sorted(envs.items()):
            if "start" in w and "end" in w:
                delta = {o: w["end"].get(o, {}).get("ops", 0) - w["start"].get(o, {}).get("ops", 0) for o in OPS}
                deleg += delta["DELEGRETURN"]
                print("    %-28s %s" % (host_of(who), " ".join("%11d" % delta[o] for o in OPS)))
            else:
                print("    %-28s (no end record: the probe did not finish)" % host_of(who))
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
            cross = verdict["nolock"][2]
            print("  - detector self test (nolock): %s" % (
                "works across hosts, %d cross-host violations seen" % cross if cross else
                "NO cross-host violations: the hosts did not overlap, the results below are not meaningful"))
        if not real:
            print("  - no lock modes in this input (self test only)")
        elif bad:
            status = 1
            print("  - REPRODUCED in: %s" % ", ".join(
                "%s (%d violations, %d cross-host, %d stale-lockfile, in %d iterations)"
                % (m, real[m][1], real[m][2], real[m][3], real[m][4]) for m in bad))
            same, diff = sum(real[m][6] for m in bad), sum(real[m][7] for m in bad)
            if same or diff:
                print("  - lock inodes of the two participants (from --verbose entries): %d different, %d the same"
                      % (diff, same))
                if diff and not same:
                    print("    every overlap had each host holding a lock on a DIFFERENT lock file under the same"
                          " name: the locks excluded, the lock-file name did not")
                elif same:
                    print("    two hosts held a lock on the SAME file at once: the NFS lock itself did not exclude")
            if any(m in bad for m in ("flock", "posix")):
                print("  - plain flock/lockf fails: the NFS locks themselves do not exclude across hosts")
            elif any(m.startswith("bitbake") for m in bad):
                print("  - plain flock/lockf clean, BitBake protocol fails: the lock-file protocol"
                      " (unlink + re-create + stat) is what breaks on this mount")
            clean = ["%s: 0 in %d iterations" % (m, v[4]) for m, v in real.items() if v[0] and m not in bad]
            if clean:
                print("  - clean: %s" % "; ".join(clean))
                print("    a clean mode only counts with as many iterations under contention as the failing one")
        elif not tested:
            print("  - INCONCLUSIVE: no mode ran on two or more hosts at the same time")
            status = status or 2
        else:
            print("  - NOT REPRODUCED: 0 violations and 0 stale lock files in %s" % ", ".join(
                "%s (%d iterations)" % (m, real[m][4]) for m in tested))
            print("    next: --round-ms 1000, then --hold-ms 200 --workers 4, then one mount option change per run")
        if any(v[5] for v in verdict.values()):
            print("  - markers vanished from under their creator: another participant removed them while it was"
                  " inside (probe versions before 2026-10-03 also did this in their end-of-run cleanup)")
        if deleg:
            print("  - DELEGRETURN grew by %d: the server grants delegations (a client holding one may answer"
                  " opens and locks of that file without asking the server)" % deleg)
        print()
    sys.exit(status)


if __name__ == "__main__":
    main()
