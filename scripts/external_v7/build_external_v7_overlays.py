#!/usr/bin/env python3
"""Build identity-bound V7 workload and per-sample evidence overlays."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "external/v7/outputs"
STATUS = ROOT / "external/v7/status"
HEIR_SOURCE = ROOT / "external/v7/sources/heir"
NOT_REPORTED = "NOT_REPORTED"
NOT_EVALUATED = "NOT_EVALUATED"
NOT_APPLICABLE = "NOT_APPLICABLE"
NOT_SEPARATELY_RECORDED = "NOT_SEPARATELY_RECORDED"
OUTPUT_UNAVAILABLE = "OUTPUT_UNAVAILABLE"

PROVIDER_EXECUTION_FIELDS = [
    "schema_version",
    "provider_id",
    "provider_commit",
    "runtime",
    "workload_id",
    "evidence_level",
    "model_digest",
    "graph_digest",
    "input_id",
    "input_digest",
    "split_role",
    "context_or_key_id",
    "pass_index",
    "plaintext_output",
    "decrypted_output",
    "plaintext_decision",
    "encrypted_decision",
    "decision_margin_or_top_two_gap",
    "numerical_error",
    "decision_flip",
    "provider_prediction",
    "execution_status",
    "gate_status",
    "security_status",
    "compile_time_ms",
    "tuning_time_ms",
    "keygen_time_ms",
    "encryption_time_ms",
    "evaluation_time_ms",
    "decryption_time_ms",
    "total_time_ms",
    "raw_output_digest",
    "candidate_id",
    "threshold",
    "error_violation",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode()).hexdigest()}"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, NOT_REPORTED) for field in fields})
            count += 1
    return count


def source_ref(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def input_identities() -> dict[str, dict[str, Any]]:
    eva_official = OUTPUTS / "eva/official-image-v1/per_pixel_outputs.csv"
    official_rows = read_csv(eva_official)
    canonical_pixels = [
        (row["pixel_index"], row["input_value"])
        for row in official_rows
        if row["program"] == "sobel" and row["key_context"] == "1"
    ]
    if len(canonical_pixels) != 4096:
        raise RuntimeError("EVA official input population drift")
    official_material = "\n".join(f"{index},{value}" for index, value in canonical_pixels) + "\n"

    shared_root = OUTPUTS / "eva/shared-polynomial-v1"
    validation_rows = [
        row for row in read_csv(shared_root / "validation_scale_30.csv")
        if row["key_repeat"] == "1"
    ]
    audit_rows = [
        row for row in read_csv(shared_root / "locked_audit_selected.csv")
        if row["key_repeat"] == "1"
    ]
    validation_material = "\n".join(
        f"{row['row_id']},{row['plaintext_score']}" for row in validation_rows
    ) + "\n"
    audit_material = "\n".join(
        f"{row['row_id']},{row['plaintext_score']}" for row in audit_rows
    ) + "\n"

    core_result = load_json(
        OUTPUTS / "corelab/elasm-linear-regression-grid-v1/eva_15/result.json"
    )
    core_digest = sha256_text(
        f"{core_result['input_x_sha256']}\n{core_result['input_y_sha256']}\n"
    )

    heir_files = [
        HEIR_SOURCE / "tests/Examples/common/dot_product_8f.mlir",
        HEIR_SOURCE / "tests/Examples/openfhe/ckks/dot_product_8f/dot_product_8f_test.cpp",
        HEIR_SOURCE / "tests/Examples/lattigo/ckks/dot_product_8f/dot_product_8f_test.go",
    ]
    heir_digest = sha256_text("\n".join(sha256_file(path) for path in heir_files) + "\n")
    return {
        "eva_official_image": {
            "input_id": "eva_v1.0.1_official_baboon_64x64",
            "input_digest": sha256_text(official_material),
            "unique_inputs": 1,
            "ordered_observations": 4096,
            "source": source_ref(eva_official),
        },
        "eva_shared_validation": {
            "input_id": "shared_polynomial_validation_v1",
            "input_digest": sha256_text(validation_material),
            "unique_inputs": len(validation_rows),
            "role": "configuration_validation",
            "source": source_ref(shared_root / "validation_scale_30.csv"),
        },
        "eva_shared_audit": {
            "input_id": "shared_polynomial_locked_audit_v1",
            "input_digest": sha256_text(audit_material),
            "unique_inputs": len(audit_rows),
            "role": "locked_audit",
            "source": source_ref(shared_root / "locked_audit_selected.csv"),
        },
        "corelab_linear_regression": {
            "input_id": "official_linear_regression_seed_20260805",
            "input_digest": core_digest,
            "input_x_sha256": core_result["input_x_sha256"],
            "input_y_sha256": core_result["input_y_sha256"],
            "unique_inputs": 1,
        },
        "heir_dot_product_8f": {
            "input_id": "official_dot_product_8f_input_v1",
            "input_digest": heir_digest,
            "unique_inputs": 1,
            "source_files": [source_ref(path) for path in heir_files],
        },
        "heco_official_benchmark": {
            "input_id": OUTPUT_UNAVAILABLE,
            "input_digest": OUTPUT_UNAVAILABLE,
            "unique_inputs": NOT_REPORTED,
        },
    }


def build_identity_manifests(destination: Path, identities: dict[str, dict[str, Any]]) -> None:
    eva_official_path = OUTPUTS / "eva/official-image-v1/manifest.json"
    eva_official = load_json(eva_official_path)
    shared_path = OUTPUTS / "eva/shared-polynomial-v1/manifest.json"
    shared = load_json(shared_path)
    core_path = OUTPUTS / "corelab/elasm-linear-regression-grid-v1/manifest.json"
    core = load_json(core_path)
    heir_path = OUTPUTS / "heir/dot-product-8f-v1/manifest.json"
    heir = load_json(heir_path)
    heco_path = OUTPUTS / "heco/official-benchmark-v1/manifest.json"
    heco = load_json(heco_path)

    workload_contracts = {
        "schema_version": "flipguard_external_v7_workload_contracts_v1",
        "contracts": [
            {
                "workload_id": eva_official["workload_id"],
                "provider": "EVA",
                "graph_identity": "PROVIDER_NATIVE_EXACT",
                "programs": [
                    {
                        "name": program["program"],
                        "graph_digest": sha256_file(
                            eva_official_path.parent / f"{program['program']}_compiled.dot"
                        ),
                        "ordered_observations": program["ordered_observations"],
                    }
                    for program in eva_official["programs"]
                ],
                "decision_rule": NOT_EVALUATED,
                "raw_manifest": source_ref(eva_official_path),
            },
            {
                "workload_id": "shared_polynomial_v1",
                "provider": "EVA",
                "graph_identity": "SHARED_POLYNOMIAL_CONTRACT",
                "graph_digest": shared["contract_sha256"],
                "threshold": 0.5,
                "decision_rule": "binary_threshold",
                "raw_manifest": source_ref(shared_path),
            },
            {
                "workload_id": core["workload"],
                "provider": "ELASM/CoreLab",
                "graph_identity": "PROVIDER_NATIVE_EXACT",
                "graph_digest": core["trace_sha256"],
                "decision_rule": NOT_EVALUATED,
                "raw_manifest": source_ref(core_path),
            },
            {
                "workload_id": heir["workload"],
                "provider": "HEIR",
                "graph_identity": "PROVIDER_NATIVE_EXACT",
                "graph_digest": sha256_file(
                    HEIR_SOURCE / "tests/Examples/common/dot_product_8f.mlir"
                ),
                "decision_rule": NOT_EVALUATED,
                "raw_manifest": source_ref(heir_path),
            },
            {
                "workload_id": "official_benchmark",
                "provider": "HECO",
                "graph_identity": "PROVIDER_NATIVE_DIFFERENT_SCHEME",
                "graph_digest": NOT_REPORTED,
                "scheme": heco["implemented_scheme"],
                "decision_rule": NOT_EVALUATED,
                "raw_manifest": source_ref(heco_path),
            },
        ],
    }
    write_json(destination / "workload_contracts/manifest.json", workload_contracts)
    write_json(
        destination / "input_manifests/manifest.json",
        {
            "schema_version": "flipguard_external_v7_input_manifests_v1",
            "identities": identities,
            "validation_audit_overlap": 0,
        },
    )
    candidates = {
        "schema_version": "flipguard_external_v7_provider_candidates_v1",
        "providers": {
            "EVA": {
                "official_programs": [row["program"] for row in eva_official["programs"]],
                "shared_candidates": [
                    {
                        "candidate_id": arm["candidate_id"],
                        "input_scale_bits": arm["input_scale_bits"],
                        "poly_modulus_degree": arm["poly_modulus_degree"],
                        "prime_bits": arm["prime_bits"],
                        "security_state": arm["security_reference"]["final_admission"],
                        "validation_state": arm["validation"]["status"],
                    }
                    for arm in shared["arms"]
                ],
                "selected_candidate": shared["selected"]["candidate_id"],
            },
            "ELASM/CoreLab": {
                "modes": core["modes"],
                "waterlines": core["waterlines"],
                "plans_generated": core["plans_generated"],
                "plans_executed": core["plans_executed"],
            },
            "HEIR": {"runtimes": heir["runtimes"], "decision_rule": heir["decision_rule"]},
            "HECO": {"scheme": heco["implemented_scheme"], "ckks_eligible": heco["ckks_eligible"]},
        },
    }
    write_json(destination / "provider_candidate_manifests/manifest.json", candidates)

    operations = []
    for path in sorted(STATUS.glob("*/*/run_manifest.json")):
        payload = load_json(path)
        operations.append(
            {
                "provider": payload["provider"],
                "run_id": payload["run_id"],
                "stage": payload["stage"],
                "state": payload["state"],
                "source_sha256": payload["source_sha256"],
                "input_sha256": payload["input_sha256"],
                "output_sha256": payload["output_sha256"],
                "manifest": source_ref(path),
            }
        )
    write_json(
        destination / "operation_manifests/manifest.json",
        {
            "schema_version": "flipguard_external_v7_operation_manifests_v1",
            "operation_count": len(operations),
            "operations": operations,
        },
    )


def base_record(**values: Any) -> dict[str, Any]:
    row = {field: NOT_REPORTED for field in PROVIDER_EXECUTION_FIELDS}
    row.update(
        {
            "schema_version": "flipguard_provider_execution_record_v7",
            "model_digest": NOT_APPLICABLE,
            "pass_index": NOT_SEPARATELY_RECORDED,
            "plaintext_decision": NOT_EVALUATED,
            "encrypted_decision": NOT_EVALUATED,
            "decision_margin_or_top_two_gap": NOT_EVALUATED,
            "decision_flip": NOT_EVALUATED,
            "gate_status": NOT_EVALUATED,
            "tuning_time_ms": NOT_SEPARATELY_RECORDED,
            "security_status": "SECURITY_NOT_EVALUATED",
            "candidate_id": NOT_APPLICABLE,
            "threshold": NOT_EVALUATED,
            "error_violation": NOT_EVALUATED,
            **values,
        }
    )
    return row


def eva_official_rows(identities: dict[str, dict[str, Any]]) -> Iterable[dict[str, Any]]:
    root = OUTPUTS / "eva/official-image-v1"
    manifest = load_json(root / "manifest.json")
    graph_digests = {
        program["program"]: sha256_file(root / f"{program['program']}_compiled.dot")
        for program in manifest["programs"]
    }
    raw_digest = sha256_file(root / "per_pixel_outputs.csv")
    for row in read_csv(root / "per_pixel_outputs.csv"):
        yield base_record(
            provider_id="EVA",
            provider_commit=manifest["provider_commit"],
            runtime="native_eva_seal",
            workload_id=manifest["workload_id"],
            evidence_level=3,
            graph_digest=graph_digests[row["program"]],
            input_id=row["input_id"],
            input_digest=identities["eva_official_image"]["input_digest"],
            split_role="official_native_example",
            context_or_key_id=row["key_context"],
            plaintext_output=row["plaintext_output"],
            decrypted_output=row["decrypted_output"],
            numerical_error=row["absolute_error"],
            provider_prediction=row["decrypted_output"],
            execution_status="PASS",
            compile_time_ms=next(
                item["compile_ms"] for item in manifest["programs"]
                if item["program"] == row["program"]
            ),
            keygen_time_ms=row["keygen_ms"],
            encryption_time_ms=row["encrypt_ms"],
            evaluation_time_ms=row["execute_ms"],
            decryption_time_ms=row["decrypt_ms"],
            total_time_ms=row["total_ms"],
            raw_output_digest=raw_digest,
            candidate_id=row["program"],
        )


def eva_shared_rows(identities: dict[str, dict[str, Any]]) -> Iterable[dict[str, Any]]:
    root = OUTPUTS / "eva/shared-polynomial-v1"
    manifest = load_json(root / "manifest.json")
    arms = {str(arm["input_scale_bits"]): arm for arm in manifest["arms"]}
    sources = [
        (root / f"validation_scale_{scale}.csv", arm, "eva_shared_validation")
        for scale, arm in arms.items()
    ]
    selected = next(arm for arm in manifest["arms"] if arm["candidate_id"] == manifest["selected"]["candidate_id"])
    sources.append((root / "locked_audit_selected.csv", selected, "eva_shared_audit"))
    for path, arm, identity_key in sources:
        raw_digest = sha256_file(path)
        for row in read_csv(path):
            gate = "REJECTED_SAMPLE" if row["decision_flip"] == "true" or row["error_violation"] == "true" else "SAFE_SAMPLE"
            yield base_record(
                provider_id="EVA",
                provider_commit=manifest["runtime"]["eva_commit"],
                runtime="native_eva_seal",
                workload_id="shared_polynomial_v1",
                evidence_level=6 if identity_key == "eva_shared_audit" else 5,
                graph_digest=arm["compiled_program_semantic_sha256"],
                input_id=row["row_id"],
                input_digest=identities[identity_key]["input_digest"],
                split_role=row["phase"],
                context_or_key_id=row["key_repeat"],
                plaintext_output=row["plaintext_score"],
                decrypted_output=row["native_ckks_score"],
                plaintext_decision=row["plaintext_decision"],
                encrypted_decision=row["native_ckks_decision"],
                decision_margin_or_top_two_gap=row["decision_margin"],
                numerical_error=row["absolute_error"],
                decision_flip=row["decision_flip"],
                provider_prediction=row["native_ckks_score"],
                execution_status="PASS" if row["execution_status"] == "OK" else "FAILED",
                gate_status=gate,
                security_status="SECURITY_TARGET_MATCH_ASSUMPTIONS_DIFFER",
                compile_time_ms=NOT_SEPARATELY_RECORDED,
                keygen_time_ms=row["keygen_ms"],
                encryption_time_ms=row["encrypt_ms"],
                evaluation_time_ms=row["execute_ms"],
                decryption_time_ms=row["decrypt_ms"],
                total_time_ms=row["total_sample_ms"],
                raw_output_digest=raw_digest,
                candidate_id=arm["candidate_id"],
                threshold=row["threshold"],
                error_violation=row["error_violation"],
            )


def corelab_rows(identities: dict[str, dict[str, Any]]) -> Iterable[dict[str, Any]]:
    root = OUTPUTS / "corelab/elasm-linear-regression-grid-v1"
    manifest = load_json(root / "manifest.json")
    for row in read_csv(root / "records.csv"):
        plan_id = f"{row['mode']}_{int(row['waterline']):02d}"
        result_path = root / plan_id / "result.json"
        if result_path.is_file():
            result = load_json(result_path)
            plaintext = json.dumps(
                {"w": result["plaintext_w"], "c": result["plaintext_c"]},
                sort_keys=True,
                separators=(",", ":"),
            )
            decrypted = json.dumps(
                {"w_slot0": result["encrypted_w_slot0"], "c_slot0": result["encrypted_c_slot0"]},
                sort_keys=True,
                separators=(",", ":"),
            )
            raw_digest = sha256_file(result_path)
            timing = result["timing_ms"]
        else:
            plaintext = OUTPUT_UNAVAILABLE
            decrypted = OUTPUT_UNAVAILABLE
            raw_digest = sha256_file(root / plan_id / "execute.stderr")
            timing = {}
        yield base_record(
            provider_id="ELASM" if row["mode"] == "elasm" else "CoreLab EVA mode",
            provider_commit=manifest["provider_commit"],
            runtime="SEAL_HEVM",
            workload_id=manifest["workload"],
            evidence_level=row["evidence_level"],
            graph_digest=manifest["trace_sha256"],
            input_id=identities["corelab_linear_regression"]["input_id"],
            input_digest=identities["corelab_linear_regression"]["input_digest"],
            split_role="official_native_example",
            context_or_key_id=plan_id,
            plaintext_output=plaintext,
            decrypted_output=decrypted,
            numerical_error=row["reported_rms_error"] or OUTPUT_UNAVAILABLE,
            provider_prediction=decrypted,
            execution_status=row["execution_status"],
            compile_time_ms=float(row["compile_wall_seconds"]) * 1000,
            keygen_time_ms=timing.get("context_keygen", NOT_SEPARATELY_RECORDED),
            encryption_time_ms=timing.get("encryption", NOT_SEPARATELY_RECORDED),
            evaluation_time_ms=timing.get("evaluation", NOT_SEPARATELY_RECORDED),
            decryption_time_ms=timing.get("decryption", NOT_SEPARATELY_RECORDED),
            total_time_ms=timing.get("total", float(row["execution_wrapper_wall_seconds"]) * 1000),
            raw_output_digest=raw_digest,
            candidate_id=plan_id,
        )


def heir_rows(identities: dict[str, dict[str, Any]]) -> Iterable[dict[str, Any]]:
    root = OUTPUTS / "heir/dot-product-8f-output-capture-v1"
    manifest_path = root / "manifest.json"
    outputs_path = root / "decrypted_outputs.csv"
    if not manifest_path.is_file() and not outputs_path.is_file():
        return
    if not manifest_path.is_file() or not outputs_path.is_file():
        raise RuntimeError("partial HEIR per-sample output capture")
    manifest = load_json(manifest_path)
    raw_digest = sha256_file(outputs_path)
    graph_digest = sha256_file(HEIR_SOURCE / "tests/Examples/common/dot_product_8f.mlir")
    for row in read_csv(outputs_path):
        yield base_record(
            provider_id="HEIR",
            provider_commit=manifest["source_commit"],
            runtime=row["runtime"],
            workload_id=manifest["workload"],
            evidence_level=3,
            graph_digest=graph_digest,
            input_id=row["input_id"],
            input_digest=identities["heir_dot_product_8f"]["input_digest"],
            split_role="official_native_example",
            context_or_key_id="output_capture_context_1",
            plaintext_output=row["expected_output"],
            decrypted_output=row["decrypted_output"],
            numerical_error=row["absolute_error"],
            provider_prediction=row["decrypted_output"],
            execution_status="PASS",
            raw_output_digest=raw_digest,
        )


def build_per_sample_outputs(destination: Path, identities: dict[str, dict[str, Any]]) -> dict[str, int]:
    root = destination / "per_sample_outputs"
    counts = {
        "eva_official": write_csv(
            root / "eva_official_image.csv", eva_official_rows(identities), PROVIDER_EXECUTION_FIELDS
        ),
        "eva_shared": write_csv(
            root / "eva_shared_polynomial.csv", eva_shared_rows(identities), PROVIDER_EXECUTION_FIELDS
        ),
        "corelab": write_csv(
            root / "corelab_linear_regression_plans.csv", corelab_rows(identities), PROVIDER_EXECUTION_FIELDS
        ),
        "heir": write_csv(
            root / "heir_dot_product_8f.csv", heir_rows(identities), PROVIDER_EXECUTION_FIELDS
        ),
    }
    write_json(
        root / "manifest.json",
        {
            "schema_version": "flipguard_external_v7_per_sample_outputs_v1",
            "schema_fields": PROVIDER_EXECUTION_FIELDS,
            "row_counts": counts,
            "total_rows": sum(counts.values()),
            "no_missing_value_imputation": True,
        },
    )
    return counts


def build_flip_summary(destination: Path) -> None:
    gates_path = destination / "provider_gate_records.csv"
    rows = []
    for row in read_csv(gates_path):
        rows.append(
            {
                "provider": row["provider"],
                "workload": row["workload"],
                "candidate_id": row["candidate_id"],
                "validation_flips": row["validation_flips"],
                "audit_flips": row["audit_flips"],
                "validation_state": row["validation_status"],
                "audit_state": row["audit_status"],
                "final_state": row["final_flipguard_state"],
            }
        )
    write_csv(
        destination / "flip_summary.csv",
        rows,
        [
            "provider", "workload", "candidate_id", "validation_flips", "audit_flips",
            "validation_state", "audit_state", "final_state",
        ],
    )


def build_overlays(destination: Path) -> dict[str, Any]:
    identities = input_identities()
    build_identity_manifests(destination, identities)
    counts = build_per_sample_outputs(destination, identities)
    build_flip_summary(destination)
    return {
        "per_sample_output_counts": counts,
        "per_sample_output_total": sum(counts.values()),
        "workload_contract_count": 5,
        "input_manifest_count": len(identities),
    }
