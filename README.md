# Shared BitBake DL_DIR on Amazon FSx for OpenZFS: lock collision evidence

Evidence pack for an AWS support case about parallel build hosts corrupting
the same download file while each holds an exclusive `flock()` on a lock file
on an FSx for OpenZFS (NFSv4.2) mount, after the same workload ran on Amazon
EFS without the problem.

- `aws-fsx-dldir-report.md` — the report: environment, timeline, incidents,
  storage x lock-protocol comparison, mechanism, open hypotheses, asks to AWS
- `aws-case-summary.md` — draft opening message for the support case
- `pairs.md` — raw job log lines of every collision, per host, with ms timestamps
- `incidents.tsv` — machine-readable incident table
- `probe/` — `nfs-lock-probe.py`, a standalone reproducer, and how to run it on
  two hosts against both file systems, and `summarize-probe.py`, which turns
  the results of all hosts into a reproduced / not reproduced verdict per run

## Data

GitHub Actions job logs of `qualcomm-linux/meta-qcom` and
`qualcomm-linux/meta-qcom-robotics-sdk`, 2026-07-01 .. 2026-09-29, reduced
to what the analysis needs:

- `metaqcom/`, `robotics/`: `runs.tsv` (workflow runs), `alljobs.tsv` (every
  job of every attempt of the inspected runs), `events.tsv` (every log hit of
  the signature classes in `SIGNATURES.md`), `scan*/*.json` (per-job
  extracts: hits, environment lines, `do_fetch` intervals), `robotics/full/`
  (complete logs of run 35938315722)
- `cells.txt`, `*/contention.txt`, `incidents.txt`, `*/analyze.txt`: outputs
  of the scripts below, as quoted in the report

## Reproducing the numbers

    ./finalize-analysis.sh          # analyze.py, incidents.py, pairs.py, cells.py, contention2.py

`scanjob.sh` / `scanlog.py` turn a job log into a `scan*/<job>.json` extract;
`listjobs.sh` lists the jobs of a run. Both need `gh` authenticated for the
repositories (the logs endpoint counts against the hourly API limit).

## License

MIT, see `COPYING.MIT`. Copyright (c) Qualcomm Technologies, Inc. and/or its
subsidiaries. The job logs quoted here are the public GitHub Actions logs of
the repositories named above.
