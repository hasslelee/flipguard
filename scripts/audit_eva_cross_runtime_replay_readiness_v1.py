#!/usr/bin/env python3
"""Build and verify the fail-closed EVA cross-runtime replay readiness pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DEFAULT = (
    REPO_ROOT / "docs/evidence/eva_cross_runtime_replay_readiness_v1"
)
SCRIPT_RELATIVE = (
    "scripts/audit_eva_cross_runtime_replay_readiness_v1.py"
)
DIRECT_DIGEST = (
    "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
SECURITY_DIGEST = (
    "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)
SOURCES = {
    "native_manifest": Path(
        "docs/evidence/eva_native_scale_sensitivity_v1/manifest.json"
    ),
    "native_summary": Path(
        "docs/evidence/eva_native_scale_sensitivity_v1/summary.json"
    ),
    "native_scale30_dot": Path(
        "docs/evidence/eva_native_scale_sensitivity_v1/raw/"
        "compiled_scale_30.dot"
    ),
    "schedule_manifest": Path(
        "docs/evidence/eva_schedule_bound_adapter_replay_v1/manifest.json"
    ),
    "schedule_summary": Path(
        "docs/evidence/eva_schedule_bound_adapter_replay_v1/summary.json"
    ),
    "schedule_smoke": Path(
        "docs/evidence/eva_schedule_bound_adapter_replay_v1/runs/"
        "corrected_schedule/smoke_selection.json"
    ),
    "scale20_compiler_output": Path(
        "docs/evidence/eva_external_adapter_replay_v1/run/"
        "compiler_output.json"
    ),
    "backend_adapter": Path(
        "internal/ckksbackend/eva_execution_schedule.go"
    ),
    "provider_gate": Path(
        "internal/providergate/provider_execution_schedule.go"
    ),
    "research_boundary": Path(
        "docs/research/step_7g13_cross_runtime_evidence_boundary.md"
    ),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("ascii")


def pretty_json(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode("ascii")


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def git_blob(commit: str, relative: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def source_records() -> dict[str, dict[str, str]]:
    records: dict[str, dict[str, str]] = {}
    for name, relative in SOURCES.items():
        path = REPO_ROOT / relative
        require(path.is_file(), f"missing readiness source: {relative}")
        records[name] = {
            "path": relative.as_posix(),
            "sha256": sha256_path(path),
        }
    return records


def inspect_current_state() -> dict[str, Any]:
    native_manifest = load_json(REPO_ROOT / SOURCES["native_manifest"])
    native_summary = load_json(REPO_ROOT / SOURCES["native_summary"])
    schedule_manifest = load_json(REPO_ROOT / SOURCES["schedule_manifest"])
    schedule_summary = load_json(REPO_ROOT / SOURCES["schedule_summary"])
    schedule_smoke = load_json(REPO_ROOT / SOURCES["schedule_smoke"])
    compiler_output = load_json(
        REPO_ROOT / SOURCES["scale20_compiler_output"]
    )
    adapter_text = (
        REPO_ROOT / SOURCES["backend_adapter"]
    ).read_text(encoding="utf-8")
    provider_text = (
        REPO_ROOT / SOURCES["provider_gate"]
    ).read_text(encoding="utf-8")

    require(native_manifest["status"] == "PASS", "native pack is not PASS")
    require(
        native_manifest["direct_policy_digest"] == DIRECT_DIGEST,
        "native Direct Policy changed",
    )
    require(
        native_manifest["security_policy_digest"] == SECURITY_DIGEST,
        "native Security Policy changed",
    )
    require(
        native_summary["selected"]["input_scale_bits"] == 30,
        "native selected scale changed",
    )
    require(
        native_summary["locked_audit"]["status"] == "SAFE",
        "native selected audit is not SAFE",
    )
    require(
        native_summary["claim_states"][
            "cross_runtime_numerical_equivalence"
        ]
        == "NOT_EVALUATED",
        "native cross-runtime claim changed",
    )
    require(
        schedule_manifest["paper_claim_allowed"] is False,
        "schedule paper gate changed",
    )
    require(
        schedule_summary["corrected_smoke"]["status"] == "REJECTED",
        "schedule replay result changed",
    )

    selected = native_summary["selected"]
    exact_literal_captured = "q" in selected and "p" in selected
    scale20_concrete = compiler_output["concrete_seal_materialization"]
    same_materializer_inputs = (
        selected["poly_modulus_degree"]
        == scale20_concrete["poly_modulus_degree"]
        and selected["prime_bits"] == scale20_concrete["prime_bits"]
    )
    derived_q = scale20_concrete["first_context_coeff_modulus"]
    derived_p = [scale20_concrete["special_modulus"]]

    scale_constant = re.search(
        r"evaV101InputScaleBits\s*=\s*(\d+)", adapter_text
    )
    require(scale_constant is not None, "backend scale constant missing")
    backend_scale = int(scale_constant.group(1))
    backend_supports_selected_scale = backend_scale == 30
    backend_binds_scale20_digest = (
        "evaV101CompiledProgramSHA256" in provider_text
        and compiler_output["abstract_eva_output"][
            "compiled_program_dot_sha256"
        ]
        in provider_text
    )

    smoke_ledger = schedule_smoke["trial"]["sample_ledger"]
    native_validation_observations = sum(
        1
        for _ in (
            REPO_ROOT
            / "docs/evidence/eva_native_scale_sensitivity_v1/raw/"
            "validation_scale_30.csv"
        ).read_text(encoding="utf-8").splitlines()[1:]
        if _
    )
    native_audit_observations = sum(
        1
        for _ in (
            REPO_ROOT
            / "docs/evidence/eva_native_scale_sensitivity_v1/raw/"
            "locked_audit_selected.csv"
        ).read_text(encoding="utf-8").splitlines()[1:]
        if _
    )
    paired_population_available = (
        len(smoke_ledger) == native_validation_observations
    )

    blockers = []
    if not exact_literal_captured:
        blockers.append("SELECTED_NATIVE_EXACT_QP_NOT_CAPTURED")
    if not backend_supports_selected_scale:
        blockers.append("LATTIGO_ADAPTER_BINDS_SCALE20_NOT_SELECTED_SCALE30")
    if backend_binds_scale20_digest:
        blockers.append("PROVIDER_GATE_BINDS_SCALE20_SOURCE_DIGEST")
    if not paired_population_available:
        blockers.append("LATTIGO_NATIVE_PAIRED_POPULATION_MISSING")
    blockers.append("RUNTIME_SPECIFIC_SECURITY_DISTRIBUTIONS_DIFFER")

    return {
        "selected_native_candidate": {
            "candidate_id": selected["candidate_id"],
            "input_scale_bits": selected["input_scale_bits"],
            "poly_modulus_degree": selected["poly_modulus_degree"],
            "prime_bits": selected["prime_bits"],
            "compiled_program_sha256": selected[
                "compiled_program_sha256"
            ],
            "compiled_program_semantic_sha256": selected[
                "compiled_program_semantic_sha256"
            ],
            "exact_qp_captured_in_selected_run": exact_literal_captured,
            "validation_status": "SAFE",
            "validation_observations": native_validation_observations,
            "locked_audit_status": "SAFE",
            "locked_audit_observations": native_audit_observations,
        },
        "deterministic_materialization_bridge": {
            "same_degree_and_ordered_prime_bits_as_scale20": (
                same_materializer_inputs
            ),
            "derived_q": derived_q,
            "derived_p": derived_p,
            "status": (
                "DERIVABLE_FROM_PINNED_SEAL_MATERIALIZER_BUT_NOT_BOUND_"
                "TO_SELECTED_RUN"
            ),
            "formal_identity_usable": False,
        },
        "lattigo_adapter": {
            "implemented_input_scale_bits": backend_scale,
            "supports_selected_scale30": backend_supports_selected_scale,
            "provider_gate_binds_scale20_source_digest": (
                backend_binds_scale20_digest
            ),
            "smoke_observations": len(smoke_ledger),
            "smoke_status": schedule_smoke["trial"]["status"],
        },
        "pairing": {
            "native_validation_observations": native_validation_observations,
            "native_locked_audit_observations": native_audit_observations,
            "lattigo_observations": len(smoke_ledger),
            "matched_row_key_population_available": (
                paired_population_available
            ),
        },
        "security": {
            "direct_policy_digest": DIRECT_DIGEST,
            "security_policy_digest": SECURITY_DIGEST,
            "native_runtime_security": (
                "NOT_EVALUATED_DIFFERENT_RUNTIME_DISTRIBUTION"
            ),
            "distribution_identity": False,
        },
        "blockers": blockers,
    }


def build_summary(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": (
            "flipguard_eva_cross_runtime_replay_readiness_summary_v1"
        ),
        "status": "NOT_READY_INTEGRITY_PRESERVING_REPLAY",
        "encrypted_execution_allowed": False,
        "paper_claim_allowed": False,
        "cross_runtime_numerical_equivalence": "NOT_EVALUATED",
        "state": state,
        "required_resolution_order": [
            {
                "step": 1,
                "action": (
                    "materialize and bind exact Q/P for the selected scale-30 "
                    "compiler run using the pinned SEAL helper"
                ),
                "encrypted_execution": False,
            },
            {
                "step": 2,
                "action": (
                    "export a structured scale-30 operation/state trace and "
                    "bind its semantic and raw digests"
                ),
                "encrypted_execution": False,
            },
            {
                "step": 3,
                "action": (
                    "implement a digest-bound scale-30 Lattigo adapter and "
                    "verify every expected level and scale transition"
                ),
                "encrypted_execution": False,
            },
            {
                "step": 4,
                "action": (
                    "predeclare paired row/key roles and the decision-space "
                    "equivalence or non-inferiority tolerance"
                ),
                "encrypted_execution": False,
            },
            {
                "step": 5,
                "action": (
                    "run matched Lattigo validation and conditional locked "
                    "audit without policy retuning"
                ),
                "encrypted_execution": True,
            },
            {
                "step": 6,
                "action": (
                    "keep Lattigo and native SEAL security interpretations "
                    "separate even if numerical outcomes agree"
                ),
                "encrypted_execution": False,
            },
        ],
        "claim_boundary": {
            "native_eva_candidate_certification": "PARTIALLY_SUPPORTED",
            "native_eva_locked_audit": "PARTIALLY_SUPPORTED",
            "cross_runtime_numerical_equivalence": "NOT_EVALUATED",
            "runtime_specific_native_security": "NOT_EVALUATED",
            "general_external_autotuner_integration": "NOT_EVALUATED",
        },
        "policy_modifications": 0,
        "encrypted_executions_added": 0,
    }


def write_checksums(root: Path) -> None:
    lines = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "SHA256SUMS":
            continue
        lines.append(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  "
            f"{path.relative_to(root).as_posix()}"
        )
    (root / "SHA256SUMS").write_text(
        "\n".join(lines) + "\n", encoding="ascii"
    )


def freeze(output: Path, source_commit: str) -> None:
    require(not output.exists(), f"refusing to overwrite evidence: {output}")
    require(git("rev-parse", "HEAD") == source_commit, "source HEAD mismatch")
    require(not git("status", "--short"), "source tree is not clean")
    script_blob = git_blob(source_commit, SCRIPT_RELATIVE)
    require(
        script_blob == (REPO_ROOT / SCRIPT_RELATIVE).read_bytes(),
        "freezer source is not committed",
    )
    state = inspect_current_state()
    summary = build_summary(state)
    records = source_records()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=output.name + ".", dir=output.parent)
    )
    try:
        (temporary / "summary.json").write_bytes(pretty_json(summary))
        shutil.copyfile(
            REPO_ROOT / SOURCES["research_boundary"],
            temporary / "cross_runtime_boundary.md",
        )
        manifest = {
            "schema_version": (
                "flipguard_eva_cross_runtime_replay_readiness_evidence_v1"
            ),
            "status": summary["status"],
            "source_commit": source_commit,
            "freezer": {
                "path": SCRIPT_RELATIVE,
                "sha256": sha256_bytes(script_blob),
            },
            "sources": records,
            "summary_sha256": sha256_path(temporary / "summary.json"),
            "boundary_snapshot_sha256": sha256_path(
                temporary / "cross_runtime_boundary.md"
            ),
            "direct_policy_digest": DIRECT_DIGEST,
            "security_policy_digest": SECURITY_DIGEST,
            "encrypted_execution_allowed": False,
            "encrypted_executions_added": 0,
            "policy_modifications": 0,
            "paper_claim_allowed": False,
        }
        (temporary / "manifest.json").write_bytes(pretty_json(manifest))
        readme = (
            "# EVA Cross-Runtime Replay Readiness V1\n\n"
            "This static fail-closed pack records why the selected native "
            "scale-30 EVA result cannot yet be called a matched Lattigo-SEAL "
            "replay. It adds no encrypted execution and changes no policy.\n\n"
            f"Status: `{summary['status']}`.\n"
            "`paper_claim_allowed=false`.\n"
        )
        (temporary / "README.md").write_text(readme, encoding="ascii")
        write_checksums(temporary)
        temporary.rename(output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    verify(output)


def verify_checksums(root: Path) -> None:
    lines = (root / "SHA256SUMS").read_text(encoding="ascii").splitlines()
    listed = set()
    for line in lines:
        digest, relative = line.split("  ", 1)
        path = root / relative
        require(path.is_file(), f"checksum path missing: {relative}")
        require(
            hashlib.sha256(path.read_bytes()).hexdigest() == digest,
            f"checksum mismatch: {relative}",
        )
        listed.add(relative)
    expected = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    require(listed == expected, "checksum inventory changed")


def verify(output: Path) -> None:
    manifest = load_json(output / "manifest.json")
    summary = load_json(output / "summary.json")
    require(
        manifest["schema_version"]
        == "flipguard_eva_cross_runtime_replay_readiness_evidence_v1",
        "readiness evidence schema changed",
    )
    require(
        summary["status"] == "NOT_READY_INTEGRITY_PRESERVING_REPLAY",
        "readiness status changed",
    )
    require(
        summary["encrypted_execution_allowed"] is False,
        "cross-runtime execution was incorrectly opened",
    )
    require(summary["paper_claim_allowed"] is False, "paper gate changed")
    require(
        summary["cross_runtime_numerical_equivalence"] == "NOT_EVALUATED",
        "cross-runtime claim changed",
    )
    require(summary["policy_modifications"] == 0, "policy was modified")
    require(
        summary["encrypted_executions_added"] == 0,
        "static pack claims encrypted execution",
    )
    blockers = summary["state"]["blockers"]
    required_blockers = {
        "SELECTED_NATIVE_EXACT_QP_NOT_CAPTURED",
        "LATTIGO_ADAPTER_BINDS_SCALE20_NOT_SELECTED_SCALE30",
        "PROVIDER_GATE_BINDS_SCALE20_SOURCE_DIGEST",
        "LATTIGO_NATIVE_PAIRED_POPULATION_MISSING",
        "RUNTIME_SPECIFIC_SECURITY_DISTRIBUTIONS_DIFFER",
    }
    require(set(blockers) == required_blockers, "readiness blockers changed")
    require(
        manifest["summary_sha256"] == sha256_path(output / "summary.json"),
        "summary digest changed",
    )
    require(
        manifest["boundary_snapshot_sha256"]
        == sha256_path(output / "cross_runtime_boundary.md"),
        "boundary snapshot digest changed",
    )
    script_blob = git_blob(
        manifest["source_commit"], manifest["freezer"]["path"]
    )
    require(
        sha256_bytes(script_blob) == manifest["freezer"]["sha256"],
        "historical freezer digest changed",
    )
    for record in manifest["sources"].values():
        require(
            sha256_path(REPO_ROOT / record["path"]) == record["sha256"],
            f"bound source changed: {record['path']}",
        )
    require(
        manifest["direct_policy_digest"] == DIRECT_DIGEST,
        "Direct Policy digest changed",
    )
    require(
        manifest["security_policy_digest"] == SECURITY_DIGEST,
        "Security Policy digest changed",
    )
    require(manifest["paper_claim_allowed"] is False, "manifest paper gate")
    verify_checksums(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--source-commit")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    output = (
        args.output_root
        if args.output_root.is_absolute()
        else REPO_ROOT / args.output_root
    )
    if args.verify:
        verify(output)
    else:
        require(args.source_commit is not None, "--source-commit is required")
        freeze(output, args.source_commit)
    print(
        "eva_cross_runtime_replay_readiness_v1="
        "NOT_READY_INTEGRITY_PRESERVING_REPLAY "
        "encrypted_execution_allowed=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
