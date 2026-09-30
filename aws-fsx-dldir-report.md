# Shared BitBake download directory on Amazon FSx for OpenZFS: cross-host lock collisions

Evidence pack for an AWS support case. Prepared 2026-09-30 from the GitHub Actions
logs of `qualcomm-linux/meta-qcom` and `qualcomm-linux/meta-qcom-robotics-sdk`
(2026-07-01 .. 2026-09-29), the git history of both repositories and the BitBake
source. Everything below is traceable to a file in the working directory
(see "Data files" at the end). Statements marked *inference* are not directly
measured.

## 1. Summary

- Since the CI caches moved from Amazon EFS to Amazon FSx for OpenZFS
  (`fs-09119c6fed54104fc`, us-west-2, NFSv4.2), parallel build hosts have
  repeatedly written the same download file at the same time, although each
  host holds an exclusive `flock()` on a per-file lock file on that mount while
  it downloads. The corrupted file then fails every later build until it is
  removed by hand.
- 12 files were corrupted by cross-host collisions, documented with
  millisecond timestamps, runner instance ids and client hostnames (section 4,
  raw lines in `pairs.md`), all on FSx. The same scan over the EFS period
  (9,389 jobs, 843,000 `do_fetch` tasks, 1,839 downloads where two hosts
  contended for the same file) found none (section 6). With the BitBake lock
  protocol held constant (the version in use since 2026-08-26), EFS served 485
  contended downloads (59 with both hosts starting within 300 ms) without a
  collision; FSx served 445 (126) and collided on 12 files.
- The locks are not simply ignored: in the same runs, hosts that arrive while
  another host holds the lock wait for it and then find the finished file
  (section 5). The collisions happen when two hosts start the same download
  within a few hundred milliseconds of each other.
- BitBake's lock protocol unlinks and re-creates the lock file and validates
  the lock with `stat()` by name (section 7). That sequence is sensitive to how
  a NFS server and client handle lookups, unlinked-but-open files and locks on
  them, which is where EFS and FSx for OpenZFS can differ. Which of the two
  mechanisms in section 8 applies has not been measured yet; the probe in
  section 9 measures it directly on both mounts.

## 2. Environment

| item | value | source |
|---|---|---|
| file system | Amazon FSx for OpenZFS `fs-09119c6fed54104fc.fsx.us-west-2.amazonaws.com:/fsx`, server address 10.166.255.235 | `findmnt` on a runner |
| mount options | `rw,noatime,sync,vers=4.2,rsize=1048576,wsize=1048576,namlen=255,hard,proto=tcp,nconnect=16,timeo=600,retrans=2,sec=sys,local_lock=none` | `findmnt` on a runner |
| mount point | `/efsx` on the runner; the build container sees `/efsx/qli/<repo>/downloads` as `/downloads` and `/efsx/qli/<repo>/sstate-cache` as `/sstate` | `.github/workflows/build-yocto.yml`, `.github/actions/compile/action.yml`, job logs |
| previous file system | Amazon EFS mounted at `/efs` (mount options not in the logs; collected by the probe's step 5) | workflow history |
| clients | ephemeral on-demand EC2 runners, Ubuntu 24.04 image (`foundri-prd-u2404-x64-od-eph-<instance id>`), runner group `gha-prd-foundri-selfhosted-rg`, hostnames `ip-10-185-x-y` (VPC 10.185.0.0/16), GitHub runner 2.337.0 | job logs, "Set up job" |
| client kernel / NFS client version | not in the logs; collected by the probe | |
| build container | `ghcr.io/siemens/kas/kas:5.5` (Debian trixie, Python 3.13) run by `kas-container`, cache directories bind-mounted from the host | job logs |
| application | BitBake fetcher, `bb.utils.lockfile()` = `fcntl.flock()` on `<DL_DIR>/<file>.lock`; downloads written to `<DL_DIR>/<file>.tmp` with `wget --continue`, then renamed to `<file>`; `<file>.done` stamp after verification | `lib/bb/fetch/__init__.py`, `lib/bb/fetch/wget.py`, `lib/bb/utils.py` |
| concurrency | 16-20 build jobs per robotics run, up to ~300 per meta-qcom run, each on its own EC2 instance, all sharing one `DL_DIR` and one `SSTATE_DIR` | job listings |

Absolute paths of the affected files on the file system (for server-side logs):
`/fsx/qli/meta-qcom-robotics-sdk/downloads/<file>{,.tmp,.lock,.done}` and
`/fsx/qli/meta-qcom/downloads/<file>{,.tmp,.lock,.done}`.

## 3. Timeline

Two things changed within a week of each other, so both are tracked:

| date (UTC) | repo / branch | change | evidence |
|---|---|---|---|
| 2026-08-13 / 08-20 | bitbake upstream | fetcher switches to a shared lock first, then upgrades to exclusive by *unlocking and re-locking* (`e8f8ab657`, `f56f63b89`) | bitbake git |
| 2026-08-26 17:35 | meta-qcom master | first CI pin of a bitbake with that change (`8042d76f`, bitbake `c6a1288cb1`) | `ci/base.lock.yml` history |
| 2026-09-02 19:11 | meta-qcom master | cache moves from `/efs` to `/efsx` (PR #3054, commit `0df38008`) | git, GitHub API |
| 2026-09-02 19:14 | meta-qcom wrynose | same move (`6cd98f08`); wrynose keeps the *old* bitbake lock protocol (pin `0ad6c1c34a`) throughout | git |
| 2026-09-08 06:24 | robotics-sdk main | bitbake pin with the new lock protocol (`ecaf1b7`, bitbake `75c85c54d9`), still on `/efs` | git |
| 2026-09-10 22:38 | robotics-sdk PR #380 | PR branch builds on `/efsx` with an empty cache (first run 34538407155) | run list, logs |
| 2026-09-11 15:20 | robotics-sdk | first documented collision (jinja2) | logs |
| 2026-09-22 04:03 | meta-qcom master PRs | `golang.org.x.sys@v0.48.0.zip` collision; corrupt `.tmp` fails every docker-compose build until 2026-09-28 | logs |
| 2026-09-28 03:35 | robotics-sdk main | PR #380 merged, main on `/efsx` | GitHub API |
| 2026-09-29 | meta-qcom | workaround merged: bitbake patch renaming the bad `.tmp` (PR #3250), submitted upstream | git, patchwork |

So the control periods are: meta-qcom master on EFS with the new protocol
(2026-08-26 .. 09-02), robotics main on EFS with the new protocol (09-08 ..
09-28), and meta-qcom wrynose on FSx with the old protocol (09-02 ..).

## 4. Incidents

### 4a. Cross-host collisions (two or more hosts corrupt the same download)

Full raw lines for each in `pairs.md`; machine-readable rows in `incidents.tsv`.

| # | UTC | repo | file | hosts (instance id / client) | gap between the two hosts' failures | outcome |
|---|---|---|---|---|---|---|
| 1 | 2026-09-11 15:20:09 | robotics | jinja2-3.1.6.tar.gz | i-00df8fa976000516c / 10.185.112.182, i-03744bef0c0946172 / 10.185.117.172 | task starts 3 ms apart, failures 22 ms apart | one job failed, one recovered from a mirror |
| 2 | 2026-09-12 06:03:17 | robotics | portable-atomic-util-0.2.7.crate | i-082b5f65413b9bb8e / 10.185.126.77, i-04f94f58c3d2efc62 / 10.185.117.77 | 28 ms | both failed |
| 3 | 2026-09-13 18:47:26 | robotics | setuptools_rust-1.13.0.tar.gz | i-…7d5ee05ba5 / 10.185.125.90, i-…0cd22f1940 / 10.185.119.170 | 306 ms | one failed |
| 4 | 2026-09-13 18:57:57 | robotics | glam-0.27.0.crate | i-…3e4d81e819 / 10.185.119.89, i-…2f50406ef6 / 10.185.127.177 | 50 ms | one failed |
| 5 | 2026-09-15 02:16:16 | robotics | untrusted-0.9.0.crate | i-…cba37a7730 / 10.185.126.59, i-…f68d949cb6 / 10.185.122.200 | 11 ms | one failed |
| 6 | 2026-09-24 00:47:03 | robotics | endian-type-0.1.2.crate | i-…88f5250e8a / 10.185.121.136, i-…cd5d7ab8f4 / 10.185.117.57 | 91 ms | one failed |
| 7 | 2026-09-24 00:51:03 | robotics | github.com.anchore.go-struct-converter@v0.1.0.zip | i-…dae001b5fc / 10.185.116.32, i-…e4d66eff15 / 10.185.119.122 | 9 ms | both failed |
| 8 | 2026-09-24 00:51:47 | robotics | github.com.aws.aws-sdk-go-v2.feature.s3.manager@v1.17.10.zip | i-…e032732d06 / 10.185.125.161, i-…c2e2685426 / 10.185.118.182 | 128 ms | one failed |
| 9 | 2026-09-24 00:52:01 | robotics | github.com.cenkalti.backoff.v5@v5.0.3.zip | i-…c2e2685426 / 10.185.118.182, i-…e032732d06 / 10.185.125.161 | 10 ms | one failed |
| 10 | 2026-09-24 00:52:46 | robotics | github.com.cloudflare.circl@v1.6.3.zip | i-…e4d66eff15 / 10.185.119.122, i-…82a3ef4f94 / 10.185.122.56 | 791 ms | one failed |
| 11 | 2026-09-24 00:54:53 | robotics | github.com.google.gofuzz@v1.2.0.zip | i-…dae001b5fc / 10.185.116.32, i-…56e23fbe52 / 10.185.122.230 | 53 ms | one failed |
| 12 | 2026-09-22 04:03:38 | meta-qcom | golang.org.x.sys@v0.48.0.zip | i-…ed352150e1 / 10.185.124.239, i-…8d85855e5a / 10.185.126.108, i-…b4c12eb4a0 / 10.185.123.84 | 124 ms (third host 3 s later hit the already-corrupt file) | all three failed |

Full instance ids for the abbreviated rows are in `incidents.tsv`. Every
collision is on `/efsx`. The two (or three) hosts always reach the file within
about a second of each other, most within 100 ms. The affected recipes are the
ones whose `do_fetch` walks through hundreds of small files (Go modules, Rust
crates) or that run first in every job (native Python packages), i.e. exactly
the places where parallel jobs are most likely to arrive at the same file at
the same instant.

### 4b. Persistent damage

- `golang.org.x.sys@v0.48.0.zip.tmp` (meta-qcom): corrupted 2026-09-22 04:03,
  failed every docker-compose `do_fetch` on 09-22 (attempts 1-3 of run
  35684511207), 09-27 (attempts 1-4 of run 36340100617) and 09-28 (run
  36456733827), on different hosts each time, until the workaround landed.
- `v2.47.0.260601.zip.tmp` (robotics, qairt-sdk, multi-GB): 14 jobs on 14
  hosts were inside the same `do_fetch` when the run was cancelled at 00:55:31
  on 2026-09-24 (starts spread over 00:46:12 .. 00:48:42). Attempts 2, 3 and 4
  (single job each, no concurrency) all died in `zlib.error: invalid stored
  block lengths` while hashing the resumed file. The logs cannot tell whether
  the 14 jobs were downloading or waiting for the lock (a job blocked on the
  lock also logs "do_fetch: Started"), so concurrent writing is *inferred*
  here, not shown. What is shown is that a `.tmp` left by cancelled jobs on a
  `sync` mount was not a clean prefix of the file (a clean prefix resumes
  correctly).
- Shared git clone directories (`DL_DIR/git2/*`) on the robotics FSx cache were
  unusable for 10+ days after the 09-11..09-15 runs (`clone directory not
  available or not up to date`, 14-103 events per day, `robotics/events.tsv`
  class B). This has a competing explanation (fail-fast cancellations killing
  `git` mid-write), so it is listed as context, not as lock evidence.

### 4c. Not attributed to FSx

- `OSError: [Errno 116] Stale file handle` on `/sstate/.../*.siginfo` occurs on
  both file systems (EFS: 2026-08-01, 08-31, 09-02; FSx: 09-03, 09-13). It is
  the expected NFS behaviour when another host replaces a file, and is not part
  of the claim.
- Single-host checksum failures in meta-qcom PRs (camxlib-hamoa, qcom-adreno,
  firmware-qcom-cdt) are recipes under development; their logs are truncated
  before the checksum values, so they are unclassified and excluded.

## 5. The locks do work once held

Run 34538407155 attempt 2, all 16 build jobs, `python3-jinja2-native do_fetch`
(full table in `pairs.md`, block 1, and in the terminal timeline):

```
15:20:09.7198  10.185.112.182  do_fetch Started            <- host A
15:20:09.7228  10.185.117.172  do_fetch Started            <- host B, 3 ms later
15:20:09.8990  10.185.117.172  Checksum failure encountered with download ...
15:20:09.9213  10.185.112.182  Checksum failure encountered with download ...
15:20:10.7806  10.185.112.182  do_fetch Failed
15:20:11.0030  10.185.122.6    do_fetch Started            <- host C
15:20:11.1556  10.185.121.104  do_fetch Started            <- host D
15:20:11.3907  10.185.117.172  do_fetch Succeeded          <- B finishes (mirror fallback)
15:20:11.3985  10.185.121.104  do_fetch Succeeded          <- D, 8 ms after B released the lock
15:20:11.4660  10.185.122.6    do_fetch Succeeded          <- C, 75 ms after
15:20:41 .. 15:20:49  twelve more hosts: do_fetch Started -> Succeeded in 22-37 ms (file already there)
```

C and D arrived while B still held the lock; they took 240-460 ms instead of
the usual 22-37 ms and finished right after B: they were blocked by B's lock on
another host. A and B, which started 3 ms apart, were not serialized. The same
"simultaneous start" pattern holds for every collision in 4a. So the server
does enforce the locks; what fails is the acquisition when two hosts race for
the same lock file at the same moment.

## 6. Storage x lock protocol

Every job log scanned, grouped by storage and by the BitBake lock protocol in
use (from the bitbake revision pinned by the branch, section 3). "Collision
signature" = a job with a `Checksum failure encountered with download` /
`Checksum mismatch` warning; the file-level collisions of section 4 are the
subset where two hosts show it for the same file.

| repo | bitbake lock protocol | storage | runs | jobs scanned | do_fetch tasks | jobs with a collision signature | distinct files |
|---|---|---|---|---|---|---|---|
| meta-qcom | new (shared, then unlock + relock) | /efs (2026-08-26 .. 09-02) | 20 | 440 | 58,616 | 0 | 0 |
| meta-qcom | new | /efsx | 98 | 725 | 42,032 | 23 | 4 (1 collision, 3 unclassified single-host PR recipes) |
| meta-qcom | old (exclusive only) | /efs | 289 | 3,849 | 210,242 | 1 (recipe-side mismatch on an existing file, 2026-08-13) | 1 |
| meta-qcom | old | /efsx (wrynose) | 30 | 717 | 7,355 | 0 | 0 |
| robotics | new | /efs (2026-09-08 .. 09-28) | 55 | 860 | 102,461 | 0 | 0 |
| robotics | new | /efsx | 12 | 365 | 95,160 | 34 | 24 (11 collisions, 2 re-failures on the corrupt qairt `.tmp`, rest single-host) |
| robotics | old | /efs | 243 | 4,240 | 471,250 | 0 | 0 |

Exposure, measured rather than assumed. A "contended download" is a
`do_fetch` of the same recipe running on two or more hosts at once where the
first host to finish worked for more than 2 s (a real download) and another
host finished within 1 s after it (it was blocked behind the first one's
lock). This is exactly the situation the lock exists for:

| storage | contended downloads | of which both hosts started within 300 ms | collided |
|---|---|---|---|
| /efs (both repos, both protocols) | 1,839 | 285 | 0 |
| /efsx (both repos, both protocols) | 457 | 127 | 3 by this strict rule; 12 files in total when counted by checksum warnings on two hosts (section 4a) |
| /efs, new lock protocol only | 485 | 59 | 0 |
| /efsx, new lock protocol only | 445 | 126 | 3 / 12 files |

The strict rule under-counts collisions (a multi-file `do_fetch` such as
docker-compose's 600 Go modules has no "waiter that finished right after"),
so it is only used to compare exposure. Read the table as: EFS served 1,839
contended downloads, 285 of them with near-simultaneous starts, with zero
collisions; FSx served a quarter as many and collided on 12 files.

Caveats:
- meta-qcom EFS/FSx rows other than the control runs count *failed jobs
  only*; a collision where both hosts recover through a mirror is invisible
  there. The control runs (all jobs of the layer-bump PR runs
  33021271604, 33219921169, 33448452323 on EFS; 34544029905, 36511068409 on
  FSx master; 35682855335, 35748666843, 36054286498, 36121245807, 36390613400
  on FSx wrynose) and all robotics runs since 2026-08-20 are complete.
- The FSx caches started empty, the EFS caches were warm; the contended
  download count above is the exposure that matters and is reported per
  storage for that reason.
- The wrynose-on-FSx cell (old lock protocol) had only 12 contended
  downloads, too few to say whether the old protocol is also affected.
- 76 meta-qcom job logs from 2026-07-01..07-02 had expired and 25 could not be
  fetched; 80 jobs had no cache directory in their log and are not attributed.

## 7. What BitBake does on the wire

Per download, `Fetch.download()` (`lib/bb/fetch/__init__.py`) with the new
protocol:

```
lf = lockfile(<file>.lock, shared=True)        # 1
if not verify_donestamp(...):                  # file not there yet
    lf = lockfile_to_exclusive(lf)             # 2 = unlockfile(lf) + lockfile(<file>.lock)
    ... download to <file>.tmp, verify, rename to <file>, write <file>.done ...
unlockfile(lf)                                 # 3
```

`bb.utils.lockfile()` (`lib/bb/utils.py:556-590`):

```
loop:
    lf = open(name, "a+")                  # NFSv4 OPEN (create if missing)
    flock(lf, LOCK_SH | LOCK_EX)           # NFSv4 LOCK, whole file (flock is sent as a byte-range lock)
    st  = fstat(lf)                        # GETATTR (or attribute cache)
    if exists(name) and stat(name).st_ino == st.st_ino:   # LOOKUP+GETATTR, or the client's lookup/attribute cache
        return lf                          # lock accepted
    close(lf); retry                       # the name changed under us
```

`bb.utils.unlockfile()` (`lib/bb/utils.py:598-619`):

```
try:
    flock(lf, LOCK_EX | LOCK_NB)           # LOCK non-blocking: "am I the only holder?"
    unlink(name)                           # REMOVE the lock file (only if that succeeded)
except OSError: pass
flock(lf, LOCK_UN)                         # LOCKU
close(lf)                                  # CLOSE
```

With two hosts A and B starting the same download at the same instant:

1. both take the shared lock on the same lock file (inode I1);
2. both call `lockfile_to_exclusive`: the first one to run `unlockfile` fails
   the non-blocking promotion (the other still holds shared) and just releases;
   the second one succeeds, **unlinks I1**, releases;
3. host A re-opens the name. If its OPEN reached the server before the REMOVE,
   A gets I1 back and its LOCK is granted as soon as B releases, on a file that
   no longer has a name. A now validates the lock with `stat(name)`: on a local
   file system that fails (no name) and A retries; on NFS the answer comes from
   A's cached lookup of the name unless the client revalidates it with the
   server, so A can be told "I1" and **accept a lock on an unlinked file**;
4. host B re-opens the name, creates I2, locks it, validates it (its own cache
   knows about the unlink), and accepts too.

Both hosts now hold "the" exclusive lock and both run `wget --continue` on the
same `<file>.tmp`. This only happens when the two hosts go through step 2 at
the same time, which matches the observed 3-800 ms arrival gaps. With the old
protocol (exclusive lock from the start) the unlink happens once, at the end
of a download, so the window should be much smaller (*inference*; the
wrynose-on-FSx sample in section 6 is too small to confirm it).

The protocol is BitBake's; whether the stale answer in step 3 is possible
depends on the NFS client's dentry/attribute caching (`lookupcache`, `ac`,
directory change attribute handling) and on the server's behaviour for LOCK on
an unlinked-but-open file and for OPEN/REMOVE ordering across `nconnect=16`
connections. Those are the points where EFS (NFSv4.1 via efs-utils) and FSx for
OpenZFS (NFSv4.2, Linux nfsd on ZFS) can legitimately differ.

## 8. Candidate mechanisms and how to tell them apart

| # | mechanism | fits the data? | discriminating test |
|---|---|---|---|
| H1 | FSx does not enforce byte-range locks across clients | no: later arrivals do wait (section 5) | probe modes `flock`, `posix` would show violations |
| H2 | acquisition race in BitBake's unlink/re-create/`stat()` protocol, made visible by NFS lookup caching or by LOCK succeeding on an unlinked file | yes: only simultaneous starts collide, and the new protocol multiplies the unlink/re-create churn | probe: `bitbake-shared` fails, `flock` clean, `bitbake-shared-fresh` / `-nounlink` clean, `stale-lockfile` events |
| H3 | server grants NFSv4 delegations; the client then handles `flock()` locally and the recall path races | possible on FSx (Linux nfsd grants delegations), impossible on EFS (no delegations) | `DELEGRETURN` counter in the probe's `env` records; `flock` mode would also fail |
| H4 | lost lock state (lease expiry under load, client-id collision between cloned instances, server failover/grace) | unlikely: collisions correlate with simultaneous start, not with time | `dmesg` on the runners (`lock reclaim failed`, `state manager`), server-side lease events |

H1 is contradicted by the logs. H2 and H3 are open and only distinguishable by
running the probe on the real mounts. Note that H2 does not make the difference
between EFS and FSx go away: the protocol is the same on both, so whatever
makes the stale answer possible on FSx and not on EFS is still a property of
the file system / mount (caching semantics, unlinked-file handling, delegations,
`nconnect`), which is a legitimate question for AWS even if the fix ends up in
BitBake.

## 9. The missing measurement: `probe/nfs-lock-probe.py`

A standalone Python script (standard library only) that runs the same
lock/critical-section loop on several hosts against one shared directory and
detects any overlap with an `O_CREAT|O_EXCL` marker. Modes: `flock`, `posix`
(plain locks on a persistent lock file), `bitbake`, `bitbake-shared` (the
protocols above, copied from `bb/utils.py`), `bitbake-shared-fresh` and
`bitbake-shared-nounlink` (two candidate fixes). It also records, per mode,
`stale-lockfile` events (lock accepted on a file with `st_nlink == 0`) and the
NFS per-operation counters from `/proc/self/mountstats` before and after
(`LOCK`, `LOCKU`, `OPEN`, `REMOVE`, `LOOKUP`, `DELEGRETURN`, ...), plus
`uname`, mount options and the NFS client identifier.

Validated locally on ext4 with 6 processes: 0 violations in every lock mode,
4,006 violations in the self-test mode without locks (`nolock`).

Instructions to run it by hand on two runners, on `/efsx` and then on `/efs`,
are in `probe/README.md`. One run of each takes ~14 minutes. The results decide
between H1/H2/H3 and give AWS the exact operation mix.

## 10. What to ask AWS

1. For `fs-09119c6fed54104fc` at 2026-09-11 15:20:09-11 UTC (clients
   10.185.112.182 and 10.185.117.172, file
   `/fsx/qli/meta-qcom-robotics-sdk/downloads/jinja2-3.1.6.tar.gz.lock`) and
   2026-09-22 04:02:00-04:04 UTC (clients 10.185.124.239, 10.185.126.108,
   10.185.123.84, file
   `/fsx/qli/meta-qcom/downloads/golang.org.x.sys@v0.48.0.zip.lock`): the
   server-side sequence of OPEN / LOCK / LOCKU / REMOVE for that path, and
   whether two WRITE_LT locks were held at the same time, or a LOCK was granted
   on an unlinked file handle.
2. Whether the FSx for OpenZFS NFS server grants read/write delegations to
   NFSv4.2 clients, and the lease time in effect.
3. The server's behaviour for LOCK requests on a file that has been REMOVEd
   while other clients still hold it open, and for the ordering of OPEN and
   REMOVE arriving over different connections of one `nconnect=16` client.
4. Any known interaction between `nconnect` and NFSv4.x locking on FSx for
   OpenZFS, and the recommended mount options for lock-heavy workloads
   (`lookupcache`, `actimeo`, `nconnect`).
5. Whether there were server events (failover, maintenance, lease expiry,
   client-id conflicts) for this file system on 2026-09-11, 09-12, 09-13,
   09-15, 09-22 and 09-24.

## 11. Data files

All in this repository:

- `incidents.tsv`, `pairs.md` — the incidents and their raw log lines (`pairs.md` part A: the 12 simultaneous collisions; part B: sequential re-failures on an already corrupt `.tmp`)
- `metaqcom/events.tsv`, `robotics/events.tsv` — every class A/B/C hit (format in `SIGNATURES.md`)
- `metaqcom/runs.tsv`, `robotics/runs.tsv` — all workflow runs in the window; `*/alljobs.tsv` — every job of every attempt of the inspected runs (runner name, times, conclusion)
- `metaqcom/scan*/*.json`, `robotics/scan*/*.json` — per-job extracts (hits, environment lines, `do_fetch` intervals)
- `cells.txt`, `metaqcom/contention.txt`, `robotics/contention.txt`, `incidents.txt` — the outputs behind section 6
- `aws-case-summary.md` — draft opening message for the support case
- `robotics/full/*.log` — full logs of run 35938315722 (qairt case)
- `cells.py`, `contention2.py`, `incidents.py`, `pairs.py`, `timeline.py`, `scanlog.py`, `finalize-analysis.sh` — the tooling
- `probe/nfs-lock-probe.py`, `probe/README.md` — the probe and how to run it

Method caveats: GitHub keeps logs 90 days, so nothing before 2026-07-01 was
available; job logs carry the runner's own timestamps (chrony-synced, sub-ms
agreement between hosts in the jinja2 case); "collision" requires a checksum
warning on at least two hosts for the same file within 30 s, so a collision
where one host's wget finished before the other started writing is counted as
a single-host event.
