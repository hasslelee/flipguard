#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

POINTS="${POINTS:-201}"
REPETITIONS="${REPETITIONS:-5}"
OUTPUT_TAG="${OUTPUT_TAG:-final_${POINTS}x${REPETITIONS}}"
SCORE_ABS_ERROR_CAP="${SCORE_ABS_ERROR_CAP:-0.001}"
SCORE_REL_ERROR_CAP="${SCORE_REL_ERROR_CAP:-0.01}"

echo "== FlipGuard CKKS output accuracy guard =="
echo "Repository: $REPO_ROOT"
echo "points=$POINTS repetitions=$REPETITIONS output_tag=$OUTPUT_TAG score_abs_error_cap=$SCORE_ABS_ERROR_CAP score_rel_error_cap=$SCORE_REL_ERROR_CAP"
echo

echo "== 1. Running Go tests =="
go test ./...
echo

echo "== 2. Running CKKS output accuracy guard =="
go run ./cmd/flipguard \
  -experiment ckks_output_accuracy \
  -ckks-points="$POINTS" \
  -ckks-repetitions="$REPETITIONS" \
  -ckks-output-tag="$OUTPUT_TAG" \
  -ckks-score-abs-error-cap="$SCORE_ABS_ERROR_CAP" \
  -ckks-score-rel-error-cap="$SCORE_REL_ERROR_CAP"
echo

SUMMARY_CSV="results/ckks_output_accuracy/$OUTPUT_TAG/summary.csv"
RECORDS_CSV="results/ckks_output_accuracy/$OUTPUT_TAG/records.csv"

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

echo "== 4. CKKS output accuracy summary =="
cat "$SUMMARY_CSV"
echo

echo "== Done =="