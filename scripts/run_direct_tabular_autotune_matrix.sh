#!/usr/bin/env bash
set -uo pipefail

MODE="seed0"
FORCE=0
RESUME=0
RETRY_FAILED=0
QUIET_SKIPS=0
MAX_NEW_RUNS=0
PRECISION_FLOOR_BITS=0
SAME_TIER_PRECISION=0
KEY_REPEATS=1
ONLY_SEED=""
MARGIN_FLOOR="0.001"
SAFETY_FACTOR="0.5"
PRINT_RUN_ID=0
MATERIALIZE_MODEL_INPUT=0
SPLIT_ROOT_OPTION="results/thesis_grade_protocol/tabular_splits_v1"
MODEL_IDS_OPTION="linear_poly3,mlp_square_linear_score"
DATASET_IDS_OPTION="banknote,digits_binary,iris_binary,mnist_pool16,wdbc"
RUN_LABEL=""
BINARY_OVERRIDE=""

usage() {
  cat <<'EOF'
usage: scripts/run_direct_tabular_autotune_matrix.sh [OPTIONS]

Modes:
  --smoke       Run iris_binary/linear_poly3 on split seed 0.
  --seed0       Run five datasets and two models on split seed 0 (default).
  --full        Run five datasets, two models, and split seeds 0..4.

Execution:
  --resume              Resume an existing mode directory.
  --force               Replace an existing mode directory.
  --retry-failed        Retry terminal failed workloads when resuming.
  --max-new-runs N      Stop after N newly started workloads.
  --precision-floor N   Experimental min scale/Q-prime bits; keeps P >= 30.
  --same-tier-precision Maximize precision without increasing minimum LogN.
  --key-repeats N       Fresh-key validation runs per configuration trial.
  --margin-floor X      Decision-margin floor (default: 0.001).
  --safety-factor X     Error-budget fraction in (0,1] (default: 0.5).
  --split-root PATH     Digest-bound split root.
  --materialize-model-input
                        Recompute the canonical validation artifact from the
                        split's model-input feature rows before autotuning.
  --model-ids CSV       Explicit model allowlist.
  --dataset-ids CSV     Explicit dataset allowlist.
  --run-label ID        Result-ID component for a separate experiment.
  --binary PATH         Reuse an immutable prebuilt autotune binary.
  --only-seed N         In --full mode, run only split seed N (0..4).
  --print-run-id        Print the derived result run ID without executing.
  --quiet-skips         Suppress one-line messages for resumed workloads.
  -h, --help            Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --smoke)
      MODE="smoke"
      shift
      ;;
    --seed0)
      MODE="seed0"
      shift
      ;;
    --full)
      MODE="full"
      shift
      ;;
    --resume)
      RESUME=1
      shift
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --retry-failed)
      RETRY_FAILED=1
      shift
      ;;
    --quiet-skips)
      QUIET_SKIPS=1
      shift
      ;;
    --max-new-runs)
      if [[ $# -lt 2 ]] || [[ ! "$2" =~ ^[1-9][0-9]*$ ]]; then
        echo "ERROR: --max-new-runs requires a positive integer" >&2
        exit 2
      fi
      MAX_NEW_RUNS="$2"
      shift 2
      ;;
    --precision-floor)
      if [[ $# -lt 2 ]] || [[ ! "$2" =~ ^[1-9][0-9]*$ ]]; then
        echo "ERROR: --precision-floor requires a positive integer" >&2
        exit 2
      fi
      PRECISION_FLOOR_BITS="$2"
      shift 2
      ;;
    --same-tier-precision)
      SAME_TIER_PRECISION=1
      shift
      ;;
    --key-repeats)
      if [[ $# -lt 2 ]] || [[ ! "$2" =~ ^[1-9][0-9]*$ ]]; then
        echo "ERROR: --key-repeats requires a positive integer" >&2
        exit 2
      fi
      KEY_REPEATS="$2"
      shift 2
      ;;
    --margin-floor)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --margin-floor requires a non-negative number" >&2
        exit 2
      fi
      if ! MARGIN_FLOOR="$(
        python3 - "$2" <<'PYEOF'
import math
import sys

try:
    value = float(sys.argv[1])
except ValueError:
    raise SystemExit(1)
if not math.isfinite(value) or value < 0:
    raise SystemExit(1)
print(format(value, ".12g"))
PYEOF
      )"; then
        echo "ERROR: --margin-floor requires a non-negative finite number" >&2
        exit 2
      fi
      shift 2
      ;;
    --safety-factor)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --safety-factor requires a number in (0,1]" >&2
        exit 2
      fi
      if ! SAFETY_FACTOR="$(
        python3 - "$2" <<'PYEOF'
import math
import sys

try:
    value = float(sys.argv[1])
except ValueError:
    raise SystemExit(1)
if not math.isfinite(value) or value <= 0 or value > 1:
    raise SystemExit(1)
print(format(value, ".12g"))
PYEOF
      )"; then
        echo "ERROR: --safety-factor requires a finite number in (0,1]" >&2
        exit 2
      fi
      shift 2
      ;;
    --split-root)
      if [[ $# -lt 2 ]] || [[ -z "$2" ]]; then
        echo "ERROR: --split-root requires a path" >&2
        exit 2
      fi
      SPLIT_ROOT_OPTION="$2"
      shift 2
      ;;
    --materialize-model-input)
      MATERIALIZE_MODEL_INPUT=1
      shift
      ;;
    --model-ids)
      if [[ $# -lt 2 ]] || [[ -z "$2" ]]; then
        echo "ERROR: --model-ids requires a comma-separated list" >&2
        exit 2
      fi
      MODEL_IDS_OPTION="$2"
      shift 2
      ;;
    --dataset-ids)
      if [[ $# -lt 2 ]] || [[ -z "$2" ]]; then
        echo "ERROR: --dataset-ids requires a comma-separated list" >&2
        exit 2
      fi
      DATASET_IDS_OPTION="$2"
      shift 2
      ;;
    --run-label)
      if [[ $# -lt 2 ]] || [[ ! "$2" =~ ^[a-z0-9][a-z0-9_]*$ ]]; then
        echo "ERROR: --run-label requires [a-z0-9][a-z0-9_]*" >&2
        exit 2
      fi
      RUN_LABEL="$2"
      shift 2
      ;;
    --binary)
      if [[ $# -lt 2 ]] || [[ ! -f "$2" ]]; then
        echo "ERROR: --binary requires an existing file" >&2
        exit 2
      fi
      BINARY_OVERRIDE="$2"
      shift 2
      ;;
    --only-seed)
      if [[ $# -lt 2 ]] || [[ ! "$2" =~ ^[0-4]$ ]]; then
        echo "ERROR: --only-seed requires an integer from 0 to 4" >&2
        exit 2
      fi
      ONLY_SEED="$2"
      shift 2
      ;;
    --print-run-id)
      PRINT_RUN_ID=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ $FORCE -eq 1 ]] && [[ $RESUME -eq 1 ]]; then
  echo "ERROR: --force and --resume are mutually exclusive" >&2
  exit 2
fi
if [[ $SAME_TIER_PRECISION -eq 1 ]] &&
   [[ $PRECISION_FLOOR_BITS -eq 0 ]]; then
  echo "ERROR: --same-tier-precision requires --precision-floor" >&2
  exit 2
fi

REPOSITORY_ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." &&
    pwd
)"
cd "$REPOSITORY_ROOT" || exit 1

SPLIT_ROOT="$SPLIT_ROOT_OPTION"
BASE_ROOT="results/thesis_grade_protocol/direct_tabular_autotune_v1"
POLICY_COMPONENTS=()
AUTOTUNE_POLICY_ARGS=(
  --margin-floor "$MARGIN_FLOOR"
  --safety-factor "$SAFETY_FACTOR"
  --key-repeats "$KEY_REPEATS"
)
if [[ -n "$RUN_LABEL" ]]; then
  POLICY_COMPONENTS+=("$RUN_LABEL")
fi
if [[ $MATERIALIZE_MODEL_INPUT -eq 1 ]]; then
  POLICY_COMPONENTS+=("inputmodel")
fi
if [[ "$MARGIN_FLOOR" != "0.001" ]]; then
  MARGIN_SLUG="${MARGIN_FLOOR//./p}"
  MARGIN_SLUG="${MARGIN_SLUG//-/m}"
  MARGIN_SLUG="${MARGIN_SLUG//+/}"
  POLICY_COMPONENTS+=("margin${MARGIN_SLUG}")
fi
if [[ "$SAFETY_FACTOR" != "0.5" ]]; then
  SAFETY_SLUG="${SAFETY_FACTOR//./p}"
  SAFETY_SLUG="${SAFETY_SLUG//-/m}"
  SAFETY_SLUG="${SAFETY_SLUG//+/}"
  POLICY_COMPONENTS+=("alpha${SAFETY_SLUG}")
fi
if [[ $PRECISION_FLOOR_BITS -gt 0 ]]; then
  POLICY_COMPONENTS+=("floor${PRECISION_FLOOR_BITS}")
  AUTOTUNE_POLICY_ARGS+=(
    --min-scale-bits "$PRECISION_FLOOR_BITS"
    --min-prime-bits "$PRECISION_FLOOR_BITS"
    --special-prime-bits 30
  )
fi
if [[ $SAME_TIER_PRECISION -eq 1 ]]; then
  POLICY_COMPONENTS+=("same_tier")
  AUTOTUNE_POLICY_ARGS+=(
    --precision-slack-mode maximize_within_min_log_n
  )
fi
if [[ $KEY_REPEATS -gt 1 ]]; then
  POLICY_COMPONENTS+=("keys${KEY_REPEATS}")
fi
POLICY_ID="default"
if [[ ${#POLICY_COMPONENTS[@]} -gt 0 ]]; then
  POLICY_ID=""
  for component in "${POLICY_COMPONENTS[@]}"; do
    if [[ -n "$POLICY_ID" ]]; then
      POLICY_ID="${POLICY_ID}_"
    fi
    POLICY_ID="${POLICY_ID}${component}"
  done
fi
RUN_ID="$MODE"
RUN_ROOT="$BASE_ROOT/$MODE"
if [[ "$POLICY_ID" != "default" ]]; then
  RUN_ID="${MODE}_${POLICY_ID}"
  RUN_ROOT="$BASE_ROOT/$RUN_ID"
fi
if [[ $PRINT_RUN_ID -eq 1 ]]; then
  printf '%s\n' "$RUN_ID"
  exit 0
fi

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
IFS=',' read -r -a DATASETS <<<"$DATASET_IDS_OPTION"
IFS=',' read -r -a MODELS <<<"$MODEL_IDS_OPTION"
if [[ ${#DATASETS[@]} -eq 0 ]] || [[ ${#MODELS[@]} -eq 0 ]]; then
  echo "ERROR: dataset and model allowlists must be non-empty" >&2
  exit 2
fi
for value in "${DATASETS[@]}" "${MODELS[@]}"; do
  if [[ ! "$value" =~ ^[A-Za-z0-9][A-Za-z0-9_]*$ ]]; then
    echo "ERROR: invalid dataset/model ID $value" >&2
    exit 2
  fi
done

case "$MODE" in
  smoke)
    SEEDS=(0)
    DATASETS=(iris_binary)
    MODELS=(linear_poly3)
    ;;
  seed0)
    SEEDS=(0)
    ;;
  full)
    SEEDS=(0 1 2 3 4)
    ;;
  *)
    echo "ERROR: unsupported mode $MODE" >&2
    exit 2
    ;;
esac

if [[ -n "$ONLY_SEED" ]]; then
  if [[ "$MODE" != "full" ]]; then
    echo "ERROR: --only-seed requires --full" >&2
    exit 2
  fi
  SEEDS=("$ONLY_SEED")
fi
EXPECTED_RUNS=$((
  ${#SEEDS[@]} * ${#DATASETS[@]} * ${#MODELS[@]}
))

if [[ ! -f "$SPLIT_ROOT/summary.json" ]]; then
  echo "ERROR: missing split summary $SPLIT_ROOT/summary.json" >&2
  exit 1
fi

if [[ -d "$RUN_ROOT" ]]; then
  if [[ $FORCE -eq 1 ]]; then
    rm -rf "$RUN_ROOT"
  elif [[ $RESUME -ne 1 ]]; then
    echo "ERROR: $RUN_ROOT already exists; use --resume or --force" >&2
    exit 1
  fi
fi

mkdir -p \
  "$RUN_ROOT/bin" \
  "$RUN_ROOT/logs" \
  "$RUN_ROOT/results" \
  "$RUN_ROOT/summary"
if [[ $MATERIALIZE_MODEL_INPUT -eq 1 ]]; then
  mkdir -p "$RUN_ROOT/materialized"
fi

BINARY="$RUN_ROOT/bin/flipguard-autotune"
STATUS_PATH="$RUN_ROOT/run_status.csv"

echo "=== build direct autotune binary ==="
if [[ -n "$BINARY_OVERRIDE" ]]; then
  cp "$BINARY_OVERRIDE" "$BINARY"
  chmod 0755 "$BINARY"
  BUILD_STATUS=$?
  echo "binary_source=frozen path=$BINARY_OVERRIDE"
else
  GOCACHE="$REPOSITORY_ROOT/$RUN_ROOT/go-cache" \
    go build -o "$BINARY" ./cmd/flipguard-autotune
  BUILD_STATUS=$?
  echo "binary_source=current_build"
fi
echo "binary_build_status=$BUILD_STATUS"
if [[ $BUILD_STATUS -ne 0 ]]; then
  exit 1
fi

if [[ ! -f "$STATUS_PATH" ]]; then
  printf '%s\n' \
    'run_id,split_seed,dataset_id,model_id,tag,status,exit_code,outcome,trials_used,result_path,stdout_log' \
    >"$STATUS_PATH"
fi

remove_status_row() {
  local tag="$1"
  python3 - "$STATUS_PATH" "$tag" <<'PYEOF'
import csv
import os
import sys
import tempfile
from pathlib import Path

path = Path(sys.argv[1])
tag = sys.argv[2]
with path.open("r", encoding="utf-8", newline="") as handle:
    reader = csv.DictReader(handle)
    fieldnames = list(reader.fieldnames or [])
    rows = [row for row in reader if row.get("tag") != tag]

if not fieldnames:
    raise SystemExit("ERROR: run-status CSV has no header")

with tempfile.NamedTemporaryFile(
    "w",
    encoding="utf-8",
    newline="",
    dir=path.parent,
    delete=False,
) as handle:
    temporary = Path(handle.name)
    writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
os.replace(temporary, path)
PYEOF
}

append_status_row() {
  python3 - "$STATUS_PATH" "$@" <<'PYEOF'
import csv
import sys
from pathlib import Path

path = Path(sys.argv[1])
keys = [
    "run_id",
    "split_seed",
    "dataset_id",
    "model_id",
    "tag",
    "status",
    "exit_code",
    "outcome",
    "trials_used",
    "result_path",
    "stdout_log",
]
values = sys.argv[2:]
if len(keys) != len(values):
    raise SystemExit("ERROR: invalid status-row argument count")
row = dict(zip(keys, values))
with path.open("a", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=keys, lineterminator="\n")
    writer.writerow(row)
PYEOF
}

read_result_field() {
  local result_path="$1"
  local field="$2"
  python3 - "$result_path" "$field" <<'PYEOF'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
value = payload[sys.argv[2]]
print(value)
PYEOF
}

workload_total=0
workload_started=0
workload_ok=0
workload_failed=0
workload_skipped=0
stopped_early=0

for seed in "${SEEDS[@]}"; do
  for dataset in "${DATASETS[@]}"; do
    for model in "${MODELS[@]}"; do
      workload_total=$((workload_total + 1))

      split_id="split_seed_${seed}"
      model_path="datasets/tabular_suite/${dataset}/${model}/model.json"
      validation_path="$SPLIT_ROOT/$split_id/${dataset}/${model}/configuration_validation.csv"
      tag="directv1_${RUN_ID}_seed${seed}_${dataset}_${model}"
      result_path="$RUN_ROOT/results/${tag}.json"
      stdout_log="$RUN_ROOT/logs/${tag}.txt"
      materialized_path=""
      INPUT_ARGS=(
        --validation "$validation_path"
      )
      if [[ $MATERIALIZE_MODEL_INPUT -eq 1 ]]; then
        materialized_path="$RUN_ROOT/materialized/${tag}.csv"
        INPUT_ARGS=(
          --data "$validation_path"
          --data-space model
          --prepared-validation-out "$materialized_path"
        )
      fi

      if [[ ! -f "$model_path" ]]; then
        echo "ERROR: missing model artifact $model_path" >&2
        exit 1
      fi
      if [[ ! -f "$validation_path" ]]; then
        echo "ERROR: missing validation split $validation_path" >&2
        exit 1
      fi

      if [[ $RESUME -eq 1 ]] &&
         [[ -f "$result_path" ]] &&
         grep -Fq ",${tag},ok,0," "$STATUS_PATH"; then
        if [[ $QUIET_SKIPS -ne 1 ]]; then
          echo "SKIP completed workload: $tag"
        fi
        workload_skipped=$((workload_skipped + 1))
        continue
      fi

      if [[ $RESUME -eq 1 ]] &&
         [[ $RETRY_FAILED -ne 1 ]] &&
         [[ -f "$stdout_log" ]] &&
         grep -Eq ",${tag},failed,[1-9][0-9]*," "$STATUS_PATH"; then
        if [[ $QUIET_SKIPS -ne 1 ]]; then
          echo "SKIP terminal FAILED workload: $tag"
        fi
        workload_skipped=$((workload_skipped + 1))
        continue
      fi

      if [[ $MAX_NEW_RUNS -gt 0 ]] &&
         [[ $workload_started -ge $MAX_NEW_RUNS ]]; then
        stopped_early=1
        break 3
      fi

      workload_started=$((workload_started + 1))
      remove_status_row "$tag"
      rm -f "$result_path" "$stdout_log"
      if [[ -n "$materialized_path" ]]; then
        rm -f "$materialized_path"
      fi

      echo
      echo "RUN seed=$seed dataset=$dataset model=$model"
      set +e
      "$BINARY" \
        --model "$model_path" \
        "${INPUT_ARGS[@]}" \
        --split-id "$split_id" \
        --out "$result_path" \
        "${AUTOTUNE_POLICY_ARGS[@]}" \
        >"$stdout_log" 2>&1
      exit_code=$?
      set -e

      outcome=""
      trials_used=""
      if [[ $exit_code -eq 0 ]] && [[ -f "$result_path" ]]; then
        if outcome="$(read_result_field "$result_path" outcome)" &&
           trials_used="$(read_result_field "$result_path" trials_used)"; then
          status="ok"
          workload_ok=$((workload_ok + 1))
        else
          status="failed"
          exit_code=1
          workload_failed=$((workload_failed + 1))
        fi
      else
        status="failed"
        workload_failed=$((workload_failed + 1))
      fi

      append_status_row \
        "$RUN_ID" \
        "$seed" \
        "$dataset" \
        "$model" \
        "$tag" \
        "$status" \
        "$exit_code" \
        "$outcome" \
        "$trials_used" \
        "$result_path" \
        "$stdout_log"

      echo "workload_status=$status outcome=$outcome trials=$trials_used tag=$tag"
    done
  done
done

echo
echo "workload_total_seen=$workload_total"
echo "workload_started=$workload_started"
echo "workload_ok=$workload_ok"
echo "workload_failed=$workload_failed"
echo "workload_skipped=$workload_skipped"
echo "stopped_early=$stopped_early"

SUMMARY_ARGS=()
if [[ $MATERIALIZE_MODEL_INPUT -eq 1 ]]; then
  SUMMARY_ARGS+=(--require-source-replay)
fi
python3 scripts/summarize_direct_tabular_autotune.py \
  --run-status "$STATUS_PATH" \
  --output-root "$RUN_ROOT/summary" \
  --expected-runs "$EXPECTED_RUNS" \
  "${SUMMARY_ARGS[@]}"
SUMMARY_STATUS=$?
echo "summary_status=$SUMMARY_STATUS"
if [[ $SUMMARY_STATUS -ne 0 ]]; then
  exit 1
fi

if [[ $stopped_early -eq 1 ]]; then
  echo "direct_autotune_checkpoint=PASS"
else
  echo "direct_autotune_matrix=PASS"
fi
