#!/usr/bin/env python3
"""Freeze the bounded Orion V9 self-test and its definitive full-run blocker."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "external/v9/orion"
SOURCE = ROOT / "external/v7/sources/orion"
PACK = ROOT / "docs/evidence/final_realistic_baseline_closure_v9"
EXPECTED_SOURCE = "be8a827350a147d610fe3bb998b5bea8de814ff8"


def sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return "sha256:" + digest


def main() -> int:
    result_path = RAW / "orion_preflight_10.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    declared_path = RAW / "preflight_input_manifest.json"
    declared = json.loads(declared_path.read_text(encoding="utf-8"))
    if result["status"] != "PASS" or result["unique_inputs"] != 10:
        raise RuntimeError("Orion encrypted preflight did not pass on ten unique inputs")
    if result["argmax_flips"] != 0 or not result["all_logits_extractable"]:
        raise RuntimeError("Orion encrypted preflight output drift")
    if result["ordered_input_ids"] != declared["ordered_test_indices"]:
        raise RuntimeError("Orion input ordering drift")
    commit = subprocess.run(
        ["git", "-C", str(SOURCE), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if commit != EXPECTED_SOURCE:
        raise RuntimeError("Orion pinned source drift")
    tracked = subprocess.run(
        ["git", "-C", str(SOURCE), "status", "--porcelain", "--untracked-files=no"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if tracked:
        raise RuntimeError("Orion tracked source is dirty")
    model_weights = sorted(
        str(path.relative_to(SOURCE))
        for suffix in ("*.pt", "*.pth", "*.ckpt", "*.h5", "*.onnx")
        for path in SOURCE.rglob(suffix)
        if "mlp" in path.name.lower()
    )
    if model_weights:
        raise RuntimeError(f"unexpected official trained MLP weight artifact: {model_weights}")

    records = result["records"]
    mean_eval = sum(float(row["evaluate_ms"]) for row in records) / len(records)
    mean_total = sum(float(row["total_ms"]) for row in records) / len(records)
    payload = {
        "schema_version": "flipguard_orion_v9_feasibility_v1",
        "provider": "Orion",
        "final_status": "ORION_OFFICIAL_SELF_TEST_ONLY_FULL_EXTENSION_BLOCKED",
        "preflight_status": "PASS",
        "preflight_evidence_role": "OFFICIAL_SELF_TEST_ONLY_UNTRAINED_DETERMINISTIC_WEIGHTS",
        "full_run_performed": False,
        "full_run_status": "REPRODUCTION_BLOCKED",
        "full_run_reason_code": "OFFICIAL_TRAINED_MLP_WEIGHTS_NOT_DISTRIBUTED",
        "full_run_reason": (
            "The pinned official MLP test and example construct deterministic seed-42 random "
            "weights and distribute no trained MLP state. A 100-validation/100-audit decision "
            "study would therefore not preserve official trained weights and was not launched."
        ),
        "source": {
            "repository": "https://github.com/baahl-nyu/orion",
            "commit": commit,
            "tracked_source_clean": True,
            "model_source": result["model_architecture_source"],
            "model_source_sha256": result["model_architecture_sha256"],
            "official_test_source": "external/v7/sources/orion/tests/models/test_mlp.py",
            "official_test_source_sha256": sha256(SOURCE / "tests/models/test_mlp.py"),
            "official_example_source": "external/v7/sources/orion/examples/run_mlp.py",
            "official_example_source_sha256": sha256(SOURCE / "examples/run_mlp.py"),
            "official_trained_mlp_weight_artifacts": model_weights,
        },
        "build": {
            "official_wrapper_exit": "FALSE_FAILURE_AFTER_SHARED_OBJECT_BUILD",
            "classification": "BUILD_WRAPPER_FALSE_NEGATIVE",
            "shared_object_sha256": result["binary_sha256"],
            "dynamic_load": "PASS",
            "required_symbols": "PASS",
            "official_tests": "11_PASS",
            "official_source_modified": False,
        },
        "environment": {
            "container_base": "python:3.11-slim",
            "container_image_id": "sha256:9ffed1ed08b29b906daf7e1717fc77153fd02e34172936ff83a66213642ff1a7",
            "python": "3.11.15",
            "torch": "2.2.2+cpu",
            "torchvision": "0.17.2+cpu",
            "numpy": "1.26.4",
            "dockerfile_sha256": sha256(RAW / "Dockerfile.py311"),
            "systemd_user_service": True,
            "concurrent_ckks_processes": 0,
        },
        "recoveries": [
            {
                "attempt": 1,
                "state": "RECOVERABLE_ENVIRONMENT_FAILURE",
                "reason_code": "PYTHON_3_12_TORCH_DYNAMO_UNSUPPORTED",
                "error": "RuntimeError: Dynamo is not supported on Python 3.12+",
                "log_sha256": sha256(RAW / "preflight_attempt1.stderr.log"),
                "encrypted_inference_reached": False,
            },
            {
                "attempt": 2,
                "state": "RECOVERABLE_ENVIRONMENT_FAILURE",
                "reason_code": "CONTAINER_GIT_EXECUTABLE_MISSING",
                "error": "FileNotFoundError: No such file or directory: git",
                "log_sha256": sha256(RAW / "preflight_attempt2.stderr.log"),
                "encrypted_inference_reached": False,
            },
            {
                "attempt": 3,
                "state": "PASS",
                "reason_code": "PYTHON_3_11_PINNED_RUNTIME",
                "log_sha256": sha256(RAW / "preflight.stderr.log"),
                "encrypted_inference_reached": True,
            },
        ],
        "preflight": {
            "actual_keygen_encrypt_evaluate_decrypt": result["actual_keygen_encrypt_evaluate_decrypt"],
            "unique_inputs": result["unique_inputs"],
            "ordered_input_ids": result["ordered_input_ids"],
            "input_manifest_sha256": result["input_manifest_sha256"],
            "all_logits_extractable": result["all_logits_extractable"],
            "argmax_flips": result["argmax_flips"],
            "model_state_sha256": result["model_state_sha256"],
            "weight_provenance": result["weight_provenance"],
            "config_sha256": result["config_sha256"],
            "binary_sha256": result["binary_sha256"],
            "input_level": result["input_level"],
            "scheme_init_and_keygen_ms": result["scheme_init_and_keygen_ms"],
            "fit_ms": result["fit_ms"],
            "compile_ms": result["compile_ms"],
            "mean_evaluate_ms": mean_eval,
            "mean_encrypt_evaluate_decrypt_ms": mean_total,
            "max_absolute_error": max(float(row["max_absolute_error"]) for row in records),
            "mean_mae": sum(float(row["mae"]) for row in records) / len(records),
            "records": records,
        },
        "full_extension_accounting": {
            "validation_unique_inputs": "NOT_EVALUATED",
            "audit_unique_inputs": "NOT_EVALUATED",
            "validation_audit_overlap": "NOT_EVALUATED",
            "validation_argmax_flips": "NOT_EVALUATED",
            "audit_argmax_flips": "NOT_EVALUATED",
            "retuning": 0,
        },
        "claim_effect": (
            "The official Orion path is executable and exposes encrypted logits, but this "
            "untrained deterministic self-test is auxiliary feasibility evidence, not a measured "
            "decision-bearing baseline or trained-model performance result."
        ),
        "measured_provider_in_final_matrix": False,
        "paper_evidence_tier": "RELATED_WORK_WITH_AUXILIARY_OFFICIAL_SELF_TEST",
    }
    PACK.mkdir(parents=True, exist_ok=True)
    (PACK / "orion_preflight.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    shutil.copyfile(declared_path, PACK / "orion_input_manifest.json")
    print(json.dumps({
        "status": payload["final_status"],
        "preflight_inputs": payload["preflight"]["unique_inputs"],
        "preflight_flips": payload["preflight"]["argmax_flips"],
        "full_run_performed": payload["full_run_performed"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
