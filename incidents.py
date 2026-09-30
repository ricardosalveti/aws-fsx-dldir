#!/usr/bin/env python3
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
# Merge the class A events of both repos into incidents: same file, events within 30 s.
import csv, collections, re, sys, datetime
import os
S = os.path.dirname(os.path.abspath(__file__))
def t(ts):
    return datetime.datetime.strptime(ts[:23], "%Y-%m-%dT%H:%M:%S.%f").timestamp()
def fname(line):
    for pat in (r"/downloads/([^\s'\"]+?)(?:_bad-checksum_\w+)?(?:['\"\s]|$)", r"download of (?:crate://crates.io/|gomod://)?(\S+?)(?:;| - )", r"URL: '([^']+)'", r"fetching (?:crate://crates.io/|gomod://)?(\S+?)(?:;|$)"):
        m = re.search(pat, line)
        if m: return m.group(1)
    return ""
ev = []
for repo, d in (("meta-qcom", "metaqcom"), ("robotics-sdk", "robotics")):
    rows = list(csv.DictReader(open("%s/%s/events.tsv" % (S, d)), delimiter="\t", quoting=csv.QUOTE_NONE))
    seen = set()
    for r in rows:
        if r["class"] != "A": continue
        k = (r["runner_name"], r["utc_timestamp"], r["log_line"][:80])
        if k in seen: continue
        seen.add(k); r["repo"] = repo; r["file"] = fname(r["log_line"]); ev.append(r)
# group by recipe (per repo) within 30 s
ev.sort(key=lambda r: r["utc_timestamp"])
inc = []
for r in ev:
    key = (r["repo"], r["recipe_task"].split(":")[0])
    for g in inc:
        if g["key"] == key and t(r["utc_timestamp"]) - g["last"] <= 30:
            g["ev"].append(r); g["last"] = t(r["utc_timestamp"]); break
    else:
        inc.append({"key": key, "ev": [r], "last": t(r["utc_timestamp"])})
out = open(S + "/incidents.tsv", "w")
out.write("n\trepo\tstorage\tfirst_utc\trecipe\tfiles\trunners\tmachines(client ips)\tjobs(run/attempt/job)\tkind\tfirst_warning_gap_ms\n")
n = 0
for g in inc:
    e = g["ev"]; r0 = e[0]
    runners = sorted(set(x["runner_name"][-19:] for x in e))
    machines = sorted(set(x["machine_name"] for x in e if x["machine_name"]))
    jobs = sorted(set("%s/%s/%s" % (x["run_id"], x["run_attempt"], x["job_id"]) for x in e))
    files = sorted(set(x["file"] for x in e if x["file"] and "downloads" not in x["file"]))[:3]
    firsts = sorted(set(min(t(x["utc_timestamp"]) for x in e if x["runner_name"] == rn) for rn in set(x["runner_name"] for x in e)))
    gap = (firsts[-1] - firsts[0]) * 1000 if len(firsts) > 1 else -1
    corrupt = any("zlib.error" in x["log_line"] or "BadZipFile" in x["log_line"] for x in e)
    if len(runners) > 1 and gap <= 5000 and not corrupt:
        kind = "collision (%d runners)" % len(runners)
    elif len(runners) > 1:
        kind = "re-failure on corrupt .tmp (%d runners)" % len(runners) + (", corrupt zip" if corrupt else "")
    else:
        kind = "single runner" + (", corrupt zip" if corrupt else "")
    n += 1
    out.write("\t".join(map(str, [n, r0["repo"], r0["storage"], r0["utc_timestamp"][:23] + "Z", g["key"][1], ";".join(files), ";".join(runners), ";".join(machines), ";".join(jobs), kind, "%.0f" % gap])) + "\n")
print("incidents:", n)
kinds = {}
for l in open(S + "/incidents.tsv"):
    p = l.rstrip("\n").split("\t")
    if p[0] != "n": kinds[p[0]] = (p[1], p[2], p[9].split(" (")[0])
c = collections.Counter(kinds.values())
for k in sorted(c): print("  ", k, c[k])
