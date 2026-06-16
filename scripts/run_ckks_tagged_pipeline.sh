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

echo "== FlipGuard tagged CKKS pipeline =="
echo "Repository: $REPO_ROOT"
echo "min_z=$MIN_Z max_z=$MAX_Z points=$POINTS repetitions=$REPETITIONS safety_factor=$SAFETY_FACTOR output_tag=$OUTPUT_TAG"
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

echo "== 3. Running tagged policy comparison and paper table =="
OUTPUT_TAG="$OUTPUT_TAG" \
MIN_Z="$MIN_Z" \
MAX_Z="$MAX_Z" \
POINTS="$POINTS" \
REPETITIONS="$REPETITIONS" \
SAFETY_FACTOR="$SAFETY_FACTOR" \
./scripts/run_ckks_paper_table.sh
echo

echo "== 4. Checking tagged outputs =="
paths=(
  "results/ckks_certificate_audit/$OUTPUT_TAG/summary.csv"
  "results/ckks_certificate_audit/$OUTPUT_TAG/records.csv"
  "results/ckks_policy_comparison/$OUTPUT_TAG/comparison.csv"
  "results/ckks_paper_table/$OUTPUT_TAG/table.csv"
  "results/ckks_paper_table/$OUTPUT_TAG/table.tex"
)

for path in "${paths[@]}"; do
  if [[ ! -f "$path" ]]; then
    echo "missing output file: $path" >&2
    exit 1
  fi
  echo "found: $path"
done

echo
echo "== 5. Final paper table =="
cat "results/ckks_paper_table/$OUTPUT_TAG/table.csv"
echo

echo "== Done =="