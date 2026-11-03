#!/usr/bin/env bash
set -euo pipefail

go run ./cmd/flipguard -experiment tuner_planner_demo

echo
echo "Generated artifacts:"
find results/tuner_planner_demo -maxdepth 1 -type f | sort

echo
echo "Planner report preview:"
sed -n '1,220p' results/tuner_planner_demo/plan.md

echo
echo "Closest executable profile matches:"
head -n 40 results/tuner_planner_demo/profile_matches.csv