#!/usr/bin/env python3
"""Build the deterministic margin-utilization interpretation overlay."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path("docs/evidence/margin_utilization_interpretation_v1")
PRIMARY_PACKS = (
    Path("docs/evidence/direct_locked_audit_seed0_development_v1"),
    Path("docs/evidence/direct_locked_audit_final_source_v1"),
)
STRUCTURAL_ANALYSIS = Path(
    "docs/evidence/structural_audit_failure_analysis_v1/"
    "analysis/margin_error_analysis.json"
)
POLICY_SUMMARY = Path(
    "docs/evidence/policy_sensitivity_v1/results/summary.json"
)
POLICY_PLANS = Path(
    "docs/evidence/policy_sensitivity_v1/results/synthesis_plans.csv"
)
VERIFIER = Path("scripts/verify_margin_utilization_interpretation_v1.py")
RHO = 0.5


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def source_record(relative: Path) -> dict[str, Any]:
    path = ROOT / relative
    return {
        "path": str(relative),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def selected_trial(result: dict[str, Any]) -> dict[str, Any]:
    selected = result.get("selected") or {}
    matches = [
        trial
        for trial in result.get("trials", [])
        if trial.get("candidate", {}).get("id") == selected.get("id")
        and trial.get("status") == "SAFE"
    ]
    if len(matches) != 1:
        raise ValueError("selection does not bind exactly one SAFE trial")
    return matches[0]


def utilization_row(
    csv_row: dict[str, str],
    stage: str,
    status: str,
    flips: int,
    violations: int,
    max_error: float,
    max_budget_usage: float,
    margin: float,
    budget: float,
    source_digest: str,
) -> dict[str, Any]:
    utilization = RHO * max_budget_usage
    preserved = flips == 0
    reserve_pass = violations == 0 and utilization < RHO
    return {
        "population": (
            "development_seed0"
            if int(csv_row["split_seed"]) == 0
            else "confirmatory_seeds1_4"
        ),
        "split_seed": int(csv_row["split_seed"]),
        "dataset_id": csv_row["dataset_id"],
        "model_id": csv_row["model_id"],
        "stage": stage,
        "candidate_id": csv_row["candidate_id"],
        "status": status,
        "margin": margin,
        "absolute_error": max_error,
        "margin_utilization_ratio": utilization,
        "margin_utilization_cap": RHO,
        "reserved_margin_fraction": 1 - RHO,
        "operational_acceptance_budget": budget,
        "observed_decision_preserved": preserved,
        "reserve_policy_pass": reserve_pass,
        "policy_reject_without_flip": (
            preserved and (violations > 0 or not reserve_pass)
        ),
        "minimum_cap_required": utilization,
        "decision_flips": flips,
        "error_violations": violations,
        "observation_binding": "aggregate_extrema_not_sample_bound",
        "source_sha256": source_digest,
    }


def load_primary_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    output: list[dict[str, Any]] = []
    inputs: list[dict[str, Any]] = []
    for pack in PRIMARY_PACKS:
        table = pack / "outputs/locked_audit_results.csv"
        inputs.append(source_record(table))
        with (ROOT / table).open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            selection_path = Path(row["selection_result_path"])
            selection_file = ROOT / selection_path
            if sha256(selection_file) != row["selection_result_sha256"]:
                raise ValueError(f"{selection_path}: selection digest mismatch")
            selection = read_json(selection_file)
            trial = selected_trial(selection)
            decision = selection["plan"]["contract"]["decision"]
            selection_source = row["selection_result_sha256"]
            output.append(
                utilization_row(
                    row,
                    "configuration_validation",
                    trial["status"],
                    int(trial["decision_flips"]),
                    int(trial["error_violations"]),
                    float(trial["max_observed_error"]),
                    float(trial["max_error_budget_usage"]),
                    float(decision["protected_margin"]),
                    float(decision["output_error_budget"]),
                    selection_source,
                )
            )

            audit_path = Path(row["result_path"])
            audit_file = ROOT / audit_path
            audit = read_json(audit_file)
            audit_trial = audit["audit_trial"]
            audit_decision = audit["audit_contract"]["decision"]
            output.append(
                utilization_row(
                    row,
                    "locked_audit",
                    audit_trial["status"],
                    int(audit_trial["decision_flips"]),
                    int(audit_trial["error_violations"]),
                    float(audit_trial["max_observed_error"]),
                    float(audit_trial["max_error_budget_usage"]),
                    float(audit_decision["protected_margin"]),
                    float(audit_decision["output_error_budget"]),
                    sha256(audit_file),
                )
            )
    output.sort(
        key=lambda row: (
            row["split_seed"],
            row["dataset_id"],
            row["model_id"],
            row["stage"],
        )
    )
    if len(output) != 100:
        raise ValueError(f"expected 100 primary rows, found {len(output)}")
    return output, inputs


def alpha_rows() -> list[dict[str, Any]]:
    summary = read_json(ROOT / POLICY_SUMMARY)
    diagnostics = summary["alpha_certificate_diagnostics"]
    if (
        diagnostics["candidate_state_changes_across_alpha"] != 0
        or diagnostics["oracle_candidate_changes_across_alpha"] != 0
    ):
        raise ValueError("alpha status/oracle invariance no longer holds")

    by_workload: dict[tuple[str, str, str], set[tuple[int, int, int, int]]] = {}
    with (ROOT / POLICY_PLANS).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if (
                row["partition"] != "configuration_validation"
                or float(row["margin_floor"]) != 0.001
            ):
                continue
            key = (row["split_seed"], row["dataset_id"], row["model_id"])
            literal = (
                int(row["log_n"]),
                int(row["q_prime_count"]),
                int(row["p_prime_count"]),
                int(row["log_default_scale"]),
            )
            by_workload.setdefault(key, set()).add(literal)
    if len(by_workload) != 50 or any(len(values) != 1 for values in by_workload.values()):
        raise ValueError("direct initial path-and-parameter literal changed")

    return [
        {
            "alpha": alpha,
            "relative_to_primary_alpha": RHO,
            "natural_candidate_state_changes": 0,
            "bounded_oracle_selection_changes": 0,
            "direct_initial_literal_changes": 0,
            "interpretation": "TESTED_PRIMARY_RANGE_POLICY_INVARIANCE",
            "reason": "minimum_synthesis_floor_dominance",
            "optimality_evidence": False,
        }
        for alpha in diagnostics["alpha_grid"]
    ]


def structural_interpretation() -> dict[str, Any]:
    analysis = read_json(ROOT / STRUCTURAL_ANALYSIS)
    preserved = analysis["preserved_result"]
    validation_ratio = RHO * float(preserved["selection_max_usage"])
    audit_ratio = RHO * float(preserved["audit_max_usage"])
    return {
        "schema_version": 1,
        "workload": analysis["workload"],
        "failure_class": analysis["failure_class"],
        "validation": {
            "margin": None,
            "margin_field_status": "MAX_USAGE_SAMPLE_MARGIN_NOT_RECORDED",
            "absolute_error": preserved["selection_max_error"],
            "absolute_error_field_scope": "population_maximum",
            "margin_utilization_ratio": validation_ratio,
            "margin_utilization_cap": RHO,
            "reserved_margin_fraction": 1 - RHO,
            "operational_acceptance_budget": "rho_times_sample_margin",
            "observed_decision_preserved": preserved["selection_flips"] == 0,
            "reserve_policy_pass": True,
            "policy_reject_without_flip": False,
            "minimum_cap_required": validation_ratio,
        },
        "locked_audit": {
            "margin": None,
            "margin_field_status": "MAX_USAGE_SAMPLE_MARGIN_NOT_RECORDED",
            "absolute_error": preserved["audit_max_error"],
            "absolute_error_field_scope": "population_maximum",
            "margin_utilization_ratio": audit_ratio,
            "margin_utilization_cap": RHO,
            "reserved_margin_fraction": 1 - RHO,
            "operational_acceptance_budget": "rho_times_sample_margin",
            "observed_decision_preserved": preserved["audit_flips"] == 0,
            "reserve_policy_pass": False,
            "policy_reject_without_flip": True,
            "minimum_cap_required": audit_ratio,
        },
        "classification": [
            "OBSERVED_DECISION_PRESERVED",
            "RESERVE_POLICY_REJECTED",
            "POLICY_REJECTED_WITHOUT_FLIP",
        ],
        "not_classified_as": [
            "CRYPTOGRAPHIC_CORRECTNESS_FAILURE",
            "OBSERVED_DECISION_FAILURE",
        ],
        "sample_binding": analysis["recording_limit"],
        "policy_change_authorized": False,
        "encrypted_rerun_performed": False,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"{path}: no rows")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build(output: Path, source_commit: str) -> None:
    if output.exists():
        raise ValueError(f"{output} already exists")
    output.mkdir(parents=True)
    primary_rows, primary_inputs = load_primary_rows()
    sensitivity = alpha_rows()

    policy = {
        "schema_version": 1,
        "legacy_api_field": "SafetyFactor",
        "legacy_api_preserved": True,
        "paper_facing_term": "margin_utilization_cap",
        "plaintext_score": "f_plain(x)",
        "ckks_score": "f_c(x)",
        "threshold": "tau",
        "decision_margin": "m(x)=abs(f_plain(x)-tau)",
        "absolute_error": "e_c(x)=abs(f_c(x)-f_plain(x))",
        "decision_preservation_sufficient_condition": "e_c(x)<m(x)",
        "operational_reserve_policy": "e_c(x)<rho*m(x)",
        "primary_rho": RHO,
        "reserved_margin_fraction": 1 - RHO,
        "rho_origin": "predeclared_operational_policy_not_theorem_or_optimum",
    }
    write_json(output / "policy_interpretation.json", policy)
    write_csv(output / "workload_utilization_summary.csv", primary_rows)
    write_json(
        output / "structural_rejection_interpretation.json",
        structural_interpretation(),
    )
    write_csv(output / "alpha_sensitivity_summary.csv", sensitivity)
    shutil.copy2(ROOT / VERIFIER, output / VERIFIER.name)

    input_records = primary_inputs + [
        source_record(STRUCTURAL_ANALYSIS),
        source_record(POLICY_SUMMARY),
        source_record(POLICY_PLANS),
    ]
    manifest = {
        "schema_version": 1,
        "evidence_id": "margin_utilization_interpretation_v1",
        "artifact_class": "DERIVED_INTERPRETATION_OVERLAY",
        "source_commit": source_commit,
        "frozen_evidence_modified": False,
        "encrypted_execution_performed": False,
        "direct_policy_modified": False,
        "security_policy_modified": False,
        "primary_rho": RHO,
        "primary_rows": len(primary_rows),
        "development_rows": sum(
            row["population"] == "development_seed0" for row in primary_rows
        ),
        "confirmatory_rows": sum(
            row["population"] == "confirmatory_seeds1_4"
            for row in primary_rows
        ),
        "structural_claim_state": "PARTIALLY_SUPPORTED",
        "input_records": input_records,
        "recording_limit": (
            "max error and max utilization are population extrema and are not "
            "asserted to belong to the same sample"
        ),
        "files": {},
    }
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name not in {"manifest.json", "SHA256SUMS"}:
            manifest["files"][path.name] = {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
    write_json(output / "manifest.json", manifest)
    checksum_paths = sorted(
        path for path in output.iterdir() if path.is_file() and path.name != "SHA256SUMS"
    )
    (output / "SHA256SUMS").write_text(
        "".join(
            f"{sha256(path).removeprefix('sha256:')}  {path.name}\n"
            for path in checksum_paths
        ),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-commit", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = (ROOT / args.output).resolve()
    build(output, args.source_commit or git_head())
    subprocess.run(
        ["python3", str(output / VERIFIER.name), "--evidence-root", str(output)],
        cwd=ROOT,
        check=True,
    )
    print(f"margin_utilization_interpretation=BUILT output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
