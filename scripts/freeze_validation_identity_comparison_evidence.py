#!/usr/bin/env python3
"""Freeze validation identity and strict comparator-v2 evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_IDENTITY_ROOT = Path(
    "results/thesis_grade_protocol/validation_identity_audit_v2"
)
DEFAULT_COMPARISON_ROOT = Path(
    "results/thesis_grade_protocol/direct_vs_catalog_oracle_v2/"
    "final_source_baseline"
)
DEFAULT_OUTPUT_ROOT = Path(
    "docs/evidence/validation_identity_comparison_v2"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--identity-root",
        type=Path,
        default=DEFAULT_IDENTITY_ROOT,
    )
    parser.add_argument(
        "--comparison-root",
        type=Path,
        default=DEFAULT_COMPARISON_ROOT,
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path, prefix: bool = True) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    value = digest.hexdigest()
    return f"sha256:{value}" if prefix else value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected an object")
    return value


def canonical_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def prepare_output(path: Path, force: bool) -> None:
    if path.exists():
        if not force:
            raise ValueError(f"{path} exists; use --force")
        shutil.rmtree(path)
    (path / "identity").mkdir(parents=True)
    (path / "comparison").mkdir(parents=True)


def copy_inputs(args: argparse.Namespace) -> None:
    for name in (
        "validation_identity_matrix.csv",
        "mismatch_details.json",
        "summary.json",
        "verify_validation_identity_audit.py",
        "SHA256SUMS",
    ):
        shutil.copyfile(
            args.identity_root / name,
            args.output_root / "identity" / name,
        )
    for name in ("comparison.csv", "summary.json"):
        shutil.copyfile(
            args.comparison_root / name,
            args.output_root / "comparison" / name,
        )
    shutil.copyfile(
        Path(__file__).with_name(
            "verify_validation_identity_comparison_evidence.py"
        ),
        args.output_root / "verify_evidence.py",
    )


def write_sums(root: Path) -> None:
    files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path != root / "SHA256SUMS"
    )
    (root / "SHA256SUMS").write_text(
        "".join(
            f"{sha256_file(path, prefix=False)}  "
            f"{path.relative_to(root)}\n"
            for path in files
        ),
        encoding="utf-8",
    )


def generate(args: argparse.Namespace) -> int:
    identity = load_json(args.identity_root / "summary.json")
    comparison = load_json(args.comparison_root / "summary.json")
    if identity.get("encrypted_rerun_required_workloads") != 0:
        raise ValueError("identity audit requires an encrypted rerun")
    if identity.get("identity_class_counts") != {
        "SOURCE_AND_SEMANTICS_MATCH_PREPARED_BYTES_DIFFER": 50
    }:
        raise ValueError("only the completed 50-row CLASS A audit may freeze")
    if (
        comparison.get("schema_version") != 2
        or comparison.get("complete_oracle_workloads_compared") != 50
        or comparison.get("security_admitted_catalog_candidates") != 700
    ):
        raise ValueError("strict comparator v2 is incomplete")
    prepare_output(args.output_root, args.force)
    copy_inputs(args)
    manifest = {
        "schema_version": 1,
        "evidence_id": "validation_identity_comparison_v2",
        "status": "SUPPORTED_CLASS_A_NO_RERUN",
        "paper_claim_allowed": False,
        "block_reason": (
            "remaining confirmatory NO_SAFE, structural, and paired-latency "
            "stages have not resumed"
        ),
        "original_failure_reason_code":
            "VALIDATION_IDENTITY_UNRESOLVED_FAIL_CLOSED",
        "encrypted_execution_commit": identity[
            "execution_source_commit"
        ],
        "comparator_commit": comparison["comparison_builder_commit"],
        "identity_class_counts": identity["identity_class_counts"],
        "encrypted_rerun_required_workloads": 0,
        "raw_catalog_executions": 1100,
        "security_admitted_catalog_candidates": 700,
        "security_excluded_catalog_candidates": 400,
        "security_policy_id": comparison["security_policy_id"],
        "security_policy_digest": comparison["security_policy_digest"],
        "direct_policy_id": comparison["direct_policy_id"],
        "direct_policy_digest": comparison["direct_policy_digest"],
        "preserved_evidence_manifests": identity[
            "preserved_evidence_manifests"
        ],
        "source_roots": {
            "identity": {
                "path": str(args.identity_root),
                "summary_sha256": sha256_file(
                    args.identity_root / "summary.json"
                ),
            },
            "comparison": {
                "path": str(args.comparison_root),
                "summary_sha256": sha256_file(
                    args.comparison_root / "summary.json"
                ),
            },
        },
    }
    canonical_json(args.output_root / "manifest.json", manifest)
    write_sums(args.output_root)
    subprocess.run(
        [
            sys.executable,
            str(args.output_root / "verify_evidence.py"),
            str(args.output_root),
        ],
        check=True,
    )
    print(
        "validation_identity_comparison_evidence=FROZEN "
        f"output={args.output_root}"
    )
    return 0


def verify(args: argparse.Namespace) -> int:
    subprocess.run(
        [
            sys.executable,
            str(args.output_root / "verify_evidence.py"),
            str(args.output_root),
        ],
        check=True,
    )
    with tempfile.TemporaryDirectory(
        prefix="flipguard-validation-comparison-evidence-",
        dir="/tmp",
    ) as temporary:
        regenerated = Path(temporary) / "evidence"
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--identity-root",
                str(args.identity_root),
                "--comparison-root",
                str(args.comparison_root),
                "--output-root",
                str(regenerated),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        existing = {
            path.relative_to(args.output_root): path.read_bytes()
            for path in args.output_root.rglob("*")
            if path.is_file()
        }
        rebuilt = {
            path.relative_to(regenerated): path.read_bytes()
            for path in regenerated.rglob("*")
            if path.is_file()
        }
        if existing != rebuilt:
            raise ValueError("deterministic evidence regeneration changed")
    print("validation_identity_comparison_evidence=DETERMINISTIC_PASS")
    return 0


def main() -> int:
    args = parse_args()
    if args.verify:
        if args.force:
            raise ValueError("--verify and --force are mutually exclusive")
        return verify(args)
    return generate(args)


if __name__ == "__main__":
    raise SystemExit(main())
