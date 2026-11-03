#!/usr/bin/env bash
set -euo pipefail

MODE="smoke"

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

cd "$REPOSITORY_ROOT"

ORACLE_ROOT="results/thesis_grade_protocol/tabular_validation_oracle_v1/$MODE/summary"
OUTPUT_ROOT="results/thesis_grade_protocol/planner_oracle_comparison_v1/$MODE"

CANDIDATES="$ORACLE_ROOT/candidate_certificates.csv"
COVERAGE="$ORACLE_ROOT/validation_coverage.csv"
ORACLE_SUMMARY="$ORACLE_ROOT/summary.json"

if [[ ! -f "$CANDIDATES" ]]; then
  echo "ERROR: missing oracle candidate certificates $CANDIDATES" >&2
  exit 1
fi

if [[ ! -f "$COVERAGE" ]]; then
  echo "ERROR: missing oracle validation coverage $COVERAGE" >&2
  exit 1
fi

if [[ ! -f "$ORACLE_SUMMARY" ]]; then
  echo "ERROR: missing oracle summary $ORACLE_SUMMARY" >&2
  exit 1
fi

if [[ "$MODE" == "full" ]]; then
  python3 - "$ORACLE_SUMMARY" <<'PYEOF'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
summary = json.loads(path.read_text(encoding="utf-8"))

actual = int(summary["actual_run_count"])
expected = int(summary["expected_full_run_count"])
allow_incomplete = bool(summary["allow_incomplete"])

if allow_incomplete or actual != expected:
    raise SystemExit(
        "ERROR: full planner/oracle comparison requires a strict "
        f"complete oracle; allow_incomplete={allow_incomplete} "
        f"actual={actual} expected={expected}"
    )
PYEOF
fi

go run ./cmd/flipguard-planner-oracle \
  -candidate-certificates "$CANDIDATES" \
  -validation-coverage "$COVERAGE" \
  -output-root "$OUTPUT_ROOT" \
  -selection-metric mean_total_ms

echo
echo "Planner/oracle comparison:"
sed -n '1,12p' "$OUTPUT_ROOT/comparison.csv"

echo
echo "Summary:"
sed -n '1,220p' "$OUTPUT_ROOT/summary.json"
