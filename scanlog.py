#!/usr/bin/env python3
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
# Stream a GitHub Actions job log on stdin, keep only what the AWS report needs.
# usage: scanlog.py <job_id> <outdir>   -> <outdir>/<job_id>.json
import sys, re, json

A = re.compile(r"Checksum failure encountered with download|Checksum mismatch|Checksum failure fetching|_bad-checksum_|Mirror checksum failure|returned success for url .* but .* doesn.t exist|resulted in a zero size file|zlib\.error|BadZipFile|File is not a zip file", re.I)
B = re.compile(r"clone directory not available or not up to date|even from upstream|nonexistent object|fatal: bad object|did not send all necessary objects|index-pack failed|loose object .* is corrupt|packfile .* (is corrupt|cannot be accessed)|shallow file has changed|not a git repository", re.I)
C = re.compile(r"Stale file handle|Errno 116|No locks available|Errno 37\b|Input/output error|\.nfs[0-9a-f]{12,}|Device or resource busy|Unable to acquire lock|Waiting for lock", re.I)
ENV = re.compile(r"Runner name:|Machine name:|Runner group name:|Current runner version|Linux version|kas-container|KAS_IMAGE_VERSION|ghcr\.io/siemens/kas|Cache directory:|Using SSTATE cache|/efsx?/|/s3efs/|Build Configuration|BB_VERSION|^\S+ drwx", re.I)
FETCH = re.compile(r"NOTE: recipe (\S+): task do_fetch: (Started|Succeeded|Failed)")
TASKERR = re.compile(r"ERROR: Task \((?:[^)]*/)?([^/)]+\.bb:do_[a-z_]+)\) failed")
SUMMARY = re.compile(r"Tasks Summary:|Sstate summary:|sstate reuse")

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
job, outdir = sys.argv[1], sys.argv[2]
res = {"job": job, "bytes": 0, "lines": 0, "first_ts": None, "last_ts": None,
       "fetch_started": 0, "fetch_failed": 0, "hits": [], "env": [], "failed_tasks": [], "summary": [], "fetch_events": {}, "fetch": {}}
hit_recipes = set()
pending = {}
for raw in sys.stdin.buffer:
    res["bytes"] += len(raw); res["lines"] += 1
    line = ANSI.sub("", raw.decode("utf-8", "replace").rstrip("\r\n"))
    ts = line[:28] if re.match(r"\d{4}-\d\d-\d\dT", line) else None
    if ts:
        if not res["first_ts"]: res["first_ts"] = ts
        res["last_ts"] = ts
    m = FETCH.search(line)
    if m:
        if m.group(2) == "Started": res["fetch_started"] += 1
        if m.group(2) == "Failed": res["fetch_failed"] += 1
        pending.setdefault(m.group(1), []).append(line[:200])
        # every do_fetch interval: recipe -> [start, end, status]
        iv = res["fetch"].setdefault(m.group(1), [None, None, None])
        if m.group(2) == "Started": iv[0] = line[:28]
        else: iv[1] = line[:28]; iv[2] = m.group(2)
        continue
    cls = "A" if A.search(line) else "B" if B.search(line) else "C" if C.search(line) else None
    if cls:
        if len(res["hits"]) < 400:
            res["hits"].append([cls, line[:500]])
        r = re.search(r"(?:WARNING|ERROR): (\S+) do_(?:fetch|unpack)", line)
        if r: hit_recipes.add(r.group(1))
        continue
    m = TASKERR.search(line)
    if m: res["failed_tasks"].append(m.group(1)); continue
    if len(res["env"]) < 60 and res["lines"] < 4000 and "aws/dist" not in line and ENV.search(line):
        res["env"].append(line[:300]); continue
    if SUMMARY.search(line) and len(res["summary"]) < 12:
        res["summary"].append(line[:250])
# keep do_fetch start/stop lines only for recipes that had a hit
for r in hit_recipes:
    if r in pending: res["fetch_events"][r] = pending[r][:20]
with open("%s/%s.json" % (outdir, job), "w") as f:
    json.dump(res, f)
