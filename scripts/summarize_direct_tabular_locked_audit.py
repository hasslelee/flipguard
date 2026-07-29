#!/usr/bin/env python3
"""Validate and summarize no-retuning locked-audit artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


RESULT_FIELDS = [
    "run_id",
    "split_seed",
    "dataset_id",
    "model_id",
    "workload_id",
    "outcome",
    "trial_status",
    "retuning_performed",
    "candidate_id",
    "log_n",
    "q_prime_count",
    "p_prime_count",
    "log_default_scale",
    "key_repeats_requested",
    "key_repeats_completed",
    "success_runs",
    "decision_flips",
    "error_violations",
    "max_observed_error",
    "max_error_budget_usage",
    "v_cert",
    "v_amb",
    "mean_total_ms",
    "median_total_ms",
    "p95_total_ms",
    "selection_contract_digest",
    "selection_result_sha256",
    "split_manifest_sha256",
    "audit_csv_sha256",
    "source_replay_verified",
    "source_feature_space",
    "preprocessing_method",
    "source_data_sha256",
    "prepared_validation_sha256",
    "audit_source_replay_verified",
    "audit_source_feature_space",
    "audit_preprocessing_method",
    "prepared_audit_sha256",
    "selection_result_path",
    "split_manifest_path",
    "audit_csv_path",
    "result_path",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-status", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--expected-runs", type=int, required=True)
    parser.add_argument(
        "--require-source-replay",
        action="store_true",
        help=(
            "require verified source materialization for both selection "
            "and locked-audit partitions"
        ),
    )
    return parser.parse_args()


def require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def csv_row_ids(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{path}: CSV contains no rows")
    if "row_id" not in rows[0]:
        raise ValueError(f"{path}: CSV has no row_id column")
    values = [row["row_id"].strip() for row in rows]
    if any(not value for value in values):
        raise ValueError(f"{path}: CSV contains an empty row_id")
    if len(set(values)) != len(values):
        raise ValueError(f"{path}: CSV contains duplicate row_id values")
    return set(values)


def load_status_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {
        "run_id",
        "split_seed",
        "dataset_id",
        "model_id",
        "tag",
        "status",
        "exit_code",
        "outcome",
        "result_path",
        "selection_path",
        "audit_path",
        "manifest_path",
        "stdout_log",
    }
    if rows and not required.issubset(rows[0]):
        missing = sorted(required - set(rows[0]))
        raise ValueError(f"run-status CSV missing columns: {missing}")
    tags = [row["tag"] for row in rows]
    duplicates = [
        tag for tag, count in Counter(tags).items() if count > 1
    ]
    if duplicates:
        raise ValueError(
            f"duplicate run-status tags: {sorted(duplicates)}"
        )
    return rows


def require_artifact_binding(
    binding: dict[str, Any],
    expected_path: Path,
    label: str,
) -> str:
    if str(binding.get("path", "")) != str(expected_path):
        raise ValueError(
            f"{label}: bound path {binding.get('path')!r} "
            f"!= {str(expected_path)!r}"
        )
    actual_digest = sha256_file(expected_path)
    if binding.get("sha256") != actual_digest:
        raise ValueError(
            f"{label}: bound digest {binding.get('sha256')!r} "
            f"!= {actual_digest!r}"
        )
    return actual_digest


def summarize_result(
    status: dict[str, str],
    require_source_replay: bool = False,
) -> dict[str, Any]:
    result_path = Path(status["result_path"])
    selection_path = Path(status["selection_path"])
    audit_path = Path(status["audit_path"])
    manifest_path = Path(status["manifest_path"])

    result = require_dict(
        json.loads(result_path.read_text(encoding="utf-8")),
        str(result_path),
    )
    selection = require_dict(
        json.loads(selection_path.read_text(encoding="utf-8")),
        str(selection_path),
    )
    manifest = require_dict(
        json.loads(manifest_path.read_text(encoding="utf-8")),
        str(manifest_path),
    )

    if result.get("schema_version") != 1:
        raise ValueError(f"{result_path}: unsupported schema version")
    if result.get("retuning_performed") is not False:
        raise ValueError(f"{result_path}: retuning_performed is not false")

    split_id = f"split_seed_{status['split_seed']}"
    workload_id = (
        f"{split_id}/{status['dataset_id']}/{status['model_id']}"
    )
    if result.get("selection_workload_id") != workload_id:
        raise ValueError(
            f"{result_path}: selection workload identity mismatch"
        )

    selection_plan = require_dict(
        selection.get("plan"), f"{selection_path}: plan"
    )
    selection_contract = require_dict(
        selection_plan.get("contract"),
        f"{selection_path}: contract",
    )
    expected_identity = (
        split_id,
        status["dataset_id"],
        status["model_id"],
        workload_id,
    )
    actual_identity = (
        selection_contract.get("split_id"),
        selection_contract.get("dataset_id"),
        selection_contract.get("model_id"),
        selection_contract.get("workload_id"),
    )
    if actual_identity != expected_identity:
        raise ValueError(
            f"{selection_path}: identity {actual_identity} "
            f"!= {expected_identity}"
        )
    if selection.get("outcome") != "SELECTED":
        raise ValueError(f"{selection_path}: selection is not SELECTED")
    selected = require_dict(
        selection.get("selected"), f"{selection_path}: selected"
    )
    if result.get("selected_candidate") != selected:
        raise ValueError(f"{result_path}: selected literal changed")
    if (
        result.get("selection_contract_digest")
        != selection_plan.get("contract_digest")
    ):
        raise ValueError(
            f"{result_path}: selection contract digest mismatch"
        )

    selection_binding = require_dict(
        result.get("selection_result"),
        f"{result_path}: selection binding",
    )
    manifest_binding = require_dict(
        result.get("split_manifest"),
        f"{result_path}: manifest binding",
    )
    selection_digest = require_artifact_binding(
        selection_binding,
        selection_path,
        f"{result_path}: selection binding",
    )
    manifest_digest = require_artifact_binding(
        manifest_binding,
        manifest_path,
        f"{result_path}: manifest binding",
    )

    if manifest.get("schema_version") != 1:
        raise ValueError(f"{manifest_path}: unsupported schema version")
    if (
        manifest.get("split_seed") != int(status["split_seed"])
        or manifest.get("dataset_id") != status["dataset_id"]
        or manifest.get("model_id") != status["model_id"]
    ):
        raise ValueError(f"{manifest_path}: workload identity mismatch")

    manifest_validation = require_dict(
        manifest.get("configuration_validation"),
        f"{manifest_path}: configuration_validation",
    )
    manifest_audit = require_dict(
        manifest.get("locked_audit_test"),
        f"{manifest_path}: locked_audit_test",
    )
    selection_validation = require_dict(
        selection_contract.get("validation_data"),
        f"{selection_path}: validation_data",
    )
    selection_partition = selection_validation
    source_replay_verified = False
    source_feature_space = ""
    preprocessing_method = ""
    source_data_sha256 = ""
    source_value = selection_contract.get("source_data")
    materialization_value = selection_contract.get(
        "input_materialization"
    )
    if source_value is not None or materialization_value is not None:
        selection_source = require_dict(
            source_value,
            f"{selection_path}: source_data",
        )
        materialization = require_dict(
            materialization_value,
            f"{selection_path}: input_materialization",
        )
        if (
            materialization.get("schema_version")
            != "flipguard_tabular_validation_v2"
            or materialization.get("source_feature_space")
            != "model_input"
            or materialization.get("preprocessing_method")
            != "identity_model_input_v1"
            or materialization.get("source_replay_verified")
            is not True
        ):
            raise ValueError(
                f"{selection_path}: invalid source replay contract"
            )
        source_path = Path(str(selection_source["path"]))
        source_data_sha256 = str(selection_source["sha256"])
        if sha256_file(source_path) != source_data_sha256:
            raise ValueError(
                f"{selection_path}: source data digest mismatch"
            )
        selection_partition = selection_source
        source_replay_verified = True
        source_feature_space = str(
            materialization["source_feature_space"]
        )
        preprocessing_method = str(
            materialization["preprocessing_method"]
        )
    elif require_source_replay:
        raise ValueError(
            f"{selection_path}: selection source replay is required"
        )
    if (
        manifest_validation.get("path")
        != selection_partition.get("path")
        or manifest_validation.get("csv_digest")
        != selection_partition.get("sha256")
    ):
        raise ValueError(
            f"{manifest_path}: selection validation binding mismatch"
        )
    if manifest_audit.get("path") != str(audit_path):
        raise ValueError(f"{manifest_path}: audit path mismatch")
    audit_digest = sha256_file(audit_path)
    if manifest_audit.get("csv_digest") != audit_digest:
        raise ValueError(f"{manifest_path}: audit digest mismatch")

    validation_path = Path(str(selection_validation["path"]))
    if sha256_file(validation_path) != selection_validation.get("sha256"):
        raise ValueError(
            f"{selection_path}: validation artifact digest mismatch"
        )
    validation_ids = csv_row_ids(validation_path)
    manifest_validation_ids = {
        str(value).strip()
        for value in require_list(
            manifest_validation.get("row_ids"),
            f"{manifest_path}: validation row_ids",
        )
    }
    manifest_audit_ids = {
        str(value).strip()
        for value in require_list(
            manifest_audit.get("row_ids"),
            f"{manifest_path}: audit row_ids",
        )
    }
    if validation_ids != manifest_validation_ids:
        raise ValueError(
            f"{manifest_path}: validation row IDs mismatch"
        )
    if source_replay_verified:
        source_ids = csv_row_ids(
            Path(str(selection_partition["path"]))
        )
        if source_ids != validation_ids:
            raise ValueError(
                f"{selection_path}: source/prepared row IDs mismatch"
            )
    audit_contract = require_dict(
        result.get("audit_contract"),
        f"{result_path}: audit contract",
    )
    if (
        audit_contract.get("split_id") != split_id + "/locked_audit"
        or audit_contract.get("dataset_id") != status["dataset_id"]
        or audit_contract.get("model_id") != status["model_id"]
    ):
        raise ValueError(f"{result_path}: audit contract identity mismatch")
    audit_binding = require_dict(
        audit_contract.get("validation_data"),
        f"{result_path}: audit validation binding",
    )
    audit_source_replay_verified = False
    audit_source_feature_space = ""
    audit_preprocessing_method = ""
    audit_prepared_path = audit_path
    audit_source_value = audit_contract.get("source_data")
    audit_materialization_value = audit_contract.get(
        "input_materialization"
    )
    if (
        audit_source_value is not None
        or audit_materialization_value is not None
    ):
        audit_source = require_dict(
            audit_source_value,
            f"{result_path}: audit source data",
        )
        audit_materialization = require_dict(
            audit_materialization_value,
            f"{result_path}: audit input materialization",
        )
        if (
            audit_source.get("path") != str(audit_path)
            or audit_source.get("sha256") != audit_digest
            or audit_materialization.get("schema_version")
            != "flipguard_tabular_validation_v2"
            or audit_materialization.get("source_feature_space")
            != "model_input"
            or audit_materialization.get("preprocessing_method")
            != "identity_model_input_v1"
            or audit_materialization.get(
                "source_replay_verified"
            )
            is not True
        ):
            raise ValueError(
                f"{result_path}: audit source replay contract mismatch"
            )
        audit_prepared_path = Path(str(audit_binding["path"]))
        audit_source_replay_verified = True
        audit_source_feature_space = str(
            audit_materialization["source_feature_space"]
        )
        audit_preprocessing_method = str(
            audit_materialization["preprocessing_method"]
        )
    elif (
        audit_binding.get("path") != str(audit_path)
        or audit_binding.get("sha256") != audit_digest
    ):
        raise ValueError(f"{result_path}: audit contract binding mismatch")
    elif require_source_replay:
        raise ValueError(
            f"{result_path}: audit source replay is required"
        )
    prepared_audit_digest = sha256_file(audit_prepared_path)
    if prepared_audit_digest != audit_binding.get("sha256"):
        raise ValueError(
            f"{result_path}: prepared audit digest mismatch"
        )
    audit_ids = csv_row_ids(audit_prepared_path)
    if audit_ids != manifest_audit_ids:
        raise ValueError(f"{manifest_path}: audit row IDs mismatch")
    if validation_ids & audit_ids:
        raise ValueError(
            f"{result_path}: validation and audit row IDs overlap"
        )
    if audit_source_replay_verified:
        audit_source_ids = csv_row_ids(audit_path)
        if audit_source_ids != audit_ids:
            raise ValueError(
                f"{result_path}: audit source/prepared row IDs mismatch"
            )
    deployment = require_dict(
        audit_contract.get("deployment"),
        f"{result_path}: audit deployment",
    )
    if deployment.get("max_encrypted_trials") != 1:
        raise ValueError(
            f"{result_path}: audit contract permits more than one trial"
        )

    trial = require_dict(
        result.get("audit_trial"), f"{result_path}: audit trial"
    )
    if trial.get("trial_index") != 1:
        raise ValueError(f"{result_path}: audit trial index is not one")
    if trial.get("candidate") != selected:
        raise ValueError(f"{result_path}: audit trial literal changed")
    requested = int(trial.get("key_repeats_requested", -1))
    completed = int(trial.get("key_repeats_completed", -1))
    if requested != int(deployment.get("validation_key_repeats", -1)):
        raise ValueError(f"{result_path}: requested key count mismatch")
    if status["outcome"] != result.get("outcome"):
        raise ValueError(f"{result_path}: status outcome mismatch")

    outcome = str(result.get("outcome", ""))
    trial_status = str(trial.get("status", ""))
    if outcome == "LOCKED_AUDIT_PASS":
        if trial_status != "SAFE":
            raise ValueError(f"{result_path}: PASS trial is not SAFE")
        if (
            completed != requested
            or int(trial.get("success_runs", -1)) != requested
            or int(trial.get("decision_flips", -1)) != 0
            or int(trial.get("error_violations", -1)) != 0
        ):
            raise ValueError(
                f"{result_path}: PASS evidence is internally inconsistent"
            )
    elif outcome == "LOCKED_AUDIT_FAIL":
        if trial_status == "SAFE":
            raise ValueError(f"{result_path}: FAIL trial is SAFE")
    else:
        raise ValueError(f"{result_path}: unsupported outcome {outcome!r}")

    parameters = require_dict(
        selected.get("parameters"), f"{result_path}: parameters"
    )
    return {
        "run_id": status["run_id"],
        "split_seed": int(status["split_seed"]),
        "dataset_id": status["dataset_id"],
        "model_id": status["model_id"],
        "workload_id": workload_id,
        "outcome": outcome,
        "trial_status": trial_status,
        "retuning_performed": result["retuning_performed"],
        "candidate_id": selected.get("id", ""),
        "log_n": parameters.get("log_n", ""),
        "q_prime_count": len(parameters.get("log_q", [])),
        "p_prime_count": len(parameters.get("log_p", [])),
        "log_default_scale": parameters.get(
            "log_default_scale", ""
        ),
        "key_repeats_requested": requested,
        "key_repeats_completed": completed,
        "success_runs": trial.get("success_runs", ""),
        "decision_flips": trial.get("decision_flips", ""),
        "error_violations": trial.get("error_violations", ""),
        "max_observed_error": trial.get("max_observed_error", ""),
        "max_error_budget_usage": trial.get(
            "max_error_budget_usage",
            "",
        ),
        "v_cert": trial.get("v_cert", ""),
        "v_amb": trial.get("v_amb", ""),
        "mean_total_ms": trial.get("mean_total_ms", ""),
        "median_total_ms": trial.get("median_total_ms", ""),
        "p95_total_ms": trial.get("p95_total_ms", ""),
        "selection_contract_digest": result.get(
            "selection_contract_digest", ""
        ),
        "selection_result_sha256": selection_digest,
        "split_manifest_sha256": manifest_digest,
        "audit_csv_sha256": audit_digest,
        "source_replay_verified": source_replay_verified,
        "source_feature_space": source_feature_space,
        "preprocessing_method": preprocessing_method,
        "source_data_sha256": source_data_sha256,
        "prepared_validation_sha256": selection_validation[
            "sha256"
        ],
        "audit_source_replay_verified":
            audit_source_replay_verified,
        "audit_source_feature_space": audit_source_feature_space,
        "audit_preprocessing_method": audit_preprocessing_method,
        "prepared_audit_sha256": prepared_audit_digest,
        "selection_result_path": str(selection_path),
        "split_manifest_path": str(manifest_path),
        "audit_csv_path": str(audit_path),
        "result_path": str(result_path),
    }


def main() -> int:
    args = parse_args()
    if args.expected_runs < 1:
        raise ValueError("--expected-runs must be positive")

    status_rows = load_status_rows(args.run_status)
    successful_status = [
        row for row in status_rows if row["status"] == "ok"
    ]
    failed_status = [
        row for row in status_rows if row["status"] != "ok"
    ]
    rows = [
        summarize_result(row, args.require_source_replay)
        for row in successful_status
    ]
    rows.sort(
        key=lambda row: (
            row["split_seed"],
            row["dataset_id"],
            row["model_id"],
        )
    )

    args.output_root.mkdir(parents=True, exist_ok=True)
    results_path = args.output_root / "locked_audit_results.csv"
    with results_path.open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=RESULT_FIELDS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    passed = [
        row
        for row in rows
        if row["outcome"] == "LOCKED_AUDIT_PASS"
    ]
    summary = {
        "schema_version": 1,
        "run_status_path": str(args.run_status),
        "expected_runs": args.expected_runs,
        "recorded_runs": len(status_rows),
        "successful_executions": len(rows),
        "failed_executions": len(failed_status),
        "complete": (
            len(status_rows) == args.expected_runs
            and not failed_status
        ),
        "locked_audit_passes": len(passed),
        "locked_audit_fails": sum(
            row["outcome"] == "LOCKED_AUDIT_FAIL"
            for row in rows
        ),
        "retuned_runs": sum(
            bool(row["retuning_performed"]) for row in rows
        ),
        "total_configuration_trials": len(rows),
        "total_fresh_key_runs": sum(
            int(row["key_repeats_completed"]) for row in rows
        ),
        "zero_flip_passes": sum(
            int(row["decision_flips"]) == 0 for row in passed
        ),
        "zero_violation_passes": sum(
            int(row["error_violations"]) == 0 for row in passed
        ),
        "source_replay_verified_runs": sum(
            row["source_replay_verified"] is True for row in rows
        ),
        "audit_source_replay_verified_runs": sum(
            row["audit_source_replay_verified"] is True
            for row in rows
        ),
        "require_source_replay": args.require_source_replay,
        "source_feature_space_counts": dict(
            sorted(
                Counter(
                    row["source_feature_space"]
                    for row in rows
                    if row["source_feature_space"]
                ).items()
            )
        ),
        "preprocessing_method_counts": dict(
            sorted(
                Counter(
                    row["preprocessing_method"]
                    for row in rows
                    if row["preprocessing_method"]
                ).items()
            )
        ),
        "audit_source_feature_space_counts": dict(
            sorted(
                Counter(
                    row["audit_source_feature_space"]
                    for row in rows
                    if row["audit_source_feature_space"]
                ).items()
            )
        ),
        "audit_preprocessing_method_counts": dict(
            sorted(
                Counter(
                    row["audit_preprocessing_method"]
                    for row in rows
                    if row["audit_preprocessing_method"]
                ).items()
            )
        ),
        "total_v_cert": sum(int(row["v_cert"]) for row in rows),
        "total_v_amb": sum(int(row["v_amb"]) for row in rows),
        "outcome_counts": dict(
            sorted(Counter(row["outcome"] for row in rows).items())
        ),
        "failed_tags": [row["tag"] for row in failed_status],
    }
    summary_path = args.output_root / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        "locked_audit_summary="
        f"{'COMPLETE' if summary['complete'] else 'CHECKPOINT'} "
        f"recorded={summary['recorded_runs']}/{summary['expected_runs']} "
        f"pass={summary['locked_audit_passes']} "
        f"audit_fail={summary['locked_audit_fails']} "
        f"exec_fail={summary['failed_executions']} "
        f"retuned={summary['retuned_runs']} "
        f"key_runs={summary['total_fresh_key_runs']}"
    )
    print(f"locked_audit_results={results_path}")
    print(f"summary_json={summary_path}")
    if failed_status:
        print(
            "ERROR: locked audit matrix contains execution failures: "
            + ",".join(row["tag"] for row in failed_status)
        )
        return 1
    if summary["locked_audit_fails"]:
        print(
            "ERROR: frozen candidates failed locked audit: "
            + ",".join(
                row["workload_id"]
                for row in rows
                if row["outcome"] == "LOCKED_AUDIT_FAIL"
            )
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
