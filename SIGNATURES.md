# Shared conventions for the FSx/EFS DL_DIR evidence mining

All access is READ-ONLY. Never `git push`, never post/comment/review on GitHub,
never `git checkout`/switch branches in ~/projects/qcom/* (use `git show <ref>:<path>`),
never start builds. Use `gh api` / `gh run` / `gh pr view` / `gh issue view` only to read.
Check `gh api rate_limit --jq .resources.core` before bulk downloads and keep at least
800 requests in reserve ; the logs endpoint is rate limited even when `rate_limit` reports a full quota.

Job log download: `gh api repos/<owner>/<repo>/actions/jobs/<job_id>/logs`
Jobs of a run (all attempts): `gh api --paginate "repos/<owner>/<repo>/actions/runs/<run_id>/jobs?filter=all&per_page=100"`
Jobs carry `runner_name` (EC2 instance id based) and `run_attempt`.

## Signature classes (grep -a -i -E)

Class A - plain (wget/crate/gomod/npm) downloads, shared `<file>.tmp`:
  Checksum failure encountered with download|Checksum mismatch|Checksum failure fetching|_bad-checksum_|Mirror checksum failure|returned success for url .* but .* doesn.t exist|resulted in a zero size file|zlib\.error|BadZipFile|File is not a zip file

Class B - shared git clone directories (DL_DIR/git2):
  clone directory not available or not up to date|even from upstream|nonexistent object|fatal: bad object|did not send all necessary objects|index-pack failed|loose object .* is corrupt|packfile .* (is corrupt|cannot be accessed)|shallow file has changed|not a git repository

Class C - NFS level errors on the shared mount (/efs, /efsx, container paths /downloads, /sstate):
  Stale file handle|Errno 116|No locks available|Errno 37|Input/output error|\.nfs[0-9a-f]{12,}|Device or resource busy|Unable to acquire lock|Waiting for lock

## Event record (TSV, one line per log hit, header included)
repo  run_id  run_attempt  job_id  job_name  runner_name  utc_timestamp(ms)  class  recipe_task  file_or_repo  storage(/efs|/efsx|/s3efs|unknown)  log_line(trimmed to 400 chars)

Storage must be established from evidence (workflow file at that commit: CACHE_DIR,
or mount/ls output in the log), not assumed from the date.

## What makes an event valuable for the AWS report
A "pair": two jobs on DIFFERENT runners (runner_name) working on the SAME file/repo
at overlapping times, i.e. both inside what bitbake's per-file lock
(`DL_DIR/<file>.lock`, fcntl.flock -> NFSv4 LOCK) should make mutually exclusive.
For pairs, keep the raw log lines of both sides with millisecond timestamps
(bitbake "task do_fetch: Started/Succeeded/Failed" lines and the error/warning lines).
