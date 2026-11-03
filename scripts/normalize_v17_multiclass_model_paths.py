#!/usr/bin/env python3
"""Normalize non-semantic local paths in unfrozen V17 model artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/model_family_expansion_v17/plaintext/multiclass_training_seed"


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def normalize_path(value: str) -> str:
    path = Path(value)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError as exc:
        raise RuntimeError(f"path is outside repository: {value}") from exc


def semantic_digest(model: dict) -> str:
    copy = json.loads(json.dumps(model))
    copy["source"]["path"] = "<NORMALIZED_PATH>"
    split_field = "split_manifest" if "split_manifest" in copy else "input_split_manifest"
    copy[split_field]["path"] = "<NORMALIZED_PATH>"
    payload = json.dumps(copy, sort_keys=True, separators=(",", ":")).encode("ascii")
    return sha(payload)


def main() -> None:
    summary_path = OUT / "summary.json"
    status_path = OUT / "run_status.csv"
    summary = json.loads(summary_path.read_text(encoding="ascii"))
    records = []
    current_hashes = {}
    for item in summary["records"]:
        path = ROOT / item["model_path"]
        before = path.read_bytes()
        model = json.loads(before)
        before_semantic = semantic_digest(model)
        changes = []
        split_field = "split_manifest" if "split_manifest" in model else "input_split_manifest"
        for object_name in ("source", split_field):
            binding = model[object_name]
            original = binding["path"]
            normalized = normalize_path(original)
            if original != normalized:
                binding["path"] = normalized
                changes.append({"field": f"{object_name}.path", "before_was_absolute": True, "after": normalized})
        after = (json.dumps(model, indent=2, sort_keys=True) + "\n").encode("ascii")
        path.write_bytes(after)
        item["model_sha256"] = sha(after)
        current_hashes[item["model_path"]] = sha(after)
        records.append({
            "path": item["model_path"],
            "before_sha256": sha(before),
            "after_sha256": sha(after),
            "semantic_sha256": before_semantic,
            "semantic_sha256_after": semantic_digest(model),
            "changed_fields": changes,
            "numeric_payload_unchanged": True,
        })
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="ascii")
    status_before = status_path.read_bytes()
    with status_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        status_rows = list(reader)
    for row in status_rows:
        if row["model_path"] in current_hashes:
            row["model_sha256"] = current_hashes[row["model_path"]]
    temporary = status_path.with_suffix(".csv.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(status_rows)
    temporary.replace(status_path)
    manifest = {
        "schema_version": "flipguard_v17_multiclass_path_normalization_v1",
        "allowed_fields": ["source.path", "split_manifest.path"],
        "model_count": len(records),
        "records": records,
        "summary_sha256": sha(summary_path.read_bytes()),
        "run_status_sha256_before": sha(status_before),
        "run_status_sha256_after": sha(status_path.read_bytes()),
    }
    manifest_path = OUT / "path_normalization_manifest.json"
    if manifest_path.exists():
        raise FileExistsError(manifest_path)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": "PASS", "models": len(records), "manifest_sha256": sha(manifest_path.read_bytes())}, sort_keys=True))


if __name__ == "__main__":
    main()
