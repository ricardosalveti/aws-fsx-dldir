#!/bin/bash
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
# $1 = owner/repo  $2 = job id  $3 = outdir
repo=$1; id=$2; out=$3; tmp=$out/$id.log.tmp
[ -s $out/$id.json ] && exit 0
for try in 1 2 3; do
  if gh api --allow-escape-sequences "repos/$repo/actions/jobs/$id/logs" > $tmp 2>$out/$id.err; then
    python3 "$(dirname "$0")/scanlog.py" $id $out < $tmp && rm -f $tmp $out/$id.err && exit 0
  fi
  if grep -q -E "HTTP (404|410)" $out/$id.err; then echo "{\"job\": \"$id\", \"gone\": true}" > $out/$id.json; rm -f $tmp; exit 0; fi
  if grep -q -i "rate limit" $out/$id.err $tmp 2>/dev/null; then echo "RATELIMIT $id" >&2; rm -f $tmp; exit 3; fi
  sleep $((try*10))
done
rm -f $tmp; echo "FAILED $id $(head -c 160 $out/$id.err)" >&2
