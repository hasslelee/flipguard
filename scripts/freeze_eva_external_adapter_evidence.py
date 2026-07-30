#!/usr/bin/env python3
"""Freeze the source-replayed EVA compiler adapter evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path("docs/evidence/eva_external_adapter_replay_v1")
CONTRACT = Path("experiments/eva_external_adapter_v1/contract.json")
PROTOCOL = Path(
    "docs/research/step_7g9_eva_external_compiler_adapter_protocol.md"
)
VERIFY_PATH = REPO_ROOT / (
    "scripts/verify_eva_external_adapter_output.py"
)
SPEC = importlib.util.spec_from_file_location(
    "verify_eva_output_for_freezer",
    VERIFY_PATH,
)
assert SPEC is not None and SPEC.loader is not None
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)

RECOVERY_RUNS = [
    {
        "run_id": "30552296617",
        "source_commit":
            "0dc7da0a10801c165616093d3584cb7d0682b9de",
        "conclusion": "FAILURE",
        "stage": "VERIFY_SOURCE_IDENTITY_AND_CONTRACT",
        "reason_code":
            "COMPILER_PREFLIGHT_REQUIRED_GITIGNORED_RUNTIME_ARTIFACTS",
        "classification": "RECOVERABLE_IMPLEMENTATION_FAILURE",
        "contract_changed": False,
        "cryptographic_source_changed": False,
    },
    {
        "run_id": "30552734306",
        "source_commit":
            "91e74d61cb50df322f5d12fe8a1d99f1599b000e",
        "conclusion": "FAILURE",
        "stage": "BUILD_PINNED_MICROSOFT_SEAL",
        "reason_code":
            "SEAL_3_6_4_MISSING_MUTEX_TRANSITIVE_INCLUDE",
        "classification": "RECOVERABLE_IMPLEMENTATION_FAILURE",
        "contract_changed": False,
        "cryptographic_source_changed": False,
    },
    {
        "run_id": "30553222153",
        "source_commit":
            "6981b9831643b835534dc1f4b66c277bf0abd580",
        "conclusion": "FAILURE",
        "stage": "BUILD_EXACT_SEAL_PRIME_EXPORTER",
        "reason_code": "SEAL_CONSUMER_MISSING_MUTEX_INCLUDE",
        "classification": "RECOVERABLE_IMPLEMENTATION_FAILURE",
        "contract_changed": False,
        "cryptographic_source_changed": False,
    },
    {
        "run_id": "30553813485",
        "source_commit":
            "04938d9d330c4994baaf45048704dbd17e4ab7d0",
        "conclusion": "SUCCESS",
        "stage": "COMPILER_REPLAY_AND_ARTIFACT_UPLOAD",
        "reason_code": "COMPLETE",
        "classification": "PASS",
        "contract_changed": False,
        "cryptographic_source_changed": False,
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--freezer-commit")
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


def save_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=path.parent,
        prefix=path.name + ".",
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def require_clean_origin() -> tuple[str, str]:
    status = git("status", "--short")
    if status:
        raise ValueError(
            "EVA evidence freeze requires a clean tree:\n" + status
        )
    head = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    if not branch:
        raise ValueError("EVA evidence freeze requires a branch")
    origin = git("rev-parse", f"origin/{branch}")
    if head != origin:
        raise ValueError(
            f"EVA evidence freeze HEAD {head} != origin {origin}"
        )
    return head, origin


def file_inventory(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_path(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "SHA256SUMS"
    }


def write_sha256sums(root: Path) -> None:
    inventory = file_inventory(root)
    lines = [
        f"{digest.removeprefix('sha256:')}  {name}"
        for name, digest in inventory.items()
    ]
    save_atomic(
        root / "SHA256SUMS",
        ("\n".join(lines) + "\n").encode("ascii"),
    )


def verify_frozen(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    output = output if output.is_absolute() else REPO_ROOT / output
    if not output.is_dir():
        raise ValueError(f"frozen EVA evidence is missing: {output}")
    expected = {}
    for line in (output / "SHA256SUMS").read_text(
        encoding="ascii"
    ).splitlines():
        digest, name = line.split(None, 1)
        expected[name.lstrip("*")] = "sha256:" + digest
    actual = file_inventory(output)
    if expected != actual:
        raise ValueError("frozen EVA evidence inventory changed")
    summary = VERIFIER.verify(output / "run")
    frozen_summary = json.loads(
        (output / "summary.json").read_text(encoding="ascii")
    )
    if frozen_summary != summary:
        raise ValueError("frozen EVA summary changed")
    recovery = json.loads(
        (output / "recovery_log.json").read_text(encoding="ascii")
    )
    if recovery["runs"] != RECOVERY_RUNS:
        raise ValueError("EVA recovery log changed")
    manifest = json.loads(
        (output / "manifest.json").read_text(encoding="ascii")
    )
    if (
        manifest["schema_version"] !=
        "flipguard_eva_external_adapter_evidence_v1"
        or manifest["status"] != "BLOCKED_GRAPH_COMPATIBILITY"
        or manifest["summary"] != summary
        or manifest["recovery_log_sha256"] !=
        sha256_path(output / "recovery_log.json")
        or manifest["paper_claim_allowed"] is not False
    ):
        raise ValueError("frozen EVA manifest changed")
    return manifest


def freeze(
    raw_root: Path,
    output: Path,
    freezer_commit: str | None,
) -> None:
    head, origin = require_clean_origin()
    if freezer_commit is not None and freezer_commit != head:
        raise ValueError(
            f"requested freezer commit {freezer_commit} != HEAD {head}"
        )
    raw_root = (
        raw_root if raw_root.is_absolute() else REPO_ROOT / raw_root
    )
    output = output if output.is_absolute() else REPO_ROOT / output
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite EVA evidence: {output}"
        )
    summary = VERIFIER.verify(raw_root)
    output.mkdir(parents=True)
    shutil.copytree(raw_root, output / "run")
    shutil.copyfile(REPO_ROOT / CONTRACT, output / "contract.json")
    shutil.copyfile(REPO_ROOT / PROTOCOL, output / "protocol.md")
    save_atomic(output / "summary.json", canonical_json(summary))
    recovery = {
        "schema_version":
            "flipguard_eva_external_adapter_recovery_log_v1",
        "policy": (
            "implementation-only recovery; no contract, candidate, "
            "cryptographic source, or policy change"
        ),
        "runs": RECOVERY_RUNS,
        "failure_count": 3,
        "successful_run_count": 1,
        "systemic_failure_repeated_three_times": False,
    }
    save_atomic(
        output / "recovery_log.json",
        canonical_json(recovery),
    )
    readme = """# EVA External Adapter Replay V1

This immutable pack preserves an actual Microsoft EVA v1.0.1 compiler output
and exact Microsoft SEAL v3.6.4 modulus materialization for the predeclared
seed-0 Iris `linear_poly3` program.

The compiler replay succeeded and the exact concrete candidate passed
Security Policy V2. It was not encrypted because EVA produced only three
ciphertext Q primes while the frozen FlipGuard Lattigo lowering requires
seven. The result is `BLOCKED_GRAPH_COMPATIBILITY`; no prime was padded and no
compiler option, scale, frozen policy, or graph lowering was retuned.

The three preceding implementation failures are retained in
`recovery_log.json`. They occurred before compiler output evaluation and did
not modify the predeclared contract or upstream cryptographic source bytes.
"""
    save_atomic(output / "README.md", readme.encode("ascii"))
    manifest = {
        "schema_version":
            "flipguard_eva_external_adapter_evidence_v1",
        "evidence_id": "eva_external_adapter_replay_v1",
        "classification":
            "SOURCE_REPLAYED_PUBLIC_COMPILER_PARAMETER_OUTPUT",
        "status": "BLOCKED_GRAPH_COMPATIBILITY",
        "freezer_commit": head,
        "origin_commit": origin,
        "compiler_execution_commit":
            summary["compiler_execution_commit"],
        "github_actions_run_id":
            summary["github_actions_run_id"],
        "contract_sha256": sha256_path(REPO_ROOT / CONTRACT),
        "protocol_sha256": sha256_path(REPO_ROOT / PROTOCOL),
        "security_policy_id":
            "security_guidelines_cic2025_table5_2_ternary_128_v2",
        "security_policy_digest":
            "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055",
        "direct_policy_id": "flipguard_direct_synthesis_policy_v2",
        "direct_policy_digest":
            "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603",
        "summary": summary,
        "recovery_log_sha256":
            sha256_path(output / "recovery_log.json"),
        "claim_states": {
            "actual_eva_compiler_parameter_output": "SUPPORTED",
            "security_v2_static_admission": "SUPPORTED",
            "encrypted_external_candidate_certification":
                "NOT_EVALUATED",
            "native_eva_seal_execution": "NOT_EVALUATED",
            "cross_backend_graph_compatibility": "BLOCKED",
            "general_external_autotuner_integration":
                "PARTIALLY_SUPPORTED",
        },
        "paper_claim_allowed": False,
        "block_reason": (
            "the exact EVA candidate has three Q primes but the frozen "
            "FlipGuard Lattigo lowering requires seven"
        ),
    }
    save_atomic(output / "manifest.json", canonical_json(manifest))
    write_sha256sums(output)
    verify_frozen(output)
    print(
        "eva_external_adapter_evidence_v1=FROZEN "
        f"output={output} status={manifest['status']}"
    )


def main() -> None:
    args = parse_args()
    if args.verify:
        manifest = verify_frozen(args.output)
        print(
            "eva_external_adapter_evidence_v1=VERIFIED "
            f"status={manifest['status']} "
            f"run={manifest['github_actions_run_id']} "
            "encrypted_trials=0 paper_claim_allowed=false"
        )
        return
    if args.raw_root is None:
        raise ValueError("--raw-root is required unless --verify is used")
    freeze(args.raw_root, args.output, args.freezer_commit)


if __name__ == "__main__":
    main()
