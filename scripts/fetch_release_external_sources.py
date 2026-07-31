#!/usr/bin/env python3
"""Fetch an explicitly licensed external source and verify its checksum."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "release/external_sources_v1.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def entries() -> dict[str, dict[str, object]]:
    value = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {entry["dataset_id"]: entry for entry in value["sources"]}


def download_source(
    record: dict[str, object],
    destination: Path,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> None:
    headers: dict[str, str] = {}
    required_encoding = record.get("required_content_encoding")
    if required_encoding is not None:
        headers["Accept-Encoding"] = str(required_encoding)
    request = urllib.request.Request(str(record["source_url"]), headers=headers)
    with opener(request) as response, destination.open("wb") as handle:
        if required_encoding is not None:
            observed = response.headers.get("Content-Encoding")
            if observed != required_encoding:
                raise ValueError(
                    "downloaded source content-encoding mismatch: "
                    f"expected {required_encoding}, observed {observed}"
                )
        shutil.copyfileobj(response, handle, length=1024 * 1024)


def verify_download(record: dict[str, object], source: Path) -> None:
    expected = str(record["expected_sha256"])
    if sha256(source) != expected:
        raise ValueError("downloaded source checksum mismatch")
    uncompressed_expected = record.get("uncompressed_sha256")
    if uncompressed_expected is not None:
        digest = hashlib.sha256()
        with gzip.open(source, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != uncompressed_expected:
            raise ValueError("downloaded uncompressed content checksum mismatch")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    registry = entries()
    if args.dataset not in registry:
        raise ValueError(f"unknown dataset: {args.dataset}")
    record = registry[args.dataset]
    destination = ROOT / str(record["local_raw_path"])
    expected = str(record["expected_sha256"])
    if args.verify_existing:
        if not destination.is_file() or sha256(destination) != expected:
            raise ValueError(f"{destination}: missing or checksum mismatch")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=destination.parent, delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
        try:
            download_source(record, temporary_path)
            verify_download(record, temporary_path)
            temporary_path.replace(destination)
        finally:
            temporary_path.unlink(missing_ok=True)
    print(f"{args.dataset}=VERIFIED sha256:{expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
