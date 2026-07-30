#!/usr/bin/env python3
"""Run exact-modulus LWE estimates under a pinned estimator checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
import traceback
from functools import reduce
from operator import mul
from pathlib import Path
from typing import Any

from sage.all import N, log, oo

from estimator import LWE, ND, RC


SCHEMA_VERSION = "flipguard_exact_security_estimator_run_v1"
ATTACKS = ("primal_usvp", "primal_bdd", "dual_hybrid")
TARGET_SECURITY_BITS = 128


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


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def signature_payload(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "log_n": entry["signature"]["log_n"],
        "exact_q_primes": entry["exact_q_primes"],
        "exact_p_primes": entry["exact_p_primes"],
        "xs": entry["xs"],
        "xe": entry["xe"],
    }


def signature_id(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload)).hexdigest()[:16]


def exact_product(values: list[int]) -> int:
    return reduce(mul, values, 1)


def cost_field(cost: Any, name: str) -> str | None:
    try:
        value = cost[name]
    except (KeyError, TypeError):
        return None
    return str(value)


def estimate_attack(
    name: str,
    params: Any,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        if name == "primal_usvp":
            cost = LWE.primal_usvp(params, red_cost_model=RC.BDGL16)
        elif name == "primal_bdd":
            cost = LWE.primal_bdd(params, red_cost_model=RC.BDGL16)
        elif name == "dual_hybrid":
            cost = LWE.dual_hybrid(params, red_cost_model=RC.BDGL16)
        else:
            raise ValueError(f"unsupported attack: {name}")
        rop = cost["rop"]
        if rop == oo:
            log2_rop = "Infinity"
        else:
            # Estimator cost models may return 53-bit real values. Asking
            # Sage for 16 decimal digits requires about 57 bits and turns a
            # successful attack estimate into a post-processing failure.
            log2_rop = str(N(log(rop, 2), digits=15))
        return {
            "attack": name,
            "status": "PASS",
            "log2_rop": log2_rop,
            "beta": cost_field(cost, "beta"),
            "dimension": cost_field(cost, "d"),
            "samples": cost_field(cost, "m"),
            "elapsed_seconds": round(time.monotonic() - started, 6),
        }
    except Exception as error:
        return {
            "attack": name,
            "status": "FAILED",
            "error_type": type(error).__name__,
            "error": str(error),
            "traceback": traceback.format_exc(),
            "elapsed_seconds": round(time.monotonic() - started, 6),
        }


def estimate_object(
    payload: dict[str, Any],
    object_type: str,
) -> dict[str, Any]:
    q_product = exact_product(payload["exact_q_primes"])
    p_product = exact_product(payload["exact_p_primes"])
    if object_type == "CIPHERTEXT_Q":
        modulus = q_product
    elif object_type == "EVALUATION_KEY_QP":
        modulus = q_product * p_product
    else:
        raise ValueError(f"unsupported object type: {object_type}")
    n = 1 << payload["log_n"]
    params = LWE.Parameters(
        n=n,
        q=modulus,
        Xs=ND.Uniform(-1, 1),
        Xe=ND.DiscreteGaussian(payload["xe"]["sigma"]),
        m=oo,
        tag=f"flipguard_{signature_id(payload)}_{object_type.lower()}",
    )
    attacks = [
        estimate_attack(name, params)
        for name in ATTACKS
    ]
    successful = [
        float(attack["log2_rop"])
        for attack in attacks
        if attack["status"] == "PASS"
        and attack["log2_rop"] != "Infinity"
    ]
    failed_count = sum(
        attack["status"] != "PASS" for attack in attacks
    )
    minimum = min(successful) if successful else None
    if minimum is not None and minimum < TARGET_SECURITY_BITS:
        status = "FAIL_ESTIMATOR_MODEL"
    elif failed_count:
        status = "INCOMPLETE_ATTACK_COVERAGE"
    elif minimum is None:
        status = "INCOMPLETE_ATTACK_COVERAGE"
    else:
        status = "PASS_ESTIMATOR_MODEL"
    return {
        "signature_id": signature_id(payload),
        "object_type": object_type,
        "log_n": payload["log_n"],
        "n": n,
        "exact_modulus": str(modulus),
        "exact_modulus_bit_length": modulus.bit_length(),
        "exact_log2_modulus": str(N(log(modulus, 2), digits=16)),
        "attacks": attacks,
        "attack_success_count": len(ATTACKS) - failed_count,
        "attack_failure_count": failed_count,
        "minimum_log2_rop": (
            None if minimum is None else round(minimum, 12)
        ),
        "target_security_bits": TARGET_SECURITY_BITS,
        "status": status,
    }


def estimator_git_commit(estimator_root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=estimator_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def run(
    input_path: Path,
    output_path: Path,
    estimator_root: Path,
    expected_estimator_commit: str,
    model_id: str,
    model_role: str,
    source_commit: str,
) -> None:
    actual_commit = estimator_git_commit(estimator_root)
    if actual_commit != expected_estimator_commit:
        raise ValueError(
            f"estimator commit {actual_commit}; "
            f"expected {expected_estimator_commit}"
        )
    source = json.loads(input_path.read_text(encoding="utf-8"))
    if source["security_policy_id"] != (
        "security_guidelines_cic2025_table5_2_ternary_128_v2"
    ):
        raise ValueError("unexpected security policy ID")
    unique: dict[str, dict[str, Any]] = {}
    source_rows: dict[str, int] = {}
    for entry in source["inputs"]:
        payload = signature_payload(entry)
        identifier = signature_id(payload)
        unique.setdefault(identifier, payload)
        source_rows[identifier] = source_rows.get(identifier, 0) + 1
    if len(source["inputs"]) != 14 or len(unique) != 9:
        raise ValueError(
            "expected 14 source rows and 9 unique modulus identities"
        )

    objects = []
    for identifier in sorted(unique):
        payload = unique[identifier]
        for object_type in ("CIPHERTEXT_Q", "EVALUATION_KEY_QP"):
            result = estimate_object(payload, object_type)
            result["source_signature_rows"] = source_rows[identifier]
            objects.append(result)

    status_counts: dict[str, int] = {}
    attack_failures = 0
    for result in objects:
        status_counts[result["status"]] = (
            status_counts.get(result["status"], 0) + 1
        )
        attack_failures += result["attack_failure_count"]
    if status_counts.get("FAIL_ESTIMATOR_MODEL", 0):
        run_status = "FALSIFIED_UNDER_ESTIMATOR_MODEL"
    elif attack_failures:
        run_status = "PARTIAL_ESTIMATOR_EXECUTION"
    else:
        run_status = "COMPLETE_ESTIMATOR_EXECUTION"

    output = {
        "schema_version": SCHEMA_VERSION,
        "model_id": model_id,
        "model_role": model_role,
        "source_commit": source_commit,
        "security_policy_id": source["security_policy_id"],
        "security_policy_effect": "NONE_SENSITIVITY_ONLY",
        "input": {
            "path": input_path.as_posix(),
            "sha256": sha256_path(input_path),
            "source_rows": len(source["inputs"]),
            "unique_modulus_identities": len(unique),
        },
        "estimator": {
            "repository": "https://github.com/malb/lattice-estimator",
            "git_commit": actual_commit,
            "cost_model": "RC.BDGL16",
            "attacks": list(ATTACKS),
            "sample_model": "m=oo",
            "target_security_bits": TARGET_SECURITY_BITS,
        },
        "distribution_binding": {
            "runtime_xs": {
                "concrete_type": "ring.Ternary",
                "p": 2.0 / 3.0,
            },
            "estimator_xs": "ND.Uniform(-1, 1)",
            "xs_match": "EXACT_COEFFICIENT_DISTRIBUTION",
            "runtime_xe": {
                "concrete_type": "ring.DiscreteGaussian",
                "sigma": 3.2,
                "bound": 19.2,
            },
            "estimator_xe": "ND.DiscreteGaussian(3.2)",
            "xe_match": "SIGMA_MATCH_BOUND_NOT_MODELED",
            "exact_distribution_claim_allowed": False,
        },
        "modulus_binding": {
            "q": "exact product of exported Lattigo Q primes",
            "qp": "exact product of exported Lattigo Q and P primes",
            "exact_modulus_claim": True,
        },
        "environment": {
            "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
            "github_run_attempt": os.environ.get(
                "GITHUB_RUN_ATTEMPT", ""
            ),
            "github_sha": os.environ.get("GITHUB_SHA", ""),
            "runner_os": os.environ.get("RUNNER_OS", ""),
            "runner_arch": os.environ.get("RUNNER_ARCH", ""),
            "sage_version": os.environ.get(
                "FLIPGUARD_SAGE_VERSION", ""
            ),
            "container_image": os.environ.get(
                "FLIPGUARD_CONTAINER_IMAGE", ""
            ),
        },
        "summary": {
            "run_status": run_status,
            "objects": len(objects),
            "status_counts": status_counts,
            "attack_failures": attack_failures,
            "paper_claim_allowed": False,
        },
        "objects": objects,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(canonical_json(output))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--estimator-root", type=Path, required=True)
    parser.add_argument("--estimator-commit", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--model-role", required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    run(
        args.input,
        args.output,
        args.estimator_root,
        args.estimator_commit,
        args.model_id,
        args.model_role,
        args.source_commit,
    )
    print(
        f"exact_security_estimator={args.model_id} "
        f"output={args.output}"
    )


if __name__ == "__main__":
    main()
