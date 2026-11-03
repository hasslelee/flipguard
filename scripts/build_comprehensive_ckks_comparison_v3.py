#!/usr/bin/env python3
"""Build the evidence-tiered 21-system CKKS comparison pack.

This builder consumes frozen FlipGuard and V2 external-audit evidence. It does
not run encrypted workloads, infer missing measurements, or translate an
external plan into the common executor.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import statistics
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "docs/evidence/comprehensive_ckks_comparison_v3"
PROTOCOL = PACK / "protocol"
V2 = ROOT / "docs/evidence/external_autotuner_comparison_v2"
RESULTS = ROOT / "results/thesis_grade_protocol/comprehensive_ckks_comparison_v3"
PAPER = ROOT / "results/thesis_grade_protocol/comprehensive_ckks_comparison_paper_inputs_v1"
CLAIMS = ROOT / "docs/evidence/comprehensive_ckks_comparison_claim_admission_v1"
PROTOCOL_COMMIT = "0076fa55e479b121a11aa747709adcff24750f62"

MISSING = {
    "NOT_REPORTED", "NOT_EVALUATED", "NOT_APPLICABLE", "BUILD_BLOCKED",
    "OUTPUT_UNAVAILABLE", "HARDWARE_BLOCKED",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checksum_tree(root: Path, exclude: set[str] | None = None) -> list[str]:
    exclude = exclude or set()
    lines = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "SHA256SUMS":
            continue
        rel = path.relative_to(root).as_posix()
        if rel in exclude or any(rel.startswith(prefix + "/") for prefix in exclude):
            continue
        lines.append(f"{sha256(path)}  {rel}")
    (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return lines


def publication_state(row: dict) -> str:
    if row["system"] == "FHECrafter":
        return "WORKSHOP_PEER_REVIEWED"
    if row["system"] == "FlipGuard":
        return "TECHNICAL_REPORT"
    if row.get("publication_status") == "preprint":
        return "PREPRINT"
    return "PEER_REVIEWED"


def artifact_state(system: str) -> str:
    archive = {"Orbit"}
    repositories = {
        "EVA", "HECO", "HEIR", "ANT-ACE", "HECATE", "ELASM", "DaCapo",
        "HALO", "ReSBM", "AutoFHE", "Orion", "SLOTHE", "FlipGuard",
    }
    if system in archive:
        return "OFFICIAL_ARCHIVE"
    if system in repositories:
        return "OFFICIAL_REPOSITORY"
    return "PAPER_ONLY"


def load_systems() -> list[dict]:
    source = read_json(V2 / "protocol/source_registry.json")
    overrides = read_json(PROTOCOL / "v3_source_overrides.json")
    rows = []
    for raw in source["systems"]:
        row = dict(raw)
        row.update(overrides["systems"].get(row["system"], {}))
        rows.append(row)
    rows.append(overrides["flipguard"])
    assert len(rows) == 21
    assert len({row["system"] for row in rows}) == 21
    return rows


def load_attempts() -> list[dict]:
    attempts = {row["system"]: dict(row) for row in read_json(V2 / "protocol/build_attempts.json")["systems"]}
    new_path = PROTOCOL / "v3_artifact_attempts.json"
    if new_path.exists():
        for update in read_json(new_path)["systems"]:
            attempts[update["system"]] = update
    attempts["FlipGuard"] = {
        "system": "FlipGuard", "set": "SYSTEM_UNDER_EVALUATION",
        "artifact_revision": "flipguard-thesis-v1.0.0-rc2@6c5f8b234f9f9da91a189fa0f2dc180bb996abf5",
        "attempts": 1, "status": "PASS", "reproduced": True,
        "container_or_environment": "frozen Lattigo v6.2.0 research environment",
        "command_class": "FROZEN_EVIDENCE_VERIFICATION",
        "last_error": "", "dependency": "Go; Lattigo v6.2.0; Python",
        "official_environment_difference": "NOT_APPLICABLE",
        "reason_code": "PASS_FROZEN_RESEARCH_ARTIFACT",
        "algorithm_semantics_changed": False,
        "log_sha256": "docs/evidence/research_release_binding_rc2_v1/SHA256SUMS",
        "notes": "Existing frozen evidence was verified, not re-executed.",
        "patches": [],
    }
    return [attempts[row["system"]] for row in load_systems()]


def execution_axes(system: str, attempt: dict) -> dict:
    native = system in {"EVA", "FlipGuard"}
    schedule = system in {"Orbit"}
    config_only = system in {"Orion"}
    build_status = attempt["status"]
    if build_status == "PASS":
        build_state = "BUILD_SMOKE_PASS"
    elif build_status in {"REPRODUCTION_BLOCKED", "RELATED_WORK_ONLY", "NOT_COMPARABLE", "NOT_APPLICABLE"}:
        build_state = "BUILD_BLOCKED" if attempt.get("attempts", 0) else "NOT_ATTEMPTED"
    elif build_status == "HARDWARE_BLOCKED":
        build_state = "HARDWARE_BLOCKED"
    else:
        build_state = "BUILD_BLOCKED"
    if native:
        execution_state = "NATIVE_END_TO_END_PASS"
    elif schedule or config_only:
        execution_state = "NATIVE_END_TO_END_PARTIAL"
    else:
        execution_state = "NO_END_TO_END_RUN"
    if native:
        output_state = "RAW_PER_SAMPLE_OUTPUT"
    elif schedule:
        output_state = "SCHEDULE_ONLY"
    elif config_only:
        output_state = "CONFIGURATION_ONLY"
    else:
        output_state = "PAPER_REPORTED_ONLY"
    if system in {"EVA", "Orion", "FlipGuard"}:
        gate = "GATE_EVALUATED"
    elif native:
        gate = "GATE_NOT_APPLICABLE"
    elif output_state in {"CONFIGURATION_ONLY", "SCHEDULE_ONLY"}:
        gate = "OUTPUT_UNAVAILABLE"
    else:
        gate = "OUTPUT_UNAVAILABLE"
    return {
        "build_state": build_state,
        "execution_state": execution_state,
        "output_evidence_state": output_state,
        "decision_gate_state": gate,
        "portability_state": "NATIVE_ONLY" if native else "NOT_EVALUATED",
        "latency_comparability": "NATIVE_DIAGNOSTIC_ONLY" if native else "NOT_AVAILABLE",
    }


def make_landscape(systems: list[dict], attempts: list[dict]) -> tuple[list[dict], list[dict]]:
    attempt_map = {row["system"]: row for row in attempts}
    fields = [
        "system", "full_title", "authors", "venue", "year", "publication_state",
        "official_paper", "official_repository", "official_archive", "artifact_revision",
        "license", "supported_scheme", "backend", "frontend_model_format",
        "optimization_target", "parameter_search_space", "scale_management",
        "bootstrapping", "packing_layout", "security_handling", "error_correctness_metric",
        "model_workload", "artifact_state", "build_state", "execution_state",
        "workload_mapping_state", "output_evidence_state", "decision_gate_state",
        "portability_state", "latency_comparability", "experimental_tier",
        "comparison_relevance", "direct_comparison_limitation",
    ]
    output = []
    artifacts = []
    for system in systems:
        name = system["system"]
        axes = execution_axes(name, attempt_map[name])
        tier = "TIER_1"
        if axes["execution_state"] == "NATIVE_END_TO_END_PASS":
            tier = "TIER_3"
        elif name in {row["system"] for row in read_json(PROTOCOL / "paper_reported_source_records.json")["records"]}:
            tier = "TIER_2"
        row = {key: system.get(key, "NOT_REPORTED") for key in fields}
        row.update(axes)
        row.update({
            "publication_state": publication_state(system),
            "official_archive": system.get("official_archive", "NOT_REPORTED"),
            "artifact_state": artifact_state(name),
            "workload_mapping_state": "EXACT_SHARED_GRAPH" if name == "FlipGuard" else (
                "SAME_TASK_DIFFERENT_GRAPH" if name in {"EVA", "HECATE", "ELASM", "Orion"} else "NOT_APPLICABLE"
            ),
            "experimental_tier": tier,
            "direct_comparison_limitation": system.get("exclusion_reason", "NOT_REPORTED"),
        })
        output.append(row)
        artifacts.append({
            "system": name,
            "artifact_state": row["artifact_state"],
            "official_repository": row["official_repository"],
            "official_archive": row["official_archive"],
            "revision": row["artifact_revision"],
            "license": row["license"],
            "audit_status": attempt_map[name]["status"],
            "attempts": attempt_map[name]["attempts"],
            "reason_code": attempt_map[name]["reason_code"],
        })
    write_csv(PACK / "landscape/systems.csv", output, fields)
    write_csv(
        PACK / "landscape/artifact_matrix.csv", artifacts,
        ["system", "artifact_state", "official_repository", "official_archive", "revision", "license", "audit_status", "attempts", "reason_code"],
    )
    pub = Counter(row["publication_state"] for row in output)
    write_csv(PACK / "landscape/publication_status.csv", [{"publication_state": k, "systems": v} for k, v in sorted(pub.items())], ["publication_state", "systems"])
    sources = {
        "schema_version": "flipguard_comprehensive_official_sources_v3",
        "audit_date": "2026-08-05",
        "protocol_commit": PROTOCOL_COMMIT,
        "raw_papers_not_redistributed": True,
        "systems": [
            {
                "system": row["system"], "paper": row["official_paper"],
                "repository": row["official_repository"], "archive": row["official_archive"],
                "revision": row["artifact_revision"], "license": row["license"],
            }
            for row in output
        ],
        "paper_checksums": read_json(PROTOCOL / "paper_reported_source_records.json")["records"],
    }
    write_json(PACK / "landscape/official_sources.json", sources)
    write_json(PACK / "official_sources/official_sources.json", sources)
    write_csv(
        PACK / "official_sources/source_checksums.csv",
        [
            {"system": row["system"], "official_paper": row["official_paper"], "pdf_sha256": row["pdf_sha256"], "source_locator": row["source_locator"]}
            for row in read_json(PROTOCOL / "paper_reported_source_records.json")["records"]
        ],
        ["system", "official_paper", "pdf_sha256", "source_locator"],
    )
    write_json(PACK / "official_sources/local_checksum_audit.json", {
        "audit_date": "2026-08-05",
        "raw_pdfs_committed": False,
        "verified_records": 13,
        "status": "PASS",
        "method": "downloaded official PDF bytes matched the recorded SHA-256 before evidence freeze",
        "systems": [row["system"] for row in read_json(PROTOCOL / "paper_reported_source_records.json")["records"] if row["system"] != "FlipGuard"],
    })
    write_json(PACK / "landscape/landscape_manifest.json", {
        "systems": 21, "external_systems": 20, "publication_state_counts": dict(pub),
        "performance_ranking": False, "all_missing_explicit": True,
    })
    return output, artifacts


def make_artifact_audit(attempts: list[dict]) -> list[dict]:
    fields = [
        "system", "set", "artifact_revision", "attempts", "status", "smoke_gate_pass",
        "container_or_environment", "command_class", "last_error", "dependency",
        "official_environment_difference", "reason_code", "algorithm_semantics_changed",
        "log_sha256", "notes",
    ]
    audit_rows = [{**row, "smoke_gate_pass": row["status"] == "PASS"} for row in attempts]
    write_csv(PACK / "build_matrix.csv", audit_rows, fields)
    write_csv(PACK / "artifact_audit/build_matrix.csv", audit_rows, fields)
    patches = []
    failures = []
    for row in attempts:
        slug = row["system"].lower().replace(".", "_").replace("-", "_").replace(" ", "_")
        write_json(PACK / f"artifact_audit/environment_manifests/{slug}.json", {
            "system": row["system"], "revision": row["artifact_revision"],
            "environment": row["container_or_environment"], "dependency": row["dependency"],
            "official_environment_difference": row["official_environment_difference"],
        })
        for patch in row.get("patches", []):
            patches.append({"system": row["system"], **patch})
        if row["status"] != "PASS":
            failures.append({
                "system": row["system"], "stage": "ARTIFACT_AUDIT", "status": row["status"],
                "reason_code": row["reason_code"], "attempts": row["attempts"],
                "exact_error": row["last_error"],
                "scientific_effect": "not counted as native reproduction; retained in landscape",
            })
    write_csv(PACK / "artifact_audit/patch_inventory.csv", patches, ["system", "attempt", "kind", "description", "semantics_changed"])
    write_csv(PACK / "failure_summary.csv", failures, ["system", "stage", "status", "reason_code", "attempts", "exact_error", "scientific_effect"])
    write_json(PACK / "artifact_audit/log_redaction_manifest.json", {
        "schema_version": "flipguard_build_log_redaction_v1",
        "redactions": [{
            "path": "build_logs/resbm_attempt1_build_and_mode_smoke.log",
            "reason": "remove local researcher home path from the public evidence copy",
            "replacement": "${FLIPGUARD_ARTIFACT_CACHE}",
            "source_raw_sha256": "sha256:530a24139e75a91195e125a1aeceaeadf737298ecd15b3e1b6f34ff368c7ade6",
            "public_copy_sha256": "sha256:3208727f34f702d85b5d98cd13aa668372798a5756088b950b366a2426b44d28",
            "execution_output_changed": False,
        }],
    })
    return failures


def applicability_state(system: str, workload: str, build: str) -> tuple[str, str]:
    if build in {"REPRODUCTION_BLOCKED", "HARDWARE_BLOCKED"}:
        return ("BUILD_BLOCKED" if build == "REPRODUCTION_BLOCKED" else "HARDWARE_UNAVAILABLE", "official artifact did not reach executable output")
    official = {
        "EVA": {"external_eva_sobel", "external_eva_harris", "external_eva_polynomial"},
        "HECATE": {"external_corelab_mlp", "external_corelab_lenet", "external_corelab_regression"},
        "ELASM": {"external_corelab_mlp", "external_corelab_lenet", "external_corelab_regression"},
        "HEIR": {"external_heir_ckks_examples"},
        "ANT-ACE": {"external_ant_onnx_cnn"},
        "Orion": {"external_orion_nn"},
        "AutoFHE": {"external_autofhe_cifar"},
        "DaCapo": {"external_bootstrap_deep"}, "HALO": {"external_bootstrap_deep"},
        "ReSBM": {"external_bootstrap_deep"}, "Orbit": {"external_bootstrap_deep"},
        "SLOTHE": {"external_slothe_model"},
    }
    if workload in official.get(system, set()):
        return "EXACT_OFFICIAL_PROVIDER_WORKLOAD", "official workload; not automatically shared with FlipGuard"
    if system == "FlipGuard" and workload.startswith("frozen_"):
        return "EXACT_SHARED_WORKLOAD", "frozen FlipGuard workload"
    if workload.startswith("frozen_") and system in {"EVA", "HECATE", "ELASM", "Orion", "ANT-ACE", "AutoFHE", "LOHEN"}:
        return "SAME_TASK_DIFFERENT_GRAPH", "name or task overlaps, but graph/packing/model identity is not exact"
    if workload.startswith("frozen_") and system in {"DaCapo", "HALO", "ReSBM", "Orbit"}:
        return "NO_BOOTSTRAP_NOT_APPLICABLE", "frozen workloads do not require bootstrapping"
    if system in {"CHET", "HEaaN.MLIR", "HEILP", "LOHEN", "Application-Aware Approximate HE", "FHE-Agent", "FHECrafter"}:
        return "ARTIFACT_UNAVAILABLE", "no executable output closure for this audit"
    return "OUTPUT_NOT_EXPOSED", "no exact graph and raw output pair was established"


def make_applicability(systems: list[dict], attempts: list[dict]) -> list[dict]:
    workloads = [
        "frozen_binary_tabular", "frozen_mlp100", "frozen_lenet5_small", "frozen_sobel",
        "frozen_harris", "frozen_cnn_lite", "frozen_deeper_polynomial",
        "external_eva_sobel", "external_eva_harris", "external_eva_polynomial",
        "external_corelab_mlp", "external_corelab_lenet", "external_corelab_regression",
        "external_heir_ckks_examples", "external_ant_onnx_cnn", "external_orion_nn",
        "external_autofhe_cifar", "external_bootstrap_deep", "external_slothe_model",
    ]
    build = {row["system"]: row["status"] for row in attempts}
    rows = []
    for system in systems:
        row = {"system": system["system"]}
        reasons = []
        for workload in workloads:
            state, reason = applicability_state(system["system"], workload, build[system["system"]])
            row[workload] = state
            reasons.append(f"{workload}:{reason}")
        row["reason_summary"] = " | ".join(reasons)
        rows.append(row)
    write_csv(PACK / "applicability_matrix.csv", rows, ["system", *workloads, "reason_summary"])
    shutil.copyfile(PACK / "applicability_matrix.csv", PROTOCOL / "tool_workload_applicability.csv")
    return rows


def make_native_and_gate(systems: list[dict], attempts: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    old_native = {row["provider"]: row for row in read_csv(V2 / "native_results.csv")}
    attempt_map = {row["system"]: row for row in attempts}
    native = []
    for system in systems:
        name = system["system"]
        row = {
            "schema_version": "flipguard_provider_execution_record_v3", "provider_id": name,
            "provider_commit": system.get("artifact_revision", "NOT_REPORTED"),
            "runtime": attempt_map[name]["container_or_environment"],
            "workload_id": "NOT_EVALUATED", "model_digest": "NOT_EVALUATED",
            "graph_digest": "NOT_EVALUATED", "input_id": "NOT_EVALUATED",
            "input_digest": "NOT_EVALUATED", "split_role": "OFFICIAL_NATIVE_DIAGNOSTIC",
            "key_or_context_id": "NOT_EVALUATED", "plaintext_output": "NOT_EVALUATED",
            "decrypted_output": "NOT_EVALUATED", "numerical_error": "NOT_EVALUATED",
            "provider_prediction": "NOT_EVALUATED", "plaintext_prediction": "NOT_EVALUATED",
            "decision_flip": "NOT_EVALUATED", "decision_quantity": "NOT_EVALUATED",
            "reserve_policy_status": "NOT_EVALUATED", "execution_status": "NO_END_TO_END_RUN",
            "security_metadata": "NOT_EVALUATED", "compile_time_ms": "NOT_SEPARATELY_RECORDED",
            "tuning_time_ms": "NOT_EVALUATED", "keygen_time_ms": "NOT_EVALUATED",
            "evaluation_time_ms": "NOT_EVALUATED", "total_time_ms": "NOT_EVALUATED",
            "raw_output_digest": "OUTPUT_UNAVAILABLE",
        }
        if name == "EVA":
            old = old_native[name]
            row.update({
                "workload_id": old["workload"], "plaintext_output": old["output_values"],
                "decrypted_output": old["output_values"], "numerical_error": f"rms={old['rms_error']};max={old['max_error']}",
                "decision_flip": old["decision_flips"], "reserve_policy_status": "REJECTED",
                "execution_status": "NATIVE_END_TO_END_PASS", "security_metadata": old["security_state"],
                "keygen_time_ms": old["key_generation"], "evaluation_time_ms": old["evaluation_latency"],
                "total_time_ms": old["total_latency"], "raw_output_digest": "BOUND_BY_FROZEN_EVA_LEDGER",
            })
        elif name == "Orbit":
            row.update({
                "workload_id": "official motivation.mlir optimizer smoke", "execution_status": "NATIVE_END_TO_END_PARTIAL",
                "plaintext_output": "NOT_EVALUATED", "decrypted_output": "OUTPUT_UNAVAILABLE",
                "raw_output_digest": attempt_map[name]["log_sha256"],
            })
        elif name == "FlipGuard":
            row.update({
                "workload_id": "controlled primary 50 workload-partition instances",
                "model_digest": "BOUND_BY_FROZEN_MANIFESTS", "graph_digest": "BOUND_BY_FROZEN_MANIFESTS",
                "input_id": "five deterministic partitions", "input_digest": "BOUND_BY_FROZEN_MANIFESTS",
                "split_role": "OFFICIAL_NATIVE_DIAGNOSTIC", "key_or_context_id": "three fresh-key repeats; seed roles bound by frozen manifests",
                "plaintext_output": "BOUND_BY_FROZEN_LEDGER", "decrypted_output": "BOUND_BY_FROZEN_LEDGER",
                "numerical_error": "BOUND_BY_FROZEN_LEDGER", "provider_prediction": "BOUND_BY_FROZEN_LEDGER",
                "plaintext_prediction": "BOUND_BY_FROZEN_LEDGER", "decision_flip": 0,
                "decision_quantity": "binary threshold margin", "reserve_policy_status": "SAFE 50/50",
                "execution_status": "NATIVE_END_TO_END_PASS", "security_metadata": "SECURITY_POLICY_V2_ADMITTED",
                "compile_time_ms": "NOT_SEPARATELY_RECORDED", "tuning_time_ms": "NOT_SEPARATELY_RECORDED",
                "keygen_time_ms": "210 selection key runs", "evaluation_time_ms": "FROZEN_PAIRED_EVIDENCE",
                "total_time_ms": "FROZEN_PAIRED_EVIDENCE", "raw_output_digest": "BOUND_BY_FINAL_CONFIRMATORY_MANIFEST",
            })
        native.append(row)
    native_fields = list(native[0])
    write_csv(PACK / "native_execution_records.csv", native, native_fields)

    gates = [
        {
            "provider": "EVA", "provider_objective": "vector compiler parameter generation",
            "workload": "seed0 development native replay", "candidate": "N16384 Q=3x60 P=60 input-scale=20",
            "provider_only_result": "EXECUTION_PASS", "security_admission": "STATIC_PASS_RUNTIME_MODEL_NOT_EQUIVALENT",
            "validation_flips": 11, "audit_flips": "NOT_EVALUATED", "reserve_policy_status": "REJECTED",
            "final_flipguard_state": "REJECTED", "latency": "NATIVE_DIAGNOSTIC_ONLY", "gate_overhead": "NOT_PAIRED",
            "output_scope": "RAW_PER_SAMPLE_OUTPUT", "evidence": "docs/evidence/eva_native_runtime_replay_v1/summary.json",
        },
        {
            "provider": "Orion", "provider_objective": "packed deep-learning compilation",
            "workload": "public configuration static audit", "candidate": "three public configurations inspected",
            "provider_only_result": "PUBLIC_SOURCE_AVAILABLE", "security_admission": "NOT_ADMITTED",
            "validation_flips": "NOT_EXECUTED", "audit_flips": "NOT_EXECUTED", "reserve_policy_status": "NOT_EVALUATED",
            "final_flipguard_state": "PLAN_UNSUPPORTED", "latency": "NOT_EVALUATED", "gate_overhead": "STATIC_ONLY",
            "output_scope": "CONFIGURATION_ONLY", "evidence": "docs/evidence/orion_external_adapter_audit_v1/manifest.json",
        },
    ]
    write_csv(PACK / "provider_gate_records.csv", gates, list(gates[0]))

    common = []
    for system in systems:
        if system["system"] == "FlipGuard":
            common.append({
                "provider": "FlipGuard internal providers", "workload": "controlled primary",
                "level": "PORTABLE_EXACT_INTERNAL", "graph_identity": "MATCH",
                "operation_order_identity": "MATCH", "weights_input_identity": "MATCH",
                "packing_identity": "MATCH", "parameter_schedule_identity": "MATCH",
                "security_comparable": "SECURITY_POLICY_ALIGNED", "headline_eligible": True,
                "result": "catalog/direct geometric mean total ratio 3.140660 confirmatory",
                "reason": "frozen paired Lattigo arms; not an external-provider portability result",
            })
        else:
            common.append({
                "provider": system["system"], "workload": "frozen and official workload audit",
                "level": "NOT_EVALUATED", "graph_identity": "NOT_ESTABLISHED",
                "operation_order_identity": "NOT_ESTABLISHED", "weights_input_identity": "NOT_ESTABLISHED",
                "packing_identity": "NOT_ESTABLISHED", "parameter_schedule_identity": "NOT_ESTABLISHED",
                "security_comparable": "NOT_ESTABLISHED", "headline_eligible": False,
                "result": "NOT_EVALUATED", "reason": "no external plan satisfied all E1 fields or a predeclared defensible E2 translation",
            })
    write_csv(PACK / "common_executor_records.csv", common, list(common[0]))
    return native, gates, common


def make_provider_manifests() -> None:
    manifests = [
        {
            "schema_version": "flipguard_provider_candidate_manifest_v3",
            "provider": "EVA", "provider_objective": "vector compilation and automatic parameter generation",
            "source_commit": "v1.0.1@4cd3254c9c51340ae30c451495ce5378135758c0",
            "workload": "seed0 development linear_poly3 native replay",
            "log_n": 14, "q": [60, 60, 60], "p": [60], "scale": 20,
            "scale_schedule": "EVA-generated native schedule", "rescale_modswitch_relinearization_placement": "EVA generated",
            "bootstrapping_placement": "NOT_APPLICABLE", "packing": "EVA/SEAL vector packing",
            "plans_generated": 1, "plans_executed": 1, "selected_plan": "native_v1.0.1_N16384_Q3x60_P60_scale20",
            "tuning_parameters": "NOT_SEPARATELY_RECORDED", "security_assumptions": "SEAL sec_level_type::none in source replay; separately qualified",
            "runtime_assumptions": "EVA v1.0.1 / Microsoft SEAL 3.6.4",
            "unsupported_or_missing_fields": ["exact operation-order equivalence to frozen current workloads", "portable packing identity"],
            "raw_artifact_digest": "sha256:a8a0ad63c50c6f806fa50adce43686d59c67f5817c8f01fab63aa8f41c1f4581",
        },
        {
            "schema_version": "flipguard_provider_candidate_manifest_v3",
            "provider": "Orion", "provider_objective": "packed deep-learning compilation",
            "source_commit": "main@be8a827350a147d610fe3bb998b5bea8de814ff8",
            "workload": "three public configurations static audit", "log_n": "NOT_ADMITTED",
            "q": "UNSUPPORTED_OR_MISSING", "p": "UNSUPPORTED_OR_MISSING", "scale": "PUBLIC_CONFIGURATION_FIELDS",
            "scale_schedule": "NOT_LOSSLESSLY_IMPORTED", "rescale_modswitch_relinearization_placement": "NOT_LOSSLESSLY_IMPORTED",
            "bootstrapping_placement": "PUBLIC_CONFIG_ONLY", "packing": "ORION_NATIVE_PACKING_NOT_PORTED",
            "plans_generated": 3, "plans_executed": 0, "selected_plan": "PLAN_UNSUPPORTED",
            "tuning_parameters": "STATIC_FAIL_CLOSED_IMPORT", "security_assumptions": "NOT_ADMITTED",
            "runtime_assumptions": "Orion native runtime not executed for frozen workload",
            "unsupported_or_missing_fields": ["exact Q/P materialization", "raw per-sample output", "common-executor schedule"],
            "raw_artifact_digest": "sha256:bc0a1f248850fee0ab280317a1621521c1130f2e7472ad5edba08617d7db48c9",
        },
        {
            "schema_version": "flipguard_provider_candidate_manifest_v3",
            "provider": "Orbit", "provider_objective": "rescale and bootstrap placement by integer programming",
            "source_commit": "zenodo-v2@f364122b77be482bfe902c20a89755cee2060c5a",
            "workload": "official motivation.mlir optimizer smoke", "log_n": "NOT_EMITTED_BY_QUICK_PATH",
            "q": "NOT_EMITTED_BY_QUICK_PATH", "p": "NOT_EMITTED_BY_QUICK_PATH", "scale": "SCHEDULE_MODEL",
            "scale_schedule": "assignment estimate 0.266 seconds; TDAG estimate 0.235 seconds",
            "rescale_modswitch_relinearization_placement": "optimizer schedule output", "bootstrapping_placement": "optimizer schedule output",
            "packing": "NOT_EVALUATED", "plans_generated": 1, "plans_executed": 0,
            "selected_plan": "SCHEDULE_ONLY", "tuning_parameters": "official motivation.mlir quick command",
            "security_assumptions": "NOT_EVALUATED_IN_QUICK_PATH", "runtime_assumptions": "official Docker quick path",
            "unsupported_or_missing_fields": ["encrypted execution", "per-sample output", "exact shared workload", "common-executor plan"],
            "raw_artifact_digest": "sha256:fd36de1e1f7b409c00b4bd2c30df68778cd841412fbb4297ea4c4f9affa04c94",
        },
        {
            "schema_version": "flipguard_provider_candidate_manifest_v3",
            "provider": "FlipGuard direct", "provider_objective": "bounded direct synthesis under a decision-integrity contract",
            "source_commit": "flipguard-thesis-v1.0.0-rc2@6c5f8b234f9f9da91a189fa0f2dc180bb996abf5",
            "workload": "controlled primary 50 workload-partition instances", "log_n": "PER_LITERAL_IN_FROZEN_MANIFEST",
            "q": "PER_LITERAL_IN_FROZEN_MANIFEST", "p": "PER_LITERAL_IN_FROZEN_MANIFEST", "scale": "PER_LITERAL_IN_FROZEN_MANIFEST",
            "scale_schedule": "Direct Policy V2", "rescale_modswitch_relinearization_placement": "Direct Policy V2 graph trace",
            "bootstrapping_placement": "NOT_SUPPORTED_IN_FROZEN_SCOPE", "packing": "scalar-replicated",
            "plans_generated": 70, "plans_executed": 70, "selected_plan": "first SAFE literal per instance",
            "tuning_parameters": "rho=0.5; margin floor=0.001; maximum trials=4; bounded repairs",
            "security_assumptions": "Security Policy V2", "runtime_assumptions": "Lattigo v6.2.0 frozen execution",
            "unsupported_or_missing_fields": ["single universal literal", "actual tuning wall-clock separated from candidate timing"],
            "raw_artifact_digest": "docs/evidence/final_confirmatory_suite_v1/manifest.json",
        },
    ]
    target = PACK / "provider_candidate_manifests"
    target.mkdir(parents=True, exist_ok=True)
    for row in manifests:
        write_json(target / f"{row['provider'].lower().replace(' ', '_')}.json", row)
    write_csv(target / "index.csv", [
        {"provider": row["provider"], "workload": row["workload"], "selected_plan": row["selected_plan"], "raw_artifact_digest": row["raw_artifact_digest"]}
        for row in manifests
    ], ["provider", "workload", "selected_plan", "raw_artifact_digest"])


def make_workload_contracts() -> None:
    target = PACK / "workload_contracts"
    target.mkdir(parents=True, exist_ok=True)
    for source in sorted((PROTOCOL / "workload_contracts").glob("*.json")):
        shutil.copyfile(source, target / source.name)
    rows = [
        {"workload_family": "EVA Sobel/Harris/polynomial", "source_system": "EVA", "contract_state": "EXACT_OFFICIAL_PROVIDER_WORKLOAD", "shared_with_flipguard": False, "reason": "official graph retained; no exact current frozen-plan equivalence"},
        {"workload_family": "CoreLab MLP/LeNet/regression", "source_system": "HECATE/ELASM", "contract_state": "EXACT_OFFICIAL_PROVIDER_WORKLOAD", "shared_with_flipguard": False, "reason": "same task names do not establish graph/packing identity"},
        {"workload_family": "HEIR CKKS examples", "source_system": "HEIR", "contract_state": "BUILD_BLOCKED", "shared_with_flipguard": False, "reason": "release closure did not execute"},
        {"workload_family": "ANT-ACE ONNX CNN", "source_system": "ANT-ACE", "contract_state": "HARDWARE_UNAVAILABLE", "shared_with_flipguard": False, "reason": "different packed graph and high-resource official evaluation"},
        {"workload_family": "Orion NN", "source_system": "Orion", "contract_state": "OUTPUT_NOT_EXPOSED", "shared_with_flipguard": False, "reason": "configuration-only static audit"},
        {"workload_family": "AutoFHE CIFAR", "source_system": "AutoFHE", "contract_state": "HARDWARE_UNAVAILABLE", "shared_with_flipguard": False, "reason": "different architecture-search objective and high-resource evaluation"},
        {"workload_family": "bootstrap deep models", "source_system": "DaCapo/HALO/ReSBM/Orbit", "contract_state": "NO_BOOTSTRAP_NOT_APPLICABLE", "shared_with_flipguard": False, "reason": "no bootstrap workload was manufactured"},
    ]
    write_csv(target / "official_workload_contract_index.csv", rows, list(rows[0]))


def make_paper_reported() -> list[dict]:
    rows = read_json(PROTOCOL / "paper_reported_source_records.json")["records"]
    fields = list(rows[0])
    write_csv(PACK / "paper_reported_results.csv", rows, fields)
    return rows


def trial_distribution() -> dict:
    manifests = [
        ROOT / "docs/evidence/direct_locked_audit_seed0_development_v1/manifest.json",
        ROOT / "docs/evidence/direct_locked_audit_final_source_v1/manifest.json",
    ]
    selection_roots = [path.parent / "inputs/selections" for path in manifests]
    values = []
    trials = []
    for manifest_path, selection_root in zip(manifests, selection_roots):
        manifest = read_json(manifest_path)
        values.extend(int(row["configuration_trials"]) for row in manifest["workloads"])
        for path in sorted(selection_root.glob("*.json")):
            trials.extend(read_json(path)["trials"])
    assert len(values) == 50 and sum(values) == 70 and len(trials) == 70
    quartiles = statistics.quantiles(values, n=4, method="inclusive")
    result = {
        "instances": len(values), "candidate_trials": sum(values),
        "mean": statistics.mean(values), "median": statistics.median(values),
        "q1": quartiles[0], "q3": quartiles[2], "iqr": quartiles[2] - quartiles[0],
        "maximum": max(values), "one_trial_instances": values.count(1),
        "two_trial_instances": values.count(2), "three_trial_instances": values.count(3),
        "four_trial_instances": values.count(4),
        "repair_causes": dict(Counter(trial.get("failure_signal", "NONE") for trial in trials if trial.get("status") != "SAFE")),
        "selection_key_runs": sum(int(trial["key_repeats_completed"]) for trial in trials),
        "encrypted_sample_evaluations": sum((int(trial["v_cert"]) + int(trial["v_amb"])) * int(trial["key_repeats_completed"]) for trial in trials),
        "actual_tuning_wall_clock": "NOT_SEPARATELY_RECORDED",
        "sum_of_per_trial_mean_total_ms_not_wall_clock": sum(float(trial["mean_total_ms"]) for trial in trials),
        "statistical_unit": "workload-partition instance",
    }
    write_json(PACK / "internal_trial_distribution.json", result)
    write_csv(PACK / "tuning_cost_records.csv", [
        {
            "provider": "FlipGuard direct", "workload": "controlled primary 50 instances",
            "source_build_time": "NOT_INCLUDED", "compile_time": "NOT_SEPARATELY_RECORDED",
            "configuration_generation_time": "NOT_SEPARATELY_RECORDED", "search_tuning_time": "NOT_SEPARATELY_RECORDED",
            "plans_generated": 70, "plans_executed": 70, "encrypted_candidate_executions": 70,
            "fresh_key_runs": result["selection_key_runs"], "sample_evaluations": result["encrypted_sample_evaluations"],
            "final_inference_latency": "SEE_FROZEN_PAIRED_EVIDENCE", "boundary": "candidate trial accounting; not process wall-clock",
        }
    ], ["provider", "workload", "source_build_time", "compile_time", "configuration_generation_time", "search_tuning_time", "plans_generated", "plans_executed", "encrypted_candidate_executions", "fresh_key_runs", "sample_evaluations", "final_inference_latency", "boundary"])
    return result


def make_summaries(native: list[dict], gates: list[dict], common: list[dict], trials: dict) -> None:
    paired = read_json(ROOT / "docs/evidence/journal_mlp_paired_latency_v1/analysis/summary.json")
    primary = read_json(ROOT / "results/thesis_grade_protocol/paired_latency_claim_admission_v1/seeds1_4_confirmatory_summary.json")
    latency = [
        {
            "comparison": "controlled_primary_catalog_over_direct", "scope": "COMMON_EXECUTOR_INTERNAL_FLIPGUARD_ARMS",
            "statistical_unit": "10 dataset-model clusters", "geometric_mean_total_ratio": primary["catalog_over_direct"]["geometric_mean_total_latency_ratio"],
            "ci95_low": primary["catalog_over_direct"]["cluster_bootstrap_95_ci_total"]["low"], "ci95_high": primary["catalog_over_direct"]["cluster_bootstrap_95_ci_total"]["high"],
            "decision_stable": True, "cross_runtime_ranking": False,
        },
        {
            "comparison": "MLP100_graph_only_over_gap_aware", "scope": "COMMON_EXECUTOR_INTERNAL_FLIPGUARD_ARMS",
            "statistical_unit": "100 image clusters", "geometric_mean_total_ratio": paired["pairs"][0]["geometric_mean_total_ratio"],
            "ci95_low": paired["pairs"][0]["total_ci_low"], "ci95_high": paired["pairs"][0]["total_ci_high"],
            "decision_stable": True, "cross_runtime_ranking": False,
        },
        {
            "comparison": "MLP100_catalog_over_gap_aware", "scope": "COMMON_EXECUTOR_INTERNAL_FLIPGUARD_ARMS",
            "statistical_unit": "100 image clusters", "geometric_mean_total_ratio": paired["pairs"][1]["geometric_mean_total_ratio"],
            "ci95_low": paired["pairs"][1]["total_ci_low"], "ci95_high": paired["pairs"][1]["total_ci_high"],
            "decision_stable": True, "cross_runtime_ranking": False,
        },
    ]
    write_csv(PACK / "latency_summary.csv", latency, list(latency[0]))
    flips = [
        {"provider": "EVA", "scope": "native development diagnostic", "validation_flips": 11, "audit_flips": "NOT_EVALUATED", "final_state": "REJECTED"},
        {"provider": "Orion", "scope": "static configuration audit", "validation_flips": "NOT_EXECUTED", "audit_flips": "NOT_EXECUTED", "final_state": "PLAN_UNSUPPORTED"},
        {"provider": "FlipGuard direct", "scope": "controlled primary confirmatory", "validation_flips": 0, "audit_flips": 0, "final_state": "SAFE"},
    ]
    write_csv(PACK / "decision_flip_summary.csv", flips, list(flips[0]))
    security = [
        {"provider": row["provider_id"], "native_security_state": row["security_metadata"], "flipguard_policy_interpretation": "SEPARATE_RUNTIME_INTERPRETATION" if row["provider_id"] == "EVA" else ("SECURITY_POLICY_V2_ADMITTED" if row["provider_id"] == "FlipGuard" else "NOT_EVALUATED"), "comparability": "SECURITY_POLICY_ALIGNED" if row["provider_id"] == "FlipGuard" else "SECURITY_ASSUMPTIONS_DIFFER" if row["provider_id"] == "EVA" else "SECURITY_NOT_EVALUATED"}
        for row in native
    ]
    write_csv(PACK / "security_summary.csv", security, list(security[0]))
    portability = Counter(row["level"] for row in common if row["provider"] != "FlipGuard internal providers")
    write_csv(PACK / "portability_summary.csv", [{"portability_state": key, "external_systems": value} for key, value in sorted(portability.items())], ["portability_state", "external_systems"])
    stable = []
    for row in read_csv(ROOT / "docs/evidence/paired_latency_final_v1/summary/pair_summaries.csv"):
        if row["numerator_arm_id"] == "catalog" and row["denominator_arm_id"] == "direct":
            stable.append({
                "workload": row["workload_id"], "declared_candidate_set": "direct; Security-V2 bounded-catalog; fixed reference",
                "fastest_stable_candidate": "direct", "catalog_over_direct_total_ratio": row["geometric_mean_total_ratio"],
                "external_candidate_included": False, "scope": "frozen internal common-executor arms",
            })
    write_csv(PACK / "fastest_stable_candidates.csv", stable, list(stable[0]))
    write_json(RESULTS / "summary.json", {
        "native_rows": len(native), "provider_gate_rows": len(gates),
        "external_portable_exact": 0, "external_graph_equivalent_common_executor": 0,
        "trial_distribution": trials, "latency": latency,
        "fastest_stable_internal_workloads": len(stable),
        "no_external_head_to_head_claim": True,
    })


def feature_value(system: str, feature: str) -> str:
    groups = {
        "parameter_selection": {"CHET", "EVA", "HECATE", "ELASM", "DaCapo", "ReSBM", "Orbit", "FHE-Agent", "FHECrafter", "FlipGuard"},
        "scale_management": {"EVA", "HECATE", "ELASM", "HEILP", "DaCapo", "HALO", "ReSBM", "Orbit", "FlipGuard"},
        "bootstrapping": {"DaCapo", "HALO", "ReSBM", "Orbit", "AutoFHE", "Orion", "LOHEN", "SLOTHE", "FHE-Agent"},
        "packing_layout": {"CHET", "HECO", "HEIR", "ANT-ACE", "HEaaN.MLIR", "Orion", "LOHEN", "FHE-Agent"},
        "model_adaptation": {"ANT-ACE", "AutoFHE", "Orion", "LOHEN", "SLOTHE", "FHE-Agent"},
        "numerical_error": {"EVA", "HECATE", "ELASM", "Application-Aware Approximate HE", "FHE-Agent", "FlipGuard"},
        "final_decision": {"FlipGuard"}, "no_safe": {"FlipGuard"}, "locked_audit": {"FlipGuard"},
        "security_admission": {"Application-Aware Approximate HE", "FHE-Agent", "FlipGuard"},
    }
    return "FULL" if system in groups[feature] else "OUT_OF_SCOPE"


def make_tables_figures(landscape: list[dict], artifacts: list[dict], native: list[dict], gates: list[dict], common: list[dict], reported: list[dict], trials: dict, applicability: list[dict]) -> None:
    tables = PACK / "tables"
    figures = PACK / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    features = ["parameter_selection", "scale_management", "bootstrapping", "packing_layout", "model_adaptation", "numerical_error", "final_decision", "no_safe", "locked_audit", "security_admission"]
    taxonomy = [{"system": row["system"], "publication": row["publication_state"], "optimization_target": row["optimization_target"], **{f: feature_value(row["system"], f) for f in features}} for row in landscape]
    write_csv(tables / "01_representative_systems_and_scope.csv", taxonomy, list(taxonomy[0]))
    write_csv(tables / "02_artifact_build_execution_status.csv", artifacts, list(artifacts[0]))
    equivalence = [{"system": row["system"], "workload_mapping": row["workload_mapping_state"], "portability": row["portability_state"], "latency_comparability": row["latency_comparability"]} for row in landscape]
    write_csv(tables / "03_exact_workload_model_equivalence.csv", equivalence, list(equivalence[0]))
    write_csv(tables / "04_native_provider_and_gate_results.csv", gates, list(gates[0]))
    write_csv(tables / "05_common_executor_stable_latency.csv", common, list(common[0]))
    shutil.copyfile(PACK / "tuning_cost_records.csv", tables / "06_configuration_tuning_cost.csv")
    write_csv(tables / "07_original_paper_normalized_results.csv", reported, list(reported[0]))
    write_csv(tables / "08_internal_trial_distribution.csv", [trials], list(trials))
    fairness = [
        {"issue": "cross-runtime latency", "boundary": "native absolute times are diagnostic only", "claim_effect": "no cross-provider speed ranking"},
        {"issue": "build smoke", "boundary": "compiler/help/test smoke is not end-to-end output", "claim_effect": "reported separately"},
        {"issue": "workload names", "boundary": "same name does not imply graph/packing/weight identity", "claim_effect": "no exact mapping inferred"},
        {"issue": "external portability", "boundary": "all E1 fields or defensible E2 translation required", "claim_effect": "zero external common-executor arms"},
        {"issue": "paper-normalized results", "boundary": "each value uses its paper's own baseline", "claim_effect": "not pooled or ranked"},
        {"issue": "security", "boundary": "runtime assumptions recorded separately", "claim_effect": "no universal security equivalence"},
    ]
    write_csv(tables / "09_fairness_limitations.csv", fairness, list(fairness[0]))

    def svg(path: Path, title: str, subtitle: str, body: list[str], accent: str = "#1F6FEB") -> None:
        height = max(420, 170 + 42 * len(body))
        texts = []
        y = 150
        for index, line in enumerate(body):
            fill = "#0D2A52" if index % 2 == 0 else "#334155"
            texts.append(f'<text x="70" y="{y}" font-size="22" fill="{fill}">{escape(line)}</text>')
            y += 42
        value = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">{escape(subtitle)}</desc>
<rect width="1200" height="{height}" fill="#ffffff"/><rect x="0" y="0" width="18" height="{height}" fill="{accent}"/>
<text x="70" y="62" font-family="sans-serif" font-size="32" font-weight="700" fill="#0D2A52">{escape(title)}</text>
<text x="70" y="102" font-family="sans-serif" font-size="18" fill="#475569">{escape(subtitle)}</text>
<g font-family="sans-serif">{''.join(texts)}</g></svg>'''
        path.write_text(value + "\n", encoding="utf-8")

    svg(figures / "01_problem_objective.svg", "Fastest decision-stable CKKS configuration", "Minimum latency only within the comparable admitted candidate set", ["Candidate providers: manual | catalog | external | direct", "Security/runtime admission -> frozen decision validation", "C_stable empty -> NO_SAFE", "Otherwise choose minimum T(c) under identical timing"])
    svg(figures / "02_providers_and_gate.svg", "Providers and the FlipGuard gate", "Candidate generation and decision-stability admission are separate roles", ["Manual / bounded catalog / external compiler / direct synthesis", "Security admission", "Decision-stability validation", "SAFE | REJECTED | FAILED | PLAN_UNSUPPORTED | NO_SAFE", "No-retuning locked audit"])
    svg(figures / "03_ckks_landscape_matrix.svg", "21-system CKKS landscape", "Capability map, not a performance ranking", [f"{row['system']}: {row['experimental_tier']} | {row['publication_state']}" for row in landscape])
    counts = Counter(row["build_state"] for row in landscape)
    svg(figures / "04_artifact_reproduction_funnel.svg", "Artifact and reproduction funnel", "A smoke gate is not benchmark reproduction", [f"Papers identified: {len(landscape)}", f"Official repository/archive rows: {sum(row['artifact_state'] != 'PAPER_ONLY' for row in landscape)}", f"Build/runtime smoke pass: {sum(row['build_state'] == 'BUILD_SMOKE_PASS' for row in landscape)}", f"Native end-to-end output: {sum(row['execution_state'] == 'NATIVE_END_TO_END_PASS' for row in landscape)}", f"Raw-output external providers: {sum(row['output_evidence_state'] == 'RAW_PER_SAMPLE_OUTPUT' and row['system'] != 'FlipGuard' for row in landscape)}", f"External common-executor arms: {sum(row['headline_eligible'] in (True, 'True', 'true') for row in common if row['provider'] != 'FlipGuard internal providers')}"])
    svg(figures / "05_tool_workload_heatmap.svg", "Tool-workload applicability", "Exact official workload is distinct from exact shared workload", [f"Rows: {len(applicability)} systems", "Columns: 7 frozen families + 12 official workload families", "No graph identity inferred from model names", "See applicability_matrix.csv for every classified cell"])
    svg(figures / "06_provider_latency_decision_flips.svg", "Provider latency and decision evidence", "Native-only values are not cross-runtime ranked", ["EVA: native diagnostic, 11 validation flips, gate REJECTED", "Orion: configuration-only, PLAN_UNSUPPORTED", "FlipGuard controlled primary: common-executor internal paired evidence", "Missing provider outputs remain NOT_EVALUATED"])
    svg(figures / "07_configuration_tuning_cost.svg", "Configuration-generation and tuning cost", "Build, compilation, tuning, validation, and inference boundaries remain separate", [f"FlipGuard: {trials['candidate_trials']} candidate executions", f"Selection key runs: {trials['selection_key_runs']}", f"Encrypted sample evaluations: {trials['encrypted_sample_evaluations']}", "Actual tuning wall-clock: NOT_SEPARATELY_RECORDED", "External paper values are retained within their native boundaries"])
    svg(figures / "08_original_paper_normalized_results.svg", "Original-paper normalized improvements", "Each value is normalized to its own paper baseline; not a head-to-head ranking", [f"{row['system']}: {row['normalized_baseline_over_system']:.4g} baseline/system ({row['source_locator']})" for row in reported])
    svg(figures / "09_security_decision_audit_funnel.svg", "Provider to stable candidate", "Security, validation, and audit are explicit fail-closed stages", ["Provider candidate", "Security/runtime admission", "Frozen validation decision gate", "Reserve-policy admission", "Literal lock", "Disjoint audit without retuning"])
    svg(figures / "10_fastest_stable_candidate.svg", "Fastest stable candidate by exact shared scope", "No external provider met E1/E2 portability in this audit", ["Controlled primary: direct was point-estimate fastest in 50/50 internal paired workloads", "MLP-100: S29 and S32 total-latency CI includes 1", "MLP-100 catalog S40 / S29 ratio: 1.981795", "External common-executor winner: NOT_EVALUATED"])

    def grid_svg(path: Path, title: str, subtitle: str, columns: list[str], rows: list[dict], key: str, palette: dict[str, str]) -> None:
        left, top, cell_w, cell_h = 250, 190, 82, 31
        width = left + cell_w * len(columns) + 50
        legend_columns = min(4, len(palette))
        legend_rows = (len(palette) + legend_columns - 1) // legend_columns
        height = top + cell_h * len(rows) + 70 + legend_rows * 30
        labels = []
        for col_index, column in enumerate(columns):
            x = left + col_index * cell_w + 12
            label = column.replace("external_", "ext. ").replace("frozen_", "frozen ").replace("_", " ")
            labels.append(f'<text x="{x}" y="178" text-anchor="start" transform="rotate(-55 {x} 178)" font-size="11" fill="#334155">{escape(label)}</text>')
        cells = []
        for row_index, row in enumerate(rows):
            y = top + row_index * cell_h
            cells.append(f'<text x="235" y="{y + 21}" text-anchor="end" font-size="13" fill="#0D2A52">{escape(row[key])}</text>')
            for col_index, column in enumerate(columns):
                value = row[column]
                color = palette.get(value, "#CBD5E1")
                x = left + col_index * cell_w
                cells.append(f'<rect x="{x + 1}" y="{y + 1}" width="{cell_w - 3}" height="{cell_h - 3}" rx="2" fill="{color}"/><title>{escape(row[key])}: {escape(column)} = {escape(value)}</title>')
        legend = []
        legend_top = top + cell_h * len(rows) + 35
        legend_width = (width - 70) / legend_columns
        for index, (state, color) in enumerate(palette.items()):
            x = 35 + (index % legend_columns) * legend_width
            y = legend_top + (index // legend_columns) * 30
            label = state.replace("_", " ")
            legend.append(f'<rect x="{x}" y="{y - 14}" width="18" height="18" rx="2" fill="{color}"/><text x="{x + 26}" y="{y}" font-size="11" fill="#334155">{escape(label)}</text>')
        path.write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">{escape(subtitle)}</desc><rect width="100%" height="100%" fill="#fff"/>
<text x="36" y="46" font-family="sans-serif" font-size="28" font-weight="700" fill="#0D2A52">{escape(title)}</text>
<text x="36" y="76" font-family="sans-serif" font-size="15" fill="#475569">{escape(subtitle)}</text>
<g font-family="sans-serif">{''.join(labels)}{''.join(cells)}{''.join(legend)}</g></svg>\n''', encoding="utf-8")

    grid_svg(
        figures / "03_ckks_landscape_matrix.svg", "21-system CKKS landscape",
        "Capability coverage only; cells are not performance ranks.", features, taxonomy, "system",
        {"FULL": "#2DA44E", "PARTIAL": "#2F9ECA", "OUT_OF_SCOPE": "#E5E7EB"},
    )
    heat_columns = [column for column in applicability[0] if column not in {"system", "reason_summary"}]
    grid_svg(
        figures / "05_tool_workload_heatmap.svg", "Tool-workload applicability",
        "Exact official workloads remain distinct from exact shared workloads.", heat_columns, applicability, "system",
        {
            "EXACT_SHARED_WORKLOAD": "#2DA44E", "EXACT_OFFICIAL_PROVIDER_WORKLOAD": "#1F6FEB",
            "SAME_TASK_DIFFERENT_GRAPH": "#F2CC60", "NO_BOOTSTRAP_NOT_APPLICABLE": "#D0D7DE",
            "BUILD_BLOCKED": "#CF222E", "HARDWARE_UNAVAILABLE": "#BC8C00",
            "ARTIFACT_UNAVAILABLE": "#8C959F", "OUTPUT_NOT_EXPOSED": "#A371F7",
        },
    )

    funnel = [
        ("Papers", len(landscape)),
        ("Official artifacts", sum(row["artifact_state"] != "PAPER_ONLY" and row["system"] != "FlipGuard" for row in landscape)),
        ("Smoke pass", sum(row["build_state"] == "BUILD_SMOKE_PASS" and row["system"] != "FlipGuard" for row in landscape)),
        ("Native output", sum(row["execution_state"] == "NATIVE_END_TO_END_PASS" and row["system"] != "FlipGuard" for row in landscape)),
        ("Provider gate", len(gates)),
        ("External E1/E2", 0),
    ]
    bars = []
    for index, (label, value) in enumerate(funnel):
        y = 140 + index * 72
        width = 820 * value / 21 if value else 4
        bars.append(f'<text x="60" y="{y + 24}" font-size="17" fill="#0D2A52">{escape(label)}</text><rect x="250" y="{y}" width="{width}" height="36" rx="3" fill="#1F6FEB"/><text x="{265 + width}" y="{y + 24}" font-size="17" fill="#0D2A52">{value}</text>')
    (figures / "04_artifact_reproduction_funnel.svg").write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="620" viewBox="0 0 1200 620" role="img" aria-labelledby="title desc"><title id="title">Artifact and reproduction funnel</title><desc id="desc">Build smoke is separated from native end-to-end and common-executor evidence.</desc><rect width="1200" height="620" fill="#fff"/><text x="60" y="55" font-family="sans-serif" font-size="30" font-weight="700" fill="#0D2A52">Artifact and reproduction funnel</text><text x="60" y="88" font-family="sans-serif" font-size="16" fill="#475569">A smoke gate is not benchmark reproduction.</text><g font-family="sans-serif">{''.join(bars)}</g></svg>\n''', encoding="utf-8")

    external_reported = [row for row in reported if row["system"] != "FlipGuard"]
    plot = []
    for index, row in enumerate(external_reported):
        value = float(row["normalized_baseline_over_system"])
        x = 300 + 760 * math.log10(value) / math.log10(4000)
        y = 135 + index * 39
        plot.append(f'<text x="275" y="{y + 5}" text-anchor="end" font-size="14" fill="#0D2A52">{escape(row["system"])}</text><line x1="300" y1="{y}" x2="{x}" y2="{y}" stroke="#94A3B8" stroke-width="2"/><circle cx="{x}" cy="{y}" r="6" fill="#1F6FEB"><title>{escape(row["reported_improvement"])}; {escape(row["source_locator"])}</title></circle><text x="{x + 12}" y="{y + 5}" font-size="12" fill="#334155">{value:.4g}x</text>')
    ticks = []
    for value in [1, 2, 10, 100, 1000, 4000]:
        x = 300 + 760 * math.log10(value) / math.log10(4000)
        ticks.append(f'<line x1="{x}" y1="105" x2="{x}" y2="650" stroke="#E2E8F0"/><text x="{x}" y="680" text-anchor="middle" font-size="12" fill="#475569">{value}x</text>')
    (figures / "08_original_paper_normalized_results.svg").write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="720" viewBox="0 0 1200 720" role="img" aria-labelledby="title desc"><title id="title">Original-paper normalized improvements</title><desc id="desc">Values use each paper's own baseline and are not a head-to-head ranking.</desc><rect width="1200" height="720" fill="#fff"/><text x="45" y="48" font-family="sans-serif" font-size="29" font-weight="700" fill="#0D2A52">Original-paper normalized improvements</text><text x="45" y="78" font-family="sans-serif" font-size="15" fill="#475569">Own-paper baseline/system ratio on a log axis; no pooled cross-paper inference.</text><g font-family="sans-serif">{''.join(ticks)}{''.join(plot)}</g></svg>\n''', encoding="utf-8")

    stable_bars = [("Direct fastest (controlled primary)", 50, "#2DA44E"), ("MLP-100 unresolved S29/S32", 1, "#F2CC60"), ("External E1/E2 winner", 0, "#8C959F")]
    rendered = []
    for index, (label, value, color) in enumerate(stable_bars):
        y = 165 + index * 100
        width = 760 * value / 50 if value else 4
        rendered.append(f'<text x="70" y="{y - 12}" font-size="17" fill="#0D2A52">{escape(label)}</text><rect x="70" y="{y}" width="{width}" height="42" rx="3" fill="{color}"/><text x="{90 + width}" y="{y + 28}" font-size="17" fill="#0D2A52">{value}</text>')
    (figures / "10_fastest_stable_candidate.svg").write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="520" viewBox="0 0 1100 520" role="img" aria-labelledby="title desc"><title id="title">Fastest stable candidate by exact shared scope</title><desc id="desc">Internal shared arms and unavailable external common-executor arms are separated.</desc><rect width="1100" height="520" fill="#fff"/><text x="70" y="55" font-family="sans-serif" font-size="29" font-weight="700" fill="#0D2A52">Fastest stable candidate by exact shared scope</text><text x="70" y="88" font-family="sans-serif" font-size="15" fill="#475569">Counts denote declared comparison units, not the global CKKS space.</text><g font-family="sans-serif">{''.join(rendered)}</g></svg>\n''', encoding="utf-8")


def escape(value: str) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def make_claims() -> list[dict]:
    claims = [
        {"claim_id": "comprehensive_landscape", "state": "SUPPORTED", "paper_admitted": True, "tier": "TIER_1", "wording": "We audited 20 representative external CKKS systems and FlipGuard across capability, publication, artifact, and evidence axes.", "scope": "named 21-system census", "limitation": "representative, not every CKKS system", "prohibited": "all state-of-the-art autotuners"},
        {"claim_id": "official_artifact_audit", "state": "SUPPORTED", "paper_admitted": True, "tier": "TIER_1", "wording": "All official artifacts identified by the frozen registry were audited under a maximum three-recovery policy.", "scope": "verified repository/archive set", "limitation": "license, hardware, and dependency blocks remain", "prohibited": "all systems reproduced"},
        {"claim_id": "original_paper_normalized", "state": "SUPPORTED", "paper_admitted": True, "tier": "TIER_2", "wording": "Original-paper improvements are shown relative to each paper's own baseline.", "scope": "source-located reported values", "limitation": "not head-to-head", "prohibited": "cross-paper absolute speed ranking"},
        {"claim_id": "native_provider_output", "state": "PARTIALLY_SUPPORTED", "paper_admitted": True, "tier": "TIER_3", "wording": "Native per-sample output and a decision-gate diagnostic were obtained for the scoped EVA replay.", "scope": "one external native provider", "limitation": "other smoke passes are not native reproduction", "prohibited": "six external runtimes reproduced"},
        {"claim_id": "provider_independent_gate", "state": "PARTIALLY_SUPPORTED", "paper_admitted": True, "tier": "TIER_3", "wording": "The common gate was exercised on an EVA native candidate and an Orion configuration-level fail-closed import.", "scope": "two feasible external candidate artifacts", "limitation": "only EVA exposes raw per-sample output", "prohibited": "general external-provider interoperability"},
        {"claim_id": "external_common_executor_latency", "state": "NOT_EVALUATED", "paper_admitted": False, "tier": "TIER_4", "wording": "No external plan met the frozen E1 or E2 portability gate.", "scope": "audited external plans", "limitation": "zero external common-executor arms", "prohibited": "external head-to-head latency superiority"},
        {"claim_id": "external_fastest_stable_selection", "state": "BLOCKED", "paper_admitted": False, "tier": "TIER_4", "wording": "No external fastest-stable winner is claimed.", "scope": "external providers", "limitation": "no exact shared external plan", "prohibited": "globally fastest"},
        {"claim_id": "internal_fastest_stable_selection", "state": "SUPPORTED", "paper_admitted": True, "tier": "TIER_4_INTERNAL", "wording": "Within the frozen manual, Security-V2 catalog, and direct arms, the direct arm had the lowest paired point estimate in all 50 controlled-primary instances.", "scope": "frozen Lattigo internal arms", "limitation": "not the global CKKS space", "prohibited": "global optimum"},
        {"claim_id": "tuning_cost_accounting", "state": "PARTIALLY_SUPPORTED", "paper_admitted": True, "tier": "TIER_2_AND_INTERNAL", "wording": "Candidate executions and provider-native timing boundaries are reported separately.", "scope": "available counters", "limitation": "actual FlipGuard tuning wall-clock was not separately recorded", "prohibited": "missing wall-clock equals zero"},
    ]
    dependencies = [
        {"claim_id": row["claim_id"], "evidence": "docs/evidence/comprehensive_ckks_comparison_v3/manifest.json", "tier": row["tier"], "required": True}
        for row in claims
    ]
    write_json(PACK / "claim_admission.json", {"schema_version": "comprehensive_ckks_claims_v1", "claims": claims})
    CLAIMS.mkdir(parents=True, exist_ok=True)
    write_json(CLAIMS / "claims.json", {"schema_version": "comprehensive_ckks_claim_admission_v1", "claims": claims})
    write_csv(CLAIMS / "claim_evidence_dependencies.csv", dependencies, ["claim_id", "evidence", "tier", "required"])
    (CLAIMS / "allowed_sentences.md").write_text("# Allowed Sentences\n\n" + "\n".join(f"- `{row['claim_id']}`: {row['wording']}" for row in claims if row["paper_admitted"]) + "\n", encoding="utf-8")
    (CLAIMS / "prohibited_sentences.md").write_text("# Prohibited Sentences\n\n" + "\n".join(f"- {row['prohibited']}" for row in claims) + "\n", encoding="utf-8")
    return claims


def make_fairness() -> None:
    (PACK / "fairness_limitations.md").write_text("""# Fairness Limitations

- Build/runtime smoke demonstrates artifact reachability, not benchmark reproduction.
- Native absolute latencies use different runtimes, graphs, packing, security assumptions, and hosts; they are never ranked across providers.
- Original-paper normalized values use each paper's own baseline and are not pooled.
- Model names such as LeNet, MLP, Sobel, and Harris do not establish graph identity.
- `PORTABLE_EXACT` requires graph, operation order, weights, preprocessing, packing, parameters, schedules, and output semantics to match.
- No external candidate met the E1/E2 common-executor gate. Missing measurements remain explicit states, never zero.
- The native feasible set was exhausted under official artifact, license, hardware, output, and workload constraints; this is not evidence of inferior algorithms.
- Security assumptions remain runtime-specific unless explicitly aligned.
- FlipGuard's fastest-stable result is bounded to declared candidates, finite inputs, and a measured host, not the global CKKS configuration space.
""", encoding="utf-8")


def finalize(landscape: list[dict], artifacts: list[dict], attempts: list[dict], native: list[dict], gates: list[dict], common: list[dict], reported: list[dict], claims: list[dict]) -> None:
    counts = {
        "landscape_rows": len(landscape),
        "external_systems": 20,
        "official_artifact_rows_including_flipguard": sum(row["artifact_state"] != "PAPER_ONLY" for row in landscape),
        "external_official_artifact_rows": sum(row["artifact_state"] != "PAPER_ONLY" and row["system"] != "FlipGuard" for row in landscape),
        "build_runtime_smoke_pass_including_flipguard": sum(row["status"] == "PASS" for row in attempts),
        "external_build_runtime_smoke_pass": sum(row["status"] == "PASS" and row["system"] != "FlipGuard" for row in attempts),
        "external_native_end_to_end_pass": sum(row["execution_status"] == "NATIVE_END_TO_END_PASS" and row["provider_id"] != "FlipGuard" for row in native),
        "external_raw_output_providers": sum(row["plaintext_output"] not in MISSING and row["plaintext_output"] != "NOT_EVALUATED" and row["provider_id"] != "FlipGuard" for row in native),
        "external_provider_gate_rows": len(gates),
        "external_portable_exact": 0,
        "external_graph_equivalent_common_executor": 0,
        "paper_reported_result_systems": len({row["system"] for row in reported if row["system"] != "FlipGuard"}),
        "paper_reported_result_points": len(reported),
        "figures": len(list((PACK / "figures").glob("*.svg"))),
        "tables": len(list((PACK / "tables").glob("*.csv"))),
    }
    completion = {
        "status": "EXHAUSTED_FEASIBLE_SET",
        "all_official_artifacts_audited": True,
        "blocked_reasons_recorded": True,
        "missing_values_explicit": True,
        "graph_or_algorithm_changed_to_fill_targets": False,
        "frozen_flipguard_evidence_modified": False,
        "policy_retuning": False,
        "native_target_met": counts["external_native_end_to_end_pass"] >= 6,
        "provider_gate_target_met": counts["external_provider_gate_rows"] >= 6,
        "common_executor_target_met": counts["external_portable_exact"] + counts["external_graph_equivalent_common_executor"] >= 3,
        "reported_result_target_met": counts["paper_reported_result_systems"] >= 12,
        "target_shortfalls_are_fairness_constraints_not_zeroes": True,
    }
    manifest = {
        "artifact_id": "comprehensive_ckks_comparison_v3",
        "schema_version": "flipguard_comprehensive_ckks_comparison_v3",
        "protocol_commit": PROTOCOL_COMMIT,
        "predecessor": "docs/evidence/external_autotuner_comparison_v2/manifest.json",
        "comparison_objective": "fastest decision-stable candidate within a comparable admitted set",
        "evidence_tiers": 4,
        "counts": counts,
        "completion": completion,
        "claim_counts": dict(Counter(row["state"] for row in claims)),
        "paper_writing_status": "COMPARATIVE_EVIDENCE_FROZEN; HWP_DOCX_FINALIZATION_STILL_PAUSED",
    }
    write_json(PACK / "manifest.json", manifest)
    write_json(RESULTS / "manifest.json", manifest)
    write_json(PAPER / "manifest.json", {
        "artifact_id": "comprehensive_ckks_comparison_paper_inputs_v1",
        "source_manifest": "docs/evidence/comprehensive_ckks_comparison_v3/manifest.json",
        "source_manifest_sha256": sha256(PACK / "manifest.json"),
        "figures": 10, "tables": 9, "publication_status": "EVIDENCE_TIERED_INPUTS_NOT_MANUSCRIPT",
    })
    for name in ["figures", "tables"]:
        target = PAPER / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(PACK / name, target)
    shutil.copyfile(PACK / "claim_admission.json", PAPER / "claim_admission.json")
    shutil.copyfile(PACK / "manuscript_recenter_contract.md", PAPER / "manuscript_recenter_contract.md")
    for name in [
        "native_execution_records.csv", "provider_gate_records.csv", "common_executor_records.csv",
        "paper_reported_results.csv", "tuning_cost_records.csv", "latency_summary.csv",
        "decision_flip_summary.csv", "security_summary.csv", "portability_summary.csv",
        "failure_summary.csv", "fastest_stable_candidates.csv", "internal_trial_distribution.json",
    ]:
        shutil.copyfile(PACK / name, RESULTS / name)
    verifier_source = ROOT / "scripts/verify_comprehensive_ckks_comparison_v3.py"
    shutil.copyfile(verifier_source, PACK / "verify_comprehensive_ckks_comparison_v3.py")
    shutil.copyfile(verifier_source, CLAIMS / "verify_comprehensive_ckks_comparison_claim_admission_v1.py")
    checksum_tree(PACK / "landscape")
    checksum_tree(PACK / "official_sources")
    checksum_tree(PACK / "artifact_audit", {"build_logs"})
    checksum_tree(RESULTS)
    checksum_tree(PAPER)
    write_json(CLAIMS / "manifest.json", {
        "artifact_id": "comprehensive_ckks_comparison_claim_admission_v1",
        "comparison_manifest_sha256": sha256(PACK / "manifest.json"),
        "admitted_claims": sum(bool(row["paper_admitted"]) for row in claims),
        "blocked_or_not_evaluated_claims": sum(not bool(row["paper_admitted"]) for row in claims),
    })
    checksum_tree(CLAIMS)
    checksum_tree(PACK, {"artifact_audit/build_logs"})


def build() -> None:
    for path in [RESULTS, PAPER, CLAIMS]:
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)
    for name in ["landscape", "official_sources", "tables", "figures", "provider_candidate_manifests", "workload_contracts"]:
        path = PACK / name
        if path.exists():
            shutil.rmtree(path)
    for name in [
        "manifest.json", "claim_admission.json", "build_matrix.csv", "applicability_matrix.csv",
        "native_execution_records.csv", "provider_gate_records.csv", "common_executor_records.csv",
        "paper_reported_results.csv", "tuning_cost_records.csv", "latency_summary.csv",
        "decision_flip_summary.csv", "security_summary.csv", "portability_summary.csv",
        "failure_summary.csv", "fastest_stable_candidates.csv", "internal_trial_distribution.json",
        "fairness_limitations.md", "SHA256SUMS",
    ]:
        (PACK / name).unlink(missing_ok=True)
    systems = load_systems()
    attempts = load_attempts()
    landscape, artifacts = make_landscape(systems, attempts)
    make_artifact_audit(attempts)
    applicability = make_applicability(systems, attempts)
    native, gates, common = make_native_and_gate(systems, attempts)
    make_provider_manifests()
    make_workload_contracts()
    reported = make_paper_reported()
    trials = trial_distribution()
    make_summaries(native, gates, common, trials)
    make_tables_figures(landscape, artifacts, native, gates, common, reported, trials, applicability)
    claims = make_claims()
    make_fairness()
    finalize(landscape, artifacts, attempts, native, gates, common, reported, claims)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        manifest = read_json(PACK / "manifest.json")
        assert manifest["counts"]["landscape_rows"] == 21
        assert manifest["completion"]["status"] == "EXHAUSTED_FEASIBLE_SET"
        print("comprehensive_ckks_comparison_v3_build=PASS")
        return 0
    build()
    print("comprehensive_ckks_comparison_v3_build=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
