#!/usr/bin/env python3
"""Freeze or verify the combined final-confirmatory evidence index."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path("docs/evidence/final_confirmatory_suite_v1")
RUN_MANIFEST = Path(
    "results/thesis_grade_protocol/final_confirmatory_suite_v1/"
    "run_manifest/run_manifest.json"
)
FINAL_COMPARISON = Path(
    "results/thesis_grade_protocol/direct_vs_catalog_oracle_v1/"
    "final_source_baseline"
)
PACKS = {
    "direct_confirmatory": Path(
        "docs/evidence/direct_locked_audit_final_source_v1"
    ),
    "direct_development": Path(
        "docs/evidence/direct_locked_audit_seed0_development_v1"
    ),
    "no_safe": Path(
        "docs/evidence/no_safe_controls_confirmatory_v1"
    ),
    "structural": Path("docs/evidence/structural_extension_v1"),
    "paired": Path("docs/evidence/paired_latency_final_v1"),
    "security": Path(
        "docs/evidence/security_v2_static_attestation_formal_v2"
    ),
    "bounded_oracle": Path(
        "docs/evidence/security_v2_bounded_oracle_v1"
    ),
    "policy_sensitivity": Path(
        "docs/evidence/policy_sensitivity_v1"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
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


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def generate(output: Path) -> None:
    if output.exists():
        raise ValueError(f"{output} exists; use --force")
    output.mkdir(parents=True)
    run_manifest_path = REPO_ROOT / RUN_MANIFEST
    run_manifest = load_json(run_manifest_path)
    pack_records = {}
    snapshot_sources = {"run_manifest": run_manifest_path}
    for name, relative in PACKS.items():
        root = REPO_ROOT / relative
        manifest_path = root / "manifest.json"
        if not manifest_path.is_file():
            raise ValueError(f"missing final evidence pack {root}")
        manifest = load_json(manifest_path)
        pack_records[name] = {
            "path": str(relative),
            "tree_sha256": tree_digest(root),
            "manifest_sha256": sha256(manifest_path),
            "status": manifest.get(
                "status", manifest.get("classification", "")
            ),
            "paper_claim_allowed": bool(
                manifest.get(
                    "paper_claim_allowed",
                    manifest.get("paper_latency_claim_allowed", False),
                )
            ),
        }
        snapshot_sources[f"{name}_manifest"] = manifest_path
    comparison_summary_path = (
        REPO_ROOT / FINAL_COMPARISON / "summary.json"
    )
    comparison_csv_path = (
        REPO_ROOT / FINAL_COMPARISON / "comparison.csv"
    )
    comparison = load_json(comparison_summary_path)
    required_counts = {
        "raw_catalog_executions": 1100,
        "security_admitted_catalog_candidates": 700,
        "security_excluded_catalog_candidates": 400,
        "development_catalog_candidates": 140,
        "confirmatory_catalog_candidates": 560,
    }
    for key, expected in required_counts.items():
        if comparison.get(key) != expected:
            raise ValueError(f"final comparison {key} changed")
    snapshot_sources["final_comparison_summary"] = (
        comparison_summary_path
    )
    snapshot_sources["final_comparison_rows"] = comparison_csv_path
    snapshot_dir = output / "snapshots"
    for name, source in snapshot_sources.items():
        suffix = source.suffix or ".json"
        destination = snapshot_dir / f"{name}{suffix}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    claims = {
        "direct_synthesis": "SUPPORTED",
        "adaptive_repair": "PARTIALLY_SUPPORTED",
        "decision_integrity_certification": "PARTIALLY_SUPPORTED",
        "trial_reduction": "SUPPORTED",
        "bounded_catalog_comparison": "SUPPORTED",
        "latency": "PARTIALLY_SUPPORTED",
        "security": "PARTIALLY_SUPPORTED",
        "locked_audit": "SUPPORTED",
        "structural_generalization": "PARTIALLY_SUPPORTED",
        "conditional_analytical": "BLOCKED",
    }
    (output / "claim_states.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "paper_claim_allowed": False,
                "block_reason": (
                    "manual post-suite claim admission and paper review "
                    "have not been performed"
                ),
                "states": claims,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "evidence_id": "final_confirmatory_suite_v1",
        "status": "PARTIALLY_SUPPORTED",
        "paper_claim_allowed": False,
        "block_reason": (
            "manual post-suite claim admission and paper review have not "
            "been performed"
        ),
        "execution_source_commit": run_manifest[
            "execution_source_commit"
        ],
        "run_manifest": {
            "path": str(RUN_MANIFEST),
            "sha256": sha256(run_manifest_path),
        },
        "security_policy": run_manifest["security_policy"],
        "direct_policy": run_manifest["direct_policy"],
        "catalog_accounting": required_counts,
        "formal_trial_accounting": {
            key: comparison[key]
            for key in (
                "direct_trials_all",
                "direct_trials_development",
                "direct_trials_confirmatory",
                "formal_trial_reduction_all",
                "formal_trial_reduction_confirmatory",
            )
        },
        "reference_counts": {
            key: comparison[key]
            for key in (
                "reference_security_pass_count",
                "reference_safe_count",
                "reference_rejected_count",
                "reference_failed_count",
            )
        },
        "packs": pack_records,
        "claim_states": claims,
        "files": {},
    }
    internal_files = sorted(
        path
        for path in output.rglob("*")
        if path.is_file()
        and path.name not in {"manifest.json", "SHA256SUMS"}
    )
    manifest["files"] = {
        str(path.relative_to(output)): {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in internal_files
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checksum_files = sorted(
        internal_files + [output / "manifest.json"]
    )
    (output / "SHA256SUMS").write_text(
        "".join(
            f"{sha256(path).removeprefix('sha256:')}  "
            f"{path.relative_to(output)}\n"
            for path in checksum_files
        ),
        encoding="utf-8",
    )


def verify(output: Path) -> None:
    manifest = load_json(output / "manifest.json")
    if manifest.get("paper_claim_allowed") is not False:
        raise ValueError("combined evidence cannot auto-admit paper claims")
    for relative, expected in manifest["files"].items():
        path = output / relative
        if (
            not path.is_file()
            or path.stat().st_size != expected["bytes"]
            or sha256(path) != expected["sha256"]
        ):
            raise ValueError(f"{path}: combined evidence digest changed")
    run_manifest_path = REPO_ROOT / manifest["run_manifest"]["path"]
    if sha256(run_manifest_path) != manifest["run_manifest"]["sha256"]:
        raise ValueError("combined run manifest binding changed")
    for record in manifest["packs"].values():
        root = REPO_ROOT / record["path"]
        if tree_digest(root) != record["tree_sha256"]:
            raise ValueError(f"{root}: final pack tree changed")
        if sha256(root / "manifest.json") != record["manifest_sha256"]:
            raise ValueError(f"{root}: final manifest changed")
    expected_lines = []
    for path in sorted(
        item
        for item in output.rglob("*")
        if item.is_file() and item.name != "SHA256SUMS"
    ):
        expected_lines.append(
            f"{sha256(path).removeprefix('sha256:')}  "
            f"{path.relative_to(output)}\n"
        )
    if (output / "SHA256SUMS").read_text(
        encoding="utf-8"
    ) != "".join(expected_lines):
        raise ValueError("combined SHA256SUMS changed")
    print(
        "final_confirmatory_evidence=VERIFIED "
        f"packs={len(manifest['packs'])} "
        "paper_claim_allowed=false"
    )


def main() -> int:
    args = parse_args()
    output = (REPO_ROOT / args.output_root).resolve()
    if args.verify:
        verify(output)
        return 0
    if output.exists() and args.force:
        shutil.rmtree(output)
    generate(output)
    verify(output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
