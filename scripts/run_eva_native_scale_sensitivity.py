#!/usr/bin/env python3
"""Run the predeclared native EVA input-scale sensitivity control."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DEFAULT = (
    REPO_ROOT
    / "experiments/eva_native_scale_sensitivity_v1/contract.json"
)
VERIFY_PATH = (
    REPO_ROOT / "scripts/verify_eva_native_scale_sensitivity.py"
)
VERIFY_SPEC = importlib.util.spec_from_file_location(
    "verify_eva_native_scale_sensitivity_for_runner", VERIFY_PATH
)
assert VERIFY_SPEC is not None and VERIFY_SPEC.loader is not None
VERIFY = importlib.util.module_from_spec(VERIFY_SPEC)
VERIFY_SPEC.loader.exec_module(VERIFY)

NATIVE_RUNNER_PATH = REPO_ROOT / "scripts/run_eva_native_runtime.py"
NATIVE_SPEC = importlib.util.spec_from_file_location(
    "run_eva_native_runtime_for_scale_sensitivity", NATIVE_RUNNER_PATH
)
assert NATIVE_SPEC is not None and NATIVE_SPEC.loader is not None
NATIVE = importlib.util.module_from_spec(NATIVE_SPEC)
NATIVE_SPEC.loader.exec_module(NATIVE)
EXPORTER = NATIVE.EXPORTER


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_program(
    contract: dict[str, Any],
    model: dict[str, Any],
    input_scale_bits: int,
) -> tuple[Any, list[str]]:
    from eva import EvaProgram, Input, Output

    program_contract = contract["program"]
    if model["model_type"] != "linear_poly3":
        raise ValueError("scale sensitivity requires linear_poly3")
    if (
        model["polynomial_score"]["formula"]
        != "0.5 + 0.197*z - 0.004*z^3"
    ):
        raise ValueError("model score formula changed")
    weights = model["scaled_model_for_ckks"]["weights"]
    bias = model["scaled_model_for_ckks"]["bias"]
    names = program_contract["input_names"]
    if len(weights) != len(names) or model["input_dim"] != len(names):
        raise ValueError("model input dimension changed")
    program = EvaProgram(
        f"{program_contract['program_id_prefix']}_{input_scale_bits}",
        vec_size=program_contract["vector_size"],
    )
    with program:
        inputs = [Input(name) for name in names]
        z = bias
        for weight, value in zip(weights, inputs):
            z = z + weight * value
        score = 0.5 + 0.197 * z - 0.004 * (z ** 3)
        Output("score", score)
    program.set_input_scales(input_scale_bits)
    program.set_output_ranges(program_contract["output_range_bits"])
    return program, names


def compile_program(
    contract: dict[str, Any],
    model: dict[str, Any],
    input_scale_bits: int,
) -> tuple[Any, Any, Any, list[str]]:
    from eva.ckks import CKKSCompiler

    program, names = build_program(contract, model, input_scale_bits)
    config = contract["program"]["compiler_config"]
    compiler = CKKSCompiler(
        {
            "balance_reductions": str(
                config["balance_reductions"]
            ).lower(),
            "rescaler": config["rescaler"],
            "lazy_relinearize": str(
                config["lazy_relinearize"]
            ).lower(),
            "security_level": str(config["security_level"]),
            "quantum_safe": str(config["quantum_safe"]).lower(),
            "warn_vec_size": str(config["warn_vec_size"]).lower(),
        }
    )
    compiled, parameters, signature = compiler.compile(program)
    return compiled, parameters, signature, names


def candidate_id(
    scale: int,
    degree: int,
    prime_bits: list[int],
    semantic_digest: str,
) -> str:
    log_n = int(math.log2(degree))
    return (
        f"eva_native_scale{scale}_N{log_n}_"
        f"QP{sum(prime_bits)}_{semantic_digest.removeprefix('sha256:')[:12]}"
    )


def write_arm_summary(path: Path, arms: list[dict[str, Any]]) -> None:
    fields = [
        "arm_index",
        "candidate_id",
        "input_scale_bits",
        "compilation_status",
        "compilation_failure",
        "log_n",
        "q_prime_bits",
        "p_prime_bits",
        "log_q",
        "log_p",
        "log_qp",
        "security_admission",
        "validation_status",
        "validation_key_runs",
        "validation_observations",
        "decision_flips",
        "error_violations",
        "max_absolute_error",
        "max_normalized_budget_usage",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, lineterminator="\n"
        )
        writer.writeheader()
        for index, arm in enumerate(arms, start=1):
            security = arm["security_reference"]
            validation = arm["validation"]
            counts = validation.get("counts", {})
            writer.writerow(
                {
                    "arm_index": index,
                    "candidate_id": arm["candidate_id"],
                    "input_scale_bits": arm["input_scale_bits"],
                    "compilation_status": arm["compilation_status"],
                    "compilation_failure": arm.get(
                        "compilation_failure", ""
                    ),
                    "log_n": security.get("log_n", ""),
                    "q_prime_bits": "|".join(
                        str(value)
                        for value in security.get("q_prime_bits", [])
                    ),
                    "p_prime_bits": "|".join(
                        str(value)
                        for value in security.get("p_prime_bits", [])
                    ),
                    "log_q": security.get("log_q", ""),
                    "log_p": security.get("log_p", ""),
                    "log_qp": security.get("log_qp", ""),
                    "security_admission": security["final_admission"],
                    "validation_status": validation["status"],
                    "validation_key_runs": counts.get("key_repeats", 0),
                    "validation_observations": counts.get(
                        "observations", 0
                    ),
                    "decision_flips": counts.get("decision_flips", 0),
                    "error_violations": counts.get(
                        "error_violations", 0
                    ),
                    "max_absolute_error": counts.get(
                        "max_absolute_error", 0
                    ),
                    "max_normalized_budget_usage": counts.get(
                        "max_normalized_budget_usage", 0
                    ),
                }
            )


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=CONTRACT_DEFAULT)
    parser.add_argument("--eva-root", type=Path, required=True)
    parser.add_argument("--seal-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--action-run-id", required=True)
    args = parser.parse_args()
    contract_path = (
        args.contract
        if args.contract.is_absolute()
        else REPO_ROOT / args.contract
    )
    output = (
        args.output_root
        if args.output_root.is_absolute()
        else REPO_ROOT / args.output_root
    )
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite EVA scale sensitivity: {output}"
        )
    contract = VERIFY.validate_contract(contract_path)
    if git_head() != args.source_commit:
        raise ValueError("INTEGRITY_BLOCK: source commit changed")
    if subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip():
        raise ValueError("INTEGRITY_BLOCK: source tree is dirty")

    binding = contract["source_binding"]
    source_contract = VERIFY.load_json(
        REPO_ROOT / binding["compiler_source_contract_path"]
    )
    model = VERIFY.load_json(REPO_ROOT / binding["model_path"])
    EXPORTER.verify_sources(source_contract, args.eva_root, args.seal_root)
    validation_rows = load_rows(REPO_ROOT / binding["validation_path"])
    audit_rows = load_rows(REPO_ROOT / binding["locked_audit_path"])
    decision = contract["decision_contract"]
    protocol = contract["execution_protocol"]
    matrix = contract["candidate_matrix"]

    output.mkdir(parents=True)
    arms: list[dict[str, Any]] = []
    runtime_objects: dict[int, tuple[Any, Any, Any, list[str]]] = {}
    for scale in matrix["arm_order"]:
        try:
            compiled, parameters, signature, names = compile_program(
                contract, model, scale
            )
        except Exception as error:
            arms.append(
                {
                    "candidate_id": f"eva_native_scale{scale}_COMPILE_FAILED",
                    "input_scale_bits": scale,
                    "compilation_status": "FAILED",
                    "compilation_failure": (
                        f"{type(error).__name__}: {error}"
                    ),
                    "security_reference": {
                        "final_admission": "NOT_EVALUATED"
                    },
                    "validation": {
                        "status": "FAILED_COMPILATION",
                        "reason": "compiler did not produce a candidate",
                    },
                }
            )
            continue
        dot = compiled.to_DOT().encode("utf-8")
        dot_path = output / f"compiled_scale_{scale}.dot"
        dot_path.write_bytes(dot)
        dot_digest = VERIFY.sha256_path(dot_path)
        semantic_digest = VERIFY.NATIVE.dot_semantic_digest(dot)
        prime_bits = list(parameters.prime_bits)
        degree = int(parameters.poly_modulus_degree)
        if list(parameters.rotations):
            raise ValueError(
                f"INTEGRITY_BLOCK: unexpected rotations at scale {scale}"
            )
        security = VERIFY.security_reference(
            degree=degree,
            prime_bits=prime_bits,
            caps=contract["security_reference"]["caps"],
        )
        arm: dict[str, Any] = {
            "candidate_id": candidate_id(
                scale, degree, prime_bits, semantic_digest
            ),
            "input_scale_bits": scale,
            "compilation_status": "OK",
            "poly_modulus_degree": degree,
            "prime_bits": prime_bits,
            "compiled_program_path": dot_path.name,
            "compiled_program_sha256": dot_digest,
            "compiled_program_semantic_sha256": semantic_digest,
            "security_reference": security,
        }
        if security["final_admission"] != "PASS":
            arm["validation"] = {
                "status": "NOT_EVALUATED_SECURITY_BLOCK",
                "reason": "compiler output exceeds Security V2 reference cap",
            }
        else:
            ledger, validation = NATIVE.run_phase(
                phase=f"configuration_validation_scale_{scale}",
                rows=validation_rows,
                key_repeats=protocol[
                    "validation_key_repeats_per_arm"
                ],
                compiled=compiled,
                parameters=parameters,
                signature=signature,
                input_names=names,
                threshold=decision["threshold"],
                alpha=decision["primary_alpha"],
                margin_floor=decision["primary_margin_floor"],
            )
            ledger_path = output / f"validation_scale_{scale}.csv"
            NATIVE.write_ledger(ledger_path, ledger)
            validation["ledger_path"] = ledger_path.name
            arm["validation"] = validation
            runtime_objects[scale] = (
                compiled,
                parameters,
                signature,
                names,
            )
        arms.append(arm)

    selected_arm = VERIFY.choose_first_safe(arms, matrix["arm_order"])
    selected: dict[str, Any] | None = None
    locked_audit: dict[str, Any] = {
        "status": "NOT_EVALUATED_NO_SAFE",
        "reason": "no validation arm established SAFE",
        "retuning": 0,
    }
    if selected_arm is not None:
        scale = int(selected_arm["input_scale_bits"])
        compiled, parameters, signature, names = runtime_objects[scale]
        audit_ledger, locked_audit = NATIVE.run_phase(
            phase=f"locked_audit_scale_{scale}",
            rows=audit_rows,
            key_repeats=protocol["locked_audit_key_repeats"],
            compiled=compiled,
            parameters=parameters,
            signature=signature,
            input_names=names,
            threshold=decision["threshold"],
            alpha=decision["primary_alpha"],
            margin_floor=decision["primary_margin_floor"],
        )
        audit_path = output / "locked_audit_selected.csv"
        NATIVE.write_ledger(audit_path, audit_ledger)
        locked_audit["ledger_path"] = audit_path.name
        locked_audit["retuning"] = 0
        selected = {
            "candidate_id": selected_arm["candidate_id"],
            "input_scale_bits": scale,
            "compiled_program_sha256": selected_arm[
                "compiled_program_sha256"
            ],
            "compiled_program_semantic_sha256": selected_arm[
                "compiled_program_semantic_sha256"
            ],
            "poly_modulus_degree": selected_arm[
                "poly_modulus_degree"
            ],
            "prime_bits": selected_arm["prime_bits"],
        }

    if selected is None:
        outcome = "NO_SAFE"
    elif locked_audit["status"] == "SAFE":
        outcome = "SELECTED_AUDIT_PASS"
    else:
        outcome = f"SELECTED_AUDIT_{locked_audit['status']}"
    status = (
        "PASS"
        if outcome == "SELECTED_AUDIT_PASS"
        else "PARTIAL_SCIENTIFIC_RESULT"
    )
    validation_counts = [
        arm["validation"].get("counts", {}) for arm in arms
    ]
    accounting = {
        "candidate_trials": sum(bool(counts) for counts in validation_counts),
        "validation_key_runs": sum(
            int(counts.get("key_repeats", 0))
            for counts in validation_counts
        ),
        "validation_encrypted_sample_evaluations": sum(
            int(counts.get("observations", 0))
            for counts in validation_counts
        ),
        "locked_audit_key_runs": int(
            locked_audit.get("counts", {}).get("key_repeats", 0)
        ),
        "locked_audit_encrypted_sample_evaluations": int(
            locked_audit.get("counts", {}).get("observations", 0)
        ),
        "synthesis_calls": 0,
        "repair_calls": 0,
        "retuning": 0,
    }
    write_arm_summary(output / "arm_summaries.csv", arms)
    manifest = {
        "schema_version": (
            "flipguard_eva_native_scale_sensitivity_result_v1"
        ),
        "status": status,
        "outcome": outcome,
        "classification": contract["classification"],
        "evaluation_role": contract["evaluation_role"],
        "source_commit": args.source_commit,
        "action_run_id": args.action_run_id,
        "contract_sha256": VERIFY.sha256_path(contract_path),
        "original_native_evidence_manifest_sha256": binding[
            "original_native_evidence_manifest_sha256"
        ],
        "runtime": {
            "backend": "native_eva_seal",
            "eva_commit": contract["upstream"]["eva_commit"],
            "seal_commit": contract["upstream"]["seal_commit"],
            "python": platform.python_version(),
            "platform": platform.platform(),
            "native_seal_secret": contract["security_reference"][
                "native_seal_secret"
            ],
            "native_seal_error": contract["security_reference"][
                "native_seal_error"
            ],
        },
        "arms": arms,
        "selected": selected,
        "locked_audit": locked_audit,
        "accounting": accounting,
        "direct_policy_digest": NATIVE.VERIFIER.DIRECT_DIGEST,
        "security_policy_digest": NATIVE.VERIFIER.SECURITY_DIGEST,
        "runtime_security_claim": contract["security_reference"][
            "runtime_security_claim"
        ],
        "retuning": 0,
        "policy_modifications": 0,
        "claim_states": {
            "external_precision_sensitivity": (
                "PARTIALLY_SUPPORTED"
            ),
            "native_eva_safe_candidate_locked_audit": (
                "SUPPORTED"
                if outcome == "SELECTED_AUDIT_PASS"
                else (
                    "BLOCKED"
                    if selected is not None
                    else "NOT_EVALUATED"
                )
            ),
            "original_scale20_candidate_decision_certification": "BLOCKED",
            "general_external_compiler_interoperability": (
                "PARTIALLY_SUPPORTED"
            ),
            "cross_runtime_numerical_equivalence": "NOT_EVALUATED",
        },
        "paper_claim_allowed": False,
    }
    (output / "manifest.json").write_bytes(
        VERIFY.canonical_json(manifest)
    )
    NATIVE.write_checksums(output)
    VERIFY.verify_result(output, contract_path)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
