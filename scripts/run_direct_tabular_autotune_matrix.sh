#!/usr/bin/env bash
set -uo pipefail

MODE="seed0"
FORCE=0
RESUME=0
RETRY_FAILED=0
QUIET_SKIPS=0
MAX_NEW_RUNS=0

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

REPOSITORY_ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." &&
    pwd
)"
cd "$REPOSITORY_ROOT" || exit 1

SPLIT_ROOT="results/thesis_grade_protocol/tabular_splits_v1"
BASE_ROOT="results/thesis_grade_protocol/direct_tabular_autotune_v1"
RUN_ROOT="$BASE_ROOT/$MODE"

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

case "$MODE" in
  smoke)
    SEEDS=(0)
    DATASETS=(iris_binary)
    MODELS=(linear_poly3)
    EXPECTED_RUNS=1
    ;;
  seed0)
    SEEDS=(0)
    EXPECTED_RUNS=10
    ;;
  full)
    SEEDS=(0 1 2 3 4)
    EXPECTED_RUNS=50
    ;;
  *)
    echo "ERROR: unsupported mode $MODE" >&2
    exit 2
    ;;
esac

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

mkdir -p "$RUN_ROOT/bin" "$RUN_ROOT/logs" "$RUN_ROOT/results" "$RUN_ROOT/summary"

BINARY="$RUN_ROOT/bin/flipguard-autotune"
STATUS_PATH="$RUN_ROOT/run_status.csv"

echo "=== build direct autotune binary ==="
go build -o "$BINARY" ./cmd/flipguard-autotune
BUILD_STATUS=$?
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
      tag="directv1_${MODE}_seed${seed}_${dataset}_${model}"
      result_path="$RUN_ROOT/results/${tag}.json"
      stdout_log="$RUN_ROOT/logs/${tag}.txt"

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

      echo
      echo "RUN seed=$seed dataset=$dataset model=$model"
      set +e
      "$BINARY" \
        --model "$model_path" \
        --validation "$validation_path" \
        --split-id "$split_id" \
        --out "$result_path" \
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
        "$MODE" \
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

python3 scripts/summarize_direct_tabular_autotune.py \
  --run-status "$STATUS_PATH" \
  --output-root "$RUN_ROOT/summary" \
  --expected-runs "$EXPECTED_RUNS"
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
