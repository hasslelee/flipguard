#!/usr/bin/env python3
"""Fail-closed verifier for the derived MNIST CNN-lite holdout."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = Path(
    "datasets/vision_suite/mnist/cnn_lite_square_binary01"
)
EXPORTER_PATH = (
    REPO_ROOT / "scripts/export_mnist_cnn_lite_holdout.py"
)
SPEC = importlib.util.spec_from_file_location(
    "export_mnist_cnn_lite_holdout",
    EXPORTER_PATH,
)
EXPORTER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(EXPORTER)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--source-replay", action="store_true")
    parser.add_argument(
        "--source",
        type=Path,
        default=EXPORTER.DEFAULT_SOURCE,
    )
    return parser.parse_args()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksums(root: Path) -> None:
    lines = (root / "SHA256SUMS").read_text(
        encoding="ascii"
    ).splitlines()
    observed: set[str] = set()
    for line in lines:
        digest, name = line.split("  ", 1)
        path = root / name
        if not path.is_file():
            raise ValueError(f"checksum target missing: {name}")
        if sha256_path(path) != digest:
            raise ValueError(f"checksum mismatch: {name}")
        observed.add(name)
    expected = {
        "configuration_validation.csv",
        "extraction_manifest.json",
        "locked_audit_test.csv",
        "model.json",
    }
    if observed != expected:
        raise ValueError(
            f"checksum file set changed: {sorted(observed)}"
        )


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="ascii") as handle:
        return list(csv.DictReader(handle))


def verify_partition(
    rows: list[dict[str, str]],
    source_partition: str,
    source_digest: str,
    extraction_digest: str,
    parameters: list[float],
) -> dict[str, Any]:
    expected_rows = 2 * EXPORTER.CONFIGURATION_VALIDATION_PER_CLASS
    if source_partition == "test":
        expected_rows = 2 * EXPORTER.LOCKED_AUDIT_PER_CLASS
    if len(rows) != expected_rows:
        raise ValueError(
            f"{source_partition} has {len(rows)} rows, "
            f"expected {expected_rows}"
        )
    identities: set[int] = set()
    label_counts = {0: 0, 1: 0}
    correct = 0
    positive_decisions = 0
    margins: list[float] = []
    for row in rows:
        row_id = int(row["row_id"])
        if row_id in identities:
            raise ValueError(f"duplicate MNIST row {row_id}")
        identities.add(row_id)
        if row["sample_id"] != f"mnist_{row_id:05d}":
            raise ValueError(f"sample identity changed at row {row_id}")
        if row["source_partition"] != source_partition:
            raise ValueError(
                f"partition identity changed at row {row_id}"
            )
        if source_partition == "train" and \
                row_id >= EXPORTER.OFFICIAL_TRAIN_ROWS:
            raise ValueError("validation escaped official train partition")
        if source_partition == "test" and \
                row_id < EXPORTER.OFFICIAL_TRAIN_ROWS:
            raise ValueError("audit escaped official test partition")
        label = int(row["digit_label"])
        binary_label = int(row["binary_label"])
        if label not in (0, 1) or binary_label != label:
            raise ValueError(f"binary task changed at row {row_id}")
        label_counts[label] += 1
        if row["source_sha256"] != source_digest:
            raise ValueError(f"source digest changed at row {row_id}")
        if row["extraction_policy_digest"] != extraction_digest:
            raise ValueError(
                f"extraction digest changed at row {row_id}"
            )
        features = [
            float(row[name])
            for name in EXPORTER.PIXEL_COLUMNS
        ]
        if any(
            not math.isfinite(value) or value < 0 or value > 1
            for value in features
        ):
            raise ValueError(f"invalid pooled input at row {row_id}")
        expected_score = EXPORTER.cnn_score(features, parameters)
        observed_score = float(row["plaintext_score"])
        if not math.isclose(
            expected_score,
            observed_score,
            rel_tol=1e-13,
            abs_tol=1e-14,
        ):
            raise ValueError(f"plaintext graph changed at row {row_id}")
        if float(row["decision_threshold"]) != 0:
            raise ValueError(f"threshold changed at row {row_id}")
        margin = abs(observed_score)
        if not math.isclose(
            float(row["decision_margin"]),
            margin,
            rel_tol=0,
            abs_tol=1e-15,
        ):
            raise ValueError(f"margin changed at row {row_id}")
        decision = row["plaintext_decision"] == "true"
        if decision != (observed_score >= 0):
            raise ValueError(f"decision changed at row {row_id}")
        positive_decisions += int(decision)
        correct += int(decision == bool(label))
        margins.append(margin)
    per_class = expected_rows // 2
    if label_counts != {0: per_class, 1: per_class}:
        raise ValueError(
            f"partition is no longer label-balanced: {label_counts}"
        )
    return {
        "rows": len(rows),
        "row_ids": identities,
        "correct": correct,
        "incorrect": len(rows) - correct,
        "accuracy": correct / len(rows),
        "positive_labels": label_counts[1],
        "negative_labels": label_counts[0],
        "positive_decisions": positive_decisions,
        "negative_decisions": len(rows) - positive_decisions,
        "minimum_margin": min(margins),
    }


def compare_metrics(
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    fields = (
        "rows",
        "correct",
        "incorrect",
        "accuracy",
        "positive_labels",
        "negative_labels",
        "positive_decisions",
        "negative_decisions",
        "minimum_margin",
    )
    for field in fields:
        if isinstance(actual[field], float):
            if not math.isclose(
                actual[field],
                float(expected[field]),
                rel_tol=1e-13,
                abs_tol=1e-15,
            ):
                raise ValueError(f"partition metric changed: {field}")
        elif actual[field] != expected[field]:
            raise ValueError(f"partition metric changed: {field}")


def verify(
    root: Path,
    source_replay: bool,
    source: Path,
) -> None:
    verify_checksums(root)
    model_path = root / "model.json"
    manifest_path = root / "extraction_manifest.json"
    model = json.loads(model_path.read_text(encoding="ascii"))
    manifest = json.loads(
        manifest_path.read_text(encoding="ascii")
    )
    if model["schema_version"] != EXPORTER.SCHEMA_VERSION or \
            manifest["schema_version"] != EXPORTER.SCHEMA_VERSION:
        raise ValueError("MNIST CNN-lite schema changed")
    if model["model_id"] != EXPORTER.MODEL_ID or \
            model["model_type"] != EXPORTER.MODEL_TYPE or \
            model["graph_adapter_id"] != EXPORTER.GRAPH_ADAPTER_ID:
        raise ValueError("MNIST CNN-lite graph identity changed")
    if model["packing_scope"] != \
            "scalar_replicated_per_ciphertext_v1":
        raise ValueError("MNIST CNN-lite packing scope changed")
    source_digest = "sha256:" + EXPORTER.EXPECTED_SOURCE_SHA256
    extraction_digest = EXPORTER.policy_digest()
    if model["source_archive"]["sha256"] != source_digest or \
            manifest["source_archive"]["sha256"] != source_digest:
        raise ValueError("MNIST source binding changed")
    if model["extraction_policy_digest"] != extraction_digest or \
            manifest["extraction_policy_digest"] != extraction_digest:
        raise ValueError("MNIST extraction policy changed")
    if model["direct_policy_reference"] != {
        "policy_id": EXPORTER.DIRECT_POLICY_ID,
        "policy_digest": EXPORTER.DIRECT_POLICY_DIGEST,
        "relationship": (
            "frozen_constants_reused_by_predeclared_graph_adapter;"
            "model_type_not_added_to_policy_supported_models"
        ),
    }:
        raise ValueError("Direct Policy V2 extension boundary changed")
    if manifest["model"]["sha256"] != \
            "sha256:" + sha256_path(model_path):
        raise ValueError("MNIST model digest binding changed")
    noninterference = manifest["audit_noninterference"]
    if set(noninterference.values()) != {False}:
        raise ValueError("locked-audit noninterference changed")

    parameters = EXPORTER.flatten_parameters(model)
    if any(not math.isfinite(value) for value in parameters):
        raise ValueError("MNIST model contains non-finite parameter")
    validation_path = root / "configuration_validation.csv"
    audit_path = root / "locked_audit_test.csv"
    validation = verify_partition(
        read_rows(validation_path),
        "train",
        source_digest,
        extraction_digest,
        parameters,
    )
    audit = verify_partition(
        read_rows(audit_path),
        "test",
        source_digest,
        extraction_digest,
        parameters,
    )
    if validation["row_ids"] & audit["row_ids"]:
        raise ValueError("MNIST validation/audit rows overlap")
    manifest_validation = manifest["partitions"][
        "configuration_validation"
    ]
    manifest_audit = manifest["partitions"]["locked_audit_test"]
    if manifest_validation["sha256"] != \
            "sha256:" + sha256_path(validation_path) or \
            manifest_audit["sha256"] != \
            "sha256:" + sha256_path(audit_path):
        raise ValueError("MNIST partition digest binding changed")
    compare_metrics(validation, manifest_validation["metrics"])
    compare_metrics(audit, manifest_audit["metrics"])

    if source_replay:
        source_path = (
            source
            if source.is_absolute()
            else REPO_ROOT / source
        )
        EXPORTER.verify(source_path, root)
    print(
        "mnist_cnn_lite_artifact=PASS "
        f"validation_rows={validation['rows']} "
        f"audit_rows={audit['rows']} "
        f"validation_accuracy={validation['accuracy']:.6f} "
        f"audit_accuracy={audit['accuracy']:.6f} "
        f"policy_digest={extraction_digest}"
    )


def main() -> None:
    args = parse_args()
    root = args.root if args.root.is_absolute() else REPO_ROOT / args.root
    verify(root, args.source_replay, args.source)


if __name__ == "__main__":
    main()
