#!/usr/bin/env python3
"""Replay and verify independent-training-seed extension inputs."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORTER_PATH = (
    REPO_ROOT / "scripts/export_independent_training_seed_extension.py"
)
SPEC = importlib.util.spec_from_file_location(
    "export_independent_training_seed_extension",
    EXPORTER_PATH,
)
EXPORTER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(EXPORTER)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-root",
        type=Path,
        default=EXPORTER.DEFAULT_OUTPUT,
    )
    parser.add_argument("--sklearn-data-root", type=Path)
    return parser.parse_args()


def resolve_suite_path(input_root: Path, logical_path: str) -> Path:
    path = Path(logical_path)
    try:
        relative = path.relative_to(EXPORTER.DEFAULT_OUTPUT)
    except ValueError as exc:
        raise ValueError(
            f"path is outside the frozen suite root: {logical_path}"
        ) from exc
    return input_root / relative


def validate_tree(input_root: Path) -> dict:
    summary = json.loads(
        (input_root / "summary.json").read_text(encoding="ascii")
    )
    if summary["schema_version"] != EXPORTER.SCHEMA_VERSION or \
            summary["policy_id"] != EXPORTER.POLICY_ID or \
            summary["policy_digest"] != \
                EXPORTER.canonical_digest(EXPORTER.POLICY) or \
            summary["dataset_count"] != 3 or \
            summary["training_seed_count"] != 3 or \
            summary["instance_count"] != 9 or \
            summary["model_id"] != EXPORTER.MODEL_ID or \
            summary["paper_claim_allowed"]:
        raise ValueError("independent-seed summary contract changed")

    expected_pairs = {
        (seed, dataset)
        for seed in EXPORTER.SEEDS
        for dataset in EXPORTER.DATASET_IDS
    }
    observed_pairs = set()
    model_digests: dict[str, set[str]] = {
        dataset: set() for dataset in EXPORTER.DATASET_IDS
    }
    for instance in summary["instances"]:
        seed = int(instance["training_seed"])
        dataset = instance["dataset_id"]
        pair = (seed, dataset)
        if pair in observed_pairs or pair not in expected_pairs:
            raise ValueError(f"invalid independent-seed pair {pair}")
        observed_pairs.add(pair)
        model_path = resolve_suite_path(
            input_root,
            instance["model_path"],
        )
        manifest_path = resolve_suite_path(
            input_root,
            instance["split_manifest"],
        )
        if EXPORTER.sha256_path(model_path) != \
                instance["model_sha256"] or \
                EXPORTER.sha256_path(manifest_path) != \
                instance["split_manifest_sha256"]:
            raise ValueError(f"independent-seed digest changed: {pair}")
        model_digests[dataset].add(instance["model_sha256"])
        model = json.loads(model_path.read_text(encoding="ascii"))
        manifest = json.loads(
            manifest_path.read_text(encoding="ascii")
        )
        if model["training_seed"] != seed or \
                model["training_protocol"]["locked_audit_used"] or \
                manifest["training_seed"] != seed or \
                manifest["model_artifact_digest"] != \
                    instance["model_sha256"]:
            raise ValueError(f"model provenance changed: {pair}")
        role_sets = {
            "training": set(
                manifest["model_training"]["row_ids"]
            ),
            "validation": set(
                manifest["configuration_validation"]["row_ids"]
            ),
            "audit": set(
                manifest["locked_audit_test"]["row_ids"]
            ),
        }
        if role_sets["training"] & role_sets["validation"] or \
                role_sets["training"] & role_sets["audit"] or \
                role_sets["validation"] & role_sets["audit"]:
            raise ValueError(f"role overlap changed: {pair}")
        for role_name, manifest_key in (
            ("validation", "configuration_validation"),
            ("audit", "locked_audit_test"),
        ):
            path = resolve_suite_path(
                input_root,
                manifest[manifest_key]["path"],
            )
            if EXPORTER.sha256_path(path) != \
                    manifest[manifest_key]["csv_digest"]:
                raise ValueError(
                    f"{pair}: {role_name} digest changed"
                )
            with path.open(
                newline="",
                encoding="ascii",
            ) as handle:
                rows = list(csv.DictReader(handle))
            if {int(row["row_id"]) for row in rows} != \
                    role_sets[role_name] or \
                    len(rows) != manifest[manifest_key]["row_count"] or \
                    {int(row["label"]) for row in rows} != {0, 1}:
                raise ValueError(
                    f"{pair}: {role_name} identity changed"
                )
    if observed_pairs != expected_pairs:
        raise ValueError("independent-seed matrix is incomplete")
    for dataset, digests in model_digests.items():
        if len(digests) != len(EXPORTER.SEEDS):
            raise ValueError(
                f"{dataset}: training seeds did not produce distinct models"
            )
    return summary


def verify_replay(
    input_root: Path,
    sklearn_data_root: Path | None,
) -> dict:
    summary = validate_tree(input_root)
    with tempfile.TemporaryDirectory(
        prefix="flipguard_independent_seed_replay_"
    ) as temporary:
        replay = Path(temporary) / "suite"
        EXPORTER.build_suite(replay, sklearn_data_root)
        expected = {
            path.relative_to(input_root)
            for path in input_root.rglob("*")
            if path.is_file()
        }
        observed = {
            path.relative_to(replay)
            for path in replay.rglob("*")
            if path.is_file()
        }
        if expected != observed:
            raise ValueError("independent-seed file set changed")
        for relative in sorted(expected):
            if (input_root / relative).read_bytes() != \
                    (replay / relative).read_bytes():
                raise ValueError(
                    f"independent-seed replay changed: {relative}"
                )
    return summary


def main() -> None:
    args = parse_args()
    input_root = (
        args.input_root
        if args.input_root.is_absolute()
        else REPO_ROOT / args.input_root
    )
    summary = verify_replay(
        input_root,
        args.sklearn_data_root,
    )
    print(
        "independent_training_seed_suite=PASS "
        f"instances={summary['instance_count']} "
        f"policy_digest={summary['policy_digest']} "
        f"summary={EXPORTER.sha256_path(input_root / 'summary.json')}"
    )


if __name__ == "__main__":
    main()
