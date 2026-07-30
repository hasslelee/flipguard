#!/usr/bin/env python3
"""Validate and classify the frozen mlp_square_poly3 structural extension."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


SELECTION_ROOT = Path(
    "results/thesis_grade_protocol/direct_tabular_autotune_v1/"
    "full_structural_poly3_inputmodel_floor18_keys3"
)
AUDIT_ROOT = SELECTION_ROOT / (
    "locked_audit/"
    "full_structural_poly3_inputmodel_floor18_keys3_locked_audit_keys3"
)
SPLIT_SUMMARY = Path(
    "results/thesis_grade_protocol/structural_extension_splits_v1/summary.json"
)
RUN_MANIFEST = Path(
    "results/thesis_grade_protocol/final_confirmatory_suite_v1/"
    "run_manifest/run_manifest.json"
)
RESUME_PROVENANCE = Path(
    "results/thesis_grade_protocol/final_confirmatory_suite_v1/"
    "resume_provenance/resume_provenance.json"
)
DEFAULT_OUTPUT = SELECTION_ROOT / "summary/structural_protocol.json"
FAILURE_CLASS = "VALIDATION_NEAR_BUDGET_LIMIT_AUDIT_OVERRUN"
EXPECTED_SPLIT_DIGEST = (
    "sha256:8e1ac4e74e086a86944510023c0312f5ee77b0dedeaaa4dc3d1b5332607fa609"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def expected_document(
    evidence_builder_parent_commit: str | None = None,
) -> dict[str, Any]:
    selection_summary_path = SELECTION_ROOT / "summary/summary.json"
    selection_rows_path = SELECTION_ROOT / "summary/workload_results.csv"
    audit_summary_path = AUDIT_ROOT / "summary/summary.json"
    audit_rows_path = AUDIT_ROOT / "summary/locked_audit_results.csv"
    selection_summary = read_json(selection_summary_path)
    audit_summary = read_json(audit_summary_path)
    selection_rows = read_csv(selection_rows_path)
    audit_rows = read_csv(audit_rows_path)
    run_manifest = read_json(RUN_MANIFEST)
    resume_provenance = read_json(RESUME_PROVENANCE)

    if sha256(SPLIT_SUMMARY) != EXPECTED_SPLIT_DIGEST:
        raise ValueError("structural split summary digest changed")
    if (
        selection_summary.get("successful_runs") != 25
        or selection_summary.get("selected_runs") != 25
        or selection_summary.get("failed_runs") != 0
        or selection_summary.get("no_safe_runs") != 0
        or selection_summary.get("total_encrypted_trials") != 43
        or selection_summary.get("repaired_runs") != 18
        or selection_summary.get("total_encrypted_key_runs") != 129
        or selection_summary.get("source_replay_verified_runs") != 25
        or len(selection_rows) != 25
    ):
        raise ValueError("structural selection checkpoint changed")
    if (
        audit_summary.get("locked_audit_passes") != 24
        or audit_summary.get("locked_audit_fails") != 1
        or audit_summary.get("failed_executions") != 0
        or audit_summary.get("retuned_runs") != 0
        or audit_summary.get("total_fresh_key_runs") != 75
        or audit_summary.get("source_replay_verified_runs") != 25
        or audit_summary.get("audit_source_replay_verified_runs") != 25
        or len(audit_rows) != 25
    ):
        raise ValueError("structural locked-audit checkpoint changed")
    if (
        sum(int(row["v_cert"]) for row in selection_rows) != 3992
        or sum(int(row["v_amb"]) for row in selection_rows) != 123
        or audit_summary.get("total_v_cert") != 4033
        or audit_summary.get("total_v_amb") != 117
    ):
        raise ValueError("structural coverage checkpoint changed")
    if any(
        row["model_id"] != "mlp_square_poly3"
        or row["selected_trial_status"] != "SAFE"
        or int(row["decision_flips"]) != 0
        or int(row["error_violations"]) != 0
        or row["source_replay_verified"] != "True"
        or float(row["max_error_budget_usage"]) >= 1
        for row in selection_rows
    ):
        raise ValueError("structural selection certificate changed")

    failure_rows = [row for row in audit_rows if row["outcome"] != "LOCKED_AUDIT_PASS"]
    if len(failure_rows) != 1:
        raise ValueError("expected exactly one preserved structural audit rejection")
    failure = failure_rows[0]
    if (
        failure["split_seed"] != "4"
        or failure["dataset_id"] != "banknote"
        or failure["model_id"] != "mlp_square_poly3"
        or failure["outcome"] != "LOCKED_AUDIT_FAIL"
        or failure["trial_status"] != "REJECTED"
        or failure["retuning_performed"] != "False"
        or int(failure["decision_flips"]) != 0
        or int(failure["error_violations"]) != 1
        or failure["candidate_id"]
        != "synth_analysis_minimum_rescale_N14_Q10_S22_01ae407b2f60"
        or failure["source_replay_verified"] != "True"
        or failure["audit_source_replay_verified"] != "True"
    ):
        raise ValueError("structural rejection identity changed")

    pass_rows = [row for row in audit_rows if row["outcome"] == "LOCKED_AUDIT_PASS"]
    if len(pass_rows) != 24 or any(
        row["trial_status"] != "SAFE"
        or row["retuning_performed"] != "False"
        or int(row["decision_flips"]) != 0
        or int(row["error_violations"]) != 0
        or row["source_replay_verified"] != "True"
        or row["audit_source_replay_verified"] != "True"
        or float(row["max_error_budget_usage"]) >= 1
        for row in pass_rows
    ):
        raise ValueError("structural audit PASS rows changed")

    for row in selection_rows:
        result = read_json(Path(row["result_path"]))
        contract = result["plan"]["contract"]
        if (
            contract["model_type"] != "mlp_square_poly3"
            or contract["graph"]["multiplicative_depth"] != 3
            or contract["deployment"]["required_q_primes"] != 10
            or contract["input_materialization"]["source_replay_verified"] is not True
        ):
            raise ValueError("structural graph contract changed")
    for row in audit_rows:
        result = read_json(Path(row["result_path"]))
        if (
            result["retuning_performed"] is not False
            or result["selected_candidate"]["id"] != row["candidate_id"]
            or result["audit_contract"]["input_materialization"][
                "source_replay_verified"
            ]
            is not True
        ):
            raise ValueError("structural audit replay or candidate identity changed")

    failure_result = read_json(Path(failure["result_path"]))
    if failure_result["audit_trial"]["failure_signal"] != "NUMERICAL_REJECT":
        raise ValueError("structural rejection failure signal changed")
    if resume_provenance.get("execution_critical_source_unchanged") is not True:
        raise ValueError("execution-critical source provenance is not closed")

    return {
        "schema_version": 2,
        "experiment_id": "structural_extension_v1",
        "stage_status": "PARTIAL_SCIENTIFIC_RESULT",
        "claim_state": "PARTIALLY_SUPPORTED",
        "claim_boundary": (
            "Observed support for mlp_square_poly3 on the frozen scalar-tabular "
            "five-partition scope; not arbitrary graph, image, or CNN support."
        ),
        "counts": {
            "structural_instances": 25,
            "selection_selected": 25,
            "selection_failed": 0,
            "selection_no_safe": 0,
            "selection_trials": 43,
            "selection_repairs": 18,
            "selection_key_runs": 129,
            "locked_audit_pass": 24,
            "locked_audit_rejected": 1,
            "locked_audit_failed": 0,
            "locked_audit_key_runs": 75,
            "retuning": 0,
            "flip_count": 0,
            "violation_count": 1,
            "policy_modification_after_audit": 0,
            "validation_v_cert": 3992,
            "validation_v_amb": 123,
            "audit_v_cert": 4033,
            "audit_v_amb": 117,
        },
        "negative_result": {
            "failure_class": FAILURE_CLASS,
            "seed": 4,
            "dataset": "banknote",
            "model": "mlp_square_poly3",
            "candidate_literal": failure["candidate_id"],
            "validation_status": "SAFE",
            "validation_flips": 0,
            "validation_violations": 0,
            "validation_max_usage": 0.9413060189678464,
            "audit_status": "REJECTED",
            "audit_flips": 0,
            "audit_violations": 1,
            "audit_max_usage": float(failure["max_error_budget_usage"]),
            "retuning": False,
            "preservation_rule": (
                "No repair, reselection, policy change, or audit-to-validation "
                "movement is authorized."
            ),
        },
        "provenance": {
            "direct_selection_execution_commit": run_manifest[
                "execution_source_commit"
            ],
            "locked_audit_execution_commit": run_manifest[
                "execution_source_commit"
            ],
            "evidence_builder_parent_commit": (
                evidence_builder_parent_commit or git_head()
            ),
            "execution_critical_source_digest": resume_provenance[
                "execution_critical_source_digest"
            ],
            "execution_critical_source_unchanged": True,
            "selection_binary_sha256": run_manifest["binaries"][
                "flipguard_autotune"
            ]["sha256"],
            "audit_binary_sha256": run_manifest["binaries"]["flipguard_audit"][
                "sha256"
            ],
            "direct_policy": run_manifest["direct_policy"],
            "security_policy": run_manifest["security_policy"],
        },
        "inputs": {
            "split_summary": {
                "path": str(SPLIT_SUMMARY),
                "sha256": sha256(SPLIT_SUMMARY),
            },
            "run_manifest": {
                "path": str(RUN_MANIFEST),
                "sha256": sha256(RUN_MANIFEST),
            },
            "resume_provenance": {
                "path": str(RESUME_PROVENANCE),
                "sha256": sha256(RESUME_PROVENANCE),
            },
        },
        "outputs": {
            "selection_summary": {
                "path": str(selection_summary_path),
                "sha256": sha256(selection_summary_path),
            },
            "selection_rows": {
                "path": str(selection_rows_path),
                "sha256": sha256(selection_rows_path),
            },
            "audit_summary": {
                "path": str(audit_summary_path),
                "sha256": sha256(audit_summary_path),
            },
            "audit_rows": {
                "path": str(audit_rows_path),
                "sha256": sha256(audit_rows_path),
            },
            "failure_result": {
                "path": failure["result_path"],
                "sha256": sha256(Path(failure["result_path"])),
            },
        },
    }


def main() -> int:
    args = parse_args()
    if args.verify:
        if args.force:
            raise ValueError("--verify and --force are mutually exclusive")
        actual = read_json(args.output)
        builder_commit = actual["provenance"]["evidence_builder_parent_commit"]
        expected = (
            json.dumps(
                expected_document(builder_commit),
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        if args.output.read_text(encoding="utf-8") != expected:
            raise ValueError("structural protocol differs from preserved results")
    else:
        expected = json.dumps(expected_document(), indent=2, sort_keys=True) + "\n"
        if args.output.exists() and not args.force:
            raise FileExistsError(f"{args.output} exists; use --force")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(expected, encoding="utf-8")
    print(
        "structural_extension=PARTIAL_SCIENTIFIC_RESULT "
        "selection=25/25 audit_pass=24/25 audit_rejected=1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
