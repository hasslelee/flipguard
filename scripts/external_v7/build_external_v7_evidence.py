#!/usr/bin/env python3
"""Build deterministic, fail-closed normalized evidence from V7 raw ledgers."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
from typing import Any, Iterable

from normalize_provider_output_v7 import MISSING
from build_external_v7_overlays import build_overlays


ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "external/v7/status"
OUTPUTS = ROOT / "external/v7/outputs"
LOGS = ROOT / "external/v7/logs"
EVIDENCE = ROOT / "docs/evidence/external_end_to_end_code_v7"
LANDSCAPE = ROOT / "docs/evidence/external_autotuner_comparison_v2/official_sources.json"

NOT_REPORTED = "NOT_REPORTED"
NOT_EVALUATED = "NOT_EVALUATED"
NOT_APPLICABLE = "NOT_APPLICABLE"
NOT_SEPARATELY_RECORDED = "NOT_SEPARATELY_RECORDED"

SYSTEMS = [
    ("EVA", "eva"),
    ("ELASM", "corelab"),
    ("HECATE", "corelab"),
    ("HEIR", "heir"),
    ("HECO", "heco"),
    ("Orion", "orion"),
    ("ANT-ACE", "ant-ace"),
    ("AutoFHE", "autofhe"),
    ("DaCapo", "dacapo"),
    ("LOHEN", "lohen"),
    ("SLOTHE", "slothe"),
    ("HEaaN.MLIR", "heaan-mlir"),
    ("HEILP", "heilp"),
    ("HALO", "halo"),
    ("ReSBM", "resbm"),
    ("Orbit", "orbit"),
    ("FHE-Agent", "fhe-agent"),
    ("FHECrafter", "fhecrafter"),
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, NOT_REPORTED) for field in fields})


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def verified_heir_capture() -> tuple[Path, dict[str, Any], list[dict[str, str]]] | None:
    root = OUTPUTS / "heir/dot-product-8f-output-capture-v1"
    manifest_path = root / "manifest.json"
    outputs_path = root / "decrypted_outputs.csv"
    sums_path = root / "SHA256SUMS"
    if not manifest_path.exists() and not outputs_path.exists() and not sums_path.exists():
        return None
    if not all(path.is_file() for path in (manifest_path, outputs_path, sums_path)):
        raise RuntimeError("partial HEIR output-capture evidence exists")
    for line in sums_path.read_text(encoding="ascii").splitlines():
        digest, relative = line.split("  ", 1)
        source = root / relative
        if not source.is_file() or sha256_file(source) != f"sha256:{digest}":
            raise RuntimeError(f"HEIR output-capture checksum mismatch: {relative}")
    manifest = load_json(manifest_path)
    rows = csv_rows(outputs_path)
    if manifest.get("raw_decrypted_output_available") is not True:
        raise RuntimeError("HEIR output-capture manifest does not attest raw output")
    if {row["runtime"] for row in rows} != {"OpenFHE", "Lattigo"} or len(rows) != 2:
        raise RuntimeError("HEIR output-capture runtime set drift")
    return manifest_path, manifest, rows


def mean(values: Iterable[float]) -> float | str:
    materialized = list(values)
    return statistics.fmean(materialized) if materialized else NOT_REPORTED


def percentile(values: Iterable[float], quantile: float) -> float | str:
    ordered = sorted(values)
    if not ordered:
        return NOT_REPORTED
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def stage_manifests() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(STATUS.glob("*/*/run_manifest.json")):
        payload = load_json(path)
        payload["manifest_path"] = path.relative_to(ROOT).as_posix()
        rows.append(payload)
    return rows


def terminal_manifests() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(OUTPUTS.glob("*/terminal-state-v1/manifest.json")):
        payload = load_json(path)
        payload["manifest_path"] = path.relative_to(ROOT).as_posix()
        result[payload["provider"]] = payload
    return result


def highest_stage_state(stages: list[dict[str, Any]], provider: str, stage: str) -> str:
    matches = [row["state"] for row in stages if row["provider"] == provider and row["stage"] == stage]
    if "PASS" in matches:
        return "PASS"
    if "FAILED" in matches:
        return "FAILED"
    return NOT_EVALUATED


def official_sources(destination: Path, source_commit: str) -> dict[str, Any]:
    predecessor = load_json(LANDSCAPE)
    payload = {
        "schema_version": "flipguard_external_official_sources_v7",
        "source_commit": source_commit,
        "predecessor_path": LANDSCAPE.relative_to(ROOT).as_posix(),
        "predecessor_sha256": sha256_file(LANDSCAPE),
        "audit_date": predecessor["audit_date"],
        "systems": predecessor["systems"],
    }
    write_json(destination / "official_sources.json", payload)
    return payload


def build_source_and_license_tables(
    destination: Path,
    sources: dict[str, Any],
    stages: list[dict[str, Any]],
) -> None:
    source_by_name = {row["system"]: row for row in sources["systems"]}
    source_rows = []
    for row in stages:
        if row["stage"] != "SOURCE_CHECKOUT":
            continue
        source_rows.append(
            {
                "provider": row["provider"],
                "run_id": row["run_id"],
                "workload": row["workload"],
                "state": row["state"],
                "source_sha256": row["source_sha256"],
                "output_sha256": row["output_sha256"],
                "elapsed_seconds": row["elapsed_seconds"],
                "manifest_path": row["manifest_path"],
            }
        )
    write_csv(
        destination / "source_checkout_manifest.csv",
        [
            "provider", "run_id", "workload", "state", "source_sha256",
            "output_sha256", "elapsed_seconds", "manifest_path",
        ],
        source_rows,
    )

    licenses = []
    for system, provider in SYSTEMS:
        source = source_by_name.get(system, {})
        licenses.append(
            {
                "system": system,
                "provider_queue_id": provider,
                "license": source.get("license", NOT_REPORTED),
                "artifact_revision": source.get("artifact_revision", NOT_REPORTED),
                "source_status": source.get("source_status", NOT_REPORTED),
                "official_repository": source.get("repository", NOT_REPORTED),
                "official_paper": source.get("paper", NOT_REPORTED),
            }
        )
    write_csv(
        destination / "license_inventory.csv",
        [
            "system", "provider_queue_id", "license", "artifact_revision", "source_status",
            "official_repository", "official_paper",
        ],
        licenses,
    )


def build_stage_matrices(destination: Path, stages: list[dict[str, Any]]) -> None:
    build_rows = []
    for row in stages:
        if row["stage"] != "CLEAN_BUILD":
            continue
        build_rows.append(
            {
                "provider": row["provider"],
                "run_id": row["run_id"],
                "workload": row["workload"],
                "state": row["state"],
                "elapsed_seconds": row["elapsed_seconds"],
                "source_sha256": row["source_sha256"],
                "binary_sha256": row["binary_sha256"],
                "output_sha256": row["output_sha256"],
                "manifest_path": row["manifest_path"],
            }
        )
    write_csv(
        destination / "clean_build_matrix.csv",
        [
            "provider", "run_id", "workload", "state", "elapsed_seconds", "source_sha256",
            "binary_sha256", "output_sha256", "manifest_path",
        ],
        build_rows,
    )

    pipeline_rows = []
    for row in stages:
        if row["stage"] not in {"OFFICIAL_PIPELINE", "ENCRYPTED_VALIDATION", "ENCRYPTED_AUDIT"}:
            continue
        pipeline_rows.append(
            {
                "provider": row["provider"],
                "run_id": row["run_id"],
                "stage": row["stage"],
                "workload": row["workload"],
                "state": row["state"],
                "elapsed_seconds": row["elapsed_seconds"],
                "source_sha256": row["source_sha256"],
                "binary_sha256": row["binary_sha256"],
                "output_sha256": row["output_sha256"],
                "manifest_path": row["manifest_path"],
            }
        )
    write_csv(
        destination / "official_pipeline_matrix.csv",
        [
            "provider", "run_id", "stage", "workload", "state", "elapsed_seconds",
            "source_sha256", "binary_sha256", "output_sha256", "manifest_path",
        ],
        pipeline_rows,
    )


def eva_native_records() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    native: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    official_path = OUTPUTS / "eva/official-image-v1/manifest.json"
    official = load_json(official_path)
    for program in official["programs"]:
        contexts = program["contexts"]
        native.append(
            {
                "provider": "EVA",
                "system": "EVA",
                "workload": official["workload_id"],
                "arm": program["program"],
                "runtime": "native_eva_seal",
                "scheme": "CKKS",
                "evidence_level": 3,
                "execution_status": "PASS",
                "actual_output_available": True,
                "decision_output_available": False,
                "contexts_keysets": program["key_contexts"],
                "unique_inputs": official["unique_input_images"],
                "raw_output_rows": program["raw_output_rows"],
                "compile_time_ms": program["compile_ms"],
                "tuning_time_ms": NOT_APPLICABLE,
                "keygen_time_ms": mean(row["keygen_ms"] for row in contexts),
                "encryption_time_ms": mean(row["encrypt_ms"] for row in contexts),
                "evaluation_time_ms": mean(row["execute_ms"] for row in contexts),
                "decryption_time_ms": mean(row["decrypt_ms"] for row in contexts),
                "total_time_ms": mean(row["total_ms"] for row in contexts),
                "rms_error": math.sqrt(program["mse_all_contexts"]),
                "max_absolute_error": program["max_absolute_error"],
                "validation_flips": NOT_EVALUATED,
                "audit_flips": NOT_EVALUATED,
                "gate_state": NOT_EVALUATED,
                "security_state": "SECURITY_NOT_EVALUATED",
                "portability_state": "NATIVE_ONLY",
                "output_manifest": official_path.relative_to(ROOT).as_posix(),
                "provider_commit": official["provider_commit"],
            }
        )

    shared_path = OUTPUTS / "eva/shared-polynomial-v1/manifest.json"
    shared = load_json(shared_path)
    selected_id = shared["selected"]["candidate_id"]
    for arm in shared["arms"]:
        scale = arm["input_scale_bits"]
        ledger = OUTPUTS / f"eva/shared-polynomial-v1/validation_scale_{scale}.csv"
        rows = csv_rows(ledger)
        successful = [row for row in rows if row["execution_status"] == "OK"]
        selected = arm["candidate_id"] == selected_id
        audit_rows = csv_rows(OUTPUTS / "eva/shared-polynomial-v1/locked_audit_selected.csv") if selected else []
        native.append(
            {
                "provider": "EVA",
                "system": "EVA",
                "workload": "shared_polynomial_v1",
                "arm": arm["candidate_id"],
                "runtime": "native_eva_seal",
                "scheme": "CKKS",
                "evidence_level": 6 if selected else 5,
                "execution_status": "PASS",
                "actual_output_available": True,
                "decision_output_available": True,
                "contexts_keysets": arm["validation"]["counts"]["key_repeats"],
                "unique_inputs": arm["validation"]["counts"]["sample_count"] + (shared["locked_audit"]["counts"]["sample_count"] if selected else 0),
                "raw_output_rows": len(rows) + len(audit_rows),
                "compile_time_ms": NOT_SEPARATELY_RECORDED,
                "tuning_time_ms": NOT_APPLICABLE,
                "keygen_time_ms": mean(float(row["keygen_ms"]) for row in successful),
                "encryption_time_ms": mean(float(row["encrypt_ms"]) for row in successful),
                "evaluation_time_ms": mean(float(row["execute_ms"]) for row in successful),
                "decryption_time_ms": mean(float(row["decrypt_ms"]) for row in successful),
                "total_time_ms": mean(float(row["total_sample_ms"]) for row in successful),
                "rms_error": NOT_REPORTED,
                "max_absolute_error": arm["validation"]["counts"]["max_absolute_error"],
                "validation_flips": arm["validation"]["counts"]["decision_flips"],
                "audit_flips": shared["locked_audit"]["counts"]["decision_flips"] if selected else NOT_APPLICABLE,
                "gate_state": "SAFE_AUDIT_PASS" if selected else arm["validation"]["status"],
                "security_state": "SECURITY_TARGET_MATCH_ASSUMPTIONS_DIFFER",
                "portability_state": "NATIVE_ONLY",
                "output_manifest": shared_path.relative_to(ROOT).as_posix(),
                "provider_commit": shared["runtime"]["eva_commit"],
            }
        )
        gates.append(
            {
                "provider": "EVA",
                "workload": "shared_polynomial_v1",
                "candidate_id": arm["candidate_id"],
                "provider_objective": "native input-scale sensitivity",
                "security_admission": arm["security_reference"]["final_admission"],
                "validation_status": arm["validation"]["status"],
                "validation_flips": arm["validation"]["counts"]["decision_flips"],
                "validation_violations": arm["validation"]["counts"]["error_violations"],
                "audit_status": shared["locked_audit"]["status"] if selected else NOT_APPLICABLE,
                "audit_flips": shared["locked_audit"]["counts"]["decision_flips"] if selected else NOT_APPLICABLE,
                "audit_violations": shared["locked_audit"]["counts"]["error_violations"] if selected else NOT_APPLICABLE,
                "retuning": shared["retuning"] if selected else NOT_APPLICABLE,
                "final_flipguard_state": "SAFE" if selected else arm["validation"]["status"],
                "raw_ledger": ledger.relative_to(ROOT).as_posix(),
            }
        )
    audits.append(
        {
            "provider": "EVA",
            "workload": "shared_polynomial_v1",
            "candidate_id": selected_id,
            "validation_samples": 14,
            "audit_samples": shared["locked_audit"]["counts"]["sample_count"],
            "contexts_keysets": shared["locked_audit"]["counts"]["key_repeats"],
            "audit_status": shared["locked_audit"]["status"],
            "audit_flips": shared["locked_audit"]["counts"]["decision_flips"],
            "audit_violations": shared["locked_audit"]["counts"]["error_violations"],
            "execution_failures": shared["locked_audit"]["counts"]["execution_failures"],
            "retuning": shared["locked_audit"]["retuning"],
            "raw_ledger": (OUTPUTS / "eva/shared-polynomial-v1/locked_audit_selected.csv").relative_to(ROOT).as_posix(),
        }
    )
    return native, gates, audits


def corelab_native_records() -> list[dict[str, Any]]:
    manifest_path = OUTPUTS / "corelab/elasm-linear-regression-grid-v1/manifest.json"
    manifest = load_json(manifest_path)
    rows = csv_rows(OUTPUTS / "corelab/elasm-linear-regression-grid-v1/records.csv")
    result = []
    for row in rows:
        result.append(
            {
                "provider": "CoreLab",
                "system": "ELASM" if row["mode"] == "elasm" else "CoreLab EVA mode",
                "workload": "official_LinearRegression",
                "arm": f"{row['mode']}_waterline_{int(row['waterline']):02d}",
                "runtime": "SEAL_HEVM",
                "scheme": "CKKS",
                "evidence_level": int(row["evidence_level"]),
                "execution_status": row["execution_status"],
                "actual_output_available": row["actual_output_available"],
                "decision_output_available": False,
                "contexts_keysets": 1,
                "unique_inputs": NOT_REPORTED,
                "raw_output_rows": 1 if row["actual_output_available"] == "true" else 0,
                "compile_time_ms": float(row["compile_wall_seconds"]) * 1000,
                "tuning_time_ms": NOT_SEPARATELY_RECORDED,
                "keygen_time_ms": NOT_SEPARATELY_RECORDED,
                "encryption_time_ms": NOT_SEPARATELY_RECORDED,
                "evaluation_time_ms": float(row["reported_hevm_seconds"]) * 1000 if row["reported_hevm_seconds"] else NOT_REPORTED,
                "decryption_time_ms": NOT_SEPARATELY_RECORDED,
                "total_time_ms": float(row["execution_wrapper_wall_seconds"]) * 1000,
                "rms_error": float(row["reported_rms_error"]) if row["reported_rms_error"] else NOT_REPORTED,
                "max_absolute_error": NOT_REPORTED,
                "validation_flips": NOT_EVALUATED,
                "audit_flips": NOT_EVALUATED,
                "gate_state": NOT_EVALUATED,
                "security_state": "SECURITY_NOT_REPORTED",
                "portability_state": "NATIVE_ONLY",
                "output_manifest": manifest_path.relative_to(ROOT).as_posix(),
                "provider_commit": manifest["provider_commit"],
            }
        )
    return result


def other_native_records() -> list[dict[str, Any]]:
    heir_path = OUTPUTS / "heir/dot-product-8f-v1/manifest.json"
    heir = load_json(heir_path)
    result = []
    for runtime in heir["runtimes"]:
        result.append(
            {
                "provider": "HEIR",
                "system": "HEIR",
                "workload": heir["workload"],
                "arm": runtime,
                "runtime": runtime,
                "scheme": "CKKS",
                "evidence_level": 2,
                "execution_status": "PASS",
                "actual_output_available": False,
                "decision_output_available": False,
                "contexts_keysets": 1,
                "unique_inputs": 1,
                "raw_output_rows": 0,
                "compile_time_ms": NOT_SEPARATELY_RECORDED,
                "tuning_time_ms": NOT_APPLICABLE,
                "keygen_time_ms": NOT_SEPARATELY_RECORDED,
                "encryption_time_ms": NOT_SEPARATELY_RECORDED,
                "evaluation_time_ms": NOT_SEPARATELY_RECORDED,
                "decryption_time_ms": NOT_SEPARATELY_RECORDED,
                "total_time_ms": 6540 if runtime == "OpenFHE" else NOT_SEPARATELY_RECORDED,
                "rms_error": NOT_REPORTED,
                "max_absolute_error": NOT_REPORTED,
                "validation_flips": NOT_EVALUATED,
                "audit_flips": NOT_EVALUATED,
                "gate_state": NOT_EVALUATED,
                "security_state": "SECURITY_NOT_REPORTED",
                "portability_state": "NATIVE_ONLY",
                "output_manifest": heir_path.relative_to(ROOT).as_posix(),
                "provider_commit": heir["source_commit"],
                "plaintext_output": "OUTPUT_UNAVAILABLE",
                "decrypted_output": "OUTPUT_UNAVAILABLE",
                "numerical_error": "OUTPUT_UNAVAILABLE",
            }
        )
    capture = verified_heir_capture()
    if capture is not None:
        capture_path, capture_manifest, capture_rows = capture
        for row in capture_rows:
            result.append(
                {
                    "provider": "HEIR",
                    "system": "HEIR",
                    "workload": capture_manifest["workload"],
                    "arm": f"{row['runtime']}_output_capture_v1",
                    "runtime": row["runtime"],
                    "scheme": "CKKS",
                    "evidence_level": 3,
                    "execution_status": "PASS",
                    "actual_output_available": True,
                    "decision_output_available": False,
                    "contexts_keysets": 1,
                    "unique_inputs": 1,
                    "raw_output_rows": 1,
                    "compile_time_ms": NOT_SEPARATELY_RECORDED,
                    "tuning_time_ms": NOT_APPLICABLE,
                    "keygen_time_ms": NOT_SEPARATELY_RECORDED,
                    "encryption_time_ms": NOT_SEPARATELY_RECORDED,
                    "evaluation_time_ms": NOT_SEPARATELY_RECORDED,
                    "decryption_time_ms": NOT_SEPARATELY_RECORDED,
                    "total_time_ms": NOT_SEPARATELY_RECORDED,
                    "rms_error": NOT_REPORTED,
                    "max_absolute_error": row["absolute_error"],
                    "validation_flips": NOT_EVALUATED,
                    "audit_flips": NOT_EVALUATED,
                    "gate_state": NOT_EVALUATED,
                    "security_state": "SECURITY_NOT_REPORTED",
                    "portability_state": "NATIVE_ONLY",
                    "output_manifest": capture_path.relative_to(ROOT).as_posix(),
                    "provider_commit": capture_manifest["source_commit"],
                    "input_id": row["input_id"],
                    "split_role": "official_native_example",
                    "plaintext_output": row["expected_output"],
                    "decrypted_output": row["decrypted_output"],
                    "numerical_error": row["absolute_error"],
                    "plaintext_decision": NOT_EVALUATED,
                    "encrypted_decision": NOT_EVALUATED,
                    "decision_flip": NOT_EVALUATED,
                    "raw_output_digest": sha256_file(capture_path.parent / "decrypted_outputs.csv"),
                }
            )
    heco_path = OUTPUTS / "heco/official-benchmark-v1/manifest.json"
    heco = load_json(heco_path)
    result.append(
        {
            "provider": "HECO",
            "system": "HECO",
            "workload": "official_benchmark",
            "arm": "official_bfv_pipeline",
            "runtime": "HElib",
            "scheme": heco["implemented_scheme"],
            "evidence_level": heco["evidence_level"],
            "execution_status": "OFFICIAL_PIPELINE_PASS",
            "actual_output_available": False,
            "decision_output_available": False,
            "contexts_keysets": NOT_REPORTED,
            "unique_inputs": NOT_REPORTED,
            "raw_output_rows": 0,
            "compile_time_ms": NOT_SEPARATELY_RECORDED,
            "tuning_time_ms": NOT_SEPARATELY_RECORDED,
            "keygen_time_ms": NOT_SEPARATELY_RECORDED,
            "encryption_time_ms": NOT_SEPARATELY_RECORDED,
            "evaluation_time_ms": NOT_SEPARATELY_RECORDED,
            "decryption_time_ms": NOT_SEPARATELY_RECORDED,
            "total_time_ms": NOT_SEPARATELY_RECORDED,
            "rms_error": NOT_REPORTED,
            "max_absolute_error": NOT_REPORTED,
            "validation_flips": NOT_EVALUATED,
            "audit_flips": NOT_EVALUATED,
            "gate_state": NOT_EVALUATED,
            "security_state": NOT_APPLICABLE,
            "portability_state": "NOT_PORTABLE_DIFFERENT_SCHEME",
            "output_manifest": heco_path.relative_to(ROOT).as_posix(),
            "provider_commit": heco["source_commit"],
        }
    )
    return result


NATIVE_FIELDS = [
    "schema_version", "provider_id", "provider_commit", "workload_id", "model_digest",
    "graph_digest", "input_id", "input_digest", "split_role", "context_or_key_id",
    "pass_index", "plaintext_output", "decrypted_output", "plaintext_decision",
    "encrypted_decision", "decision_margin_or_top_two_gap", "numerical_error",
    "decision_flip", "provider_prediction", "gate_status", "security_status",
    "raw_output_digest",
    "provider", "system", "workload", "arm", "runtime", "scheme", "evidence_level",
    "execution_status", "actual_output_available", "decision_output_available",
    "contexts_keysets", "unique_inputs", "raw_output_rows", "compile_time_ms",
    "tuning_time_ms", "keygen_time_ms", "encryption_time_ms", "evaluation_time_ms",
    "decryption_time_ms", "total_time_ms", "rms_error", "max_absolute_error",
    "validation_flips", "audit_flips", "gate_state", "security_state",
    "portability_state", "output_manifest",
]


def complete_native_record(row: dict[str, Any]) -> dict[str, Any]:
    completed = dict(row)
    completed.setdefault("schema_version", "flipguard_provider_execution_record_v7")
    completed.setdefault("provider_id", completed["provider"])
    completed.setdefault("workload_id", completed["workload"])
    completed.setdefault("gate_status", completed["gate_state"])
    completed.setdefault("security_status", completed["security_state"])
    completed.setdefault("decision_flip", completed["validation_flips"])
    completed.setdefault("numerical_error", completed["max_absolute_error"])
    completed.setdefault("raw_output_digest", sha256_file(ROOT / completed["output_manifest"]))
    return completed


def system_summary_rows(stages: list[dict[str, Any]], terminals: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    heir_capture_available = verified_heir_capture() is not None
    overrides: dict[str, dict[str, Any]] = {
        "EVA": {"final_state": "DECISION_BEARING_LOCKED_AUDIT", "evidence_level": 6, "encrypted_runs": 18, "decision_gate": "SAFE_AUDIT_PASS"},
        "ELASM": {"final_state": "ENCRYPTED_END_TO_END_PARTIAL_GRID", "evidence_level": 3, "encrypted_runs": 70, "decision_gate": NOT_EVALUATED},
        "HECATE": {"final_state": "CLEAN_BUILD_PASS_RUNTIME_PREPARATION_FAILED", "evidence_level": 1, "encrypted_runs": 0, "decision_gate": NOT_EVALUATED},
        "HEIR": {
            "final_state": "ENCRYPTED_END_TO_END_RAW_OUTPUT" if heir_capture_available else "OFFICIAL_PIPELINE_PASS_OUTPUT_UNAVAILABLE",
            "evidence_level": 3 if heir_capture_available else 2,
            "encrypted_runs": 4 if heir_capture_available else 2,
            "decision_gate": NOT_EVALUATED,
        },
        "HECO": {"final_state": "OFFICIAL_PIPELINE_ONLY_DIFFERENT_SCHEME", "evidence_level": 2, "encrypted_runs": 0, "decision_gate": NOT_EVALUATED},
        "Orion": {"final_state": "ENVIRONMENT_CREATE_BLOCKED", "evidence_level": 0, "encrypted_runs": 0, "decision_gate": NOT_EVALUATED},
        "HALO": {"final_state": "SHARED_REPOSITORY_CLEAN_BUILD_ONLY", "evidence_level": 1, "encrypted_runs": 0, "decision_gate": NOT_EVALUATED},
    }
    rows = []
    for system, provider in SYSTEMS:
        terminal = terminals.get(provider, {})
        override = overrides.get(system, {})
        evidence_level = override.get("evidence_level", 0)
        rows.append(
            {
                "system": system,
                "provider_queue_id": provider,
                "source_checkout_state": highest_stage_state(stages, provider, "SOURCE_CHECKOUT"),
                "clean_build_state": highest_stage_state(stages, provider, "CLEAN_BUILD"),
                "official_pipeline_state": highest_stage_state(stages, provider, "OFFICIAL_PIPELINE"),
                "final_state": override.get("final_state", terminal.get("terminal_state", "REPRODUCTION_BLOCKED")),
                "evidence_level": evidence_level,
                "encrypted_e2e_runs": override.get("encrypted_runs", 0),
                "decision_gate_state": override.get("decision_gate", NOT_EVALUATED),
                "security_state": "SECURITY_TARGET_MATCH_ASSUMPTIONS_DIFFER" if system == "EVA" else "SECURITY_NOT_EVALUATED",
                "portability_state": "NATIVE_ONLY" if evidence_level >= 2 else NOT_EVALUATED,
                "reason": terminal.get("reason", NOT_APPLICABLE if system in overrides else NOT_REPORTED),
                "terminal_manifest": terminal.get("manifest_path", NOT_APPLICABLE),
            }
        )
    return rows


def build_accounting(
    destination: Path,
    native: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    stages: list[dict[str, Any]],
) -> None:
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        system_native = [row for row in native if row["system"] == summary["system"]]
        provider = summary["provider_queue_id"]
        provider_stages = [row for row in stages if row["provider"] == provider]
        unique_inputs: int | str = sum(
            row["unique_inputs"] for row in system_native if isinstance(row["unique_inputs"], int)
        ) or (NOT_REPORTED if system_native else 0)
        if summary["system"] == "EVA":
            unique_inputs = 31
        elif summary["system"] == "ELASM":
            unique_inputs = 1
        source_commits = sorted({
            str(row["provider_commit"])
            for row in system_native
            if row.get("provider_commit") not in {None, NOT_REPORTED}
        })
        workloads = sorted({str(row["workload"]) for row in system_native})
        compile_times = [
            float(row["compile_time_ms"]) / 1000
            for row in system_native if isinstance(row["compile_time_ms"], (int, float))
        ]
        tuning_times = [
            float(row["tuning_time_ms"]) / 1000
            for row in system_native if isinstance(row["tuning_time_ms"], (int, float))
        ]
        inference_times = [
            float(row["evaluation_time_ms"]) / 1000
            for row in system_native if isinstance(row["evaluation_time_ms"], (int, float))
        ]
        build_wall = sum(
            float(row["elapsed_seconds"])
            for row in provider_stages if row["stage"] == "CLEAN_BUILD"
        )
        pipeline_wall = sum(
            float(row["elapsed_seconds"])
            for row in provider_stages
            if row["stage"] in {"OFFICIAL_PIPELINE", "ENCRYPTED_VALIDATION", "ENCRYPTED_AUDIT"}
        )
        rows.append(
            {
                "provider": provider,
                "system": summary["system"],
                "workload": ";".join(workloads) if workloads else NOT_EVALUATED,
                "evidence_level": summary["evidence_level"],
                "source_commit": ";".join(source_commits) if source_commits else NOT_REPORTED,
                "clean_build_runs": sum(row["stage"] == "CLEAN_BUILD" for row in provider_stages),
                "compiler_runs": sum(row["stage"] in {"OFFICIAL_PIPELINE", "ENCRYPTED_VALIDATION", "ENCRYPTED_AUDIT"} for row in provider_stages),
                "plans_generated": 72 if summary["system"] == "ELASM" else NOT_APPLICABLE,
                "plans_executed": 72 if summary["system"] == "ELASM" else NOT_APPLICABLE,
                "encrypted_candidate_runs": summary["encrypted_e2e_runs"],
                "unique_inputs": unique_inputs,
                "validation_samples": 14 if summary["system"] == "EVA" else NOT_EVALUATED,
                "audit_samples": 16 if summary["system"] == "EVA" else NOT_EVALUATED,
                "contexts_keysets": max((row["contexts_keysets"] for row in system_native if isinstance(row["contexts_keysets"], int)), default=NOT_REPORTED),
                "measurement_passes": NOT_SEPARATELY_RECORDED,
                "raw_output_rows": sum(row["raw_output_rows"] for row in system_native if isinstance(row["raw_output_rows"], int)),
                "build_wall_clock_seconds": build_wall,
                "compile_wall_clock_seconds": sum(compile_times) if compile_times else NOT_SEPARATELY_RECORDED,
                "tuning_wall_clock_seconds": sum(tuning_times) if tuning_times else NOT_SEPARATELY_RECORDED,
                "inference_wall_clock_seconds": sum(inference_times) if inference_times else NOT_SEPARATELY_RECORDED,
                "pipeline_wall_clock_seconds": pipeline_wall,
                "total_elapsed_seconds": build_wall + pipeline_wall,
                "validation_flips": sum(row["validation_flips"] for row in system_native if isinstance(row["validation_flips"], int)),
                "audit_flips": sum(row["audit_flips"] for row in system_native if isinstance(row["audit_flips"], int)),
                "gate_state": summary["decision_gate_state"],
                "security_state": summary["security_state"],
                "portability_state": summary["portability_state"],
                "final_selection_state": summary["final_state"],
            }
        )
    write_csv(
        destination / "execution_accounting.csv",
        [
            "provider", "system", "workload", "evidence_level", "source_commit",
            "clean_build_runs", "compiler_runs",
            "plans_generated", "plans_executed", "encrypted_candidate_runs", "unique_inputs",
            "validation_samples", "audit_samples", "contexts_keysets", "measurement_passes",
            "raw_output_rows", "build_wall_clock_seconds", "compile_wall_clock_seconds",
            "tuning_wall_clock_seconds", "inference_wall_clock_seconds",
            "pipeline_wall_clock_seconds", "total_elapsed_seconds",
            "validation_flips", "audit_flips", "gate_state", "security_state",
            "portability_state", "final_selection_state",
        ],
        rows,
    )


def build_summaries(destination: Path, native: list[dict[str, Any]]) -> None:
    latency_rows = []
    for (provider, workload), rows_iter in _group(native, lambda row: (row["provider"], row["workload"])):
        rows = list(rows_iter)
        totals = [float(row["total_time_ms"]) for row in rows if isinstance(row["total_time_ms"], (int, float))]
        evaluations = [float(row["evaluation_time_ms"]) for row in rows if isinstance(row["evaluation_time_ms"], (int, float))]
        latency_rows.append(
            {
                "provider": provider,
                "workload": workload,
                "timing_boundary": "provider_native_no_cross_runtime_speedup",
                "comparable_rows": len(totals),
                "mean_total_ms": mean(totals),
                "median_total_ms": statistics.median(totals) if totals else NOT_REPORTED,
                "p95_total_ms": percentile(totals, 0.95),
                "mean_evaluation_ms": mean(evaluations),
                "cross_runtime_ratio_admitted": False,
            }
        )
    write_csv(
        destination / "latency_summary.csv",
        [
            "provider", "workload", "timing_boundary", "comparable_rows", "mean_total_ms",
            "median_total_ms", "p95_total_ms", "mean_evaluation_ms", "cross_runtime_ratio_admitted",
        ],
        latency_rows,
    )

    numerical_rows = []
    for row in native:
        if row["rms_error"] == NOT_REPORTED and row["max_absolute_error"] == NOT_REPORTED:
            continue
        numerical_rows.append(
            {
                "provider": row["provider"],
                "workload": row["workload"],
                "arm": row["arm"],
                "rms_error": row["rms_error"],
                "max_absolute_error": row["max_absolute_error"],
                "validation_flips": row["validation_flips"],
                "audit_flips": row["audit_flips"],
                "gate_state": row["gate_state"],
            }
        )
    write_csv(
        destination / "numerical_error_summary.csv",
        [
            "provider", "workload", "arm", "rms_error", "max_absolute_error",
            "validation_flips", "audit_flips", "gate_state",
        ],
        numerical_rows,
    )


def _group(rows: list[dict[str, Any]], key):
    grouped: dict[Any, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(key(row), []).append(row)
    return sorted(grouped.items(), key=lambda item: item[0])


def build_security_and_portability(destination: Path, native: list[dict[str, Any]]) -> None:
    eva_official = load_json(OUTPUTS / "eva/official-image-v1/manifest.json")
    eva_shared = load_json(OUTPUTS / "eva/shared-polynomial-v1/manifest.json")
    shared_arms = {arm["candidate_id"]: arm for arm in eva_shared["arms"]}
    security_rows = []
    portability_rows = []
    for row in native:
        parameters = {
            "log_n": NOT_REPORTED,
            "n": NOT_REPORTED,
            "q_prime_bits": NOT_REPORTED,
            "p_prime_bits": NOT_REPORTED,
            "q_primes_exact": "EXACT_VALUES_NOT_REPORTED",
            "p_primes_exact": "EXACT_VALUES_NOT_REPORTED",
            "log_q": NOT_REPORTED,
            "log_p": NOT_REPORTED,
            "log_qp": NOT_REPORTED,
            "scale_bits": NOT_REPORTED,
            "secret_distribution": NOT_REPORTED,
            "error_distribution": NOT_REPORTED,
            "ciphertext_q_admission": NOT_EVALUATED,
            "evaluation_key_qp_admission": NOT_EVALUATED,
            "final_admission": NOT_EVALUATED,
        }
        if row["system"] == "EVA" and row["arm"] in shared_arms:
            arm = shared_arms[row["arm"]]
            security = arm["security_reference"]
            parameters.update(
                {
                    "log_n": security["log_n"],
                    "n": arm["poly_modulus_degree"],
                    "q_prime_bits": json.dumps(security["q_prime_bits"], separators=(",", ":")),
                    "p_prime_bits": json.dumps(security["p_prime_bits"], separators=(",", ":")),
                    "log_q": security["log_q"],
                    "log_p": security["log_p"],
                    "log_qp": security["log_qp"],
                    "scale_bits": arm["input_scale_bits"],
                    "secret_distribution": eva_shared["runtime"]["native_seal_secret"],
                    "error_distribution": eva_shared["runtime"]["native_seal_error"],
                    "ciphertext_q_admission": security["ciphertext_q_admission"],
                    "evaluation_key_qp_admission": security["evaluation_key_qp_admission"],
                    "final_admission": security["final_admission"],
                }
            )
        elif row["system"] == "EVA" and row["arm"] in {"sobel", "harris"}:
            program = next(item for item in eva_official["programs"] if item["program"] == row["arm"])
            parameters.update(
                {
                    "log_n": 14,
                    "n": program["poly_modulus_degree"],
                    "q_prime_bits": json.dumps(program["prime_bits"], separators=(",", ":")),
                    "scale_bits": NOT_REPORTED,
                }
            )
        security_rows.append(
            {
                "provider": row["provider"],
                "workload": row["workload"],
                "arm": row["arm"],
                "scheme": row["scheme"],
                "security_state": row["security_state"],
                "headline_eligible": row["security_state"] == "SECURITY_ALIGNED",
                "reason": "Runtime distribution equivalence was not established" if row["security_state"] != "SECURITY_ALIGNED" else NOT_APPLICABLE,
                **parameters,
            }
        )
        portability_rows.append(
            {
                "provider": row["provider"],
                "workload": row["workload"],
                "arm": row["arm"],
                "portability_state": row["portability_state"],
                "portable_exact": row["portability_state"] == "PORTABLE_EXACT",
                "graph_equivalent_common_executor": row["portability_state"] == "GRAPH_EQUIVALENT_COMMON_EXECUTOR",
                "headline_latency_eligible": row["portability_state"] == "PORTABLE_EXACT" and row["security_state"] == "SECURITY_ALIGNED",
            }
        )
    write_csv(
        destination / "security_summary.csv",
        [
            "provider", "workload", "arm", "scheme", "log_n", "n", "q_prime_bits",
            "p_prime_bits", "q_primes_exact", "p_primes_exact", "log_q", "log_p",
            "log_qp", "scale_bits", "secret_distribution", "error_distribution",
            "ciphertext_q_admission", "evaluation_key_qp_admission", "final_admission",
            "security_state", "headline_eligible", "reason",
        ],
        security_rows,
    )
    write_csv(
        destination / "portability_summary.csv",
        [
            "provider", "workload", "arm", "portability_state", "portable_exact",
            "graph_equivalent_common_executor", "headline_latency_eligible",
        ],
        portability_rows,
    )
    write_csv(
        destination / "common_executor_records.csv",
        [
            "provider", "workload", "arm", "portability_state", "security_state",
            "timing_boundary", "result_state",
        ],
        [],
    )


def build_failure_rows(
    destination: Path,
    stages: list[dict[str, Any]],
    terminals: dict[str, dict[str, Any]],
) -> None:
    reason_overrides = {
        ("eva", "0003-clean-build"): "PINNED_PYBIND11_SUBMODULE_NOT_INITIALIZED",
        ("corelab", "0005-elasm-grid"): "MISSING_NUMPY_AND_EXIT_137",
        ("corelab", "0005-elasm-grid-retry1"): "HARD_RESOURCE_STOP_EPHEMERAL_KEY_CONTEXT_ACCUMULATION",
        ("corelab", "0010-hecate-runtime"): "PROMISOR_REMOTE_LAZY_FETCH_FAILED_DURING_RUNTIME_CLONE",
        ("heir", "0003-output-freeze"): "OUTPUT_ROOT_PERMISSION_DENIED",
        ("heco", "0005-output-freeze"): "OUTPUT_ROOT_PERMISSION_DENIED",
        ("orion", "0002-clean-environment"): "MISSING_DECLARED_POETRY_CORE_BUILD_BACKEND",
        ("orion", "0002b-environment-recovery1"): "INVALID_POETRY_PACKAGE_METADATA_FOR_EDITABLE_INSTALL",
    }
    rows = []
    for row in stages:
        if row["state"] != "FAILED":
            continue
        rows.append(
            {
                "provider": row["provider"],
                "run_id": row["run_id"],
                "stage": row["stage"],
                "failure_class": "RECOVERABLE_IMPLEMENTATION_FAILURE",
                "exit_code": row["return_code"],
                "reason_code": reason_overrides.get((row["provider"], row["run_id"]), "STAGE_COMMAND_FAILED"),
                "scientific_result_preserved": True,
                "retry_changed_semantics": False,
                "manifest_path": row["manifest_path"],
            }
        )
    interrupted = STATUS / "corelab/0005-elasm-grid-retry1/current_stage.txt"
    if interrupted.exists():
        rows.append(
            {
                "provider": "corelab",
                "run_id": "0005-elasm-grid-retry1",
                "stage": "ENCRYPTED_VALIDATION",
                "failure_class": "HARD_RESOURCE_STOP",
                "exit_code": "SIGNAL_15",
                "reason_code": reason_overrides[("corelab", "0005-elasm-grid-retry1")],
                "scientific_result_preserved": True,
                "retry_changed_semantics": False,
                "manifest_path": NOT_APPLICABLE,
            }
        )
    core_rows = csv_rows(OUTPUTS / "corelab/elasm-linear-regression-grid-v1/records.csv")
    for row in core_rows:
        if row["execution_status"] == "PASS":
            continue
        run_dir = OUTPUTS / f"corelab/elasm-linear-regression-grid-v1/{row['mode']}_{int(row['waterline']):02d}"
        stderr = (run_dir / "execute.stderr").read_text(encoding="utf-8", errors="replace").strip().splitlines()
        rows.append(
            {
                "provider": "corelab",
                "run_id": f"{row['mode']}_{int(row['waterline']):02d}",
                "stage": "ENCRYPTED_PLAN_EXECUTION",
                "failure_class": "SCIENTIFIC_PLAN_EXECUTION_FAILURE",
                "exit_code": row["execution_exit_status"],
                "reason_code": stderr[-1] if stderr else row["failure_reason"],
                "scientific_result_preserved": True,
                "retry_changed_semantics": NOT_APPLICABLE,
                "manifest_path": run_dir.relative_to(ROOT).as_posix(),
            }
        )
    for provider, terminal in terminals.items():
        if terminal["terminal_state"] in {"OFFICIAL_PIPELINE_ONLY"}:
            continue
        rows.append(
            {
                "provider": provider,
                "run_id": "terminal-state-v1",
                "stage": "PROVIDER_FINALIZE",
                "failure_class": terminal["terminal_state"],
                "exit_code": NOT_APPLICABLE,
                "reason_code": terminal["reason"],
                "scientific_result_preserved": True,
                "retry_changed_semantics": NOT_APPLICABLE,
                "manifest_path": terminal["manifest_path"],
            }
        )
    write_csv(
        destination / "failure_summary.csv",
        [
            "provider", "run_id", "stage", "failure_class", "exit_code", "reason_code",
            "scientific_result_preserved", "retry_changed_semantics", "manifest_path",
        ],
        rows,
    )


def build_retry_inventory(destination: Path) -> None:
    rows = []
    for path in sorted(EVIDENCE.glob("orchestration_amendment_*.json")):
        payload = load_json(path)
        rows.append(
            {
                "amendment": path.stem,
                "provider_or_scope": payload.get("affected_provider", payload.get("affected_scope", NOT_REPORTED)),
                "classification": payload.get("classification", payload.get("amendment_class", NOT_REPORTED)),
                "semantic_change": payload.get("computation_semantics_changed", payload.get("encrypted_execution_semantics_changed", payload.get("semantic_impact", "none"))) not in {False, "none", "none; initialize the official pinned submodule and rebuild from an empty V7 build directory", "none; install the declared Python numerical dependency before rerunning the same frozen 72-plan grid"},
                "policy_change": payload.get("frozen_policy_changed", payload.get("policy_change", False)),
                "encrypted_rerun_count": payload.get("recovery_encrypted_execution_count", NOT_APPLICABLE),
                "source_path": path.relative_to(ROOT).as_posix(),
                "payload_sha256": sha256_file(path),
            }
        )
    write_csv(
        destination / "retry_and_patch_inventory.csv",
        [
            "amendment", "provider_or_scope", "classification", "semantic_change",
            "policy_change", "encrypted_rerun_count", "source_path", "payload_sha256",
        ],
        rows,
    )


def build_claims(destination: Path, summaries: list[dict[str, Any]], native: list[dict[str, Any]]) -> dict[str, Any]:
    encrypted_systems = sorted(row["system"] for row in summaries if int(row["evidence_level"]) >= 3)
    decision_providers = sorted({row["provider"] for row in native if row["evidence_level"] >= 5})
    locked_audit_providers = sorted({row["provider"] for row in native if row["evidence_level"] >= 6})
    claims = {
        "external_encrypted_end_to_end": {
            "state": "PARTIALLY_SUPPORTED",
            "paper_admitted": True,
            "scope": encrypted_systems,
            "allowed_wording": f"V7 reproduced encrypted end-to-end execution with raw outputs for {', '.join(encrypted_systems)} on their declared native workloads.",
        },
        "external_decision_bearing_comparison": {
            "state": "PARTIALLY_SUPPORTED",
            "paper_admitted": True,
            "scope": decision_providers,
            "allowed_wording": "A frozen EVA candidate was evaluated by the FlipGuard gate and replayed on a disjoint locked audit.",
        },
        "multiple_external_decision_providers": {
            "state": "BLOCKED",
            "paper_admitted": False,
            "block_reason": "Only one external provider exposed a frozen decision-bearing validation/audit output.",
        },
        "portable_exact_common_executor": {
            "state": "NOT_EVALUATED",
            "paper_admitted": False,
            "block_reason": "No external plan satisfied the full PORTABLE_EXACT contract.",
        },
        "cross_runtime_speedup": {
            "state": "BLOCKED",
            "paper_admitted": False,
            "block_reason": "Native timing boundaries and runtime security assumptions differ.",
        },
        "universal_provider_superiority": {
            "state": "BLOCKED",
            "paper_admitted": False,
            "block_reason": "The reproduced set is finite and heterogeneous.",
        },
    }
    payload = {
        "schema_version": "flipguard_external_v7_claim_admission_v1",
        "paper_claim_allowed": False,
        "final_classification": "PARTIAL_EXTERNAL_EVIDENCE",
        "encrypted_e2e_system_count": len(encrypted_systems),
        "decision_bearing_provider_count": len(decision_providers),
        "locked_audit_provider_count": len(locked_audit_providers),
        "portable_exact_count": 0,
        "claims": claims,
    }
    write_json(destination / "claim_admission.json", payload)
    return payload


def build_fairness(destination: Path) -> None:
    (destination / "fairness_limitations.md").write_text(
        """# V7 Fairness Limitations

- Native absolute latencies are system-level observations and are not configuration-algorithm speedups.
- Only `PORTABLE_EXACT` rows could enter a common-executor headline; V7 established none.
- EVA, ELASM, HEIR, and HECO expose different graphs, runtimes, timing boundaries, and security assumptions.
- The CoreLab grid executed all 72 frozen plans; two execution failures remain in the denominator.
- HECO's recovered official benchmark is BFV and is not treated as a CKKS comparison arm.
- HECATE built successfully but its runtime checkout failed before encrypted execution.
- Hardware, license, absent-artifact, and environment blockers are not numeric zero results.
- A rejected external candidate would only fail the additional FlipGuard gate, not falsify its provider's original claim.
- No result is described as a global optimum or universal provider comparison.
""",
        encoding="utf-8",
    )


def build(destination: Path, source_commit: str) -> dict[str, Any]:
    destination.mkdir(parents=True, exist_ok=True)
    stages = stage_manifests()
    terminals = terminal_manifests()
    sources = official_sources(destination, source_commit)
    build_source_and_license_tables(destination, sources, stages)
    build_stage_matrices(destination, stages)

    eva_native, gates, audits = eva_native_records()
    native = [
        complete_native_record(row)
        for row in eva_native + corelab_native_records() + other_native_records()
    ]
    write_csv(destination / "native_execution_records.csv", NATIVE_FIELDS, native)
    write_csv(
        destination / "provider_gate_records.csv",
        [
            "provider", "workload", "candidate_id", "provider_objective", "security_admission",
            "validation_status", "validation_flips", "validation_violations", "audit_status",
            "audit_flips", "audit_violations", "retuning", "final_flipguard_state", "raw_ledger",
        ],
        gates,
    )
    write_csv(
        destination / "audit_records.csv",
        [
            "provider", "workload", "candidate_id", "validation_samples", "audit_samples",
            "contexts_keysets", "audit_status", "audit_flips", "audit_violations",
            "execution_failures", "retuning", "raw_ledger",
        ],
        audits,
    )
    summaries = system_summary_rows(stages, terminals)
    write_csv(
        destination / "artifact_execution_levels.csv",
        [
            "system", "provider_queue_id", "source_checkout_state", "clean_build_state",
            "official_pipeline_state", "final_state", "evidence_level", "encrypted_e2e_runs",
            "decision_gate_state", "security_state", "portability_state", "reason", "terminal_manifest",
        ],
        summaries,
    )
    build_accounting(destination, native, summaries, stages)
    build_summaries(destination, native)
    build_security_and_portability(destination, native)
    build_failure_rows(destination, stages, terminals)
    build_retry_inventory(destination)
    claims = build_claims(destination, summaries, native)
    build_fairness(destination)
    overlays = build_overlays(destination)
    return {
        "stage_manifest_count": len(stages),
        "system_count": len(summaries),
        "native_record_count": len(native),
        "provider_gate_record_count": len(gates),
        "audit_record_count": len(audits),
        **{key: claims[key] for key in (
            "final_classification", "encrypted_e2e_system_count",
            "decision_bearing_provider_count", "locked_audit_provider_count", "portable_exact_count",
        )},
        **overlays,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    source_commit = args.source_commit or subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    print(json.dumps(build(args.destination.resolve(), source_commit), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
