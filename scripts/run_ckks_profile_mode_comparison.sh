#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

OUTPUT_TAG="${OUTPUT_TAG:-profile_mode_default}"
NAIVE_PROFILE_TAG="${NAIVE_PROFILE_TAG:-profile_naive_default}"
RESCALE_PROFILE_TAG="${RESCALE_PROFILE_TAG:-profile_rescale_default}"

NAIVE_SUMMARY="results/ckks_profile_benchmark/$NAIVE_PROFILE_TAG/summary.csv"
RESCALE_SUMMARY="results/ckks_profile_benchmark/$RESCALE_PROFILE_TAG/summary.csv"

echo "== FlipGuard CKKS profile-mode comparison =="
echo "Repository: $REPO_ROOT"
echo "output_tag=$OUTPUT_TAG naive_profile_tag=$NAIVE_PROFILE_TAG rescale_profile_tag=$RESCALE_PROFILE_TAG"
echo

echo "== 1. Checking source benchmark files =="
if [[ ! -f "$NAIVE_SUMMARY" ]]; then
  echo "missing naive summary file: $NAIVE_SUMMARY" >&2
  echo "run: OUTPUT_TAG=$NAIVE_PROFILE_TAG EVALUATION_MODE=naive ./scripts/run_ckks_profile_benchmark.sh" >&2
  exit 1
fi

if [[ ! -f "$RESCALE_SUMMARY" ]]; then
  echo "missing rescale summary file: $RESCALE_SUMMARY" >&2
  echo "run: OUTPUT_TAG=$RESCALE_PROFILE_TAG EVALUATION_MODE=rescale ./scripts/run_ckks_profile_benchmark.sh" >&2
  exit 1
fi

echo "found: $NAIVE_SUMMARY"
echo "found: $RESCALE_SUMMARY"
echo

echo "== 2. Running Go tests =="
go test ./...
echo

echo "== 3. Running CKKS profile-mode comparison =="
go run ./cmd/flipguard \
  -experiment ckks_profile_mode_comparison \
  -ckks-output-tag="$OUTPUT_TAG" \
  -ckks-naive-profile-tag="$NAIVE_PROFILE_TAG" \
  -ckks-rescale-profile-tag="$RESCALE_PROFILE_TAG"
echo

SUMMARY_CSV="results/ckks_profile_mode_comparison/$OUTPUT_TAG/summary.csv"
TABLE_TEX="results/ckks_profile_mode_comparison/$OUTPUT_TAG/table.tex"

echo "== 4. Checking generated result files =="
if [[ ! -f "$SUMMARY_CSV" ]]; then
  echo "missing summary file: $SUMMARY_CSV" >&2
  exit 1
fi

if [[ ! -f "$TABLE_TEX" ]]; then
  echo "missing table file: $TABLE_TEX" >&2
  exit 1
fi

echo "found: $SUMMARY_CSV"
echo "found: $TABLE_TEX"
echo

echo "== 5. CKKS profile-mode comparison summary =="
cat "$SUMMARY_CSV"
echo

echo "== 6. CKKS profile-mode comparison LaTeX table =="
cat "$TABLE_TEX"
echo

echo "== Done =="