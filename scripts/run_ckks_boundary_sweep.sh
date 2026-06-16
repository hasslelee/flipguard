#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "== FlipGuard CKKS dense boundary sweep run =="
echo "Repository: $REPO_ROOT"
echo

echo "== 1. Running Go tests =="
go test ./...
echo

echo "== 2. Running CKKS boundary sweep experiment =="
go run ./cmd/flipguard -experiment ckks_boundary_sweep
echo

RESULT_DIR="results/ckks_boundary_sweep"
SUMMARY_CSV="$RESULT_DIR/summary.csv"
RECORDS_CSV="$RESULT_DIR/records.csv"

echo "== 3. Checking generated result files =="
if [[ ! -f "$SUMMARY_CSV" ]]; then
  echo "missing summary file: $SUMMARY_CSV" >&2
  exit 1
fi

if [[ ! -f "$RECORDS_CSV" ]]; then
  echo "missing records file: $RECORDS_CSV" >&2
  exit 1
fi

echo "found: $SUMMARY_CSV"
echo "found: $RECORDS_CSV"
echo

echo "== 4. CKKS boundary sweep summary =="
cat "$SUMMARY_CSV"
echo

echo "== 5. CKKS boundary sweep records preview =="
head -n 20 "$RECORDS_CSV"
echo

echo "== Done =="