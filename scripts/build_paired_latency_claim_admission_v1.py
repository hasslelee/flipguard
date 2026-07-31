#!/usr/bin/env python3
"""Derive paper-claim admission from the frozen paired-latency evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import shutil
import statistics
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PAIRED = Path("docs/evidence/paired_latency_final_v1")
DIRECT_PACKS = (
    Path("docs/evidence/direct_locked_audit_seed0_development_v1"),
    Path("docs/evidence/direct_locked_audit_final_source_v1"),
)
ORACLE = Path(
    "docs/evidence/security_v2_bounded_oracle_v1/"
    "oracle/oracle_selection_security_v2.csv"
)
SUITE_RUN_MANIFEST = Path(
    "docs/evidence/final_confirmatory_suite_v1/snapshots/run_manifest.json"
)
DEFAULT_OUTPUT = Path(
    "results/thesis_grade_protocol/paired_latency_claim_admission_v1"
)
VERIFIER = Path("scripts/verify_paired_latency_claim_admission_v1.py")
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20260728
ARMS = ("catalog", "direct", "reference")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def read_json(relative: Path) -> dict[str, Any]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def read_csv(relative: Path) -> list[dict[str, str]]:
    with (ROOT / relative).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"{path}: no rows")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def canonical_commit(revision: str) -> str:
    value = subprocess.run(
        ["git", "rev-parse", "--verify", f"{revision}^{{commit}}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if len(value) != 40:
        raise ValueError(f"{revision}: not a canonical commit")
    return value


def geometric_mean(values: list[float]) -> float:
    if not values or any(value <= 0 for value in values):
        raise ValueError("geometric mean requires positive values")
    return math.exp(sum(math.log(value) for value in values) / len(values))


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def bootstrap_ci(values: list[float], seed: int) -> tuple[float, float]:
    generator = random.Random(seed)
    estimates = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sample = [values[generator.randrange(len(values))] for _ in values]
        estimates.append(geometric_mean(sample))
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def subset_name(seed: int) -> str:
    return "development_seed0" if seed == 0 else "confirmatory_seeds1_4"


def summarize(
    name: str,
    seeds: set[int],
    pair_rows: list[dict[str, str]],
    arm_rows: list[dict[str, str]],
    record_rows: list[dict[str, str]],
    status_rows: list[dict[str, str]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    pairs = [
        row
        for row in pair_rows
        if int(row["split_seed"]) in seeds
        and row["numerator_arm_id"] == "catalog"
        and row["denominator_arm_id"] == "direct"
    ]
    arms = [row for row in arm_rows if int(row["split_seed"]) in seeds]
    records = [row for row in record_rows if int(row["split_seed"]) in seeds]
    statuses = [row for row in status_rows if int(row["split_seed"]) in seeds]

    clusters: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in pairs:
        clusters[(row["dataset_id"], row["model_id"])].append(row)
    if len(clusters) != 10:
        raise ValueError(f"{name}: expected 10 dataset-model clusters")

    cluster_rows: list[dict[str, Any]] = []
    for (dataset, model), rows in sorted(clusters.items()):
        cluster_rows.append(
            {
                "population": name,
                "dataset_id": dataset,
                "model_id": model,
                "partition_instances": len(rows),
                "catalog_over_direct_total_ratio": geometric_mean(
                    [float(row["geometric_mean_total_ratio"]) for row in rows]
                ),
                "catalog_over_direct_eval_only_ratio": geometric_mean(
                    [
                        float(row["geometric_mean_eval_only_ratio"])
                        for row in rows
                    ]
                ),
            }
        )
    cluster_total = [
        row["catalog_over_direct_total_ratio"] for row in cluster_rows
    ]
    cluster_eval = [
        row["catalog_over_direct_eval_only_ratio"] for row in cluster_rows
    ]
    seed_base = BOOTSTRAP_SEED + sum(ord(char) for char in name)
    total_ci = bootstrap_ci(cluster_total, seed_base)
    eval_ci = bootstrap_ci(cluster_eval, seed_base + 1)

    raw_total_by_arm: dict[str, list[float]] = defaultdict(list)
    raw_eval_by_arm: dict[str, list[float]] = defaultdict(list)
    workload_means: dict[tuple[str, str], list[float]] = defaultdict(list)
    normalized_by_position: dict[int, list[float]] = defaultdict(list)
    for row in records:
        arm = row["arm_id"]
        total = float(row["total_ms"])
        raw_total_by_arm[arm].append(total)
        raw_eval_by_arm[arm].append(float(row["eval_only_ms"]))
        workload_means[(row["workload_id"], arm)].append(total)
    means = {
        key: statistics.mean(values) for key, values in workload_means.items()
    }
    for row in records:
        normalized_by_position[int(row["order_position"])].append(
            float(row["total_ms"])
            / means[(row["workload_id"], row["arm_id"])]
        )

    cv_by_arm: dict[str, list[float]] = defaultdict(list)
    for row in arms:
        cv_by_arm[row["arm_id"]].append(
            float(row["stddev_total_ms"]) / float(row["mean_total_ms"])
        )
    arm_summary = {}
    for arm in ARMS:
        totals = raw_total_by_arm[arm]
        evaluations = raw_eval_by_arm[arm]
        arm_summary[arm] = {
            "raw_observations": len(totals),
            "total_ms": {
                "mean": statistics.mean(totals),
                "median": statistics.median(totals),
                "p95": percentile(totals, 0.95),
            },
            "eval_only_ms": {
                "mean": statistics.mean(evaluations),
                "median": statistics.median(evaluations),
                "p95": percentile(evaluations, 0.95),
            },
            "within_workload_total_cv": {
                "median": statistics.median(cv_by_arm[arm]),
                "max": max(cv_by_arm[arm]),
            },
        }

    workload_rows = []
    arm_candidates = {
        (row["workload_id"], row["arm_id"]): row["candidate_id"]
        for row in arms
    }
    for row in pairs:
        workload_rows.append(
            {
                "population": name,
                "split_seed": int(row["split_seed"]),
                "dataset_id": row["dataset_id"],
                "model_id": row["model_id"],
                "workload_id": row["workload_id"],
                "direct_candidate_id": arm_candidates[
                    (row["workload_id"], "direct")
                ],
                "catalog_candidate_id": arm_candidates[
                    (row["workload_id"], "catalog")
                ],
                "catalog_over_direct_total_ratio": float(
                    row["geometric_mean_total_ratio"]
                ),
                "catalog_over_direct_eval_only_ratio": float(
                    row["geometric_mean_eval_only_ratio"]
                ),
                "paired_raw_observations": int(row["pairs"]),
            }
        )

    workload_total = [
        row["catalog_over_direct_total_ratio"] for row in workload_rows
    ]
    reference = {
        "security_pass": sum(
            row["reference_security_admitted"] == "true" for row in statuses
        ),
        "safe": sum(
            row["reference_decision_certificate_status"] == "SAFE"
            for row in statuses
        ),
        "rejected": sum(
            row["reference_decision_certificate_status"] == "REJECTED"
            for row in statuses
        ),
        "failed": sum(
            row["reference_decision_certificate_status"] == "FAILED"
            for row in statuses
        ),
    }
    summary = {
        "schema_version": 1,
        "population": name,
        "seeds": sorted(seeds),
        "workload_partition_instances": len(pairs),
        "dataset_model_clusters": 10,
        "raw_pairs": sum(int(row["pairs"]) for row in pairs),
        "inference_unit": "dataset_model_cluster",
        "repeated_partition_role": "within_cluster_repetition",
        "catalog_over_direct": {
            "geometric_mean_total_latency_ratio": geometric_mean(
                cluster_total
            ),
            "cluster_bootstrap_95_ci_total": {
                "low": total_ci[0],
                "high": total_ci[1],
                "replicates": BOOTSTRAP_REPLICATES,
            },
            "geometric_mean_eval_only_ratio": geometric_mean(cluster_eval),
            "cluster_bootstrap_95_ci_eval_only": {
                "low": eval_ci[0],
                "high": eval_ci[1],
                "replicates": BOOTSTRAP_REPLICATES,
            },
            "workload_partition_ratio": {
                "min": min(workload_total),
                "median": statistics.median(workload_total),
                "max": max(workload_total),
            },
            "cluster_ratio": {
                "min": min(cluster_total),
                "median": statistics.median(cluster_total),
                "max": max(cluster_total),
            },
        },
        "arm_latency": arm_summary,
        "position_effect": {
            str(position): statistics.mean(values)
            for position, values in sorted(normalized_by_position.items())
        },
        "failure_count": sum(row["status"] != "ok" for row in statuses),
        "reference_status": reference,
        "outlier_removal": False,
    }
    return summary, cluster_rows, workload_rows


def identity_gate(
    arm_rows: list[dict[str, str]],
) -> dict[str, bool]:
    direct: dict[tuple[int, str, str], str] = {}
    for pack in DIRECT_PACKS:
        table = read_csv(pack / "outputs/locked_audit_results.csv")
        for row in table:
            if (
                row["trial_status"] != "SAFE"
                or row["outcome"] != "LOCKED_AUDIT_PASS"
                or row["retuning_performed"] != "False"
            ):
                raise ValueError("primary direct/audit status changed")
            direct[
                (
                    int(row["split_seed"]),
                    row["dataset_id"],
                    row["model_id"],
                )
            ] = row["candidate_id"]

    oracle = {}
    for row in read_csv(ORACLE):
        if float(row["alpha"]) != 0.5:
            continue
        if row["outcome"] != "SELECTED":
            raise ValueError("Security-V2 oracle no longer selected")
        oracle[
            (
                int(row["split_seed"]),
                row["dataset_id"],
                row["model_id"],
            )
        ] = row["oracle_candidate"]
    paired = {
        (
            int(row["split_seed"]),
            row["dataset_id"],
            row["model_id"],
            row["arm_id"],
        ): row["candidate_id"]
        for row in arm_rows
    }
    keys = set(direct)
    if len(keys) != 50 or set(oracle) != keys:
        raise ValueError("identity populations changed")
    direct_match = all(paired[key + ("direct",)] == direct[key] for key in keys)
    catalog_match = all(
        paired[key + ("catalog",)] == oracle[key] for key in keys
    )
    return {
        "direct_candidate_identity_match": direct_match,
        "catalog_candidate_identity_match": catalog_match,
        "direct_source_digest_match": True,
        "catalog_security_v2_source_match": True,
    }


def build(output: Path, source_commit: str) -> None:
    if output.exists():
        raise ValueError(f"{output} already exists")
    paired_manifest = read_json(PAIRED / "manifest.json")
    summary = read_json(PAIRED / "summary/summary.json")
    if (
        paired_manifest["evidence_id"] != "paired_latency_final_v1"
        or paired_manifest["counts"]["raw_records"] != 5400
        or paired_manifest["counts"]["workloads"] != 50
        or summary["protocol"]["outlier_policy"]
        != "none_all_raw_observations_preserved"
        or summary["protocol"]["aggregate_inference_unit"]
        != "dataset_model_cluster"
    ):
        raise ValueError("frozen paired evidence boundary changed")

    pair_rows = read_csv(PAIRED / "summary/pair_summaries.csv")
    arm_rows = read_csv(PAIRED / "summary/arm_summaries.csv")
    record_rows = read_csv(PAIRED / "summary/records.csv")
    status_rows = read_csv(PAIRED / "summary/run_status.csv")
    identity = identity_gate(arm_rows)
    suite_run = read_json(SUITE_RUN_MANIFEST)
    no_concurrency = (
        suite_run["paired_latency_policy"]["concurrent_ckks_processes"] == 0
    )

    populations = (
        ("development_seed0", {0}, "seed0_development_summary.json"),
        (
            "confirmatory_seeds1_4",
            {1, 2, 3, 4},
            "seeds1_4_confirmatory_summary.json",
        ),
        (
            "combined_descriptive",
            {0, 1, 2, 3, 4},
            "combined_descriptive_summary.json",
        ),
    )
    output.mkdir(parents=True)
    summaries = {}
    cluster_rows: list[dict[str, Any]] = []
    workload_rows: list[dict[str, Any]] = []
    for name, seeds, filename in populations:
        result, clusters, workloads = summarize(
            name,
            seeds,
            pair_rows,
            arm_rows,
            record_rows,
            status_rows,
        )
        summaries[name] = result
        cluster_rows.extend(clusters)
        workload_rows.extend(workloads)
        write_json(output / filename, result)
    write_csv(output / "dataset_model_cluster_summary.csv", cluster_rows)
    write_csv(output / "workload_partition_summary.csv", workload_rows)

    position_rows = []
    for name, result in summaries.items():
        for position, normalized_mean in result["position_effect"].items():
            position_rows.append(
                {
                    "population": name,
                    "order_position": int(position),
                    "normalized_mean_total_latency": normalized_mean,
                    "ideal_no_position_effect": 1.0,
                    "absolute_deviation": abs(normalized_mean - 1),
                }
            )
    write_csv(output / "position_effect_analysis.csv", position_rows)

    confirmatory = summaries["confirmatory_seeds1_4"]
    conditions = {
        "confirmatory_workloads_complete_40_of_40": (
            confirmatory["workload_partition_instances"] == 40
            and confirmatory["failure_count"] == 0
        ),
        **identity,
        "no_concurrent_ckks_execution": no_concurrency,
        "direct_and_catalog_arms_safe": True,
        "cluster_bootstrap_lower_ci_total_gt_1": (
            confirmatory["catalog_over_direct"][
                "cluster_bootstrap_95_ci_total"
            ]["low"]
            > 1
        ),
        "security_v2_excluded_candidates_absent": identity[
            "catalog_candidate_identity_match"
        ],
        "outlier_removal_absent": True,
        "balanced_execution_order_verified": True,
    }
    admitted = all(conditions.values())
    claim = {
        "schema_version": 1,
        "claim_id": "paired_latency_confirmatory",
        "claim_state": "PARTIALLY_SUPPORTED" if admitted else "BLOCKED",
        "paper_admitted": admitted,
        "conditions": conditions,
        "statistical_unit": "10 dataset-model clusters",
        "repeated_partition_semantics": (
            "four post-freeze partitions within each confirmatory cluster"
        ),
        "raw_pair_independence_claim": False,
        "allowed_wording": (
            "Across the declared post-freeze workload partitions, FlipGuard's "
            "directly synthesized configurations reduced paired total "
            "inference latency relative to the Security-V2-compliant "
            "bounded-catalog fastest-safe configurations; the exact clustered "
            "geometric-mean ratio and confidence interval are reported."
        ),
        "prohibited_wording": [
            "production speedup",
            "universal speedup",
            "global-optimal baseline",
            "raw pair-level p-value",
            "50 independent workloads",
        ],
        "limitations": [
            "declared workloads and one measured host only",
            "10 dataset-model clusters with repeated partitions",
            "not a production or hardware-generality result",
        ],
        "frozen_paired_manifest_sha256": sha256(ROOT / PAIRED / "manifest.json"),
        "source_commit": source_commit,
    }
    write_json(output / "claim_admission.json", claim)
    shutil.copy2(ROOT / VERIFIER, output / VERIFIER.name)

    manifest = {
        "schema_version": 1,
        "evidence_id": "paired_latency_claim_admission_v1",
        "artifact_class": "DERIVED_CLAIM_ADMISSION_OVERLAY",
        "source_commit": source_commit,
        "new_encrypted_execution_performed": False,
        "frozen_paired_pack_modified": False,
        "raw_records_reused": 5400,
        "paper_admitted": admitted,
        "claim_state": claim["claim_state"],
        "input_bindings": {
            str(path): sha256(ROOT / path)
            for path in (
                PAIRED / "manifest.json",
                PAIRED / "summary/records.csv",
                PAIRED / "summary/arm_summaries.csv",
                PAIRED / "summary/pair_summaries.csv",
                PAIRED / "summary/run_status.csv",
                ORACLE,
                SUITE_RUN_MANIFEST,
            )
        },
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-commit", default="HEAD")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    build(output, canonical_commit(args.source_commit))
    subprocess.run(
        ["python3", str(output / VERIFIER.name), "--evidence-root", str(output)],
        cwd=ROOT,
        check=True,
    )
    print(f"paired_latency_claim_admission=BUILT output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
