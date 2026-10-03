# Shared BitBake download directory on NFS: lock-file collisions, rare on EFS, frequent on FSx for OpenZFS

Evidence pack for an AWS support case and for the BitBake upstream discussion.
Prepared 2026-09-30 from the GitHub Actions logs of `qualcomm-linux/meta-qcom`
and `qualcomm-linux/meta-qcom-robotics-sdk` (2026-07-01 .. 2026-09-29), the
git history of both repositories and the BitBake source; updated 2026-10-03
with the results of `probe/nfs-lock-probe.py` run on two hosts against FSx
for OpenZFS and Amazon EFS (section 9). Statements marked *inference* are not
directly measured.

## 1. Summary

- Since the CI caches moved from Amazon EFS to Amazon FSx for OpenZFS
  (`fs-09119c6fed54104fc`, us-west-2, NFSv4.2), parallel build hosts have
  repeatedly written the same download file at the same time, although each
  host takes an exclusive `flock()` on the file's lock file before it
  downloads. The corrupted file then fails every later build until it is
  removed by hand. 12 such collisions are documented with millisecond
  timestamps, instance ids and client addresses (section 4), all on FSx; the
  EFS period of the same logs has none (section 6).
- **The NFS locks are not the problem.** A two-host probe (section 9)
  reproduced the collision on FSx and also, much more rarely, on EFS. In all
  112 overlaps of the two runs that logged the lock file held at every entry,
  the two hosts held exclusive locks on two *different* lock files that had the same name at different moments; two
  locks on the same file never coexisted, and plain `flock()` / `lockf()` on a
  lock file that stays in place never failed on either file system.
- **The cause is BitBake's lock-file protocol.** `bb.utils.unlockfile()`
  deletes the lock file and `bb.utils.lockfile()` re-creates it and accepts
  the lock after checking, by name, that the name still points to the file it
  locked (section 7). Across NFS clients that check can pass on two hosts at
  once. The same probe with the lock file never deleted had 0 collisions in
  119 rounds in which both hosts started together, against 57 of 119 with the
  protocol BitBake uses today.
- **FSx makes it far more frequent.** When both hosts start in the same
  round, the current protocol collides in 57 of 119 rounds on FSx and in 1 of
  56 on EFS. The older exclusive-only protocol collides in 5 of 119 on FSx and
  0 of 65 on EFS. On FSx the server hands out NFSv4 delegations exactly in the
  modes that delete and re-create the lock file, and EFS hands out none
  (section 9); that the delegations are what makes FSx worse is an
  *inference* and the main question for AWS (section 10).
- Fix on the BitBake side: never delete the lock file (section 8). The
  questions for AWS are now about delegation and name-caching behaviour on
  FSx for OpenZFS, not about lock enforcement.

## 2. Environment

| item | value | source |
|---|---|---|
| file system | Amazon FSx for OpenZFS `fs-09119c6fed54104fc.fsx.us-west-2.amazonaws.com:/fsx`, server address 10.166.255.235 | `findmnt` on a runner |
| mount options | `rw,noatime,sync,vers=4.2,rsize=1048576,wsize=1048576,namlen=255,hard,proto=tcp,nconnect=16,timeo=600,retrans=2,sec=sys,local_lock=none` | `findmnt` on a runner |
| mount point | `/efsx` on the runner; the build container sees `/efsx/qli/<repo>/downloads` as `/downloads` and `/efsx/qli/<repo>/sstate-cache` as `/sstate` | `.github/workflows/build-yocto.yml`, `.github/actions/compile/action.yml`, job logs |
| previous file system | Amazon EFS mounted at `/efs` (mount options not in the logs; collected by the probe's step 5) | workflow history |
| clients | ephemeral on-demand EC2 runners, Ubuntu 24.04 image (`foundri-prd-u2404-x64-od-eph-<instance id>`), runner group `gha-prd-foundri-selfhosted-rg`, hostnames `ip-10-185-x-y` (VPC 10.185.0.0/16), GitHub runner 2.337.0 | job logs, "Set up job" |
| client kernel / NFS client version | not in the CI logs; the probe hosts (same image family) run Ubuntu 24.04.2, kernel `6.8.0-1030-aws`, Python 3.12.3 | probe `env` records |
| probe hosts | `ip-10-167-6-167`, `ip-10-167-6-68` (VPC 10.167.0.0/16), both mounting the two file systems below | probe `env` records, `host-info.txt` |
| probe FSx | FSx for OpenZFS `fs-0960c6bcb45962992.fsx.us-west-2.amazonaws.com:/fsx`, server 10.167.7.111, **not** the CI file system above; same mount options as the CI; `lease_time=30`; server implementation id empty | `findmnt`, `/proc/self/mountstats` |
| probe EFS | Amazon EFS `fs-095b00661f536ba20.efs.us-west-2.amazonaws.com:/`, `rw,relatime,vers=4.1,rsize=1048576,wsize=1048576,namlen=255,hard,noresvport,proto=tcp,timeo=600,retrans=2,sec=sys,local_lock=none`; `lease_time=90`; implementation id `Amazon EFS` | `findmnt`, `/proc/self/mountstats` |
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
| 2026-09-29 | meta-qcom, bitbake | workaround merged: bitbake patch renaming the bad `.tmp` (meta-qcom PR #3250); merged upstream as bitbake `37b9c56ae` | git, patchwork |
| 2026-10-02 | probe | two-host probe runs on FSx (16:02, 21:15, 22:50 UTC) and EFS (23:07 UTC) | section 9 |

So the control periods are: meta-qcom master on EFS with the new protocol
(2026-08-26 .. 09-02), robotics main on EFS with the new protocol (09-08 ..
09-28), and meta-qcom wrynose on FSx with the old protocol (09-02 ..). The
probe adds the comparison the CI logs could not make: the new protocol
collides on EFS too, at a rate low enough to explain zero CI events there, and
the old protocol collides on FSx too, about ten times less often than the new
one (section 9).

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
the same lock file at the same moment. The probe (section 9) confirms both
halves on the real file systems.

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
  downloads, too few to say from the logs whether the old protocol is also
  affected. The probe says it is, at about a tenth of the new protocol's rate
  (section 9).
- The probe's rates are consistent with these counts: about 2% per
  simultaneous start on EFS predicts about one collision in the 59 EFS starts
  within 300 ms (0 observed), and FSx collided on 12 files in 126 such starts
  (about 10%). The probe's FSx rate is higher (48%) because its starts are
  aligned to the millisecond, which CI starts rarely are.
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

The old protocol takes the exclusive lock directly in step 1 and has no
step 2.

`bb.utils.lockfile()` (`lib/bb/utils.py:556-590`):

```
loop:
    lf = open(name, "a+")                  # NFSv4 OPEN (create if missing)
    flock(lf, LOCK_SH | LOCK_EX)           # NFSv4 LOCK, whole file (flock is sent as a byte-range lock)
    st  = fstat(lf)                        # GETATTR (or attribute cache)
    if exists(name) and stat(name).st_ino == st.st_ino:   # LOOKUP+GETATTR, or the client's lookup/attribute cache
        return lf                          # lock accepted
    close(lf); retry                       # the name changed under us
                                           # (any OSError, ESTALE included, also just retries)
```

`bb.utils.unlockfile()` (`lib/bb/utils.py:598-619`):

```
try:
    flock(lf, LOCK_EX | LOCK_NB)           # LOCK non-blocking: "am I the only holder?"
    unlink(name)                           # REMOVE by *name*, whatever file the name points to now
except OSError: pass
flock(lf, LOCK_UN)                         # LOCKU
close(lf)                                  # CLOSE
```

The protocol is correct only if every participant sees the name and the file
behind it the same way the server does at the moment it checks. On one
machine that holds: two processes on the same probe host never overlapped in
2,564 entries of the current protocol (section 9). Across NFS clients it does
not. What the probe measured, for every one of the 112 overlaps of the two
runs that logged the lock file held at every entry (FSx and EFS):

- each of the two hosts held an exclusive lock, on two **different** lock
  files (inodes), both of which had been created under the same name;
- each had accepted its lock with the check above passing; on FSx 100 of the
  110 violating hosts passed it on the first attempt, without a retry;
- in 69 of the FSx overlaps the host that entered second held the **older**
  file, in 41 the **newer** one.

Two paths fit these facts (*inference*, the probe cannot see inside the NFS
client):

1. A host checks its lock against a stale view of the name: the name already
   points to a newer file on the server (or to none), but the host's client
   still answers `stat(name)` with the file it holds. That is the "older file"
   case.
2. A host that holds a lock on a file whose name has already moved on calls
   `unlockfile()`, and `unlink(name)` removes the **current** lock file of
   another host that is inside. The next host to arrive creates a new file,
   locks it, its check passes, and it enters next to the host whose file was
   removed. That is the "newer file" case, and it is a consequence of path 1,
   not an independent one.

Re-checking with a new `open()` instead of `stat()` (`bitbake-shared-fresh`)
did not help on either file system, so the stale view is not limited to
`stat()`'s attribute cache. Never deleting the lock file (`-nounlink`) removes
both paths: there is only ever one file under the name.

Why FSx is so much worse than EFS is not measured. What is measured: on FSx
the clients return 0.4-1.7 delegations (`DELEGRETURN`) per entry, but only in
the modes that delete and re-create the lock file;
in the modes where the file stays (`flock`, `posix`, `-nounlink`) there are
almost none, and on EFS there are none at all (section 9). A client holding
a delegation for a file may answer opens and attribute requests for it
without asking the server (*inference*, not verified against the kernel
source for this case), which would explain stale answers that even a fresh
`open()` cannot avoid.

## 8. Mechanisms, tested

| # | mechanism | result |
|---|---|---|
| H1 | FSx does not enforce byte-range locks across clients | **refuted by measurement**: plain `flock()`/`lockf()` 0 overlaps on FSx (and EFS); all 112 attributed overlaps were on different lock files, none on the same file |
| H2 | acquisition race in BitBake's delete/re-create/check-by-name protocol | **confirmed**: fails on FSx and EFS, never on one host, 0 with the lock file never deleted (`-nounlink`) under the same contention |
| H3 | NFSv4 delegations on FSx | **amplifier, not an independent failure**: delegations appear only in the re-create modes and only on FSx, where the rate is ~25x EFS's (at least ~5x: EFS had only 2 events); the link between the two is *inferred* |
| H4 | lost lock state (lease expiry, client-id collision, failover) | no evidence: no lock-recovery or state-manager messages in the probe hosts' kernel logs; overlaps follow simultaneous starts, not time |

Consequence for BitBake: the lock file must not be deleted while other hosts
may be using it (`-nounlink` mode). That is a new change to
`bb.utils.unlockfile()` (and so to `lockfile_to_exclusive()`, which calls
it): BitBake master still deletes the lock file on every release
(`lib/bb/utils.py`, `os.unlink(lf.name)`). The deletion keeps `DL_DIR` free
of `.lock` files; leaving them in place costs one empty file per download.
The `.tmp` rename patch (meta-qcom PR #3250, merged in BitBake master as
`37b9c56ae`) fixes a different part: it stops a corrupt partial download from
failing every later build, but does not stop two hosts from writing it at
once.

Consequence for operations: blocking `flock()` on these mounts is resolved by
client-side polling. Waiters routinely waited tens of seconds (up to 134 s on
FSx, median 3.6 s for plain `flock` on EFS in the round runs), long after the
holder released. That is separate from the collisions and plausibly behind
the `do_fetch` stall pile-ups seen in CI.

## 9. Probe results: `probe/nfs-lock-probe.py`

A standalone Python script (standard library only) that runs the same
lock/critical-section loop on several hosts against one shared directory and
detects any overlap with an `O_CREAT|O_EXCL` marker created inside the
critical section. Modes: `flock`, `posix` (plain locks on a lock file that
stays in place), `bitbake` (the old protocol), `bitbake-shared` (today's
protocol, both copied from `bb/utils.py`), and two candidate fixes:
`bitbake-shared-fresh` (check with a new `open()`) and
`bitbake-shared-nounlink` (never delete the lock file). With `--verbose`
every entry is logged with the inode of the lock file it holds, which is what
attributes each overlap to the other host and tells "same file" from
"different file". `probe/summarize-probe.py` turns the logs of all hosts into
the tables below. How to run both: `probe/README.md`.

Runs on 2026-10-02, hosts `ip-10-167-6-167` and `ip-10-167-6-68`, 2 workers
per host, 20 ms inside the critical section:

| run (UTC) | file system | starts | result |
|---|---|---|---|
| 16:02 | FSx `fs-0960c6bcb45962992` | free-running | `bitbake-shared` 6 overlaps, `-fresh` 3; `flock`/`posix` 0 in ~7,800 entries |
| 16:22 | same FSx, **one host only** | free-running | 0 overlaps in every mode (2,564 `bitbake-shared` entries) |
| 21:15 | same FSx | free-running | `bitbake-shared` 5, `-fresh` 2; `flock`/`posix` 0 in ~7,800 entries |
| 22:50 | same FSx | aligned to 1 s rounds, `--verbose` | table below |
| 23:07 | EFS `fs-095b00661f536ba20` | aligned to 1 s rounds, `--verbose` | table below |

The free-running runs show the problem but compare modes poorly: after the
first seconds of a mode one host keeps winning the lock and the other waits,
so most entries see no contention. The aligned runs start every attempt of
every process at the same wall-clock second, which is the CI pattern (two
builds starting the same download together), and count per round in which
both hosts started:

| mode | FSx: rounds with an overlap | EFS: rounds with an overlap |
|---|---|---|
| `flock` | 0 / 88 | 0 / 19 |
| `posix` | 0 / 119 | 0 / 23 |
| `bitbake` (old protocol) | 5 / 119 (4%) | 0 / 65 |
| `bitbake-shared` (today's protocol) | **57 / 119 (48%)** | **1 / 56 (2%)** |
| `bitbake-shared-fresh` | 48 / 119 (40%) | 1 / 50 (2%) |
| `bitbake-shared-nounlink` | **0 / 119** | 0 / 36 |

Every overlap in both aligned runs (110 on FSx, 2 on EFS) was between the two
hosts, each holding a lock on a different lock file. EFS completed fewer
rounds per mode because its blocking locks waited longer (section 8), which
is why its denominators are smaller.

NFS operations per entry on FSx, aligned run, per host:

| mode | LOCK | OPEN | REMOVE | DELEGRETURN |
|---|---|---|---|---|
| `flock` | 1.8-2.9 | 1.0 | 1.0 | 0.0-0.1 |
| `posix` | 1.8-3.2 | 1.0 | 1.0 | 0.0 |
| `bitbake` | 2.4-3.9 | 2.1-2.5 | 1.9-2.0 | 0.4-1.2 |
| `bitbake-shared` | 5.0-5.2 | 2.6-2.9 | 1.6-2.3 | 0.7-1.6 |
| `bitbake-shared-fresh` | 5.1-5.5 | 3.0-3.1 | 1.5-2.5 | 1.1-1.7 |
| `bitbake-shared-nounlink` | 4.9-5.6 | 1.0 | 1.0 | 0.0 |

On EFS `DELEGRETURN` is 0 in every mode. (`REMOVE` is 1.0 in the modes that
never delete the lock file because the probe's marker is created and deleted
once per entry.) `ESTALE` errors during lock acquisition, which
`bb.utils.lockfile()` silently retries, occurred in 173 of 1,561 BitBake-mode
entries on FSx and 287 of 1,047 on EFS.

Validated locally on ext4 (one machine, two simulated hosts): 0 overlaps in
every lock mode, and the no-lock self test sees the other host.

## 10. What to ask AWS

The question is no longer whether FSx enforces locks; it does. It is why the
same client-side protocol produces a stale view of a name far more often on
FSx for OpenZFS than on EFS (about 25 times as a point estimate, at least
about 5 times at 95% confidence, since EFS had only 2 events in 106
rounds), and whether that can be tuned.

1. Does the FSx for OpenZFS NFS server grant read or write delegations on
   files a client has just created (we see 0.4-1.7 `DELEGRETURN` per entry
   when the lock file is deleted and re-created, about 0 when it stays in
   place, and none on EFS)? Can delegations be
   disabled or limited for a file system, and is that advisable?
2. When client B removes a file on which client A holds a delegation, is the
   delegation recalled and returned before the REMOVE completes, and until
   then can client A's view of the name still resolve to the removed file?
3. For one overlap on the probe file system `fs-0960c6bcb45962992`:
   2026-10-02 22:56:46-22:56:48 UTC, path
   `/fsx/qli/lock-probe/probe-bitbake-shared.lock` (and the matching
   `probe-bitbake-shared.marker`), clients 10.167.6.68 (inside from
   22:56:47.015, holding a lock on inode 12592228) and 10.167.6.167 (inside at
   22:56:47.021, holding a lock on inode 12592127), can you provide the server-side sequence of OPEN, LOCK, LOCKU,
   REMOVE, CB_RECALL and DELEGRETURN for that path? The first CI collision
   (`fs-09119c6fed54104fc`, 2026-09-11 15:20:09-11 UTC, clients
   10.185.112.182 and 10.185.117.172,
   `/fsx/qli/meta-qcom-robotics-sdk/downloads/jinja2-3.1.6.tar.gz.lock`) is
   the same pattern if older logs are still available.
4. Recommended client mount options for this access pattern (many clients
   creating, locking and deleting the same small files): `lookupcache`,
   `actimeo`, `nconnect=16` with NFSv4.2 locking, and their cost.
5. Does the server send `CB_NOTIFY_LOCK` to clients waiting on a blocked
   lock? Waiters here are woken by client polling, tens of seconds after the
   lock is free.

## 11. Data files

All in this repository:

- `incidents.tsv`, `pairs.md` — the incidents and their raw log lines (`pairs.md` part A: the 12 simultaneous collisions; part B: sequential re-failures on an already corrupt `.tmp`)
- `metaqcom/events.tsv`, `robotics/events.tsv` — every class A/B/C hit (format in `SIGNATURES.md`)
- `metaqcom/runs.tsv`, `robotics/runs.tsv` — all workflow runs in the window; `*/alljobs.tsv` — every job of every attempt of the inspected runs (runner name, times, conclusion)
- `metaqcom/scan*/*.json`, `robotics/scan*/*.json` — per-job extracts (hits, environment lines, `do_fetch` intervals)
- `cells.txt`, `metaqcom/contention.txt`, `robotics/contention.txt`, `incidents.txt` — the outputs behind section 6
- `aws-case-summary.md` — opening message for the support case
- `robotics/full/*.log` — full logs of run 35938315722 (qairt case)
- `cells.py`, `contention2.py`, `incidents.py`, `pairs.py`, `timeline.py`, `scanlog.py`, `finalize-analysis.sh` — the tooling
- `probe/nfs-lock-probe.py`, `probe/summarize-probe.py`, `probe/README.md` — the probe, its summarizer and how to run them

The raw probe logs of section 9 (one tarball per host) are not in this
repository; they are available on request.

Method caveats: GitHub keeps logs 90 days, so nothing before 2026-07-01 was
available; job logs carry the runner's own timestamps (chrony-synced, sub-ms
agreement between hosts in the jinja2 case); "collision" requires a checksum
warning on at least two hosts for the same file within 30 s, so a collision
where one host's wget finished before the other started writing is counted as
a single-host event. The probe ran on a different FSx file system than the
CI, with the same mount options; the EFS file system it used is not known to
be the one the CI used before 2026-09-02.
