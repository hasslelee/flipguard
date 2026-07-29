#!/usr/bin/env python3
"""Build or verify the planner baseline on the Security V2 filtered catalog."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SECURITY_ROOT = Path(
    "results/thesis_grade_protocol/security_v2_static_attestation/"
    "bounded_oracle_security_v2"
)
DEFAULT_OUTPUT = Path(
    "results/thesis_grade_protocol/"
    "planner_oracle_comparison_security_v2"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--security-root", type=Path, default=DEFAULT_SECURITY_ROOT
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def mean(rows: list[dict[str, str]], field: str) -> float:
    values = [float(row[field]) for row in rows if row.get(field, "") != ""]
    if not values:
        raise ValueError(f"no defined values for {field}")
    return statistics.fmean(values)


def scoped_metrics(rows: list[dict[str, str]]) -> dict[str, Any]:
    regrets = [
        float(row["latency_regret"])
        for row in rows
        if row["latency_regret"] != ""
    ]
    return {
        "rows": len(rows),
        "safe_recall": mean(rows, "safe_recall"),
        "bounded_optimum_recall": mean(rows, "optimum_recall"),
        "latency_regret_mean": statistics.fmean(regrets),
        "latency_regret_median": statistics.median(regrets),
        "latency_regret_max": max(regrets),
        "pruning_ratio": mean(rows, "pruning_ratio"),
        "false_no_safe": sum(
            row["false_no_safe"] == "true" for row in rows
        ),
        "planning_overhead_us": mean(rows, "planning_overhead_us"),
    }


def derive(rows: list[dict[str, str]]) -> dict[str, Any]:
    models = sorted({row["model_id"] for row in rows})
    return {
        "schema_version": 2,
        "catalog_scope": "security_v2_admitted_7_profiles_x_2_paths",
        "all": scoped_metrics(rows),
        "development_seed0": scoped_metrics(
            [row for row in rows if row["split_seed"] == "0"]
        ),
        "confirmatory_seeds1_4": scoped_metrics(
            [row for row in rows if row["split_seed"] in {"1", "2", "3", "4"}]
        ),
        "by_model": {
            model: scoped_metrics(
                [row for row in rows if row["model_id"] == model]
            )
            for model in models
        },
    }


def validate_inputs(security_root: Path) -> None:
    certificates = read_csv(
        security_root / "candidate_certificates_security_v2.csv"
    )
    identities = {
        (
            row["split_seed"],
            row["dataset_id"],
            row["model_id"],
            row["profile"],
            row["path"],
        )
        for row in certificates
    }
    if len(certificates) != 3500 or len(identities) != 700:
        raise ValueError(
            "Security V2 planner input must contain 3,500 alpha rows "
            "and 700 candidate identities"
        )


def generate(security_root: Path, output: Path) -> None:
    if output.exists():
        raise ValueError(f"{output} exists; use --force")
    validate_inputs(security_root)
    output.mkdir(parents=True)
    certificates = security_root / "candidate_certificates_security_v2.csv"
    coverage = security_root / "validation_coverage.csv"
    subprocess.run(
        [
            "go",
            "run",
            "./cmd/flipguard-planner-oracle",
            "-candidate-certificates",
            str(certificates),
            "-validation-coverage",
            str(coverage),
            "-output-root",
            str(output),
            "-selection-metric",
            "mean_total_ms",
        ],
        cwd=REPO_ROOT,
        check=True,
    )
    rows = read_csv(output / "comparison.csv")
    if len(rows) != 250 or any(
        row["oracle_candidate_count"] != "14" for row in rows
    ):
        raise ValueError("filtered planner comparison matrix changed")
    derived = derive(rows)
    (output / "derived_metrics.json").write_text(
        json.dumps(derived, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    files = {}
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            files[path.name] = {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
    manifest = {
        "schema_version": 1,
        "artifact_id": "planner_oracle_comparison_security_v2",
        "source_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip(),
        "catalog_candidate_identities": 700,
        "candidate_certificate_rows": 3500,
        "comparison_rows": 250,
        "inputs": {
            str(certificates.relative_to(REPO_ROOT)): sha256(certificates),
            str(coverage.relative_to(REPO_ROOT)): sha256(coverage),
        },
        "files": files,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify(security_root: Path, output: Path) -> None:
    validate_inputs(security_root)
    manifest = load_json(output / "manifest.json")
    for relative, expected in manifest["inputs"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"{path}: planner input digest changed")
    for relative, expected in manifest["files"].items():
        path = output / relative
        if (
            not path.is_file()
            or path.stat().st_size != expected["bytes"]
            or sha256(path) != expected["sha256"]
        ):
            raise ValueError(f"{path}: planner output digest changed")
    rows = read_csv(output / "comparison.csv")
    if len(rows) != 250 or any(
        row["oracle_candidate_count"] != "14" for row in rows
    ):
        raise ValueError("filtered planner comparison matrix changed")
    if derive(rows) != load_json(output / "derived_metrics.json"):
        raise ValueError("filtered planner derived metrics changed")
    print(
        "security_v2_planner=VERIFIED "
        "candidate_identities=700 comparison_rows=250"
    )


def main() -> int:
    args = parse_args()
    security_root = (REPO_ROOT / args.security_root).resolve()
    output = (REPO_ROOT / args.output_root).resolve()
    if args.verify:
        verify(security_root, output)
        return 0
    if output.exists() and args.force:
        shutil.rmtree(output)
    generate(security_root, output)
    verify(security_root, output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
