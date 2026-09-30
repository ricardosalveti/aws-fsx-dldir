#!/usr/bin/env python3
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
# usage: analyze.py <repo-dir> <repo-name>
# Builds events.tsv from the scan results and prints class A groups per run attempt.
import json, glob, collections, re, sys, os
D, REPO = sys.argv[1], sys.argv[2]
jobs = {}
for l in open(D + "/alljobs.tsv"):
    p = l.rstrip("\n").split("\t")
    jobs[p[0]] = dict(job=p[0], run=p[1], att=p[2], name=p[3], concl=p[4], start=p[5], end=p[6], runner=p[7])
runs = {}
for l in open(D + "/runs.tsv"):
    p = l.rstrip("\n").split("\t")
    runs[p[0]] = dict(wf=p[1], event=p[2], branch=p[3], created=p[4], concl=p[5], sha=p[7], pr=p[8] if len(p) > 8 else "")

def storage(d):
    e = " ".join(d.get("env", []))
    if "/efsx/" in e: return "/efsx"
    if "/s3efs/" in e: return "/s3efs"
    if "/efs/" in e: return "/efs"
    return "unknown"

def subject(line):
    m = re.search(r"(?:WARNING|ERROR): (\S+) (do_\w+):", line)
    rec = (m.group(1) + ":" + m.group(2)) if m else ""
    f = ""
    for pat in (r"(/downloads/[^\s'\"]+)", r"download of (\S+?)(?:;| - )", r"fetching (\S+?)(?:;|$)", r"(git2/[^\s'\"]+)", r"(/sstate/[^\s'\"]+)"):
        m = re.search(pat, line)
        if m: f = m.group(1); break
    return rec, f

ev = []
scanned = 0
stor = {}
for f in sorted(set(glob.glob(D + "/scan/*.json") + glob.glob(D + "/scan2/*.json") + glob.glob(D + "/scan-sib/*.json") + glob.glob(D + "/scan-ctrl/*.json"))):
    d = json.load(open(f))
    if d.get("gone") or d["bytes"] < 2000: continue
    scanned += 1
    j = jobs.get(d["job"])
    if not j: continue
    j["storage"] = storage(d); j["fetch_started"] = d["fetch_started"]; j["failed_tasks"] = d["failed_tasks"]
    j["machine"] = next((re.search(r"Machine name: '([^']+)'", e).group(1) for e in d["env"] if "Machine name" in e), "")
    j["scanned"] = True
    for cls, line in d["hits"]:
        ts = line[:28]
        rec, fil = subject(line)
        ev.append(dict(repo=REPO, run=j["run"], att=j["att"], job=j["job"], name=j["name"], runner=j["runner"], machine=j["machine"],
                       ts=ts, cls=cls, rec=rec, file=fil, storage=j["storage"], line=line[29:429].replace("\t", " ")))
ev.sort(key=lambda e: (e["ts"], int(e["att"] or 0)))
with open(D + "/events.tsv", "w") as o:
    o.write("repo\trun_id\trun_attempt\tjob_id\tjob_name\trunner_name\tmachine_name\tutc_timestamp\tclass\trecipe_task\tfile_or_repo\tstorage\tlog_line\n")
    for e in ev:
        o.write("\t".join([e["repo"], e["run"], e["att"], e["job"], e["name"], e["runner"], e["machine"], e["ts"], e["cls"], e["rec"], e["file"], e["storage"], e["line"]]) + "\n")
json.dump(jobs, open(D + "/jobs-annotated.json", "w"))
print("scanned jobs:", scanned, " events:", len(ev))
bycls = collections.Counter((e["cls"], e["storage"]) for e in ev)
print("events per class/storage:", dict(bycls))
jobcls = collections.defaultdict(set)
for e in ev: jobcls[(e["cls"], e["storage"])].add(e["job"])
print("jobs per class/storage:", {k: len(v) for k, v in jobcls.items()})
# class A groups: same run attempt, same recipe
g = collections.defaultdict(list)
for e in ev:
    if e["cls"] == "A" and e["rec"]:
        g[(e["run"], e["att"], e["rec"].split(":")[0])].append(e)
print("\nclass A groups (run, attempt, recipe): %d" % len(g))
rows = []
for k, es in g.items():
    runners = sorted(set(e["runner"][-19:] for e in es))
    t = sorted(e["ts"] for e in es)
    rows.append((t[0], k, len(set(e["job"] for e in es)), len(runners), t[-1], es[0]["storage"], runs.get(k[0], {}).get("branch", "")))
for r in sorted(rows):
    print("  %s run=%s att=%s %-45s jobs=%d runners=%d last=%s %s %s" % (r[0][:23], r[1][0], r[1][1], r[1][2][:45], r[2], r[3], r[4][11:23], r[5], r[6][:30]))
