#!/usr/bin/env python3
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
# usage: timeline.py <recipe-regex> <log> [<log> ...]
# Per job: do_fetch Started/Succeeded/Failed of the matching recipe and every warning/error about it.
import sys, re, os
pat = re.compile(sys.argv[1])
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
rows = []
for path in sys.argv[2:]:
    runner = machine = ""
    ev = []
    lastts = ""
    for raw in open(path, "rb"):
        line = ANSI.sub("", raw.decode("utf-8", "replace").rstrip("\r\n"))
        if line[:4].isdigit(): lastts = line[:28]
        if not runner and "Runner name:" in line: runner = re.search(r"'([^']+)'", line).group(1)
        if not machine and "Machine name:" in line: machine = re.search(r"'([^']+)'", line).group(1)
        m = re.search(r"NOTE: recipe (\S+): task (do_fetch|do_unpack): (Started|Succeeded|Failed)", line)
        if m and pat.search(m.group(1)):
            ev.append((line[:28], m.group(2) + " " + m.group(3), ""))
            continue
        m = re.search(r"(WARNING|ERROR): (\S+) (do_fetch|do_unpack): (.*)", line)
        if m and pat.search(m.group(2)):
            ev.append((line[:28], m.group(1), m.group(4)[:150]))
    rows.append((os.path.basename(path).replace(".log", ""), runner[-19:], machine, ev, lastts))
allev = []
for job, runner, machine, ev, lastts in rows:
    for ts, kind, txt in ev:
        allev.append((ts, runner[-10:], machine, job, kind, txt))
    if ev and not any(k in ("do_fetch Succeeded", "do_fetch Failed") for _, k, _ in ev if k.startswith("do_fetch")):
        allev.append((lastts, runner[-10:], machine, job, "LOG ENDS (job cancelled/killed), do_fetch still running", ""))
for e in sorted(allev):
    print("%s  %s %-18s job=%s  %s %s" % (e[0][11:24], e[1], e[2], e[3], e[4], e[5]))
print("jobs with the recipe: %d of %d logs" % (sum(1 for r in rows if r[3]), len(rows)))
