#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

MIN_Z="${MIN_Z:--0.05}"
MAX_Z="${MAX_Z:-0.05}"
POINTS="${POINTS:-101}"
REPETITIONS="${REPETITIONS:-3}"
SAFETY_FACTOR="${SAFETY_FACTOR:-0.5}"
OUTPUT_TAG="${OUTPUT_TAG:-tagged_${POINTS}x${REPETITIONS}}"
SCORE_ABS_ERROR_CAP="${SCORE_ABS_ERROR_CAP:-0.001}"
SCORE_REL_ERROR_CAP="${SCORE_REL_ERROR_CAP:-0.01}"

echo "== FlipGuard tagged CKKS pipeline =="
echo "Repository: $REPO_ROOT"
echo "min_z=$MIN_Z max_z=$MAX_Z points=$POINTS repetitions=$REPETITIONS safety_factor=$SAFETY_FACTOR output_tag=$OUTPUT_TAG score_abs_error_cap=$SCORE_ABS_ERROR_CAP score_rel_error_cap=$SCORE_REL_ERROR_CAP"
echo

echo "== 1. Running Go tests =="
go test ./...
echo

echo "== 2. Running tagged certificate audit =="
OUTPUT_TAG="$OUTPUT_TAG" \
MIN_Z="$MIN_Z" \
MAX_Z="$MAX_Z" \
POINTS="$POINTS" \
REPETITIONS="$REPETITIONS" \
SAFETY_FACTOR="$SAFETY_FACTOR" \
./scripts/run_ckks_large_certificate_audit.sh
echo

echo "== 3. Running tagged policy comparison, output accuracy guard, and paper table =="
OUTPUT_TAG="$OUTPUT_TAG" \
MIN_Z="$MIN_Z" \
MAX_Z="$MAX_Z" \
POINTS="$POINTS" \
REPETITIONS="$REPETITIONS" \
SAFETY_FACTOR="$SAFETY_FACTOR" \
SCORE_ABS_ERROR_CAP="$SCORE_ABS_ERROR_CAP" \
SCORE_REL_ERROR_CAP="$SCORE_REL_ERROR_CAP" \
./scripts/run_ckks_paper_table.sh
echo

echo "== 4. Running tagged final check =="
OUTPUT_TAG="$OUTPUT_TAG" \
POINTS="$POINTS" \
REPETITIONS="$REPETITIONS" \
./scripts/run_ckks_final_check.sh
echo

echo "== 5. Checking tagged outputs =="
paths=(
  "results/ckks_certificate_audit/$OUTPUT_TAG/summary.csv"
  "results/ckks_certificate_audit/$OUTPUT_TAG/records.csv"
  "results/ckks_output_accuracy/$OUTPUT_TAG/summary.csv"
  "results/ckks_output_accuracy/$OUTPUT_TAG/records.csv"
  "results/ckks_policy_comparison/$OUTPUT_TAG/comparison.csv"
  "results/ckks_paper_table/$OUTPUT_TAG/table.csv"
  "results/ckks_paper_table/$OUTPUT_TAG/table.tex"
  "results/ckks_final_check/$OUTPUT_TAG/check.csv"
)

for path in "${paths[@]}"; do
  if [[ ! -f "$path" ]]; then
    echo "missing output file: $path" >&2
    exit 1
  fi
  echo "found: $path"
done

echo
echo "== 6. Final paper table =="
cat "results/ckks_paper_table/$OUTPUT_TAG/table.csv"
echo

echo "== Done =="