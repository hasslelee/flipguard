#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

BASE_DIR="results/planner_guided_actual_execution"
PROFILE_LIST_DIR="${BASE_DIR}/profile_lists"
FULL_CACHE_DIR="${BASE_DIR}/full_cache"

LINREG_RESULT_DIR="results/ckks_linear_regression_tuner"
LOGREG_RESULT_DIR="results/ckks_auto_tuner_eval"
POLY_RESULT_DIR="results/ckks_polynomial_regression_tuner"
SOBEL_RESULT_DIR="results/ckks_sobel_edge_tuner"

LINREG_SUBSET_DIR="${BASE_DIR}/linear_regression"
LOGREG_SUBSET_DIR="${BASE_DIR}/logreg_small"
POLY_SUBSET_DIR="${BASE_DIR}/polynomial_regression"
SOBEL_SUBSET_DIR="${BASE_DIR}/sobel_edge"

restore_full_outputs() {
  if [[ -d "${FULL_CACHE_DIR}/ckks_linear_regression_tuner" ]]; then
    rm -rf "${LINREG_RESULT_DIR}"
    cp -a "${FULL_CACHE_DIR}/ckks_linear_regression_tuner" "${LINREG_RESULT_DIR}"
  fi

  if [[ -d "${FULL_CACHE_DIR}/ckks_auto_tuner_eval" ]]; then
    rm -rf "${LOGREG_RESULT_DIR}"
    cp -a "${FULL_CACHE_DIR}/ckks_auto_tuner_eval" "${LOGREG_RESULT_DIR}"
  fi

  if [[ -d "${FULL_CACHE_DIR}/ckks_polynomial_regression_tuner" ]]; then
    rm -rf "${POLY_RESULT_DIR}"
    cp -a "${FULL_CACHE_DIR}/ckks_polynomial_regression_tuner" "${POLY_RESULT_DIR}"
  fi

  if [[ -d "${FULL_CACHE_DIR}/ckks_sobel_edge_tuner" ]]; then
    rm -rf "${SOBEL_RESULT_DIR}"
    cp -a "${FULL_CACHE_DIR}/ckks_sobel_edge_tuner" "${SOBEL_RESULT_DIR}"
  fi
}

require_dir() {
  local path="$1"

  if [[ ! -d "${path}" ]]; then
    echo "Required directory does not exist: ${path}" >&2
    exit 1
  fi
}

require_file() {
  local path="$1"

  if [[ ! -f "${path}" ]]; then
    echo "Required file does not exist: ${path}" >&2
    exit 1
  fi
}

require_dir "${LINREG_RESULT_DIR}"
require_dir "${LOGREG_RESULT_DIR}"
require_dir "${POLY_RESULT_DIR}"
require_dir "${SOBEL_RESULT_DIR}"
require_file "results/tuner_planner_demo/profile_matches.csv"

rm -rf \
  "${FULL_CACHE_DIR}" \
  "${LINREG_SUBSET_DIR}" \
  "${LOGREG_SUBSET_DIR}" \
  "${POLY_SUBSET_DIR}" \
  "${SOBEL_SUBSET_DIR}" \
  "${PROFILE_LIST_DIR}"

mkdir -p \
  "${FULL_CACHE_DIR}" \
  "${LINREG_SUBSET_DIR}" \
  "${LOGREG_SUBSET_DIR}" \
  "${POLY_SUBSET_DIR}" \
  "${SOBEL_SUBSET_DIR}" \
  "${PROFILE_LIST_DIR}"

cp -a "${LINREG_RESULT_DIR}" "${FULL_CACHE_DIR}/ckks_linear_regression_tuner"
cp -a "${LOGREG_RESULT_DIR}" "${FULL_CACHE_DIR}/ckks_auto_tuner_eval"
cp -a "${POLY_RESULT_DIR}" "${FULL_CACHE_DIR}/ckks_polynomial_regression_tuner"
cp -a "${SOBEL_RESULT_DIR}" "${FULL_CACHE_DIR}/ckks_sobel_edge_tuner"

trap restore_full_outputs EXIT

python3 scripts/extract_planner_guided_profiles.py

LINREG_PROFILES="$(cat "${PROFILE_LIST_DIR}/linear_regression_profiles.txt")"
LOGREG_PROFILES="$(cat "${PROFILE_LIST_DIR}/logreg_small_profiles.txt")"
POLY_PROFILES="$(cat "${PROFILE_LIST_DIR}/polynomial_regression_profiles.txt")"
SOBEL_PROFILES="$(cat "${PROFILE_LIST_DIR}/sobel_edge_profiles.txt")"

echo
echo "Planner-guided Linear Regression profiles: ${LINREG_PROFILES}"
echo "Planner-guided LogReg profiles: ${LOGREG_PROFILES}"
echo "Planner-guided Polynomial Regression profiles: ${POLY_PROFILES}"
echo "Planner-guided Sobel Edge profiles: ${SOBEL_PROFILES}"

echo
echo "Running planner-guided Linear Regression execution..."
go run ./cmd/flipguard \
  -experiment ckks_linear_regression_tuner \
  -ckks-profile-names "${LINREG_PROFILES}" \
  -ckks-timing-measurement-runs 3

rm -rf "${LINREG_SUBSET_DIR}"
mkdir -p "${LINREG_SUBSET_DIR}"
cp -a "${LINREG_RESULT_DIR}/." "${LINREG_SUBSET_DIR}/"

echo
echo "Running planner-guided LogReg/Profile execution..."
go run ./cmd/flipguard \
  -experiment ckks_auto_tuner_eval \
  -ckks-profile-names "${LOGREG_PROFILES}" \
  -ckks-timing-measurement-runs 3

rm -rf "${LOGREG_SUBSET_DIR}"
mkdir -p "${LOGREG_SUBSET_DIR}"
cp -a "${LOGREG_RESULT_DIR}/." "${LOGREG_SUBSET_DIR}/"

echo
echo "Running planner-guided Polynomial Regression execution..."
go run ./cmd/flipguard \
  -experiment ckks_polynomial_regression_tuner \
  -ckks-profile-names "${POLY_PROFILES}" \
  -ckks-timing-measurement-runs 3

rm -rf "${POLY_SUBSET_DIR}"
mkdir -p "${POLY_SUBSET_DIR}"
cp -a "${POLY_RESULT_DIR}/." "${POLY_SUBSET_DIR}/"

echo
echo "Running planner-guided Sobel Edge execution..."
go run ./cmd/flipguard \
  -experiment ckks_sobel_edge_tuner \
  -ckks-profile-names "${SOBEL_PROFILES}" \
  -ckks-timing-measurement-runs 3

rm -rf "${SOBEL_SUBSET_DIR}"
mkdir -p "${SOBEL_SUBSET_DIR}"
cp -a "${SOBEL_RESULT_DIR}/." "${SOBEL_SUBSET_DIR}/"

python3 scripts/build_planner_guided_actual_execution_summary.py

echo
echo "Generated artifacts:"
find "${BASE_DIR}" -maxdepth 2 -type f | sort

echo
echo "Actual planner-guided execution table:"
sed -n '1,320p' "${BASE_DIR}/table.md"
