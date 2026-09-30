#!/bin/bash
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
# $1 = run id. Writes jobs/<id>.tsv with every job of every attempt.
id=$1; out=jobs/$id.tsv
[ -e $out ] && exit 0
for try in 1 2 3; do
  if gh api --paginate "repos/qualcomm-linux/meta-qcom-robotics-sdk/actions/runs/$id/jobs?filter=all&per_page=100" \
      --jq '.jobs[] | [.id, .run_id, .run_attempt, .name, .conclusion, .started_at, .completed_at, (.runner_name // ""), ([.steps[]? | select(.conclusion=="failure") | .name] | join("|"))] | @tsv' > $out.tmp 2>jobs/$id.err; then
    mv $out.tmp $out; rm -f jobs/$id.err; exit 0
  fi
  sleep 5
done
echo "FAILED $id" >&2
