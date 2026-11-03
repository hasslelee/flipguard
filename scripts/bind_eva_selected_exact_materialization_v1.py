#!/usr/bin/env python3
"""Bind exact SEAL Q/P to the selected native EVA scale-30 candidate."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_RELATIVE = "scripts/bind_eva_selected_exact_materialization_v1.py"
OUTPUT_DEFAULT = (
    REPO_ROOT / "docs/evidence/eva_selected_exact_materialization_v1"
)
NATIVE_SUMMARY = Path(
    "docs/evidence/eva_native_scale_sensitivity_v1/summary.json"
)
NATIVE_MANIFEST = Path(
    "docs/evidence/eva_native_scale_sensitivity_v1/manifest.json"
)
NATIVE_SCALE30_DOT = Path(
    "docs/evidence/eva_native_scale_sensitivity_v1/raw/"
    "compiled_scale_30.dot"
)
NATIVE_CONTRACT = Path(
    "experiments/eva_native_scale_sensitivity_v1/contract.json"
)
COMPILER_ROOT = Path(
    "docs/evidence/eva_external_adapter_replay_v1/run"
)
COMPILER_OUTPUT = COMPILER_ROOT / "compiler_output.json"
COMPILER_VERIFY_PATH = (
    REPO_ROOT / "scripts/verify_eva_external_adapter_output.py"
)
EXPORTER_PATH = REPO_ROOT / "scripts/export_eva_external_candidate.py"
DIRECT_DIGEST = (
    "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
SECURITY_DIGEST = (
    "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMPILER_VERIFY = load_module(
    "verify_eva_external_adapter_for_selected_binding",
    COMPILER_VERIFY_PATH,
)
EXPORTER = load_module(
    "export_eva_external_candidate_for_selected_binding",
    EXPORTER_PATH,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("ascii")


def pretty_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        + "\n"
    ).encode("ascii")


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def load_json(relative: Path) -> dict[str, Any]:
    path = relative if relative.is_absolute() else REPO_ROOT / relative
    value = json.loads(path.read_text(encoding="ascii"))
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


def product_bit_length(values: list[int]) -> int:
    product = math.prod(values)
    return product.bit_length()


def build_binding() -> dict[str, Any]:
    compiler_checked = COMPILER_VERIFY.verify(COMPILER_ROOT)
    native_summary = load_json(NATIVE_SUMMARY)
    native_manifest = load_json(NATIVE_MANIFEST)
    native_contract = load_json(NATIVE_CONTRACT)
    compiler_output = load_json(COMPILER_OUTPUT)
    selected = native_summary["selected"]
    materialized = compiler_output["concrete_seal_materialization"]

    require(
        native_summary["status"] == "PASS"
        and native_manifest["status"] == "PASS",
        "native pack is not PASS",
    )
    require(
        native_manifest["direct_policy_digest"] == DIRECT_DIGEST,
        "Direct Policy digest changed",
    )
    require(
        native_manifest["security_policy_digest"] == SECURITY_DIGEST,
        "Security Policy digest changed",
    )
    require(
        native_summary["locked_audit"]["status"] == "SAFE",
        "selected native locked audit is not SAFE",
    )
    require(
        selected["input_scale_bits"] == 30,
        "selected native input scale changed",
    )
    require(
        sha256_path(REPO_ROOT / NATIVE_SCALE30_DOT)
        == selected["compiled_program_sha256"],
        "selected compiled graph digest changed",
    )
    require(
        selected["poly_modulus_degree"]
        == materialized["poly_modulus_degree"],
        "materializer degree does not match selected candidate",
    )
    require(
        selected["prime_bits"] == materialized["prime_bits"],
        "materializer ordered prime bits do not match selected candidate",
    )
    require(
        native_contract["upstream"] == compiler_output["upstream"],
        "native and materializer upstream commits differ",
    )
    require(
        native_contract["source_binding"]["model_sha256"]
        == compiler_output["model_sha256"],
        "native and materializer model binding differs",
    )
    require(
        compiler_checked["compiler_replay"] == "PASS",
        "pinned compiler materialization is not verified",
    )

    q, p = EXPORTER.validate_materialization(
        selected["poly_modulus_degree"],
        selected["prime_bits"],
        materialized,
    )
    require(
        all(COMPILER_VERIFY.is_prime_u64(value) for value in q + p),
        "bound modulus contains a non-prime value",
    )

    exact_literal = {
        "schema_version": 2,
        "provider_kind": "external_autotuner",
        "provider_id": (
            "microsoft_eva_v1.0.1_seal3.6.4_"
            "selected_scale30_posthoc_materialization_v1"
        ),
        "path": "rescale",
        "parameters": {
            "log_n": int(
                math.log2(selected["poly_modulus_degree"])
            ),
            "q": q,
            "p": p,
            "log_default_scale": selected["input_scale_bits"],
        },
    }
    cap = native_contract["security_reference"]["caps"][
        str(exact_literal["parameters"]["log_n"])
    ]
    log_q = product_bit_length(q)
    log_p = product_bit_length(p)
    log_qp = product_bit_length(q + p)
    security = {
        "security_policy_digest": SECURITY_DIGEST,
        "reference_only_for_native_seal_runtime": True,
        "log_n": exact_literal["parameters"]["log_n"],
        "log_q": log_q,
        "log_p": log_p,
        "log_qp": log_qp,
        "cap": cap,
        "ciphertext_q_admission": (
            "PASS" if log_q <= cap else "FAIL"
        ),
        "evaluation_key_qp_admission": (
            "PASS" if log_qp <= cap else "FAIL"
        ),
        "headroom_bits": cap - log_qp,
        "runtime_specific_native_security": "NOT_EVALUATED",
    }
    security["final_reference_admission"] = (
        "PASS"
        if security["ciphertext_q_admission"] == "PASS"
        and security["evaluation_key_qp_admission"] == "PASS"
        else "FAIL"
    )
    require(
        security["final_reference_admission"] == "PASS",
        "selected exact materialization fails Security V2 reference cap",
    )

    source_files = {
        "native_summary": NATIVE_SUMMARY,
        "native_manifest": NATIVE_MANIFEST,
        "native_scale30_dot": NATIVE_SCALE30_DOT,
        "native_contract": NATIVE_CONTRACT,
        "compiler_output": COMPILER_OUTPUT,
        "compiler_raw_sha256sums": COMPILER_ROOT / "SHA256SUMS",
        "compiler_verifier": Path(
            "scripts/verify_eva_external_adapter_output.py"
        ),
        "prime_exporter": Path(
            "tools/eva-seal-prime-exporter/main.cpp"
        ),
    }
    sources = {
        name: {
            "path": relative.as_posix(),
            "sha256": sha256_path(REPO_ROOT / relative),
        }
        for name, relative in source_files.items()
    }

    return {
        "schema_version": (
            "flipguard_eva_selected_exact_materialization_binding_v1"
        ),
        "status": "EXACT_MATERIALIZATION_BOUND_POSTHOC",
        "classification": "STATIC_PROVENANCE_BINDING_NO_ENCRYPTION",
        "selected_candidate": {
            **selected,
            "native_evidence_manifest_sha256": sha256_path(
                REPO_ROOT / NATIVE_MANIFEST
            ),
        },
        "materializer_bridge": {
            "upstream": compiler_output["upstream"],
            "compiler_execution_commit": compiler_output[
                "flipguard_commit"
            ],
            "github_actions_run_id": compiler_output["action_run_id"],
            "compiler_output_sha256": sha256_path(
                REPO_ROOT / COMPILER_OUTPUT
            ),
            "same_poly_modulus_degree": True,
            "same_ordered_prime_bits": True,
            "deterministic_materializer_inputs_identical": True,
            "exact_qp_captured_in_original_selected_run": False,
            "exact_qp_bound_by_posthoc_static_replay": True,
        },
        "exact_literal": exact_literal,
        "exact_literal_sha256": sha256_bytes(
            canonical_json(exact_literal)
        ),
        "security_reference": security,
        "sources": sources,
        "claim_boundary": {
            "exact_selected_qp_materialization": "SUPPORTED",
            "native_execution_literal_serialization_identity": (
                "NOT_EVALUATED"
            ),
            "cross_runtime_numerical_equivalence": "NOT_EVALUATED",
            "runtime_specific_native_security": "NOT_EVALUATED",
            "general_external_autotuner_integration": "NOT_EVALUATED",
        },
        "encrypted_executions_added": 0,
        "policy_modifications": 0,
        "paper_claim_allowed": False,
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


def verify_checksums(root: Path) -> None:
    listed = set()
    for line in (root / "SHA256SUMS").read_text(
        encoding="ascii"
    ).splitlines():
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


def freeze(output: Path, source_commit: str) -> None:
    require(not output.exists(), f"refusing to overwrite evidence: {output}")
    require(git("rev-parse", "HEAD") == source_commit, "source HEAD mismatch")
    require(not git("status", "--short"), "source tree is not clean")
    script_blob = git_blob(source_commit, SCRIPT_RELATIVE)
    require(
        script_blob == (REPO_ROOT / SCRIPT_RELATIVE).read_bytes(),
        "binding source is not committed",
    )
    binding = build_binding()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=output.name + ".", dir=output.parent)
    )
    try:
        (temporary / "materialization.json").write_bytes(
            pretty_json(binding)
        )
        manifest = {
            "schema_version": (
                "flipguard_eva_selected_exact_materialization_evidence_v1"
            ),
            "evidence_id": "eva_selected_exact_materialization_v1",
            "status": binding["status"],
            "source_commit": source_commit,
            "builder": {
                "path": SCRIPT_RELATIVE,
                "sha256": sha256_bytes(script_blob),
            },
            "materialization_sha256": sha256_path(
                temporary / "materialization.json"
            ),
            "exact_literal_sha256": binding["exact_literal_sha256"],
            "direct_policy_digest": DIRECT_DIGEST,
            "security_policy_digest": SECURITY_DIGEST,
            "encrypted_executions_added": 0,
            "policy_modifications": 0,
            "paper_claim_allowed": False,
        }
        (temporary / "manifest.json").write_bytes(pretty_json(manifest))
        (temporary / "README.md").write_text(
            "# EVA Selected Exact Materialization V1\n\n"
            "This static post-hoc provenance binding attaches the exact "
            "SEAL v3.6.4 Q/P sequence to the selected native EVA scale-30 "
            "candidate. The original run did not serialize Q/P; this pack "
            "does not rewrite that history. It uses the selected run's "
            "degree and ordered prime-bit vector and the independently "
            "verified deterministic SEAL materializer output.\n\n"
            "No encryption or policy modification was performed. "
            "Cross-runtime numerical equivalence and native runtime "
            "security remain `NOT_EVALUATED`; "
            "`paper_claim_allowed=false`.\n",
            encoding="ascii",
        )
        write_checksums(temporary)
        temporary.rename(output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    verify(output)


def verify(output: Path = OUTPUT_DEFAULT) -> dict[str, Any]:
    output = output if output.is_absolute() else REPO_ROOT / output
    verify_checksums(output)
    binding = load_json(output / "materialization.json")
    manifest = load_json(output / "manifest.json")
    require(binding == build_binding(), "materialization replay changed")
    require(
        manifest["schema_version"]
        == "flipguard_eva_selected_exact_materialization_evidence_v1",
        "evidence schema changed",
    )
    require(
        manifest["status"] == "EXACT_MATERIALIZATION_BOUND_POSTHOC",
        "evidence status changed",
    )
    require(
        manifest["materialization_sha256"]
        == sha256_path(output / "materialization.json"),
        "materialization digest changed",
    )
    require(
        manifest["exact_literal_sha256"]
        == binding["exact_literal_sha256"],
        "exact literal digest changed",
    )
    require(
        manifest["encrypted_executions_added"] == 0
        and manifest["policy_modifications"] == 0,
        "static binding changed execution or policy",
    )
    require(
        manifest["paper_claim_allowed"] is False,
        "paper claim gate opened",
    )
    script_blob = git_blob(
        manifest["source_commit"], manifest["builder"]["path"]
    )
    require(
        sha256_bytes(script_blob) == manifest["builder"]["sha256"],
        "historical builder digest changed",
    )
    return {
        "status": manifest["status"],
        "candidate_id": binding["selected_candidate"]["candidate_id"],
        "exact_literal_sha256": binding["exact_literal_sha256"],
        "q_primes": len(
            binding["exact_literal"]["parameters"]["q"]
        ),
        "p_primes": len(
            binding["exact_literal"]["parameters"]["p"]
        ),
        "log_qp": binding["security_reference"]["log_qp"],
        "headroom_bits": binding[
            "security_reference"
        ]["headroom_bits"],
        "cross_runtime_numerical_equivalence": binding[
            "claim_boundary"
        ]["cross_runtime_numerical_equivalence"],
        "paper_claim_allowed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = (
        args.output
        if args.output.is_absolute()
        else REPO_ROOT / args.output
    )
    if args.verify:
        result = verify(output)
        print(
            "eva_selected_exact_materialization=VERIFIED "
            f"candidate={result['candidate_id']} "
            f"Q={result['q_primes']} P={result['p_primes']} "
            f"logQP={result['log_qp']} "
            f"headroom={result['headroom_bits']}"
        )
        return
    source_commit = git("rev-parse", "HEAD")
    freeze(output, source_commit)
    print(
        "eva_selected_exact_materialization=FROZEN "
        f"output={output} source_commit={source_commit}"
    )


if __name__ == "__main__":
    main()
