#!/usr/bin/env bash
set -uo pipefail

MODE="seed0"
SELECTION_RUN_ID="seed0_floor18_keys3"
KEY_REPEATS=3
FORCE=0
RESUME=0
RETRY_FAILED=0
QUIET_SKIPS=0
MAX_NEW_RUNS=0
ONLY_SEED=""

usage() {
  cat <<'EOF'
usage: scripts/run_direct_tabular_locked_audit_matrix.sh [OPTIONS]

Modes:
  --smoke       Audit iris_binary/linear_poly3 on split seed 0.
  --seed0       Audit five datasets and two models on split seed 0 (default).
  --full        Audit five datasets, two models, and split seeds 0..4.

Inputs and execution:
  --selection-run ID   Existing direct-autotune run ID.
  --key-repeats N      Fresh-key audit runs per frozen configuration.
  --only-seed N        In --full mode, run only split seed N (0..4).
  --resume             Resume an existing audit ledger.
  --force              Replace only this run's locked-audit artifacts.
  --retry-failed       Retry terminal execution failures when resuming.
  --max-new-runs N     Stop after N newly started workloads.
  --quiet-skips        Suppress one-line messages for resumed workloads.
  -h, --help           Show this help.
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
    --selection-run)
      if [[ $# -lt 2 ]] || [[ -z "$2" ]]; then
        echo "ERROR: --selection-run requires an ID" >&2
        exit 2
      fi
      SELECTION_RUN_ID="$2"
      shift 2
      ;;
    --key-repeats)
      if [[ $# -lt 2 ]] || [[ ! "$2" =~ ^[1-9][0-9]*$ ]]; then
        echo "ERROR: --key-repeats requires a positive integer" >&2
        exit 2
      fi
      KEY_REPEATS="$2"
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

BASE_ROOT="results/thesis_grade_protocol/direct_tabular_autotune_v1"
RUN_ROOT="$BASE_ROOT/$SELECTION_RUN_ID"
SPLIT_ROOT="results/thesis_grade_protocol/tabular_splits_v1"
AUDIT_ID="${SELECTION_RUN_ID}_locked_audit_keys${KEY_REPEATS}"
AUDIT_ROOT="$RUN_ROOT/locked_audit/$AUDIT_ID"
RESULT_ROOT="$AUDIT_ROOT/results"
LOG_ROOT="$AUDIT_ROOT/logs"
SUMMARY_ROOT="$AUDIT_ROOT/summary"
STATUS_PATH="$AUDIT_ROOT/locked_audit_status.csv"
BINARY="$AUDIT_ROOT/flipguard-audit"

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

if [[ -n "$ONLY_SEED" ]]; then
  if [[ "$MODE" != "full" ]]; then
    echo "ERROR: --only-seed requires --full" >&2
    exit 2
  fi
  SEEDS=("$ONLY_SEED")
fi

if [[ ! -d "$RUN_ROOT/results" ]]; then
  echo "ERROR: missing selection run $RUN_ROOT/results" >&2
  exit 1
fi
if [[ ! -f "$SPLIT_ROOT/summary.json" ]]; then
  echo "ERROR: missing split summary $SPLIT_ROOT/summary.json" >&2
  exit 1
fi

if [[ -d "$AUDIT_ROOT" ]] && [[ $FORCE -ne 1 ]] &&
   [[ $RESUME -ne 1 ]]; then
  echo "ERROR: $AUDIT_ROOT already exists; use --resume or --force" >&2
  exit 1
fi
if [[ $FORCE -eq 1 ]]; then
  rm -f "$STATUS_PATH" "$BINARY"
  if [[ -d "$RESULT_ROOT" ]]; then
    find "$RESULT_ROOT" -type f -delete
  fi
  if [[ -d "$LOG_ROOT" ]]; then
    find "$LOG_ROOT" -type f -delete
  fi
  if [[ -d "$SUMMARY_ROOT" ]]; then
    find "$SUMMARY_ROOT" -type f -delete
  fi
fi

mkdir -p "$RESULT_ROOT" "$LOG_ROOT" "$SUMMARY_ROOT"

echo "=== build locked audit binary ==="
GOCACHE="$REPOSITORY_ROOT/$AUDIT_ROOT/go-cache" \
  go build -o "$BINARY" ./cmd/flipguard-audit
BUILD_STATUS=$?
echo "binary_build_status=$BUILD_STATUS"
if [[ $BUILD_STATUS -ne 0 ]]; then
  exit 1
fi

if [[ ! -f "$STATUS_PATH" ]]; then
  printf '%s\n' \
    'run_id,split_seed,dataset_id,model_id,tag,status,exit_code,outcome,result_path,selection_path,audit_path,manifest_path,stdout_log' \
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
    raise SystemExit("ERROR: locked-audit status CSV has no header")
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
    "result_path",
    "selection_path",
    "audit_path",
    "manifest_path",
    "stdout_log",
]
values = sys.argv[2:]
if len(keys) != len(values):
    raise SystemExit("ERROR: invalid status-row argument count")
with path.open("a", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=keys,
        lineterminator="\n",
    )
    writer.writerow(dict(zip(keys, values)))
PYEOF
}

read_outcome() {
  python3 - "$1" <<'PYEOF'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(payload["outcome"])
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
      selection_tag="directv1_${SELECTION_RUN_ID}_seed${seed}_${dataset}_${model}"
      selection_path="$RUN_ROOT/results/${selection_tag}.json"
      split_workload="$SPLIT_ROOT/$split_id/$dataset/$model"
      audit_path="$split_workload/locked_audit_test.csv"
      manifest_path="$split_workload/split_manifest.json"
      tag="${selection_tag}_locked_audit_keys${KEY_REPEATS}"
      result_path="$RESULT_ROOT/${tag}.json"
      stdout_log="$LOG_ROOT/${tag}.txt"

      for required in \
        "$selection_path" \
        "$audit_path" \
        "$manifest_path"; do
        if [[ ! -f "$required" ]]; then
          echo "ERROR: missing required artifact $required" >&2
          exit 1
        fi
      done

      if [[ $RESUME -eq 1 ]] &&
         [[ -f "$result_path" ]] &&
         grep -Fq ",${tag},ok,0," "$STATUS_PATH"; then
        if [[ $QUIET_SKIPS -ne 1 ]]; then
          echo "SKIP completed locked audit: $tag"
        fi
        workload_skipped=$((workload_skipped + 1))
        continue
      fi
      if [[ $RESUME -eq 1 ]] &&
         [[ $RETRY_FAILED -ne 1 ]] &&
         [[ -f "$stdout_log" ]] &&
         grep -Eq ",${tag},failed,[1-9][0-9]*," "$STATUS_PATH"; then
        if [[ $QUIET_SKIPS -ne 1 ]]; then
          echo "SKIP terminal execution failure: $tag"
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
      echo "AUDIT seed=$seed dataset=$dataset model=$model"
      set +e
      "$BINARY" \
        --selection "$selection_path" \
        --audit "$audit_path" \
        --manifest "$manifest_path" \
        --key-repeats "$KEY_REPEATS" \
        --out "$result_path" \
        >"$stdout_log" 2>&1
      exit_code=$?
      set -e

      outcome=""
      if [[ $exit_code -eq 0 ]] && [[ -f "$result_path" ]]; then
        if outcome="$(read_outcome "$result_path")"; then
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
        "$AUDIT_ID" \
        "$seed" \
        "$dataset" \
        "$model" \
        "$tag" \
        "$status" \
        "$exit_code" \
        "$outcome" \
        "$result_path" \
        "$selection_path" \
        "$audit_path" \
        "$manifest_path" \
        "$stdout_log"

      echo "audit_status=$status outcome=$outcome tag=$tag"
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

python3 scripts/summarize_direct_tabular_locked_audit.py \
  --run-status "$STATUS_PATH" \
  --output-root "$SUMMARY_ROOT" \
  --expected-runs "$EXPECTED_RUNS"
SUMMARY_STATUS=$?
echo "summary_status=$SUMMARY_STATUS"
if [[ $SUMMARY_STATUS -ne 0 ]]; then
  exit 1
fi

if [[ $stopped_early -eq 1 ]]; then
  echo "locked_audit_checkpoint=PASS"
else
  echo "locked_audit_matrix=PASS"
fi
