#!/usr/bin/env python3
"""Freeze and verify the pinned EVA native-runtime evidence."""

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
VERIFIER_PATH = REPO_ROOT / "scripts/verify_eva_native_runtime.py"
VERIFIER_SPEC = importlib.util.spec_from_file_location(
    "verify_eva_native_runtime_for_freezer", VERIFIER_PATH
)
assert VERIFIER_SPEC is not None and VERIFIER_SPEC.loader is not None
VERIFIER = importlib.util.module_from_spec(VERIFIER_SPEC)
VERIFIER_SPEC.loader.exec_module(VERIFIER)

CONTRACT = REPO_ROOT / "experiments/eva_native_runtime_v1/contract.json"
PROTOCOL = (
    REPO_ROOT / "docs/research/step_7g11_eva_native_runtime_protocol.md"
)
OUTPUT_DEFAULT = (
    REPO_ROOT / "docs/evidence/eva_native_runtime_replay_v1"
)


def sha256_path(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return "sha256:" + digest.hexdigest()


def write_checksums(root: Path) -> None:
    lines = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "SHA256SUMS":
            continue
        relative = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {relative}")
    (root / "SHA256SUMS").write_text(
        "\n".join(lines) + "\n", encoding="ascii"
    )


def verify_checksums(root: Path) -> None:
    checksum_path = root / "SHA256SUMS"
    VERIFIER.require(checksum_path.is_file(), "missing frozen SHA256SUMS")
    expected: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        digest, relative = line.split("  ", 1)
        expected[relative] = digest
    files = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    VERIFIER.require(sorted(expected) == files, "frozen file set changed")
    for relative, digest in expected.items():
        actual = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        VERIFIER.require(actual == digest, f"frozen checksum: {relative}")


def clean_source_gate() -> tuple[str, str]:
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    if status:
        raise ValueError(
            "EVA native evidence freeze requires a clean tree:\n" + status
        )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    origin = subprocess.run(
        ["git", "rev-parse", f"origin/{branch}"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    if head != origin:
        raise ValueError(f"EVA native freeze HEAD {head} != origin {origin}")
    return head, branch


def build_summary(
    result: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    validation = result["validation"]
    audit = result["locked_audit"]
    audit_state = (
        "SUPPORTED"
        if audit["status"] == "SAFE"
        else (
            "BLOCKED"
            if audit["status"] in {"REJECTED", "FAILED"}
            else "NOT_EVALUATED"
        )
    )
    return {
        "schema_version": "flipguard_eva_native_runtime_evidence_v1",
        "status": result["status"],
        "classification": result["classification"],
        "evaluation_role": contract["workload"]["role"],
        "validation": validation,
        "locked_audit": audit,
        "accounting": result["accounting"],
        "candidate": result["candidate"],
        "runtime": result["runtime"],
        "security_interpretation": {
            "static_candidate_security_v2_admission": (
                contract["security_interpretation"][
                    "static_candidate_security_v2_admission"
                ]
            ),
            "runtime_security_claim": result["runtime_security_claim"],
            "native_seal_context_security_enforcement": (
                contract["security_interpretation"][
                    "native_seal_context_security_enforcement"
                ]
            ),
            "lattigo_xs_xe_distribution_identity": False,
        },
        "pre_execution_recoveries": contract[
            "pre_execution_recoveries"
        ],
        "claim_states": {
            "native_eva_seal_execution": "SUPPORTED",
            "native_eva_seal_decision_certification": result[
                "claim_states"
            ]["native_eva_seal_decision_certification"],
            "native_eva_seal_locked_audit": audit_state,
            "cross_runtime_numerical_equivalence": "NOT_EVALUATED",
            "general_external_compiler_interoperability": (
                "PARTIALLY_SUPPORTED"
            ),
        },
        "policy_modifications": 0,
        "paper_claim_allowed": False,
        "block_reason": (
            "single seed-0 development workload; native SEAL and Lattigo "
            "runtime distributions differ; cross-runtime equivalence and "
            "general external-compiler behavior are not evaluated"
        ),
    }


def freeze(
    source_root: Path,
    recovery_log: Path,
    execution_log: Path,
    output: Path,
    freezer_commit: str,
) -> None:
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite EVA native evidence: {output}"
        )
    result_check = VERIFIER.verify_result(source_root, CONTRACT)
    if not recovery_log.is_file():
        raise ValueError(f"missing preflight recovery log: {recovery_log}")
    recovery_text = recovery_log.read_text(encoding="utf-8")
    for run_id, marker in (
        ("30561535356", "missing bound artifact"),
        ("30562143758", "compiled DOT changed"),
    ):
        if run_id not in recovery_text or marker not in recovery_text:
            raise ValueError(
                f"preflight recovery log is missing run {run_id}"
            )
    if not execution_log.is_file():
        raise ValueError(f"missing native execution log: {execution_log}")
    contract = VERIFIER.load_json(CONTRACT)
    result = VERIFIER.load_json(source_root / "manifest.json")
    execution_text = execution_log.read_text(encoding="utf-8")
    if (
        result["action_run_id"] not in execution_text
        or result["source_commit"] not in execution_text
        or '"validation_status": "REJECTED"' not in execution_text
    ):
        raise ValueError("native execution log identity is incomplete")
    if result_check["paper_claim_allowed"] is not False:
        raise ValueError("native result paper gate changed")

    output.mkdir(parents=True)
    shutil.copytree(source_root, output / "raw")
    shutil.copy2(CONTRACT, output / "contract.json")
    shutil.copy2(PROTOCOL, output / "protocol.md")
    shutil.copy2(recovery_log, output / "preflight_failure.log")
    shutil.copy2(execution_log, output / "execution.log")
    summary = build_summary(result, contract)
    (output / "summary.json").write_bytes(
        VERIFIER.canonical_json(summary)
    )
    manifest = {
        "schema_version": "flipguard_eva_native_runtime_evidence_v1",
        "evidence_id": "eva_native_runtime_replay_v1",
        "classification": result["classification"],
        "status": result["status"],
        "freezer_commit": freezer_commit,
        "execution_source_commit": result["source_commit"],
        "github_actions_run_id": result["action_run_id"],
        "contract_sha256": sha256_path(output / "contract.json"),
        "protocol_sha256": sha256_path(output / "protocol.md"),
        "raw_manifest_sha256": sha256_path(
            output / "raw/manifest.json"
        ),
        "raw_tree_sha256": tree_digest(output / "raw"),
        "preflight_failure_log_sha256": sha256_path(
            output / "preflight_failure.log"
        ),
        "execution_log_sha256": sha256_path(output / "execution.log"),
        "summary_sha256": sha256_path(output / "summary.json"),
        "direct_policy_digest": VERIFIER.DIRECT_DIGEST,
        "security_policy_digest": VERIFIER.SECURITY_DIGEST,
        "policy_modifications": 0,
        "paper_claim_allowed": False,
    }
    (output / "manifest.json").write_bytes(
        VERIFIER.canonical_json(manifest)
    )
    readme = f"""# EVA Native Runtime Replay V1

This immutable pack preserves the pinned EVA v1.0.1 program executed on its
native Microsoft SEAL v3.6.4 backend. Validation status is
`{result["validation"]["status"]}` and locked-audit status is
`{result["locked_audit"]["status"]}`.

The pack also preserves the first clean-runner preflight packaging failure,
which performed zero encrypted executions. It changes no Direct or Security
policy and makes no cross-runtime equivalence claim.

`paper_claim_allowed=false`.
"""
    (output / "README.md").write_text(readme, encoding="ascii")
    write_checksums(output)


def verify(output: Path = OUTPUT_DEFAULT) -> dict[str, Any]:
    verify_checksums(output)
    contract = VERIFIER.load_json(output / "contract.json")
    result_check = VERIFIER.verify_result(
        output / "raw", output / "contract.json"
    )
    result = VERIFIER.load_json(output / "raw/manifest.json")
    summary = VERIFIER.load_json(output / "summary.json")
    manifest = VERIFIER.load_json(output / "manifest.json")
    VERIFIER.require(
        summary == build_summary(result, contract),
        "frozen native summary changed",
    )
    VERIFIER.require(
        manifest["schema_version"]
        == "flipguard_eva_native_runtime_evidence_v1",
        "frozen native evidence schema changed",
    )
    VERIFIER.require(
        manifest["contract_sha256"] == sha256_path(output / "contract.json"),
        "frozen native contract digest changed",
    )
    VERIFIER.require(
        manifest["raw_manifest_sha256"]
        == sha256_path(output / "raw/manifest.json"),
        "frozen native raw manifest changed",
    )
    VERIFIER.require(
        manifest["raw_tree_sha256"] == tree_digest(output / "raw"),
        "frozen native raw tree changed",
    )
    VERIFIER.require(
        manifest["summary_sha256"] == sha256_path(output / "summary.json"),
        "frozen native summary digest changed",
    )
    VERIFIER.require(
        manifest["preflight_failure_log_sha256"]
        == sha256_path(output / "preflight_failure.log"),
        "frozen preflight log digest changed",
    )
    VERIFIER.require(
        manifest["execution_log_sha256"]
        == sha256_path(output / "execution.log"),
        "frozen execution log digest changed",
    )
    VERIFIER.require(
        manifest["paper_claim_allowed"] is False,
        "frozen native paper gate changed",
    )
    VERIFIER.require(
        summary["policy_modifications"] == 0,
        "frozen native policy modification changed",
    )
    return {
        **result_check,
        "evidence_manifest_sha256": sha256_path(
            output / "manifest.json"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--preflight-failure-log", type=Path)
    parser.add_argument("--execution-log", type=Path)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    output = (
        args.output
        if args.output.is_absolute()
        else REPO_ROOT / args.output
    )
    if args.verify:
        print(json.dumps(verify(output), indent=2, sort_keys=True))
        return
    if (
        args.source_root is None
        or args.preflight_failure_log is None
        or args.execution_log is None
    ):
        raise ValueError(
            "--source-root, --preflight-failure-log, and --execution-log "
            "are required"
        )
    source_root = (
        args.source_root
        if args.source_root.is_absolute()
        else REPO_ROOT / args.source_root
    )
    recovery_log = (
        args.preflight_failure_log
        if args.preflight_failure_log.is_absolute()
        else REPO_ROOT / args.preflight_failure_log
    )
    execution_log = (
        args.execution_log
        if args.execution_log.is_absolute()
        else REPO_ROOT / args.execution_log
    )
    head, _ = clean_source_gate()
    freeze(source_root, recovery_log, execution_log, output, head)
    print(
        f"eva_native_runtime_evidence=FROZEN output={output} "
        f"freezer_commit={head}"
    )


if __name__ == "__main__":
    main()
