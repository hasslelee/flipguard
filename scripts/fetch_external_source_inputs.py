#!/usr/bin/env python3
"""Fetch byte-pinned external datasets for clean-machine source replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tarfile
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "flipguard_external_source_fetch_v1"
SOURCE_SPECS = (
    {
        "source_id": "openml_mnist_784_arff_gzip_v1",
        "path": "results/source_datasets/mnist/mnist_784.arff.gz",
        "url": (
            "https://www.openml.org/data/v1/download/52667/"
            "mnist_784.arff"
        ),
        "request_headers": {"Accept-Encoding": "gzip"},
        "sha256": (
            "fe4410d8dbb50f6db6482b187557c5cb8bccfbcec74eeb6abc47c858f4ffab78"
        ),
        "bytes": 15469256,
    },
    {
        "source_id": "berkeley_bsds500_archive_v1",
        "path": "results/source_datasets/bsds500/BSR_bsds500.tgz",
        "url": (
            "https://www2.eecs.berkeley.edu/Research/Projects/CS/"
            "vision/grouping/BSR/BSR_bsds500.tgz"
        ),
        "request_headers": {},
        "sha256": (
            "97e49d31764f3912f0c4122707d53062ac9e783ba0f095e447a4d53c1a41af8e"
        ),
        "bytes": 70763455,
    },
)
BSDS500_EXTRACTION = {
    "source_id": "berkeley_bsds500_archive_v1",
    "archive_path": (
        "results/source_datasets/bsds500/BSR_bsds500.tgz"
    ),
    "extraction_root": "results/source_datasets/bsds500/BSR",
    "image_root": (
        "results/source_datasets/bsds500/BSR/BSDS500/data/images"
    ),
    "partition_counts": {
        "train": 200,
        "val": 100,
        "test": 200,
    },
}


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    ).encode("ascii")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_source(path: Path, spec: dict[str, Any]) -> None:
    if not path.is_file():
        raise ValueError(f"missing source input: {path}")
    actual_bytes = path.stat().st_size
    if actual_bytes != spec["bytes"]:
        raise ValueError(
            f"{path}: bytes={actual_bytes}; expected {spec['bytes']}"
        )
    actual_digest = sha256_path(path)
    if actual_digest != spec["sha256"]:
        raise ValueError(
            f"{path}: sha256={actual_digest}; "
            f"expected {spec['sha256']}"
        )


def download_once(
    spec: dict[str, Any],
    destination: Path,
    *,
    timeout_seconds: int,
) -> None:
    request = urllib.request.Request(
        spec["url"],
        headers=spec["request_headers"],
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            delete=False,
        ) as output:
            temporary = Path(output.name)
            with urllib.request.urlopen(
                request,
                timeout=timeout_seconds,
            ) as response:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        validate_source(temporary, spec)
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def ensure_source(
    source_root: Path,
    spec: dict[str, Any],
    *,
    attempts: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    destination = source_root / spec["path"]
    if destination.exists():
        validate_source(destination, spec)
        disposition = "EXISTING_VERIFIED"
    else:
        errors = []
        for attempt in range(1, attempts + 1):
            try:
                download_once(
                    spec,
                    destination,
                    timeout_seconds=timeout_seconds,
                )
                break
            except Exception as error:
                errors.append(
                    {
                        "attempt": attempt,
                        "error_type": type(error).__name__,
                        "error": str(error),
                    }
                )
                if attempt == attempts:
                    raise
                time.sleep(attempt)
        validate_source(destination, spec)
        disposition = "DOWNLOADED_VERIFIED"
    return {
        "source_id": spec["source_id"],
        "path": spec["path"],
        "url": spec["url"],
        "request_headers": spec["request_headers"],
        "sha256": spec["sha256"],
        "bytes": spec["bytes"],
        "disposition": disposition,
    }


def validate_bsds500_extraction(source_root: Path) -> dict[str, int]:
    image_root = source_root / BSDS500_EXTRACTION["image_root"]
    counts = {}
    for partition, expected in BSDS500_EXTRACTION[
        "partition_counts"
    ].items():
        root = image_root / partition
        if not root.is_dir():
            raise ValueError(
                f"missing BSDS500 image partition: {root}"
            )
        count = len(list(root.glob("*.jpg")))
        if count != expected:
            raise ValueError(
                f"{root}: images={count}; expected {expected}"
            )
        counts[partition] = count
    return counts


def ensure_bsds500_extraction(source_root: Path) -> dict[str, Any]:
    archive = source_root / BSDS500_EXTRACTION["archive_path"]
    extraction_root = source_root / BSDS500_EXTRACTION["extraction_root"]
    image_root = source_root / BSDS500_EXTRACTION["image_root"]
    if image_root.is_dir():
        disposition = "EXISTING_VERIFIED"
    else:
        if extraction_root.exists():
            raise ValueError(
                "refusing to overwrite incomplete BSDS500 extraction: "
                f"{extraction_root}"
            )
        with tarfile.open(archive, mode="r:gz") as handle:
            handle.extractall(
                archive.parent,
                filter="data",
            )
        disposition = "EXTRACTED_VERIFIED"
    counts = validate_bsds500_extraction(source_root)
    return {
        **BSDS500_EXTRACTION,
        "partition_counts": counts,
        "total_images": sum(counts.values()),
        "disposition": disposition,
    }


def source_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
    ).strip()


def fetch(
    source_root: Path,
    output: Path,
    *,
    attempts: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite source-fetch manifest: {output}"
        )
    started_at = utc_timestamp()
    records = [
        ensure_source(
            source_root,
            spec,
            attempts=attempts,
            timeout_seconds=timeout_seconds,
        )
        for spec in SOURCE_SPECS
    ]
    extractions = [ensure_bsds500_extraction(source_root)]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS",
        "classification": "EXTERNAL_SOURCE_FETCH_ONLY",
        "source_commit": source_commit(),
        "started_at": started_at,
        "ended_at": utc_timestamp(),
        "sources": records,
        "derived_extractions": extractions,
        "encrypted_execution": {
            "candidate_trials": 0,
            "key_runs": 0,
            "sample_evaluations": 0,
        },
        "policy_modifications": 0,
        "paper_claim_allowed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_json(manifest))
    return manifest


def verify(source_root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise ValueError("external source-fetch schema mismatch")
    if manifest["status"] != "PASS":
        raise ValueError("external source-fetch status is not PASS")
    expected_ids = [spec["source_id"] for spec in SOURCE_SPECS]
    actual_ids = [record["source_id"] for record in manifest["sources"]]
    if actual_ids != expected_ids:
        raise ValueError("external source inventory mismatch")
    for spec, record in zip(
        SOURCE_SPECS,
        manifest["sources"],
        strict=True,
    ):
        for key in (
            "source_id",
            "path",
            "url",
            "request_headers",
            "sha256",
            "bytes",
        ):
            if record[key] != spec[key]:
                raise ValueError(f"{spec['source_id']}: {key} mismatch")
        if record["disposition"] not in {
            "DOWNLOADED_VERIFIED",
            "EXISTING_VERIFIED",
        }:
            raise ValueError(
                f"{spec['source_id']}: invalid disposition"
            )
        validate_source(source_root / spec["path"], spec)
    if len(manifest.get("derived_extractions", [])) != 1:
        raise ValueError("external source extraction inventory mismatch")
    extraction = manifest["derived_extractions"][0]
    for key in (
        "source_id",
        "archive_path",
        "extraction_root",
        "image_root",
    ):
        if extraction[key] != BSDS500_EXTRACTION[key]:
            raise ValueError(f"BSDS500 extraction {key} mismatch")
    if extraction["disposition"] not in {
        "EXTRACTED_VERIFIED",
        "EXISTING_VERIFIED",
    }:
        raise ValueError("invalid BSDS500 extraction disposition")
    counts = validate_bsds500_extraction(source_root)
    if extraction["partition_counts"] != counts:
        raise ValueError("BSDS500 extraction counts mismatch")
    if extraction["total_images"] != sum(counts.values()):
        raise ValueError("BSDS500 extraction total mismatch")
    if manifest["encrypted_execution"] != {
        "candidate_trials": 0,
        "key_runs": 0,
        "sample_evaluations": 0,
    }:
        raise ValueError("external source fetch encrypted accounting")
    if manifest["policy_modifications"] != 0:
        raise ValueError("external source fetch modified policy")
    if manifest["paper_claim_allowed"] is not False:
        raise ValueError("external source fetch promoted paper claim")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    if bool(args.output) == bool(args.verify):
        raise ValueError("choose exactly one of --output or --verify")
    source_root = args.source_root.resolve()
    if args.verify:
        manifest = verify(source_root, args.verify.resolve())
        print(
            "external_source_fetch=VERIFIED "
            f"sources={len(manifest['sources'])}"
        )
        return
    if args.attempts < 1:
        raise ValueError("--attempts must be positive")
    manifest = fetch(
        source_root,
        args.output.resolve(),
        attempts=args.attempts,
        timeout_seconds=args.timeout_seconds,
    )
    print(
        "external_source_fetch=PASS "
        f"sources={len(manifest['sources'])}"
    )


if __name__ == "__main__":
    main()
