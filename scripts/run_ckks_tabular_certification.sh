#!/usr/bin/env bash

set -euo pipefail

go run ./cmd/flipguard \
  -experiment ckks_tabular_certification \
  -ckks-repetitions 3 \
  -ckks-safety-factor 0.5 \
  "$@"

echo
echo "Generated artifacts:"
find results/certification/tabular/current \
  -maxdepth 1 \
  -type f \
  | LC_ALL=C sort

echo
echo "Certification report:"
sed -n '1,260p' \
  results/certification/tabular/current/report.md
