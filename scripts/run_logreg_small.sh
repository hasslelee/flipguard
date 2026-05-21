#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "== FlipGuard logreg_small reproducibility run =="
echo "Repository: $REPO_ROOT"
echo

echo "== 1. Running Go tests =="
go test ./...
echo

echo "== 2. Running logreg_small experiment =="
go run ./cmd/flipguard -experiment logreg_small
echo

RESULT_DIR="results/logreg_small"
SUMMARY_CSV="$RESULT_DIR/summary.csv"
PAPER_TABLE="$RESULT_DIR/paper_table.md"

echo "== 3. Checking generated result files =="
if [[ ! -f "$SUMMARY_CSV" ]]; then
  echo "missing summary file: $SUMMARY_CSV" >&2
  exit 1
fi

if [[ ! -f "$PAPER_TABLE" ]]; then
  echo "missing paper table file: $PAPER_TABLE" >&2
  exit 1
fi

echo "found: $SUMMARY_CSV"
echo "found: $PAPER_TABLE"
echo

echo "== 4. Paper-ready table preview =="
head -n 60 "$PAPER_TABLE"
echo

echo "== 5. Key summary rows =="
grep -E '^(uniform_bits_12|uniform_bits_16|accuracy_only_tol002_m12|accuracy_only_tol0005_m16|flipguard_p5_m12|flipguard_p1_m16),' "$SUMMARY_CSV"
echo

echo "== Done =="