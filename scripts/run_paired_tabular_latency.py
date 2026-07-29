#!/usr/bin/env python3
"""Run and summarize the paired selected-literal latency protocol."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import random
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COMPARISON = Path(
    "results/thesis_grade_protocol/direct_vs_catalog_oracle_v1/full/"
    "comparison.csv"
)
DEFAULT_DIRECT_RESULTS = Path(
    "results/thesis_grade_protocol/direct_tabular_autotune_v1/"
    "full_floor18_keys3/summary/workload_results.csv"
)
MEASUREMENT_SOURCE_FILES = (
    Path("cmd/flipguard-paired-latency/main.go"),
    Path("internal/ckksbackend/paired_tabular_latency.go"),
    Path("internal/ckksbackend/tabular_inference.go"),
    Path("scripts/run_paired_tabular_latency.py"),
    Path("go.mod"),
    Path("go.sum"),
)
BOOTSTRAP_SEED = 20260728
BOOTSTRAP_REPLICATES = 10_000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run direct/catalog/reference literals in a within-workload "
            "paired schedule."
        )
    )
    parser.add_argument(
        "--comparison",
        type=Path,
        default=DEFAULT_COMPARISON,
    )
    parser.add_argument(
        "--direct-results",
        type=Path,
        default=DEFAULT_DIRECT_RESULTS,
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--mode",
        choices=("pilot", "final"),
        default="pilot",
    )
    parser.add_argument("--warmup-runs", type=int, default=1)
    parser.add_argument("--measurement-runs", type=int, default=3)
    parser.add_argument("--max-rows", type=int, default=4)
    parser.add_argument(
        "--max-workloads",
        type=int,
        default=0,
        help="zero runs every workload",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.5,
    )
    parser.add_argument(
        "--binary",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="rerun valid existing workload results",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
    )
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
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def read_text_if_present(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, PermissionError, OSError):
        return ""


def host_metadata() -> dict[str, Any]:
    cpu_model = ""
    cpu_info = read_text_if_present(Path("/proc/cpuinfo"))
    for line in cpu_info.splitlines():
        if line.lower().startswith("model name"):
            cpu_model = line.split(":", 1)[-1].strip()
            break

    governors = sorted(
        {
            value
            for path in Path("/sys/devices/system/cpu").glob(
                "cpu*/cpufreq/scaling_governor"
            )
            if (value := read_text_if_present(path))
        }
    )
    affinity = (
        sorted(os.sched_getaffinity(0))
        if hasattr(os, "sched_getaffinity")
        else []
    )
    return {
        "platform": platform.platform(),
        "uname": " ".join(platform.uname()),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_model": cpu_model,
        "logical_cpu": os.cpu_count(),
        "process_cpu_affinity": affinity,
        "cpu_governors": governors,
        "dmi_system_vendor": read_text_if_present(
            Path("/sys/class/dmi/id/sys_vendor")
        ),
        "dmi_product_name": read_text_if_present(
            Path("/sys/class/dmi/id/product_name")
        ),
        "python": platform.python_version(),
        "gomaxprocs": os.environ.get("GOMAXPROCS", "runtime_default"),
    }


def run_text(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def measurement_source_bindings() -> dict[str, dict[str, Any]]:
    return {
        str(path): {
            "sha256": sha256_path(REPO_ROOT / path),
            "bytes": (REPO_ROOT / path).stat().st_size,
        }
        for path in MEASUREMENT_SOURCE_FILES
    }


def source_binding_digest(
    bindings: dict[str, dict[str, Any]],
) -> str:
    digest = hashlib.sha256()
    for path, binding in sorted(bindings.items()):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(binding["sha256"].encode("ascii"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def source_state() -> tuple[
    str,
    str,
    bool,
    dict[str, dict[str, Any]],
    str,
]:
    commit = run_text(["git", "rev-parse", "HEAD"])
    status = run_text(
        [
            "git",
            "status",
            "--porcelain",
            "--",
            *[str(path) for path in MEASUREMENT_SOURCE_FILES],
        ]
    )
    dirty = bool(status)
    label = commit + ("+measurement-working-tree" if dirty else "")
    bindings = measurement_source_bindings()
    return (
        commit,
        label,
        dirty,
        bindings,
        source_binding_digest(bindings),
    )


def build_binary(binary: Path) -> None:
    binary.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["GOCACHE"] = "/tmp/flipguard-paired-latency-gocache"
    subprocess.run(
        [
            "go",
            "build",
            "-o",
            str(binary),
            "./cmd/flipguard-paired-latency",
        ],
        cwd=REPO_ROOT,
        env=env,
        check=True,
    )


def workload_key(row: dict[str, str]) -> tuple[int, str, str]:
    return (
        int(row["split_seed"]),
        row["dataset_id"],
        row["model_id"],
    )


def select_workloads(
    comparison_path: Path,
    alpha: float,
    max_workloads: int,
) -> list[dict[str, str]]:
    selected = [
        row
        for row in read_csv(comparison_path)
        if math.isclose(float(row["alpha"]), alpha)
    ]
    selected.sort(key=workload_key)
    keys = [workload_key(row) for row in selected]
    if len(keys) != len(set(keys)):
        raise ValueError("comparison contains duplicate workload rows")
    if max_workloads > 0:
        selected = selected[:max_workloads]
    if not selected:
        raise ValueError("no comparison workloads selected")
    return selected


def direct_result_index(path: Path) -> dict[tuple[int, str, str], Path]:
    output: dict[tuple[int, str, str], Path] = {}
    for row in read_csv(path):
        if row["status"] != "ok" or row["outcome"] != "SELECTED":
            continue
        key = workload_key(row)
        if key in output:
            raise ValueError(f"duplicate direct result for {key}")
        output[key] = Path(row["result_path"])
    return output


def result_path(
    output_root: Path,
    row: dict[str, str],
) -> Path:
    return (
        output_root
        / "results"
        / (
            f"seed{row['split_seed']}_{row['dataset_id']}_"
            f"{row['model_id']}.json"
        )
    )


def validate_existing_result(
    path: Path,
    row: dict[str, str],
    selection_path: Path,
    source_revision: str,
    source_digest: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        result = json.load(handle)
    expected_workload = (
        f"split_seed_{row['split_seed']}/"
        f"{row['dataset_id']}/{row['model_id']}"
    )
    checks = (
        (result["workload_id"], expected_workload, "workload ID"),
        (
            result["source_revision"],
            source_revision,
            "source revision",
        ),
        (
            result["source_digest"],
            source_digest,
            "source digest",
        ),
        (
            result["selection_result"]["path"],
            str(selection_path),
            "selection path",
        ),
        (
            result["selection_result"]["sha256"],
            sha256_path(selection_path),
            "selection digest",
        ),
        (
            result["catalog_candidate"],
            row["catalog_oracle_candidate"],
            "catalog candidate",
        ),
        (
            result["reference_candidate"],
            row["reference_candidate"],
            "reference candidate",
        ),
        (
            result["measurement"]["protocol"]["warmup_runs"],
            args.warmup_runs,
            "warm-up runs",
        ),
        (
            result["measurement"]["protocol"]["measurement_runs"],
            args.measurement_runs,
            "measurement runs",
        ),
        (
            result["measurement"]["protocol"]["requested_max_rows"],
            args.max_rows,
            "max rows",
        ),
    )
    for actual, expected, label in checks:
        if actual != expected:
            raise ValueError(
                f"{path}: {label} mismatch: {actual!r} != {expected!r}"
            )
    return result


def execute_workload(
    binary: Path,
    output_path: Path,
    log_path: Path,
    row: dict[str, str],
    selection_path: Path,
    source_revision: str,
    source_digest: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    command = [
        str(binary),
        "--selection-result",
        str(selection_path),
        "--catalog-candidate",
        row["catalog_oracle_candidate"],
        "--reference-candidate",
        row["reference_candidate"],
        "--out",
        str(output_path),
        "--source-revision",
        source_revision,
        "--source-digest",
        source_digest,
        "--warmup-runs",
        str(args.warmup_runs),
        "--measurement-runs",
        str(args.measurement_runs),
        "--max-rows",
        str(args.max_rows),
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
            f"paired latency command failed with exit code "
            f"{completed.returncode}; see {log_path}"
        )
    return validate_existing_result(
        output_path,
        row,
        selection_path,
        source_revision,
        source_digest,
        args,
    )


def flatten_result(
    row: dict[str, str],
    result: dict[str, Any],
    record_rows: list[dict[str, Any]],
    arm_rows: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
) -> None:
    identity = {
        "split_seed": row["split_seed"],
        "dataset_id": row["dataset_id"],
        "model_id": row["model_id"],
        "workload_id": result["workload_id"],
    }
    measurement = result["measurement"]
    for record in measurement["records"]:
        record_rows.append({**identity, **record})
    metadata = {
        item["id"]: item
        for item in measurement["arms"]
    }
    for summary in measurement["arm_summaries"]:
        arm_rows.append(
            {
                **identity,
                **metadata[summary["arm_id"]],
                **summary,
            }
        )
    for summary in measurement["pair_summaries"]:
        pair_rows.append({**identity, **summary})


def aggregate_pair_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (
            row["numerator_arm_id"],
            row["denominator_arm_id"],
        )
        grouped.setdefault(key, []).append(row)

    output = []
    for (numerator, denominator), group in sorted(grouped.items()):
        total_pairs = sum(int(row["pairs"]) for row in group)
        clusters: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in group:
            clusters[(row["dataset_id"], row["model_id"])].append(row)
        cluster_total_ratios = [
            geometric_mean(
                [
                    float(row["geometric_mean_total_ratio"])
                    for row in cluster
                ]
            )
            for _, cluster in sorted(clusters.items())
        ]
        cluster_eval_ratios = [
            geometric_mean(
                [
                    float(row["geometric_mean_eval_only_ratio"])
                    for row in cluster
                ]
            )
            for _, cluster in sorted(clusters.items())
        ]
        total_ratio = geometric_mean(cluster_total_ratios)
        eval_ratio = geometric_mean(cluster_eval_ratios)
        pair_seed = BOOTSTRAP_SEED + sum(
            ord(char) for char in numerator + "/" + denominator
        )
        total_ci = bootstrap_geometric_mean_ci(
            cluster_total_ratios,
            pair_seed,
        )
        eval_ci = bootstrap_geometric_mean_ci(
            cluster_eval_ratios,
            pair_seed + 1,
        )
        output.append(
            {
                "numerator_arm_id": numerator,
                "denominator_arm_id": denominator,
                "workloads": len(group),
                "dataset_model_clusters": len(clusters),
                "inference_unit": "dataset_model_cluster",
                "pairs": total_pairs,
                "geometric_mean_total_ratio": total_ratio,
                "total_ratio_workload_bootstrap_ci95_low": total_ci[0],
                "total_ratio_workload_bootstrap_ci95_high": total_ci[1],
                "geometric_mean_eval_only_ratio": eval_ratio,
                "eval_ratio_workload_bootstrap_ci95_low": eval_ci[0],
                "eval_ratio_workload_bootstrap_ci95_high": eval_ci[1],
                "median_workload_total_ratio": statistics.median(
                    cluster_total_ratios
                ),
                "min_workload_total_ratio": min(cluster_total_ratios),
                "max_workload_total_ratio": max(cluster_total_ratios),
                "mean_of_workload_mean_total_differences_ms": (
                    sum(
                        float(row["mean_paired_total_difference_ms"])
                        for row in group
                    )
                    / len(group)
                ),
                "mean_of_workload_mean_eval_only_differences_ms": (
                    sum(
                        float(
                            row[
                                "mean_paired_eval_only_difference_ms"
                            ]
                        )
                        for row in group
                    )
                    / len(group)
                ),
            }
        )
    return output


def geometric_mean(values: list[float]) -> float:
    if not values or any(value <= 0 for value in values):
        raise ValueError("geometric mean requires positive values")
    return math.exp(
        sum(math.log(value) for value in values) / len(values)
    )


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("percentile requires values")
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def bootstrap_geometric_mean_ci(
    values: list[float],
    seed: int,
) -> tuple[float, float]:
    generator = random.Random(seed)
    estimates = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sample = [
            values[generator.randrange(len(values))]
            for _ in values
        ]
        estimates.append(geometric_mean(sample))
    return (
        percentile(estimates, 0.025),
        percentile(estimates, 0.975),
    )


def timing_diagnostics(
    record_rows: list[dict[str, Any]],
    arm_rows: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    group_values: dict[tuple[str, str], list[float]] = {}
    for row in record_rows:
        key = (row["workload_id"], row["arm_id"])
        group_values.setdefault(key, []).append(float(row["total_ms"]))
    group_means = {
        key: statistics.mean(values)
        for key, values in group_values.items()
    }

    normalized_by_run: dict[int, list[float]] = {}
    normalized_by_position: dict[int, list[float]] = {}
    for row in record_rows:
        normalized = (
            float(row["total_ms"])
            / group_means[(row["workload_id"], row["arm_id"])]
        )
        run = int(row["measurement_run"])
        position = int(row["order_position"])
        normalized_by_run.setdefault(run, []).append(normalized)
        normalized_by_position.setdefault(position, []).append(
            normalized
        )

    cv_by_arm: dict[str, list[float]] = {}
    metadata: dict[tuple[str, str], tuple[str, str]] = {}
    for row in arm_rows:
        cv_by_arm.setdefault(row["arm_id"], []).append(
            float(row["stddev_total_ms"])
            / float(row["mean_total_ms"])
        )
        metadata[(row["workload_id"], row["arm_id"])] = (
            row["candidate_id"],
            row["evaluation_mode"],
        )

    duplicate_ratios = []
    for row in pair_rows:
        if (
            row["numerator_arm_id"] == "reference"
            and row["denominator_arm_id"] == "catalog"
            and metadata[(row["workload_id"], "reference")]
            == metadata[(row["workload_id"], "catalog")]
        ):
            duplicate_ratios.append(
                float(row["geometric_mean_total_ratio"])
            )

    return {
        "normalized_mean_total_by_measurement_run": {
            str(key): statistics.mean(values)
            for key, values in sorted(normalized_by_run.items())
        },
        "normalized_mean_total_by_order_position": {
            str(key): statistics.mean(values)
            for key, values in sorted(normalized_by_position.items())
        },
        "within_workload_total_cv_by_arm": {
            arm: {
                "median": statistics.median(values),
                "max": max(values),
            }
            for arm, values in sorted(cv_by_arm.items())
        },
        "duplicate_catalog_reference": {
            "workloads": len(duplicate_ratios),
            "geometric_mean_total_ratio": (
                geometric_mean(duplicate_ratios)
                if duplicate_ratios
                else None
            ),
        },
    }


def main() -> int:
    args = parse_args()
    if args.warmup_runs < 0:
        raise ValueError("--warmup-runs must be non-negative")
    if args.measurement_runs <= 0:
        raise ValueError("--measurement-runs must be positive")
    if args.max_rows < 0:
        raise ValueError("--max-rows must be non-negative")
    if args.max_workloads < 0:
        raise ValueError("--max-workloads must be non-negative")
    if args.mode == "final":
        frozen = (
            args.warmup_runs,
            args.measurement_runs,
            args.max_rows,
            args.max_workloads,
            args.alpha,
        )
        expected = (1, 6, 6, 0, 0.5)
        if frozen != expected:
            raise ValueError(
                "final mode requires frozen settings "
                "warmup=1 measurement=6 rows=6 "
                "max-workloads=0 alpha=0.5"
            )

    comparison_path = (REPO_ROOT / args.comparison).resolve()
    direct_results_path = (REPO_ROOT / args.direct_results).resolve()
    output_root = (REPO_ROOT / args.output_root).resolve()
    binary = (
        (REPO_ROOT / args.binary).resolve()
        if args.binary is not None
        else output_root / "bin" / "flipguard-paired-latency"
    )

    workloads = select_workloads(
        comparison_path,
        args.alpha,
        args.max_workloads,
    )
    direct_results = direct_result_index(direct_results_path)
    (
        source_commit,
        source_revision,
        source_dirty,
        source_files,
        source_digest,
    ) = source_state()
    if args.mode == "final" and source_dirty:
        raise ValueError(
            "final mode requires a clean committed measurement source"
        )
    if args.mode == "final" and len(workloads) != 50:
        raise ValueError(
            f"final mode requires 50 workloads, got {len(workloads)}"
        )
    build_binary(binary)

    statuses: list[dict[str, Any]] = []
    record_rows: list[dict[str, Any]] = []
    arm_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []

    for index, row in enumerate(workloads, start=1):
        key = workload_key(row)
        selection_path = direct_results.get(key)
        if selection_path is None:
            raise ValueError(f"missing direct SELECTED result for {key}")
        selection_path = (REPO_ROOT / selection_path).resolve()
        output_path = result_path(output_root, row)
        log_path = (
            output_root
            / "logs"
            / (output_path.stem + ".log")
        )
        action = "run"
        try:
            if output_path.exists() and not args.force:
                result = validate_existing_result(
                    output_path,
                    row,
                    selection_path,
                    source_revision,
                    source_digest,
                    args,
                )
                action = "skip"
            else:
                result = execute_workload(
                    binary,
                    output_path,
                    log_path,
                    row,
                    selection_path,
                    source_revision,
                    source_digest,
                    args,
                )
            flatten_result(
                row,
                result,
                record_rows,
                arm_rows,
                pair_rows,
            )
            results.append(result)
            statuses.append(
                {
                    "split_seed": key[0],
                    "dataset_id": key[1],
                    "model_id": key[2],
                    "status": "ok",
                    "action": action,
                    "result_path": str(output_path.relative_to(REPO_ROOT)),
                    "result_sha256": sha256_path(output_path),
                }
            )
            if not args.quiet:
                print(
                    f"[{index}/{len(workloads)}] {action} "
                    f"seed{key[0]}/{key[1]}/{key[2]}"
                )
        except Exception as error:  # preserve other completed workloads
            statuses.append(
                {
                    "split_seed": key[0],
                    "dataset_id": key[1],
                    "model_id": key[2],
                    "status": "failed",
                    "action": action,
                    "result_path": str(output_path.relative_to(REPO_ROOT)),
                    "result_sha256": "",
                    "error": str(error),
                }
            )
            print(
                f"[{index}/{len(workloads)}] FAIL "
                f"seed{key[0]}/{key[1]}/{key[2]}: {error}",
                file=sys.stderr,
            )

    summary_dir = output_root / "summary"
    status_fields = [
        "split_seed",
        "dataset_id",
        "model_id",
        "status",
        "action",
        "result_path",
        "result_sha256",
        "error",
    ]
    for row in statuses:
        row.setdefault("error", "")
    write_csv(summary_dir / "run_status.csv", status_fields, statuses)

    identity_fields = [
        "split_seed",
        "dataset_id",
        "model_id",
        "workload_id",
    ]
    record_fields = identity_fields + list(
        results[0]["measurement"]["records"][0].keys()
        if results
        else []
    )
    arm_fields = identity_fields + (
        [
            key
            for key in arm_rows[0]
            if key not in identity_fields
        ]
        if arm_rows
        else []
    )
    pair_fields = identity_fields + (
        [
            key
            for key in pair_rows[0]
            if key not in identity_fields
        ]
        if pair_rows
        else []
    )
    write_csv(summary_dir / "records.csv", record_fields, record_rows)
    write_csv(summary_dir / "arm_summaries.csv", arm_fields, arm_rows)
    write_csv(summary_dir / "pair_summaries.csv", pair_fields, pair_rows)

    aggregate_pairs = aggregate_pair_rows(pair_rows)
    aggregate_pair_fields = (
        list(aggregate_pairs[0].keys()) if aggregate_pairs else []
    )
    write_csv(
        summary_dir / "aggregate_pairs.csv",
        aggregate_pair_fields,
        aggregate_pairs,
    )

    successful = sum(row["status"] == "ok" for row in statuses)
    failed = len(statuses) - successful
    flip_counts: dict[str, int] = {}
    for row in arm_rows:
        flip_counts[row["arm_id"]] = (
            flip_counts.get(row["arm_id"], 0)
            + int(row["decision_flips"])
        )

    summary = {
        "schema_version": 2,
        "mode": args.mode.upper(),
        "evidence_status": (
            "PILOT_ONLY"
            if args.mode == "pilot"
            else "PAIRED_MEASUREMENT_PENDING_FREEZE"
        ),
        "paper_latency_claim_allowed": False,
        "claim_boundary": (
            "Pilot results choose frozen repetition counts and cannot support "
            "paper latency claims."
            if args.mode == "pilot"
            else "The paired run must be frozen, independently verified, and "
            "reported within the bounded workload/configuration scope before "
            "a paper latency claim is allowed."
        ),
        "protocol": {
            "warmup_runs": args.warmup_runs,
            "measurement_runs": args.measurement_runs,
            "max_rows": args.max_rows,
            "workloads_requested": len(workloads),
            "alpha": args.alpha,
            "order_schedule": (
                "balanced_cyclic_and_reverse_row_rotated_v1"
            ),
            "key_policy": (
                "one_parameter_compatible_keyset_per_arm_reused_within_workload"
            ),
            "outlier_policy": "none_all_raw_observations_preserved",
            "aggregate_inference_unit": "dataset_model_cluster",
            "dataset_model_clusters": len(
                {(row["dataset_id"], row["model_id"]) for row in workloads}
            ),
            "partition_instances": len(workloads),
            "partition_semantics": (
                "five deterministic repeated partitions of a fixed held-out artifact"
            ),
            "seed_roles": {
                "0": "development_ablation",
                "1-4": "post_freeze_repeated_partition_evaluation",
            },
            "inferential_warning": (
                "partition rows are not independent samples; uncertainty "
                "resamples dataset-model clusters"
            ),
            "bootstrap_seed": BOOTSTRAP_SEED,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        },
        "counts": {
            "workloads_successful": successful,
            "workloads_failed": failed,
            "raw_records": len(record_rows),
            "arm_summary_rows": len(arm_rows),
            "pair_summary_rows": len(pair_rows),
            "decision_flips_by_arm": flip_counts,
        },
        "aggregate_pairs": aggregate_pairs,
        "timing_diagnostics": timing_diagnostics(
            record_rows,
            arm_rows,
            pair_rows,
        ),
        "inputs": {
            "comparison": {
                "path": str(comparison_path.relative_to(REPO_ROOT)),
                "sha256": sha256_path(comparison_path),
            },
            "direct_results": {
                "path": str(direct_results_path.relative_to(REPO_ROOT)),
                "sha256": sha256_path(direct_results_path),
            },
        },
        "source": {
            "commit": source_commit,
            "revision_label": source_revision,
            "measurement_files_dirty": source_dirty,
            "digest": source_digest,
            "files": source_files,
        },
        "host": host_metadata(),
        "outputs": {
            name: {
                "path": str((summary_dir / name).relative_to(REPO_ROOT)),
                "sha256": sha256_path(summary_dir / name),
            }
            for name in (
                "run_status.csv",
                "records.csv",
                "arm_summaries.csv",
                "pair_summaries.csv",
                "aggregate_pairs.csv",
            )
        },
    }
    write_json(summary_dir / "summary.json", summary)

    if not args.quiet:
        print(
            f"paired_latency mode={args.mode} successful={successful}/"
            f"{len(workloads)} records={len(record_rows)} failed={failed}"
        )
        for row in aggregate_pairs:
            print(
                f"pair={row['numerator_arm_id']}/"
                f"{row['denominator_arm_id']} "
                f"total_ratio={row['geometric_mean_total_ratio']:.6f} "
                f"eval_ratio="
                f"{row['geometric_mean_eval_only_ratio']:.6f}"
            )
        print(f"summary={summary_dir / 'summary.json'}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
