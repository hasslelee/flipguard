#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "== FlipGuard CKKS scale probe reproducibility run =="
echo "Repository: $REPO_ROOT"
echo

echo "== 1. Running Go tests =="
go test ./...
echo

echo "== 2. Running CKKS scale probe experiment =="
go run ./cmd/flipguard -experiment ckks_scale_probe
echo

RESULT_DIR="results/ckks_scale_probe"
SUMMARY_CSV="$RESULT_DIR/summary.csv"
REPORT_MD="$RESULT_DIR/report.md"

echo "== 3. Checking generated result files =="
if [[ ! -f "$SUMMARY_CSV" ]]; then
  echo "missing summary file: $SUMMARY_CSV" >&2
  exit 1
fi

if [[ ! -f "$REPORT_MD" ]]; then
  echo "missing report file: $REPORT_MD" >&2
  exit 1
fi

echo "found: $SUMMARY_CSV"
echo "found: $REPORT_MD"
echo

echo "== 4. CKKS scale probe summary =="
cat "$SUMMARY_CSV"
echo

echo "== 5. CKKS scale probe report preview =="
head -n 100 "$REPORT_MD"
echo

echo "== Done =="