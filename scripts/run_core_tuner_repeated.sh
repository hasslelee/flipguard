#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

REPEATS="${1:-3}"
OUTPUT_ROOT="results/core_tuner_repeated/current"
RAW_ROOT="${OUTPUT_ROOT}/raw"

rm -rf "${RAW_ROOT}"
mkdir -p "${RAW_ROOT}"

run_one() {
  local repeat="$1"
  local workload="$2"
  local experiment="$3"
  local result_dir="$4"
  shift 4

  echo
  echo "================================================================"
  echo "repeat=${repeat} workload=${workload} experiment=${experiment}"
  echo "================================================================"

  rm -rf "${result_dir}"

  go run ./cmd/flipguard \
    -experiment "${experiment}" \
    "$@"

  local dest="${RAW_ROOT}/r${repeat}/${workload}"
  mkdir -p "$(dirname "${dest}")"
  rm -rf "${dest}"
  cp -a "${result_dir}" "${dest}"

  echo "copied ${result_dir} -> ${dest}"
}

for repeat in $(seq 1 "${REPEATS}"); do
  run_one \
    "${repeat}" \
    "linear_regression" \
    "ckks_linear_regression_tuner" \
    "results/ckks_linear_regression_tuner" \
    -ckks-timing-measurement-runs 3

  run_one \
    "${repeat}" \
    "logreg_small_profile" \
    "ckks_auto_tuner_eval" \
    "results/ckks_auto_tuner_eval" \
    -ckks-timing-warmup-runs 1 \
    -ckks-timing-measurement-runs 5

  run_one \
    "${repeat}" \
    "polynomial_regression" \
    "ckks_polynomial_regression_tuner" \
    "results/ckks_polynomial_regression_tuner" \
    -ckks-timing-measurement-runs 3

  run_one \
    "${repeat}" \
    "sobel_edge" \
    "ckks_sobel_edge_tuner" \
    "results/ckks_sobel_edge_tuner" \
    -ckks-timing-measurement-runs 3
done

python3 scripts/summarize_core_tuner_repeated.py \
  --root "${OUTPUT_ROOT}"

echo
echo "Repeated core tuner outputs:"
find "${OUTPUT_ROOT}" -maxdepth 2 -type f | sort
