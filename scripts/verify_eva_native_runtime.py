#!/usr/bin/env python3
"""Verify the predeclared EVA native-runtime contract and result artifact."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DEFAULT = (
    REPO_ROOT / "experiments/eva_native_runtime_v1/contract.json"
)
ALLOWED_PHASE_STATUS = {"SAFE", "REJECTED", "FAILED", "NOT_EVALUATED"}
DIRECT_DIGEST = (
    "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
SECURITY_DIGEST = (
    "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def sha256_path(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def resolve(relative: str) -> Path:
    path = REPO_ROOT / relative
    require(path.is_file(), f"missing bound artifact: {relative}")
    return path


def validate_contract(
    contract_path: Path = CONTRACT_DEFAULT,
) -> dict[str, Any]:
    contract = load_json(contract_path)
    require(
        contract["schema_version"]
        == "flipguard_eva_native_runtime_contract_v1",
        "native runtime contract schema changed",
    )
    require(
        contract["status"]
        == "PREDECLARED_BEFORE_NATIVE_ENCRYPTED_EXECUTION",
        "native runtime predeclaration status changed",
    )
    require(contract["paper_claim_allowed"] is False, "paper gate changed")
    upstream = contract["upstream"]
    require(
        upstream["eva_commit"]
        == "4cd3254c9c51340ae30c451495ce5378135758c0",
        "EVA commit changed",
    )
    require(
        upstream["seal_commit"]
        == "0b058d99b7f18a00e5ebb2b80caee593804b0500",
        "SEAL commit changed",
    )
    compiler = contract["compiler_binding"]
    for path_key, digest_key in (
        ("parameter_contract_path", "parameter_contract_sha256"),
        ("compiler_output_path", "compiler_output_sha256"),
        ("compiled_program_path", "compiled_program_sha256"),
    ):
        require(
            sha256_path(resolve(compiler[path_key]))
            == compiler[digest_key],
            f"{path_key} digest changed",
        )
    compiler_output = load_json(resolve(compiler["compiler_output_path"]))
    candidate_parameters = compiler_output["candidate_request"]["parameters"]
    concrete = compiler_output["concrete_seal_materialization"]
    require(candidate_parameters["q"] == compiler["q"], "bound Q changed")
    require(candidate_parameters["p"] == compiler["p"], "bound P changed")
    require(
        candidate_parameters["log_n"]
        == int(math.log2(compiler["poly_modulus_degree"])),
        "bound LogN changed",
    )
    require(
        concrete["prime_bits"] == compiler["prime_bits"],
        "bound SEAL prime bits changed",
    )
    require(
        concrete["first_context_coeff_modulus"] == compiler["q"],
        "bound ciphertext modulus changed",
    )
    require(
        [concrete["special_modulus"]] == compiler["p"],
        "bound special modulus changed",
    )
    workload = contract["workload"]
    for path_key, digest_key in (
        ("model_path", "model_sha256"),
        ("validation_path", "validation_sha256"),
        ("locked_audit_path", "locked_audit_sha256"),
    ):
        require(
            sha256_path(resolve(workload[path_key]))
            == workload[digest_key],
            f"{path_key} digest changed",
        )
    for path_key, count_key in (
        ("validation_path", "validation_rows"),
        ("locked_audit_path", "locked_audit_rows"),
    ):
        with resolve(workload[path_key]).open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        require(len(rows) == workload[count_key], f"{count_key} changed")
    decision = contract["decision_contract"]
    require(decision["threshold"] == 0.5, "threshold changed")
    require(decision["primary_alpha"] == 0.5, "alpha changed")
    require(
        decision["primary_margin_floor"] == 0.001,
        "margin floor changed",
    )
    protocol = contract["execution_protocol"]
    require(protocol["validation_key_repeats"] == 3, "validation keys changed")
    require(
        protocol["locked_audit_key_repeats"] == 3,
        "audit keys changed",
    )
    require(protocol["candidate_trials"] == 1, "trial budget changed")
    require(protocol["synthesis_calls"] == 0, "synthesis enabled")
    require(protocol["repair_calls"] == 0, "repair enabled")
    require(protocol["retuning"] == 0, "retuning enabled")
    security = contract["security_interpretation"]
    require(
        security["security_policy_digest"] == SECURITY_DIGEST,
        "security digest changed",
    )
    require(
        security["direct_policy_digest"] == DIRECT_DIGEST,
        "direct policy digest changed",
    )
    require(
        security["formal_security_v2_runtime_claim"]
        == "NOT_EVALUATED_DIFFERENT_RUNTIME_DISTRIBUTION",
        "runtime security boundary changed",
    )
    require(
        security["lattigo_xs_xe_distribution_identity"] is False,
        "runtime distribution identity changed",
    )
    require(
        security["native_seal_context_security_enforcement"]
        == "sec_level_type::none",
        "native SEAL context enforcement changed",
    )
    return contract


def verify_checksums(root: Path) -> None:
    checksum_path = root / "SHA256SUMS"
    require(checksum_path.is_file(), "missing SHA256SUMS")
    expected: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        digest, name = line.split("  ", 1)
        expected[name] = digest
    actual_files = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    require(sorted(expected) == actual_files, "checksum file set changed")
    for relative, digest in expected.items():
        actual = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        require(actual == digest, f"checksum mismatch: {relative}")


def verify_ledger(
    path: Path,
    *,
    threshold: float,
    alpha: float,
    margin_floor: float,
) -> dict[str, Any]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    require(rows, f"empty ledger: {path}")
    flips = 0
    violations = 0
    failures = 0
    max_error = 0.0
    max_usage = 0.0
    keys: set[int] = set()
    samples: set[str] = set()
    for row in rows:
        keys.add(int(row["key_repeat"]))
        samples.add(row["row_id"])
        if row["execution_status"] != "OK":
            failures += 1
            continue
        plain = float(row["plaintext_score"])
        score = float(row["native_ckks_score"])
        margin = abs(plain - threshold)
        budget = alpha * margin
        error = abs(score - plain)
        usage = error / budget if budget else math.inf
        certifiable = margin > margin_floor
        plain_decision = plain >= threshold
        ckks_decision = score >= threshold
        flip = certifiable and plain_decision != ckks_decision
        violation = certifiable and error >= budget
        require(
            math.isclose(float(row["decision_margin"]), margin, abs_tol=1e-15),
            "ledger margin mismatch",
        )
        require(
            math.isclose(float(row["error_budget"]), budget, abs_tol=1e-15),
            "ledger budget mismatch",
        )
        require(
            math.isclose(float(row["absolute_error"]), error, abs_tol=1e-15),
            "ledger error mismatch",
        )
        require(
            math.isclose(
                float(row["normalized_budget_usage"]),
                usage,
                rel_tol=1e-12,
                abs_tol=1e-15,
            ),
            "ledger usage mismatch",
        )
        require(
            (row["certifiable"] == "true") == certifiable,
            "ledger certifiable mismatch",
        )
        require(
            (row["decision_flip"] == "true") == flip,
            "ledger flip mismatch",
        )
        require(
            (row["error_violation"] == "true") == violation,
            "ledger violation mismatch",
        )
        flips += int(flip)
        violations += int(violation)
        max_error = max(max_error, error)
        max_usage = max(max_usage, usage)
    return {
        "observations": len(rows),
        "sample_count": len(samples),
        "key_repeats": len(keys),
        "execution_failures": failures,
        "decision_flips": flips,
        "error_violations": violations,
        "max_absolute_error": max_error,
        "max_normalized_budget_usage": max_usage,
    }


def verify_result(
    root: Path,
    contract_path: Path = CONTRACT_DEFAULT,
) -> dict[str, Any]:
    contract = validate_contract(contract_path)
    verify_checksums(root)
    manifest = load_json(root / "manifest.json")
    require(
        manifest["schema_version"]
        == "flipguard_eva_native_runtime_result_v1",
        "native runtime result schema changed",
    )
    require(manifest["paper_claim_allowed"] is False, "result paper gate changed")
    require(
        manifest["contract_sha256"] == sha256_path(contract_path),
        "result contract binding changed",
    )
    require(
        manifest["direct_policy_digest"] == DIRECT_DIGEST,
        "result direct policy changed",
    )
    require(
        manifest["security_policy_digest"] == SECURITY_DIGEST,
        "result security policy changed",
    )
    require(
        manifest["policy_modifications"] == 0,
        "result policy modifications changed",
    )
    decision = contract["decision_contract"]
    validation = verify_ledger(
        root / "validation_ledger.csv",
        threshold=decision["threshold"],
        alpha=decision["primary_alpha"],
        margin_floor=decision["primary_margin_floor"],
    )
    require(
        validation == manifest["validation"]["counts"],
        "validation aggregate changed",
    )
    expected_validation = (
        "SAFE"
        if validation["execution_failures"] == 0
        and validation["decision_flips"] == 0
        and validation["error_violations"] == 0
        else (
            "FAILED"
            if validation["execution_failures"] > 0
            else "REJECTED"
        )
    )
    require(
        manifest["validation"]["status"] == expected_validation,
        "validation status changed",
    )
    audit_status = manifest["locked_audit"]["status"]
    require(audit_status in ALLOWED_PHASE_STATUS, "invalid audit status")
    if expected_validation == "SAFE":
        audit = verify_ledger(
            root / "locked_audit_ledger.csv",
            threshold=decision["threshold"],
            alpha=decision["primary_alpha"],
            margin_floor=decision["primary_margin_floor"],
        )
        require(
            audit == manifest["locked_audit"]["counts"],
            "audit aggregate changed",
        )
        expected_audit = (
            "SAFE"
            if audit["execution_failures"] == 0
            and audit["decision_flips"] == 0
            and audit["error_violations"] == 0
            else (
                "FAILED"
                if audit["execution_failures"] > 0
                else "REJECTED"
            )
        )
        require(audit_status == expected_audit, "audit status changed")
    else:
        require(
            audit_status == "NOT_EVALUATED",
            "audit ran after non-SAFE validation",
        )
        require(
            not (root / "locked_audit_ledger.csv").exists(),
            "unexpected locked audit ledger",
        )
    return {
        "status": manifest["status"],
        "validation_status": expected_validation,
        "locked_audit_status": audit_status,
        "paper_claim_allowed": False,
        "manifest_sha256": sha256_path(root / "manifest.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=CONTRACT_DEFAULT)
    parser.add_argument("--result-root", type=Path)
    args = parser.parse_args()
    contract_path = (
        args.contract
        if args.contract.is_absolute()
        else REPO_ROOT / args.contract
    )
    if args.result_root is None:
        contract = validate_contract(contract_path)
        print(
            json.dumps(
                {
                    "contract_status": contract["status"],
                    "contract_sha256": sha256_path(contract_path),
                    "paper_claim_allowed": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    result_root = (
        args.result_root
        if args.result_root.is_absolute()
        else REPO_ROOT / args.result_root
    )
    print(
        json.dumps(
            verify_result(result_root, contract_path),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
