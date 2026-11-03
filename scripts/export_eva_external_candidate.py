#!/usr/bin/env python3
"""Run pinned EVA compilation and export its exact SEAL modulus proposal."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFY_PATH = REPO_ROOT / (
    "scripts/verify_eva_external_adapter_contract.py"
)
SPEC = importlib.util.spec_from_file_location(
    "verify_eva_contract_for_exporter",
    VERIFY_PATH,
)
assert SPEC is not None and SPEC.loader is not None
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)

OUTPUT_SCHEMA = "flipguard_eva_external_compiler_output_v1"
PROVIDER_ID = "microsoft_eva_v1.0.1_seal3.6.4_source_replay_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path("experiments/eva_external_adapter_v1/contract.json"),
    )
    parser.add_argument("--eva-root", type=Path, required=True)
    parser.add_argument("--seal-root", type=Path, required=True)
    parser.add_argument("--prime-exporter", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dot-output", type=Path, required=True)
    parser.add_argument("--flipguard-commit", required=True)
    parser.add_argument("--action-run-id", required=True)
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


def verify_sources(
    contract: dict[str, Any],
    eva_root: Path,
    seal_root: Path,
) -> list[dict[str, Any]]:
    roots = {"eva": eva_root, "seal": seal_root}
    verified: list[dict[str, Any]] = []
    for source in contract["sources"]:
        path = roots[source["repository"]] / source["path"]
        if not path.is_file():
            raise ValueError(f"missing pinned source: {path}")
        actual = sha256_path(path)
        if actual != source["sha256"]:
            raise ValueError(
                f"INTEGRITY_BLOCK: {source['source_id']} digest "
                f"{actual} != {source['sha256']}"
            )
        verified.append({
            **source,
            "verified_path": path.as_posix(),
        })
    return verified


def build_program(
    contract: dict[str, Any],
    model: dict[str, Any],
) -> tuple[Any, list[str]]:
    from eva import EvaProgram, Input, Output

    compiler_input = contract["compiler_input"]
    if model["model_type"] != "linear_poly3":
        raise ValueError("EVA replay supports only the predeclared linear model")
    if model["polynomial_score"]["formula"] != \
            "0.5 + 0.197*z - 0.004*z^3":
        raise ValueError("model score formula changed")
    weights = model["scaled_model_for_ckks"]["weights"]
    bias = model["scaled_model_for_ckks"]["bias"]
    names = compiler_input["input_names"]
    if len(weights) != len(names) or model["input_dim"] != len(names):
        raise ValueError("model input dimension changed")

    program = EvaProgram(
        compiler_input["program_id"],
        vec_size=compiler_input["vector_size"],
    )
    with program:
        inputs = [Input(name) for name in names]
        z = bias
        for weight, value in zip(weights, inputs):
            z = z + weight * value
        score = 0.5 + 0.197 * z - 0.004 * (z ** 3)
        Output("score", score)
    program.set_input_scales(compiler_input["input_scale_bits"])
    program.set_output_ranges(compiler_input["output_range_bits"])
    return program, names


def compile_program(
    contract: dict[str, Any],
    model: dict[str, Any],
) -> tuple[Any, Any, Any, list[str]]:
    from eva.ckks import CKKSCompiler

    program, names = build_program(contract, model)
    config = contract["compiler_input"]["compiler_config"]
    compiler = CKKSCompiler({
        "balance_reductions": str(config["balance_reductions"]).lower(),
        "rescaler": config["rescaler"],
        "lazy_relinearize": str(config["lazy_relinearize"]).lower(),
        "security_level": str(config["security_level"]),
        "quantum_safe": str(config["quantum_safe"]).lower(),
        "warn_vec_size": str(config["warn_vec_size"]).lower(),
    })
    compiled, parameters, signature = compiler.compile(program)
    return compiled, parameters, signature, names


def run_prime_exporter(
    executable: Path,
    degree: int,
    prime_bits: list[int],
) -> dict[str, Any]:
    completed = subprocess.run(
        [str(executable), str(degree), *[str(value) for value in prime_bits]],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise ValueError("prime exporter did not return a JSON object")
    return value


def product_bit_length(values: list[int]) -> int:
    product = 1
    for value in values:
        product *= value
    return product.bit_length()


def validate_materialization(
    degree: int,
    prime_bits: list[int],
    materialized: dict[str, Any],
) -> tuple[list[int], list[int]]:
    if materialized["schema_version"] != \
            "flipguard_eva_seal_prime_materialization_v1":
        raise ValueError("prime materialization schema changed")
    if materialized["poly_modulus_degree"] != degree:
        raise ValueError("prime materialization degree changed")
    if materialized["prime_bits"] != prime_bits:
        raise ValueError("prime materialization bit sizes changed")
    key = materialized["key_context_coeff_modulus"]
    q = materialized["first_context_coeff_modulus"]
    p = [materialized["special_modulus"]]
    if (
        materialized["using_keyswitching"] is not True
        or len(key) != len(q) + 1
        or key[:-1] != q
        or key[-1:] != p
        or len(set(key)) != len(key)
    ):
        raise ValueError("SEAL key/ciphertext modulus split changed")
    modulus = 2 * degree
    for expected_bits, prime in zip(prime_bits, key):
        if (
            prime <= 0
            or prime.bit_length() != expected_bits
            or prime % modulus != 1
        ):
            raise ValueError("materialized NTT prime is inconsistent")
    return q, p


def derive_candidate(
    contract: dict[str, Any],
    degree: int,
    q: list[int],
    p: list[int],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if degree <= 0 or degree & (degree - 1):
        raise ValueError("EVA poly modulus degree is not a power of two")
    log_n = int(math.log2(degree))
    caps = contract["policy"]["security_v2_caps"]
    cap = caps.get(str(log_n))
    log_q = product_bit_length(q)
    log_p = product_bit_length(p)
    log_qp = product_bit_length(q + p)
    q_admission = "PASS" if cap is not None and log_q <= cap else "FAIL"
    qp_admission = "PASS" if cap is not None and log_qp <= cap else "FAIL"
    security = {
        "log_n": log_n,
        "log_q": log_q,
        "log_p": log_p,
        "log_qp": log_qp,
        "security_v2_cap": cap,
        "ciphertext_q_admission": q_admission,
        "evaluation_key_qp_admission": qp_admission,
        "final_admission": (
            "PASS"
            if q_admission == "PASS" and qp_admission == "PASS"
            else "FAIL"
        ),
        "headroom_bits": cap - log_qp if cap is not None else None,
    }
    translation = contract["translation_contract"]
    graph_compatible = (
        len(q) >= translation["required_q_primes"]
        and degree // 2 >= translation["required_slots"]
    )
    if security["final_admission"] != "PASS":
        status = "BLOCKED_SECURITY_V2"
    elif not graph_compatible:
        status = "BLOCKED_GRAPH_COMPATIBILITY"
    else:
        status = "ELIGIBLE_FOR_ONE_TRIAL_PROVIDER_GATE"
    request = {
        "schema_version": 2,
        "provider_kind": "external_autotuner",
        "provider_id": PROVIDER_ID,
        "path": translation["path"],
        "parameters": {
            "log_n": log_n,
            "q": q,
            "p": p,
            "log_default_scale":
                contract["compiler_input"]["input_scale_bits"],
        },
    }
    gate = {
        "status": status,
        "security": security,
        "graph_compatible": graph_compatible,
        "required_q_primes": translation["required_q_primes"],
        "actual_q_primes": len(q),
        "required_slots": translation["required_slots"],
        "actual_slots": degree // 2,
        "encrypted_execution_allowed":
            status == "ELIGIBLE_FOR_ONE_TRIAL_PROVIDER_GATE",
    }
    return request, gate


def signature_rows(signature: Any, names: list[str]) -> list[dict[str, Any]]:
    rows = []
    for name in names:
        info = signature.inputs[name]
        rows.append({
            "name": name,
            "scale": int(info.scale),
            "level": int(info.level),
            "input_type": str(info.input_type),
        })
    return rows


def main() -> None:
    args = parse_args()
    contract_path = (
        args.contract
        if args.contract.is_absolute()
        else REPO_ROOT / args.contract
    )
    VERIFIER.validate_contract(
        contract_path,
        require_runtime_artifacts=False,
    )
    contract = load_json(contract_path)
    source_manifest = verify_sources(
        contract,
        args.eva_root,
        args.seal_root,
    )
    model_path = REPO_ROOT / contract["workload"]["model_path"]
    model = load_json(model_path)
    compiled, parameters, signature, names = compile_program(
        contract,
        model,
    )
    dot = compiled.to_DOT().encode("utf-8")
    save_atomic(args.dot_output, dot)
    prime_bits = [int(value) for value in parameters.prime_bits]
    degree = int(parameters.poly_modulus_degree)
    materialized = run_prime_exporter(
        args.prime_exporter,
        degree,
        prime_bits,
    )
    q, p = validate_materialization(
        degree,
        prime_bits,
        materialized,
    )
    request, gate = derive_candidate(contract, degree, q, p)

    output = {
        "schema_version": OUTPUT_SCHEMA,
        "classification":
            "SOURCE_REPLAYED_PUBLIC_COMPILER_PARAMETER_OUTPUT",
        "flipguard_commit": args.flipguard_commit,
        "action_run_id": args.action_run_id,
        "contract_sha256": sha256_path(contract_path),
        "model_sha256": sha256_path(model_path),
        "upstream": contract["upstream"],
        "source_manifest": source_manifest,
        "compiler_input": contract["compiler_input"],
        "abstract_eva_output": {
            "poly_modulus_degree": degree,
            "prime_bits": prime_bits,
            "rotations": sorted(int(value) for value in parameters.rotations),
            "signature": signature_rows(signature, names),
            "compiled_program_dot_sha256": sha256_path(args.dot_output),
        },
        "concrete_seal_materialization": materialized,
        "candidate_request": request,
        "preflight_gate": gate,
        "runtime_boundary": contract["runtime_boundary"],
        "paper_claim_allowed": False,
    }
    save_atomic(args.output, canonical_json(output))
    print(
        "eva_external_candidate=EXPORTED "
        f"status={gate['status']} "
        f"logN={request['parameters']['log_n']} "
        f"q_primes={len(q)} "
        f"logQP={gate['security']['log_qp']} "
        f"output={args.output}"
    )


if __name__ == "__main__":
    main()
