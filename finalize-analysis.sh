#!/bin/bash
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
S=$(cd "$(dirname "$0")" && pwd)
cd $S
python3 analyze.py robotics qualcomm-linux/meta-qcom-robotics-sdk > robotics/analyze.txt
python3 analyze.py metaqcom qualcomm-linux/meta-qcom > metaqcom/analyze.txt
python3 incidents.py > incidents.txt
python3 pairs.py > /dev/null
python3 cells.py > cells.txt
python3 contention2.py robotics scan,scan2 > robotics/contention.txt
python3 contention2.py metaqcom scan,scan-sib,scan-ctrl > metaqcom/contention.txt
echo "== cells"; cat cells.txt; echo "== robotics contention"; cat robotics/contention.txt; echo "== metaqcom contention"; cat metaqcom/contention.txt; echo "== incidents"; head -6 incidents.txt
