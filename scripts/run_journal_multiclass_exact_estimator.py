#!/usr/bin/env python3
"""Run candidate-specific exact-Q/P estimates for the journal extension."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from sage.all import oo

from run_exact_security_estimator import (
    ATTACKS,
    TARGET_SECURITY_BITS,
    canonical_json,
    estimate_object,
    estimator_git_commit,
    sha256_path,
)


SCHEMA = "flipguard_journal_multiclass_exact_estimator_v1"
MATERIALIZATION_SCHEMA = "flipguard_journal_multiclass_security_materialization_v1"


def payload(candidate: dict) -> dict:
    return {
        "log_n": candidate["parameters"]["log_n"],
        "exact_q_primes": candidate["exact_q_primes"],
        "exact_p_primes": candidate["exact_p_primes"],
        "xs": {
            "concrete_type": "ring.Ternary",
            "p": 2.0 / 3.0,
        },
        "xe": {
            "concrete_type": "ring.DiscreteGaussian",
            "sigma": 3.2,
            "bound": 19.2,
        },
    }


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
        raise ValueError(f"estimator commit {actual_commit}; expected {expected_estimator_commit}")
    source = json.loads(input_path.read_text(encoding="utf-8"))
    if source["schema_version"] != MATERIALIZATION_SCHEMA:
        raise ValueError("unexpected materialization schema")
    if source["security_policy_id"] != "security_guidelines_cic2025_table5_2_ternary_128_v2":
        raise ValueError("unexpected security policy")
    if source["policy_retuning"] != 0 or len(source["candidates"]) != 4:
        raise ValueError("unexpected materialization scope")

    candidates = []
    for candidate in source["candidates"]:
        objects = []
        for object_type in ("CIPHERTEXT_Q", "EVALUATION_KEY_QP"):
            result = estimate_object(payload(candidate), object_type)
            result["model_id"] = candidate["model_id"]
            result["arm"] = candidate["arm"]
            result["candidate_id"] = candidate["candidate_id"]
            result["profile"] = candidate.get("profile", "")
            objects.append(result)
        final_status = (
            "PASS_ESTIMATOR_MODEL"
            if all(item["status"] == "PASS_ESTIMATOR_MODEL" for item in objects)
            else "FAIL_ESTIMATOR_MODEL"
            if any(item["status"] == "FAIL_ESTIMATOR_MODEL" for item in objects)
            else "INCOMPLETE_ATTACK_COVERAGE"
        )
        candidates.append(
            {
                "model_id": candidate["model_id"],
                "arm": candidate["arm"],
                "candidate_id": candidate["candidate_id"],
                "profile": candidate.get("profile", ""),
                "parameters": candidate["parameters"],
                "security_policy_v2": candidate["security_policy_v2"],
                "objects": objects,
                "final_status": final_status,
                "minimum_log2_rop": min(
                    item["minimum_log2_rop"]
                    for item in objects
                    if item["minimum_log2_rop"] is not None
                ),
            }
        )

    incomplete = sum(
        item["final_status"] == "INCOMPLETE_ATTACK_COVERAGE" for item in candidates
    )
    failed = sum(item["final_status"] == "FAIL_ESTIMATOR_MODEL" for item in candidates)
    run_status = (
        "FALSIFIED_UNDER_ESTIMATOR_MODEL"
        if failed
        else "PARTIAL_ESTIMATOR_EXECUTION"
        if incomplete
        else "COMPLETE_ESTIMATOR_EXECUTION"
    )
    output = {
        "schema_version": SCHEMA,
        "source_commit": source_commit,
        "materialization": {
            "path": input_path.as_posix(),
            "sha256": sha256_path(input_path),
            "source_commit": source["source_commit"],
            "candidates": len(source["candidates"]),
        },
        "security_policy_id": source["security_policy_id"],
        "security_policy_digest": source["security_policy_digest"],
        "estimator": {
            "repository": "https://github.com/malb/lattice-estimator",
            "git_commit": actual_commit,
            "model_id": model_id,
            "model_role": model_role,
            "attacks": list(ATTACKS),
            "sample_model": "m=oo",
            "target_security_bits": TARGET_SECURITY_BITS,
            "classical_cost_model": "RC.BDGL16",
            "quantum_cost_model": "NOT_EVALUATED",
        },
        "distribution_binding": {
            "runtime_xs": {"concrete_type": "ring.Ternary", "p": 2.0 / 3.0},
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
            "q": "exact product of materialized Lattigo Q primes",
            "qp": "exact product of materialized Lattigo Q and P primes",
            "q_and_qp_separately_estimated": True,
        },
        "environment": {
            "container_image": os.environ.get("FLIPGUARD_CONTAINER_IMAGE", ""),
            "sage_version": os.environ.get("FLIPGUARD_SAGE_VERSION", ""),
        },
        "candidates": candidates,
        "summary": {
            "run_status": run_status,
            "candidate_count": len(candidates),
            "pass": len(candidates) - failed - incomplete,
            "fail": failed,
            "incomplete": incomplete,
            "object_count": len(candidates) * 2,
            "attack_count": len(candidates) * 2 * len(ATTACKS),
            "sample_model": str(oo),
        },
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
    print(f"journal_multiclass_exact_estimator={args.model_id} output={args.output}")


if __name__ == "__main__":
    main()
