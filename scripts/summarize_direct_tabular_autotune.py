#!/usr/bin/env python3
"""Validate and summarize direct adaptive autotune matrix artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


TRIAL_FIELDS = [
    "run_id",
    "split_seed",
    "partition_role",
    "dataset_id",
    "model_id",
    "workload_id",
    "status",
    "outcome",
    "trials_used",
    "encrypted_key_runs",
    "selected_candidate_id",
    "selected_trial_status",
    "selected_assurance",
    "log_n",
    "q_prime_count",
    "p_prime_count",
    "log_default_scale",
    "declared_log_qp",
    "security_headroom_bits",
    "analysis_scale_bits",
    "backend_scale_lift_bits",
    "backend_validation_attempts",
    "same_tier_precision_gain_bits",
    "same_tier_static_candidates_tried",
    "generation_kind",
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
    "contract_digest",
    "model_sha256",
    "validation_sha256",
    "prepared_validation_sha256",
    "source_data_sha256",
    "source_validation_sha256",
    "materialization_schema",
    "source_feature_space",
    "preprocessing_method",
    "source_replay_verified",
    "result_path",
]

TRIAL_DETAIL_FIELDS = [
    "run_id",
    "split_seed",
    "partition_role",
    "dataset_id",
    "model_id",
    "workload_id",
    "trial_index",
    "candidate_id",
    "generation_kind",
    "status",
    "assurance",
    "failure_signal",
    "failure",
    "log_n",
    "q_prime_count",
    "p_prime_count",
    "log_default_scale",
    "declared_log_qp",
    "security_headroom_bits",
    "analysis_scale_bits",
    "backend_scale_lift_bits",
    "backend_validation_attempts",
    "same_tier_precision_gain_bits",
    "same_tier_static_candidates_tried",
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
            "require every result to bind source feature data and a "
            "successfully replayed input materialization"
        ),
    )
    return parser.parse_args()


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
        "trials_used",
        "result_path",
        "stdout_log",
    }
    if rows and not required.issubset(rows[0]):
        missing = sorted(required - set(rows[0]))
        raise ValueError(f"run-status CSV missing columns: {missing}")
    tags = [row["tag"] for row in rows]
    duplicates = [tag for tag, count in Counter(tags).items() if count > 1]
    if duplicates:
        raise ValueError(f"duplicate run-status tags: {sorted(duplicates)}")
    return rows


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


def source_replay_fields(
    contract: dict[str, Any],
    result_path: Path,
    require_source_replay: bool,
) -> dict[str, Any]:
    source_value = contract.get("source_data")
    materialization_value = contract.get("input_materialization")
    if source_value is None and materialization_value is None:
        if require_source_replay:
            raise ValueError(
                f"{result_path}: source replay is required"
            )
        return {
            "source_data_sha256": "",
            "source_validation_sha256": "",
            "materialization_schema": "",
            "source_feature_space": "",
            "preprocessing_method": "",
            "source_replay_verified": False,
        }
    source = require_dict(
        source_value,
        f"{result_path}: source data",
    )
    materialization = require_dict(
        materialization_value,
        f"{result_path}: input materialization",
    )
    source_path = Path(str(source.get("path", "")))
    source_digest = str(source.get("sha256", ""))
    if (
        not source_path.is_file()
        or not source_digest.startswith("sha256:")
        or sha256_file(source_path) != source_digest
    ):
        raise ValueError(
            f"{result_path}: source data binding changed"
        )
    schema = str(materialization.get("schema_version", ""))
    feature_space = str(
        materialization.get("source_feature_space", "")
    )
    preprocessing = str(
        materialization.get("preprocessing_method", "")
    )
    replay_verified = materialization.get(
        "source_replay_verified"
    )
    if (
        schema not in {
            "flipguard_tabular_validation_v1",
            "flipguard_tabular_validation_v2",
        }
        or not feature_space
        or not preprocessing
        or replay_verified is not True
    ):
        raise ValueError(
            f"{result_path}: source materialization contract is invalid"
        )
    return {
        "source_data_sha256": source_digest,
        "source_validation_sha256": source_digest,
        "materialization_schema": schema,
        "source_feature_space": feature_space,
        "preprocessing_method": preprocessing,
        "source_replay_verified": True,
    }


def require_identity(
    status: dict[str, str],
    contract: dict[str, Any],
    result_path: Path,
) -> None:
    expected_split = f"split_seed_{status['split_seed']}"
    expected_workload = (
        f"{expected_split}/{status['dataset_id']}/{status['model_id']}"
    )
    actual = (
        str(contract.get("split_id", "")),
        str(contract.get("dataset_id", "")),
        str(contract.get("model_id", "")),
        str(contract.get("workload_id", "")),
    )
    expected = (
        expected_split,
        status["dataset_id"],
        status["model_id"],
        expected_workload,
    )
    if actual != expected:
        raise ValueError(
            f"{result_path}: workload identity {actual} does not match {expected}"
        )


def summarize_result(
    status: dict[str, str],
    require_source_replay: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result_path = Path(status["result_path"])
    payload = require_dict(
        json.loads(result_path.read_text(encoding="utf-8")),
        str(result_path),
    )
    plan = require_dict(payload.get("plan"), f"{result_path}: plan")
    contract = require_dict(plan.get("contract"), f"{result_path}: contract")
    require_identity(status, contract, result_path)

    outcome = str(payload.get("outcome", ""))
    trials = require_list(payload.get("trials"), f"{result_path}: trials")
    trials_used = int(payload.get("trials_used", -1))
    if trials_used != len(trials) or trials_used < 1:
        raise ValueError(
            f"{result_path}: trials_used={trials_used} but has {len(trials)} trials"
        )
    if status["outcome"] != outcome:
        raise ValueError(
            f"{result_path}: status outcome {status['outcome']} != {outcome}"
        )
    if int(status["trials_used"]) != trials_used:
        raise ValueError(
            f"{result_path}: status trials {status['trials_used']} != {trials_used}"
        )
    encrypted_key_runs = int(
        payload.get(
            "encrypted_key_runs",
            sum(
                int(
                    require_dict(
                        trial,
                        f"{result_path}: trial",
                    ).get("key_repeats_completed", 1)
                )
                for trial in trials
            ),
        )
    )

    selected = payload.get("selected")
    selected_candidate: dict[str, Any] = {}
    selected_trial: dict[str, Any] = {}
    if outcome == "SELECTED":
        selected_candidate = require_dict(selected, f"{result_path}: selected")
        selected_id = str(selected_candidate.get("id", ""))
        matching = [
            require_dict(trial, f"{result_path}: trial")
            for trial in trials
            if require_dict(trial, f"{result_path}: trial")
            .get("candidate", {})
            .get("id")
            == selected_id
        ]
        if len(matching) != 1:
            raise ValueError(
                f"{result_path}: selected candidate has {len(matching)} trial matches"
            )
        selected_trial = matching[0]
        if selected_trial.get("status") != "SAFE":
            raise ValueError(f"{result_path}: selected trial is not SAFE")
    elif outcome == "NO_SAFE":
        if selected is not None:
            raise ValueError(f"{result_path}: NO_SAFE result contains selected candidate")
        selected_trial = require_dict(trials[-1], f"{result_path}: final trial")
    else:
        raise ValueError(f"{result_path}: unsupported outcome {outcome!r}")

    parameters = require_dict(
        selected_candidate.get("parameters", {}),
        f"{result_path}: selected parameters",
    )
    security = require_dict(
        selected_candidate.get("security", {}),
        f"{result_path}: selected security",
    )
    decision = require_dict(
        contract.get("decision"),
        f"{result_path}: decision contract",
    )
    model_artifact = require_dict(
        contract.get("model_artifact"),
        f"{result_path}: model artifact",
    )
    validation_artifact = require_dict(
        contract.get("validation_data"),
        f"{result_path}: validation artifact",
    )
    replay_fields = source_replay_fields(
        contract,
        result_path,
        require_source_replay,
    )

    trial_rows: list[dict[str, Any]] = []
    for raw_trial in trials:
        trial = require_dict(raw_trial, f"{result_path}: trial")
        candidate = require_dict(
            trial.get("candidate"),
            f"{result_path}: trial candidate",
        )
        trial_parameters = require_dict(
            candidate.get("parameters"),
            f"{result_path}: trial parameters",
        )
        trial_security = require_dict(
            candidate.get("security"),
            f"{result_path}: trial security",
        )
        trial_rows.append(
            {
                "run_id": status["run_id"],
                "split_seed": int(status["split_seed"]),
                "partition_role": (
                    "development_ablation"
                    if int(status["split_seed"]) == 0
                    else "post_freeze_repeated_partition_evaluation"
                ),
                "dataset_id": status["dataset_id"],
                "model_id": status["model_id"],
                "workload_id": contract["workload_id"],
                "trial_index": trial.get("trial_index", ""),
                "candidate_id": candidate.get("id", ""),
                "generation_kind": candidate.get("generation_kind", ""),
                "status": trial.get("status", ""),
                "assurance": trial.get("assurance", ""),
                "failure_signal": trial.get("failure_signal", ""),
                "failure": trial.get("failure", ""),
                "log_n": trial_parameters.get("log_n", ""),
                "q_prime_count": len(trial_parameters.get("log_q", [])),
                "p_prime_count": len(trial_parameters.get("log_p", [])),
                "log_default_scale": trial_parameters.get(
                    "log_default_scale",
                    "",
                ),
                "declared_log_qp": trial_security.get("declared_log_qp", ""),
                "security_headroom_bits": trial_security.get(
                    "headroom_bits",
                    "",
                ),
                "analysis_scale_bits": candidate.get(
                    "analysis_scale_bits",
                    "",
                ),
                "backend_scale_lift_bits": candidate.get(
                    "backend_scale_lift_bits",
                    "",
                ),
                "backend_validation_attempts": candidate.get(
                    "backend_validation_attempts",
                    "",
                ),
                "same_tier_precision_gain_bits": candidate.get(
                    "same_tier_precision_gain_bits",
                    "",
                ),
                "same_tier_static_candidates_tried": candidate.get(
                    "same_tier_static_candidates_tried",
                    "",
                ),
                "key_repeats_requested": trial.get(
                    "key_repeats_requested",
                    1,
                ),
                "key_repeats_completed": trial.get(
                    "key_repeats_completed",
                    1,
                ),
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
                "result_path": str(result_path),
            }
        )

    workload_row = {
        "run_id": status["run_id"],
        "split_seed": int(status["split_seed"]),
        "partition_role": (
            "development_ablation"
            if int(status["split_seed"]) == 0
            else "post_freeze_repeated_partition_evaluation"
        ),
        "dataset_id": status["dataset_id"],
        "model_id": status["model_id"],
        "workload_id": contract["workload_id"],
        "status": status["status"],
        "outcome": outcome,
        "trials_used": trials_used,
        "encrypted_key_runs": encrypted_key_runs,
        "selected_candidate_id": selected_candidate.get("id", ""),
        "selected_trial_status": selected_trial.get("status", ""),
        "selected_assurance": selected_trial.get("assurance", ""),
        "log_n": parameters.get("log_n", ""),
        "q_prime_count": len(parameters.get("log_q", [])),
        "p_prime_count": len(parameters.get("log_p", [])),
        "log_default_scale": parameters.get("log_default_scale", ""),
        "declared_log_qp": security.get("declared_log_qp", ""),
        "security_headroom_bits": security.get("headroom_bits", ""),
        "analysis_scale_bits": selected_candidate.get(
            "analysis_scale_bits",
            "",
        ),
        "backend_scale_lift_bits": selected_candidate.get(
            "backend_scale_lift_bits",
            "",
        ),
        "backend_validation_attempts": selected_candidate.get(
            "backend_validation_attempts",
            "",
        ),
        "same_tier_precision_gain_bits": selected_candidate.get(
            "same_tier_precision_gain_bits",
            "",
        ),
        "same_tier_static_candidates_tried": selected_candidate.get(
            "same_tier_static_candidates_tried",
            "",
        ),
        "generation_kind": selected_candidate.get("generation_kind", ""),
        "key_repeats_requested": selected_trial.get(
            "key_repeats_requested",
            1,
        ),
        "key_repeats_completed": selected_trial.get(
            "key_repeats_completed",
            1,
        ),
        "success_runs": selected_trial.get("success_runs", ""),
        "decision_flips": selected_trial.get("decision_flips", ""),
        "error_violations": selected_trial.get("error_violations", ""),
        "max_observed_error": selected_trial.get("max_observed_error", ""),
        "max_error_budget_usage": selected_trial.get(
            "max_error_budget_usage",
            "",
        ),
        "v_cert": selected_trial.get("v_cert", decision.get("certifiable_samples", "")),
        "v_amb": selected_trial.get("v_amb", decision.get("ambiguous_samples", "")),
        "mean_total_ms": selected_trial.get("mean_total_ms", ""),
        "median_total_ms": selected_trial.get("median_total_ms", ""),
        "p95_total_ms": selected_trial.get("p95_total_ms", ""),
        "contract_digest": plan.get("contract_digest", ""),
        "model_sha256": model_artifact.get("sha256", ""),
        "validation_sha256": validation_artifact.get("sha256", ""),
        "prepared_validation_sha256": validation_artifact.get(
            "sha256",
            "",
        ),
        **replay_fields,
        "result_path": str(result_path),
    }
    return workload_row, trial_rows


def mean_or_none(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def main() -> int:
    args = parse_args()
    if args.expected_runs < 1:
        raise ValueError("--expected-runs must be positive")

    status_rows = load_status_rows(args.run_status)
    successful_status = [row for row in status_rows if row["status"] == "ok"]
    failed_status = [row for row in status_rows if row["status"] != "ok"]

    parsed = [
        summarize_result(row, args.require_source_replay)
        for row in successful_status
    ]
    rows = [workload_row for workload_row, _ in parsed]
    trial_rows = [
        trial_row
        for _, workload_trials in parsed
        for trial_row in workload_trials
    ]
    rows.sort(key=lambda row: (row["split_seed"], row["dataset_id"], row["model_id"]))
    trial_rows.sort(
        key=lambda row: (
            row["split_seed"],
            row["dataset_id"],
            row["model_id"],
            int(row["trial_index"]),
        )
    )

    args.output_root.mkdir(parents=True, exist_ok=True)
    trials_path = args.output_root / "workload_results.csv"
    with trials_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRIAL_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    encrypted_trials_path = args.output_root / "encrypted_trials.csv"
    with encrypted_trials_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=TRIAL_DETAIL_FIELDS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(trial_rows)

    selected_rows = [row for row in rows if row["outcome"] == "SELECTED"]
    grouped_trials: dict[str, list[int]] = defaultdict(list)
    grouped_latency: dict[str, list[float]] = defaultdict(list)
    for row in selected_rows:
        grouped_trials[row["model_id"]].append(int(row["trials_used"]))
        grouped_latency[row["model_id"]].append(float(row["mean_total_ms"]))

    summary = {
        "schema_version": 1,
        "evaluation_unit": (
            "10 dataset-model workloads x 5 partition seeds; "
            "50 workload-partition instances"
        ),
        "partition_semantics": (
            "five deterministic repeated partitions of a fixed held-out artifact"
        ),
        "seed_roles": {
            "0": "development_ablation",
            "1-4": "post_freeze_repeated_partition_evaluation",
        },
        "formal_confirmatory_seeds": [1, 2, 3, 4],
        "run_status_path": str(args.run_status),
        "expected_runs": args.expected_runs,
        "recorded_runs": len(status_rows),
        "successful_runs": len(rows),
        "failed_runs": len(failed_status),
        "complete": len(status_rows) == args.expected_runs and not failed_status,
        "selected_runs": len(selected_rows),
        "no_safe_runs": sum(row["outcome"] == "NO_SAFE" for row in rows),
        "total_encrypted_trials": sum(int(row["trials_used"]) for row in rows),
        "total_encrypted_key_runs": sum(
            int(row["key_repeats_completed"])
            for row in trial_rows
        ),
        "encrypted_trial_status_counts": dict(
            sorted(Counter(row["status"] for row in trial_rows).items())
        ),
        "repaired_runs": sum(int(row["trials_used"]) > 1 for row in rows),
        "initial_rejected_runs": sum(
            row["trial_index"] == 1 and row["status"] == "REJECTED"
            for row in trial_rows
        ),
        "mean_encrypted_trials_per_successful_run": mean_or_none(
            [int(row["trials_used"]) for row in rows]
        ),
        "max_encrypted_trials": max(
            (int(row["trials_used"]) for row in rows),
            default=None,
        ),
        "zero_flip_selected_runs": sum(
            int(row["decision_flips"]) == 0 for row in selected_rows
        ),
        "zero_violation_selected_runs": sum(
            int(row["error_violations"]) == 0 for row in selected_rows
        ),
        "require_source_replay": args.require_source_replay,
        "source_replay_verified_runs": sum(
            row["source_replay_verified"] is True for row in rows
        ),
        "source_feature_space_counts": dict(
            sorted(
                Counter(
                    str(row["source_feature_space"])
                    for row in rows
                    if row["source_feature_space"]
                ).items()
            )
        ),
        "preprocessing_method_counts": dict(
            sorted(
                Counter(
                    str(row["preprocessing_method"])
                    for row in rows
                    if row["preprocessing_method"]
                ).items()
            )
        ),
        "by_model": {
            model_id: {
                "selected_runs": len(grouped_trials[model_id]),
                "mean_encrypted_trials": mean_or_none(grouped_trials[model_id]),
                "mean_of_workload_mean_latency_ms": mean_or_none(
                    grouped_latency[model_id]
                ),
            }
            for model_id in sorted(grouped_trials)
        },
        "failed_tags": [row["tag"] for row in failed_status],
    }
    summary_path = args.output_root / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        "direct_autotune_summary="
        f"{'COMPLETE' if summary['complete'] else 'CHECKPOINT'} "
        f"recorded={summary['recorded_runs']}/{summary['expected_runs']} "
        f"selected={summary['selected_runs']} "
        f"no_safe={summary['no_safe_runs']} "
        f"failed={summary['failed_runs']} "
        f"trials={summary['total_encrypted_trials']} "
        f"key_runs={summary['total_encrypted_key_runs']}"
    )
    print(f"workload_results={trials_path}")
    print(f"encrypted_trials={encrypted_trials_path}")
    print(f"summary_json={summary_path}")
    if failed_status:
        print(
            "ERROR: direct autotune matrix contains failed workloads: "
            + ",".join(row["tag"] for row in failed_status)
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
