#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <run_id>" >&2
  exit 64
fi

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
RUN_ID=$1
RUN_ROOT="$ROOT/results/model_family_expansion_v17/runs/$RUN_ID"
LOG_ROOT="$RUN_ROOT/supervisor"
mkdir -p "$LOG_ROOT"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
export GOMAXPROCS=6

if [[ ! -f "$RUN_ROOT/run_manifest.json" ]]; then
  echo "missing run manifest: $RUN_ROOT/run_manifest.json" >&2
  exit 65
fi

printf '%s\n' "$$" > "$RUN_ROOT/supervisor.pid"
printf '%s\n' "GOMAXPROCS=6 taskset -c 0-5 $0 $RUN_ID" > "$RUN_ROOT/supervisor.command"

taskset -c 0-5 python3 "$ROOT/scripts/capture_v17_vm1x6_telemetry.py" \
  --run-root "$RUN_ROOT" --interval-seconds 10 \
  >> "$LOG_ROOT/telemetry.log" 2>&1 &
TELEMETRY_PID=$!
printf '%s\n' "$TELEMETRY_PID" > "$RUN_ROOT/telemetry.pid"

stop_telemetry() {
  : > "$RUN_ROOT/TELEMETRY_STOP"
  wait "$TELEMETRY_PID" || true
}
trap stop_telemetry EXIT INT TERM

no_progress=0
iteration=0
previous_terminal=-1
while true; do
  iteration=$((iteration + 1))
  taskset -c 0-5 python3 "$ROOT/scripts/verify_model_family_expansion_v17_vm1x6.py" \
    --run-id "$RUN_ID" --progress > "$LOG_ROOT/verify-before-${iteration}.json"
  read -r terminal pending running retryable < <(
    python3 - "$RUN_ROOT/run_status.csv" <<'PY'
import csv,sys
rows=list(csv.DictReader(open(sys.argv[1], newline='', encoding='utf-8')))
terminal=sum(row['state'] in {'DONE','FAILED_RECORDED','UNSUPPORTED_RECORDED'} for row in rows)
pending=sum(row['state'] in {'PENDING','PENDING_DEPENDENCY'} for row in rows)
running=sum(row['state']=='RUNNING' for row in rows)
retryable=sum(row['state']=='RETRYABLE' for row in rows)
print(terminal,pending,running,retryable)
PY
  )
  if [[ "$pending" -eq 0 && "$running" -eq 0 && "$retryable" -eq 0 ]]; then
    break
  fi
  if [[ "$terminal" -eq "$previous_terminal" ]]; then
    no_progress=$((no_progress + 1))
  else
    no_progress=0
  fi
  if [[ "$no_progress" -ge 3 ]]; then
    echo "INFRASTRUCTURE_BLOCK: no terminal progress for three supervisor iterations" >&2
    exit 75
  fi
  previous_terminal=$terminal
  taskset -c 0-5 python3 "$ROOT/scripts/run_model_family_expansion_v17_vm1x6.py" \
    --run-id "$RUN_ID" --run-root "$RUN_ROOT" --resume --clear-stop-request --phase all \
    >> "$LOG_ROOT/runner.log" 2>&1 || true
done

taskset -c 0-5 python3 "$ROOT/scripts/verify_model_family_expansion_v17_vm1x6.py" \
  --run-id "$RUN_ID" --require-complete > "$LOG_ROOT/verify-complete.json"
taskset -c 0-5 python3 "$ROOT/scripts/finalize_model_family_expansion_v17_vm1x6.py" \
  --run-id "$RUN_ID" >> "$LOG_ROOT/finalize.log" 2>&1

printf '%s\n' "COMPLETE" > "$RUN_ROOT/SUPERVISOR_COMPLETE"
