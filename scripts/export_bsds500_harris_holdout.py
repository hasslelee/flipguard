#!/usr/bin/env python3
"""Export a deterministic BSDS500 Harris decision-integrity holdout."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE = Path(
    "results/source_datasets/bsds500/BSR_bsds500.tgz"
)
DEFAULT_IMAGE_ROOT = Path(
    "results/source_datasets/bsds500/BSR/BSDS500/data/images"
)
DEFAULT_OUTPUT = Path(
    "datasets/vision_suite/bsds500/harris_corner_response"
)
LOGICAL_OUTPUT = DEFAULT_OUTPUT

SCHEMA_VERSION = "flipguard_bsds500_harris_holdout_v1"
EXTRACTION_POLICY_ID = "bsds500_harris_patch_extraction_v1"
MODEL_ID = "harris_corner_response"
MODEL_TYPE = "harris_corner_response"
ARCHIVE_URL = (
    "https://www2.eecs.berkeley.edu/Research/Projects/CS/vision/"
    "grouping/BSR/BSR_bsds500.tgz"
)
EXPECTED_ARCHIVE_SHA256 = (
    "97e49d31764f3912f0c4122707d53062ac9e783ba0f095e447a4d53c1a41af8e"
)
TRAIN_IMAGES = 100
VALIDATION_IMAGES = 50
AUDIT_IMAGES = 50
PATCHES_PER_IMAGE = 4
THRESHOLD_QUANTILE = 0.80
HARRIS_K = 0.04

PIXEL_COLUMNS = tuple(
    f"p{row}{column}"
    for row in range(5)
    for column in range(5)
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--image-root", type=Path, default=DEFAULT_IMAGE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        + "\n"
    ).encode("ascii")


def policy_spec() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_id": EXTRACTION_POLICY_ID,
        "source_dataset": "BSDS500",
        "source_url": ARCHIVE_URL,
        "source_archive_sha256": EXPECTED_ARCHIVE_SHA256,
        "image_selection": {
            "method": "sha256_rank_v1",
            "train_images": TRAIN_IMAGES,
            "configuration_validation_images": VALIDATION_IMAGES,
            "locked_audit_images": AUDIT_IMAGES,
        },
        "patch_selection": {
            "method": "sha256_coordinate_stream_without_replacement_v1",
            "patch_size": [5, 5],
            "patches_per_image": PATCHES_PER_IMAGE,
            "border_pixels": 2,
        },
        "pixel_transform": {
            "method": "bt601_integer_luma_normalized_v1",
            "formula": "(299*R + 587*G + 114*B) / 255000",
            "range": [0.0, 1.0],
        },
        "score": {
            "formula": "det(M)-k*trace(M)^2",
            "k": HARRIS_K,
            "window": "3x3 Sobel gradients within one 5x5 patch",
            "sxx": "sum(Ix^2)",
            "syy": "sum(Iy^2)",
            "sxy": "sum(Ix*Iy)",
        },
        "threshold": {
            "source_partition": "train",
            "quantile": THRESHOLD_QUANTILE,
            "method": "nearest_rank_ceil_v1",
        },
        "roles": {
            "train": "threshold_calibration_only",
            "val": "configuration_validation",
            "test": "locked_audit_no_retuning",
        },
    }


def policy_digest() -> str:
    return "sha256:" + hashlib.sha256(
        canonical_json(policy_spec())
    ).hexdigest()


def rank_images(
    paths: Iterable[Path],
    partition: str,
    count: int,
) -> list[Path]:
    ranked = sorted(
        paths,
        key=lambda path: hashlib.sha256(
            (
                EXTRACTION_POLICY_ID
                + "\0image\0"
                + partition
                + "\0"
                + path.name
            ).encode("ascii")
        ).digest(),
    )
    if len(ranked) < count:
        raise ValueError(
            f"partition {partition} has {len(ranked)} images, need {count}"
        )
    return ranked[:count]


def patch_centers(
    image_id: str,
    partition: str,
    width: int,
    height: int,
    count: int,
) -> list[tuple[int, int]]:
    if width < 5 or height < 5:
        raise ValueError(f"image {image_id} is smaller than 5x5")
    available = (width - 4) * (height - 4)
    if available < count:
        raise ValueError(
            f"image {image_id} has only {available} valid patch centers"
        )

    centers: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    counter = 0
    while len(centers) < count:
        digest = hashlib.sha256(
            (
                EXTRACTION_POLICY_ID
                + "\0patch\0"
                + partition
                + "\0"
                + image_id
                + "\0"
                + str(counter)
            ).encode("ascii")
        ).digest()
        x = 2 + int.from_bytes(digest[:8], "big") % (width - 4)
        y = 2 + int.from_bytes(digest[8:16], "big") % (height - 4)
        center = (x, y)
        if center not in seen:
            seen.add(center)
            centers.append(center)
        counter += 1
    return centers


def normalized_luma(pixel: tuple[int, int, int]) -> float:
    red, green, blue = pixel
    return (
        299 * red + 587 * green + 114 * blue
    ) / 255000.0


def harris_components(values: list[float]) -> dict[str, float]:
    if len(values) != 25:
        raise ValueError("Harris patch must contain exactly 25 pixels")

    def pixel(row: int, column: int) -> float:
        return values[row * 5 + column]

    sxx = 0.0
    syy = 0.0
    sxy = 0.0
    for row in range(1, 4):
        for column in range(1, 4):
            gx = (
                -pixel(row - 1, column - 1)
                + pixel(row - 1, column + 1)
                - 2.0 * pixel(row, column - 1)
                + 2.0 * pixel(row, column + 1)
                - pixel(row + 1, column - 1)
                + pixel(row + 1, column + 1)
            )
            gy = (
                -pixel(row - 1, column - 1)
                - 2.0 * pixel(row - 1, column)
                - pixel(row - 1, column + 1)
                + pixel(row + 1, column - 1)
                + 2.0 * pixel(row + 1, column)
                + pixel(row + 1, column + 1)
            )
            sxx += gx * gx
            syy += gy * gy
            sxy += gx * gy
    determinant = sxx * syy - sxy * sxy
    trace = sxx + syy
    score = determinant - HARRIS_K * trace * trace
    return {
        "plaintext_sxx": sxx,
        "plaintext_syy": syy,
        "plaintext_sxy": sxy,
        "plaintext_determinant": determinant,
        "plaintext_trace": trace,
        "plaintext_score": score,
    }


def image_rows(
    paths: list[Path],
    partition: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    row_id = {
        "train": 0,
        "val": 100000,
        "test": 200000,
    }[partition]
    for path in paths:
        image_id = path.stem
        with Image.open(path) as source:
            image = source.convert("RGB")
            centers = patch_centers(
                image_id,
                partition,
                image.width,
                image.height,
                PATCHES_PER_IMAGE,
            )
            for patch_index, (center_x, center_y) in enumerate(centers):
                values = [
                    normalized_luma(
                        image.getpixel(
                            (center_x + column, center_y + row)
                        )
                    )
                    for row in range(-2, 3)
                    for column in range(-2, 3)
                ]
                row: dict[str, Any] = {
                    "row_id": row_id,
                    "image_id": image_id,
                    "source_partition": partition,
                    "patch_index": patch_index,
                    "center_x": center_x,
                    "center_y": center_y,
                }
                row.update(dict(zip(PIXEL_COLUMNS, values, strict=True)))
                row.update(harris_components(values))
                rows.append(row)
                row_id += 1
    return rows


def nearest_rank(values: list[float], quantile: float) -> float:
    if not values:
        raise ValueError("cannot compute threshold from no values")
    if not 0 < quantile <= 1:
        raise ValueError("quantile must be in (0, 1]")
    ordered = sorted(values)
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[index]


def format_float(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError("non-finite output value")
    return format(value, ".17g")


def write_rows(
    path: Path,
    rows: list[dict[str, Any]],
    threshold: float,
) -> None:
    component_fields = [
        "plaintext_sxx",
        "plaintext_syy",
        "plaintext_sxy",
        "plaintext_determinant",
        "plaintext_trace",
        "plaintext_score",
    ]
    fieldnames = [
        "row_id",
        "image_id",
        "source_partition",
        "patch_index",
        "center_x",
        "center_y",
        *PIXEL_COLUMNS,
        *component_fields,
        "decision_threshold",
        "decision_margin",
        "plaintext_decision",
        "source_archive_sha256",
        "extraction_policy_digest",
    ]
    with path.open("w", newline="", encoding="ascii") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            output = {
                key: row[key]
                for key in fieldnames
                if key in row
            }
            for key in (*PIXEL_COLUMNS, *component_fields):
                output[key] = format_float(float(output[key]))
            score = float(row["plaintext_score"])
            output["decision_threshold"] = format_float(threshold)
            output["decision_margin"] = format_float(
                abs(score - threshold)
            )
            output["plaintext_decision"] = (
                "true" if score >= threshold else "false"
            )
            output["source_archive_sha256"] = (
                "sha256:" + EXPECTED_ARCHIVE_SHA256
            )
            output["extraction_policy_digest"] = policy_digest()
            writer.writerow(output)


def describe_rows(
    rows: list[dict[str, Any]],
    threshold: float,
) -> dict[str, Any]:
    scores = [float(row["plaintext_score"]) for row in rows]
    margins = [abs(score - threshold) for score in scores]
    images = {str(row["image_id"]) for row in rows}
    positive = sum(score >= threshold for score in scores)
    return {
        "rows": len(rows),
        "images": len(images),
        "positive": positive,
        "negative": len(rows) - positive,
        "minimum_score": min(scores),
        "maximum_score": max(scores),
        "minimum_margin": min(margins),
        "median_margin": nearest_rank(margins, 0.5),
    }


def build(
    archive: Path,
    image_root: Path,
    output_root: Path,
    force: bool,
) -> None:
    archive_digest = sha256_path(archive)
    if archive_digest != EXPECTED_ARCHIVE_SHA256:
        raise ValueError(
            "BSDS500 archive digest mismatch: "
            f"got {archive_digest}, expected {EXPECTED_ARCHIVE_SHA256}"
        )
    if output_root.exists():
        if not force:
            raise FileExistsError(
                f"{output_root} exists; use --force to replace derived files"
            )
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    selections: dict[str, list[Path]] = {}
    for partition, count in (
        ("train", TRAIN_IMAGES),
        ("val", VALIDATION_IMAGES),
        ("test", AUDIT_IMAGES),
    ):
        paths = sorted((image_root / partition).glob("*.jpg"))
        selections[partition] = rank_images(paths, partition, count)

    train_rows = image_rows(selections["train"], "train")
    validation_rows = image_rows(selections["val"], "val")
    audit_rows = image_rows(selections["test"], "test")
    threshold = nearest_rank(
        [float(row["plaintext_score"]) for row in train_rows],
        THRESHOLD_QUANTILE,
    )

    model = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": "bsds500",
        "dataset_name": "Berkeley Segmentation Data Set 500",
        "model_id": MODEL_ID,
        "model_type": MODEL_TYPE,
        "input_dim": 25,
        "graph_formula": "det(M)-0.04*trace(M)^2",
        "decision_threshold": threshold,
        "threshold_source": {
            "partition": "train",
            "images": TRAIN_IMAGES,
            "patches": len(train_rows),
            "quantile": THRESHOLD_QUANTILE,
            "method": "nearest_rank_ceil_v1",
        },
        "packing_scope": "scalar_replicated_per_ciphertext_v1",
        "source_archive": {
            "url": ARCHIVE_URL,
            "sha256": "sha256:" + EXPECTED_ARCHIVE_SHA256,
        },
        "direct_policy_reference": {
            "policy_id": "flipguard_direct_synthesis_policy_v2",
            "policy_digest": (
                "sha256:"
                "503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
            ),
            "relationship": (
                "frozen_constants_reused_by_predeclared_graph_adapter;"
                "model_type_not_added_to_policy_supported_models"
            ),
        },
        "extraction_policy_id": EXTRACTION_POLICY_ID,
        "extraction_policy_digest": policy_digest(),
    }
    (output_root / "model.json").write_bytes(canonical_json(model))
    write_rows(
        output_root / "configuration_validation.csv",
        validation_rows,
        threshold,
    )
    write_rows(
        output_root / "locked_audit_test.csv",
        audit_rows,
        threshold,
    )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "extraction_policy": policy_spec(),
        "extraction_policy_digest": policy_digest(),
        "source_archive": {
            "path": str(DEFAULT_ARCHIVE),
            "url": ARCHIVE_URL,
            "sha256": "sha256:" + archive_digest,
        },
        "model": {
            "path": str(LOGICAL_OUTPUT / "model.json"),
            "sha256": "sha256:" + sha256_path(output_root / "model.json"),
            "decision_threshold": threshold,
        },
        "partitions": {
            "threshold_calibration_train": {
                **describe_rows(train_rows, threshold),
                "selected_image_ids": [
                    path.stem for path in selections["train"]
                ],
            },
            "configuration_validation": {
                **describe_rows(validation_rows, threshold),
                "path": str(
                    LOGICAL_OUTPUT / "configuration_validation.csv"
                ),
                "sha256": (
                    "sha256:"
                    + sha256_path(
                        output_root / "configuration_validation.csv"
                    )
                ),
                "selected_image_ids": [
                    path.stem for path in selections["val"]
                ],
            },
            "locked_audit_test": {
                **describe_rows(audit_rows, threshold),
                "path": str(LOGICAL_OUTPUT / "locked_audit_test.csv"),
                "sha256": (
                    "sha256:"
                    + sha256_path(output_root / "locked_audit_test.csv")
                ),
                "selected_image_ids": [
                    path.stem for path in selections["test"]
                ],
            },
        },
        "claim_scope": {
            "operator": "single-window Harris response threshold",
            "statistical_unit": "image_cluster",
            "not_claimed": [
                "full_image_corner_detection_accuracy",
                "non_maximum_suppression",
                "arbitrary_CKKS_graph_generalization",
                "CNN_generalization",
            ],
        },
    }
    (output_root / "extraction_manifest.json").write_bytes(
        canonical_json(manifest)
    )

    checksum_paths = (
        "configuration_validation.csv",
        "extraction_manifest.json",
        "locked_audit_test.csv",
        "model.json",
    )
    checksums = "".join(
        f"{sha256_path(output_root / name)}  {name}\n"
        for name in checksum_paths
    )
    (output_root / "SHA256SUMS").write_text(
        checksums,
        encoding="ascii",
    )


def verify(
    archive: Path,
    image_root: Path,
    output_root: Path,
) -> None:
    if not output_root.is_dir():
        raise FileNotFoundError(output_root)
    with tempfile.TemporaryDirectory(
        prefix="flipguard-bsds500-harris-"
    ) as temporary:
        rebuilt = Path(temporary) / "rebuilt"
        build(archive, image_root, rebuilt, force=False)
        expected_names = sorted(
            path.name for path in output_root.iterdir() if path.is_file()
        )
        rebuilt_names = sorted(
            path.name for path in rebuilt.iterdir() if path.is_file()
        )
        if expected_names != rebuilt_names:
            raise ValueError(
                f"artifact file set changed: {expected_names} != {rebuilt_names}"
            )
        for name in expected_names:
            expected = (output_root / name).read_bytes()
            actual = (rebuilt / name).read_bytes()
            if actual != expected:
                raise ValueError(f"artifact replay mismatch: {name}")

    print(
        "bsds500_harris_holdout=PASS "
        f"output={output_root} policy_digest={policy_digest()}"
    )


def main() -> None:
    args = parse_args()
    archive = (REPO_ROOT / args.archive).resolve()
    image_root = (REPO_ROOT / args.image_root).resolve()
    output_root = (REPO_ROOT / args.output_root).resolve()
    if args.verify:
        verify(archive, image_root, output_root)
        return
    build(archive, image_root, output_root, args.force)
    print(
        "bsds500_harris_holdout=BUILT "
        f"output={output_root} policy_digest={policy_digest()}"
    )


if __name__ == "__main__":
    main()
