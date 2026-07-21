#!/usr/bin/env python3

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


SCHEMA_VERSION = 1
ALGORITHM = "sha256_stratified_rank_v1"


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def stable_rank(
    seed: int,
    dataset_id: str,
    model_id: str,
    label: str,
    row_id: str,
) -> str:
    payload = "\0".join(
        [
            str(seed),
            dataset_id,
            model_id,
            label,
            row_id,
        ]
    ).encode("utf-8")

    return hashlib.sha256(payload).hexdigest()


def load_csv(path: Path):
    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        if reader.fieldnames is None:
            raise ValueError(f"{path}: missing CSV header")

        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    required = {
        "row_id",
        "label",
        "polynomial_score",
        "plaintext_decision",
    }

    missing = sorted(required.difference(fieldnames))
    if missing:
        raise ValueError(
            f"{path}: missing fields {missing}"
        )

    feature_fields = [
        name
        for name in fieldnames
        if name.startswith("x_")
    ]

    if not feature_fields:
        raise ValueError(
            f"{path}: no model-ready x_i fields"
        )

    seen = set()

    for row_index, row in enumerate(rows):
        row_id = row["row_id"]

        if not row_id:
            raise ValueError(
                f"{path}: row {row_index} has empty row_id"
            )

        if row_id in seen:
            raise ValueError(
                f"{path}: duplicate row_id {row_id!r}"
            )

        seen.add(row_id)

        for field in feature_fields:
            value = float(row[field])

            if not math.isfinite(value):
                raise ValueError(
                    f"{path}: row {row_id} field {field} "
                    "is not finite"
                )

    if len(rows) < 4:
        raise ValueError(
            f"{path}: too few held-out rows"
        )

    return fieldnames, rows, feature_fields


def split_rows(
    rows: Sequence[Dict[str, str]],
    seed: int,
    dataset_id: str,
    model_id: str,
    validation_ratio: float,
):
    grouped: Dict[str, List[Dict[str, str]]] = (
        defaultdict(list)
    )

    for row in rows:
        grouped[row["label"]].append(row)

    validation_ids = set()

    for label, label_rows in sorted(grouped.items()):
        ranked = sorted(
            label_rows,
            key=lambda row: stable_rank(
                seed,
                dataset_id,
                model_id,
                label,
                row["row_id"],
            ),
        )

        target = int(
            math.floor(
                len(ranked) * validation_ratio
            )
        )

        target = max(
            1,
            min(len(ranked) - 1, target),
        )

        validation_ids.update(
            row["row_id"]
            for row in ranked[:target]
        )

    validation = [
        row
        for row in rows
        if row["row_id"] in validation_ids
    ]

    audit = [
        row
        for row in rows
        if row["row_id"] not in validation_ids
    ]

    if not validation or not audit:
        raise ValueError(
            f"{dataset_id}/{model_id}: empty split"
        )

    return validation, audit


def write_csv_atomic(
    path: Path,
    fieldnames: Sequence[str],
    rows: Iterable[Dict[str, str]],
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="",
        dir=path.parent,
        delete=False,
    ) as handle:
        temporary = Path(handle.name)

        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            lineterminator="\n",
        )

        writer.writeheader()
        writer.writerows(rows)

    os.replace(temporary, path)


def write_json_atomic(path: Path, payload):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")

    with tempfile.NamedTemporaryFile(
        "wb",
        dir=path.parent,
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(encoded)

    os.replace(temporary, path)


def label_counts(rows):
    return dict(
        sorted(
            Counter(
                row["label"]
                for row in rows
            ).items()
        )
    )


def build_splits(
    suite_root: Path,
    output_root: Path,
    seeds: Sequence[int],
    validation_ratio: float,
    model_ids: Sequence[str],
):
    all_workloads = sorted(
        suite_root.glob("*/*/test.csv")
    )

    if not all_workloads:
        raise ValueError(
            f"no workloads under {suite_root}"
        )

    requested_model_ids = set(model_ids)

    workloads = [
        path
        for path in all_workloads
        if path.parent.name in requested_model_ids
    ]

    excluded_workloads = [
        path
        for path in all_workloads
        if path.parent.name not in requested_model_ids
    ]

    discovered_model_ids = {
        path.parent.name
        for path in all_workloads
    }

    missing_model_ids = sorted(
        requested_model_ids.difference(
            discovered_model_ids
        )
    )

    if missing_model_ids:
        raise ValueError(
            "requested model IDs are absent from the suite: "
            + ",".join(missing_model_ids)
        )

    if not workloads:
        raise ValueError(
            "model allowlist selected no workloads"
        )

    summary = []

    for test_path in workloads:
        model_root = test_path.parent
        dataset_id = model_root.parent.name
        model_id = model_root.name
        model_path = model_root / "model.json"

        if not model_path.is_file():
            raise ValueError(
                f"missing model artifact {model_path}"
            )

        fieldnames, rows, feature_fields = (
            load_csv(test_path)
        )

        for seed in seeds:
            validation, audit = split_rows(
                rows,
                seed,
                dataset_id,
                model_id,
                validation_ratio,
            )

            target = (
                output_root
                / f"split_seed_{seed}"
                / dataset_id
                / model_id
            )

            validation_path = (
                target
                / "configuration_validation.csv"
            )

            audit_path = (
                target
                / "locked_audit_test.csv"
            )

            manifest_path = (
                target
                / "split_manifest.json"
            )

            write_csv_atomic(
                validation_path,
                fieldnames,
                validation,
            )

            write_csv_atomic(
                audit_path,
                fieldnames,
                audit,
            )

            manifest = {
                "schema_version": SCHEMA_VERSION,
                "algorithm": ALGORITHM,
                "dataset_id": dataset_id,
                "model_id": model_id,
                "split_seed": seed,
                "validation_ratio": validation_ratio,
                "source_test_csv": str(test_path),
                "source_test_csv_digest":
                    sha256_file(test_path),
                "model_artifact": str(model_path),
                "model_artifact_digest":
                    sha256_file(model_path),
                "source_row_count": len(rows),
                "feature_fields": feature_fields,
                "configuration_validation": {
                    "path": str(validation_path),
                    "row_count": len(validation),
                    "label_counts":
                        label_counts(validation),
                    "csv_digest":
                        sha256_file(validation_path),
                    "row_ids": [
                        row["row_id"]
                        for row in validation
                    ],
                },
                "locked_audit_test": {
                    "path": str(audit_path),
                    "row_count": len(audit),
                    "label_counts":
                        label_counts(audit),
                    "csv_digest":
                        sha256_file(audit_path),
                    "row_ids": [
                        row["row_id"]
                        for row in audit
                    ],
                },
            }

            write_json_atomic(
                manifest_path,
                manifest,
            )

            summary.append(
                {
                    "seed": seed,
                    "dataset_id": dataset_id,
                    "model_id": model_id,
                    "source_rows": len(rows),
                    "validation_rows":
                        len(validation),
                    "audit_rows": len(audit),
                    "manifest":
                        str(manifest_path),
                }
            )

    excluded = [
        {
            "dataset_id": path.parent.parent.name,
            "model_id": path.parent.name,
            "test_csv": str(path),
        }
        for path in excluded_workloads
    ]

    return summary, excluded


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--suite-root",
        default="datasets/tabular_suite",
    )

    parser.add_argument(
        "--output-root",
        default=(
            "results/thesis_grade_protocol/"
            "tabular_splits_v1"
        ),
    )

    parser.add_argument(
        "--seeds",
        default="0,1,2,3,4",
    )

    parser.add_argument(
        "--validation-ratio",
        type=float,
        default=0.5,
    )

    parser.add_argument(
        "--model-ids",
        default=(
            "linear_poly3,"
            "mlp_square_poly3"
        ),
        help=(
            "comma-separated explicit model IDs "
            "for the primary evaluation matrix"
        ),
    )

    parser.add_argument(
        "--force",
        action="store_true",
    )

    args = parser.parse_args()

    if not 0 < args.validation_ratio < 1:
        raise SystemExit(
            "validation ratio must be in (0, 1)"
        )

    seeds = [
        int(value)
        for value in args.seeds.split(",")
        if value.strip() != ""
    ]

    if len(seeds) != len(set(seeds)):
        raise SystemExit(
            "split seeds must be unique"
        )

    if len(seeds) < 2:
        raise SystemExit(
            "at least two split seeds are required"
        )

    model_ids = [
        value.strip()
        for value in args.model_ids.split(",")
        if value.strip() != ""
    ]

    if not model_ids:
        raise SystemExit(
            "at least one model ID is required"
        )

    if len(model_ids) != len(set(model_ids)):
        raise SystemExit(
            "model IDs must be unique"
        )

    output_root = Path(args.output_root)

    if output_root.exists():
        if not args.force:
            raise SystemExit(
                f"{output_root} already exists; "
                "use --force"
            )

        shutil.rmtree(output_root)

    summary, excluded = build_splits(
        Path(args.suite_root),
        output_root,
        seeds,
        args.validation_ratio,
        model_ids,
    )

    summary_path = output_root / "summary.json"

    write_json_atomic(
        summary_path,
        {
            "schema_version": SCHEMA_VERSION,
            "algorithm": ALGORITHM,
            "split_seeds": seeds,
            "validation_ratio":
                args.validation_ratio,
            "selected_model_ids":
                model_ids,
            "selected_workload_count":
                len(
                    {
                        (
                            row["dataset_id"],
                            row["model_id"],
                        )
                        for row in summary
                    }
                ),
            "workload_split_count":
                len(summary),
            "excluded_workloads":
                excluded,
            "records": summary,
        },
    )

    print(
        "selected_model_ids="
        + ",".join(model_ids)
    )

    print(
        "selected_workload_count="
        + str(
            len(
                {
                    (
                        row["dataset_id"],
                        row["model_id"],
                    )
                    for row in summary
                }
            )
        )
    )

    print(
        "excluded_workload_count="
        + str(len(excluded))
    )

    print(
        "workload_split_count="
        + str(len(summary))
    )

    print(
        "summary_path="
        + str(summary_path)
    )

    print(
        "summary_digest="
        + sha256_file(summary_path)
    )


if __name__ == "__main__":
    main()
