# AWS support case: opening message (draft)

Subject: FSx for OpenZFS fs-09119c6fed54104fc — exclusive NFSv4.2 file locks
not excluding a second client when both acquire at the same instant

We run a CI build farm (GitHub Actions, ephemeral EC2 runners, Ubuntu 24.04,
VPC 10.185.0.0/16, us-west-2) whose build tool (BitBake) shares one download
directory between all runners. Each download is protected by an exclusive
`flock()` on a per-file lock file on the same mount. Since we moved that
directory from Amazon EFS to FSx for OpenZFS on 2026-09-02 (meta-qcom) and
2026-09-10 (meta-qcom-robotics-sdk), we see two runners writing the same file
at the same time while each holds what it believes is the exclusive lock. The
same workload ran on EFS for months without a single such event; in the EFS
period of the same log window we count 0 of them (see attached report for the
exact denominators).

Mount (identical on all runners):

    fs-09119c6fed54104fc.fsx.us-west-2.amazonaws.com:/fsx on /efsx type nfs4
    (rw,noatime,sync,vers=4.2,rsize=1048576,wsize=1048576,namlen=255,hard,proto=tcp,
     nconnect=16,timeo=600,retrans=2,sec=sys,local_lock=none)

What we observe (12 documented events, all with instance ids, client IPs and
millisecond timestamps in the attached `pairs.md`):

- Two clients start the same download within 3-800 ms of each other, both run
  the lock sequence below, both proceed, and the file is interleaved (checksum
  failure on both hosts). Example: 2026-09-11 15:20:09.72 UTC, clients
  10.185.112.182 and 10.185.117.172, path
  `/fsx/qli/meta-qcom-robotics-sdk/downloads/jinja2-3.1.6.tar.gz` (lock file
  `...jinja2-3.1.6.tar.gz.lock`). Another: 2026-09-22 04:02-04:04 UTC, clients
  10.185.124.239, 10.185.126.108, 10.185.123.84, path
  `/fsx/qli/meta-qcom/downloads/golang.org.x.sys@v0.48.0.zip`.
- Clients that arrive while another client already holds the lock do wait
  correctly and continue after it releases, so the lock is enforced once held;
  the failure is in acquisition when two clients race.

Lock sequence of the application (per file, translated to NFS operations):

    open(lock, O_RDWR|O_CREAT|O_APPEND)   OPEN (create unchecked)
    flock(fd, LOCK_SH)                    LOCK READ_LT whole file
    [ decides it must download ]
    flock(fd, LOCK_EX|LOCK_NB)            LOCK WRITE_LT non-blocking; if granted:
    unlink(lock)                          REMOVE
    flock(fd, LOCK_UN); close(fd)         LOCKU, CLOSE
    open(lock, O_RDWR|O_CREAT|O_APPEND)   OPEN (re-create)
    flock(fd, LOCK_EX)                    LOCK WRITE_LT blocking
    fstat(fd); stat(lock)                 GETATTR; LOOKUP/GETATTR or client cache
    -> lock accepted only if both inode numbers match
    ... write <file>.tmp, rename to <file> ...
    flock(fd, LOCK_EX|LOCK_NB); unlink(lock); flock(fd, LOCK_UN); close(fd)

Two clients doing this concurrently unlink and re-create the lock file within
milliseconds of each other. We suspect one of: (a) a LOCK being granted on the
file handle of the just-REMOVEd lock file and the client's `stat()` by name
being answered from its cache, or (b) a delegation/recall path (the Linux
client handles `flock()` locally while it holds a delegation). We would like to
understand which server behaviours differ from EFS here.

Questions:

1. For the two windows above, can you provide the server-side sequence of
   OPEN/LOCK/LOCKU/REMOVE/CLOSE for the lock file paths, and confirm whether
   two WRITE_LT locks on the same file were outstanding at the same time, or a
   LOCK was granted on a file handle after the REMOVE of its last name?
2. Does the FSx for OpenZFS NFS server grant read and/or write delegations to
   NFSv4.2 clients? What is the lease time?
3. How does the server order OPEN and REMOVE arriving over different TCP
   connections of the same client (`nconnect=16`), and is `nconnect` recommended
   with NFSv4.2 byte-range locking on this service?
4. Were there any server-side events (failover, maintenance, lease expiry,
   client-id conflicts) on 2026-09-11, 09-12, 09-13, 09-15, 09-22 or 09-24?
5. Recommended mount options for a lock-heavy, many-client workload on this
   file system (`lookupcache`, `actimeo`, `nconnect`, `sync`)?

We can run a standalone reproducer (Python, standard library) on two runners
against the file system and provide `/proc/self/mountstats` deltas, kernel
version and NFS client identifiers; results will follow.

Attachments: `aws-fsx-dldir-report.md` (full evidence pack), `pairs.md` (raw
log lines per event), `incidents.tsv`, `probe/nfs-lock-probe.py`.
