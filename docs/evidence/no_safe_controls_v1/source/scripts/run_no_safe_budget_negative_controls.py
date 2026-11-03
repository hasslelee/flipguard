#!/usr/bin/env python3
"""Run a disjoint-partition budgeted-NO_SAFE negative control."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SPLIT_ROOT = Path(
    "results/thesis_grade_protocol/tabular_splits_v1"
)
DATASETS = (
    "banknote",
    "digits_binary",
    "iris_binary",
    "mnist_pool16",
    "wdbc",
)
MODELS = (
    "linear_poly3",
    "mlp_square_linear_score",
)
SOURCE_FILES = (
    Path("cmd/flipguard-autotune/main.go"),
    Path("internal/ckksplanner/contract.go"),
    Path("internal/ckksplanner/executor.go"),
    Path("internal/ckksplanner/synthesis.go"),
    Path("internal/ckksplanner/tabular_contract.go"),
    Path("scripts/run_no_safe_budget_negative_controls.py"),
    Path("go.mod"),
    Path("go.sum"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run direct autotune with one encrypted trial on disjoint "
            "locked-audit partitions."
        )
    )
    parser.add_argument(
        "--mode",
        choices=("pilot", "confirm"),
        default="pilot",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_csv(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def source_state() -> tuple[str, str, bool, dict[str, Any]]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        [
            "git",
            "status",
            "--porcelain",
            "--",
            *[str(path) for path in SOURCE_FILES],
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    files = {
        str(path): {
            "sha256": sha256_path(REPO_ROOT / path),
            "bytes": (REPO_ROOT / path).stat().st_size,
        }
        for path in SOURCE_FILES
    }
    digest = hashlib.sha256()
    for path, binding in sorted(files.items()):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(binding["sha256"].encode("ascii"))
        digest.update(b"\n")
    return (
        commit,
        "sha256:" + digest.hexdigest(),
        bool(status),
        files,
    )


def build_binary(binary: Path) -> None:
    binary.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["GOCACHE"] = (
        "/tmp/flipguard-no-safe-control-gocache"
    )
    subprocess.run(
        [
            "go",
            "build",
            "-o",
            str(binary),
            "./cmd/flipguard-autotune",
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=True,
    )


def workload_paths(
    seed: int,
    dataset: str,
    model: str,
) -> tuple[Path, Path]:
    model_path = Path(
        f"datasets/tabular_suite/{dataset}/{model}/model.json"
    )
    validation_path = (
        SPLIT_ROOT
        / f"split_seed_{seed}"
        / dataset
        / model
        / "locked_audit_test.csv"
    )
    return model_path, validation_path


def expected_outcome(dataset: str, model: str) -> str:
    if model == "mlp_square_linear_score":
        return "SELECTED"
    if model == "linear_poly3" and dataset == "iris_binary":
        return "SELECTED"
    return "NO_SAFE"


def validate_result(
    result_path: Path,
    binding_path: Path,
    seed: int,
    dataset: str,
    model: str,
    model_path: Path,
    validation_path: Path,
    source_digest: str,
    key_repeats: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    binding = json.loads(binding_path.read_text(encoding="utf-8"))

    if binding["source_digest"] != source_digest:
        raise ValueError(f"{binding_path}: source digest changed")
    if binding["result"]["sha256"] != sha256_path(result_path):
        raise ValueError(f"{binding_path}: result digest changed")
    if binding["model"]["sha256"] != sha256_path(model_path):
        raise ValueError(f"{binding_path}: model digest changed")
    if binding["validation"]["sha256"] != sha256_path(
        validation_path
    ):
        raise ValueError(
            f"{binding_path}: validation digest changed"
        )

    plan = result["plan"]
    contract = plan["contract"]
    expected_workload = (
        f"split_seed_{seed}/no_safe_budget_control/"
        f"{dataset}/{model}"
    )
    if contract["workload_id"] != expected_workload:
        raise ValueError(
            f"{result_path}: workload identity mismatch"
        )
    if contract["model_artifact"]["path"] != str(model_path):
        raise ValueError(f"{result_path}: model path mismatch")
    if contract["validation_data"]["path"] != str(
        validation_path
    ):
        raise ValueError(f"{result_path}: validation path mismatch")
    if (
        contract["deployment"]["max_encrypted_trials"] != 1
        or contract["deployment"]["validation_key_repeats"]
        != key_repeats
    ):
        raise ValueError(
            f"{result_path}: negative-control budget mismatch"
        )
    policy = plan["policy"]
    if (
        policy["min_scale_bits"] != 18
        or policy["min_prime_bits"] != 18
        or policy["special_prime_bits"] != 30
    ):
        raise ValueError(
            f"{result_path}: synthesis policy mismatch"
        )

    trials = result["trials"]
    if result["trials_used"] != 1 or len(trials) != 1:
        raise ValueError(
            f"{result_path}: expected exactly one trial"
        )
    trial = trials[0]
    outcome = result["outcome"]
    selected = result.get("selected")
    if outcome == "SELECTED":
        if selected is None:
            raise ValueError(
                f"{result_path}: SELECTED has no candidate"
            )
        if trial["status"] != "SAFE":
            raise ValueError(
                f"{result_path}: selected trial is not SAFE"
            )
        if trial["candidate"] != selected:
            raise ValueError(
                f"{result_path}: selected candidate/trial mismatch"
            )
        if (
            trial["decision_flips"] != 0
            or trial["error_violations"] != 0
        ):
            raise ValueError(
                f"{result_path}: unsafe evidence was selected"
            )
    elif outcome == "NO_SAFE":
        if selected is not None:
            raise ValueError(
                f"{result_path}: NO_SAFE contains a selection"
            )
        if trial["status"] == "SAFE":
            raise ValueError(
                f"{result_path}: NO_SAFE ended on SAFE"
            )
    else:
        raise ValueError(
            f"{result_path}: unsupported outcome {outcome!r}"
        )

    return result, binding


def execute_workload(
    binary: Path,
    output_root: Path,
    seed: int,
    dataset: str,
    model: str,
    source_commit: str,
    source_digest: str,
    key_repeats: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    model_path, validation_path = workload_paths(
        seed,
        dataset,
        model,
    )
    tag = f"seed{seed}_{dataset}_{model}"
    result_path = output_root / "results" / f"{tag}.json"
    binding_path = output_root / "bindings" / f"{tag}.json"
    log_path = output_root / "logs" / f"{tag}.log"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    binding_path.parent.mkdir(parents=True, exist_ok=True)
    split_id = (
        f"split_seed_{seed}/no_safe_budget_control"
    )

    command = [
        str(binary),
        "--model",
        str(model_path),
        "--validation",
        str(validation_path),
        "--split-id",
        split_id,
        "--out",
        str(result_path),
        "--margin-floor",
        "0.001",
        "--safety-factor",
        "0.5",
        "--max-encrypted-trials",
        "1",
        "--key-repeats",
        str(key_repeats),
        "--min-scale-bits",
        "18",
        "--min-prime-bits",
        "18",
        "--special-prime-bits",
        "30",
        "--precision-slack-mode",
        "none",
    ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "$ " + " ".join(command) + "\n"
        + completed.stdout
        + completed.stderr,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed with exit code "
            f"{completed.returncode}; see {log_path}"
        )

    write_json(
        binding_path,
        {
            "schema_version": 1,
            "source_commit": source_commit,
            "source_digest": source_digest,
            "key_repeats": key_repeats,
            "result": {
                "path": str(result_path.relative_to(REPO_ROOT)),
                "sha256": sha256_path(result_path),
            },
            "model": {
                "path": str(model_path),
                "sha256": sha256_path(model_path),
            },
            "validation": {
                "path": str(validation_path),
                "sha256": sha256_path(validation_path),
            },
        },
    )
    return validate_result(
        result_path,
        binding_path,
        seed,
        dataset,
        model,
        model_path,
        validation_path,
        source_digest,
        key_repeats,
    )


def main() -> int:
    args = parse_args()
    output_root = (REPO_ROOT / args.output_root).resolve()
    binary = output_root / "bin" / "flipguard-autotune"
    seeds = (0,) if args.mode == "pilot" else (1, 2, 3, 4)
    key_repeats = 1 if args.mode == "pilot" else 3

    (
        source_commit,
        source_digest,
        source_dirty,
        source_files,
    ) = source_state()
    if args.mode == "confirm" and source_dirty:
        raise ValueError(
            "confirm mode requires clean committed control source"
        )
    build_binary(binary)

    statuses: list[dict[str, Any]] = []
    workload_rows: list[dict[str, Any]] = []
    failures = 0
    for seed in seeds:
        for dataset in DATASETS:
            for model in MODELS:
                tag = f"seed{seed}_{dataset}_{model}"
                result_path = (
                    output_root / "results" / f"{tag}.json"
                )
                binding_path = (
                    output_root / "bindings" / f"{tag}.json"
                )
                action = "run"
                try:
                    model_path, validation_path = workload_paths(
                        seed,
                        dataset,
                        model,
                    )
                    if (
                        result_path.exists()
                        and binding_path.exists()
                        and not args.force
                    ):
                        result, binding = validate_result(
                            result_path,
                            binding_path,
                            seed,
                            dataset,
                            model,
                            model_path,
                            validation_path,
                            source_digest,
                            key_repeats,
                        )
                        action = "skip"
                    else:
                        result, binding = execute_workload(
                            binary,
                            output_root,
                            seed,
                            dataset,
                            model,
                            source_commit,
                            source_digest,
                            key_repeats,
                        )

                    trial = result["trials"][0]
                    workload_rows.append(
                        {
                            "split_seed": seed,
                            "dataset_id": dataset,
                            "model_id": model,
                            "expected_outcome": expected_outcome(
                                dataset,
                                model,
                            ),
                            "outcome": result["outcome"],
                            "trial_status": trial["status"],
                            "failure_signal": trial.get(
                                "failure_signal",
                                "",
                            ),
                            "decision_flips": trial[
                                "decision_flips"
                            ],
                            "error_violations": trial[
                                "error_violations"
                            ],
                            "max_observed_error": trial[
                                "max_observed_error"
                            ],
                            "v_cert": trial["v_cert"],
                            "v_amb": trial["v_amb"],
                            "candidate_id": trial["candidate"][
                                "id"
                            ],
                            "log_n": trial["candidate"][
                                "parameters"
                            ]["log_n"],
                            "q_prime_count": len(
                                trial["candidate"]["parameters"][
                                    "log_q"
                                ]
                            ),
                            "log_default_scale": trial[
                                "candidate"
                            ]["parameters"][
                                "log_default_scale"
                            ],
                            "result_path": str(
                                result_path.relative_to(REPO_ROOT)
                            ),
                            "result_sha256": binding["result"][
                                "sha256"
                            ],
                        }
                    )
                    statuses.append(
                        {
                            "split_seed": seed,
                            "dataset_id": dataset,
                            "model_id": model,
                            "status": "ok",
                            "action": action,
                            "error": "",
                        }
                    )
                    if not args.quiet:
                        print(
                            f"{action} seed{seed}/{dataset}/{model} "
                            f"outcome={result['outcome']} "
                            f"status={trial['status']}"
                        )
                except Exception as error:
                    failures += 1
                    statuses.append(
                        {
                            "split_seed": seed,
                            "dataset_id": dataset,
                            "model_id": model,
                            "status": "failed",
                            "action": action,
                            "error": str(error),
                        }
                    )
                    print(
                        f"FAIL seed{seed}/{dataset}/{model}: {error}",
                        file=sys.stderr,
                    )

    summary_root = output_root / "summary"
    write_csv(
        summary_root / "run_status.csv",
        [
            "split_seed",
            "dataset_id",
            "model_id",
            "status",
            "action",
            "error",
        ],
        statuses,
    )
    workload_fields = list(workload_rows[0]) if workload_rows else []
    write_csv(
        summary_root / "workload_results.csv",
        workload_fields,
        workload_rows,
    )

    outcome_counts: dict[str, int] = {}
    model_outcomes: dict[str, dict[str, int]] = {}
    for row in workload_rows:
        outcome = str(row["outcome"])
        outcome_counts[outcome] = (
            outcome_counts.get(outcome, 0) + 1
        )
        model_counts = model_outcomes.setdefault(
            str(row["model_id"]),
            {},
        )
        model_counts[outcome] = model_counts.get(outcome, 0) + 1

    unsafe_selected = sum(
        row["outcome"] == "SELECTED"
        and (
            int(row["decision_flips"]) != 0
            or int(row["error_violations"]) != 0
        )
        for row in workload_rows
    )
    no_safe_with_selection = 0
    no_safe_non_linear = sum(
        row["outcome"] == "NO_SAFE"
        and row["model_id"] != "linear_poly3"
        for row in workload_rows
    )
    unexpected_outcomes = sum(
        row["outcome"] != row["expected_outcome"]
        for row in workload_rows
    )
    expected_workloads = len(seeds) * len(DATASETS) * len(MODELS)
    control_pass = (
        failures == 0
        and len(workload_rows) == expected_workloads
        and outcome_counts.get("NO_SAFE", 0) > 0
        and outcome_counts.get("SELECTED", 0) > 0
        and unsafe_selected == 0
        and no_safe_with_selection == 0
        and no_safe_non_linear == 0
        and unexpected_outcomes == 0
    )

    summary = {
        "schema_version": 1,
        "mode": args.mode.upper(),
        "evidence_status": (
            "PILOT_ONLY"
            if args.mode == "pilot"
            else "CONFIRMATORY_NEGATIVE_CONTROL"
        ),
        "control_result": "PASS" if control_pass else "FAIL",
        "claim_boundary": (
            "This is a budgeted abstention control. NO_SAFE means no SAFE "
            "candidate was admitted within one encrypted trial; it does not "
            "mean no CKKS configuration exists globally."
        ),
        "protocol": {
            "partition": "disjoint_locked_audit_test",
            "split_seeds": list(seeds),
            "datasets": list(DATASETS),
            "models": list(MODELS),
            "max_encrypted_trials": 1,
            "key_repeats": key_repeats,
            "min_scale_bits": 18,
            "min_prime_bits": 18,
            "special_prime_bits": 30,
            "margin_floor": 0.001,
            "safety_factor": 0.5,
        },
        "counts": {
            "expected_workloads": expected_workloads,
            "successful_workloads": len(workload_rows),
            "failed_workloads": failures,
            "outcomes": outcome_counts,
            "outcomes_by_model": model_outcomes,
            "unsafe_selected": unsafe_selected,
            "no_safe_with_selection": no_safe_with_selection,
            "no_safe_non_linear": no_safe_non_linear,
            "unexpected_outcomes": unexpected_outcomes,
        },
        "falsification": {
            "requires_both_selected_and_no_safe": True,
            "forbid_unsafe_selected": True,
            "forbid_selected_payload_on_no_safe": True,
            "no_safe_expected_only_for_linear_control": True,
            "expected_outcome_map": {
                "non_iris_linear_poly3": "NO_SAFE",
                "iris_binary_linear_poly3": "SELECTED",
                "mlp_square_linear_score": "SELECTED",
            },
        },
        "source": {
            "commit": source_commit,
            "dirty": source_dirty,
            "digest": source_digest,
            "files": source_files,
        },
        "outputs": {
            "run_status": {
                "path": str(
                    (summary_root / "run_status.csv").relative_to(
                        REPO_ROOT
                    )
                ),
                "sha256": sha256_path(
                    summary_root / "run_status.csv"
                ),
            },
            "workload_results": {
                "path": str(
                    (
                        summary_root / "workload_results.csv"
                    ).relative_to(REPO_ROOT)
                ),
                "sha256": sha256_path(
                    summary_root / "workload_results.csv"
                ),
            },
        },
    }
    write_json(summary_root / "summary.json", summary)
    print(
        f"no_safe_control={summary['control_result']} "
        f"mode={args.mode} workloads={len(workload_rows)}/"
        f"{expected_workloads} outcomes={outcome_counts}"
    )
    print(f"summary={summary_root / 'summary.json'}")
    return 0 if control_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
