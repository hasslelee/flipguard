#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

POINTS="${POINTS:-201}"
REPETITIONS="${REPETITIONS:-5}"
OUTPUT_TAG="${OUTPUT_TAG:-final_${POINTS}x${REPETITIONS}}"

echo "== FlipGuard CKKS final result check =="
echo "Repository: $REPO_ROOT"
echo "points=$POINTS repetitions=$REPETITIONS output_tag=$OUTPUT_TAG"
echo

echo "== 1. Running Go tests =="
go test ./...
echo

echo "== 2. Running final check =="
go run ./cmd/flipguard \
  -experiment ckks_final_check \
  -ckks-points="$POINTS" \
  -ckks-repetitions="$REPETITIONS" \
  -ckks-output-tag="$OUTPUT_TAG"
echo

CHECK_CSV="results/ckks_final_check/$OUTPUT_TAG/check.csv"

echo "== 3. Checking generated result file =="
if [[ ! -f "$CHECK_CSV" ]]; then
  echo "missing check file: $CHECK_CSV" >&2
  exit 1
fi

echo "found: $CHECK_CSV"
echo

echo "== 4. Final check CSV =="
cat "$CHECK_CSV"
echo

echo "== Done =="