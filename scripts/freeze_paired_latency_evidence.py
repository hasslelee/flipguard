#!/usr/bin/env python3
"""Freeze and independently verify paired selected-literal latency evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import shutil
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_ROOT = Path(
    "results/thesis_grade_protocol/paired_tabular_latency_v1/pilot_seed0"
)
DEFAULT_OUTPUT_ROOT = Path(
    "docs/evidence/paired_latency_pilot_v1"
)
SUMMARY_FILES = (
    Path("summary.json"),
    Path("run_status.csv"),
    Path("records.csv"),
    Path("arm_summaries.csv"),
    Path("pair_summaries.csv"),
    Path("aggregate_pairs.csv"),
)
ARMS = {"direct", "catalog", "reference"}
PAIRS = {
    ("catalog", "direct"),
    ("reference", "catalog"),
    ("reference", "direct"),
}
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20260728


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-root",
        type=Path,
        default=DEFAULT_INPUT_ROOT,
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
    )
    parser.add_argument(
        "--evidence-id",
        default="paired_latency_pilot_v1",
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


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def binding(path: Path) -> dict[str, Any]:
    try:
        relative = path.relative_to(REPO_ROOT)
    except ValueError:
        relative = path
    return {
        "path": str(relative),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def resolve_bound_path(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else REPO_ROOT / path


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise ValueError(f"missing source file {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def geometric_mean(values: list[float]) -> float:
    if not values or any(value <= 0 for value in values):
        raise ValueError("geometric mean requires positive values")
    return math.exp(
        sum(math.log(value) for value in values) / len(values)
    )


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def bootstrap_ci(
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


def close(actual: float, expected: float) -> bool:
    return math.isclose(
        actual,
        expected,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def validate_aggregates(
    pair_rows: list[dict[str, str]],
    aggregate_rows: list[dict[str, str]],
    workloads: int,
    cluster_by_dataset_model: bool,
) -> None:
    grouped: dict[
        tuple[str, str],
        list[dict[str, str]],
    ] = {}
    for row in pair_rows:
        key = (
            row["numerator_arm_id"],
            row["denominator_arm_id"],
        )
        grouped.setdefault(key, []).append(row)
    if set(grouped) != PAIRS:
        raise ValueError("paired comparison roles changed")

    aggregates = {
        (
            row["numerator_arm_id"],
            row["denominator_arm_id"],
        ): row
        for row in aggregate_rows
    }
    if set(aggregates) != PAIRS:
        raise ValueError("aggregate comparison roles changed")

    for key, rows in grouped.items():
        if len(rows) != workloads:
            raise ValueError(f"{key}: workload count changed")
        if cluster_by_dataset_model:
            clusters: dict[tuple[str, str], list[dict[str, str]]] = {}
            for row in rows:
                clusters.setdefault(
                    (row["dataset_id"], row["model_id"]),
                    [],
                ).append(row)
            total = [
                geometric_mean(
                    [
                        float(row["geometric_mean_total_ratio"])
                        for row in cluster
                    ]
                )
                for _, cluster in sorted(clusters.items())
            ]
            evaluation = [
                geometric_mean(
                    [
                        float(row["geometric_mean_eval_only_ratio"])
                        for row in cluster
                    ]
                )
                for _, cluster in sorted(clusters.items())
            ]
        else:
            total = [
                float(row["geometric_mean_total_ratio"])
                for row in rows
            ]
            evaluation = [
                float(row["geometric_mean_eval_only_ratio"])
                for row in rows
            ]
        seed = BOOTSTRAP_SEED + sum(
            ord(character)
            for character in key[0] + "/" + key[1]
        )
        total_ci = bootstrap_ci(total, seed)
        evaluation_ci = bootstrap_ci(evaluation, seed + 1)
        aggregate = aggregates[key]
        checks = {
            "geometric_mean_total_ratio": geometric_mean(total),
            "total_ratio_workload_bootstrap_ci95_low": total_ci[0],
            "total_ratio_workload_bootstrap_ci95_high": total_ci[1],
            "geometric_mean_eval_only_ratio":
                geometric_mean(evaluation),
            "eval_ratio_workload_bootstrap_ci95_low":
                evaluation_ci[0],
            "eval_ratio_workload_bootstrap_ci95_high":
                evaluation_ci[1],
            "median_workload_total_ratio": statistics.median(total),
            "min_workload_total_ratio": min(total),
            "max_workload_total_ratio": max(total),
        }
        for field, expected in checks.items():
            if not close(float(aggregate[field]), expected):
                raise ValueError(
                    f"{key}: aggregate {field} changed"
                )


def validate_study(
    root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary_dir = root / "summary"
    summary = load_json(summary_dir / "summary.json")
    mode = summary.get("mode")
    if mode not in {"PILOT", "FINAL"}:
        raise ValueError(f"unsupported paired mode {mode!r}")

    protocol = summary["protocol"]
    cluster_by_dataset_model = (
        protocol.get("aggregate_inference_unit")
        == "dataset_model_cluster"
    )
    if mode == "FINAL" and not cluster_by_dataset_model:
        raise ValueError(
            "final paired inference must cluster by dataset-model"
        )
    if mode == "PILOT":
        expected = {
            "workloads": 10,
            "records": 360,
            "arms": 30,
            "pairs": 30,
            "warmup": 1,
            "measurement": 3,
            "rows": 4,
        }
        if (
            summary.get("evidence_status") != "PILOT_ONLY"
            or summary.get("paper_latency_claim_allowed") is not False
        ):
            raise ValueError("pilot claim boundary changed")
    else:
        expected = {
            "workloads": 50,
            "records": 5400,
            "arms": 150,
            "pairs": 150,
            "warmup": 1,
            "measurement": 6,
            "rows": 6,
        }
        if (
            summary["source"]["measurement_files_dirty"]
            or "+measurement-working-tree"
            in summary["source"]["revision_label"]
        ):
            raise ValueError("final paired source is not clean")

    counts = summary["counts"]
    if (
        counts["workloads_successful"] != expected["workloads"]
        or counts["workloads_failed"] != 0
        or counts["raw_records"] != expected["records"]
        or counts["arm_summary_rows"] != expected["arms"]
        or counts["pair_summary_rows"] != expected["pairs"]
        or protocol["warmup_runs"] != expected["warmup"]
        or protocol["measurement_runs"] != expected["measurement"]
        or protocol["max_rows"] != expected["rows"]
        or protocol["workloads_requested"] != expected["workloads"]
        or protocol["bootstrap_seed"] != BOOTSTRAP_SEED
        or protocol["bootstrap_replicates"] != BOOTSTRAP_REPLICATES
    ):
        raise ValueError("paired protocol or counts changed")

    for name, expected_output in summary["outputs"].items():
        path = summary_dir / name
        if sha256_path(path) != expected_output["sha256"]:
            raise ValueError(f"{path}: summary digest mismatch")

    statuses = read_csv(summary_dir / "run_status.csv")
    records = read_csv(summary_dir / "records.csv")
    arm_rows = read_csv(summary_dir / "arm_summaries.csv")
    pair_rows = read_csv(summary_dir / "pair_summaries.csv")
    aggregate_rows = read_csv(summary_dir / "aggregate_pairs.csv")
    if (
        len(statuses) != expected["workloads"]
        or len(records) != expected["records"]
        or len(arm_rows) != expected["arms"]
        or len(pair_rows) != expected["pairs"]
        or len(aggregate_rows) != 3
    ):
        raise ValueError("paired CSV row counts changed")

    workload_keys = {
        (
            row["split_seed"],
            row["dataset_id"],
            row["model_id"],
        )
        for row in statuses
    }
    if (
        len(workload_keys) != expected["workloads"]
        or any(row["status"] != "ok" for row in statuses)
    ):
        raise ValueError("paired workload status matrix changed")

    external: dict[str, dict[str, Any]] = {}
    for item in summary["inputs"].values():
        path = resolve_bound_path(item["path"])
        if sha256_path(path) != item["sha256"]:
            raise ValueError(f"{path}: paired input digest changed")
        external[str(path)] = binding(path)

    result_by_workload: dict[str, dict[str, Any]] = {}
    for row in statuses:
        result_path = root / "results" / Path(
            row["result_path"]
        ).name
        if sha256_path(result_path) != row["result_sha256"]:
            raise ValueError(f"{result_path}: result digest changed")
        result = load_json(result_path)
        workload_id = result["workload_id"]
        if workload_id in result_by_workload:
            raise ValueError(f"duplicate result {workload_id}")
        result_by_workload[workload_id] = result
        if (
            result["source_revision"]
            != summary["source"]["revision_label"]
            or result["source_digest"]
            != summary["source"]["digest"]
        ):
            raise ValueError(f"{result_path}: source binding changed")

        for field in (
            "selection_result",
            "model_artifact",
            "validation_data",
        ):
            item = result[field]
            path = resolve_bound_path(item["path"])
            if sha256_path(path) != item["sha256"]:
                raise ValueError(
                    f"{path}: {field} digest changed"
                )
            external[str(path)] = binding(path)

        measurement = result["measurement"]
        item_protocol = measurement["protocol"]
        item_arms = measurement["arms"]
        item_records = measurement["records"]
        item_arm_summaries = measurement["arm_summaries"]
        item_pair_summaries = measurement["pair_summaries"]
        if (
            item_protocol["warmup_runs"] != expected["warmup"]
            or item_protocol["measurement_runs"]
            != expected["measurement"]
            or item_protocol["selected_rows"] != expected["rows"]
            or {item["id"] for item in item_arms} != ARMS
            or len(item_arm_summaries) != 3
            or len(item_pair_summaries) != 3
            or len(item_records)
            != expected["measurement"] * expected["rows"] * 3
        ):
            raise ValueError(
                f"{result_path}: measurement matrix changed"
            )

        grouped: dict[
            tuple[int, int],
            list[dict[str, Any]],
        ] = {}
        for record in item_records:
            key = (
                int(record["measurement_run"]),
                int(record["row_index"]),
            )
            grouped.setdefault(key, []).append(record)
            for field in (
                "encode_encrypt_ms",
                "eval_only_ms",
                "decrypt_decode_ms",
                "total_ms",
            ):
                value = float(record[field])
                if not math.isfinite(value) or value <= 0:
                    raise ValueError(
                        f"{result_path}: invalid {field}"
                    )
        for key, group in grouped.items():
            if (
                {item["arm_id"] for item in group} != ARMS
                or {int(item["order_position"]) for item in group}
                != {1, 2, 3}
            ):
                raise ValueError(
                    f"{result_path}: incomplete pairing {key}"
                )
        if mode == "FINAL":
            positions: dict[
                tuple[int, str],
                Counter[int],
            ] = {}
            for record in item_records:
                key = (
                    int(record["row_index"]),
                    record["arm_id"],
                )
                positions.setdefault(key, Counter())[
                    int(record["order_position"])
                ] += 1
            if any(
                counts != Counter({1: 2, 2: 2, 3: 2})
                for counts in positions.values()
            ):
                raise ValueError(
                    f"{result_path}: final order is unbalanced"
                )

    csv_record_keys = {
        (
            row["workload_id"],
            row["measurement_run"],
            row["row_index"],
            row["arm_id"],
        )
        for row in records
    }
    if len(csv_record_keys) != len(records):
        raise ValueError("flattened records contain duplicates")
    if {
        (row["workload_id"], row["arm_id"])
        for row in arm_rows
    } != {
        (workload_id, arm)
        for workload_id in result_by_workload
        for arm in ARMS
    }:
        raise ValueError("flattened arm summaries are incomplete")
    if {
        (
            row["workload_id"],
            row["numerator_arm_id"],
            row["denominator_arm_id"],
        )
        for row in pair_rows
    } != {
        (workload_id, numerator, denominator)
        for workload_id in result_by_workload
        for numerator, denominator in PAIRS
    }:
        raise ValueError("flattened pair summaries are incomplete")

    observed_flips = Counter()
    for row in records:
        if row["decision_flip"].lower() == "true":
            observed_flips[row["arm_id"]] += 1
    for arm in ARMS:
        if observed_flips[arm] != int(
            counts["decision_flips_by_arm"].get(arm, 0)
        ):
            raise ValueError(f"{arm}: flip count changed")

    validate_aggregates(
        pair_rows,
        aggregate_rows,
        expected["workloads"],
        cluster_by_dataset_model,
    )
    return (
        summary,
        [
            external[key]
            for key in sorted(external)
        ],
    )


def write_readme(
    path: Path,
    manifest: dict[str, Any],
) -> None:
    primary = manifest["primary_pair"]
    mode = manifest["mode"]
    claim = (
        "allowed within the frozen bounded scope"
        if manifest["paper_latency_claim_allowed"]
        else "not allowed from this evidence"
    )
    path.write_text(
        f"""# FlipGuard Paired Selected-Literal Latency Evidence

- Mode: `{mode}`
- Workloads: `{manifest["counts"]["workloads"]}`
- Raw measured records: `{manifest["counts"]["raw_records"]}`
- Decision flips: `{manifest["counts"]["decision_flips"]}`
- Primary catalog/direct total ratio:
  `{primary["geometric_mean_total_ratio"]:.6f}`
- 95% workload-bootstrap interval:
  `[{primary["ci95_low"]:.6f}, {primary["ci95_high"]:.6f}]`
- Paper latency claim: `{claim}`

The inference unit is one workload. Raw repeated timings are not treated as
independent workload samples. The catalog comparison is bounded to the
declared candidate space.

Verify copied files, all external input bindings, every three-arm pairing,
the final balanced order, flip accounting, and independently recomputed
workload-level estimates with:

```bash
python3 scripts/freeze_paired_latency_evidence.py \\
  --output-root {path.parent.relative_to(REPO_ROOT)} \\
  --verify
```
""",
        encoding="utf-8",
    )


def generate(
    input_root: Path,
    output_root: Path,
    evidence_id: str,
    force: bool,
) -> None:
    summary, external = validate_study(input_root)
    if output_root.exists():
        if not force:
            raise ValueError(f"{output_root} exists; use --force")
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    for relative in SUMMARY_FILES:
        copy_file(
            input_root / "summary" / relative,
            output_root / "summary" / relative,
        )
    for source in sorted((input_root / "results").glob("*.json")):
        copy_file(source, output_root / "results" / source.name)
    for source in sorted((input_root / "logs").glob("*.log")):
        copy_file(source, output_root / "logs" / source.name)
    for relative, expected in summary["source"]["files"].items():
        source = REPO_ROOT / relative
        if (
            source.stat().st_size != expected["bytes"]
            or sha256_path(source) != expected["sha256"]
        ):
            raise ValueError(f"{source}: source snapshot changed")
        copy_file(source, output_root / "source" / relative)
    copy_file(
        REPO_ROOT / "scripts/freeze_paired_latency_evidence.py",
        output_root
        / "source/scripts/freeze_paired_latency_evidence.py",
    )

    primary = next(
        row
        for row in summary["aggregate_pairs"]
        if (
            row["numerator_arm_id"],
            row["denominator_arm_id"],
        )
        == ("catalog", "direct")
    )
    flips = sum(
        summary["counts"]["decision_flips_by_arm"].values()
    )
    final_claim_allowed = (
        summary["mode"] == "FINAL"
        and not summary["source"]["measurement_files_dirty"]
        and flips == 0
        and primary["total_ratio_workload_bootstrap_ci95_low"] > 1
    )
    manifest = {
        "schema_version": 1,
        "evidence_id": evidence_id,
        "status": (
            "PARTIALLY_SUPPORTED"
            if summary["mode"] == "FINAL"
            else "PILOT_ONLY"
        ),
        "paper_claim_allowed": final_claim_allowed,
        "block_reason": (
            ""
            if final_claim_allowed
            else "paired final evidence is absent or its predeclared gate did not pass"
        ),
        "mode": summary["mode"],
        "paper_latency_claim_allowed": final_claim_allowed,
        "claim_boundary": (
            "The estimate is limited to the frozen workloads and bounded "
            "catalog; it is not a global optimality or production-latency "
            "claim."
        ),
        "counts": {
            "workloads": summary["counts"]["workloads_successful"],
            "raw_records": summary["counts"]["raw_records"],
            "decision_flips": flips,
            "internal_files": 0,
            "external_artifacts": len(external),
        },
        "primary_pair": {
            "numerator": "catalog",
            "denominator": "direct",
            "geometric_mean_total_ratio":
                primary["geometric_mean_total_ratio"],
            "ci95_low":
                primary["total_ratio_workload_bootstrap_ci95_low"],
            "ci95_high":
                primary["total_ratio_workload_bootstrap_ci95_high"],
        },
        "source": summary["source"],
        "host": summary["host"],
        "files": {},
        "external_artifacts": external,
    }
    write_readme(output_root / "README.md", manifest)
    copied = sorted(
        path
        for path in output_root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    )
    manifest["counts"]["internal_files"] = len(copied)
    manifest["files"] = {
        str(path.relative_to(output_root)): {
            "bytes": path.stat().st_size,
            "sha256": sha256_path(path),
        }
        for path in copied
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify(output_root: Path) -> None:
    manifest = load_json(output_root / "manifest.json")
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported paired evidence manifest")
    expected_files = set(manifest["files"])
    actual_files = {
        str(path.relative_to(output_root))
        for path in output_root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if actual_files != expected_files:
        raise ValueError(
            "paired evidence file set changed: "
            f"missing={sorted(expected_files - actual_files)} "
            f"unexpected={sorted(actual_files - expected_files)}"
        )
    for relative, expected in manifest["files"].items():
        path = output_root / relative
        if (
            path.stat().st_size != expected["bytes"]
            or sha256_path(path) != expected["sha256"]
        ):
            raise ValueError(f"{path}: evidence digest changed")
    for expected in manifest["external_artifacts"]:
        path = resolve_bound_path(expected["path"])
        if (
            path.stat().st_size != expected["bytes"]
            or sha256_path(path) != expected["sha256"]
        ):
            raise ValueError(f"{path}: external digest changed")

    summary, external = validate_study(output_root)
    if {
        item["path"]: item["sha256"] for item in external
    } != {
        item["path"]: item["sha256"]
        for item in manifest["external_artifacts"]
    }:
        raise ValueError("paired external bindings changed")
    for relative, expected in summary["source"]["files"].items():
        path = output_root / "source" / relative
        if (
            path.stat().st_size != expected["bytes"]
            or sha256_path(path) != expected["sha256"]
        ):
            raise ValueError(f"{path}: frozen source mismatch")

    print(
        "paired_latency_evidence=VERIFIED "
        f"mode={manifest['mode']} "
        f"files={len(expected_files)} "
        f"external={len(external)} "
        f"records={manifest['counts']['raw_records']} "
        f"claim_allowed="
        f"{str(manifest['paper_latency_claim_allowed']).lower()}"
    )


def main() -> int:
    args = parse_args()
    input_root = (REPO_ROOT / args.input_root).resolve()
    output_root = (REPO_ROOT / args.output_root).resolve()
    if args.verify:
        verify(output_root)
    else:
        generate(
            input_root,
            output_root,
            args.evidence_id,
            args.force,
        )
        verify(output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
