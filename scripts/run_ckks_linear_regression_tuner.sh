#!/usr/bin/env bash
set -euo pipefail

go run ./cmd/flipguard -experiment ckks_linear_regression_tuner "$@"

echo
echo "Generated artifacts:"
find results/ckks_linear_regression_tuner -maxdepth 1 -type f | sort

echo
echo "Selection summary:"
sed -n '1,180p' results/ckks_linear_regression_tuner/selection_summary.md