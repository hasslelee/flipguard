#!/usr/bin/env bash
set -euo pipefail

ACTION="--resume"
AUTOTUNE_BINARY=""
AUDIT_BINARY=""

usage() {
  cat <<'EOF'
usage: scripts/run_structural_extension.sh [OPTIONS]

Runs the frozen 25-workload mlp_square_poly3 selection and disjoint locked
audit from a clean committed measurement source.

Options:
  --resume   Resume completed workload artifacts (default).
  --force    Replace structural selection and audit artifacts.
  --autotune-binary PATH
             Reuse the frozen direct-selection binary.
  --audit-binary PATH
             Reuse the frozen locked-audit binary.
  -h, --help Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --resume)
      ACTION="--resume"
      shift
      ;;
    --force)
      ACTION="--force"
      shift
      ;;
    --autotune-binary)
      if [[ $# -lt 2 ]] || [[ ! -f "$2" ]]; then
        echo "ERROR: --autotune-binary requires an existing file" >&2
        exit 2
      fi
      AUTOTUNE_BINARY="$2"
      shift 2
      ;;
    --audit-binary)
      if [[ $# -lt 2 ]] || [[ ! -f "$2" ]]; then
        echo "ERROR: --audit-binary requires an existing file" >&2
        exit 2
      fi
      AUDIT_BINARY="$2"
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

REPOSITORY_ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." &&
    pwd
)"
cd "$REPOSITORY_ROOT"

SOURCE_PATHS=(
  cmd/flipguard-autotune
  cmd/flipguard-audit
  internal
  go.mod
  go.sum
  scripts/build_thesis_grade_tabular_splits.py
  scripts/run_direct_tabular_autotune_matrix.sh
  scripts/run_direct_tabular_locked_audit_matrix.sh
  scripts/run_structural_extension.sh
  scripts/summarize_direct_tabular_autotune.py
  scripts/summarize_direct_tabular_locked_audit.py
)
source_status="$(
  git status --porcelain --untracked-files=all -- "${SOURCE_PATHS[@]}"
)"
if [[ -n "$source_status" ]]; then
  echo "ERROR: structural extension requires clean committed source:" >&2
  printf '%s\n' "$source_status" >&2
  exit 1
fi

SPLIT_ROOT="results/thesis_grade_protocol/structural_extension_splits_v1"
EXPECTED_SPLIT_DIGEST="sha256:8e1ac4e74e086a86944510023c0312f5ee77b0dedeaaa4dc3d1b5332607fa609"
SELECTION_RUN_ID="full_structural_poly3_inputmodel_floor18_keys3"
SELECTION_ROOT="results/thesis_grade_protocol/direct_tabular_autotune_v1/$SELECTION_RUN_ID"
AUDIT_ID="${SELECTION_RUN_ID}_locked_audit_keys3"
AUDIT_ROOT="$SELECTION_ROOT/locked_audit/$AUDIT_ID"

python3 scripts/build_thesis_grade_tabular_splits.py \
  --output-root "$SPLIT_ROOT" \
  --model-ids mlp_square_poly3 \
  --force

actual_split_digest="$(
  python3 - "$SPLIT_ROOT/summary.json" <<'PYEOF'
import hashlib
import sys
from pathlib import Path

path = Path(sys.argv[1])
print("sha256:" + hashlib.sha256(path.read_bytes()).hexdigest())
PYEOF
)"
if [[ "$actual_split_digest" != "$EXPECTED_SPLIT_DIGEST" ]]; then
  echo "ERROR: structural split digest changed" >&2
  echo "actual=$actual_split_digest" >&2
  echo "expected=$EXPECTED_SPLIT_DIGEST" >&2
  exit 1
fi

AUTOTUNE_BINARY_ARGS=()
if [[ -n "$AUTOTUNE_BINARY" ]]; then
  AUTOTUNE_BINARY_ARGS=(--binary "$AUTOTUNE_BINARY")
fi
scripts/run_direct_tabular_autotune_matrix.sh \
  --full \
  --split-root "$SPLIT_ROOT" \
  --model-ids mlp_square_poly3 \
  --run-label structural_poly3 \
  --materialize-model-input \
  --precision-floor 18 \
  --key-repeats 3 \
  "${AUTOTUNE_BINARY_ARGS[@]}" \
  "$ACTION"

AUDIT_BINARY_ARGS=()
if [[ -n "$AUDIT_BINARY" ]]; then
  AUDIT_BINARY_ARGS=(--binary "$AUDIT_BINARY")
fi
scripts/run_direct_tabular_locked_audit_matrix.sh \
  --full \
  --selection-run "$SELECTION_RUN_ID" \
  --materialize-model-input \
  --split-root "$SPLIT_ROOT" \
  --model-ids mlp_square_poly3 \
  --key-repeats 3 \
  "${AUDIT_BINARY_ARGS[@]}" \
  "$ACTION"

python3 scripts/build_structural_extension_status.py --force
