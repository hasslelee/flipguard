#!/usr/bin/env bash
set -euo pipefail

go run ./cmd/flipguard -experiment ckks_auto_tuner_from_csv

echo
echo "Generated artifacts:"
find results/ckks_auto_tuner_from_csv -maxdepth 1 -type f | sort

echo
echo "Selection:"
cat results/ckks_auto_tuner_from_csv/tuner_selection.csv