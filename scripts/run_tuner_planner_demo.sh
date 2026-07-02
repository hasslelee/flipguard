#!/usr/bin/env bash
set -euo pipefail

go run ./cmd/flipguard -experiment tuner_planner_demo

echo
echo "Generated artifacts:"
find results/tuner_planner_demo -maxdepth 1 -type f | sort

echo
echo "Planner report preview:"
sed -n '1,160p' results/tuner_planner_demo/plan.md