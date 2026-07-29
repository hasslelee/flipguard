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

python3 - \
  "$SELECTION_ROOT" \
  "$AUDIT_ROOT" \
  "$SPLIT_ROOT/summary.json" \
  "${SOURCE_PATHS[@]}" <<'PYEOF'
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

repo = Path.cwd()
selection_root = Path(sys.argv[1])
audit_root = Path(sys.argv[2])
split_summary_path = Path(sys.argv[3])
source_paths = sys.argv[4:]


def sha256_path(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


selection_summary_path = selection_root / "summary/summary.json"
selection_rows_path = selection_root / "summary/workload_results.csv"
audit_summary_path = audit_root / "summary/summary.json"
audit_rows_path = audit_root / "summary/locked_audit_results.csv"
selection_summary = load_json(selection_summary_path)
audit_summary = load_json(audit_summary_path)
selection_rows = load_csv(selection_rows_path)
audit_rows = load_csv(audit_rows_path)

if (
    selection_summary.get("successful_runs") != 25
    or selection_summary.get("selected_runs") != 25
    or selection_summary.get("failed_runs") != 0
    or selection_summary.get("require_source_replay") is not True
    or selection_summary.get("source_replay_verified_runs") != 25
    or len(selection_rows) != 25
):
    raise SystemExit("ERROR: structural selection is incomplete")
if (
    audit_summary.get("locked_audit_passes") != 25
    or audit_summary.get("locked_audit_fails") != 0
    or audit_summary.get("retuned_runs") != 0
    or audit_summary.get("require_source_replay") is not True
    or audit_summary.get("source_replay_verified_runs") != 25
    or audit_summary.get("audit_source_replay_verified_runs") != 25
    or len(audit_rows) != 25
):
    raise SystemExit("ERROR: structural locked audit is incomplete")
if (
    sum(int(row["v_cert"]) for row in selection_rows) != 3992
    or sum(int(row["v_amb"]) for row in selection_rows) != 123
    or audit_summary.get("total_v_cert") != 4033
    or audit_summary.get("total_v_amb") != 117
):
    raise SystemExit("ERROR: structural coverage checkpoint changed")
if any(
    row["model_id"] != "mlp_square_poly3"
    or row["selected_trial_status"] != "SAFE"
    or int(row["decision_flips"]) != 0
    or int(row["error_violations"]) != 0
    or row["source_replay_verified"] != "True"
    or float(row["max_error_budget_usage"]) >= 1
    for row in selection_rows
):
    raise SystemExit("ERROR: structural selection safety check failed")
if any(
    row["outcome"] != "LOCKED_AUDIT_PASS"
    or row["trial_status"] != "SAFE"
    or row["retuning_performed"] != "False"
    or int(row["decision_flips"]) != 0
    or int(row["error_violations"]) != 0
    or row["source_replay_verified"] != "True"
    or row["audit_source_replay_verified"] != "True"
    or float(row["max_error_budget_usage"]) >= 1
    for row in audit_rows
):
    raise SystemExit("ERROR: structural audit safety check failed")

for row in selection_rows:
    result = load_json(repo / row["result_path"])
    contract = result["plan"]["contract"]
    if (
        contract["model_type"] != "mlp_square_poly3"
        or contract["graph"]["multiplicative_depth"] != 3
        or contract["deployment"]["required_q_primes"] != 10
        or (
            contract["input_materialization"][
                "source_replay_verified"
            ]
            is not True
        )
    ):
        raise SystemExit("ERROR: structural contract shape changed")

for row in audit_rows:
    result = load_json(repo / row["result_path"])
    materialization = result["audit_contract"][
        "input_materialization"
    ]
    if (
        materialization["source_replay_verified"] is not True
        or materialization["source_feature_space"] != "model_input"
        or materialization["preprocessing_method"]
        != "identity_model_input_v1"
    ):
        raise SystemExit(
            "ERROR: structural audit source replay changed"
        )

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
    "experiment_id": "structural_extension_v1",
    "status": "COMPLETE",
    "claim_boundary": (
        "Observed support for mlp_square_poly3 on the frozen scalar-tabular "
        "five-split scope; not arbitrary graph or CNN support."
    ),
    "counts": {
        "workloads": 25,
        "selection_passes": 25,
        "audit_passes": 25,
        "validation_v_cert": 3992,
        "validation_v_amb": 123,
        "audit_v_cert": 4033,
        "audit_v_amb": 117,
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
    "inputs": {
        "split_summary": {
            "path": str(split_summary_path),
            "sha256": sha256_path(split_summary_path),
        }
    },
    "outputs": {
        "selection_summary": {
            "path": str(selection_summary_path),
            "sha256": sha256_path(selection_summary_path),
        },
        "selection_rows": {
            "path": str(selection_rows_path),
            "sha256": sha256_path(selection_rows_path),
        },
        "audit_summary": {
            "path": str(audit_summary_path),
            "sha256": sha256_path(audit_summary_path),
        },
        "audit_rows": {
            "path": str(audit_rows_path),
            "sha256": sha256_path(audit_rows_path),
        },
    },
}
manifest_path = selection_root / "summary/structural_protocol.json"
manifest_path.write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(f"structural_protocol={manifest_path}")
print("structural_extension=PASS")
PYEOF
