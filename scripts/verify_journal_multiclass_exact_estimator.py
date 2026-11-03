#!/usr/bin/env python3
"""Verify a candidate-specific journal multiclass estimator run."""

from __future__ import annotations

import argparse
import hashlib
import json
from functools import reduce
from operator import mul
from pathlib import Path


SCHEMA = "flipguard_journal_multiclass_exact_estimator_v1"
EXPECTED_ARMS = {
    ("mnist_mlp_square_784_100_10_v1", "gap_aware_direct"),
    ("mnist_mlp_square_784_100_10_v1", "graph_only_fixed_tolerance"),
    ("mnist_mlp_square_784_100_10_v1", "bounded_catalog_fastest_safe"),
    ("mnist_lenet5_small_square_v1", "gap_aware_direct"),
}


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify(result_path: Path, materialization_path: Path | None = None) -> dict:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    require(result["schema_version"] == SCHEMA, "estimator schema")
    materialized = None
    if materialization_path is not None:
        require(digest(materialization_path) == result["materialization"]["sha256"], "materialization digest")
        materialized = json.loads(materialization_path.read_text(encoding="utf-8"))
    estimator = result["estimator"]
    require(len(estimator["git_commit"]) == 40, "estimator commit")
    require(estimator["attacks"] == ["primal_usvp", "primal_bdd", "dual_hybrid"], "attack set")
    require(estimator["classical_cost_model"] == "RC.BDGL16", "classical cost model")
    require(estimator["quantum_cost_model"] == "NOT_EVALUATED", "quantum disclosure")
    require(result["modulus_binding"]["q_and_qp_separately_estimated"] is True, "object separation")
    require(result["distribution_binding"]["exact_distribution_claim_allowed"] is False, "distribution caveat")

    arms = {(row["model_id"], row["arm"]) for row in result["candidates"]}
    require(arms == EXPECTED_ARMS, "candidate arm inventory")
    require(result["summary"]["candidate_count"] == 4, "candidate count")
    require(result["summary"]["object_count"] == 8, "object count")
    require(result["summary"]["attack_count"] == 24, "attack count")
    for candidate in result["candidates"]:
        require(candidate["security_policy_v2"]["final_admission"] == "PASS", "Security-V2 source status")
        require(len(candidate["objects"]) == 2, "candidate object count")
        object_types = {item["object_type"] for item in candidate["objects"]}
        require(object_types == {"CIPHERTEXT_Q", "EVALUATION_KEY_QP"}, "object types")
        objects = {item["object_type"]: item for item in candidate["objects"]}
        for item in objects.values():
            require(item["attack_failure_count"] == 0, "incomplete attack execution")
            require(len(item["attacks"]) == 3, "attack records")
            require(all(attack["status"] == "PASS" for attack in item["attacks"]), "attack invocation failure")
            require(item["target_security_bits"] == 128, "target security")
        if materialized is not None:
            source = next(
                row
                for row in materialized["candidates"]
                if row["model_id"] == candidate["model_id"] and row["arm"] == candidate["arm"]
            )
            q = reduce(mul, source["exact_q_primes"], 1)
            p = reduce(mul, source["exact_p_primes"], 1)
            require(objects["CIPHERTEXT_Q"]["exact_modulus"] == str(q), "exact Q product")
            require(objects["EVALUATION_KEY_QP"]["exact_modulus"] == str(q * p), "exact QP product")
    pass_count = sum(row["final_status"] == "PASS_ESTIMATOR_MODEL" for row in result["candidates"])
    fail_count = sum(row["final_status"] == "FAIL_ESTIMATOR_MODEL" for row in result["candidates"])
    incomplete = 4 - pass_count - fail_count
    require(result["summary"]["pass"] == pass_count, "pass count")
    require(result["summary"]["fail"] == fail_count, "fail count")
    require(result["summary"]["incomplete"] == incomplete, "incomplete count")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--materialization", type=Path)
    args = parser.parse_args()
    result = verify(args.result, args.materialization)
    print(
        "journal_multiclass_exact_estimator=VERIFIED "
        f"model={result['estimator']['model_id']} status={result['summary']['run_status']} "
        f"pass={result['summary']['pass']} fail={result['summary']['fail']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
