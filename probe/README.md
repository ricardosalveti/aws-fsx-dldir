# nfs-lock-probe: manual run on the CI hosts

Goal: measure, on the real mounts, whether an exclusive lock taken on one host
excludes the other hosts, and whether it is the lock itself or the lock-file
protocol used by BitBake that fails. Run it on FSx (`/efsx`) and on EFS
(`/efs`) with the same hosts, so the two results are comparable.

Needs: 2 or more hosts (ephemeral runner instances are fine) that mount the
same directory, Python 3.8+, clocks synced by chrony (the runners are). The
probe uses only the standard library, writes only to `--dir` (shared) and
`--log-dir` (local). When every host has finished, remove the shared
directory from one host (`rm -rf /efsx/qli/lock-probe`); a host that finishes
first does not remove the lock files, another host may still be using them.

## 1. Copy the script to every host

    scp nfs-lock-probe.py <host>:~/

## 2. Pick a start time, the same on every host

The modes run one after the other on a fixed wall-clock schedule, so every host
must be given the same `--start-at`. Choose a time 3-5 minutes ahead:

    START=$(date -u -d '2026-09-30 15:30:00' +%s)   # edit the time, keep UTC
    echo $START

## 3. Run on every host, on FSx first

    mkdir -p ~/lock-probe/efsx
    python3 ~/nfs-lock-probe.py --dir /efsx/qli/lock-probe --log-dir ~/lock-probe/efsx \
        --start-at $START --workers 2 --duration 120 --hold-ms 20 | tee ~/lock-probe/efsx/stdout.txt

Six modes x (120 s + 15 s gap) = about 13.5 minutes. The first line printed
says when the first mode starts and when the last one ends; it must be the
same on every host. A JSON `env` line follows right away. After that the probe
is silent while a mode runs and prints one `summary` line per worker when the
mode ends (every 2 min 15 s), so 12 summary lines in total with `--workers 2`.
`violation` or `stale-lockfile` lines in between are findings, not errors.
Exit status is 1 when any violation was seen.

To see that it is running during a mode: `pgrep -af nfs-lock-probe` (one
process per worker), and the `LOCK`/`OPEN`/`REMOVE` counts of the `/efsx`
block in `/proc/self/mountstats` keep growing.

## 4. Same on EFS, with a new start time

Both repositories build on `/efsx` now, so a current runner image may not
mount `/efs` any more. If `findmnt -T /efs` shows nothing, mount the EFS file
system on the two probe hosts first (amazon-efs-utils, the same options the
CI used before 2026-09-02). Step 5's `findmnt` output for `/efs` is also what
fills in the EFS mount options that the report is missing.

    START=$(date -u -d '2026-09-30 15:50:00' +%s)
    mkdir -p ~/lock-probe/efs
    python3 ~/nfs-lock-probe.py --dir /efs/qli/lock-probe --log-dir ~/lock-probe/efs \
        --start-at $START --workers 2 --duration 120 --hold-ms 20 | tee ~/lock-probe/efs/stdout.txt

## 5. Collect, from every host

    (uname -a; cat /etc/os-release | head -3; findmnt -T /efsx -o TARGET,SOURCE,FSTYPE,OPTIONS;
     findmnt -T /efs -o TARGET,SOURCE,FSTYPE,OPTIONS; cat /proc/self/mountstats;
     nfsstat -c 2>/dev/null; sudo dmesg | grep -i -E 'nfs|lockd|sunrpc' | tail -50) > ~/lock-probe/host-info.txt 2>&1
    tar czf ~/lock-probe-$(hostname).tgz -C ~ lock-probe

## 6. Summarize: was it reproduced?

Copy the tarballs of all hosts to one machine and run:

    python3 summarize-probe.py lock-probe-*.tgz

It also takes the `~/lock-probe` directories, or the `stdout.txt` / `.jsonl`
files directly. Always pass the files of all hosts in one call: a cross-host
collision only shows up when the hosts are compared. Give it whatever exists:
FSx only, EFS only, or both, and as many runs as were made. It prints one
section per run (same shared directory and same `--start-at`), so a second
`/efsx` run with other options is reported next to the first one, not mixed
into it. Each section has one row per mode (hosts that took part, iterations,
cross-host and same-host violations, stale lock files, lock waits), the NFS
operation counts per host during the run, and a verdict that applies the
table below: `REPRODUCED in: <modes>`, `NOT REPRODUCED`, or `INCONCLUSIVE`
when no mode ran on two hosts at the same time. Exit status 1 = reproduced,
0 = not reproduced, 2 = inconclusive.

A clean result only counts if the hosts really overlapped. To prove the
detector sees the other host, run a 30 s self test with no lock at all on the
same hosts (same `--start-at` everywhere); the summary must say
`detector self test (nolock): works across hosts`:

    python3 ~/nfs-lock-probe.py --dir /efsx/qli/lock-probe --log-dir ~/lock-probe/selftest \
        --start-at $START --modes nolock --duration 30 | tee ~/lock-probe/selftest/stdout.txt

## Reading the result

Each mode ends with one `summary` line per worker process:

    {"kind": "summary", "mode": "bitbake-shared", "iterations": 812, "violations": 17, "stale_lockfile": 21, ...}

| result                                                             | meaning                                                                                                   |
|--------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| violations in `flock` or `posix`                                   | the NFS locks themselves do not exclude across hosts: a client/server locking problem, AWS territory       |
| violations only in `bitbake` / `bitbake-shared`                    | the locks work; BitBake's unlink + re-create + `stat()` lock-file protocol is what fails on this mount     |
| `bitbake-shared-fresh` clean while `bitbake-shared` fails          | the failure comes from `stat()` being answered from the client's lookup/attribute cache                    |
| `bitbake-shared-nounlink` clean while `bitbake-shared` fails       | the failure needs the unlink; never unlinking the lock file would be a sufficient fix on the BitBake side |
| `stale-lockfile` events                                            | a lock was accepted on a lock file this client already saw as unlinked (`st_nlink == 0`); zero events prove little, `fstat()` may come from the attribute cache |
| `marker-vanished` events                                           | another participant removed the marker while its creator was inside                                       |
| all clean on FSx and on EFS                                        | the probe does not reproduce it; the CI collisions need another trigger (load, delegations, lease events)  |

The `env` lines carry the NFS per-operation counters (`LOCK`, `LOCKU`, `OPEN`,
`REMOVE`, `LOOKUP`, `DELEGRETURN`, ...) at start and end; a growing
`DELEGRETURN` count means the server hands out delegations, which changes how
the client handles locks.

## Options worth varying on a second run

- `--round-ms 1000`: every attempt starts at the same wall-clock instant on all
  hosts, with the lock file absent, which is the CI pattern (two builds
  starting the same download together). Without it the NFS lock polling is
  unfair: after the first seconds one host keeps the lock and the other waits
  for tens of seconds, so a clean mode may have seen almost no contention.
- `--verbose`: logs every entry with the inode held, to line up both hosts at
  the moment of a violation (larger logs).
- `--hold-ms 200` (longer critical section, like a real download)
- `--workers 4` (more contention from each host)
- mount options on one host: `lookupcache=positive`, `actimeo=0`, `nconnect=1`,
  `vers=4.1`, each as a separate run, to see which one makes a difference
