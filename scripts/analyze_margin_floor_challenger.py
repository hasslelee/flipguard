#!/usr/bin/env python3
"""Validate and compare the frozen margin-floor challenger experiment."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_ROOT = Path(
    "results/thesis_grade_protocol/direct_tabular_autotune_v1"
)
DEFAULT_CHALLENGER = (
    BASE_ROOT / "full_inputmodel_margin0p0005_floor18_keys3"
)
DEFAULT_BASELINE = (
    BASE_ROOT / "full_final_baseline_inputmodel_floor18_keys3"
)
DEFAULT_AUDIT_ID = (
    "full_inputmodel_margin0p0005_floor18_keys3_locked_audit_keys3"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--challenger-root",
        type=Path,
        default=DEFAULT_CHALLENGER,
    )
    parser.add_argument(
        "--audit-root",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--baseline-root",
        type=Path,
        default=DEFAULT_BASELINE,
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--expected-margin-floor",
        type=float,
        default=0.0005,
    )
    parser.add_argument(
        "--expected-validation-v-cert",
        type=int,
        default=8142,
    )
    parser.add_argument(
        "--expected-validation-v-amb",
        type=int,
        default=88,
    )
    parser.add_argument(
        "--expected-audit-v-cert",
        type=int,
        default=8203,
    )
    parser.add_argument(
        "--expected-audit-v-amb",
        type=int,
        default=97,
    )
    parser.add_argument(
        "--max-trial-ratio",
        type=float,
        default=1.10,
    )
    parser.add_argument(
        "--max-total-log-qp-ratio",
        type=float,
        default=1.10,
    )
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def resolve_repo_path(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else REPO_ROOT / path


def workload_key(row: dict[str, str]) -> tuple[int, str, str]:
    return (
        int(row["split_seed"]),
        row["dataset_id"],
        row["model_id"],
    )


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def validate_selection(
    root: Path,
    expected_margin_floor: float,
) -> tuple[
    dict[str, Any],
    dict[tuple[int, str, str], dict[str, Any]],
    list[dict[str, Any]],
]:
    summary_path = root / "summary/summary.json"
    rows_path = root / "summary/workload_results.csv"
    summary = load_json(summary_path)
    rows = read_csv(rows_path)
    if (
        summary.get("complete") is not True
        or summary.get("expected_runs") != 50
        or summary.get("successful_runs") != 50
        or summary.get("failed_runs") != 0
        or summary.get("selected_runs") != 50
        or summary.get("no_safe_runs") != 0
        or summary.get("require_source_replay") is not True
        or summary.get("source_replay_verified_runs") != 50
        or summary.get("source_feature_space_counts")
        != {"model_input": 50}
        or summary.get("preprocessing_method_counts")
        != {"identity_model_input_v1": 50}
        or len(rows) != 50
    ):
        raise ValueError("challenger selection matrix is incomplete")

    records: dict[tuple[int, str, str], dict[str, Any]] = {}
    external: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = workload_key(row)
        if key in records:
            raise ValueError(f"duplicate selection workload {key}")
        result_path = resolve_repo_path(row["result_path"])
        result = load_json(result_path)
        contract = result["plan"]["contract"]
        materialization = contract.get("input_materialization", {})
        decision = contract["decision"]
        selected = result["selected"]
        trial = result["trials"][-1]
        security = selected["security"]
        parameters = selected["parameters"]
        max_budget_usage = trial.get("max_error_budget_usage")
        if (
            row["status"] != "ok"
            or result["outcome"] != "SELECTED"
            or trial["status"] != "SAFE"
            or trial["decision_flips"] != 0
            or trial["error_violations"] != 0
            or trial["key_repeats_completed"] != 3
            or not math.isclose(
                float(decision["margin_floor"]),
                expected_margin_floor,
                rel_tol=0,
                abs_tol=1e-15,
            )
            or not math.isclose(
                float(decision["safety_factor"]),
                0.5,
                rel_tol=0,
                abs_tol=1e-15,
            )
            or int(row["v_cert"])
            != int(decision["certifiable_samples"])
            or int(row["v_amb"])
            != int(decision["ambiguous_samples"])
            or row["contract_digest"]
            != result["plan"]["contract_digest"]
            or row.get("source_replay_verified") != "True"
            or row.get("source_feature_space") != "model_input"
            or row.get("preprocessing_method")
            != "identity_model_input_v1"
            or materialization.get("source_replay_verified")
            is not True
            or materialization.get("source_feature_space")
            != "model_input"
            or materialization.get("preprocessing_method")
            != "identity_model_input_v1"
            or (
                expected_margin_floor == 0.0005
                and (
                    not isinstance(max_budget_usage, (int, float))
                    or not math.isfinite(float(max_budget_usage))
                    or float(max_budget_usage) >= 1
                )
            )
        ):
            raise ValueError(f"{result_path}: invalid selection evidence")
        for name in (
            "model_artifact",
            "validation_data",
            "source_data",
        ):
            item = contract[name]
            path = resolve_repo_path(item["path"])
            if sha256_path(path) != item["sha256"]:
                raise ValueError(f"{path}: input digest changed")
            external[str(path)] = bind(path)
        records[key] = {
            "split_seed": key[0],
            "dataset_id": key[1],
            "model_id": key[2],
            "workload_id": contract["workload_id"],
            "margin_floor": decision["margin_floor"],
            "v_cert": int(decision["certifiable_samples"]),
            "v_amb": int(decision["ambiguous_samples"]),
            "trials_used": int(result["trials_used"]),
            "encrypted_key_runs": int(result["encrypted_key_runs"]),
            "candidate_id": selected["id"],
            "log_n": int(parameters["log_n"]),
            "log_default_scale": int(
                parameters["log_default_scale"]
            ),
            "declared_log_qp": int(
                security["declared_log_qp"]
            ),
            "max_error_budget_usage": (
                float(max_budget_usage)
                if isinstance(max_budget_usage, (int, float))
                else ""
            ),
            "result_path": str(result_path.relative_to(REPO_ROOT)),
            "result_sha256": sha256_path(result_path),
        }
    return summary, records, list(external.values())


def validate_audit(
    root: Path,
    expected_margin_floor: float,
    selection_records: dict[
        tuple[int, str, str],
        dict[str, Any],
    ],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary_path = root / "summary/summary.json"
    rows_path = root / "summary/locked_audit_results.csv"
    status_path = root / "locked_audit_status.csv"
    summary = load_json(summary_path)
    rows = read_csv(rows_path)
    statuses = read_csv(status_path)
    if (
        summary.get("complete") is not True
        or summary.get("expected_runs") != 50
        or summary.get("recorded_runs") != 50
        or summary.get("successful_executions") != 50
        or summary.get("failed_executions") != 0
        or summary.get("locked_audit_passes") != 50
        or summary.get("locked_audit_fails") != 0
        or summary.get("retuned_runs") != 0
        or summary.get("require_source_replay") is not True
        or summary.get("source_replay_verified_runs") != 50
        or summary.get("audit_source_replay_verified_runs") != 50
        or summary.get("source_feature_space_counts")
        != {"model_input": 50}
        or summary.get("audit_source_feature_space_counts")
        != {"model_input": 50}
        or summary.get("preprocessing_method_counts")
        != {"identity_model_input_v1": 50}
        or summary.get("audit_preprocessing_method_counts")
        != {"identity_model_input_v1": 50}
        or len(rows) != 50
        or len(statuses) != 50
    ):
        raise ValueError("challenger locked audit is incomplete")

    status_by_key = {
        workload_key(row): row for row in statuses
    }
    if (
        len(status_by_key) != 50
        or any(row["status"] != "ok" for row in statuses)
    ):
        raise ValueError("challenger audit status matrix changed")
    external: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = workload_key(row)
        selection = selection_records.get(key)
        if selection is None:
            raise ValueError(f"audit has unknown workload {key}")
        result_path = resolve_repo_path(row["result_path"])
        result = load_json(result_path)
        contract = result["audit_contract"]
        materialization = contract.get("input_materialization", {})
        decision = contract["decision"]
        trial = result["audit_trial"]
        candidate = result["selected_candidate"]
        selection_binding = result["selection_result"]
        if (
            result["outcome"] != "LOCKED_AUDIT_PASS"
            or result["retuning_performed"] is not False
            or trial["status"] != "SAFE"
            or trial["decision_flips"] != 0
            or trial["error_violations"] != 0
            or trial["key_repeats_completed"] != 3
            or candidate["id"] != selection["candidate_id"]
            or not math.isclose(
                float(decision["margin_floor"]),
                expected_margin_floor,
                rel_tol=0,
                abs_tol=1e-15,
            )
            or selection_binding["sha256"]
            != selection["result_sha256"]
            or row.get("source_replay_verified") != "True"
            or row.get("audit_source_replay_verified") != "True"
            or row.get("audit_source_feature_space")
            != "model_input"
            or row.get("audit_preprocessing_method")
            != "identity_model_input_v1"
            or materialization.get("source_replay_verified")
            is not True
            or materialization.get("source_feature_space")
            != "model_input"
            or materialization.get("preprocessing_method")
            != "identity_model_input_v1"
            or (
                expected_margin_floor == 0.0005
                and (
                    not isinstance(
                        trial.get("max_error_budget_usage"),
                        (int, float),
                    )
                    or not math.isfinite(
                        float(trial["max_error_budget_usage"])
                    )
                    or float(trial["max_error_budget_usage"]) >= 1
                )
            )
        ):
            raise ValueError(f"{result_path}: invalid audit evidence")
        for item in (
            selection_binding,
            result["split_manifest"],
            contract["model_artifact"],
            contract["validation_data"],
            contract["source_data"],
        ):
            path = resolve_repo_path(item["path"])
            if sha256_path(path) != item["sha256"]:
                raise ValueError(f"{path}: audit input digest changed")
            external[str(path)] = bind(path)
    return summary, list(external.values())


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    challenger_root = (REPO_ROOT / args.challenger_root).resolve()
    baseline_root = (REPO_ROOT / args.baseline_root).resolve()
    audit_root = (
        (REPO_ROOT / args.audit_root).resolve()
        if args.audit_root is not None
        else challenger_root
        / "locked_audit"
        / (
            challenger_root.name
            + "_locked_audit_keys3"
        )
    )
    output_root = (
        (REPO_ROOT / args.output_root).resolve()
        if args.output_root is not None
        else challenger_root / "summary/challenger_analysis"
    )
    if (
        not math.isfinite(args.expected_margin_floor)
        or args.expected_margin_floor < 0
        or args.max_trial_ratio < 1
        or args.max_total_log_qp_ratio < 1
    ):
        raise ValueError("invalid challenger analysis policy")

    (
        challenger_summary,
        challenger,
        selection_external,
    ) = validate_selection(
        challenger_root,
        args.expected_margin_floor,
    )
    audit_summary, audit_external = validate_audit(
        audit_root,
        args.expected_margin_floor,
        challenger,
    )
    baseline_summary, baseline, baseline_external = (
        validate_selection(baseline_root, 0.001)
    )
    if set(challenger) != set(baseline):
        raise ValueError("challenger/baseline workload sets differ")

    validation_v_cert = sum(
        row["v_cert"] for row in challenger.values()
    )
    validation_v_amb = sum(
        row["v_amb"] for row in challenger.values()
    )
    coverage_checkpoint_pass = (
        validation_v_cert == args.expected_validation_v_cert
        and validation_v_amb == args.expected_validation_v_amb
        and audit_summary["total_v_cert"]
        == args.expected_audit_v_cert
        and audit_summary["total_v_amb"]
        == args.expected_audit_v_amb
    )

    workload_rows = []
    log_n_increases = 0
    for key in sorted(challenger):
        item = challenger[key]
        base = baseline[key]
        log_n_delta = item["log_n"] - base["log_n"]
        if log_n_delta > 0:
            log_n_increases += 1
        workload_rows.append(
            {
                "split_seed": key[0],
                "dataset_id": key[1],
                "model_id": key[2],
                "baseline_candidate_id": base["candidate_id"],
                "challenger_candidate_id": item["candidate_id"],
                "baseline_trials": base["trials_used"],
                "challenger_trials": item["trials_used"],
                "baseline_log_n": base["log_n"],
                "challenger_log_n": item["log_n"],
                "log_n_delta": log_n_delta,
                "baseline_declared_log_qp":
                    base["declared_log_qp"],
                "challenger_declared_log_qp":
                    item["declared_log_qp"],
                "declared_log_qp_delta":
                    item["declared_log_qp"]
                    - base["declared_log_qp"],
                "challenger_v_cert": item["v_cert"],
                "challenger_v_amb": item["v_amb"],
                "challenger_max_error_budget_usage":
                    item["max_error_budget_usage"],
            }
        )

    challenger_trials = sum(
        row["trials_used"] for row in challenger.values()
    )
    baseline_trials = sum(
        row["trials_used"] for row in baseline.values()
    )
    challenger_log_qp = sum(
        row["declared_log_qp"] for row in challenger.values()
    )
    baseline_log_qp = sum(
        row["declared_log_qp"] for row in baseline.values()
    )
    trial_ratio = challenger_trials / baseline_trials
    log_qp_ratio = challenger_log_qp / baseline_log_qp
    diagnostic_checks = {
        "selection_50_of_50": True,
        "locked_audit_50_of_50": True,
        "coverage_checkpoint_pass": coverage_checkpoint_pass,
        "total_trial_ratio_at_most":
            trial_ratio <= args.max_trial_ratio,
        "no_workload_log_n_increase": log_n_increases == 0,
        "total_log_qp_ratio_at_most":
            log_qp_ratio <= args.max_total_log_qp_ratio,
    }
    source_paths = {
        "challenger_selection_summary":
            challenger_root / "summary/summary.json",
        "challenger_selection_rows":
            challenger_root / "summary/workload_results.csv",
        "challenger_audit_summary":
            audit_root / "summary/summary.json",
        "challenger_audit_rows":
            audit_root / "summary/locked_audit_results.csv",
        "challenger_audit_status":
            audit_root / "locked_audit_status.csv",
        "baseline_selection_summary":
            baseline_root / "summary/summary.json",
        "baseline_selection_rows":
            baseline_root / "summary/workload_results.csv",
    }
    protocol_path = (
        challenger_root / "summary/challenger_protocol.json"
    )
    if args.expected_margin_floor == 0.0005:
        if not protocol_path.is_file():
            raise ValueError("missing challenger protocol manifest")
        protocol = load_json(protocol_path)
        if (
            protocol.get("status") != "COMPLETE"
            or protocol["policy"]["margin_floor"] != 0.0005
            or protocol["policy"]["workloads"] != 50
        ):
            raise ValueError("invalid challenger protocol manifest")
        source_paths["challenger_protocol"] = protocol_path

    external_by_path = {
        item["path"]: item
        for item in (
            selection_external
            + audit_external
            + baseline_external
        )
    }
    output_root.mkdir(parents=True, exist_ok=True)
    workload_path = output_root / "workload_comparison.csv"
    write_csv(workload_path, workload_rows)
    summary = {
        "schema_version": 2,
        "status": "COMPLETE",
        "policy_role": "SECONDARY_POLICY_SENSITIVITY",
        "primary_policy_adoption_allowed": False,
        "paper_claim_allowed": False,
        "claim_state": "PARTIALLY_SUPPORTED",
        "block_reason": (
            "The challenger locked audit is diagnostic and cannot be used "
            "to select or replace the predeclared primary policy."
        ),
        "claim_boundary": (
            "Margin floor 0.0005 is secondary sensitivity only. Its audit "
            "cannot select a primary policy; delta=0.001 remains frozen."
        ),
        "policy": {
            "primary_margin_floor": 0.001,
            "baseline_margin_floor": 0.001,
            "challenger_margin_floor":
                args.expected_margin_floor,
            "safety_factor": 0.5,
            "max_trial_ratio": args.max_trial_ratio,
            "max_total_log_qp_ratio":
                args.max_total_log_qp_ratio,
            "log_n_increase_allowed_per_workload": False,
        },
        "coverage": {
            "validation_v_cert": validation_v_cert,
            "validation_v_amb": validation_v_amb,
            "audit_v_cert": audit_summary["total_v_cert"],
            "audit_v_amb": audit_summary["total_v_amb"],
        },
        "cost": {
            "baseline_trials": baseline_trials,
            "challenger_trials": challenger_trials,
            "trial_ratio": trial_ratio,
            "baseline_total_declared_log_qp": baseline_log_qp,
            "challenger_total_declared_log_qp":
                challenger_log_qp,
            "total_declared_log_qp_ratio": log_qp_ratio,
            "workloads_with_log_n_increase": log_n_increases,
        },
        "diagnostic_checks": diagnostic_checks,
        "inputs": {
            name: bind(path)
            for name, path in source_paths.items()
        },
        "external_artifacts": [
            external_by_path[key]
            for key in sorted(external_by_path)
        ],
        "outputs": {
            "workload_comparison": {
                "path": str(workload_path.relative_to(REPO_ROOT))
                if workload_path.is_relative_to(REPO_ROOT)
                else str(workload_path),
                "bytes": workload_path.stat().st_size,
                "sha256": sha256_path(workload_path),
            }
        },
        "source_summaries": {
            "challenger": challenger_summary,
            "baseline": baseline_summary,
        },
    }
    write_json(output_root / "summary.json", summary)
    return summary


def verify(output_root: Path) -> None:
    summary = load_json(output_root / "summary.json")
    if (
        summary.get("schema_version") != 2
        or summary.get("status") != "COMPLETE"
        or summary.get("policy_role")
        != "SECONDARY_POLICY_SENSITIVITY"
        or summary.get("primary_policy_adoption_allowed") is not False
        or summary.get("paper_claim_allowed") is not False
    ):
        raise ValueError("unsupported challenger analysis summary")
    for item in summary["inputs"].values():
        path = resolve_repo_path(item["path"])
        if (
            path.stat().st_size != item["bytes"]
            or sha256_path(path) != item["sha256"]
        ):
            raise ValueError(f"{path}: analysis input changed")
    for item in summary["external_artifacts"]:
        path = resolve_repo_path(item["path"])
        if (
            path.stat().st_size != item["bytes"]
            or sha256_path(path) != item["sha256"]
        ):
            raise ValueError(f"{path}: external artifact changed")
    workload_path = output_root / "workload_comparison.csv"
    expected = summary["outputs"]["workload_comparison"]
    if (
        workload_path.stat().st_size != expected["bytes"]
        or sha256_path(workload_path) != expected["sha256"]
        or len(read_csv(workload_path)) != 50
    ):
        raise ValueError("challenger workload comparison changed")
    print(
        "margin_floor_challenger=VERIFIED "
        "role=SECONDARY_POLICY_SENSITIVITY "
        "primary_adoption_allowed=false "
        f"trials={summary['cost']['challenger_trials']} "
        f"validation_v_cert="
        f"{summary['coverage']['validation_v_cert']} "
        f"audit_v_cert={summary['coverage']['audit_v_cert']}"
    )


def main() -> int:
    args = parse_args()
    output_root = (
        (REPO_ROOT / args.output_root).resolve()
        if args.output_root is not None
        else (REPO_ROOT / args.challenger_root).resolve()
        / "summary/challenger_analysis"
    )
    if args.verify:
        verify(output_root)
    else:
        analyze(args)
        verify(output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
