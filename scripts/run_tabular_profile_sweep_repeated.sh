#!/usr/bin/env bash

set -u

RESULT_ROOT="results/ckks_tabular_profile_sweep_repeated"
LOG_DIR="${RESULT_ROOT}/logs"
STATUS_FILE="${RESULT_ROOT}/run_status.csv"

DATASETS_DEFAULT="wdbc iris_binary digits_binary banknote"
MODELS_DEFAULT="linear_poly3 mlp_square_linear_score"
PROFILES_DEFAULT="default scale42 scale40 scale38 deep_chain_8_scale45 deep_chain_9_scale45 short_chain_6_scale42 short_chain_6_scale40 short_chain_6_scale38 short_chain_5 short_chain_3"
MODES_DEFAULT="rescale naive"

REPEATS="${REPEATS:-3}"
FORCE="${FORCE:-0}"

mkdir -p "${LOG_DIR}"

if [[ ! -f "${STATUS_FILE}" || "${FORCE_STATUS:-0}" == "1" ]]; then
  echo "timestamp,dataset,model,profile,path,repeat,tag,status,exit_code,summary_path,log_path" > "${STATUS_FILE}"
fi

read -r -a DATASETS <<< "${DATASETS_OVERRIDE:-$DATASETS_DEFAULT}"
read -r -a MODELS <<< "${MODELS_OVERRIDE:-$MODELS_DEFAULT}"
read -r -a PROFILES <<< "${PROFILES_OVERRIDE:-$PROFILES_DEFAULT}"
read -r -a MODES <<< "${MODES_OVERRIDE:-$MODES_DEFAULT}"

path_label() {
  local mode="$1"
  if [[ "${mode}" == "rescale" ]]; then
    echo "rescale_aware"
  elif [[ "${mode}" == "naive" ]]; then
    echo "baseline_non_rescale"
  else
    echo "${mode}"
  fi
}

echo "FlipGuard repeated tabular profile sweep"
echo "datasets=${DATASETS[*]}"
echo "models=${MODELS[*]}"
echo "profiles=${PROFILES[*]}"
echo "modes=${MODES[*]}"
echo "repeats=${REPEATS}"
echo "force=${FORCE}"
echo

for dataset in "${DATASETS[@]}"; do
  for model in "${MODELS[@]}"; do
    for profile in "${PROFILES[@]}"; do
      for mode in "${MODES[@]}"; do
        path="$(path_label "${mode}")"

        for repeat in $(seq 1 "${REPEATS}"); do
          tag="tabular_sweep_${dataset}_${model}_${profile}_${path}_r${repeat}"
          summary_path="results/ckks_tabular_inference/${tag}/summary.csv"
          log_path="${LOG_DIR}/${tag}.log"

          if [[ "${FORCE}" != "1" && -f "${summary_path}" ]]; then
            echo "skip existing ${tag}"
            continue
          fi

          echo "===== ${tag} ====="

          started_at="$(date -Iseconds)"

          if [[ -n "${TABULAR_MAX_ROWS:-}" ]]; then
            TABULAR_DATASET_ID="${dataset}" \
            TABULAR_MODEL_ID="${model}" \
            TABULAR_MAX_ROWS="${TABULAR_MAX_ROWS}" \
            go run ./cmd/flipguard \
              -experiment ckks_tabular_inference \
              -ckks-output-tag="${tag}" \
              -ckks-profile-name="${profile}" \
              -ckks-evaluation-mode="${mode}" \
              -ckks-score-abs-error-cap=0.001 \
              -ckks-score-rel-error-cap=0.01 \
              > "${log_path}" 2>&1
          else
            TABULAR_DATASET_ID="${dataset}" \
            TABULAR_MODEL_ID="${model}" \
            go run ./cmd/flipguard \
              -experiment ckks_tabular_inference \
              -ckks-output-tag="${tag}" \
              -ckks-profile-name="${profile}" \
              -ckks-evaluation-mode="${mode}" \
              -ckks-score-abs-error-cap=0.001 \
              -ckks-score-rel-error-cap=0.01 \
              > "${log_path}" 2>&1
          fi

          exit_code="$?"

          if [[ "${exit_code}" == "0" && -f "${summary_path}" ]]; then
            status="ok"
          else
            status="failed"
          fi

          echo "${started_at},${dataset},${model},${profile},${path},${repeat},${tag},${status},${exit_code},${summary_path},${log_path}" >> "${STATUS_FILE}"

          echo "status=${status} exit_code=${exit_code} log=${log_path}"
        done
      done
    done
  done
done

echo
echo "wrote ${STATUS_FILE}"
