#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

OUTPUT_TAG="${OUTPUT_TAG:-final_201x5}"
PROFILE_MODE_TAG="${PROFILE_MODE_TAG:-profile_mode_default}"

echo "== FlipGuard CKKS final check =="
echo "Repository: $REPO_ROOT"
echo "output_tag=$OUTPUT_TAG profile_mode_tag=$PROFILE_MODE_TAG"
echo

echo "== 1. Running Go tests =="
go test ./...
echo

echo "== 2. Running CKKS final check =="
go run ./cmd/flipguard \
  -experiment ckks_final_check \
  -ckks-output-tag="$OUTPUT_TAG" \
  -ckks-profile-mode-tag="$PROFILE_MODE_TAG"
echo

CHECK_CSV="results/ckks_final_check/$OUTPUT_TAG/check.csv"

echo "== 3. Checking generated result file =="
if [[ ! -f "$CHECK_CSV" ]]; then
  echo "missing check file: $CHECK_CSV" >&2
  exit 1
fi

echo "found: $CHECK_CSV"
echo

echo "== 4. CKKS final check summary =="
cat "$CHECK_CSV"
echo

echo "== Done =="