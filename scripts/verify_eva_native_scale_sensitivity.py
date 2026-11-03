#!/usr/bin/env python3
"""Verify the predeclared native EVA scale-sensitivity control."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DEFAULT = (
    REPO_ROOT
    / "experiments/eva_native_scale_sensitivity_v1/contract.json"
)
NATIVE_PATH = REPO_ROOT / "scripts/verify_eva_native_runtime.py"
NATIVE_SPEC = importlib.util.spec_from_file_location(
    "verify_eva_native_runtime_for_scale_sensitivity", NATIVE_PATH
)
assert NATIVE_SPEC is not None and NATIVE_SPEC.loader is not None
NATIVE = importlib.util.module_from_spec(NATIVE_SPEC)
NATIVE_SPEC.loader.exec_module(NATIVE)


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
    require(path.is_file(), f"missing bound source: {relative}")
    return path


def validate_contract(
    path: Path = CONTRACT_DEFAULT,
) -> dict[str, Any]:
    contract = load_json(path)
    require(
        contract["schema_version"]
        == "flipguard_eva_native_scale_sensitivity_contract_v1",
        "scale-sensitivity contract schema changed",
    )
    require(
        contract["status"]
        == (
            "PREDECLARED_DEVELOPMENT_SENSITIVITY_BEFORE_NEW_"
            "ENCRYPTED_EXECUTION"
        ),
        "scale-sensitivity predeclaration changed",
    )
    require(contract["paper_claim_allowed"] is False, "paper gate changed")
    require(
        contract["evaluation_role"]
        == "seed0_development_external_compiler_precision_sensitivity",
        "evaluation role changed",
    )
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
    binding = contract["source_binding"]
    for path_key, digest_key in (
        (
            "compiler_source_contract_path",
            "compiler_source_contract_sha256",
        ),
        (
            "original_native_evidence_manifest_path",
            "original_native_evidence_manifest_sha256",
        ),
        ("model_path", "model_sha256"),
        ("validation_path", "validation_sha256"),
        ("locked_audit_path", "locked_audit_sha256"),
    ):
        require(
            sha256_path(resolve(binding[path_key]))
            == binding[digest_key],
            f"bound source changed: {path_key}",
        )
    for path_key, count_key in (
        ("validation_path", "validation_rows"),
        ("locked_audit_path", "locked_audit_rows"),
    ):
        with resolve(binding[path_key]).open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        require(len(rows) == binding[count_key], f"{count_key} changed")
    program = contract["program"]
    require(program["vector_size"] == 1, "vector size changed")
    require(
        program["input_names"] == ["x_0", "x_1", "x_2", "x_3"],
        "input names changed",
    )
    require(program["output_range_bits"] == 1, "output range changed")
    require(
        program["formula"]
        == (
            "z=bias+sum_i(weight_i*x_i); "
            "score=0.5+0.197*z-0.004*z^3"
        ),
        "program formula changed",
    )
    config = program["compiler_config"]
    require(config["balance_reductions"] is True, "reduction balance changed")
    require(config["rescaler"] == "lazy_waterline", "rescaler changed")
    require(config["lazy_relinearize"] is True, "relinearization changed")
    require(config["security_level"] == 128, "compiler security changed")
    require(config["quantum_safe"] is False, "quantum flag changed")
    require(config["warn_vec_size"] is True, "vector warning changed")
    matrix = contract["candidate_matrix"]
    require(matrix["arm_order"] == [20, 30, 40], "arm order changed")
    require(
        matrix["input_scale_bits"] == [20, 30, 40],
        "scale matrix changed",
    )
    require(
        matrix["execute_all_validation_arms"] is True,
        "all-arm rule changed",
    )
    require(matrix["candidate_trials_max"] == 3, "trial budget changed")
    require(matrix["synthesis_calls"] == 0, "synthesis enabled")
    require(matrix["repair_calls"] == 0, "repair enabled")
    require(matrix["retuning"] == 0, "retuning enabled")
    decision = contract["decision_contract"]
    require(decision["threshold"] == 0.5, "threshold changed")
    require(decision["primary_alpha"] == 0.5, "alpha changed")
    require(
        decision["primary_margin_floor"] == 0.001,
        "margin floor changed",
    )
    protocol = contract["execution_protocol"]
    require(
        protocol["validation_key_repeats_per_arm"] == 3,
        "validation key repeats changed",
    )
    require(
        protocol["locked_audit_key_repeats"] == 3,
        "audit key repeats changed",
    )
    require(protocol["outlier_removal"] is False, "outlier rule changed")
    security = contract["security_reference"]
    require(
        security["security_policy_digest"] == NATIVE.SECURITY_DIGEST,
        "Security V2 digest changed",
    )
    require(
        security["direct_policy_digest"] == NATIVE.DIRECT_DIGEST,
        "Direct V2 digest changed",
    )
    require(
        security["caps"]
        == {"12": 106, "13": 214, "14": 430, "15": 868},
        "security caps changed",
    )
    require(
        security["native_seal_context_security_enforcement"]
        == "sec_level_type::none",
        "native enforcement changed",
    )
    require(
        security["runtime_security_claim"]
        == "NOT_EVALUATED_DIFFERENT_RUNTIME_DISTRIBUTION",
        "runtime security boundary changed",
    )
    return contract


def security_reference(
    *, degree: int, prime_bits: list[int], caps: dict[str, int]
) -> dict[str, Any]:
    require(degree > 0 and degree & (degree - 1) == 0, "invalid degree")
    require(len(prime_bits) >= 2, "missing Q/P prime bits")
    require(all(value > 0 for value in prime_bits), "invalid prime bits")
    log_n = int(math.log2(degree))
    q_bits = prime_bits[:-1]
    p_bits = prime_bits[-1:]
    log_q = sum(q_bits)
    log_p = sum(p_bits)
    log_qp = log_q + log_p
    cap = caps.get(str(log_n))
    q_pass = cap is not None and log_q <= cap
    qp_pass = cap is not None and log_qp <= cap
    return {
        "log_n": log_n,
        "q_prime_bits": q_bits,
        "p_prime_bits": p_bits,
        "log_q": log_q,
        "log_p": log_p,
        "log_qp": log_qp,
        "cap": cap,
        "ciphertext_q_admission": "PASS" if q_pass else "FAIL",
        "evaluation_key_qp_admission": "PASS" if qp_pass else "FAIL",
        "final_admission": "PASS" if q_pass and qp_pass else "FAIL",
        "headroom_bits": cap - log_qp if cap is not None else None,
    }


def choose_first_safe(
    arms: list[dict[str, Any]], order: list[int]
) -> dict[str, Any] | None:
    by_scale = {int(arm["input_scale_bits"]): arm for arm in arms}
    require(sorted(by_scale) == sorted(order), "result arm set changed")
    for scale in order:
        arm = by_scale[scale]
        if (
            arm["compilation_status"] == "OK"
            and arm["security_reference"]["final_admission"] == "PASS"
            and arm["validation"]["status"] == "SAFE"
        ):
            return arm
    return None


def expected_phase_status(counts: dict[str, Any]) -> str:
    if counts["execution_failures"]:
        return "FAILED"
    if counts["decision_flips"] or counts["error_violations"]:
        return "REJECTED"
    return "SAFE"


def verify_plaintext_identity(path: Path) -> float:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    successful = [row for row in rows if row["execution_status"] == "OK"]
    require(successful, f"no successful rows in {path}")
    return max(
        abs(
            float(row["eva_plaintext_score"])
            - float(row["plaintext_score"])
        )
        for row in successful
    )


def verify_result(
    root: Path,
    contract_path: Path = CONTRACT_DEFAULT,
) -> dict[str, Any]:
    contract = validate_contract(contract_path)
    NATIVE.verify_checksums(root)
    manifest = load_json(root / "manifest.json")
    require(
        manifest["schema_version"]
        == "flipguard_eva_native_scale_sensitivity_result_v1",
        "scale-sensitivity result schema changed",
    )
    require(manifest["paper_claim_allowed"] is False, "result paper gate")
    require(
        manifest["contract_sha256"] == sha256_path(contract_path),
        "result contract binding changed",
    )
    require(
        manifest["direct_policy_digest"] == NATIVE.DIRECT_DIGEST,
        "result Direct V2 digest changed",
    )
    require(
        manifest["security_policy_digest"] == NATIVE.SECURITY_DIGEST,
        "result Security V2 digest changed",
    )
    require(
        manifest["policy_modifications"] == 0,
        "result policy modification changed",
    )
    require(manifest["retuning"] == 0, "result retuning changed")
    matrix = contract["candidate_matrix"]
    arms = manifest["arms"]
    require(len(arms) == 3, "result arm count changed")
    require(
        [int(arm["input_scale_bits"]) for arm in arms]
        == matrix["arm_order"],
        "result arm order changed",
    )
    require(
        manifest["runtime_security_claim"]
        == contract["security_reference"]["runtime_security_claim"],
        "result runtime security boundary changed",
    )
    total_key_runs = 0
    total_evaluations = 0
    executed_trials = 0
    for arm in arms:
        scale = int(arm["input_scale_bits"])
        require(scale in matrix["arm_order"], "unexpected scale arm")
        if arm["compilation_status"] == "FAILED":
            require(
                arm["validation"]["status"] == "FAILED_COMPILATION",
                f"compile failure status changed: {scale}",
            )
            require(
                arm["security_reference"]["final_admission"]
                == "NOT_EVALUATED",
                f"compile failure security state changed: {scale}",
            )
            require(
                "compiled_program_path" not in arm,
                f"failed arm has compiled program: {scale}",
            )
            require(
                bool(arm["compilation_failure"]),
                f"missing compile failure reason: {scale}",
            )
            continue
        require(
            arm["compilation_status"] == "OK",
            f"unknown compilation state: {scale}",
        )
        dot_path = root / arm["compiled_program_path"]
        require(dot_path.is_file(), f"missing compiled program: {scale}")
        require(
            sha256_path(dot_path) == arm["compiled_program_sha256"],
            f"compiled program digest changed: {scale}",
        )
        require(
            NATIVE.dot_semantic_digest(dot_path.read_bytes())
            == arm["compiled_program_semantic_sha256"],
            f"compiled program semantics changed: {scale}",
        )
        expected_security = security_reference(
            degree=arm["poly_modulus_degree"],
            prime_bits=arm["prime_bits"],
            caps=contract["security_reference"]["caps"],
        )
        require(
            arm["security_reference"] == expected_security,
            f"security reference changed: {scale}",
        )
        validation = arm["validation"]
        if expected_security["final_admission"] == "PASS":
            ledger_path = root / validation["ledger_path"]
            counts = NATIVE.verify_ledger(
                ledger_path,
                threshold=contract["decision_contract"]["threshold"],
                alpha=contract["decision_contract"]["primary_alpha"],
                margin_floor=contract["decision_contract"][
                    "primary_margin_floor"
                ],
            )
            require(
                counts["sample_count"]
                == contract["source_binding"]["validation_rows"],
                f"validation population changed: {scale}",
            )
            require(
                counts["key_repeats"]
                == contract["execution_protocol"][
                    "validation_key_repeats_per_arm"
                ],
                f"validation keys changed: {scale}",
            )
            require(
                counts == validation["counts"],
                f"validation counts changed: {scale}",
            )
            require(
                validation["status"] == expected_phase_status(counts),
                f"validation status changed: {scale}",
            )
            require(
                verify_plaintext_identity(ledger_path) <= 1e-12,
                f"plaintext identity changed: {scale}",
            )
            executed_trials += 1
            total_key_runs += counts["key_repeats"]
            total_evaluations += counts["observations"]
        else:
            require(
                validation["status"] == "NOT_EVALUATED_SECURITY_BLOCK",
                f"blocked validation state changed: {scale}",
            )
            require(
                "ledger_path" not in validation,
                f"blocked arm has ledger: {scale}",
            )
    selected_arm = choose_first_safe(arms, matrix["arm_order"])
    selected = manifest["selected"]
    audit = manifest["locked_audit"]
    audit_key_runs = 0
    audit_evaluations = 0
    if selected_arm is None:
        require(selected is None, "selected arm exists without SAFE")
        require(
            manifest["outcome"] == "NO_SAFE",
            "NO_SAFE outcome changed",
        )
        require(
            audit["status"] == "NOT_EVALUATED_NO_SAFE",
            "audit ran without SAFE arm",
        )
    else:
        require(selected is not None, "missing selected arm")
        require(
            selected["candidate_id"] == selected_arm["candidate_id"],
            "selected candidate changed",
        )
        require(
            selected["input_scale_bits"]
            == selected_arm["input_scale_bits"],
            "selected scale changed",
        )
        for key in (
            "compiled_program_sha256",
            "compiled_program_semantic_sha256",
            "poly_modulus_degree",
            "prime_bits",
        ):
            require(
                selected[key] == selected_arm[key],
                f"selected literal changed: {key}",
            )
        audit_path = root / audit["ledger_path"]
        audit_counts = NATIVE.verify_ledger(
            audit_path,
            threshold=contract["decision_contract"]["threshold"],
            alpha=contract["decision_contract"]["primary_alpha"],
            margin_floor=contract["decision_contract"][
                "primary_margin_floor"
            ],
        )
        require(
            audit_counts["sample_count"]
            == contract["source_binding"]["locked_audit_rows"],
            "audit sample population changed",
        )
        require(
            audit_counts["key_repeats"]
            == contract["execution_protocol"]["locked_audit_key_repeats"],
            "audit key population changed",
        )
        require(audit_counts == audit["counts"], "audit counts changed")
        require(
            audit["status"] == expected_phase_status(audit_counts),
            "audit status changed",
        )
        require(
            verify_plaintext_identity(audit_path) <= 1e-12,
            "audit plaintext identity changed",
        )
        audit_key_runs = audit_counts["key_repeats"]
        audit_evaluations = audit_counts["observations"]
        expected_outcome = (
            "SELECTED_AUDIT_PASS"
            if audit["status"] == "SAFE"
            else f"SELECTED_AUDIT_{audit['status']}"
        )
        require(
            manifest["outcome"] == expected_outcome,
            "selected outcome changed",
        )
    accounting = manifest["accounting"]
    require(
        accounting["candidate_trials"] == executed_trials,
        "candidate trial accounting changed",
    )
    require(
        accounting["validation_key_runs"] == total_key_runs,
        "validation key accounting changed",
    )
    require(
        accounting["validation_encrypted_sample_evaluations"]
        == total_evaluations,
        "validation evaluation accounting changed",
    )
    require(
        accounting["locked_audit_key_runs"] == audit_key_runs,
        "audit key accounting changed",
    )
    require(
        accounting["locked_audit_encrypted_sample_evaluations"]
        == audit_evaluations,
        "audit evaluation accounting changed",
    )
    require(accounting["synthesis_calls"] == 0, "synthesis count changed")
    require(accounting["repair_calls"] == 0, "repair count changed")
    require(accounting["retuning"] == 0, "retuning accounting changed")
    allowed_claim_states = {
        "SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "BLOCKED",
        "NOT_EVALUATED",
        "SUPERSEDED",
        "PILOT_ONLY",
    }
    require(
        all(
            value in allowed_claim_states
            for value in manifest["claim_states"].values()
        ),
        "invalid claim-state vocabulary",
    )
    require(
        manifest["claim_states"][
            "original_scale20_candidate_decision_certification"
        ]
        == "BLOCKED",
        "original scale-20 negative result changed",
    )
    expected_status = (
        "PASS"
        if manifest["outcome"] == "SELECTED_AUDIT_PASS"
        else "PARTIAL_SCIENTIFIC_RESULT"
    )
    require(manifest["status"] == expected_status, "overall status changed")
    return {
        "status": manifest["status"],
        "outcome": manifest["outcome"],
        "selected_scale": (
            selected["input_scale_bits"] if selected is not None else None
        ),
        "candidate_trials": executed_trials,
        "validation_key_runs": total_key_runs,
        "audit_status": audit["status"],
        "paper_claim_allowed": False,
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
            "eva_native_scale_sensitivity_contract=VERIFIED "
            f"arms={contract['candidate_matrix']['arm_order']} "
            "paper_claim_allowed=false"
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
