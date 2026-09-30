#!/usr/bin/env python3
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
# 2x2 (lock protocol x storage) from the scanned jobs of both repos.
# protocol: "new" = bitbake with e8f8ab657 (shared lock, unlock+relock upgrade), "old" = exclusive lock only.
import json, glob, collections, re, os, csv
import os
S = os.path.dirname(os.path.abspath(__file__))
prbase = {}
if os.path.exists(S+"/prbase.tsv"):
    for l in open(S+"/prbase.tsv"):
        p=l.rstrip("\n").split("\t"); prbase[(p[0], p[1])] = p[2]; prbase.setdefault((p[0], "head:" + p[3]), p[2])   # repo, pr number / head branch -> base

def protocol(repo, run):
    wf, ev, branch, created, pr = run[1], run[2], run[3], run[4], run[8] if len(run) > 8 else ""
    if repo == "meta-qcom":
        base = branch if ev != "pull_request" else prbase.get((repo, pr), prbase.get((repo, "head:" + branch), "master" if "wrynose" not in branch else "wrynose"))
        if base == "wrynose" or "wrynose" in wf: return "old"
        return "new" if created >= "2026-08-26T17:36" else "old"
    else:
        base = branch if ev != "pull_request" else prbase.get((repo, pr), prbase.get((repo, "head:" + branch), "main" if "wrynose" not in branch else "wrynose"))
        if base == "wrynose" or "wrynose" in wf: return "old"
        if branch == "ci-fsx-sstate-cache": return "new" if created >= "2026-09-10" else "old"   # PR 380 based on main
        return "new" if created >= "2026-09-08T06:25" else "old"

cells = collections.defaultdict(lambda: dict(jobs=0, fetch=0, failed=0, A=0, Ajobs=set(), Bjobs=set(), files=set(), runs=set()))
unknown = 0
for repo, d in (("meta-qcom", "metaqcom"), ("robotics-sdk", "robotics")):
    jobs = {l.split("\t")[0]: l.rstrip("\n").split("\t") for l in open("%s/%s/alljobs.tsv" % (S, d))}
    runs = {l.split("\t")[0]: l.rstrip("\n").split("\t") for l in open("%s/%s/runs.tsv" % (S, d))}
    seen = set()
    for sub in ("scan", "scan2", "scan-sib", "scan-ctrl"):
        for f in glob.glob("%s/%s/%s/*.json" % (S, d, sub)):
            x = json.load(open(f))
            if x.get("gone") or x["bytes"] < 2000: continue
            j = jobs.get(x["job"]); r = runs.get(j[1]) if j else None
            if not j or not r: continue
            k = (j[1], j[7], j[5])
            if k in seen: continue
            seen.add(k)
            e = " ".join(x.get("env", []))
            st = "/efsx" if "/efsx/" in e else "/efs" if "/efs/" in e else None
            if not st: unknown += 1; continue
            c = cells[(repo, protocol(repo, r), st)]
            c["jobs"] += 1; c["fetch"] += x["fetch_started"]; c["runs"].add(j[1])
            if j[4] == "failure": c["failed"] += 1
            hitsA = [h for h in x["hits"] if h[0] == "A"]
            if hitsA:
                c["Ajobs"].add(x["job"]); c["A"] += len(hitsA)
                for cls, line in hitsA:
                    m = re.search(r"(?:download of|fetching|local file) (\S+)", line)
                    if m: c["files"].add(m.group(1)[:60])
            if any(h[0] == "B" for h in x["hits"]): c["Bjobs"].add(x["job"])
print("jobs with unknown storage (log without cache dir):", unknown)
print("%-13s %-8s %-6s %6s %6s %8s %7s %9s %9s %s" % ("repo", "protocol", "storage", "runs", "jobs", "do_fetch", "failed", "A-jobs", "B-jobs", "distinct files with class A"))
for k in sorted(cells):
    c = cells[k]
    print("%-13s %-8s %-6s %6d %6d %8d %7d %9d %9d %d" % (*k, len(c["runs"]), c["jobs"], c["fetch"], c["failed"], len(c["Ajobs"]), len(c["Bjobs"]), len(c["files"])))
