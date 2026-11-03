#!/usr/bin/env bash
set -euo pipefail

python3 scripts/build_tuner_benchmark_summary.py

echo
echo "Generated artifacts:"
find results/tuner_benchmark_summary -maxdepth 1 -type f | sort

echo
echo "Summary table:"
sed -n '1,120p' results/tuner_benchmark_summary/table.md