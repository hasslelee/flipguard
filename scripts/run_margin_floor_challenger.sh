#!/usr/bin/env bash
set -euo pipefail

ACTION="--resume"
MARGIN_FLOOR="0.0005"
SAFETY_FACTOR="0.5"
PRECISION_FLOOR_BITS=18
KEY_REPEATS=3

usage() {
  cat <<'EOF'
usage: scripts/run_margin_floor_challenger.sh [OPTIONS]

Runs the frozen 50-workload margin-floor challenger selection followed by its
disjoint no-retuning locked audit.

Options:
  --resume   Resume valid results and retry no completed work (default).
  --force    Replace the challenger selection and audit result directories.
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
  scripts/run_direct_tabular_autotune_matrix.sh
  scripts/run_direct_tabular_locked_audit_matrix.sh
  scripts/summarize_direct_tabular_autotune.py
  scripts/summarize_direct_tabular_locked_audit.py
  scripts/analyze_margin_floor_challenger.py
  scripts/run_margin_floor_challenger.sh
)

source_status="$(
  git status --porcelain --untracked-files=all -- "${SOURCE_PATHS[@]}"
)"
if [[ -n "$source_status" ]]; then
  echo "ERROR: challenger requires clean committed measurement source:" >&2
  printf '%s\n' "$source_status" >&2
  exit 1
fi

BASELINE_RUN_ID="full_final_baseline_inputmodel_floor18_keys3"
BASELINE_ROOT="results/thesis_grade_protocol/direct_tabular_autotune_v1/$BASELINE_RUN_ID"
BASELINE_AUDIT_ID="${BASELINE_RUN_ID}_locked_audit_keys3"
BASELINE_AUDIT_ROOT="$BASELINE_ROOT/locked_audit/$BASELINE_AUDIT_ID"
SELECTION_RUN_ID="full_inputmodel_margin0p0005_floor18_keys3"
SELECTION_ROOT="results/thesis_grade_protocol/direct_tabular_autotune_v1/$SELECTION_RUN_ID"
AUDIT_ID="${SELECTION_RUN_ID}_locked_audit_keys3"
AUDIT_ROOT="$SELECTION_ROOT/locked_audit/$AUDIT_ID"

scripts/run_direct_tabular_autotune_matrix.sh \
  --full \
  --run-label final_baseline \
  --materialize-model-input \
  --margin-floor 0.001 \
  --safety-factor "$SAFETY_FACTOR" \
  --precision-floor "$PRECISION_FLOOR_BITS" \
  --key-repeats "$KEY_REPEATS" \
  "$ACTION"

scripts/run_direct_tabular_locked_audit_matrix.sh \
  --full \
  --selection-run "$BASELINE_RUN_ID" \
  --materialize-model-input \
  --key-repeats "$KEY_REPEATS" \
  "$ACTION"

scripts/run_direct_tabular_autotune_matrix.sh \
  --full \
  --materialize-model-input \
  --margin-floor "$MARGIN_FLOOR" \
  --safety-factor "$SAFETY_FACTOR" \
  --precision-floor "$PRECISION_FLOOR_BITS" \
  --key-repeats "$KEY_REPEATS" \
  "$ACTION"

scripts/run_direct_tabular_locked_audit_matrix.sh \
  --full \
  --selection-run "$SELECTION_RUN_ID" \
  --materialize-model-input \
  --key-repeats "$KEY_REPEATS" \
  "$ACTION"

python3 - \
  "$BASELINE_ROOT" \
  "$BASELINE_AUDIT_ROOT" \
  "$SELECTION_ROOT" \
  "$AUDIT_ROOT" \
  "$MARGIN_FLOOR" \
  "$SAFETY_FACTOR" \
  "${SOURCE_PATHS[@]}" <<'PYEOF'
import hashlib
import json
import subprocess
import sys
from pathlib import Path

repo = Path.cwd()
baseline_root = Path(sys.argv[1])
baseline_audit_root = Path(sys.argv[2])
selection_root = Path(sys.argv[3])
audit_root = Path(sys.argv[4])
margin_floor = float(sys.argv[5])
safety_factor = float(sys.argv[6])
source_paths = sys.argv[7:]


def sha256_path(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


baseline_summary_path = baseline_root / "summary/summary.json"
baseline_audit_summary_path = baseline_audit_root / "summary/summary.json"
selection_summary_path = selection_root / "summary/summary.json"
audit_summary_path = audit_root / "summary/summary.json"
baseline_summary = json.loads(
    baseline_summary_path.read_text(encoding="utf-8")
)
baseline_audit_summary = json.loads(
    baseline_audit_summary_path.read_text(encoding="utf-8")
)
selection_summary = json.loads(
    selection_summary_path.read_text(encoding="utf-8")
)
audit_summary = json.loads(audit_summary_path.read_text(encoding="utf-8"))
if (
    baseline_summary.get("successful_runs") != 50
    or baseline_summary.get("selected_runs") != 50
    or baseline_summary.get("failed_runs") != 0
):
    raise SystemExit("ERROR: final-source baseline selection is incomplete")
if (
    baseline_audit_summary.get("locked_audit_passes") != 50
    or baseline_audit_summary.get("locked_audit_fails") != 0
    or baseline_audit_summary.get("retuned_runs") != 0
):
    raise SystemExit("ERROR: final-source baseline audit is incomplete")
if (
    selection_summary.get("successful_runs") != 50
    or selection_summary.get("failed_runs") != 0
):
    raise SystemExit("ERROR: challenger selection is incomplete")
if (
    audit_summary.get("locked_audit_passes") != 50
    or audit_summary.get("locked_audit_fails") != 0
):
    raise SystemExit("ERROR: challenger locked audit is incomplete")

tracked = subprocess.run(
    ["git", "ls-files", "--", *source_paths],
    cwd=repo,
    check=True,
    capture_output=True,
    text=True,
).stdout.splitlines()
source_files = {
    relative: {
        "bytes": (repo / relative).stat().st_size,
        "sha256": sha256_path(repo / relative),
    }
    for relative in sorted(tracked)
}
digest = hashlib.sha256()
for relative, item in source_files.items():
    digest.update(relative.encode("utf-8"))
    digest.update(b"\0")
    digest.update(item["sha256"].encode("ascii"))
    digest.update(b"\n")

manifest = {
    "schema_version": 1,
    "experiment_id": "margin_floor_challenger_v1",
    "status": "COMPLETE",
    "policy": {
        "margin_floor": margin_floor,
        "safety_factor": safety_factor,
        "precision_floor_bits": 18,
        "selection_key_repeats": 3,
        "audit_key_repeats": 3,
        "workloads": 50,
    },
    "source": {
        "commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "digest": "sha256:" + digest.hexdigest(),
        "files": source_files,
    },
    "outputs": {
        "baseline_selection_summary": {
            "path": str(baseline_summary_path),
            "sha256": sha256_path(baseline_summary_path),
        },
        "baseline_audit_summary": {
            "path": str(baseline_audit_summary_path),
            "sha256": sha256_path(baseline_audit_summary_path),
        },
        "selection_summary": {
            "path": str(selection_summary_path),
            "sha256": sha256_path(selection_summary_path),
        },
        "audit_summary": {
            "path": str(audit_summary_path),
            "sha256": sha256_path(audit_summary_path),
        },
    },
}
manifest_path = selection_root / "summary/challenger_protocol.json"
manifest_path.write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(f"challenger_protocol={manifest_path}")
print("margin_floor_challenger_execution=COMPLETE")
PYEOF

python3 scripts/analyze_margin_floor_challenger.py \
  --challenger-root "$SELECTION_ROOT" \
  --audit-root "$AUDIT_ROOT" \
  --baseline-root "$BASELINE_ROOT"
