#!/usr/bin/env bash
set -euo pipefail

go run ./cmd/flipguard -experiment ckks_polynomial_regression

echo
echo "Generated artifacts:"
find results/ckks_polynomial_regression -maxdepth 1 -type f | sort

echo
echo "Report preview:"
sed -n '1,80p' results/ckks_polynomial_regression/report.md