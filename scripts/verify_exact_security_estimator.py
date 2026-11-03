#!/usr/bin/env python3
"""Verify exact-modulus estimator output without requiring Sage."""

from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from functools import reduce
from operator import mul
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT_DEFAULT = (
    REPO_ROOT
    / "docs/evidence/security_v2_static_attestation_formal_v2"
    / "lattice_estimator_inputs_v2.json"
)
ALLOWED_OBJECT_STATUSES = {
    "PASS_ESTIMATOR_MODEL",
    "FAIL_ESTIMATOR_MODEL",
    "INCOMPLETE_ATTACK_COVERAGE",
}
EXPECTED_ATTACKS = {"primal_usvp", "primal_bdd", "dual_hybrid"}


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


def require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(
            f"{label}={actual!r}; expected {expected!r}"
        )


def expected_identities(
    input_path: Path,
) -> dict[str, dict[str, Any]]:
    source = json.loads(input_path.read_text(encoding="utf-8"))
    require_equal(len(source["inputs"]), 14, "source rows")
    identities: dict[str, dict[str, Any]] = {}
    for entry in source["inputs"]:
        payload = signature_payload(entry)
        identities.setdefault(signature_id(payload), payload)
    require_equal(len(identities), 9, "unique modulus identities")
    return identities


def verify(result_path: Path, input_path: Path = INPUT_DEFAULT) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    require_equal(
        result["schema_version"],
        "flipguard_exact_security_estimator_run_v1",
        "schema",
    )
    require_equal(
        result["security_policy_id"],
        "security_guidelines_cic2025_table5_2_ternary_128_v2",
        "security policy ID",
    )
    require_equal(
        result["security_policy_effect"],
        "NONE_SENSITIVITY_ONLY",
        "security policy effect",
    )
    require_equal(
        result["input"]["sha256"],
        sha256_path(input_path),
        "input digest",
    )
    require_equal(
        result["estimator"]["cost_model"],
        "RC.BDGL16",
        "cost model",
    )
    require_equal(
        set(result["estimator"]["attacks"]),
        EXPECTED_ATTACKS,
        "attack set",
    )
    require_equal(
        result["estimator"]["sample_model"],
        "m=oo",
        "sample model",
    )
    require_equal(
        result["distribution_binding"]["xs_match"],
        "EXACT_COEFFICIENT_DISTRIBUTION",
        "secret distribution binding",
    )
    require_equal(
        result["distribution_binding"]["xe_match"],
        "SIGMA_MATCH_BOUND_NOT_MODELED",
        "error distribution binding",
    )
    require_equal(
        result["distribution_binding"]["exact_distribution_claim_allowed"],
        False,
        "exact distribution claim gate",
    )
    require_equal(
        result["summary"]["paper_claim_allowed"],
        False,
        "paper claim gate",
    )

    identities = expected_identities(input_path)
    require_equal(len(result["objects"]), 18, "estimated objects")
    seen = set()
    status_counts: dict[str, int] = {}
    attack_failures = 0
    for row in result["objects"]:
        identifier = row["signature_id"]
        if identifier not in identities:
            raise ValueError(f"unknown signature ID: {identifier}")
        object_type = row["object_type"]
        identity = (identifier, object_type)
        if identity in seen:
            raise ValueError(f"duplicate result object: {identity}")
        seen.add(identity)
        payload = identities[identifier]
        q = exact_product(payload["exact_q_primes"])
        p = exact_product(payload["exact_p_primes"])
        expected_modulus = q if object_type == "CIPHERTEXT_Q" else q * p
        require_equal(
            row["exact_modulus"],
            str(expected_modulus),
            f"{identity} exact modulus",
        )
        require_equal(
            row["exact_modulus_bit_length"],
            expected_modulus.bit_length(),
            f"{identity} modulus bit length",
        )
        require_equal(
            row["log_n"],
            payload["log_n"],
            f"{identity} log_n",
        )
        require_equal(
            row["n"],
            1 << payload["log_n"],
            f"{identity} n",
        )
        if row["status"] not in ALLOWED_OBJECT_STATUSES:
            raise ValueError(
                f"{identity}: invalid object status {row['status']}"
            )
        require_equal(
            {attack["attack"] for attack in row["attacks"]},
            EXPECTED_ATTACKS,
            f"{identity} attacks",
        )
        successes = [
            Decimal(attack["log2_rop"])
            for attack in row["attacks"]
            if attack["status"] == "PASS"
            and attack["log2_rop"] != "Infinity"
        ]
        failed = sum(
            attack["status"] != "PASS" for attack in row["attacks"]
        )
        require_equal(
            row["attack_failure_count"],
            failed,
            f"{identity} attack failures",
        )
        require_equal(
            row["attack_success_count"],
            len(EXPECTED_ATTACKS) - failed,
            f"{identity} attack successes",
        )
        minimum = min(successes) if successes else None
        if minimum is not None and minimum < Decimal(128):
            expected_status = "FAIL_ESTIMATOR_MODEL"
        elif failed or minimum is None:
            expected_status = "INCOMPLETE_ATTACK_COVERAGE"
        else:
            expected_status = "PASS_ESTIMATOR_MODEL"
        require_equal(
            row["status"],
            expected_status,
            f"{identity} derived status",
        )
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
        attack_failures += failed

    require_equal(
        result["summary"]["status_counts"],
        status_counts,
        "summary status counts",
    )
    require_equal(
        result["summary"]["attack_failures"],
        attack_failures,
        "summary attack failures",
    )
    return {
        "model_id": result["model_id"],
        "run_status": result["summary"]["run_status"],
        "status_counts": status_counts,
        "attack_failures": attack_failures,
        "sha256": sha256_path(result_path),
    }


def require_complete_attack_coverage(summary: dict[str, Any]) -> None:
    if summary["attack_failures"] != 0:
        raise ValueError(
            "exact estimator attack coverage is incomplete: "
            f"{summary['attack_failures']} failures"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--input", type=Path, default=INPUT_DEFAULT)
    parser.add_argument(
        "--require-complete-attack-coverage",
        action="store_true",
    )
    args = parser.parse_args()
    summary = verify(args.result, args.input)
    if args.require_complete_attack_coverage:
        require_complete_attack_coverage(summary)
    print(
        "exact_security_estimator=VERIFIED "
        f"model={summary['model_id']} "
        f"status={summary['run_status']} "
        f"attack_failures={summary['attack_failures']}"
    )


if __name__ == "__main__":
    main()
