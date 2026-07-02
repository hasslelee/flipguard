#!/usr/bin/env bash
set -euo pipefail

go run ./cmd/flipguard \
  -experiment ckks_auto_tuner_eval \
  -ckks-timing-warmup-runs 1 \
  -ckks-timing-measurement-runs 5

echo
echo "Generated artifacts:"
find results/ckks_auto_tuner_eval -maxdepth 1 -type f | sort

echo
echo "Selection:"
cat results/ckks_auto_tuner_eval/tuner_selection.csv