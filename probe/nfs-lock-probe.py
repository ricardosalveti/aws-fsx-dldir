#!/usr/bin/env python3
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
#
# nfs-lock-probe: check that an exclusive file lock taken on a shared (NFS)
# directory really excludes other hosts.
#
# Run the same command, at the same time, on two or more hosts that mount the
# same directory. Every participant loops: take the lock, enter the critical
# section, leave, release. Inside the critical section it creates a marker file
# with O_CREAT|O_EXCL (atomic on the server, never answered from a client
# cache). If the marker already exists, another participant is inside the
# critical section at the same time: the lock did not exclude it.
#
# Modes (what "take the lock" means):
#   flock           flock(LOCK_EX) on a lock file that is never removed
#   posix           fcntl.lockf(LOCK_EX) on a lock file that is never removed
#   bitbake         the protocol of BitBake's bb.utils.lockfile()/unlockfile():
#                   open(name, "a+"), flock(LOCK_EX), then accept the lock only
#                   if fstat(fd).st_ino == stat(name).st_ino; unlockfile()
#                   unlinks the lock file before releasing the lock
#   bitbake-shared  as used by the BitBake fetcher since 2026-08: take the lock
#                   shared first, then "upgrade" it with unlockfile() followed
#                   by lockfile() (exclusive)
#   bitbake-shared-fresh
#                   bitbake-shared, but the lock is accepted by comparing with
#                   a fresh open() of the name (an NFSv4 OPEN always reaches the
#                   server) instead of stat(), which may be answered from the
#                   client's lookup and attribute caches
#   bitbake-shared-nounlink
#                   bitbake-shared, but the lock file is never unlinked
#   nolock          no lock at all: self test of the detector, it must report
#                   violations (not part of the default modes)
#
# Reading the result:
#   violations in flock/posix          the locks themselves do not exclude
#                                      across hosts (NFS client/server problem)
#   violations only in bitbake modes   the locks work; the lock file protocol
#                                      (unlink + re-create + stat) is what fails
#   "stale-lockfile" events            a lock was accepted on a file that this
#                                      client already saw as unlinked (st_nlink
#                                      0); nlink 1 proves nothing, fstat() may
#                                      come from the attribute cache
#   "marker-vanished" events           another participant removed our marker
#                                      while we were inside the section
#
# Only the Python standard library is used. Nothing is written outside --dir
# (shared) and --log-dir (local).

import argparse
import errno
import fcntl
import json
import os
import re
import socket
import subprocess
import sys
import time

HOST = socket.gethostname()
STALE_MARKER_S = 60.0
ME = "%s:%d" % (HOST, os.getpid())


def now():
    return time.time()


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".%06dZ" % int((t % 1) * 1e6)


class Log:
    def __init__(self, path, echo):
        self.f = open(path, "a", buffering=1)
        self.echo = echo

    def event(self, kind, **kw):
        kw.update(kind=kind, t=now(), who=ME)
        kw["ts"] = iso(kw["t"])
        line = json.dumps(kw, sort_keys=True)
        self.f.write(line + "\n")
        if self.echo or kind in ("violation", "stale-lockfile", "stale-marker", "marker-vanished", "error",
                                     "summary", "env"):
            print(line, flush=True)


# --- lock implementations ----------------------------------------------------

def plain_lock(name, posix):
    fd = os.open(name, os.O_RDWR | os.O_CREAT, 0o664)
    if posix:
        fcntl.lockf(fd, fcntl.LOCK_EX)
    else:
        fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def plain_unlock(fd, posix):
    if posix:
        fcntl.lockf(fd, fcntl.LOCK_UN)
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)


def fresh_stat(name):
    """stat() through a new open(): not answered from the client caches."""
    try:
        fd = os.open(name, os.O_RDONLY)
    except FileNotFoundError:
        return None
    try:
        return os.fstat(fd)
    finally:
        os.close(fd)


def bb_lockfile(name, shared, stats, fresh=False):
    """bb.utils.lockfile() from BitBake (lib/bb/utils.py), blocking variant."""
    op = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
    while True:
        try:
            lf = open(name, "a+")
            fileno = lf.fileno()
            fcntl.flock(fileno, op)
            statinfo = os.fstat(fileno)
            if fresh:
                statinfo2 = fresh_stat(lf.name)
                if statinfo2 and statinfo.st_ino == statinfo2.st_ino:
                    stats["ino"] = statinfo.st_ino
                    stats["nlink"] = statinfo.st_nlink
                    return lf
            elif os.path.exists(lf.name):
                statinfo2 = os.stat(lf.name)
                if statinfo.st_ino == statinfo2.st_ino:
                    # Not part of BitBake: remember what we were granted
                    stats["ino"] = statinfo.st_ino
                    stats["nlink"] = statinfo.st_nlink
                    return lf
            stats["retries"] = stats.get("retries", 0) + 1
            lf.close()
        except OSError as e:
            stats.setdefault("oserrors", []).append(errno.errorcode.get(e.errno, str(e.errno)))
            try:
                lf.close()
            except Exception:
                pass


def bb_unlockfile(lf, unlink=True):
    """bb.utils.unlockfile() from BitBake (lib/bb/utils.py)."""
    try:
        # If we had a shared lock, we need to promote to exclusive before
        # removing the lockfile. Attempt this, ignore failures.
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if unlink:
            os.unlink(lf.name)
    except (IOError, OSError):
        pass
    fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
    lf.close()


# --- critical section --------------------------------------------------------

def critical_section(args, log, mode, it, lockinfo):
    """Returns (violations, vanished markers) of one pass."""
    marker = os.path.join(args.dir, "probe-%s.marker" % mode)
    try:
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o664)
    except FileExistsError:
        other = "?"
        try:
            with open(marker) as f:
                other = f.read().strip()
        except OSError as e:
            other = "unreadable: %s" % e
        m = re.search(r" e=([0-9.]+)", other)
        age = now() - float(m.group(1)) if m else 0
        # An OPEN can take seconds on a busy mount, so only a marker that is
        # much older than any NFS call counts as left behind.
        if age > max(STALE_MARKER_S, 50 * args.hold_ms / 1000.0):
            # left behind by a participant that was killed inside the section
            log.event("stale-marker", mode=mode, it=it, holder=other, age_s=round(age, 1))
            try:
                os.unlink(marker)
            except OSError:
                pass
            return 0, 0
        log.event("violation", mode=mode, it=it, holder=other, lock=lockinfo)
        time.sleep(args.hold_ms / 1000.0)
        return 1, 0
    mine = "%s it=%d t=%s e=%.6f" % (ME, it, iso(now()), now())
    os.write(fd, mine.encode())
    os.close(fd)
    time.sleep(args.hold_ms / 1000.0)
    try:
        os.unlink(marker)
    except FileNotFoundError:
        # Someone else removed our marker while we were inside: either it
        # took it for a stale one, or it was inside at the same time.
        log.event("marker-vanished", mode=mode, it=it, mine=mine, lock=lockinfo)
        return 0, 1
    return 0, 0


def run_mode(args, log, mode, until, count_ops):
    lockname = os.path.join(args.dir, "probe-%s.lock" % mode)
    it = violations = stale = vanished = 0
    waits = []
    fresh = mode.endswith("-fresh")
    unlink = not mode.endswith("-nounlink")
    ops0 = nfs_ops(args.dir) if count_ops else None
    while now() < until:
        if args.round_ms:
            # Start every attempt at the same wall-clock instant on all
            # hosts, like two builds starting the same download together.
            r = args.round_ms / 1000.0
            nxt = (int(now() / r) + 1) * r
            if nxt >= until:
                break
            time.sleep(nxt - now())
        it += 1
        stats = {}
        t0 = now()
        if mode == "nolock":
            pass
        elif mode in ("flock", "posix"):
            fd = plain_lock(lockname, mode == "posix")
            st = os.fstat(fd)
            stats.update(ino=st.st_ino, nlink=st.st_nlink)
        elif mode == "bitbake":
            lf = bb_lockfile(lockname, False, stats)
        else:
            lf = bb_lockfile(lockname, True, stats, fresh)
            # bb.utils.lockfile_to_exclusive()
            bb_unlockfile(lf, unlink)
            lf = bb_lockfile(lockname, False, stats, fresh)
        waited = now() - t0
        waits.append(waited)
        stats["waited_ms"] = round(waited * 1000, 3)
        if mode.startswith("bitbake"):
            # st_nlink 0 means the file we hold is already unlinked. The
            # converse is weak: fstat() may be answered from the attribute
            # cache, so nlink 1 does not prove the server still links it.
            st = os.fstat(lf.fileno())
            stats["nlink_after"] = st.st_nlink
            if st.st_nlink == 0 or stats.get("nlink") == 0:
                stale += 1
                log.event("stale-lockfile", mode=mode, it=it, lock=stats)
        if args.verbose:
            log.event("enter", mode=mode, it=it, lock=stats)
        v, gone = critical_section(args, log, mode, it, stats)
        violations += v
        vanished += gone
        if mode == "nolock":
            pass
        elif mode in ("flock", "posix"):
            plain_unlock(fd, mode == "posix")
        else:
            bb_unlockfile(lf, unlink)
        if args.pause_ms:
            time.sleep(args.pause_ms / 1000.0)
    waits.sort()
    extra = {}
    if count_ops:
        # per mount, so this covers every worker of this host
        ops1 = nfs_ops(args.dir)
        extra["nfs_ops"] = {o: ops1[o]["ops"] - ops0.get(o, {}).get("ops", 0) for o in ops1}
    log.event("summary", mode=mode, dir=args.dir, iterations=it, violations=violations,
              stale_lockfile=stale, marker_vanished=vanished, hold_ms=args.hold_ms,
              round_ms=args.round_ms,
              wait_ms_median=round(waits[len(waits) // 2] * 1000, 3) if waits else None,
              wait_ms_max=round(waits[-1] * 1000, 3) if waits else None, **extra)
    return violations


# --- environment -------------------------------------------------------------

def sh(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as e:
        return "failed: %s" % e


def read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError as e:
        return "unreadable: %s" % e.strerror


def mountstats(path):
    """The /proc/self/mountstats block of the mount holding path."""
    target = sh("findmnt -n -o TARGET -T %s" % path)
    block, keep = [], False
    for line in read("/proc/self/mountstats").splitlines():
        if line.startswith("device "):
            keep = (" mounted on %s " % target) in line
        if keep:
            block.append(line)
    return block


def nfs_ops(path):
    ops = {}
    for line in mountstats(path):
        p = line.split()
        if p and p[0].rstrip(":") in ("OPEN", "OPEN_NOATTR", "CLOSE", "LOCK", "LOCKU", "LOCKT", "LOOKUP",
                                      "GETATTR", "REMOVE", "CREATE", "RENEW", "SEQUENCE", "DELEGRETURN",
                                      "RECLAIM_COMPLETE", "EXCHANGE_ID", "CREATE_SESSION"):
            # ops, transmissions, major timeouts, ..., errors (last column on recent kernels)
            ops[p[0].rstrip(":")] = {"ops": int(p[1]), "trans": int(p[2]), "timeouts": int(p[3]),
                                     "errors": int(p[9]) if len(p) > 9 else None}
    return ops


def collect_env(args, log, when):
    env = {"when": when, "host": HOST, "nfs_ops": nfs_ops(args.dir)}
    if when == "start":
        env.update(
            uname=sh("uname -a"),
            os_release=sh(". /etc/os-release; echo $PRETTY_NAME"),
            python=sys.version.split()[0],
            findmnt=sh("findmnt -T %s -o TARGET,SOURCE,FSTYPE,OPTIONS" % args.dir),
            statfs=sh("stat -f -c 'type=%%T bsize=%%s' %s" % args.dir),
            ip=sh("hostname -I"),
            nfs_client_identifier=read("/sys/fs/nfs/net/nfs_client/identifier"),
            nfs4_unique_id=read("/sys/module/nfs/parameters/nfs4_unique_id"),
            nfs_versions=sh("modinfo -F version nfs nfsv4 2>/dev/null | tr '\\n' ' '"),
            time_sync=sh("chronyc tracking 2>/dev/null | grep -E 'System time|Last offset' || timedatectl show -p NTPSynchronized 2>/dev/null"),
            mountstats_head=mountstats(args.dir)[:12],
        )
    else:
        env["dmesg_nfs"] = sh("(dmesg 2>/dev/null || sudo -n dmesg 2>/dev/null) | grep -i -E 'nfs|lockd|sunrpc' | tail -40")
    log.event("env", **env)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dir", required=True, help="directory on the shared file system (created if missing)")
    p.add_argument("--modes", default="flock,posix,bitbake,bitbake-shared,bitbake-shared-fresh,bitbake-shared-nounlink")
    p.add_argument("--duration", type=int, default=120, help="seconds per mode")
    p.add_argument("--gap", type=int, default=15, help="seconds between modes")
    p.add_argument("--start-at", type=int, default=0,
                   help="epoch seconds when the first mode starts; pass the same value on every host "
                        "(default: next multiple of --align seconds)")
    p.add_argument("--align", type=int, default=300)
    p.add_argument("--hold-ms", type=float, default=20, help="time spent inside the critical section")
    p.add_argument("--pause-ms", type=float, default=0, help="time spent outside, between iterations")
    p.add_argument("--round-ms", type=int, default=0,
                   help="start every attempt at the next multiple of this many ms of wall-clock time, "
                        "the same instant on every host (0: loop without waiting)")
    p.add_argument("--workers", type=int, default=1, help="processes on this host")
    p.add_argument("--log-dir", default=".", help="local directory for the event log")
    p.add_argument("--verbose", action="store_true", help="log every critical section entry")
    args = p.parse_args()

    os.makedirs(args.dir, exist_ok=True)
    os.makedirs(args.log_dir, exist_ok=True)
    start = args.start_at or (int(now()) // args.align + 1) * args.align
    modes = [m for m in args.modes.split(",") if m]
    known = ("flock", "posix", "bitbake", "bitbake-shared", "bitbake-shared-fresh", "bitbake-shared-nounlink", "nolock")
    for m in modes:
        if m not in known:
            p.error("unknown mode %s" % m)
    print("%s: first mode starts at %s (epoch %d), last mode ends at %s" % (
        HOST, iso(start), start, iso(start + len(modes) * (args.duration + args.gap) - args.gap)), flush=True)

    children = []
    for w in range(1, args.workers):
        pid = os.fork()
        if pid == 0:
            children = None
            break
        children.append(pid)
    global ME
    ME = "%s:%d" % (HOST, os.getpid())
    log = Log(os.path.join(args.log_dir, "nfs-lock-probe-%s-%d.jsonl" % (HOST, os.getpid())), args.verbose)

    if children is not None:
        collect_env(args, log, "start")
    total = 0
    for i, mode in enumerate(modes):
        begin = start + i * (args.duration + args.gap)
        delay = begin - now()
        if delay > 0:
            time.sleep(delay)
        elif delay < -args.duration:
            continue
        try:
            total += run_mode(args, log, mode, begin + args.duration, children is not None)
        except Exception as e:
            # keep going: the other modes and the end record still matter
            log.event("error", mode=mode, error="%s: %s" % (type(e).__name__, e))
    if children is None:
        os._exit(1 if total else 0)
    for pid in children:
        _, status = os.waitpid(pid, 0)
        total += os.waitstatus_to_exitcode(status)
    collect_env(args, log, "end")
    # Other hosts may still be inside their last pass (a lock wait can run
    # past the end of the mode), so only remove markers this host left
    # behind; the lock files stay until the directory is removed by hand.
    for m in modes:
        marker = os.path.join(args.dir, "probe-%s.marker" % m)
        try:
            with open(marker) as f:
                mine = f.read().startswith(HOST + ":")
            if mine:
                os.unlink(marker)
        except OSError:
            pass
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
