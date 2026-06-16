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

echo "== FlipGuard CKKS paper table export run =="
echo "Repository: $REPO_ROOT"
echo "min_z=$MIN_Z max_z=$MAX_Z points=$POINTS repetitions=$REPETITIONS safety_factor=$SAFETY_FACTOR output_tag=$OUTPUT_TAG"
echo

echo "== 1. Running Go tests =="
go test ./...
echo

echo "== 2. Refreshing CKKS policy comparison =="
OUTPUT_TAG="$OUTPUT_TAG" \
MIN_Z="$MIN_Z" \
MAX_Z="$MAX_Z" \
POINTS="$POINTS" \
REPETITIONS="$REPETITIONS" \
SAFETY_FACTOR="$SAFETY_FACTOR" \
./scripts/run_ckks_policy_comparison.sh
echo

echo "== 3. Running CKKS paper table export =="
args=(
  -experiment ckks_paper_table
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

RESULT_DIR="results/ckks_paper_table"
if [[ -n "$OUTPUT_TAG" ]]; then
  RESULT_DIR="$RESULT_DIR/$OUTPUT_TAG"
fi

TABLE_CSV="$RESULT_DIR/table.csv"
TABLE_TEX="$RESULT_DIR/table.tex"

echo "== 4. Checking generated result files =="
if [[ ! -f "$TABLE_CSV" ]]; then
  echo "missing table csv file: $TABLE_CSV" >&2
  exit 1
fi

if [[ ! -f "$TABLE_TEX" ]]; then
  echo "missing table tex file: $TABLE_TEX" >&2
  exit 1
fi

echo "found: $TABLE_CSV"
echo "found: $TABLE_TEX"
echo

echo "== 5. CKKS paper table CSV =="
cat "$TABLE_CSV"
echo

echo "== 6. CKKS paper table LaTeX =="
cat "$TABLE_TEX"
echo

echo "== Done =="