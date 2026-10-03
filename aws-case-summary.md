# AWS support case: opening message (draft)

Subject: FSx for OpenZFS: lock files deleted and re-created by many NFSv4.2
clients go stale ~25x more often than on EFS (delegations?)

We run a CI build farm (GitHub Actions, ephemeral EC2 runners, Ubuntu 24.04,
us-west-2) whose build tool (BitBake) shares one download directory between
all runners. Each download is protected by an exclusive `flock()` on a
per-file lock file in that directory. Since we moved the directory from
Amazon EFS to FSx for OpenZFS (`fs-09119c6fed54104fc`, 2026-09-02), two
runners regularly download the same file at the same time and corrupt it
(12 documented events, none in months on EFS).

We have since reproduced this with a small standalone probe on two EC2
instances that mount both an FSx for OpenZFS file system
(`fs-0960c6bcb45962992`) and an EFS file system (`fs-095b00661f536ba20`), and
we want to be clear about what it shows:

- **FSx enforces the locks.** Plain `flock()` and `lockf()` on a lock file
  that stays in place never let two clients in at once, on FSx or on EFS.
- **The race is in our tool's lock-file protocol, on any NFS server.** BitBake
  deletes the lock file when it releases it, and the next holder re-creates
  it and checks, by name, that the name still points to the file it locked.
  In every overlap the probe recorded (112), the two clients each held a lock
  on a *different* lock file created under the same name. Never deleting the
  lock file removes the problem on both file systems; that fix belongs in
  BitBake and we will take it upstream.
- **But FSx makes it much more frequent.** With both clients starting at the
  same instant, the protocol overlapped in 57 of 119 rounds on FSx and in 1 of
  56 on EFS (same clients, same code, same settings). On FSx the clients
  return delegations (`DELEGRETURN` in `/proc/self/mountstats`, 0.4-1.7 per
  attempt) in exactly the modes that delete and re-create the lock file, and
  almost none in the modes that keep it; on EFS there are none at all.

Mount (identical on the CI runners and the probe hosts):

    fs-0960c6bcb45962992.fsx.us-west-2.amazonaws.com:/fsx on /efsx type nfs4
    (rw,noatime,sync,vers=4.2,rsize=1048576,wsize=1048576,namlen=255,hard,proto=tcp,
     nconnect=16,timeo=600,retrans=2,sec=sys,local_lock=none)

Clients: Ubuntu 24.04.2, kernel 6.8.0-1030-aws; `lease_time=30` on FSx, 90 on
EFS.

Lock sequence of the application (per file, translated to NFS operations):

    open(lock, O_RDWR|O_CREAT|O_APPEND)   OPEN (create if missing)
    flock(fd, LOCK_EX)                    LOCK WRITE_LT, blocking
    fstat(fd); stat(lock)                 GETATTR; LOOKUP/GETATTR or client cache
    -> lock accepted only if both inode numbers match, else retry
    ... critical section ...
    flock(fd, LOCK_EX|LOCK_NB)            LOCK WRITE_LT, non-blocking
    unlink(lock)                          REMOVE by name
    flock(fd, LOCK_UN); close(fd)         LOCKU, CLOSE

Questions:

1. Does the FSx for OpenZFS NFS server grant read or write delegations on
   files a client has just created? Can delegations be disabled or limited
   for a file system, and is that advisable?
2. When client B removes a file on which client A holds a delegation, is the
   delegation recalled and returned before the REMOVE completes, and until
   then can client A's view of the name still resolve to the removed file?
3. Server-side sequence (OPEN, LOCK, LOCKU, REMOVE, CB_RECALL, DELEGRETURN)
   for one overlap on `fs-0960c6bcb45962992`: 2026-10-02 22:56:46-22:56:48 UTC,
   path `/fsx/qli/lock-probe/probe-bitbake-shared.lock`, clients 10.167.6.68
   (holding inode 12592228) and 10.167.6.167 (holding inode 12592127). If
   older logs exist, the first CI event has the same pattern:
   `fs-09119c6fed54104fc`, 2026-09-11 15:20:09-11 UTC, clients 10.185.112.182
   and 10.185.117.172,
   `/fsx/qli/meta-qcom-robotics-sdk/downloads/jinja2-3.1.6.tar.gz.lock`.
4. Recommended mount options for many clients creating, locking and deleting
   the same small files (`lookupcache`, `actimeo`, `nconnect` with NFSv4.2
   locking), and their cost.
5. Does the server send `CB_NOTIFY_LOCK` to clients waiting on a blocked
   lock? Our waiters are woken by client polling, often tens of seconds after
   the lock is free.

Attachments: `aws-fsx-dldir-report.md` (full evidence pack, probe results in
section 9), `pairs.md` (raw CI log lines per event), `incidents.tsv`,
`probe/nfs-lock-probe.py` and `probe/summarize-probe.py` (the reproducer and
its summarizer; standard-library Python, runs in ~14 minutes per file system).
