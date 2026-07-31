#!/usr/bin/env python3
"""Fetch an explicitly licensed external source and verify its checksum."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import tempfile
import urllib.request
from pathlib import Path


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
            transport = temporary_path.with_suffix(".transport")
            urllib.request.urlretrieve(str(record["source_url"]), transport)
            transport_expected = record.get("source_transport_sha256")
            if (
                transport_expected is not None
                and sha256(transport) != transport_expected
            ):
                raise ValueError("downloaded transport checksum mismatch")
            if record.get("transport_transform") == "gzip_compresslevel9_mtime0":
                with (
                    transport.open("rb") as source,
                    temporary_path.open("wb") as raw_destination,
                    gzip.GzipFile(
                        filename="",
                        mode="wb",
                        fileobj=raw_destination,
                        compresslevel=9,
                        mtime=0,
                    ) as destination_handle,
                ):
                    for chunk in iter(
                        lambda: source.read(1024 * 1024), b""
                    ):
                        destination_handle.write(chunk)
            else:
                transport.replace(temporary_path)
            transport.unlink(missing_ok=True)
            if sha256(temporary_path) != expected:
                raise ValueError("downloaded source checksum mismatch")
            temporary_path.replace(destination)
        finally:
            temporary_path.unlink(missing_ok=True)
    print(f"{args.dataset}=VERIFIED sha256:{expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
