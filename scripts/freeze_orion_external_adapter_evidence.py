#!/usr/bin/env python3
"""Freeze and verify the actual-Orion adapter audit evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = Path(
    "experiments/orion_external_adapter_v1/contract.json"
)
DEFAULT_OUTPUT = Path(
    "docs/evidence/orion_external_adapter_audit_v1"
)
PROTOCOL = Path(
    "docs/research/step_7g2_orion_external_adapter_protocol.md"
)
SCHEMA_VERSION = "flipguard_orion_external_adapter_evidence_v1"

RUNNER_PATH = REPO_ROOT / "scripts/run_orion_external_adapter_audit.py"
RUNNER_SPEC = importlib.util.spec_from_file_location(
    "run_orion_adapter_for_freezer",
    RUNNER_PATH,
)
assert RUNNER_SPEC is not None and RUNNER_SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(RUNNER)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        + "\n"
    ).encode("ascii")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def absolute(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def require_clean_origin() -> str:
    status = git("status", "--short")
    if status:
        raise ValueError("Orion evidence freeze requires a clean tree:\n" + status)
    head = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    origin = git("rev-parse", f"origin/{branch}")
    if head != origin:
        raise ValueError(f"HEAD {head} does not match origin {origin}")
    return head


def write_checksums(root: Path) -> None:
    lines = []
    for path in sorted(
        item
        for item in root.rglob("*")
        if item.is_file() and item.name != "SHA256SUMS"
    ):
        lines.append(
            f"{sha256_path(path).removeprefix('sha256:')}  "
            f"{path.relative_to(root).as_posix()}\n"
        )
    (root / "SHA256SUMS").write_text("".join(lines), encoding="ascii")


def verify_checksums(root: Path) -> None:
    checksum_path = root / "SHA256SUMS"
    expected: set[str] = set()
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        digest, relative = line.split("  ", 1)
        target = root / relative
        if not target.is_file():
            raise ValueError(f"missing frozen Orion artifact: {relative}")
        if sha256_path(target) != f"sha256:{digest}":
            raise ValueError(f"frozen Orion artifact changed: {relative}")
        expected.add(relative)
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if actual != expected:
        raise ValueError("frozen Orion evidence file set changed")


def freeze(
    run_root: Path,
    contract_path: Path,
    output_root: Path,
) -> None:
    run_root = absolute(run_root)
    contract_path = absolute(contract_path)
    output_root = absolute(output_root)
    if output_root.exists():
        raise FileExistsError(
            f"refusing to overwrite Orion evidence: {output_root}"
        )
    freezer_commit = require_clean_origin()
    summary = RUNNER.verify_output(contract_path, run_root)
    run_manifest = load_json(run_root / "run_manifest.json")
    output_root.mkdir(parents=True)
    shutil.copytree(run_root, output_root / "run")
    shutil.copy2(contract_path, output_root / "contract.json")
    shutil.copy2(REPO_ROOT / PROTOCOL, output_root / "protocol.md")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "evidence_id": "orion_external_adapter_audit_v1",
        "classification": "STATIC_FAIL_CLOSED_INTEROPERABILITY_AUDIT",
        "freezer_commit": freezer_commit,
        "execution_commit": run_manifest["source_commit"],
        "run_manifest_sha256": sha256_path(
            output_root / "run/run_manifest.json"
        ),
        "contract_sha256": sha256_path(output_root / "contract.json"),
        "summary": summary,
        "claim_states": summary["claim_states"],
        "paper_claim_allowed": False,
        "block_reason": (
            "All public Orion configurations are semantically incompatible "
            "with the frozen runtime or Security V2; no actual autotuner "
            "output and no encrypted external candidate were evaluated."
        ),
    }
    (output_root / "manifest.json").write_bytes(canonical_json(manifest))
    readme = """# Orion External Adapter Audit V1

This pack binds three actual public Orion configuration files and the source
that defines their parameter semantics. All three configurations were
fail-closed before CKKS execution because exact runtime and Security V2
semantics did not match.

This is positive evidence for provenance-aware mismatch detection, not for
external autotuner quality or encrypted third-party candidate certification.

`paper_claim_allowed=false`.
"""
    (output_root / "README.md").write_text(readme, encoding="ascii")
    write_checksums(output_root)
    verify(output_root)


def verify(output_root: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    output_root = absolute(output_root)
    verify_checksums(output_root)
    manifest = load_json(output_root / "manifest.json")
    if (
        manifest["schema_version"] != SCHEMA_VERSION
        or manifest["paper_claim_allowed"] is not False
    ):
        raise ValueError("Orion evidence gate changed")
    summary = RUNNER.verify_output(
        output_root / "contract.json",
        output_root / "run",
    )
    if manifest["summary"] != summary:
        raise ValueError("Orion evidence summary changed")
    if manifest["run_manifest_sha256"] != sha256_path(
        output_root / "run/run_manifest.json"
    ):
        raise ValueError("Orion run manifest binding changed")
    if manifest["contract_sha256"] != sha256_path(
        output_root / "contract.json"
    ):
        raise ValueError("Orion contract binding changed")
    return summary


def main() -> int:
    args = parse_args()
    if args.verify:
        summary = verify(args.output_root)
        print(
            "orion_external_adapter_evidence=VERIFIED "
            f"configs={summary['counts']['actual_public_configurations']} "
            f"blocked={summary['counts']['blocked_semantic_mismatch']} "
            "paper_claim_allowed=false"
        )
        return 0
    if args.run_root is None:
        raise ValueError("--run-root is required when freezing")
    freeze(args.run_root, args.contract, args.output_root)
    print(
        "orion_external_adapter_evidence=FROZEN "
        f"output={absolute(args.output_root)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
