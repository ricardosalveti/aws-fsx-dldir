# nfs-lock-probe: manual run on the CI hosts

Goal: measure, on the real mounts, whether an exclusive lock taken on one host
excludes the other hosts, and whether it is the lock itself or the lock-file
protocol used by BitBake that fails. Run it on FSx (`/efsx`) and on EFS
(`/efs`) with the same hosts, so the two results are comparable.

Needs: 2 or more hosts (ephemeral runner instances are fine) that mount the
same directory, Python 3.8+, clocks synced by chrony (the runners are). The
probe uses only the standard library, writes only to `--dir` (shared) and
`--log-dir` (local), and removes its files from `--dir` when it exits normally.

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
says when the first mode starts and when the last one ends. Exit status is 1
when any violation was seen.

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

Send me the tarballs (or paste the `summary` lines of stdout.txt), and I will
turn them into the numbers for the report.

## Reading the result

Each mode ends with one `summary` line per worker process:

    {"kind": "summary", "mode": "bitbake-shared", "iterations": 812, "violations": 17, "stale_lockfile": 21, ...}

| result                                                             | meaning                                                                                                   |
|--------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| violations in `flock` or `posix`                                   | the NFS locks themselves do not exclude across hosts: a client/server locking problem, AWS territory       |
| violations only in `bitbake` / `bitbake-shared`                    | the locks work; BitBake's unlink + re-create + `stat()` lock-file protocol is what fails on this mount     |
| `bitbake-shared-fresh` clean while `bitbake-shared` fails          | the failure comes from `stat()` being answered from the client's lookup/attribute cache                    |
| `bitbake-shared-nounlink` clean while `bitbake-shared` fails       | the failure needs the unlink; never unlinking the lock file would be a sufficient fix on the BitBake side |
| `stale-lockfile` events                                            | a lock was accepted on a lock file that the server had already unlinked (`st_nlink == 0`)                 |
| all clean on FSx and on EFS                                        | the probe does not reproduce it; the CI collisions need another trigger (load, delegations, lease events)  |

The `env` lines carry the NFS per-operation counters (`LOCK`, `LOCKU`, `OPEN`,
`REMOVE`, `LOOKUP`, `DELEGRETURN`, ...) at start and end; a growing
`DELEGRETURN` count means the server hands out delegations, which changes how
the client handles locks.

## Options worth varying on a second run

- `--hold-ms 200` (longer critical section, like a real download)
- `--workers 4` (more contention from each host)
- mount options on one host: `lookupcache=positive`, `actimeo=0`, `nconnect=1`,
  `vers=4.1`, each as a separate run, to see which one makes a difference
