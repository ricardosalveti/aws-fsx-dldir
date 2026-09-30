#!/usr/bin/env python3
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
# usage: contention2.py <repo-dir> <scan-subdirs comma separated>
# "Contended downloads": the same recipe's do_fetch running on >=2 runners at once where the
# earliest finisher worked for > MINWORK seconds (a real download) and at least one other member
# finished within WAITEND seconds after it (it was blocked behind it). Reports, per storage and
# lock protocol, how many such downloads collided (class A checksum warning on >= 2 runners).
import json, glob, sys, re, collections, datetime, os
import os
S = os.path.dirname(os.path.abspath(__file__))
D, SUBS = sys.argv[1], sys.argv[2].split(",")
MINWORK, WAITEND, DELTA = 2.0, 1.0, 5.0
sys.path.insert(0, S)
def t(ts):
    ts = re.search(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{1,6}", ts).group(0)
    return datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc).timestamp()
exec(open(S + "/cells.py").read().split("cells = collections.defaultdict")[0])   # reuse protocol() and prbase
repo = "meta-qcom" if D.endswith("metaqcom") else "robotics-sdk"
jobs = {l.split("\t")[0]: l.rstrip("\n").split("\t") for l in open(D + "/alljobs.tsv")}
runs = {l.split("\t")[0]: l.rstrip("\n").split("\t") for l in open(D + "/runs.tsv")}
iv = collections.defaultdict(list); seen = set(); njobs = collections.Counter()
for sub in SUBS:
    for f in glob.glob("%s/%s/*.json" % (D, sub)):
        d = json.load(open(f))
        if d.get("gone") or d["bytes"] < 2000 or "fetch" not in d: continue
        j = jobs.get(d["job"]); r = runs.get(j[1]) if j else None
        if not j or not r: continue
        k = (j[1], j[7], j[5])
        if k in seen: continue
        seen.add(k)
        e = " ".join(d.get("env", []))
        st = "/efsx" if "/efsx/" in e else "/efs" if "/efs/" in e else None
        if not st: continue
        cell = (protocol(repo, r), st); njobs[cell] += 1
        hits = set()
        for cls, line in d["hits"]:
            m = re.search(r"(?:WARNING|ERROR): (\S+) do_fetch", line)
            if cls == "A" and m: hits.add(m.group(1))
        for rec, (s, e2, stt) in d["fetch"].items():
            if not s: continue
            end = t(e2) if e2 and t(e2) >= t(s) else None
            iv[(cell, rec)].append((t(s), end, stt, j[7], rec in hits, d["job"]))
res = collections.defaultdict(lambda: [0, 0, 0, []]); gaps = collections.defaultdict(list)   # cell -> [contended, collided, groups, examples]
for (cell, rec), l in iv.items():
    l.sort()
    i = 0
    while i < len(l):
        g = [l[i]]; k = i + 1
        while k < len(l) and l[k][0] - g[0][0] <= DELTA:
            g.append(l[k]); k += 1
        i = k
        if len(set(x[3] for x in g)) < 2: continue
        fin = [x for x in g if x[1]]
        if not fin: continue
        m = min(fin, key=lambda x: x[1])
        if m[1] - m[0] <= MINWORK: continue
        waiters = [x for x in fin if x is not m and x[3] != m[3] and 0 <= x[1] - m[1] <= WAITEND and x[1] - x[0] > 0.5]
        if not waiters: continue
        res[cell][0] += 1
        coll = len(set(x[3] for x in g if x[4])) >= 2
        # gap between the first two starters from different runners
        others = [x for x in g if x[3] != g[0][3]]
        gap = (min(x[0] for x in others) - g[0][0]) * 1000
        gaps[(cell, coll)].append(gap)
        if coll:
            res[cell][1] += 1
            res[cell][3].append((datetime.datetime.fromtimestamp(g[0][0], datetime.timezone.utc).strftime("%m-%d %H:%M:%S"), rec[:40]))
print("jobs per cell:", dict(njobs))
print("%-10s %-8s %10s %9s" % ("protocol", "storage", "contended", "collided"))
for cell in sorted(res):
    print("%-10s %-8s %10d %9d   %s" % (cell[0], cell[1], res[cell][0], res[cell][1], res[cell][3][:4]))

print("\nstart gap between the first two runners (ms), contended downloads:")
for key in sorted(gaps):
    l = sorted(gaps[key]); n = len(l)
    b = collections.Counter("<100" if x < 100 else "<300" if x < 300 else "<1000" if x < 1000 else "<5000" for x in l)
    print("  %-5s %-6s %-9s n=%4d median=%6.0f  buckets: %s" % (key[0][0], key[0][1], "COLLIDED" if key[1] else "clean", n, l[n // 2], dict(b)))
