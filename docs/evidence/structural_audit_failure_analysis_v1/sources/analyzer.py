#!/usr/bin/env python3
"""Explain the preserved structural locked-audit rejection without rerunning CKKS."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_SELECTION = Path(
    "results/thesis_grade_protocol/direct_tabular_autotune_v1/"
    "full_structural_poly3_inputmodel_floor18_keys3/results/"
    "directv1_full_structural_poly3_inputmodel_floor18_keys3_"
    "seed4_banknote_mlp_square_poly3.json"
)
DEFAULT_AUDIT = Path(
    "results/thesis_grade_protocol/direct_tabular_autotune_v1/"
    "full_structural_poly3_inputmodel_floor18_keys3/locked_audit/"
    "full_structural_poly3_inputmodel_floor18_keys3_locked_audit_keys3/"
    "results/directv1_full_structural_poly3_inputmodel_floor18_keys3_"
    "seed4_banknote_mlp_square_poly3_locked_audit_keys3.json"
)
DEFAULT_OUTPUT = Path(
    "results/thesis_grade_protocol/structural_audit_failure_analysis_v1"
)
UNAVAILABLE = "NOT_RECORDED_IN_EXECUTION_ARTIFACT"
ANALYSIS_ID = "structural_audit_failure_analysis_v1"
FAILURE_CLASS = "VALIDATION_NEAR_BUDGET_LIMIT_AUDIT_OVERRUN"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-result", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--audit-result", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_scores(path: Path, threshold: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            score = float(row["polynomial_score"])
            rows.append(
                {
                    "row_id": row["row_id"],
                    "score": score,
                    "margin": abs(score - threshold),
                    "decision": score >= threshold,
                }
            )
    if not rows:
        raise ValueError(f"no score rows in {path}")
    return rows


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def margin_summary(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    margins = [float(row["margin"]) for row in rows]
    return {
        "samples": len(margins),
        "minimum": min(margins),
        "p05": quantile(margins, 0.05),
        "p25": quantile(margins, 0.25),
        "median": quantile(margins, 0.50),
        "p75": quantile(margins, 0.75),
        "p95": quantile(margins, 0.95),
        "maximum": max(margins),
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build(selection_path: Path, audit_path: Path, output: Path) -> None:
    selection = read_json(selection_path)
    audit = read_json(audit_path)
    trial = audit["audit_trial"]
    validation_trial = selection["trials"][-1]
    contract = audit["audit_contract"]
    candidate = audit["selected_candidate"]

    if selection["outcome"] != "SELECTED":
        raise ValueError("selection result is not SELECTED")
    if audit["outcome"] != "LOCKED_AUDIT_FAIL":
        raise ValueError("audit result is not LOCKED_AUDIT_FAIL")
    if trial["status"] != "REJECTED" or trial["failure_signal"] != "NUMERICAL_REJECT":
        raise ValueError("audit failure is not the expected numerical rejection")
    if audit["retuning_performed"]:
        raise ValueError("locked audit reports retuning")
    if trial["decision_flips"] != 0 or trial["error_violations"] != 1:
        raise ValueError("unexpected audit flip/violation counts")
    if trial["key_repeats_completed"] != 3 or trial["success_runs"] != 3:
        raise ValueError("unexpected audit key-repeat accounting")
    if selection["selected"]["id"] != candidate["id"]:
        raise ValueError("selection/audit candidate identity mismatch")

    threshold = float(contract["decision"]["threshold"])
    alpha = float(contract["decision"]["safety_factor"])
    validation_path = Path(selection["plan"]["contract"]["validation_data"]["path"])
    audit_data_path = Path(contract["validation_data"]["path"])
    validation_source = Path(selection["plan"]["contract"]["source_data"]["path"])
    audit_source = Path(contract["source_data"]["path"])
    model_path = Path(contract["model_artifact"]["path"])
    split_manifest_path = Path(audit["split_manifest"]["path"])

    validation_rows = read_scores(validation_path, threshold)
    audit_rows = read_scores(audit_data_path, threshold)
    validation_ids = {row["row_id"] for row in validation_rows}
    audit_ids = {row["row_id"] for row in audit_rows}
    if validation_ids & audit_ids:
        raise ValueError("validation and audit row IDs overlap")

    max_error = float(trial["max_observed_error"])
    max_usage = float(trial["max_error_budget_usage"])
    if max_usage < 1.0 or max_usage >= 2.0:
        raise ValueError("preserved rejection does not have the expected no-flip usage range")

    observation_count = int(trial["v_cert"]) * int(trial["success_runs"])
    possible_rows = [
        row for row in audit_rows if alpha * float(row["margin"]) <= max_error
    ]
    max_failure_margin = max_error / (alpha * max_usage)
    failure_row_candidates = [
        row for row in audit_rows if float(row["margin"]) <= max_failure_margin
    ]

    params = candidate["parameters"]
    security = candidate["security"]
    digests = {
        "selection_result": sha256(selection_path),
        "audit_result": sha256(audit_path),
        "validation_prepared": sha256(validation_path),
        "audit_prepared": sha256(audit_data_path),
        "validation_source": sha256(validation_source),
        "audit_source": sha256(audit_source),
        "model": sha256(model_path),
        "split_manifest": sha256(split_manifest_path),
        "selection_contract": audit["selection_contract_digest"],
        "direct_policy": selection["plan"]["direct_policy_digest"],
        "security_policy": selection["plan"]["security_policy_digest"],
    }

    output.mkdir(parents=True, exist_ok=True)
    failure_fields = [
        "observation_id",
        "row_id",
        "row_identity_status",
        "plaintext_score",
        "threshold",
        "decision_margin",
        "ckks_score",
        "absolute_error",
        "alpha_margin_budget",
        "normalized_budget_usage",
        "plaintext_decision",
        "ckks_decision",
        "decision_flip",
        "key_repeat",
        "validation_contains_same_row",
        "validation_max_usage",
        "audit_max_usage",
        "candidate_literal",
        "log_n",
        "log_q",
        "log_p",
        "log_qp",
        "scale_bits",
        "source_digest",
        "model_digest",
        "split_digest",
        "direct_policy_digest",
        "security_policy_digest",
    ]
    failure_row = {
        "observation_id": "aggregate_unique_violation_1",
        "row_id": UNAVAILABLE,
        "row_identity_status": (
            "ONE_SAMPLE_IS_PROVEN_BUT_IDENTITY_WAS_NOT_PERSISTED"
        ),
        "plaintext_score": UNAVAILABLE,
        "threshold": threshold,
        "decision_margin": UNAVAILABLE,
        "ckks_score": UNAVAILABLE,
        "absolute_error": UNAVAILABLE,
        "alpha_margin_budget": UNAVAILABLE,
        "normalized_budget_usage": max_usage,
        "plaintext_decision": UNAVAILABLE,
        "ckks_decision": UNAVAILABLE,
        "decision_flip": False,
        "key_repeat": UNAVAILABLE,
        "validation_contains_same_row": False,
        "validation_max_usage": validation_trial["max_error_budget_usage"],
        "audit_max_usage": max_usage,
        "candidate_literal": candidate["id"],
        "log_n": params["log_n"],
        "log_q": "|".join(str(value) for value in params["log_q"]),
        "log_p": "|".join(str(value) for value in params["log_p"]),
        "log_qp": security["log_qp"],
        "scale_bits": params["log_default_scale"],
        "source_digest": digests["audit_source"],
        "model_digest": digests["model"],
        "split_digest": digests["split_manifest"],
        "direct_policy_digest": digests["direct_policy"],
        "security_policy_digest": digests["security_policy"],
    }
    write_csv(output / "failing_samples.csv", failure_fields, [failure_row])

    repeat_fields = [
        "key_repeat",
        "error",
        "budget_usage",
        "violation_status",
        "evidence_limit",
    ]
    repeat_rows = [
        {
            "key_repeat": repeat,
            "error": UNAVAILABLE,
            "budget_usage": UNAVAILABLE,
            "violation_status": "ONE_OF_THREE_NOT_IDENTIFIABLE",
            "evidence_limit": (
                "per-key scores were held in memory and not persisted by the "
                "execution artifact"
            ),
        }
        for repeat in range(1, 4)
    ]
    write_csv(
        output / "key_repeat_breakdown.csv",
        repeat_fields,
        repeat_rows,
    )

    validation_margins = margin_summary(validation_rows)
    audit_margins = margin_summary(audit_rows)
    analysis = {
        "schema_version": 1,
        "analysis_id": ANALYSIS_ID,
        "analysis_type": "EXPLANATORY_POST_HOC_STATIC_NO_POLICY_CHANGE",
        "failure_class": FAILURE_CLASS,
        "workload": {
            "seed": 4,
            "dataset": "banknote",
            "model": "mlp_square_poly3",
            "candidate_literal": candidate["id"],
        },
        "preserved_result": {
            "selection_status": validation_trial["status"],
            "selection_flips": validation_trial["decision_flips"],
            "selection_violations": validation_trial["error_violations"],
            "selection_max_error": validation_trial["max_observed_error"],
            "selection_max_usage": validation_trial["max_error_budget_usage"],
            "audit_status": trial["status"],
            "audit_flips": trial["decision_flips"],
            "audit_violations": trial["error_violations"],
            "audit_max_error": max_error,
            "audit_max_usage": max_usage,
            "retuning": audit["retuning_performed"],
            "policy_modification_after_audit": 0,
        },
        "observation_accounting": {
            "audit_samples": trial["v_cert"],
            "key_repeats": trial["success_runs"],
            "sample_key_observations": observation_count,
            "violating_observations": trial["error_violations"],
            "violation_scope": "EXACTLY_ONE_SAMPLE_KEY_REPEAT_OBSERVATION",
            "one_key_repeat_only": True,
            "all_three_key_aggregate": False,
            "one_sample_only": True,
            "sample_identity": UNAVAILABLE,
            "key_repeat_identity": UNAVAILABLE,
        },
        "margin_analysis": {
            "validation": validation_margins,
            "audit": audit_margins,
            "row_id_overlap": 0,
            "same_row_in_validation": False,
            "possible_rows_using_aggregate_max_error_upper_bound": len(possible_rows),
            "rows_compatible_with_exact_max_usage_and_max_error_bound": len(
                failure_row_candidates
            ),
            "failure_margin_upper_bound": max_failure_margin,
            "failing_sample_outside_validation_margin_distribution": (
                "NOT_DETERMINABLE_WITHOUT_PERSISTED_SAMPLE_ID"
            ),
        },
        "error_analysis": {
            "selection_to_audit_max_error_ratio": (
                max_error / float(validation_trial["max_observed_error"])
            ),
            "selection_to_audit_max_usage_ratio": (
                max_usage / float(validation_trial["max_error_budget_usage"])
            ),
            "audit_min_margin_vs_validation_min_margin_ratio": (
                float(audit_margins["minimum"])
                / float(validation_margins["minimum"])
            ),
            "cause": (
                "The aggregate audit maximum absolute error increased while the "
                "audit minimum margin did not decrease. This supports an "
                "aggregate numerical-error-overrun explanation, but the exact "
                "offending observation cannot be attributed because per-sample "
                "CKKS scores were not persisted."
            ),
            "margin_decrease_only": False,
            "absolute_error_increase_at_population_maximum": True,
            "sample_level_causal_attribution": "NOT_DETERMINABLE",
        },
        "no_flip_explanation": {
            "alpha": alpha,
            "budget_violation_threshold_usage": 1.0,
            "decision_flip_requires_usage_at_least": 1.0 / alpha,
            "observed_max_usage": max_usage,
            "explanation": (
                "The protected error budget is alpha times the decision margin. "
                "With alpha=0.5, a budget violation starts at usage 1, while "
                "crossing the threshold requires usage at least 2. The observed "
                "maximum usage was below 2, so the numerical certificate could "
                "reject without any decision flip."
            ),
        },
        "recording_limit": {
            "per_sample_ckks_scores_persisted": False,
            "per_key_errors_persisted": False,
            "aggregate_counts_persisted": True,
            "future_instrumentation_note": (
                "Persist sample/key observations in future protocols before "
                "execution; do not reconstruct or rerun this frozen audit."
            ),
        },
        "digests": digests,
        "claim_effect": {
            "structural_generalization": "PARTIALLY_SUPPORTED",
            "locked_audit_result": "24/25 PASS; 1/25 numerical REJECT",
            "policy_change_authorized": False,
            "candidate_reselection_authorized": False,
        },
    }
    (output / "margin_error_analysis.json").write_text(
        json.dumps(analysis, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = f"""# Structural locked-audit failure analysis

- Analysis: `{ANALYSIS_ID}`
- Classification: `{FAILURE_CLASS}`
- Scope: explanatory post-hoc static analysis; no encrypted rerun and no policy change
- Workload: seed 4 / banknote / mlp_square_poly3
- Candidate: `{candidate["id"]}`
- Validation: SAFE, 0 flips, 0 violations, max usage {validation_trial["max_error_budget_usage"]:.6f}
- Locked audit: REJECTED, 0 flips, 1 violation, max usage {max_usage:.6f}
- Observation accounting: exactly 1 of {observation_count} sample-key observations violated the alpha-margin budget
- Key scope: exactly one key repeat for one sample; the row and repeat identities were not persisted
- Margin evidence: validation min {float(validation_margins["minimum"]):.6f}, audit min {float(audit_margins["minimum"]):.6f}
- Error evidence: validation max {float(validation_trial["max_observed_error"]):.6f}, audit max {max_error:.6f}
- No-flip explanation: alpha=0.5 rejects at normalized usage 1, while a threshold crossing requires usage at least 2; observed max usage was {max_usage:.6f}
- Claim consequence: structural generalization is `PARTIALLY_SUPPORTED` (24/25 audit PASS, 1/25 numerical REJECT)

## Evidence limit

The execution artifact persisted aggregate certificate values but not the in-memory
per-sample CKKS scores. Exact row ID, CKKS score, absolute error, and key-repeat
identity are therefore reported as `{UNAVAILABLE}` rather than reconstructed.
"""
    (output / "summary.md").write_text(summary, encoding="utf-8")
    write_checksums(output)


def write_checksums(output: Path) -> None:
    paths = sorted(path for path in output.iterdir() if path.name != "SHA256SUMS")
    lines = [
        f"{sha256(path).removeprefix('sha256:')}  {path.name}"
        for path in paths
        if path.is_file()
    ]
    (output / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify(selection_path: Path, audit_path: Path, output: Path) -> None:
    required = {
        "failing_samples.csv",
        "key_repeat_breakdown.csv",
        "margin_error_analysis.json",
        "summary.md",
        "SHA256SUMS",
    }
    actual = {path.name for path in output.iterdir() if path.is_file()}
    if actual != required:
        raise ValueError(f"analysis files differ: actual={sorted(actual)}")
    with tempfile.TemporaryDirectory() as directory:
        expected = Path(directory) / "expected"
        build(selection_path, audit_path, expected)
        for name in sorted(required):
            if (output / name).read_bytes() != (expected / name).read_bytes():
                raise ValueError(f"analysis artifact differs: {name}")
    print(
        "structural_audit_failure_analysis=VERIFIED "
        "violating_observations=1 exact_row=NOT_RECORDED"
    )


def main() -> int:
    args = parse_args()
    if args.verify:
        if args.force:
            raise ValueError("--verify and --force are mutually exclusive")
        verify(args.selection_result, args.audit_result, args.output_root)
        return 0
    if args.output_root.exists():
        if not args.force:
            raise FileExistsError(
                f"{args.output_root} exists; use --force to replace generated analysis"
            )
        shutil.rmtree(args.output_root)
    build(args.selection_result, args.audit_result, args.output_root)
    verify(args.selection_result, args.audit_result, args.output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
