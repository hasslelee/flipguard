#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 MODEL_JSON VALIDATION_CSV SPLIT_ID OUTPUT_JSON" >&2
  exit 2
fi

model_path=$1
validation_path=$2
split_id=$3
output_path=$4

mkdir -p "$(dirname "$output_path")"

go run ./cmd/flipguard-autotune \
  --model "$model_path" \
  --validation "$validation_path" \
  --split-id "$split_id" \
  --out "$output_path"
