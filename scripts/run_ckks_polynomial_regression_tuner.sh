#!/usr/bin/env bash
set -euo pipefail

go run ./cmd/flipguard \
  -experiment ckks_polynomial_regression_tuner \
  -ckks-timing-measurement-runs 3

echo
echo "Generated artifacts:"
find results/ckks_polynomial_regression_tuner -maxdepth 1 -type f | sort

echo
echo "Selection:"
cat results/ckks_polynomial_regression_tuner/tuner_selection.csv

echo
echo "Summary:"
sed -n '1,120p' results/ckks_polynomial_regression_tuner/selection_summary.md