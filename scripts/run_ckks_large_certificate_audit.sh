#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

MIN_Z="${MIN_Z:--0.05}"
MAX_Z="${MAX_Z:-0.05}"
POINTS="${POINTS:-201}"
REPETITIONS="${REPETITIONS:-5}"
SAFETY_FACTOR="${SAFETY_FACTOR:-0.5}"
OUTPUT_TAG="${OUTPUT_TAG:-large_${POINTS}x${REPETITIONS}}"

echo "== FlipGuard large CKKS certificate audit run =="
echo "Repository: $REPO_ROOT"
echo "min_z=$MIN_Z max_z=$MAX_Z points=$POINTS repetitions=$REPETITIONS safety_factor=$SAFETY_FACTOR output_tag=$OUTPUT_TAG"
echo

echo "== 1. Running Go tests =="
go test ./...
echo

echo "== 2. Running large CKKS certificate audit =="
go run ./cmd/flipguard \
  -experiment ckks_certificate_audit \
  -ckks-min-z="$MIN_Z" \
  -ckks-max-z="$MAX_Z" \
  -ckks-points="$POINTS" \
  -ckks-repetitions="$REPETITIONS" \
  -ckks-safety-factor="$SAFETY_FACTOR" \
  -ckks-output-tag="$OUTPUT_TAG"
echo

RESULT_DIR="results/ckks_certificate_audit/$OUTPUT_TAG"
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

echo "== 4. Large CKKS certificate audit summary =="
cat "$SUMMARY_CSV"
echo

echo "== 5. Records preview =="
head -n 20 "$RECORDS_CSV"
echo

echo "== Done =="