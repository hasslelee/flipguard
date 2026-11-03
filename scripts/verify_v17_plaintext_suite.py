#!/usr/bin/env python3
"""Fail-closed verification for V17 plaintext model and split artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = REPO / "results/model_family_expansion_v17/plaintext"
SCHEMA = "flipguard_model_family_expansion_v17_plaintext_v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def csv_ids(path: Path) -> set[int]:
    with path.open(newline="", encoding="ascii") as handle:
        return {int(row["row_id"]) for row in csv.DictReader(handle)}


def verify(root: Path) -> dict:
    summary = json.loads((root / "summary.json").read_text(encoding="ascii"))
    if summary.get("schema_version") != SCHEMA or summary.get("workloads") != 119:
        raise ValueError("unexpected V17 plaintext summary")
    manifests = sorted(root.rglob("manifest.json"))
    if len(manifests) != 119:
        raise ValueError(f"manifest count {len(manifests)} != 119")
    roles = Counter()
    primary = Counter()
    training_seed_keys = set()
    for path in manifests:
        data = json.loads(path.read_text(encoding="ascii"))
        if data.get("schema_version") != SCHEMA or data.get("row_overlap") != 0:
            raise ValueError(f"invalid schema/overlap: {path}")
        role = data["role"]
        roles[role] += 1
        if role == "primary":
            primary[data["model_id"]] += 1
        if role == "training_seed":
            training_seed_keys.add((data["model_id"], data["dataset_id"], data["training_seed"]))
        model_path = REPO / data["model_path"]
        if sha256(model_path) != data["model_sha256"]:
            raise ValueError(f"model digest mismatch: {path}")
        locked_path = path.parent / "locked_split_manifest.json"
        if not locked_path.exists():
            raise ValueError(f"missing locked split manifest: {locked_path}")
        locked = json.loads(locked_path.read_text(encoding="ascii"))
        expected_split_id = (
            f"v17_{data['role']}_{data['dataset_id']}_{data['model_id']}_"
            f"fold{data['outer_fold']}_trainseed{data['training_seed']}"
        )
        if locked.get("split_id") != expected_split_id or locked.get("row_overlap") != 0:
            raise ValueError(f"invalid locked split identity: {locked_path}")
        if locked.get("model_artifact_digest") != data["model_sha256"]:
            raise ValueError(f"locked split model digest mismatch: {locked_path}")
        role_ids = {}
        for role_name, record in data["roles"].items():
            csv_path = path.parent / f"{role_name}.csv"
            if sha256(csv_path) != record["sha256"]:
                raise ValueError(f"CSV digest mismatch: {csv_path}")
            ids = csv_ids(csv_path)
            if len(ids) != record["rows"] or ids != set(record["row_ids"]):
                raise ValueError(f"CSV row identity mismatch: {csv_path}")
            role_ids[role_name] = ids
        if set(locked["configuration_validation"]["row_ids"]) != {
            str(value) for value in role_ids["configuration_selection"]
        }:
            raise ValueError(f"locked selection IDs mismatch: {locked_path}")
        if set(locked["locked_audit_test"]["row_ids"]) != {
            str(value) for value in role_ids["independent_evaluation"]
        }:
            raise ValueError(f"locked evaluation IDs mismatch: {locked_path}")
        names = sorted(role_ids)
        for left_index, left in enumerate(names):
            for right in names[left_index + 1 :]:
                if role_ids[left] & role_ids[right]:
                    raise ValueError(f"role leakage in {path}: {left}/{right}")
        quality = data["quality_independent_evaluation"]
        for field in ("accuracy", "balanced_accuracy", "macro_f1", "auroc"):
            if not 0 <= float(quality[field]) <= 1:
                raise ValueError(f"invalid quality metric {field}: {path}")
    if roles != Counter(primary=65, ablation=30, training_seed=24):
        raise ValueError(f"unexpected role counts: {roles}")
    if primary != Counter(
        linear_poly3=25,
        mlp_square_linear_score=25,
        mlp_square2_linear_score=15,
    ):
        raise ValueError(f"unexpected primary counts: {primary}")
    expected_training = {
        (model, dataset, seed)
        for model in ("mlp_square_linear_score", "mlp_square2_linear_score")
        for dataset in ("banknote", "mnist_pool16", "wdbc")
        for seed in (1, 2, 3, 4)
    }
    if training_seed_keys != expected_training:
        raise ValueError("training-seed matrix incomplete")
    return {
        "status": "PASS",
        "workloads": len(manifests),
        "roles": dict(sorted(roles.items())),
        "primary": dict(sorted(primary.items())),
        "role_overlap": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    print(json.dumps(verify(args.root.resolve()), sort_keys=True))


if __name__ == "__main__":
    main()
