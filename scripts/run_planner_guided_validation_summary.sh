#!/usr/bin/env bash
set -euo pipefail

python3 scripts/build_planner_guided_validation_summary.py

echo
echo "Generated artifacts:"
find results/planner_guided_validation -maxdepth 1 -type f | sort

echo
echo "Planner-guided validation table:"
sed -n '1,200p' results/planner_guided_validation/table.md