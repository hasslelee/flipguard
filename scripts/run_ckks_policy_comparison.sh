#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

MIN_Z="${MIN_Z:--0.05}"
MAX_Z="${MAX_Z:-0.05}"
POINTS="${POINTS:-101}"
REPETITIONS="${REPETITIONS:-3}"
SAFETY_FACTOR="${SAFETY_FACTOR:-0.5}"
OUTPUT_TAG="${OUTPUT_TAG:-}"

echo "== FlipGuard CKKS policy comparison run =="
echo "Repository: $REPO_ROOT"
echo "min_z=$MIN_Z max_z=$MAX_Z points=$POINTS repetitions=$REPETITIONS safety_factor=$SAFETY_FACTOR output_tag=$OUTPUT_TAG"
echo

echo "== 1. Running Go tests =="
go test ./...
echo

echo "== 2. Refreshing simulation baseline =="
./scripts/run_logreg_small.sh
echo

echo "== 3. Running CKKS policy comparison experiment =="
args=(
  -experiment ckks_policy_comparison
  -ckks-min-z="$MIN_Z"
  -ckks-max-z="$MAX_Z"
  -ckks-points="$POINTS"
  -ckks-repetitions="$REPETITIONS"
  -ckks-safety-factor="$SAFETY_FACTOR"
)

if [[ -n "$OUTPUT_TAG" ]]; then
  args+=(-ckks-output-tag="$OUTPUT_TAG")
fi

go run ./cmd/flipguard "${args[@]}"
echo

RESULT_DIR="results/ckks_policy_comparison"
if [[ -n "$OUTPUT_TAG" ]]; then
  RESULT_DIR="$RESULT_DIR/$OUTPUT_TAG"
fi

COMPARISON_CSV="$RESULT_DIR/comparison.csv"

echo "== 4. Checking generated result files =="
if [[ ! -f "$COMPARISON_CSV" ]]; then
  echo "missing comparison file: $COMPARISON_CSV" >&2
  exit 1
fi

echo "found: $COMPARISON_CSV"
echo

echo "== 5. CKKS policy comparison =="
cat "$COMPARISON_CSV"
echo

echo "== Done =="