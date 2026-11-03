#!/usr/bin/env python3
"""Analyze alpha and margin-floor sensitivity on the frozen 5-split study."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
import math
import os
import statistics
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SPLIT_ROOT = Path(
    "results/thesis_grade_protocol/tabular_splits_v1"
)
CERTIFICATES = Path(
    "results/thesis_grade_protocol/tabular_validation_oracle_v1/"
    "full/summary/candidate_certificates.csv"
)
ORACLE_SELECTION = Path(
    "results/thesis_grade_protocol/tabular_validation_oracle_v1/"
    "full/summary/oracle_selection.csv"
)
DEFAULT_OUTPUT = Path(
    "results/thesis_grade_protocol/policy_sensitivity_v1/full"
)
ALPHAS = (0.1, 0.25, 0.5, 0.75, 0.9)
MARGIN_FLOORS = (
    0.0,
    1e-5,
    1e-4,
    5e-4,
    1e-3,
    2e-3,
    5e-3,
    1e-2,
    5e-2,
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
PARTITIONS = (
    "configuration_validation",
    "locked_audit_test",
)
SOURCE_FILES = (
    Path("cmd/flipguard-synthesize/main.go"),
    Path("internal/ckksplanner/contract.go"),
    Path("internal/ckksplanner/synthesis.go"),
    Path("internal/ckksplanner/tabular_contract.go"),
    Path("scripts/analyze_thesis_policy_sensitivity.py"),
    Path("go.mod"),
    Path("go.sum"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def source_bindings() -> dict[str, dict[str, Any]]:
    return {
        str(path): {
            "bytes": (REPO_ROOT / path).stat().st_size,
            "sha256": sha256_path(REPO_ROOT / path),
        }
        for path in SOURCE_FILES
    }


def source_digest(files: dict[str, dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for path, item in sorted(files.items()):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(item["sha256"].encode("ascii"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def build_binary(binary: Path) -> None:
    binary.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["GOCACHE"] = (
        "/tmp/flipguard-policy-sensitivity-gocache"
    )
    subprocess.run(
        [
            "go",
            "build",
            "-o",
            str(binary),
            "./cmd/flipguard-synthesize",
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=True,
    )


def task_identity(
    partition: str,
    seed: int,
    dataset: str,
    model: str,
    alpha: float,
    margin_floor: float,
) -> tuple[Any, ...]:
    return (
        partition,
        seed,
        dataset,
        model,
        alpha,
        margin_floor,
    )


def run_synthesis_task(
    binary: Path,
    task: tuple[Any, ...],
) -> dict[str, Any]:
    (
        partition,
        seed,
        dataset,
        model,
        alpha,
        margin_floor,
    ) = task
    model_path = Path(
        f"datasets/tabular_suite/{dataset}/{model}/model.json"
    )
    validation_path = (
        SPLIT_ROOT
        / f"split_seed_{seed}"
        / dataset
        / model
        / f"{partition}.csv"
    )
    split_id = (
        f"split_seed_{seed}/policy_sensitivity/{partition}"
    )
    command = [
        str(binary),
        "--model",
        str(model_path),
        "--validation",
        str(validation_path),
        "--split-id",
        split_id,
        "--margin-floor",
        format(margin_floor, ".12g"),
        "--safety-factor",
        format(alpha, ".12g"),
        "--max-encrypted-trials",
        "3",
        "--key-repeats",
        "3",
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
    base = {
        "partition": partition,
        "split_seed": seed,
        "dataset_id": dataset,
        "model_id": model,
        "alpha": format(alpha, ".12g"),
        "margin_floor": format(margin_floor, ".12g"),
        "status": "",
        "failure_class": "",
        "failure": "",
        "validation_samples": "",
        "v_cert": "",
        "v_amb": "",
        "coverage": "",
        "protected_margin": "",
        "output_error_budget": "",
        "candidate_id": "",
        "log_n": "",
        "q_prime_count": "",
        "p_prime_count": "",
        "log_default_scale": "",
        "declared_log_qp": "",
        "security_headroom_bits": "",
        "precision_target_bits": "",
        "analysis_scale_bits": "",
        "backend_scale_lift_bits": "",
    }
    if completed.returncode != 0:
        message = completed.stderr.strip()
        base["status"] = "INFEASIBLE"
        if "no certifiable sample above margin floor" in message:
            base["failure_class"] = "NO_CERTIFIABLE_SAMPLE"
        elif "security" in message.lower():
            base["failure_class"] = "SECURITY_ENVELOPE"
        else:
            base["failure_class"] = "UNEXPECTED"
        base["failure"] = message
        return base

    plan = json.loads(completed.stdout)
    contract = plan["contract"]
    decision = contract["decision"]
    candidate = plan["initial_candidates"][0]
    parameters = candidate["parameters"]
    security = candidate["security"]
    samples = int(decision["validation_samples"])
    v_cert = int(decision["certifiable_samples"])
    base.update(
        {
            "status": "PLAN_OK",
            "validation_samples": samples,
            "v_cert": v_cert,
            "v_amb": int(decision["ambiguous_samples"]),
            "coverage": v_cert / samples,
            "protected_margin": decision["protected_margin"],
            "output_error_budget": decision[
                "output_error_budget"
            ],
            "candidate_id": candidate["id"],
            "log_n": parameters["log_n"],
            "q_prime_count": len(parameters["log_q"]),
            "p_prime_count": len(parameters["log_p"]),
            "log_default_scale": parameters[
                "log_default_scale"
            ],
            "declared_log_qp": security["declared_log_qp"],
            "security_headroom_bits": security["headroom_bits"],
            "precision_target_bits": candidate[
                "precision_target_bits"
            ],
            "analysis_scale_bits": candidate[
                "analysis_scale_bits"
            ],
            "backend_scale_lift_bits": candidate[
                "backend_scale_lift_bits"
            ],
        }
    )
    return base


def aggregate_plan_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[
        tuple[str, str, str],
        list[dict[str, Any]],
    ] = {}
    for row in rows:
        key = (
            str(row["partition"]),
            str(row["alpha"]),
            str(row["margin_floor"]),
        )
        grouped.setdefault(key, []).append(row)

    output = []
    for key, group in sorted(
        grouped.items(),
        key=lambda item: (
            item[0][0],
            float(item[0][1]),
            float(item[0][2]),
        ),
    ):
        valid = [row for row in group if row["status"] == "PLAN_OK"]
        coverage = [float(row["coverage"]) for row in valid]
        total_samples = sum(
            int(row["validation_samples"]) for row in valid
        )
        total_v_cert = sum(int(row["v_cert"]) for row in valid)
        signatures = Counter(
            (
                int(row["log_n"]),
                int(row["q_prime_count"]),
                int(row["log_default_scale"]),
            )
            for row in valid
        )
        output.append(
            {
                "partition": key[0],
                "alpha": key[1],
                "margin_floor": key[2],
                "workloads": len(group),
                "plan_ok": len(valid),
                "infeasible": len(group) - len(valid),
                "no_certifiable_sample": sum(
                    row["failure_class"]
                    == "NO_CERTIFIABLE_SAMPLE"
                    for row in group
                ),
                "unexpected_failures": sum(
                    row["failure_class"] == "UNEXPECTED"
                    for row in group
                ),
                "total_samples_in_plan_ok": total_samples,
                "total_v_cert": total_v_cert,
                "total_v_amb": total_samples - total_v_cert,
                "aggregate_coverage": (
                    total_v_cert / total_samples
                    if total_samples
                    else ""
                ),
                "min_workload_coverage": (
                    min(coverage) if coverage else ""
                ),
                "median_workload_coverage": (
                    statistics.median(coverage)
                    if coverage
                    else ""
                ),
                "candidate_signatures": json.dumps(
                    {
                        f"N{signature[0]}_Q{signature[1]}_S"
                        f"{signature[2]}": count
                        for signature, count in sorted(
                            signatures.items()
                        )
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            }
        )
    return output


def alpha_certificate_rows() -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
]:
    certificates = read_csv(REPO_ROOT / CERTIFICATES)
    oracles = read_csv(REPO_ROOT / ORACLE_SELECTION)
    output = []
    status_vectors: dict[
        tuple[int, str, str, str],
        list[str],
    ] = {}
    oracle_vectors: dict[
        tuple[int, str, str],
        list[str],
    ] = {}
    for alpha in ALPHAS:
        raw = format(alpha, ".12g")
        candidate_rows = [
            row for row in certificates if row["alpha"] == raw
        ]
        oracle_rows = [
            row for row in oracles if row["alpha"] == raw
        ]
        statuses = Counter(
            row["certificate_status"] for row in candidate_rows
        )
        outcomes = Counter(row["outcome"] for row in oracle_rows)
        output.append(
            {
                "alpha": raw,
                "candidate_rows": len(candidate_rows),
                "safe": statuses["SAFE"],
                "rejected": statuses["REJECTED"],
                "failed": statuses["FAILED"],
                "oracle_rows": len(oracle_rows),
                "oracle_selected": outcomes["SELECTED"],
                "oracle_no_safe": outcomes["NO_SAFE"],
            }
        )
        for row in candidate_rows:
            key = (
                int(row["split_seed"]),
                row["dataset_id"],
                row["model_id"],
                row["candidate_id"],
            )
            status_vectors.setdefault(key, []).append(
                row["certificate_status"]
            )
        for row in oracle_rows:
            key = (
                int(row["split_seed"]),
                row["dataset_id"],
                row["model_id"],
            )
            oracle_vectors.setdefault(key, []).append(
                row["oracle_candidate"]
            )

    state_changes = sum(
        len(set(vector)) > 1 for vector in status_vectors.values()
    )
    oracle_changes = sum(
        len(set(vector)) > 1 for vector in oracle_vectors.values()
    )
    diagnostics = {
        "alpha_grid": list(ALPHAS),
        "candidate_identities": len(status_vectors),
        "workloads": len(oracle_vectors),
        "candidate_state_changes_across_alpha": state_changes,
        "oracle_candidate_changes_across_alpha": oracle_changes,
        "status_invariant_across_grid": state_changes == 0,
        "oracle_invariant_across_grid": oracle_changes == 0,
    }
    return output, diagnostics


def verify_outputs(output_root: Path) -> None:
    summary_path = output_root / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    for item in summary["outputs"].values():
        path = REPO_ROOT / item["path"]
        if sha256_path(path) != item["sha256"]:
            raise ValueError(f"{path}: output digest changed")
    for item in summary["inputs"].values():
        path = REPO_ROOT / item["path"]
        if sha256_path(path) != item["sha256"]:
            raise ValueError(f"{path}: input digest changed")
    for relative, item in summary["source"]["files"].items():
        path = REPO_ROOT / relative
        if (
            path.stat().st_size != item["bytes"]
            or sha256_path(path) != item["sha256"]
        ):
            raise ValueError(f"{path}: source digest changed")
    if (
        summary["alpha_certificate_diagnostics"][
            "candidate_state_changes_across_alpha"
        ]
        != 0
        or summary["alpha_certificate_diagnostics"][
            "oracle_candidate_changes_across_alpha"
        ]
        != 0
        or summary["counts"]["unexpected_failures"] != 0
    ):
        raise ValueError("policy sensitivity invariants failed")
    print(
        "policy_sensitivity=VERIFIED "
        f"plans={summary['counts']['plan_rows']} "
        f"aggregates={summary['counts']['aggregate_rows']}"
    )


def main() -> int:
    args = parse_args()
    output_root = (REPO_ROOT / args.output_root).resolve()
    if args.verify:
        verify_outputs(output_root)
        return 0
    if args.workers <= 0:
        raise ValueError("--workers must be positive")
    if output_root.exists() and not args.force:
        raise ValueError(f"{output_root} exists; use --force")
    output_root.mkdir(parents=True, exist_ok=True)

    binary = output_root / "bin/flipguard-synthesize"
    build_binary(binary)
    tasks = [
        task_identity(
            partition,
            seed,
            dataset,
            model,
            alpha,
            margin_floor,
        )
        for partition in PARTITIONS
        for seed in range(5)
        for dataset in DATASETS
        for model in MODELS
        for alpha in ALPHAS
        for margin_floor in MARGIN_FLOORS
    ]
    rows: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=args.workers
    ) as executor:
        futures = [
            executor.submit(run_synthesis_task, binary, task)
            for task in tasks
        ]
        for index, future in enumerate(
            concurrent.futures.as_completed(futures),
            start=1,
        ):
            rows.append(future.result())
            if index % 250 == 0 or index == len(futures):
                print(
                    f"policy_sensitivity_progress="
                    f"{index}/{len(futures)}"
                )
    rows.sort(
        key=lambda row: (
            row["partition"],
            int(row["split_seed"]),
            row["dataset_id"],
            row["model_id"],
            float(row["alpha"]),
            float(row["margin_floor"]),
        )
    )
    plan_fields = list(rows[0])
    plans_path = output_root / "synthesis_plans.csv"
    write_csv(plans_path, plan_fields, rows)

    aggregate = aggregate_plan_rows(rows)
    aggregate_path = output_root / "synthesis_aggregate.csv"
    write_csv(aggregate_path, list(aggregate[0]), aggregate)

    alpha_rows, alpha_diagnostics = alpha_certificate_rows()
    alpha_path = output_root / "alpha_certificate_sensitivity.csv"
    write_csv(alpha_path, list(alpha_rows[0]), alpha_rows)

    default_rows = [
        row
        for row in aggregate
        if math.isclose(float(row["alpha"]), 0.5)
        and math.isclose(float(row["margin_floor"]), 0.001)
    ]
    files = source_bindings()
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    input_paths = {
        "split_summary": REPO_ROOT / SPLIT_ROOT / "summary.json",
        "candidate_certificates": REPO_ROOT / CERTIFICATES,
        "oracle_selection": REPO_ROOT / ORACLE_SELECTION,
    }
    unexpected = sum(
        row["failure_class"] == "UNEXPECTED" for row in rows
    )
    summary = {
        "schema_version": 1,
        "status": "COMPLETE",
        "claim_boundary": (
            "The alpha result is empirical invariance on the tested grid, "
            "not proof that alpha=0.5 is theoretically optimal. Margin-floor "
            "results quantify coverage and static proposal changes; they do "
            "not recertify encrypted candidates at every floor."
        ),
        "protocol": {
            "alphas": list(ALPHAS),
            "margin_floors": list(MARGIN_FLOORS),
            "partitions": list(PARTITIONS),
            "split_seeds": list(range(5)),
            "datasets": list(DATASETS),
            "models": list(MODELS),
            "synthesis_policy": {
                "min_scale_bits": 18,
                "min_prime_bits": 18,
                "special_prime_bits": 30,
                "precision_slack_mode": "none",
                "max_encrypted_trials": 4,
                "key_repeats_contract": 3,
            },
        },
        "counts": {
            "plan_rows": len(rows),
            "plan_ok": sum(
                row["status"] == "PLAN_OK" for row in rows
            ),
            "infeasible": sum(
                row["status"] == "INFEASIBLE" for row in rows
            ),
            "no_certifiable_sample": sum(
                row["failure_class"] == "NO_CERTIFIABLE_SAMPLE"
                for row in rows
            ),
            "unexpected_failures": unexpected,
            "aggregate_rows": len(aggregate),
        },
        "default_policy_aggregate": default_rows,
        "alpha_certificate_diagnostics": alpha_diagnostics,
        "inputs": {
            name: {
                "path": str(path.relative_to(REPO_ROOT)),
                "sha256": sha256_path(path),
            }
            for name, path in input_paths.items()
        },
        "source": {
            "commit": commit,
            "digest": source_digest(files),
            "files": files,
        },
        "outputs": {
            "synthesis_plans": {
                "path": str(plans_path.relative_to(REPO_ROOT)),
                "sha256": sha256_path(plans_path),
            },
            "synthesis_aggregate": {
                "path": str(
                    aggregate_path.relative_to(REPO_ROOT)
                ),
                "sha256": sha256_path(aggregate_path),
            },
            "alpha_certificate_sensitivity": {
                "path": str(alpha_path.relative_to(REPO_ROOT)),
                "sha256": sha256_path(alpha_path),
            },
        },
    }
    write_json(output_root / "summary.json", summary)
    verify_outputs(output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
