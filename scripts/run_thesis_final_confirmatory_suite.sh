#!/usr/bin/env bash
set -euo pipefail

ACTION="--resume"
FORCE_FREEZE=()
FORCE_PYTHON=()
PREFLIGHT_ONLY=false
SKIP_REGRESSION=false

usage() {
  cat <<'EOF'
usage: scripts/run_thesis_final_confirmatory_suite.sh [OPTIONS]

Runs the clean-source FlipGuard confirmatory experiments and freezes their
publication-facing evidence packs.

Options:
  --resume          Resume valid experiment and evidence artifacts (default).
  --force           Rerun valid experiment artifacts and replace evidence.
  --preflight-only  Validate source and prerequisite evidence, then stop.
  --skip-regression Skip the full Go/Python/Bash regression checks.
  -h, --help        Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --resume)
      ACTION="--resume"
      FORCE_FREEZE=()
      FORCE_PYTHON=()
      shift
      ;;
    --force)
      ACTION="--force"
      FORCE_FREEZE=(--force)
      FORCE_PYTHON=(--force)
      shift
      ;;
    --preflight-only)
      PREFLIGHT_ONLY=true
      shift
      ;;
    --skip-regression)
      SKIP_REGRESSION=true
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
  cmd
  internal
  scripts
  go.mod
  go.sum
)
source_status="$(
  git status --porcelain --untracked-files=all -- "${SOURCE_PATHS[@]}"
)"
if [[ -n "$source_status" ]]; then
  echo "ERROR: final suite requires clean committed source:" >&2
  printf '%s\n' "$source_status" >&2
  exit 1
fi

SOURCE_COMMIT="$(git rev-parse HEAD)"
BASE_ROOT="results/thesis_grade_protocol/direct_tabular_autotune_v1"
LEGACY_BASELINE_ROOT="$BASE_ROOT/full_floor18_keys3"
LEGACY_BASELINE_AUDIT="$LEGACY_BASELINE_ROOT/locked_audit/full_floor18_keys3_locked_audit_keys3"
CATALOG_ORACLE_ROOT="results/thesis_grade_protocol/tabular_validation_oracle_v1/full/summary"
SECURITY_V2_ROOT="results/thesis_grade_protocol/security_v2_static_attestation"
SECURITY_ORACLE_ROOT="$SECURITY_V2_ROOT/bounded_oracle_security_v2"
LEGACY_COMPARISON_ROOT="results/thesis_grade_protocol/direct_vs_catalog_oracle_v1/full"
FINITE_ROOT="results/thesis_grade_protocol/finite_domain_no_safe_control_v1/full"

require_file() {
  if [[ ! -f "$1" ]]; then
    echo "ERROR: missing prerequisite $1" >&2
    exit 1
  fi
}

require_pack_commit() {
  local manifest_path="$1"
  local manifest_kind="$2"
  python3 - "$manifest_path" "$manifest_kind" "$SOURCE_COMMIT" <<'PYEOF'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
kind = sys.argv[2]
expected = sys.argv[3]
manifest = json.loads(path.read_text(encoding="utf-8"))
if kind == "direct":
    actual = manifest["source_code"]["git_commit"]
elif kind == "no_safe":
    actual = manifest["budget_source_commit"]
elif kind == "paired":
    actual = manifest["source"]["commit"]
else:
    raise SystemExit(f"ERROR: unsupported evidence kind {kind}")
if actual != expected:
    raise SystemExit(
        f"ERROR: {path} source commit {actual} != {expected}; "
        "rerun with --force"
    )
PYEOF
}

require_final_no_safe_pack() {
  local manifest_path="$1"
  python3 - "$manifest_path" "$SOURCE_COMMIT" <<'PYEOF'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
expected_commit = sys.argv[2]
manifest = json.loads(path.read_text(encoding="utf-8"))
if (
    manifest.get("schema_version") != 2
    or manifest.get("status") != "CONFIRMATORY_DISJOINT_CONTROLS"
    or manifest.get("finite_audit_source_commit") != expected_commit
    or manifest.get("finite_audit_control_result") != "PASS"
    or manifest.get("counts", {}).get("finite_audit_attempts") != 300
    or manifest.get("counts", {}).get("finite_audit_no_safe") != 50
):
    raise SystemExit(
        f"ERROR: {path} is not the completed PASS final NO_SAFE pack"
    )
PYEOF
}

require_file "$LEGACY_BASELINE_ROOT/summary/summary.json"
require_file "$LEGACY_BASELINE_ROOT/summary/workload_results.csv"
require_file "$LEGACY_BASELINE_AUDIT/summary/summary.json"
require_file "$CATALOG_ORACLE_ROOT/summary.json"
require_file "$LEGACY_COMPARISON_ROOT/summary.json"
require_file "$LEGACY_COMPARISON_ROOT/comparison.csv"
require_file "$FINITE_ROOT/summary.json"
require_file "$SECURITY_V2_ROOT/security_reattestation_v2.json"
require_file "$SECURITY_V2_ROOT/direct_synthesis_policy_v2.json"
require_file "$SECURITY_V2_ROOT/bounded_oracle_security_v2/summary.json"

python3 scripts/build_security_v2_static_artifacts.py --verify
python3 scripts/compare_direct_synthesis_to_catalog_oracle.py --verify
python3 scripts/freeze_policy_sensitivity_evidence.py \
  --output-root docs/evidence/policy_sensitivity_v1 \
  --verify
python3 scripts/analyze_structural_extension_plans.py --verify
python3 scripts/freeze_direct_locked_audit_evidence.py \
  --output-root docs/evidence/direct_locked_audit_five_split_v1 \
  --verify
python3 scripts/freeze_full_oracle_comparison_evidence.py \
  --output-root docs/evidence/full_oracle_comparison_v1 \
  --verify

echo "final_suite_preflight=PASS source_commit=$SOURCE_COMMIT"
if [[ "$PREFLIGHT_ONLY" == true ]]; then
  exit 0
fi

if [[ "$SKIP_REGRESSION" == false ]]; then
  env GOCACHE=/tmp/flipguard-final-suite-test-gocache go test ./...
  env GOCACHE=/tmp/flipguard-final-suite-vet-gocache go vet ./...
  python3 -m py_compile scripts/*.py
  python3 -m unittest discover \
    -s scripts/tests \
    -p 'test_*.py'
  for script in scripts/*.sh; do
    bash -n "$script"
  done
  echo "final_suite_regression=PASS"
fi

FINAL_BASELINE_ID="full_final_baseline_inputmodel_floor18_keys3"
FINAL_BASELINE_ROOT="$BASE_ROOT/$FINAL_BASELINE_ID"
FINAL_BASELINE_AUDIT_ID="${FINAL_BASELINE_ID}_locked_audit_keys3"
FINAL_BASELINE_AUDIT="$FINAL_BASELINE_ROOT/locked_audit/$FINAL_BASELINE_AUDIT_ID"
FINAL_BASELINE_PACK="docs/evidence/direct_locked_audit_final_source_v1"

scripts/run_direct_tabular_autotune_matrix.sh \
  --full \
  --run-label final_baseline \
  --materialize-model-input \
  --margin-floor 0.001 \
  --safety-factor 0.5 \
  --precision-floor 18 \
  --key-repeats 3 \
  "$ACTION"

scripts/run_direct_tabular_locked_audit_matrix.sh \
  --full \
  --selection-run "$FINAL_BASELINE_ID" \
  --materialize-model-input \
  --key-repeats 3 \
  "$ACTION"

if [[ -d "$FINAL_BASELINE_PACK" && "$ACTION" == "--resume" ]]; then
  require_pack_commit "$FINAL_BASELINE_PACK/manifest.json" direct
  python3 scripts/freeze_direct_locked_audit_evidence.py \
    --output-root "$FINAL_BASELINE_PACK" \
    --verify
else
  python3 scripts/freeze_direct_locked_audit_evidence.py \
    --source-root "$FINAL_BASELINE_AUDIT" \
    --output-root "$FINAL_BASELINE_PACK" \
    --source-commit "$SOURCE_COMMIT" \
    --evidence-id direct_locked_audit_final_source_v1 \
    --evidence-stage confirmatory \
    --selection-run-id "$FINAL_BASELINE_ID" \
    --audit-run-id "$FINAL_BASELINE_AUDIT_ID" \
    --split-seeds 0,1,2,3,4 \
    --key-repeats 3 \
    --expected-model-ids linear_poly3,mlp_square_linear_score \
    --require-max-budget-usage-below 1 \
    --require-source-replay \
    --execution-command scripts/run_thesis_final_confirmatory_suite.sh \
    "${FORCE_FREEZE[@]}"
fi

FINAL_COMPARISON_ROOT="results/thesis_grade_protocol/direct_vs_catalog_oracle_v1/final_source_baseline"
if [[ -d "$FINAL_COMPARISON_ROOT" && "$ACTION" == "--resume" ]]; then
  python3 scripts/compare_direct_synthesis_to_catalog_oracle.py \
    --oracle-root "$SECURITY_ORACLE_ROOT" \
    --direct-root "$FINAL_BASELINE_ROOT/summary" \
    --output-root "$FINAL_COMPARISON_ROOT" \
    --expected-candidates-per-workload 14 \
    --verify
else
  python3 scripts/compare_direct_synthesis_to_catalog_oracle.py \
    --oracle-root "$SECURITY_ORACLE_ROOT" \
    --direct-root "$FINAL_BASELINE_ROOT/summary" \
    --output-root "$FINAL_COMPARISON_ROOT" \
    --expected-candidates-per-workload 14 \
    "${FORCE_FREEZE[@]}"
fi

NO_SAFE_ROOT="results/thesis_grade_protocol/no_safe_budget_control_v1/confirm_seeds1_4"
python3 scripts/run_no_safe_budget_negative_controls.py \
  --mode confirm \
  --output-root "$NO_SAFE_ROOT" \
  "${FORCE_PYTHON[@]}"

FINITE_AUDIT_ROOT="results/thesis_grade_protocol/finite_domain_no_safe_locked_audit_v1/full"
python3 scripts/run_finite_domain_no_safe_locked_audit.py \
  --mode confirm \
  --output-root "$FINITE_AUDIT_ROOT" \
  "${FORCE_PYTHON[@]}"

NO_SAFE_PACK="docs/evidence/no_safe_controls_confirmatory_v1"
if [[ -d "$NO_SAFE_PACK" && "$ACTION" == "--resume" ]]; then
  require_pack_commit "$NO_SAFE_PACK/manifest.json" no_safe
  python3 scripts/freeze_no_safe_control_evidence.py \
    --output-root "$NO_SAFE_PACK" \
    --verify
else
  python3 scripts/freeze_no_safe_control_evidence.py \
    --budget-root "$NO_SAFE_ROOT" \
    --finite-root "$FINITE_ROOT" \
    --finite-audit-root "$FINITE_AUDIT_ROOT" \
    --output-root "$NO_SAFE_PACK" \
    --evidence-id no_safe_controls_confirmatory_v1 \
    "${FORCE_FREEZE[@]}"
fi
require_final_no_safe_pack "$NO_SAFE_PACK/manifest.json"

scripts/run_structural_extension.sh "$ACTION"

STRUCTURAL_ID="full_structural_poly3_inputmodel_floor18_keys3"
STRUCTURAL_ROOT="$BASE_ROOT/$STRUCTURAL_ID"
STRUCTURAL_AUDIT_ID="${STRUCTURAL_ID}_locked_audit_keys3"
STRUCTURAL_AUDIT="$STRUCTURAL_ROOT/locked_audit/$STRUCTURAL_AUDIT_ID"
STRUCTURAL_PACK="docs/evidence/structural_extension_v1"

if [[ -d "$STRUCTURAL_PACK" && "$ACTION" == "--resume" ]]; then
  require_pack_commit "$STRUCTURAL_PACK/manifest.json" direct
  python3 scripts/freeze_direct_locked_audit_evidence.py \
    --output-root "$STRUCTURAL_PACK" \
    --verify
else
  python3 scripts/freeze_direct_locked_audit_evidence.py \
    --source-root "$STRUCTURAL_AUDIT" \
    --output-root "$STRUCTURAL_PACK" \
    --source-commit "$SOURCE_COMMIT" \
    --evidence-id structural_extension_v1 \
    --evidence-stage confirmatory \
    --selection-run-id "$STRUCTURAL_ID" \
    --audit-run-id "$STRUCTURAL_AUDIT_ID" \
    --split-seeds 0,1,2,3,4 \
    --key-repeats 3 \
    --expected-model-ids mlp_square_poly3 \
    --require-max-budget-usage-below 1 \
    --require-source-replay \
    --execution-command scripts/run_structural_extension.sh \
    --source-protocol-manifest \
      "$STRUCTURAL_ROOT/summary/structural_protocol.json" \
    --extra-artifact \
      split_summary=results/thesis_grade_protocol/structural_extension_splits_v1/summary.json \
    --extra-artifact \
      static_plan_summary=results/thesis_grade_protocol/structural_extension_v1/static_plans/summary.json \
    --extra-artifact \
      static_plans=results/thesis_grade_protocol/structural_extension_v1/static_plans/plans.csv \
    "${FORCE_FREEZE[@]}"
fi

PAIRED_ROOT="results/thesis_grade_protocol/paired_tabular_latency_v1/full"
python3 scripts/run_paired_tabular_latency.py \
  --comparison "$FINAL_COMPARISON_ROOT/comparison.csv" \
  --direct-results "$FINAL_BASELINE_ROOT/summary/workload_results.csv" \
  --mode final \
  --output-root "$PAIRED_ROOT" \
  --warmup-runs 1 \
  --measurement-runs 6 \
  --max-rows 6 \
  "${FORCE_PYTHON[@]}"

PAIRED_PACK="docs/evidence/paired_latency_final_v1"
if [[ -d "$PAIRED_PACK" && "$ACTION" == "--resume" ]]; then
  require_pack_commit "$PAIRED_PACK/manifest.json" paired
  python3 scripts/freeze_paired_latency_evidence.py \
    --output-root "$PAIRED_PACK" \
    --verify
else
  python3 scripts/freeze_paired_latency_evidence.py \
    --input-root "$PAIRED_ROOT" \
    --output-root "$PAIRED_PACK" \
    --evidence-id paired_latency_final_v1 \
    "${FORCE_FREEZE[@]}"
fi

PAPER_ARTIFACT_ROOT="results/thesis_grade_protocol/paper_artifacts_v2/current"
python3 scripts/build_flipguard_v2_paper_artifacts.py \
  --profile final \
  --output-root "$PAPER_ARTIFACT_ROOT" \
  --force
python3 scripts/build_flipguard_v2_paper_artifacts.py \
  --profile final \
  --output-root "$PAPER_ARTIFACT_ROOT" \
  --verify

echo "final_confirmatory_suite=PASS source_commit=$SOURCE_COMMIT"
