#!/usr/bin/env python3
"""Freeze or verify the Security V2 bounded-oracle and planner evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SECURITY_ROOT = Path(
    "results/thesis_grade_protocol/security_v2_static_attestation"
)
DEFAULT_PLANNER_ROOT = Path(
    "results/thesis_grade_protocol/"
    "planner_oracle_comparison_security_v2"
)
DEFAULT_OUTPUT = Path(
    "docs/evidence/security_v2_bounded_oracle_v1"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--security-root", type=Path, default=DEFAULT_SECURITY_ROOT
    )
    parser.add_argument(
        "--planner-root", type=Path, default=DEFAULT_PLANNER_ROOT
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-commit")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256(path).encode("ascii"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def validate_content(root: Path) -> None:
    summary = load_json(root / "oracle/summary.json")
    required = {
        "raw_catalog_executions": 1100,
        "security_admitted_catalog_candidates": 700,
        "security_excluded_catalog_candidates": 400,
        "development_catalog_candidates": 140,
        "confirmatory_catalog_candidates": 560,
    }
    for key, expected in required.items():
        if summary.get(key) != expected:
            raise ValueError(f"bounded oracle {key} changed")
    certificates = read_csv(root / "oracle/candidate_certificates.csv")
    identities = {
        (
            row["split_seed"],
            row["dataset_id"],
            row["model_id"],
            row["profile"],
            row["path"],
        )
        for row in certificates
    }
    if len(certificates) != 3500 or len(identities) != 700:
        raise ValueError("bounded oracle filtered candidate matrix changed")
    oracle_rows = read_csv(root / "oracle/oracle_selection.csv")
    if len(oracle_rows) != 250 or any(
        row["candidate_count"] != "14" for row in oracle_rows
    ):
        raise ValueError("bounded oracle selection matrix changed")
    planner = load_json(root / "planner/derived_metrics.json")
    if planner["all"]["rows"] != 250:
        raise ValueError("filtered planner row count changed")


def generate(
    security_root: Path,
    planner_root: Path,
    output: Path,
    source_commit: str,
) -> None:
    if output.exists():
        raise ValueError(f"{output} exists; use --force")
    output.mkdir(parents=True)
    oracle_source = security_root / "bounded_oracle_security_v2"
    oracle_files = (
        "candidate_certificates.csv",
        "candidate_certificates_security_v2.csv",
        "oracle_selection.csv",
        "oracle_selection_security_v2.csv",
        "selection_changes_security_v2.csv",
        "summary.json",
        "validation_coverage.csv",
    )
    planner_files = (
        "comparison.csv",
        "planner_candidates.csv",
        "planner_summary.csv",
        "summary.json",
        "derived_metrics.json",
        "manifest.json",
    )
    for name in oracle_files:
        destination = output / "oracle" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(oracle_source / name, destination)
    for name in planner_files:
        destination = output / "planner" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(planner_root / name, destination)
    validate_content(output)
    security_manifest = load_json(security_root / "manifest.json")
    manifest = {
        "schema_version": 1,
        "evidence_id": "security_v2_bounded_oracle_v1",
        "status": "PARTIALLY_SUPPORTED",
        "paper_claim_allowed": False,
        "block_reason": (
            "final clean-source direct and paired evidence are not yet bound"
        ),
        "source_commit": source_commit,
        "security_policy_id": security_manifest["security_policy_id"],
        "security_policy_digest": security_manifest[
            "security_policy_digest"
        ],
        "direct_policy_id": security_manifest["direct_policy_id"],
        "direct_policy_digest": security_manifest["direct_policy_digest"],
        "counts": {
            "raw_catalog_executions": 1100,
            "security_admitted_catalog_candidates": 700,
            "security_excluded_catalog_candidates": 400,
            "development_catalog_candidates": 140,
            "confirmatory_catalog_candidates": 560,
        },
        "source_trees": {
            "security": {
                "path": str(security_root.relative_to(REPO_ROOT)),
                "sha256": tree_digest(security_root),
            },
            "planner": {
                "path": str(planner_root.relative_to(REPO_ROOT)),
                "sha256": tree_digest(planner_root),
            },
        },
        "files": {},
    }
    files = {
        str(path.relative_to(output)): {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    manifest["files"] = files
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify(output: Path) -> None:
    manifest = load_json(output / "manifest.json")
    for relative, expected in manifest["files"].items():
        path = output / relative
        if (
            not path.is_file()
            or path.stat().st_size != expected["bytes"]
            or sha256(path) != expected["sha256"]
        ):
            raise ValueError(f"{path}: evidence digest changed")
    for item in manifest["source_trees"].values():
        root = REPO_ROOT / item["path"]
        if tree_digest(root) != item["sha256"]:
            raise ValueError(f"{root}: source tree digest changed")
    validate_content(output)
    print(
        "security_v2_bounded_oracle_evidence=VERIFIED "
        "raw=1100 admitted=700 excluded=400 planner_rows=250"
    )


def main() -> int:
    args = parse_args()
    security_root = (REPO_ROOT / args.security_root).resolve()
    planner_root = (REPO_ROOT / args.planner_root).resolve()
    output = (REPO_ROOT / args.output_root).resolve()
    if args.verify:
        verify(output)
        return 0
    if output.exists() and args.force:
        shutil.rmtree(output)
    source_commit = args.source_commit
    if not source_commit:
        source_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
    generate(security_root, planner_root, output, source_commit)
    verify(output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
