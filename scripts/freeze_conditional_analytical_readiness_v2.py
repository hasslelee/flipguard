#!/usr/bin/env python3
"""Freeze and verify the conditional analytical V2 readiness artifact."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DEFAULT = (
    REPO_ROOT
    / "results/thesis_grade_protocol/"
    "conditional_analytical_readiness_v2"
)
OUTPUT_DEFAULT = (
    REPO_ROOT
    / "docs/evidence/"
    "conditional_analytical_readiness_v2"
)
BUILDER_PATH = (
    REPO_ROOT / "scripts/build_conditional_analytical_readiness_v2.py"
)

SPEC = importlib.util.spec_from_file_location(
    "build_conditional_analytical_readiness_v2_for_freeze",
    BUILDER_PATH,
)
assert SPEC is not None and SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


def sha256_path(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    ).encode("ascii")


def validate_raw(raw: Path) -> dict[str, Any]:
    BUILDER.verify_existing(raw)
    summary = json.loads(
        (raw / "summary.json").read_text(encoding="ascii")
    )
    expected = {
        "primary_candidates": 50,
        "development_seed0_candidates": 10,
        "confirmatory_seeds1_4_candidates": 40,
        "linear_poly3_candidates": 25,
        "mlp_square_linear_score_candidates": 25,
        "graph_contract_supported_candidates": 25,
        "primitive_bound_complete_candidates": 0,
        "proof_eligible_candidates": 0,
        "observed_vs_bound_audits_completed": 0,
        "conditional_propagation_lemma": "SUPPORTED",
        "instantiated_ckks_analytical_certificate": "BLOCKED",
        "paper_claim_allowed": False,
        "encrypted_executions": 0,
        "policy_modifications": 0,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise ValueError(
                f"raw analytical readiness {key}={summary.get(key)!r}; "
                f"expected {value!r}"
            )
    return summary


def freeze(
    raw: Path,
    output: Path,
    freezer_commit: str,
) -> None:
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite frozen evidence pack: {output}"
        )
    summary = validate_raw(raw)
    output.mkdir(parents=True)
    raw_output = output / "raw"
    shutil.copytree(raw, raw_output)

    raw_files = []
    for path in sorted(raw_output.iterdir()):
        if path.is_file():
            raw_files.append(
                {
                    "path": f"raw/{path.name}",
                    "sha256": sha256_path(path),
                    "size_bytes": path.stat().st_size,
                }
            )

    manifest = {
        "schema_version": (
            "flipguard_conditional_analytical_readiness_evidence_v2"
        ),
        "evidence_id": "conditional_analytical_readiness_v2",
        "evidence_stage": "STATIC_POST_CONFIRMATORY_RESEARCH",
        "freezer_commit": freezer_commit,
        "derivation_source_commit": summary["source_commit"],
        "builder": {
            "path": str(BUILDER_PATH.relative_to(REPO_ROOT)),
            "sha256": sha256_path(BUILDER_PATH),
        },
        "derivation_source": summary["derivation_source"],
        "derivation_test": summary["derivation_test"],
        "bound_inputs": summary["bound_inputs"],
        "raw_files": raw_files,
        "claims": {
            "conditional_propagation_lemma": "SUPPORTED",
            "instantiated_ckks_analytical_certificate": "BLOCKED",
            "paper_claim_allowed": False,
            "block_reason": summary["block_reason"],
        },
        "accounting": {
            "primary_candidates": 50,
            "graph_contract_supported_candidates": 25,
            "primitive_bound_complete_candidates": 0,
            "proof_eligible_candidates": 0,
            "observed_vs_bound_audits_completed": 0,
            "encrypted_executions": 0,
            "policy_modifications": 0,
        },
        "frozen_evidence_modified": False,
    }
    (output / "manifest.json").write_bytes(
        canonical_json(manifest)
    )

    readme = """# Conditional Analytical Readiness V2 Evidence

This static pack binds all 50 primary direct selections to the Analytical V2
readiness inventory.

- Conditional outward-rounded propagation: `SUPPORTED`.
- Instantiated CKKS analytical certificate: `BLOCKED`.
- Complete primitive derivations: `0/50`.
- Proof-eligible selected candidates: `0/50`.
- Encrypted executions: `0`.

The deterministic verifier rebuilds the raw inventory and the complete pack.
It never substitutes observed errors or standard deviations for absolute
primitive bounds.
"""
    (output / "README.md").write_text(
        readme,
        encoding="ascii",
    )

    checksums = []
    for path in sorted(
        candidate
        for candidate in output.rglob("*")
        if candidate.is_file() and candidate.name != "SHA256SUMS"
    ):
        relative = path.relative_to(output)
        checksums.append(
            f"{sha256_path(path).removeprefix('sha256:')}  "
            f"{relative.as_posix()}\n"
        )
    (output / "SHA256SUMS").write_text(
        "".join(checksums),
        encoding="ascii",
    )


def verify_checksums(output: Path) -> None:
    lines = (output / "SHA256SUMS").read_text(
        encoding="ascii"
    ).splitlines()
    expected_paths = set()
    for line in lines:
        digest, relative = line.split("  ", 1)
        path = output / relative
        if not path.is_file():
            raise ValueError(f"missing frozen file: {relative}")
        if sha256_path(path) != f"sha256:{digest}":
            raise ValueError(f"checksum mismatch: {relative}")
        expected_paths.add(relative)

    actual_paths = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if expected_paths != actual_paths:
        raise ValueError("frozen evidence file set changed")


def compare_trees(expected: Path, actual: Path) -> None:
    expected_files = sorted(
        path.relative_to(expected)
        for path in expected.rglob("*")
        if path.is_file()
    )
    actual_files = sorted(
        path.relative_to(actual)
        for path in actual.rglob("*")
        if path.is_file()
    )
    if expected_files != actual_files:
        raise ValueError("frozen evidence rebuild file set changed")
    for relative in expected_files:
        if (expected / relative).read_bytes() != (
            actual / relative
        ).read_bytes():
            raise ValueError(
                f"frozen evidence rebuild changed: {relative}"
            )


def verify(output: Path) -> None:
    verify_checksums(output)
    manifest = json.loads(
        (output / "manifest.json").read_text(encoding="ascii")
    )
    validate_raw(output / "raw")
    with tempfile.TemporaryDirectory(
        prefix="flipguard-analytical-freeze-",
        dir="/tmp",
    ) as temporary:
        rebuilt = Path(temporary) / "rebuilt"
        freeze(
            output / "raw",
            rebuilt,
            manifest["freezer_commit"],
        )
        compare_trees(output, rebuilt)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=RAW_DEFAULT)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--freezer-commit", required=False)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    raw = args.raw if args.raw.is_absolute() else REPO_ROOT / args.raw
    output = (
        args.output
        if args.output.is_absolute()
        else REPO_ROOT / args.output
    )

    if args.verify:
        verify(output)
        print("conditional_analytical_readiness_evidence_v2=VERIFIED")
        return
    if not args.freezer_commit:
        raise ValueError("--freezer-commit is required when freezing")
    freeze(raw, output, args.freezer_commit)
    print(
        "conditional_analytical_readiness_evidence_v2=FROZEN "
        f"output={output}"
    )


if __name__ == "__main__":
    main()
