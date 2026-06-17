#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

OUTPUT_TAG="${OUTPUT_TAG:-timing_default}"
WARMUP_RUNS="${WARMUP_RUNS:-3}"
MEASUREMENT_RUNS="${MEASUREMENT_RUNS:-30}"
PROFILE_NAME="${PROFILE_NAME:-default}"
EVALUATION_MODE="${EVALUATION_MODE:-naive}"

echo "== FlipGuard CKKS timing benchmark =="
echo "Repository: $REPO_ROOT"
echo "output_tag=$OUTPUT_TAG warmup_runs=$WARMUP_RUNS measurement_runs=$MEASUREMENT_RUNS profile_name=$PROFILE_NAME evaluation_mode=$EVALUATION_MODE"
echo

echo "== 1. Running Go tests =="
go test ./...
echo

echo "== 2. Running CKKS timing benchmark =="
go run ./cmd/flipguard \
  -experiment ckks_timing_benchmark \
  -ckks-output-tag="$OUTPUT_TAG" \
  -ckks-timing-warmup-runs="$WARMUP_RUNS" \
  -ckks-timing-measurement-runs="$MEASUREMENT_RUNS" \
  -ckks-profile-name="$PROFILE_NAME" \
  -ckks-evaluation-mode="$EVALUATION_MODE"
echo

SUMMARY_CSV="results/ckks_timing_benchmark/$OUTPUT_TAG/summary.csv"
RECORDS_CSV="results/ckks_timing_benchmark/$OUTPUT_TAG/records.csv"

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

echo "== 4. CKKS timing benchmark summary =="
cat "$SUMMARY_CSV"
echo

echo "== Done =="