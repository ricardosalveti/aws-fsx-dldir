#!/usr/bin/env python3
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
# Evidence blocks for every cross-host collision: raw log lines of every side, ms timestamps.
import csv, json, glob, re, datetime, collections
import os
S = os.path.dirname(os.path.abspath(__file__))
def t(ts): return datetime.datetime.strptime(ts[:23], "%Y-%m-%dT%H:%M:%S.%f").timestamp()
out = open(S + "/pairs.md", "w")
out.write("# Download collisions on FSx: raw evidence\n\n")
blocks = {}
out.write("Each block: one file, every runner that reported a checksum problem on it within 30 s, "
          "with the runner's instance id, its hostname (= client IP in the VPC) and the raw job log lines. "
          "`do_fetch Started/Succeeded/Failed` lines are BitBake task events; the lock is taken inside the task.\n\n")
n = 0
for repo, d in (("robotics-sdk", "robotics"), ("meta-qcom", "metaqcom")):
    rows = list(csv.DictReader(open("%s/%s/events.tsv" % (S, d)), delimiter="\t", quoting=csv.QUOTE_NONE))
    jobs = {l.split("\t")[0]: l.rstrip("\n").split("\t") for l in open("%s/%s/alljobs.tsv" % (S, d))}
    # fetch events (Started/Succeeded/Failed) of the recipe, from the scan json
    fe = {}
    for sub in ("scan", "scan2", "scan-sib", "scan-ctrl"):
        for f in glob.glob("%s/%s/%s/*.json" % (S, d, sub)):
            x = json.load(open(f))
            if x.get("gone") or x["bytes"] < 2000: continue
            fe[x["job"]] = x.get("fetch_events", {})
    seen = set(); ev = []
    for r in rows:
        if r["class"] != "A": continue
        k = (r["runner_name"], r["utc_timestamp"], r["log_line"][:80])
        if k in seen: continue
        seen.add(k); ev.append(r)
    ev.sort(key=lambda r: (r["utc_timestamp"], int(r["run_attempt"] or 0)))
    groups = []
    for r in ev:
        rec = r["recipe_task"].split(":")[0]
        for g in groups:
            if g["rec"] == rec and t(r["utc_timestamp"]) - g["last"] <= 30:
                g["ev"].append(r); g["last"] = t(r["utc_timestamp"]); break
        else:
            groups.append({"rec": rec, "ev": [r], "last": t(r["utc_timestamp"])})
    for g in groups:
        runners = collections.OrderedDict()
        for r in g["ev"]: runners.setdefault(r["runner_name"], []).append(r)
        if len(runners) < 2: continue
        n += 1
        firsts0 = {rn: min(t(x["utc_timestamp"]) for x in v) for rn, v in runners.items()}
        gap0 = (max(firsts0.values()) - min(firsts0.values())) * 1000
        corrupt = any("zlib.error" in x["log_line"] or "BadZipFile" in x["log_line"] for x in g["ev"])
        section = "A" if gap0 <= 5000 and not corrupt else "B"
        blocks.setdefault(section, [])
        buf = []
        w = buf.append
        r0 = g["ev"][0]; run = r0["run_id"]; att = r0["run_attempt"]
        fname = ""
        for r in g["ev"]:
            m = re.search(r"/downloads/([^\s'\"]+?)(?:_bad-checksum_\w+)?(?:['\"\s\\]|$)", r["log_line"]) or re.search(r"download of (\S+?)(?: - |;)", r["log_line"])
            if m: fname = m.group(1); break
        w("## %s — %s — %s\n\n" % (r0["utc_timestamp"][:19] + "Z", repo, fname or g["rec"]))
        w("- recipe/task: `%s`, storage `%s`, run %s attempt %s\n" % (g["rec"], r0["storage"], run, att))
        firsts = {rn: min(t(x["utc_timestamp"]) for x in v) for rn, v in runners.items()}
        f0 = min(firsts.values())
        for rn, v in runners.items():
            j = jobs.get(v[0]["job_id"], [""] * 9)
            w("- runner `%s` host `%s` job %s (%s, %s): first checksum warning at +%d ms\n" % (rn[-19:], v[0]["machine_name"], v[0]["job_id"], j[3][:60], j[4], (firsts[rn] - f0) * 1000))
        w("\n```\n")
        lines = []
        for rn, v in runners.items():
            short = rn[-10:] + " " + v[0]["machine_name"]
            for l in fe.get(v[0]["job_id"], {}).get(g["rec"], []):
                lines.append((l[:28], short, l[29:200]))
            for x in v:
                l = x["log_line"]
                l = re.sub(r"^\S+ - (INFO|ERROR|WARNING) +- ", "", l)
                lines.append((x["utc_timestamp"], short, l[:260]))
        for ts, short, l in sorted(lines):
            w("%s  %-30s %s\n" % (ts[11:24], short, l))
        w("```\n\n")
        blocks[section].append("".join(buf))
titles = {"A": "# A. Cross-host collisions: two or more hosts corrupt the same download at the same time\n\n",
          "B": "# B. Re-failures on an already corrupt `.tmp` (sequential, not simultaneous)\n\n"}
for section in ("A", "B"):
    out.write(titles[section])
    for i, b in enumerate(blocks.get(section, []), 1):
        out.write(b.replace("## ", "## %s%d. " % (section, i), 1))
print("blocks written: A=%d B=%d" % (len(blocks.get("A", [])), len(blocks.get("B", []))))
