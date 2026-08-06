#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 PROVIDER" >&2
  exit 2
fi

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly PROVIDER="$1"
readonly STATUS="$ROOT/external/v7/status/$PROVIDER"
mkdir -p "$STATUS"

RUNNER="$ROOT/scripts/external_v7/providers/run_${PROVIDER//-/_}_v7.sh"
if [[ "$PROVIDER" == corelab && -d "$STATUS/0005-elasm-grid" ]]; then
  RUNNER="$ROOT/scripts/external_v7/providers/run_corelab_recovery_v7.sh"
elif [[ "$PROVIDER" == heir \
  && -f "$STATUS/0002-openfhe-lattigo-e2e/current_stage.txt" \
  && "$(<"$STATUS/0002-openfhe-lattigo-e2e/current_stage.txt")" == PASS ]]; then
  RUNNER="$ROOT/scripts/external_v7/providers/run_heir_recovery_v7.sh"
elif [[ "$PROVIDER" == heco \
  && -f "$STATUS/0004-official-encrypted-benchmark/current_stage.txt" \
  && "$(<"$STATUS/0004-official-encrypted-benchmark/current_stage.txt")" == PASS ]]; then
  RUNNER="$ROOT/scripts/external_v7/providers/run_heco_recovery_v7.sh"
fi
readonly RUNNER

if [[ ! -x "$RUNNER" ]]; then
  printf '%s\n' "NO_EXECUTABLE_RUNNER" > "$STATUS/final_state.txt"
  exit 0
fi

printf '%s\n' "$(date --iso-8601=seconds)" > "$STATUS/start_timestamp.txt"
printf '%s\n' "SOURCE_CHECKOUT" > "$STATUS/current_stage.txt"
printf '%s\n' "$$" > "$STATUS/pid.txt"
set +e
timeout --signal=TERM --kill-after=300s 4500s "$RUNNER"
rc=$?
set -e
printf '%s\n' "$rc" > "$STATUS/exit_code.txt"
printf '%s\n' "$(date --iso-8601=seconds)" > "$STATUS/end_timestamp.txt"
if [[ $rc -eq 0 ]]; then
  [[ -s "$STATUS/final_state.txt" ]] || printf '%s\n' "PROVIDER_FINALIZE" > "$STATUS/final_state.txt"
  exit 0
fi
printf '%s\n' "PROVIDER_FAILED_CONTINUE" > "$STATUS/final_state.txt"
exit "$rc"
