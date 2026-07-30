#!/usr/bin/env python3
"""Run the pinned EVA program on its native Microsoft SEAL backend."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DEFAULT = (
    REPO_ROOT / "experiments/eva_native_runtime_v1/contract.json"
)
VERIFIER_PATH = REPO_ROOT / "scripts/verify_eva_native_runtime.py"
VERIFIER_SPEC = importlib.util.spec_from_file_location(
    "verify_eva_native_runtime_for_runner", VERIFIER_PATH
)
assert VERIFIER_SPEC is not None and VERIFIER_SPEC.loader is not None
VERIFIER = importlib.util.module_from_spec(VERIFIER_SPEC)
VERIFIER_SPEC.loader.exec_module(VERIFIER)

EXPORTER_PATH = REPO_ROOT / "scripts/export_eva_external_candidate.py"
EXPORTER_SPEC = importlib.util.spec_from_file_location(
    "export_eva_external_candidate_for_native_runtime", EXPORTER_PATH
)
assert EXPORTER_SPEC is not None and EXPORTER_SPEC.loader is not None
EXPORTER = importlib.util.module_from_spec(EXPORTER_SPEC)
EXPORTER_SPEC.loader.exec_module(EXPORTER)

LEDGER_FIELDS = [
    "phase",
    "row_id",
    "key_repeat",
    "execution_status",
    "failure_reason",
    "plaintext_score",
    "eva_plaintext_score",
    "native_ckks_score",
    "threshold",
    "decision_margin",
    "error_budget",
    "absolute_error",
    "normalized_budget_usage",
    "certifiable",
    "plaintext_decision",
    "native_ckks_decision",
    "decision_flip",
    "error_violation",
    "keygen_ms",
    "encrypt_ms",
    "execute_ms",
    "decrypt_ms",
    "total_sample_ms",
]


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(VERIFIER.canonical_json(value))


def write_ledger(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=LEDGER_FIELDS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def phase_status(counts: dict[str, Any]) -> str:
    if counts["execution_failures"]:
        return "FAILED"
    if counts["decision_flips"] or counts["error_violations"]:
        return "REJECTED"
    return "SAFE"


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [
        row for row in rows if row["execution_status"] == "OK"
    ]
    return {
        "observations": len(rows),
        "sample_count": len({str(row["row_id"]) for row in rows}),
        "key_repeats": len({int(row["key_repeat"]) for row in rows}),
        "execution_failures": len(rows) - len(successful),
        "decision_flips": sum(
            row["decision_flip"] == "true" for row in successful
        ),
        "error_violations": sum(
            row["error_violation"] == "true" for row in successful
        ),
        "max_absolute_error": max(
            (float(row["absolute_error"]) for row in successful),
            default=0.0,
        ),
        "max_normalized_budget_usage": max(
            (
                float(row["normalized_budget_usage"])
                for row in successful
            ),
            default=0.0,
        ),
    }


def run_phase(
    *,
    phase: str,
    rows: list[dict[str, str]],
    key_repeats: int,
    compiled: Any,
    parameters: Any,
    signature: Any,
    input_names: list[str],
    threshold: float,
    alpha: float,
    margin_floor: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from eva import evaluate
    from eva.seal import generate_keys

    ledger: list[dict[str, Any]] = []
    for key_repeat in range(1, key_repeats + 1):
        key_started = time.perf_counter_ns()
        public_context, secret_context = generate_keys(parameters)
        keygen_ms = (time.perf_counter_ns() - key_started) / 1_000_000
        for row in rows:
            record: dict[str, Any] = {
                "phase": phase,
                "row_id": row["row_id"],
                "key_repeat": key_repeat,
                "execution_status": "FAILED",
                "failure_reason": "",
                "plaintext_score": row["polynomial_score"],
                "eva_plaintext_score": "",
                "native_ckks_score": "",
                "threshold": threshold,
                "decision_margin": "",
                "error_budget": "",
                "absolute_error": "",
                "normalized_budget_usage": "",
                "certifiable": "",
                "plaintext_decision": "",
                "native_ckks_decision": "",
                "decision_flip": "",
                "error_violation": "",
                "keygen_ms": keygen_ms,
                "encrypt_ms": "",
                "execute_ms": "",
                "decrypt_ms": "",
                "total_sample_ms": "",
            }
            sample_started = time.perf_counter_ns()
            try:
                inputs = {
                    name: [float(row[name])] for name in input_names
                }
                eva_plain = float(evaluate(compiled, inputs)["score"][0])
                encrypt_started = time.perf_counter_ns()
                encrypted_inputs = public_context.encrypt(inputs, signature)
                encrypt_ms = (
                    time.perf_counter_ns() - encrypt_started
                ) / 1_000_000
                execute_started = time.perf_counter_ns()
                encrypted_outputs = public_context.execute(
                    compiled, encrypted_inputs
                )
                execute_ms = (
                    time.perf_counter_ns() - execute_started
                ) / 1_000_000
                decrypt_started = time.perf_counter_ns()
                outputs = secret_context.decrypt(
                    encrypted_outputs, signature
                )
                decrypt_ms = (
                    time.perf_counter_ns() - decrypt_started
                ) / 1_000_000
                native_score = float(outputs["score"][0])
                plain_score = float(row["polynomial_score"])
                margin = abs(plain_score - threshold)
                budget = alpha * margin
                error = abs(native_score - plain_score)
                usage = error / budget if budget else math.inf
                certifiable = margin > margin_floor
                plain_decision = plain_score >= threshold
                native_decision = native_score >= threshold
                flip = certifiable and plain_decision != native_decision
                violation = certifiable and error >= budget
                record.update(
                    {
                        "execution_status": "OK",
                        "eva_plaintext_score": eva_plain,
                        "native_ckks_score": native_score,
                        "decision_margin": margin,
                        "error_budget": budget,
                        "absolute_error": error,
                        "normalized_budget_usage": usage,
                        "certifiable": bool_text(certifiable),
                        "plaintext_decision": bool_text(plain_decision),
                        "native_ckks_decision": bool_text(native_decision),
                        "decision_flip": bool_text(flip),
                        "error_violation": bool_text(violation),
                        "encrypt_ms": encrypt_ms,
                        "execute_ms": execute_ms,
                        "decrypt_ms": decrypt_ms,
                    }
                )
            except Exception as error:
                record["failure_reason"] = (
                    f"{type(error).__name__}: {error}"
                )
            record["total_sample_ms"] = (
                time.perf_counter_ns() - sample_started
            ) / 1_000_000
            ledger.append(record)
    counts = aggregate(ledger)
    return ledger, {
        "status": phase_status(counts),
        "counts": counts,
    }


def write_checksums(root: Path) -> None:
    lines = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "SHA256SUMS":
            continue
        relative = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {relative}")
    (root / "SHA256SUMS").write_text(
        "\n".join(lines) + "\n", encoding="ascii"
    )


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
    output_root = (
        args.output_root
        if args.output_root.is_absolute()
        else REPO_ROOT / args.output_root
    )
    if output_root.exists():
        raise FileExistsError(
            f"refusing to overwrite native EVA result: {output_root}"
        )
    contract = VERIFIER.validate_contract(contract_path)
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

    parameter_contract = VERIFIER.load_json(
        REPO_ROOT
        / contract["compiler_binding"]["parameter_contract_path"]
    )
    model = VERIFIER.load_json(
        REPO_ROOT / contract["workload"]["model_path"]
    )
    EXPORTER.verify_sources(
        parameter_contract, args.eva_root, args.seal_root
    )
    compiled, parameters, signature, input_names = (
        EXPORTER.compile_program(parameter_contract, model)
    )
    dot = compiled.to_DOT().encode("utf-8")
    dot_digest = "sha256:" + hashlib.sha256(dot).hexdigest()
    compiler = contract["compiler_binding"]
    if dot_digest != compiler["compiled_program_sha256"]:
        raise ValueError("INTEGRITY_BLOCK: compiled DOT changed")
    if list(parameters.prime_bits) != compiler["prime_bits"]:
        raise ValueError("INTEGRITY_BLOCK: EVA prime bits changed")
    if parameters.poly_modulus_degree != compiler["poly_modulus_degree"]:
        raise ValueError("INTEGRITY_BLOCK: EVA degree changed")
    if list(parameters.rotations):
        raise ValueError("INTEGRITY_BLOCK: EVA rotations changed")

    output_root.mkdir(parents=True)
    (output_root / "compiled_program.dot").write_bytes(dot)
    workload = contract["workload"]
    decision = contract["decision_contract"]
    protocol = contract["execution_protocol"]
    validation_rows = load_rows(REPO_ROOT / workload["validation_path"])
    validation_ledger, validation = run_phase(
        phase="configuration_validation",
        rows=validation_rows,
        key_repeats=protocol["validation_key_repeats"],
        compiled=compiled,
        parameters=parameters,
        signature=signature,
        input_names=input_names,
        threshold=decision["threshold"],
        alpha=decision["primary_alpha"],
        margin_floor=decision["primary_margin_floor"],
    )
    write_ledger(output_root / "validation_ledger.csv", validation_ledger)

    locked_audit: dict[str, Any] = {
        "status": "NOT_EVALUATED",
        "reason": "validation did not establish SAFE",
        "retuning": 0,
    }
    if validation["status"] == "SAFE":
        audit_rows = load_rows(
            REPO_ROOT / workload["locked_audit_path"]
        )
        audit_ledger, locked_audit = run_phase(
            phase="locked_audit",
            rows=audit_rows,
            key_repeats=protocol["locked_audit_key_repeats"],
            compiled=compiled,
            parameters=parameters,
            signature=signature,
            input_names=input_names,
            threshold=decision["threshold"],
            alpha=decision["primary_alpha"],
            margin_floor=decision["primary_margin_floor"],
        )
        locked_audit["retuning"] = 0
        write_ledger(
            output_root / "locked_audit_ledger.csv", audit_ledger
        )

    overall = (
        "PASS"
        if validation["status"] == "SAFE"
        and locked_audit["status"] == "SAFE"
        else "PARTIAL_SCIENTIFIC_RESULT"
    )
    manifest = {
        "schema_version": "flipguard_eva_native_runtime_result_v1",
        "status": overall,
        "classification": (
            "SOURCE_REPLAYED_PUBLIC_COMPILER_NATIVE_RUNTIME_CONTROL"
        ),
        "source_commit": args.source_commit,
        "action_run_id": args.action_run_id,
        "contract_sha256": VERIFIER.sha256_path(contract_path),
        "compiler_output_sha256": compiler["compiler_output_sha256"],
        "compiled_program_sha256": dot_digest,
        "candidate": {
            "provider": "microsoft_eva_v1.0.1_seal3.6.4",
            "poly_modulus_degree": parameters.poly_modulus_degree,
            "prime_bits": list(parameters.prime_bits),
            "q": compiler["q"],
            "p": compiler["p"],
            "input_scale_bits": compiler["input_scale_bits"],
        },
        "runtime": {
            "backend": "native_eva_seal",
            "eva_commit": contract["upstream"]["eva_commit"],
            "seal_commit": contract["upstream"]["seal_commit"],
            "seal_secret": contract["security_interpretation"][
                "native_seal_secret"
            ],
            "seal_error": contract["security_interpretation"][
                "native_seal_error"
            ],
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "validation": validation,
        "locked_audit": locked_audit,
        "accounting": {
            "candidate_trials": 1,
            "validation_key_runs": validation["counts"]["key_repeats"],
            "validation_encrypted_sample_evaluations": validation["counts"][
                "observations"
            ],
            "locked_audit_key_runs": (
                locked_audit.get("counts", {}).get("key_repeats", 0)
            ),
            "locked_audit_encrypted_sample_evaluations": (
                locked_audit.get("counts", {}).get("observations", 0)
            ),
            "synthesis_calls": 0,
            "repair_calls": 0,
            "retuning": 0,
        },
        "direct_policy_digest": VERIFIER.DIRECT_DIGEST,
        "security_policy_digest": VERIFIER.SECURITY_DIGEST,
        "runtime_security_claim": contract["security_interpretation"][
            "formal_security_v2_runtime_claim"
        ],
        "policy_modifications": 0,
        "paper_claim_allowed": False,
        "claim_states": {
            "native_eva_seal_execution": "SUPPORTED",
            "native_eva_seal_decision_certification": (
                "SUPPORTED"
                if overall == "PASS"
                else "BLOCKED"
            ),
            "cross_runtime_numerical_equivalence": "NOT_EVALUATED",
            "general_external_compiler_interoperability": (
                "PARTIALLY_SUPPORTED"
            ),
        },
    }
    write_json(output_root / "manifest.json", manifest)
    write_checksums(output_root)
    VERIFIER.verify_result(output_root, contract_path)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
