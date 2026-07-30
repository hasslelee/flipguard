#!/usr/bin/env python3
"""Fail-closed verifier for the derived BSDS500 Sobel holdout."""

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
    "datasets/vision_suite/bsds500/sobel_edge_score"
)
EXPORTER_PATH = REPO_ROOT / "scripts/export_bsds500_sobel_holdout.py"
SPEC = importlib.util.spec_from_file_location(
    "export_bsds500_sobel_holdout",
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
        "--archive",
        type=Path,
        default=EXPORTER.DEFAULT_ARCHIVE,
    )
    parser.add_argument(
        "--image-root",
        type=Path,
        default=EXPORTER.DEFAULT_IMAGE_ROOT,
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
    expected_partition: str,
    expected_row_base: int,
    threshold: float,
    archive_digest: str,
    extraction_digest: str,
) -> dict[str, Any]:
    if len(rows) != 400:
        raise ValueError(
            f"{expected_partition} has {len(rows)} rows, expected 400"
        )
    row_ids: set[int] = set()
    image_ids: set[str] = set()
    positive = 0
    margins: list[float] = []
    for index, row in enumerate(rows):
        row_id = int(row["row_id"])
        if row_id != expected_row_base + index:
            raise ValueError(
                f"{expected_partition} row order changed at {index}"
            )
        if row_id in row_ids:
            raise ValueError(f"duplicate row_id {row_id}")
        row_ids.add(row_id)
        image_ids.add(row["image_id"])
        if row["source_partition"] != expected_partition:
            raise ValueError("source partition label changed")
        if row["source_archive_sha256"] != archive_digest:
            raise ValueError("source archive digest changed")
        if row["extraction_policy_digest"] != extraction_digest:
            raise ValueError("extraction policy digest changed")
        pixels = [
            float(row[name])
            for name in EXPORTER.PIXEL_COLUMNS
        ]
        if any(
            not math.isfinite(value) or value < 0 or value > 1
            for value in pixels
        ):
            raise ValueError(f"invalid normalized pixel in row {row_id}")
        expected_score = EXPORTER.sobel_score(pixels)
        score = float(row["plaintext_score"])
        if not math.isclose(
            score,
            expected_score,
            rel_tol=0,
            abs_tol=1e-14,
        ):
            raise ValueError(f"plaintext score changed in row {row_id}")
        if not math.isclose(
            float(row["decision_threshold"]),
            threshold,
            rel_tol=0,
            abs_tol=1e-15,
        ):
            raise ValueError(f"threshold changed in row {row_id}")
        margin = abs(score - threshold)
        if not math.isclose(
            float(row["decision_margin"]),
            margin,
            rel_tol=0,
            abs_tol=1e-15,
        ):
            raise ValueError(f"margin changed in row {row_id}")
        decision = row["plaintext_decision"] == "true"
        if decision != (score >= threshold):
            raise ValueError(f"decision changed in row {row_id}")
        positive += int(decision)
        margins.append(margin)
    if len(image_ids) != 50:
        raise ValueError(
            f"{expected_partition} has {len(image_ids)} image clusters"
        )
    return {
        "rows": len(rows),
        "images": len(image_ids),
        "positive": positive,
        "negative": len(rows) - positive,
        "row_ids": row_ids,
        "image_ids": image_ids,
        "minimum_margin": min(margins),
    }


def verify(root: Path, source_replay: bool, archive: Path, image_root: Path) -> None:
    verify_checksums(root)
    model = json.loads((root / "model.json").read_text(encoding="ascii"))
    manifest = json.loads(
        (root / "extraction_manifest.json").read_text(encoding="ascii")
    )
    if model["schema_version"] != EXPORTER.SCHEMA_VERSION or \
            manifest["schema_version"] != EXPORTER.SCHEMA_VERSION:
        raise ValueError("Sobel artifact schema changed")
    if model["model_type"] != EXPORTER.MODEL_TYPE or \
            model["graph_formula"] != "Gx^2 + Gy^2":
        raise ValueError("Sobel graph identity changed")
    extraction_digest = EXPORTER.policy_digest()
    if model["extraction_policy_digest"] != extraction_digest or \
            manifest["extraction_policy_digest"] != extraction_digest:
        raise ValueError("Sobel extraction policy digest changed")
    archive_digest = "sha256:" + EXPORTER.EXPECTED_ARCHIVE_SHA256
    if model["source_archive"]["sha256"] != archive_digest or \
            manifest["source_archive"]["sha256"] != archive_digest:
        raise ValueError("Sobel source archive binding changed")
    direct = model["direct_policy_reference"]
    if direct != {
        "policy_digest": (
            "sha256:"
            "503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
        ),
        "policy_id": "flipguard_direct_synthesis_policy_v2",
        "relationship": (
            "frozen_constants_reused_by_predeclared_graph_adapter;"
            "model_type_not_added_to_policy_supported_models"
        ),
    }:
        raise ValueError("Direct Policy V2 extension boundary changed")
    threshold = float(model["decision_threshold"])
    validation_path = root / "configuration_validation.csv"
    audit_path = root / "locked_audit_test.csv"
    validation = verify_partition(
        read_rows(validation_path),
        "val",
        100000,
        threshold,
        archive_digest,
        extraction_digest,
    )
    audit = verify_partition(
        read_rows(audit_path),
        "test",
        200000,
        threshold,
        archive_digest,
        extraction_digest,
    )
    if validation["row_ids"] & audit["row_ids"]:
        raise ValueError("validation and audit row IDs overlap")
    if validation["image_ids"] & audit["image_ids"]:
        raise ValueError("validation and audit image IDs overlap")
    manifest_validation = manifest["partitions"][
        "configuration_validation"
    ]
    manifest_audit = manifest["partitions"]["locked_audit_test"]
    if manifest_validation["sha256"] != \
            "sha256:" + sha256_path(validation_path) or \
            manifest_audit["sha256"] != \
            "sha256:" + sha256_path(audit_path):
        raise ValueError("partition manifest digest mismatch")
    for summary, expected in (
        (validation, manifest_validation),
        (audit, manifest_audit),
    ):
        for field in ("rows", "images", "positive", "negative"):
            if summary[field] != expected[field]:
                raise ValueError(
                    f"partition summary mismatch for {field}"
                )

    if source_replay:
        archive_path = (REPO_ROOT / archive).resolve()
        image_root_path = (REPO_ROOT / image_root).resolve()
        EXPORTER.verify(
            archive_path,
            image_root_path,
            root,
        )
    print(
        "bsds500_sobel_artifact=PASS "
        f"validation_rows={validation['rows']} "
        f"audit_rows={audit['rows']} "
        f"validation_images={validation['images']} "
        f"audit_images={audit['images']} "
        f"threshold={threshold:.17g} "
        f"policy_digest={extraction_digest} "
        f"source_replay={str(source_replay).lower()}"
    )


def main() -> None:
    args = parse_args()
    root = (REPO_ROOT / args.root).resolve()
    verify(root, args.source_replay, args.archive, args.image_root)


if __name__ == "__main__":
    main()
