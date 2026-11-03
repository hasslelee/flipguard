#!/usr/bin/env python3
"""Bind V17 selection/evaluation roles to the existing locked-audit schema."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "results/model_family_expansion_v17/plaintext"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def row_ids(path: Path) -> list[str]:
    with path.open(newline="", encoding="ascii") as handle:
        return [row["row_id"] for row in csv.DictReader(handle)]


def main() -> None:
    created = 0
    for source_manifest_path in sorted(ROOT.rglob("manifest.json")):
        source = json.loads(source_manifest_path.read_text(encoding="ascii"))
        directory = source_manifest_path.parent
        output = directory / "locked_split_manifest.json"
        if output.exists():
            raise SystemExit(f"refusing to overwrite {output}")
        selection = directory / "configuration_selection.csv"
        evaluation = directory / "independent_evaluation.csv"
        split_id = (
            f"v17_{source['role']}_{source['dataset_id']}_{source['model_id']}_"
            f"fold{source['outer_fold']}_trainseed{source['training_seed']}"
        )
        payload = {
            "schema_version": 1,
            "split_seed": int(source["outer_fold"]),
            "split_id": split_id,
            "dataset_id": source["dataset_id"],
            "model_id": source["model_id"],
            "model_artifact_digest": source["model_sha256"],
            "configuration_validation": {
                "path": selection.relative_to(REPO).as_posix(),
                "csv_digest": digest(selection),
                "row_ids": row_ids(selection),
            },
            "locked_audit_test": {
                "path": evaluation.relative_to(REPO).as_posix(),
                "csv_digest": digest(evaluation),
                "row_ids": row_ids(evaluation),
            },
            "v17_role": source["role"],
            "training_partition_sha256": source["roles"]["model_training"]["sha256"],
            "row_overlap": 0,
        }
        output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="ascii",
        )
        created += 1
    print(json.dumps({"status": "PASS", "locked_split_manifests": created}, sort_keys=True))


if __name__ == "__main__":
    main()
