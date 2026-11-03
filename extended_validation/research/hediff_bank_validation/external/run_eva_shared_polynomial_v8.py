#!/usr/bin/env python3
"""Run the frozen V8 shared polynomial with Microsoft EVA and native SEAL."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
import time
from typing import Any


EXPECTED_EVA_COMMIT = "4cd3254c9c51340ae30c451495ce5378135758c0"
THRESHOLD = 0.5
RHO = 0.5
MARGIN_FLOOR = 0.001
VECTOR_SIZE = 1024
PREDECLARED_SELECTED_SCALE = 30
CAPS = {12: 106, 13: 214, 14: 430, 15: 868}
FIELDS = [
    "provider", "workload", "role", "scale_bits", "candidate_id", "context_index",
    "encrypted_batch_index", "row_id", "plaintext_score", "decrypted_score",
    "absolute_error", "margin", "operational_budget", "normalized_budget_usage",
    "certifiable", "plaintext_decision", "ckks_decision", "decision_flip",
    "reserve_policy_violation", "keygen_ms", "encrypt_ms", "evaluate_ms", "decrypt_ms", "total_ms",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_program(scale: int) -> Any:
    from eva import EvaProgram, Input, Output

    program = EvaProgram(f"shared_polynomial_threshold_v8_scale{scale}", vec_size=VECTOR_SIZE)
    with program:
        x0, x1, x2 = Input("x_0"), Input("x_1"), Input("x_2")
        z = ((0.8 * x0 - 0.5 * x1) + 1.2 * x2) - 0.3
        z2 = z * z
        z3 = z2 * z
        score = (0.5 + 0.197 * z) - 0.004 * z3
        Output("score", score)
    program.set_input_scales(scale)
    program.set_output_ranges(20)
    return program


def compile_program(scale: int) -> tuple[Any, Any, Any]:
    from eva.ckks import CKKSCompiler

    compiler = CKKSCompiler({
        "balance_reductions": "true", "rescaler": "always", "lazy_relinearize": "true",
        "security_level": "128", "quantum_safe": "false", "warn_vec_size": "false",
    })
    return compiler.compile(build_program(scale))


def security_reference(degree: int, prime_bits: list[int]) -> dict[str, Any]:
    log_n = int(math.log2(degree))
    log_p = prime_bits[-1]
    log_q = sum(prime_bits[:-1])
    log_qp = sum(prime_bits)
    cap = CAPS.get(log_n)
    final = "PASS" if cap is not None and log_q <= cap and log_qp <= cap else "FAIL"
    return {
        "log_n": log_n, "log_q": log_q, "log_p": log_p, "log_qp": log_qp,
        "q_prime_bits": prime_bits[:-1], "p_prime_bits": prime_bits[-1:], "cap": cap,
        "ciphertext_q_admission": "PASS" if cap is not None and log_q <= cap else "FAIL",
        "evaluation_key_qp_admission": "PASS" if cap is not None and log_qp <= cap else "FAIL",
        "final_admission": final, "headroom_bits": cap - log_qp if cap is not None else None,
    }


def run_phase(role: str, scale: int, rows: list[dict[str, str]], compiled: Any, parameters: Any, signature: Any, contexts: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from eva import evaluate
    from eva.seal import generate_keys

    padded_inputs = {}
    for name in ("x_0", "x_1", "x_2"):
        values = [float(row[name]) for row in rows]
        padded_inputs[name] = values + [0.0] * (VECTOR_SIZE - len(values))
    reference = [float(value) for value in evaluate(compiled, padded_inputs)["score"][:len(rows)]]
    records: list[dict[str, Any]] = []
    for context_index in range(1, contexts + 1):
        total_started = time.perf_counter_ns()
        started = time.perf_counter_ns()
        public, secret = generate_keys(parameters)
        keygen_ms = (time.perf_counter_ns() - started) / 1e6
        started = time.perf_counter_ns()
        encrypted = public.encrypt(padded_inputs, signature)
        encrypt_ms = (time.perf_counter_ns() - started) / 1e6
        started = time.perf_counter_ns()
        result_ct = public.execute(compiled, encrypted)
        evaluate_ms = (time.perf_counter_ns() - started) / 1e6
        started = time.perf_counter_ns()
        decrypted = [float(value) for value in secret.decrypt(result_ct, signature)["score"][:len(rows)]]
        decrypt_ms = (time.perf_counter_ns() - started) / 1e6
        total_ms = (time.perf_counter_ns() - total_started) / 1e6
        for row, eva_plain, actual in zip(rows, reference, decrypted):
            expected = float(row["polynomial_score"])
            if abs(eva_plain - expected) > 2e-6:
                raise RuntimeError(f"EVA plaintext graph drift at {row['row_id']}: {eva_plain} vs {expected}")
            margin = abs(expected - THRESHOLD)
            budget = RHO * margin
            error = abs(actual - expected)
            certifiable = margin > MARGIN_FLOOR
            plain_decision = expected >= THRESHOLD
            ckks_decision = actual >= THRESHOLD
            records.append({
                "provider": "Microsoft EVA", "workload": "shared_polynomial_threshold_v8", "role": role,
                "scale_bits": scale, "candidate_id": "", "context_index": context_index,
                "encrypted_batch_index": 1, "row_id": row["row_id"], "plaintext_score": expected,
                "decrypted_score": actual, "absolute_error": error, "margin": margin,
                "operational_budget": budget, "normalized_budget_usage": error / budget if budget else math.inf,
                "certifiable": str(certifiable).lower(), "plaintext_decision": str(plain_decision).lower(),
                "ckks_decision": str(ckks_decision).lower(),
                "decision_flip": str(certifiable and plain_decision != ckks_decision).lower(),
                "reserve_policy_violation": str(certifiable and error >= budget).lower(),
                "keygen_ms": keygen_ms, "encrypt_ms": encrypt_ms, "evaluate_ms": evaluate_ms,
                "decrypt_ms": decrypt_ms, "total_ms": total_ms,
            })
    summary = {
        "role": role, "scale_bits": scale, "unique_inputs": len(rows), "contexts": contexts,
        "encrypted_batches": contexts, "per_input_observations": len(records),
        "certifiable_observations": sum(row["certifiable"] == "true" for row in records),
        "decision_flips": sum(row["decision_flip"] == "true" for row in records),
        "reserve_policy_violations": sum(row["reserve_policy_violation"] == "true" for row in records),
        "max_absolute_error": max(float(row["absolute_error"]) for row in records),
        "max_normalized_budget_usage": max(float(row["normalized_budget_usage"]) for row in records),
    }
    summary["status"] = "SAFE" if summary["decision_flips"] == 0 and summary["reserve_policy_violations"] == 0 else "REJECTED"
    return records, summary


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eva-root", required=True, type=Path)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--contexts", type=int, default=3)
    args = parser.parse_args()
    if args.contexts != 3:
        raise ValueError("V8 protocol freezes three EVA contexts")
    output = args.output_root.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite EVA V8 output: {output}")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=args.eva_root, check=True, text=True, capture_output=True).stdout.strip()
    if head != EXPECTED_EVA_COMMIT or subprocess.run(["git", "status", "--short"], cwd=args.eva_root, check=True, text=True, capture_output=True).stdout.strip():
        raise RuntimeError("INTEGRITY_BLOCK: EVA source binding changed")
    validation = load_rows(args.input_root / "configuration_validation.csv")
    audit = load_rows(args.input_root / "locked_audit.csv")
    if len(validation) != 500 or len(audit) != 500 or {r["row_id"] for r in validation} & {r["row_id"] for r in audit}:
        raise RuntimeError("INTEGRITY_BLOCK: frozen input roles changed")
    output.mkdir(parents=True)
    arms = []
    runtime: dict[int, tuple[Any, Any, Any]] = {}
    for scale in (20, 30, 40):
        started = time.perf_counter_ns()
        compiled, parameters, signature = compile_program(scale)
        compile_ms = (time.perf_counter_ns() - started) / 1e6
        dot_path = output / f"compiled_scale_{scale}.dot"
        dot_path.write_text(compiled.to_DOT(), encoding="utf-8")
        security = security_reference(int(parameters.poly_modulus_degree), list(parameters.prime_bits))
        candidate_id = f"eva_v8_scale{scale}_N{security['log_n']}_QP{security['log_qp']}_{sha256(dot_path)[7:19]}"
        records, summary = run_phase("configuration_validation", scale, validation, compiled, parameters, signature, args.contexts)
        for record in records:
            record["candidate_id"] = candidate_id
        write_csv(output / f"validation_scale_{scale}.csv", records)
        arms.append({"candidate_id": candidate_id, "scale_bits": scale, "compile_ms": compile_ms, "compiled_dot_sha256": sha256(dot_path), "security": security, "validation": summary})
        runtime[scale] = (compiled, parameters, signature)
    selected = next(arm for arm in arms if arm["scale_bits"] == PREDECLARED_SELECTED_SCALE)
    audits = []
    for scale in (PREDECLARED_SELECTED_SCALE, 40):
        compiled, parameters, signature = runtime[scale]
        records, summary = run_phase("locked_audit", scale, audit, compiled, parameters, signature, args.contexts)
        candidate_id = next(arm["candidate_id"] for arm in arms if arm["scale_bits"] == scale)
        for record in records:
            record["candidate_id"] = candidate_id
        write_csv(output / f"audit_scale_{scale}.csv", records)
        audits.append({"candidate_id": candidate_id, "scale_bits": scale, "retuning": 0, **summary})
    manifest = {
        "schema_version": "flipguard_focused_external_v8_eva_result_v1", "status": "PASS",
        "provider": "Microsoft EVA", "provider_commit": head, "workload": "shared_polynomial_threshold_v8",
        "unique_inputs": 1000, "validation_unique_inputs": 500, "audit_unique_inputs": 500, "overlap": 0,
        "contexts": args.contexts, "arms": arms,
        "selected": selected["candidate_id"],
        "selected_scale": selected["scale_bits"],
        "selection_rule": "V7_PREDECLARED_SCALE30_BEFORE_V8_VALIDATION",
        "audits": audits, "retuning": 0,
        "runtime": {"backend": "native_eva_seal", "python": platform.python_version(), "platform": platform.platform()},
        "security_claim": "NATIVE_RUNTIME_SECURITY_NOT_EQUIVALENT_TO_LATTIGO_SECURITY_V2",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksum_lines = [f"{sha256(path)[7:]}  {path.relative_to(output).as_posix()}" for path in sorted(output.rglob("*")) if path.is_file()]
    (output / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="ascii")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
