#!/usr/bin/env python3
"""Verify the exact pinned EVA compiler replay output."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = Path(
    "docs/evidence/eva_external_adapter_replay_v1/run"
)
CONTRACT_PATH = REPO_ROOT / (
    "experiments/eva_external_adapter_v1/contract.json"
)
CONTRACT_VERIFIER_PATH = REPO_ROOT / (
    "scripts/verify_eva_external_adapter_contract.py"
)
EXPORTER_PATH = REPO_ROOT / "scripts/export_eva_external_candidate.py"

EXPECTED_RUN_ID = "30553813485"
EXPECTED_COMMIT = "04938d9d330c4994baaf45048704dbd17e4ab7d0"
EXPECTED_OUTPUT_SHA256 = (
    "sha256:"
    "605cc94bb1df230f9d58b1cbbeb66a26d11b6ae44ed4ad46dfca0925cd711dea"
)
EXPECTED_DOT_SHA256 = (
    "sha256:"
    "3c5ec469e692ea17dd413180c6c37c5042ef7bb5bfedd968d19447242fd72bca"
)
EXPECTED_Q = [
    1152921504605962241,
    1152921504606584833,
    1152921504606683137,
]
EXPECTED_P = [1152921504606748673]


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTRACT_VERIFIER = load_module(
    "verify_eva_contract_for_output",
    CONTRACT_VERIFIER_PATH,
)
EXPORTER = load_module(
    "export_eva_candidate_for_output",
    EXPORTER_PATH,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="ascii"))
    require(isinstance(value, dict), f"{path}: expected JSON object")
    return value


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def verify_sha256sums(root: Path) -> None:
    checksum_path = root / "SHA256SUMS"
    require(checksum_path.is_file(), "raw SHA256SUMS is missing")
    expected_names: set[str] = set()
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        digest, name = line.split(None, 1)
        name = name.lstrip("*")
        path = root / name
        require(path.is_file(), f"checksummed file is missing: {name}")
        require(
            sha256_path(path) == "sha256:" + digest,
            f"checksum mismatch: {name}",
        )
        expected_names.add(name)
    actual_names = {
        path.name
        for path in root.iterdir()
        if path.is_file() and path.name != "contract_verification.txt"
    }
    require(
        expected_names == actual_names - {"SHA256SUMS"},
        "raw checksummed file inventory changed",
    )


def is_prime_u64(value: int) -> bool:
    if value < 2:
        return False
    small_primes = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    for prime in small_primes:
        if value % prime == 0:
            return value == prime
    exponent = value - 1
    shifts = 0
    while exponent % 2 == 0:
        shifts += 1
        exponent //= 2
    # Deterministic for every unsigned 64-bit integer.
    for base in (2, 325, 9375, 28178, 450775, 9780504, 1795265022):
        if base % value == 0:
            continue
        result = pow(base, exponent, value)
        if result in (1, value - 1):
            continue
        for _ in range(shifts - 1):
            result = (result * result) % value
            if result == value - 1:
                break
        else:
            return False
    return True


def source_rows(contract: dict[str, Any]) -> list[dict[str, Any]]:
    fields = ("source_id", "repository", "path", "sha256", "role")
    return [
        {field: source[field] for field in fields}
        for source in contract["sources"]
    ]


def verify(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    root = root if root.is_absolute() else REPO_ROOT / root
    require(root.is_dir(), f"EVA compiler replay root is missing: {root}")
    verify_sha256sums(root)
    contract_summary = CONTRACT_VERIFIER.validate_contract(
        CONTRACT_PATH,
        require_runtime_artifacts=True,
    )
    contract = load_json(CONTRACT_PATH)
    output_path = root / "compiler_output.json"
    dot_path = root / "compiled_program.dot"
    require(
        sha256_path(output_path) == EXPECTED_OUTPUT_SHA256,
        "compiler output digest changed",
    )
    require(
        sha256_path(dot_path) == EXPECTED_DOT_SHA256,
        "compiled DOT digest changed",
    )
    output = load_json(output_path)
    require(
        output["schema_version"] ==
        "flipguard_eva_external_compiler_output_v1",
        "compiler output schema changed",
    )
    require(
        output["classification"] ==
        "SOURCE_REPLAYED_PUBLIC_COMPILER_PARAMETER_OUTPUT",
        "compiler output classification changed",
    )
    require(output["flipguard_commit"] == EXPECTED_COMMIT,
            "compiler execution commit changed")
    require(output["action_run_id"] == EXPECTED_RUN_ID,
            "GitHub Actions run ID changed")
    require(
        output["contract_sha256"] == contract_summary["contract_sha256"],
        "compiler contract binding changed",
    )
    require(
        output["model_sha256"] == contract["workload"]["model_sha256"],
        "compiler model binding changed",
    )
    require(output["upstream"] == contract["upstream"],
            "upstream binding changed")
    require(
        [
            {
                key: source[key]
                for key in ("source_id", "repository", "path", "sha256", "role")
            }
            for source in output["source_manifest"]
        ] == source_rows(contract),
        "pinned source manifest changed",
    )
    require(
        output["compiler_input"] == contract["compiler_input"],
        "compiler input changed",
    )

    abstract = output["abstract_eva_output"]
    require(
        abstract["poly_modulus_degree"] == 16384,
        "EVA degree changed",
    )
    require(abstract["prime_bits"] == [60, 60, 60, 60],
            "EVA prime bits changed")
    require(abstract["rotations"] == [], "EVA rotations changed")
    require(
        abstract["compiled_program_dot_sha256"] == EXPECTED_DOT_SHA256,
        "compiled DOT binding changed",
    )
    require(
        [row["name"] for row in abstract["signature"]] ==
        contract["compiler_input"]["input_names"],
        "EVA input signature changed",
    )
    require(
        all(
            row["scale"] == 20
            and row["level"] == 0
            and row["input_type"] == "Type.Cipher"
            for row in abstract["signature"]
        ),
        "EVA input encoding signature changed",
    )

    materialized = output["concrete_seal_materialization"]
    q, p = EXPORTER.validate_materialization(
        abstract["poly_modulus_degree"],
        abstract["prime_bits"],
        materialized,
    )
    require(q == EXPECTED_Q, "concrete EVA Q changed")
    require(p == EXPECTED_P, "concrete EVA P changed")
    require(
        all(is_prime_u64(value) for value in q + p),
        "concrete SEAL modulus is not prime",
    )
    request, gate = EXPORTER.derive_candidate(
        contract,
        abstract["poly_modulus_degree"],
        q,
        p,
    )
    require(output["candidate_request"] == request,
            "candidate translation changed")
    require(output["preflight_gate"] == gate,
            "candidate preflight gate changed")
    require(
        gate == {
            "status": "BLOCKED_GRAPH_COMPATIBILITY",
            "security": {
                "log_n": 14,
                "log_q": 180,
                "log_p": 60,
                "log_qp": 240,
                "security_v2_cap": 430,
                "ciphertext_q_admission": "PASS",
                "evaluation_key_qp_admission": "PASS",
                "final_admission": "PASS",
                "headroom_bits": 190,
            },
            "graph_compatible": False,
            "required_q_primes": 7,
            "actual_q_primes": 3,
            "required_slots": 1,
            "actual_slots": 8192,
            "encrypted_execution_allowed": False,
        },
        "fail-closed EVA result changed",
    )
    require(
        output["runtime_boundary"] == contract["runtime_boundary"],
        "runtime boundary changed",
    )
    require(output["paper_claim_allowed"] is False,
            "paper claim gate opened")

    require(
        (root / "eva_git_status.txt").read_text(encoding="ascii") == "",
        "EVA source tree was modified",
    )
    require(
        (root / "seal_git_status.txt").read_text(encoding="ascii") == "",
        "SEAL source tree was modified",
    )
    build_flags = (root / "seal_build_flags.txt").read_text(
        encoding="ascii"
    )
    for line in (
        "CMAKE_CXX_FLAGS:STRING=-include mutex",
        "SEAL_THROW_ON_TRANSPARENT_CIPHERTEXT:BOOL=OFF",
        "SEAL_USE_GAUSSIAN_NOISE:BOOL=OFF",
    ):
        require(line in build_flags, f"missing SEAL build flag: {line}")
    contract_log = (root / "contract_verification.txt").read_text(
        encoding="ascii"
    )
    require(
        "runtime_artifacts=false" in contract_log
        and contract_summary["contract_sha256"] in contract_log,
        "compiler-only contract verification log changed",
    )

    return {
        "schema_version":
            "flipguard_eva_external_adapter_output_summary_v1",
        "status": "BLOCKED_GRAPH_COMPATIBILITY",
        "compiler_replay": "PASS",
        "source_count": len(output["source_manifest"]),
        "compiler_execution_commit": output["flipguard_commit"],
        "github_actions_run_id": output["action_run_id"],
        "compiler_output_sha256": sha256_path(output_path),
        "compiled_program_dot_sha256": sha256_path(dot_path),
        "log_n": 14,
        "q_prime_count": 3,
        "p_prime_count": 1,
        "log_q": 180,
        "log_p": 60,
        "log_qp": 240,
        "security_v2_cap": 430,
        "security_v2_headroom_bits": 190,
        "security_v2_admission": "PASS",
        "required_q_primes": 7,
        "graph_compatible": False,
        "encrypted_execution_allowed": False,
        "encrypted_candidate_trials": 0,
        "encrypted_key_runs": 0,
        "encrypted_sample_evaluations": 0,
        "synthesis_calls": 0,
        "repair_calls": 0,
        "retuning": 0,
        "paper_claim_allowed": False,
    }


def main() -> None:
    summary = verify(parse_args().root)
    print(
        "eva_external_adapter_output=VERIFIED "
        f"status={summary['status']} "
        f"logN={summary['log_n']} "
        f"Q={summary['q_prime_count']} "
        f"P={summary['p_prime_count']} "
        f"logQP={summary['log_qp']} "
        f"headroom={summary['security_v2_headroom_bits']} "
        f"encrypted_trials={summary['encrypted_candidate_trials']}"
    )


if __name__ == "__main__":
    main()
