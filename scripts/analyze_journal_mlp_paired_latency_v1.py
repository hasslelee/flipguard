#!/usr/bin/env python3
"""Analyze the frozen 5,400-row focused MLP paired-latency ledger."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import shutil
import statistics
from collections import defaultdict
from pathlib import Path


SCHEMA = "flipguard_journal_mlp_paired_latency_analysis_v1"
PROTOCOL = Path("docs/evidence/journal_mlp_paired_latency_protocol_v1_3")
EXECUTION = Path("results/journal_mlp_paired_latency_v1/execution")
DEFAULT_OUTPUT = Path("results/journal_mlp_paired_latency_v1/analysis")
DIRECT_AUDIT = Path("results/journal_multiclass_extension_v1/encrypted/mnist_mlp_square_784_100_10_v1/locked_audit_result.json")
GRAPH_ONLY = Path("results/journal_multiclass_extension_v1/comparators/mlp_graph_only_fixed_logit_tolerance_v1/result.json")
VERIFIER = Path("scripts/verify_journal_mlp_paired_latency_v1.py")


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def stats(values: list[float]) -> dict:
    mean = statistics.fmean(values)
    stddev = statistics.pstdev(values)
    return {
        "count": len(values), "mean": mean, "median": statistics.median(values),
        "p95": percentile(values, 0.95), "standard_deviation": stddev,
        "IQR": percentile(values, 0.75) - percentile(values, 0.25),
        "CV": stddev / mean if mean else 0.0,
        "minimum": min(values), "maximum": max(values),
    }


def geometric_mean(values: list[float]) -> float:
    if not values or any(value <= 0 for value in values):
        raise RuntimeError("geometric mean requires positive values")
    return math.exp(statistics.fmean(math.log(value) for value in values))


def read_records(repo: Path) -> tuple[list[dict], list[dict]]:
    orchestration = load(repo / EXECUTION / "orchestration_complete.json")
    records: list[dict] = []
    bindings = []
    for item in orchestration["keysets"]:
        if item["status"] != "PASS":
            raise RuntimeError(f"keyset {item['keyset']} is not PASS")
        root = repo / item["path"]
        completion = load(root / "completed.json")
        if completion["records"] != 1800 or completion["ledger_sha256"] != sha(root / "records.jsonl"):
            raise RuntimeError(f"keyset {item['keyset']} completion mismatch")
        with (root / "records.jsonl").open(encoding="utf-8") as handle:
            key_records = [json.loads(line) for line in handle if line.strip()]
        if len(key_records) != 1800 or {row["keyset"] for row in key_records} != {item["keyset"]}:
            raise RuntimeError(f"keyset {item['keyset']} record population mismatch")
        records.extend(key_records)
        for name in ["run_manifest.json", "records.jsonl", "result.json", "completed.json"]:
            bindings.append({"path": str((root / name).relative_to(repo)), "sha256": sha(root / name)})
    if len(records) != 5400:
        raise RuntimeError(f"combined records={len(records)}; expected 5400")
    return records, bindings


def class_stratified_bootstrap(image_rows: list[dict], field: str, seed: int, repetitions: int) -> dict:
    by_class: dict[int, list[float]] = defaultdict(list)
    for row in image_rows:
        by_class[row["label"]].append(row[field])
    if set(by_class) != set(range(10)) or any(len(values) != 10 for values in by_class.values()):
        raise RuntimeError("bootstrap requires exactly 10 images per class")
    rng = random.Random(seed)
    estimates = []
    for _ in range(repetitions):
        sampled = []
        for label in range(10):
            values = by_class[label]
            sampled.extend(values[rng.randrange(len(values))] for _ in range(len(values)))
        estimates.append(geometric_mean(sampled))
    return {
        "method": "deterministic_class_stratified_image_cluster_bootstrap_percentile_v1",
        "seed": seed, "repetitions": repetitions,
        "lower_95": percentile(estimates, 0.025),
        "upper_95": percentile(estimates, 0.975),
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build(repo: Path, output: Path) -> None:
    if output.exists():
        raise RuntimeError(f"refusing to overwrite analysis: {output}")
    output.mkdir(parents=True)
    protocol = load(repo / PROTOCOL / "execution_protocol.json")
    records, raw_bindings = read_records(repo)
    arms = ["gap_aware", "graph_only", "catalog"]
    expected_keys = {
        (keyset, run, row["sample_id"], arm)
        for keyset in range(1, 4) for run in range(1, 7)
        for row in protocol["selected_rows"] for arm in arms
    }
    indexed = {}
    for record in records:
        key = (record["keyset"], record["measurement_run"], record["sample_id"], record["arm_id"])
        if key in indexed:
            raise RuntimeError(f"duplicate paired key {key}")
        indexed[key] = record
    if set(indexed) != expected_keys:
        raise RuntimeError("paired key matrix is incomplete")

    arm_rows = []
    for arm in arms:
        selected = [row for row in records if row["arm_id"] == arm]
        total = stats([row["total_ms"] for row in selected])
        evaluation = stats([row["evaluation_only_ms"] for row in selected])
        arm_rows.append({
            "arm_id": arm, "candidate_id": selected[0]["candidate_id"],
            "observations": len(selected), "images": len({row["sample_id"] for row in selected}),
            "keysets": len({row["keyset"] for row in selected}),
            "passes": len({row["measurement_run"] for row in selected}),
            "total_mean_ms": total["mean"], "total_median_ms": total["median"],
            "total_p95_ms": total["p95"], "total_stddev_ms": total["standard_deviation"],
            "total_IQR_ms": total["IQR"], "eval_mean_ms": evaluation["mean"],
            "eval_median_ms": evaluation["median"], "eval_p95_ms": evaluation["p95"],
            "eval_stddev_ms": evaluation["standard_deviation"], "eval_IQR_ms": evaluation["IQR"],
            "argmax_flips": sum(row["argmax_flip"] for row in selected),
            "reserve_policy_rejects": sum(row["reserve_policy_violation"] for row in selected),
        })

    image_metadata = {row["sample_id"]: row for row in protocol["selected_rows"]}
    image_pair_rows = []
    pair_rows = []
    class_rows = []
    for numerator in ["graph_only", "catalog"]:
        pair_id = f"{numerator}_over_gap_aware"
        raw_total_ratios = []
        raw_eval_ratios = []
        pair_image_rows = []
        for sample_id, metadata in image_metadata.items():
            total_ratios = []
            eval_ratios = []
            for keyset in range(1, 4):
                for run in range(1, 7):
                    numerator_row = indexed[(keyset, run, sample_id, numerator)]
                    denominator_row = indexed[(keyset, run, sample_id, "gap_aware")]
                    total_ratios.append(numerator_row["total_ms"] / denominator_row["total_ms"])
                    eval_ratios.append(numerator_row["evaluation_only_ms"] / denominator_row["evaluation_only_ms"])
            raw_total_ratios.extend(total_ratios)
            raw_eval_ratios.extend(eval_ratios)
            row = {
                "pair_id": pair_id, "sample_id": sample_id,
                "source_index": metadata["source_index"], "label": metadata["label"],
                "repetitions": len(total_ratios),
                "geometric_mean_total_ratio": geometric_mean(total_ratios),
                "geometric_mean_eval_ratio": geometric_mean(eval_ratios),
            }
            image_pair_rows.append(row)
            pair_image_rows.append(row)
        total_ci = class_stratified_bootstrap(pair_image_rows, "geometric_mean_total_ratio", 20260802, 10000)
        eval_ci = class_stratified_bootstrap(pair_image_rows, "geometric_mean_eval_ratio", 20260803, 10000)
        pair_rows.append({
            "pair_id": pair_id, "numerator_arm": numerator, "denominator_arm": "gap_aware",
            "raw_pairs": len(raw_total_ratios), "image_clusters": len(pair_image_rows),
            "geometric_mean_total_ratio": geometric_mean(raw_total_ratios),
            "total_ci_low": total_ci["lower_95"], "total_ci_high": total_ci["upper_95"],
            "geometric_mean_eval_ratio": geometric_mean(raw_eval_ratios),
            "eval_ci_low": eval_ci["lower_95"], "eval_ci_high": eval_ci["upper_95"],
            "bootstrap_seed_total": total_ci["seed"], "bootstrap_seed_eval": eval_ci["seed"],
            "bootstrap_repetitions": total_ci["repetitions"],
        })
        for label in range(10):
            selected = [row for row in pair_image_rows if row["label"] == label]
            class_rows.append({
                "pair_id": pair_id, "label": label, "images": len(selected),
                "geometric_mean_total_ratio": geometric_mean([row["geometric_mean_total_ratio"] for row in selected]),
                "geometric_mean_eval_ratio": geometric_mean([row["geometric_mean_eval_ratio"] for row in selected]),
            })

    position_rows = []
    for arm in arms:
        for position in [1, 2, 3]:
            selected = [row for row in records if row["arm_id"] == arm and row["order_position"] == position]
            position_rows.append({
                "arm_id": arm, "order_position": position, "observations": len(selected),
                "total_mean_ms": statistics.fmean(row["total_ms"] for row in selected),
                "eval_mean_ms": statistics.fmean(row["evaluation_only_ms"] for row in selected),
            })

    setup_rows = []
    orchestration = load(repo / EXECUTION / "orchestration_complete.json")
    for item in orchestration["keysets"]:
        result = load(repo / item["path"] / "result.json")
        for arm in result["arms"]:
            setup_rows.append({
                "keyset": item["keyset"], "arm_id": arm["id"],
                "candidate_id": arm["candidate_id"], "setup_keygen_ms": arm["setup_keygen_ms"],
                "process_attempt": item["attempt"],
            })

    direct_audit = load(repo / DIRECT_AUDIT)["result"]
    graph_only = load(repo / GRAPH_ONLY)
    direct_full_audit_pass = (
        direct_audit["trial"]["status"] == "SAFE" and direct_audit["retuning_count"] == 0
        and direct_audit["candidate_identity_match"] is True
    )
    graph_only_full_audit_pass = False
    graph_pair = next(row for row in pair_rows if row["pair_id"] == "graph_only_over_gap_aware")
    literal_difference = protocol["arms"][0]["candidate"]["id"] != protocol["arms"][1]["candidate"]["id"]
    if not literal_difference:
        effect_class = "NO_OBSERVED_EFFECT"
    elif graph_pair["total_ci_low"] > 1 and direct_full_audit_pass and graph_only_full_audit_pass:
        effect_class = "LATENCY_EFFECT_SUPPORTED"
    else:
        effect_class = "LITERAL_EFFECT_ONLY"
    claim = {
        "schema_version": SCHEMA,
        "effect_class": effect_class,
        "literal_difference": literal_difference,
        "gap_aware_full_locked_audit_pass": direct_full_audit_pass,
        "graph_only_full_locked_audit_pass": graph_only_full_audit_pass,
        "graph_only_existing_evidence_role": "configuration_validation_only",
        "latency_subset_images": 100,
        "latency_subset_decision_observations_per_arm": 1800,
        "latency_subset_argmax_flips": sum(row["argmax_flip"] for row in records),
        "latency_subset_reserve_policy_rejects": sum(row["reserve_policy_violation"] for row in records),
        "graph_only_over_gap_aware_total": graph_pair,
        "latency_superiority_paper_admitted": effect_class == "LATENCY_EFFECT_SUPPORTED",
        "literal_effect_paper_admitted": literal_difference,
        "catalog_comparison_scope": "frozen Security-V2 bounded-catalog fastest-safe on the predeclared 100-image latency subset",
        "le_net_catalog_latency": "BLOCKED_NOT_EVALUATED",
        "limitation": "The graph-only S32 comparator has no separate full 500-image locked-audit replay; its decision checks in this amendment are limited to the frozen 100-image latency subset.",
    }

    write_csv(output / "arm_summary.csv", list(arm_rows[0]), arm_rows)
    write_csv(output / "pair_summary.csv", list(pair_rows[0]), pair_rows)
    write_csv(output / "image_pair_summary.csv", list(image_pair_rows[0]), image_pair_rows)
    write_csv(output / "class_pair_summary.csv", list(class_rows[0]), class_rows)
    write_csv(output / "position_effect.csv", list(position_rows[0]), position_rows)
    write_csv(output / "setup_keygen_summary.csv", list(setup_rows[0]), setup_rows)
    (output / "claim_admission.json").write_text(canonical(claim), encoding="utf-8")
    summary = {
        "schema_version": SCHEMA,
        "protocol_id": protocol["protocol_id"], "records": len(records),
        "images": 100, "classes": 10, "keysets": 3, "measurement_passes": 6,
        "arms": arm_rows, "pairs": pair_rows,
        "all_candidate_identities_match": all(
            row["candidate_id"] == next(arm["candidate"]["id"] for arm in protocol["arms"] if arm["id"] == row["arm_id"])
            for row in records
        ),
        "argmax_flips": sum(row["argmax_flip"] for row in records),
        "reserve_policy_rejects": sum(row["reserve_policy_violation"] for row in records),
        "effect_class": effect_class,
    }
    (output / "summary.json").write_text(canonical(summary), encoding="utf-8")
    shutil.copyfile(repo / VERIFIER, output / VERIFIER.name)
    manifest = {
        "schema_version": SCHEMA,
        "protocol": {"path": str(PROTOCOL / "execution_protocol.json"), "sha256": sha(repo / PROTOCOL / "execution_protocol.json")},
        "orchestration": {"path": str(EXECUTION / "orchestration_complete.json"), "sha256": sha(repo / EXECUTION / "orchestration_complete.json")},
        "raw_bindings": raw_bindings,
        "direct_full_audit": {"path": str(DIRECT_AUDIT), "sha256": sha(repo / DIRECT_AUDIT)},
        "graph_only_validation": {"path": str(GRAPH_ONLY), "sha256": sha(repo / GRAPH_ONLY)},
        "new_encrypted_records": 5400, "policy_retuning": 0,
        "analysis_statistical_unit": "image_cluster",
    }
    (output / "manifest.json").write_text(canonical(manifest), encoding="utf-8")
    sums = []
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS":
            sums.append(f"{sha(path).removeprefix('sha256:')}  {path.name}\n")
    (output / "SHA256SUMS").write_text("".join(sums), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    repo = args.repo.resolve()
    output = (repo / args.output).resolve() if not args.output.is_absolute() else args.output.resolve()
    build(repo, output)
    print(f"journal_mlp_paired_latency_analysis=BUILT output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
