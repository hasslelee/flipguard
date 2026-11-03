#!/usr/bin/env python3
"""Create deterministic, non-claim-bearing V17 smoke subsets."""

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results/model_family_expansion_v17/smoke/inputs"


def rank(domain: str, row: dict[str, str]) -> str:
    identity = row.get("sample_id", row["row_id"])
    return hashlib.sha256(f"{domain}:{identity}".encode("ascii")).hexdigest()


def select(source: Path, destination: Path, domain: str, per_label: int, label_field: str) -> dict:
    with source.open(newline="", encoding="ascii") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    labels = sorted({row[label_field] for row in rows})
    selected = []
    for label in labels:
        candidates = [row for row in rows if row[label_field] == label]
        candidates.sort(key=lambda row: (rank(domain, row), row["row_id"]))
        selected.extend(candidates[:per_label])
    selected.sort(key=lambda row: int(row["row_id"]))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    with destination.open("w", newline="", encoding="ascii") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(selected)
    return {
        "source": source.relative_to(ROOT).as_posix(),
        "source_sha256": "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest(),
        "output": destination.relative_to(ROOT).as_posix(),
        "output_sha256": "sha256:" + hashlib.sha256(destination.read_bytes()).hexdigest(),
        "rows": len(selected),
        "labels": {label: sum(row[label_field] == label for row in selected) for label in labels},
        "ranking_domain": domain,
        "purpose": "SMOKE_ONLY_NOT_CLAIM_BEARING",
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records = [
        select(
            ROOT / "datasets/vision_suite/mnist/cnn_lite_square_binary01/configuration_validation.csv",
            OUTPUT / "packed_cnn_lite_selection_8.csv",
            "v17-packed-cnn-smoke-v1",
            4,
            "binary_label",
        ),
        select(
            ROOT / "datasets/journal_multiclass_extension_v1/mnist/configuration_validation.csv",
            OUTPUT / "multiclass_selection_20.csv",
            "v17-multiclass-smoke-v1",
            2,
            "label",
        ),
    ]
    manifest = OUTPUT / "manifest.json"
    manifest.write_text(json.dumps({"schema_version": "flipguard_v17_smoke_inputs_v1", "subsets": records}, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": "PASS", "subsets": len(records), "rows": [record["rows"] for record in records]}, sort_keys=True))


if __name__ == "__main__":
    main()
