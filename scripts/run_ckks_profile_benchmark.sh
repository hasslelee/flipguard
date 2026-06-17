#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

OUTPUT_TAG="${OUTPUT_TAG:-profile_default}"
WARMUP_RUNS="${WARMUP_RUNS:-3}"
MEASUREMENT_RUNS="${MEASUREMENT_RUNS:-30}"
PROFILE_NAMES="${PROFILE_NAMES:-default,scale42,scale40,scale38,short_chain_6_scale42,short_chain_6_scale40,short_chain_6_scale38,short_chain_5,short_chain_3}"
EVALUATION_MODE="${EVALUATION_MODE:-naive}"
SCORE_ABS_ERROR_CAP="${SCORE_ABS_ERROR_CAP:-0.001}"
SCORE_REL_ERROR_CAP="${SCORE_REL_ERROR_CAP:-0.01}"

echo "== FlipGuard CKKS profile benchmark =="
echo "Repository: $REPO_ROOT"
echo "output_tag=$OUTPUT_TAG warmup_runs=$WARMUP_RUNS measurement_runs=$MEASUREMENT_RUNS profile_names=$PROFILE_NAMES evaluation_mode=$EVALUATION_MODE score_abs_error_cap=$SCORE_ABS_ERROR_CAP score_rel_error_cap=$SCORE_REL_ERROR_CAP"
echo

echo "== 1. Running Go tests =="
go test ./...
echo

echo "== 2. Running CKKS profile benchmark =="
go run ./cmd/flipguard \
  -experiment ckks_profile_benchmark \
  -ckks-output-tag="$OUTPUT_TAG" \
  -ckks-timing-warmup-runs="$WARMUP_RUNS" \
  -ckks-timing-measurement-runs="$MEASUREMENT_RUNS" \
  -ckks-profile-names="$PROFILE_NAMES" \
  -ckks-evaluation-mode="$EVALUATION_MODE" \
  -ckks-score-abs-error-cap="$SCORE_ABS_ERROR_CAP" \
  -ckks-score-rel-error-cap="$SCORE_REL_ERROR_CAP"
echo

SUMMARY_CSV="results/ckks_profile_benchmark/$OUTPUT_TAG/summary.csv"
RECORDS_CSV="results/ckks_profile_benchmark/$OUTPUT_TAG/records.csv"

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

echo "== 4. CKKS profile benchmark summary =="
cat "$SUMMARY_CSV"
echo

echo "== Done =="