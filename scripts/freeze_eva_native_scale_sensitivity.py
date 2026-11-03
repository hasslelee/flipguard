#!/usr/bin/env python3
"""Freeze and verify native EVA scale-sensitivity evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative: str) -> Any:
    path = REPO_ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERIFIER = load_module(
    "verify_eva_native_scale_sensitivity_for_freezer",
    "scripts/verify_eva_native_scale_sensitivity.py",
)
BASE = load_module(
    "freeze_eva_native_runtime_for_scale_sensitivity",
    "scripts/freeze_eva_native_runtime_evidence.py",
)
NATIVE = VERIFIER.NATIVE

CONTRACT = (
    REPO_ROOT / "experiments/eva_native_scale_sensitivity_v1/contract.json"
)
PROTOCOL = (
    REPO_ROOT
    / "docs/research/step_7g12_eva_native_scale_sensitivity_protocol.md"
)
ORIGINAL_PACK = REPO_ROOT / "docs/evidence/eva_native_runtime_replay_v1"
OUTPUT_DEFAULT = (
    REPO_ROOT / "docs/evidence/eva_native_scale_sensitivity_v1"
)


def original_scale20_comparison(
    result: dict[str, Any],
) -> dict[str, Any]:
    original = NATIVE.load_json(ORIGINAL_PACK / "raw/manifest.json")
    scale20 = next(
        arm for arm in result["arms"] if arm["input_scale_bits"] == 20
    )
    original_identity = original["compiled_program_identity"]
    same_semantics = (
        scale20["compiled_program_semantic_sha256"]
        == original_identity["semantic_sha256"]
    )
    same_parameters = (
        scale20["poly_modulus_degree"]
        == original["candidate"]["poly_modulus_degree"]
        and scale20["prime_bits"] == original["candidate"]["prime_bits"]
    )
    if not same_semantics or not same_parameters:
        raise ValueError(
            "INTEGRITY_BLOCK: scale-20 literal no longer matches original"
        )
    return {
        "literal_identity": "SEMANTICALLY_IDENTICAL",
        "same_poly_modulus_degree_and_prime_bits": True,
        "semantic_sha256": scale20[
            "compiled_program_semantic_sha256"
        ],
        "original_raw_sha256": original_identity["observed_raw_sha256"],
        "sensitivity_raw_sha256": scale20["compiled_program_sha256"],
        "raw_representation_identical": (
            scale20["compiled_program_sha256"]
            == original_identity["observed_raw_sha256"]
        ),
        "original_action_run_id": original["action_run_id"],
        "sensitivity_action_run_id": result["action_run_id"],
        "original_validation": original["validation"],
        "sensitivity_validation": scale20["validation"],
        "conclusion": (
            "same semantic scale-20 literal was REJECTED in both fresh-key "
            "runs; stochastic counts are descriptive and not expected to "
            "be byte-reproducible"
        ),
    }


def build_summary(
    result: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    arms = []
    for arm in result["arms"]:
        arms.append(
            {
                "candidate_id": arm["candidate_id"],
                "input_scale_bits": arm["input_scale_bits"],
                "compilation_status": arm["compilation_status"],
                "poly_modulus_degree": arm.get("poly_modulus_degree"),
                "prime_bits": arm.get("prime_bits"),
                "security_reference": arm["security_reference"],
                "validation": arm["validation"],
            }
        )
    return {
        "schema_version": (
            "flipguard_eva_native_scale_sensitivity_evidence_v1"
        ),
        "status": result["status"],
        "outcome": result["outcome"],
        "classification": result["classification"],
        "evaluation_role": result["evaluation_role"],
        "arms": arms,
        "selected": result["selected"],
        "locked_audit": result["locked_audit"],
        "accounting": result["accounting"],
        "original_scale20_comparison": original_scale20_comparison(result),
        "security_interpretation": {
            "security_reference": contract["security_reference"][
                "admission_rule"
            ],
            "runtime_security_claim": result["runtime_security_claim"],
            "native_seal_context_security_enforcement": contract[
                "security_reference"
            ]["native_seal_context_security_enforcement"],
            "lattigo_distribution_identity": False,
        },
        "causal_boundary": contract["motivation"]["causal_boundary"],
        "confirmation_boundary": contract["motivation"][
            "confirmation_boundary"
        ],
        "claim_states": result["claim_states"],
        "retuning": 0,
        "policy_modifications": 0,
        "paper_claim_allowed": False,
        "block_reason": (
            "post-rejection seed-0 development sensitivity on one model "
            "and one external runtime; native SEAL distribution security, "
            "cross-runtime equivalence, and generalization are not evaluated"
        ),
    }


def freeze(
    source_root: Path,
    execution_log: Path,
    output: Path,
    freezer_commit: str,
) -> None:
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite EVA scale evidence: {output}"
        )
    checked = VERIFIER.verify_result(source_root, CONTRACT)
    if not execution_log.is_file():
        raise ValueError(f"missing execution log: {execution_log}")
    BASE.verify(ORIGINAL_PACK)
    contract = VERIFIER.load_json(CONTRACT)
    result = VERIFIER.load_json(source_root / "manifest.json")
    log_text = execution_log.read_text(encoding="utf-8")
    for marker in (
        result["source_commit"],
        result["action_run_id"],
        result["outcome"],
        result["selected"]["candidate_id"],
    ):
        if marker not in log_text:
            raise ValueError(f"execution log identity missing: {marker}")
    if checked["paper_claim_allowed"] is not False:
        raise ValueError("scale-sensitivity paper gate changed")

    output.mkdir(parents=True)
    shutil.copytree(source_root, output / "raw")
    shutil.copy2(CONTRACT, output / "contract.json")
    shutil.copy2(PROTOCOL, output / "protocol.md")
    BASE.copy_normalized_log(execution_log, output / "execution.log")
    summary = build_summary(result, contract)
    (output / "summary.json").write_bytes(
        VERIFIER.canonical_json(summary)
    )
    original_manifest = ORIGINAL_PACK / "manifest.json"
    manifest = {
        "schema_version": (
            "flipguard_eva_native_scale_sensitivity_evidence_v1"
        ),
        "evidence_id": "eva_native_scale_sensitivity_v1",
        "status": result["status"],
        "outcome": result["outcome"],
        "freezer_commit": freezer_commit,
        "execution_source_commit": result["source_commit"],
        "github_actions_run_id": result["action_run_id"],
        "contract_sha256": BASE.sha256_path(output / "contract.json"),
        "protocol_sha256": BASE.sha256_path(output / "protocol.md"),
        "raw_manifest_sha256": BASE.sha256_path(
            output / "raw/manifest.json"
        ),
        "raw_tree_sha256": BASE.tree_digest(output / "raw"),
        "source_execution_log_sha256": BASE.sha256_path(execution_log),
        "execution_log_sha256": BASE.sha256_path(output / "execution.log"),
        "log_representation": "TRAILING_SPACE_TAB_NORMALIZED_TEXT_V1",
        "summary_sha256": BASE.sha256_path(output / "summary.json"),
        "original_native_evidence_manifest_sha256": BASE.sha256_path(
            original_manifest
        ),
        "direct_policy_digest": NATIVE.DIRECT_DIGEST,
        "security_policy_digest": NATIVE.SECURITY_DIGEST,
        "retuning": 0,
        "policy_modifications": 0,
        "paper_claim_allowed": False,
    }
    (output / "manifest.json").write_bytes(
        VERIFIER.canonical_json(manifest)
    )
    readme = f"""# EVA Native Scale Sensitivity V1

This immutable development pack preserves all three predeclared native
EVA/SEAL input-scale arms. Scale 20 was `REJECTED`; scales 30 and 40 were
`SAFE` on validation. The first-SAFE rule selected scale 30, whose untouched
locked audit was `{result["locked_audit"]["status"]}`.

The original scale-20 negative result remains `BLOCKED`. This pack does not
claim exact SEAL runtime security, cross-runtime numerical equivalence,
general external-autotuner performance, or confirmatory generalization.

`paper_claim_allowed=false`.
"""
    (output / "README.md").write_text(readme, encoding="ascii")
    BASE.write_checksums(output)


def verify(output: Path = OUTPUT_DEFAULT) -> dict[str, Any]:
    BASE.verify_checksums(output)
    checked = VERIFIER.verify_result(
        output / "raw", output / "contract.json"
    )
    BASE.verify(ORIGINAL_PACK)
    contract = VERIFIER.load_json(output / "contract.json")
    result = VERIFIER.load_json(output / "raw/manifest.json")
    summary = VERIFIER.load_json(output / "summary.json")
    manifest = VERIFIER.load_json(output / "manifest.json")
    VERIFIER.require(
        summary == build_summary(result, contract),
        "frozen EVA scale summary changed",
    )
    VERIFIER.require(
        manifest["schema_version"]
        == "flipguard_eva_native_scale_sensitivity_evidence_v1",
        "frozen EVA scale evidence schema changed",
    )
    for key, relative in (
        ("contract_sha256", "contract.json"),
        ("protocol_sha256", "protocol.md"),
        ("raw_manifest_sha256", "raw/manifest.json"),
        ("execution_log_sha256", "execution.log"),
        ("summary_sha256", "summary.json"),
    ):
        VERIFIER.require(
            manifest[key] == BASE.sha256_path(output / relative),
            f"frozen EVA scale digest changed: {relative}",
        )
    VERIFIER.require(
        manifest["raw_tree_sha256"] == BASE.tree_digest(output / "raw"),
        "frozen EVA scale raw tree changed",
    )
    VERIFIER.require(
        manifest["original_native_evidence_manifest_sha256"]
        == BASE.sha256_path(ORIGINAL_PACK / "manifest.json"),
        "original native evidence binding changed",
    )
    VERIFIER.require(
        (output / "execution.log").read_bytes()
        == BASE.normalized_log_bytes(output / "execution.log"),
        "frozen EVA scale log is not normalized",
    )
    VERIFIER.require(
        manifest["paper_claim_allowed"] is False,
        "frozen EVA scale paper gate changed",
    )
    VERIFIER.require(
        summary["policy_modifications"] == 0
        and summary["retuning"] == 0,
        "frozen EVA scale policy boundary changed",
    )
    return {
        **checked,
        "evidence_manifest_sha256": BASE.sha256_path(
            output / "manifest.json"
        ),
        "summary_sha256": BASE.sha256_path(output / "summary.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path)
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
    if args.source_root is None or args.execution_log is None:
        raise ValueError("--source-root and --execution-log are required")
    source_root = (
        args.source_root
        if args.source_root.is_absolute()
        else REPO_ROOT / args.source_root
    )
    execution_log = (
        args.execution_log
        if args.execution_log.is_absolute()
        else REPO_ROOT / args.execution_log
    )
    head, _ = BASE.clean_source_gate()
    freeze(source_root, execution_log, output, head)
    print(
        f"eva_native_scale_sensitivity_evidence=FROZEN output={output} "
        f"freezer_commit={head}"
    )


if __name__ == "__main__":
    main()
