#!/usr/bin/env bash
set -uo pipefail

MODE="full"
FORCE=0
RESUME=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --smoke)
      MODE="smoke"
      shift
      ;;

    --full)
      MODE="full"
      shift
      ;;

    --force)
      FORCE=1
      shift
      ;;

    --resume)
      RESUME=1
      shift
      ;;

    *)
      echo "ERROR: unknown argument $1" >&2
      exit 2
      ;;
  esac
done

REPOSITORY_ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." &&
    pwd
)"

cd "$REPOSITORY_ROOT" || exit 1

SPLIT_ROOT="results/thesis_grade_protocol/tabular_splits_v1"
BASE_ROOT="results/thesis_grade_protocol/tabular_validation_oracle_v1"

if [[ "$MODE" == "smoke" ]]; then
  RUN_ID="smoke"
  RUN_ROOT="$BASE_ROOT/smoke"

  SEEDS=(0)
  DATASETS=(iris_binary)
  MODELS=(linear_poly3)
  PROFILES=(
    default
    short_chain_3
  )
else
  RUN_ID="full"
  RUN_ROOT="$BASE_ROOT/full"

  SEEDS=(
    0
    1
    2
    3
    4
  )

  DATASETS=(
    banknote
    digits_binary
    iris_binary
    mnist_pool16
    wdbc
  )

  MODELS=(
    linear_poly3
    mlp_square_linear_score
  )

  PROFILES=(
    default
    scale42
    scale40
    scale38
    deep_chain_8_scale45
    deep_chain_9_scale45
    short_chain_6_scale42
    short_chain_6_scale40
    short_chain_6_scale38
    short_chain_5
    short_chain_3
  )
fi

PATHS=(
  baseline_non_rescale
  rescale_aware
)

if [[ ! -f "$SPLIT_ROOT/summary.json" ]]; then
  echo "ERROR: missing split summary $SPLIT_ROOT/summary.json" >&2
  exit 1
fi

if [[ -d "$RUN_ROOT" ]]; then
  if [[ $FORCE -eq 1 ]]; then
    rm -rf "$RUN_ROOT"
  elif [[ $RESUME -ne 1 ]]; then
    echo "ERROR: $RUN_ROOT already exists; use --force or --resume" >&2
    exit 1
  fi
fi

mkdir -p \
  "$RUN_ROOT/bin" \
  "$RUN_ROOT/logs" \
  "$RUN_ROOT/materialized" \
  "$RUN_ROOT/summary"

BINARY="$RUN_ROOT/bin/flipguard"
STATUS_PATH="$RUN_ROOT/run_status.csv"

echo "=== build experiment binary ==="

go build \
  -o "$BINARY" \
  ./cmd/flipguard

BUILD_STATUS=$?
echo "binary_build_status=$BUILD_STATUS"

if [[ $BUILD_STATUS -ne 0 ]]; then
  exit 1
fi

if [[ ! -f "$STATUS_PATH" ]]; then
  printf '%s\n' \
    'run_id,split_seed,dataset_id,model_id,profile,path,evaluation_mode,candidate_id,tag,status,exit_code,summary_path,records_path,stdout_log' \
    > "$STATUS_PATH"
fi

remove_existing_status_row() {
  local tag="$1"

  python3 - \
    "$STATUS_PATH" \
    "$tag" <<'PYEOF'
import csv
import os
import sys
import tempfile
from pathlib import Path

path = Path(sys.argv[1])
target_tag = sys.argv[2]

with path.open(
    "r",
    encoding="utf-8",
    newline="",
) as handle:
    reader = csv.DictReader(handle)
    fieldnames = list(reader.fieldnames or [])
    rows = [
        row
        for row in reader
        if row.get("tag") != target_tag
    ]

if not fieldnames:
    raise SystemExit(
        "ERROR: run-status CSV has no header"
    )

with tempfile.NamedTemporaryFile(
    "w",
    encoding="utf-8",
    newline="",
    dir=path.parent,
    delete=False,
) as handle:
    temporary = Path(handle.name)

    writer = csv.DictWriter(
        handle,
        fieldnames=fieldnames,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)

os.replace(temporary, path)
PYEOF
}

append_status_row() {
  local seed="$1"
  local dataset="$2"
  local model="$3"
  local profile="$4"
  local path="$5"
  local evaluation_mode="$6"
  local candidate_id="$7"
  local tag="$8"
  local status="$9"
  local exit_code="${10}"
  local summary_path="${11}"
  local records_path="${12}"
  local stdout_log="${13}"

  python3 - \
    "$STATUS_PATH" \
    "$RUN_ID" \
    "$seed" \
    "$dataset" \
    "$model" \
    "$profile" \
    "$path" \
    "$evaluation_mode" \
    "$candidate_id" \
    "$tag" \
    "$status" \
    "$exit_code" \
    "$summary_path" \
    "$records_path" \
    "$stdout_log" <<'PYEOF'
import csv
import sys
from pathlib import Path

path = Path(sys.argv[1])

row = {
    "run_id": sys.argv[2],
    "split_seed": sys.argv[3],
    "dataset_id": sys.argv[4],
    "model_id": sys.argv[5],
    "profile": sys.argv[6],
    "path": sys.argv[7],
    "evaluation_mode": sys.argv[8],
    "candidate_id": sys.argv[9],
    "tag": sys.argv[10],
    "status": sys.argv[11],
    "exit_code": sys.argv[12],
    "summary_path": sys.argv[13],
    "records_path": sys.argv[14],
    "stdout_log": sys.argv[15],
}

with path.open(
    "a",
    encoding="utf-8",
    newline="",
) as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=list(row.keys()),
        lineterminator="\n",
    )
    writer.writerow(row)
PYEOF
}

candidate_total=0
candidate_ok=0
candidate_failed=0
candidate_skipped=0

for seed in "${SEEDS[@]}"; do
  for dataset in "${DATASETS[@]}"; do
    for model in "${MODELS[@]}"; do
      SPLIT_WORKLOAD_ROOT="$SPLIT_ROOT/split_seed_${seed}/${dataset}/${model}"

      VALIDATION_SOURCE="$SPLIT_WORKLOAD_ROOT/configuration_validation.csv"
      MANIFEST_SOURCE="$SPLIT_WORKLOAD_ROOT/split_manifest.json"
      MODEL_SOURCE="datasets/tabular_suite/${dataset}/${model}/model.json"

      if [[ ! -f "$VALIDATION_SOURCE" ]]; then
        echo "ERROR: missing validation split $VALIDATION_SOURCE" >&2
        exit 1
      fi

      if [[ ! -f "$MANIFEST_SOURCE" ]]; then
        echo "ERROR: missing split manifest $MANIFEST_SOURCE" >&2
        exit 1
      fi

      if [[ ! -f "$MODEL_SOURCE" ]]; then
        echo "ERROR: missing model artifact $MODEL_SOURCE" >&2
        exit 1
      fi

      MATERIALIZED_ROOT="$RUN_ROOT/materialized/split_seed_${seed}"
      MATERIALIZED_WORKLOAD="$MATERIALIZED_ROOT/${dataset}/${model}"

      mkdir -p "$MATERIALIZED_WORKLOAD"

      cp "$MODEL_SOURCE" \
        "$MATERIALIZED_WORKLOAD/model.json"

      cp "$VALIDATION_SOURCE" \
        "$MATERIALIZED_WORKLOAD/test.csv"

      cp "$MANIFEST_SOURCE" \
        "$MATERIALIZED_WORKLOAD/split_manifest.json"

      for profile in "${PROFILES[@]}"; do
        for path in "${PATHS[@]}"; do
          candidate_total=$((candidate_total + 1))

          case "$path" in
            baseline_non_rescale)
              evaluation_mode="naive"
              ;;

            rescale_aware)
              evaluation_mode="rescale"
              ;;

            *)
              echo "ERROR: unsupported path $path" >&2
              exit 1
              ;;
          esac

          candidate_id="${profile}__${path}"

          tag="thesisv1_${RUN_ID}_seed${seed}_${dataset}_${model}_${profile}_${path}"

          RESULT_DIR="results/ckks_tabular_inference/$tag"
          SUMMARY_PATH="$RESULT_DIR/summary.csv"
          RECORDS_PATH="$RESULT_DIR/records.csv"
          STDOUT_LOG="$RUN_ROOT/logs/${tag}.txt"

          if [[ $RESUME -eq 1 ]] &&
             [[ -f "$SUMMARY_PATH" ]] &&
             [[ -f "$RECORDS_PATH" ]] &&
             grep -Fq ",${tag},ok,0," "$STATUS_PATH"; then
            echo "SKIP completed candidate: $tag"
            candidate_skipped=$((candidate_skipped + 1))
            continue
          fi

          remove_existing_status_row "$tag"

          rm -rf "$RESULT_DIR"

          echo
          echo "RUN seed=$seed dataset=$dataset model=$model candidate=$candidate_id"

          set +e

          TABULAR_DATASET_ID="$dataset" \
          TABULAR_MODEL_ID="$model" \
          TABULAR_DATA_ROOT="$MATERIALIZED_ROOT" \
          "$BINARY" \
            -experiment ckks_tabular_inference \
            -ckks-profile-name "$profile" \
            -ckks-evaluation-mode "$evaluation_mode" \
            -ckks-output-tag "$tag" \
            >"$STDOUT_LOG" 2>&1

          exit_code=$?

          set -e

          if [[ $exit_code -eq 0 ]] &&
             [[ -f "$SUMMARY_PATH" ]] &&
             [[ -f "$RECORDS_PATH" ]]; then
            status="ok"
            candidate_ok=$((candidate_ok + 1))
          else
            status="failed"
            candidate_failed=$((candidate_failed + 1))
          fi

          append_status_row \
            "$seed" \
            "$dataset" \
            "$model" \
            "$profile" \
            "$path" \
            "$evaluation_mode" \
            "$candidate_id" \
            "$tag" \
            "$status" \
            "$exit_code" \
            "$SUMMARY_PATH" \
            "$RECORDS_PATH" \
            "$STDOUT_LOG"

          echo "candidate_status=$status exit_code=$exit_code tag=$tag"
        done
      done
    done
  done
done

echo
echo "candidate_total=$candidate_total"
echo "candidate_ok=$candidate_ok"
echo "candidate_failed=$candidate_failed"
echo "candidate_skipped=$candidate_skipped"

SUMMARY_ARGS=(
  --run-status "$STATUS_PATH"
  --split-summary "$SPLIT_ROOT/summary.json"
  --output-root "$RUN_ROOT/summary"
  --margin-floor 0.001
  --alphas 0.1,0.25,0.5,0.75,0.9
)

if [[ "$MODE" == "smoke" ]]; then
  SUMMARY_ARGS+=(--allow-incomplete)
fi

python3 \
  scripts/summarize_thesis_grade_tabular_validation.py \
  "${SUMMARY_ARGS[@]}"

SUMMARY_STATUS=$?
echo "summary_status=$SUMMARY_STATUS"

if [[ $SUMMARY_STATUS -ne 0 ]]; then
  exit 1
fi

echo "validation_oracle_run=PASS"
