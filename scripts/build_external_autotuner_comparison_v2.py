#!/usr/bin/env python3
"""Build the fail-closed CKKS landscape and external-baseline evidence pack."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "docs/evidence/external_autotuner_comparison_v2"
PROTOCOL = PACK / "protocol"
SOURCE_COMMIT = "fd53d9f23040fd1490d9816a928dd04ec58eb473"


def comparison_input_commit() -> str:
    value = os.environ.get("FLIPGUARD_COMPARISON_INPUT_COMMIT")
    if value is None:
        value = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert len(value) == 40 and all(char in "0123456789abcdef" for char in value)
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def git_blob(path: Path) -> str:
    rel = path.relative_to(ROOT)
    return subprocess.check_output(["git", "show", f"{SOURCE_COMMIT}:{rel}"], cwd=ROOT)


def verify_frozen_dependencies() -> None:
    for rel in [
        "docs/evidence/eva_native_runtime_replay_v1/summary.json",
        "docs/evidence/eva_schedule_bound_adapter_replay_v1/manifest.json",
        "docs/evidence/orion_external_adapter_audit_v1/manifest.json",
        "docs/evidence/journal_multiclass_extension_final_v1/manifest.json",
    ]:
        path = ROOT / rel
        assert path.read_bytes() == git_blob(path), f"frozen dependency changed: {rel}"


def landscape_rows() -> list[dict]:
    return read_json(PROTOCOL / "source_registry.json")["systems"]


def build_rows() -> list[dict]:
    return read_json(PROTOCOL / "build_attempts.json")["systems"]


def copy_contracts() -> None:
    target = PACK / "workload_contracts"
    target.mkdir(exist_ok=True)
    for source in sorted((PROTOCOL / "workload_contracts").glob("*.json")):
        shutil.copyfile(source, target / source.name)


def make_landscape(rows: list[dict]) -> None:
    registry = read_json(PROTOCOL / "source_registry.json")
    fields = [
        "system", "full_title", "authors", "venue", "year", "publication_status",
        "peer_reviewed", "official_paper", "official_repository", "artifact_revision",
        "license", "supported_scheme", "backend", "frontend_model_format",
        "optimization_target", "parameter_search_space", "scale_management",
        "bootstrapping", "packing_layout", "security_handling",
        "error_correctness_metric", "model_workload", "public_reproduction_status",
        "comparison_relevance", "experimental_inclusion_class", "exclusion_reason",
    ]
    write_csv(PACK / "landscape.csv", rows, fields)
    sources = {
        "schema_version": "flipguard_external_official_sources_v2",
        "audit_date": "2026-08-05",
        "source_commit": SOURCE_COMMIT,
        "downloaded_primary_source_sha256": registry["downloaded_primary_source_sha256"],
        "systems": [
            {
                "system": row["system"],
                "paper": row["official_paper"],
                "repository": row["official_repository"],
                "artifact_revision": row["artifact_revision"],
                "license": row["license"],
                "source_status": row["public_reproduction_status"],
            }
            for row in rows
        ],
    }
    write_json(PACK / "official_sources.json", sources)
    write_csv(
        PACK / "artifact_availability.csv",
        [
            {
                "system": row["system"],
                "official_repository": row["official_repository"],
                "artifact_revision": row["artifact_revision"],
                "license": row["license"],
                "availability": row["public_reproduction_status"],
                "inclusion_class": row["experimental_inclusion_class"],
                "reason": row["exclusion_reason"],
            }
            for row in rows
        ],
        ["system", "official_repository", "artifact_revision", "license", "availability", "inclusion_class", "reason"],
    )


def make_build_outputs(builds: list[dict]) -> None:
    fields = [
        "system", "set", "artifact_revision", "attempts", "status", "reproduced",
        "container_or_environment", "command_class", "last_error", "dependency",
        "official_environment_difference", "reason_code", "algorithm_semantics_changed",
        "log_sha256", "notes",
    ]
    write_csv(PACK / "build_matrix.csv", builds, fields)
    patch_rows = []
    failure_rows = []
    for row in builds:
        for patch in row.get("patches", []):
            patch_rows.append({"system": row["system"], **patch})
        if row["status"] != "PASS":
            failure_rows.append(
                {
                    "system": row["system"],
                    "stage": "BUILD_OR_REPRODUCTION",
                    "status": row["status"],
                    "reason_code": row["reason_code"],
                    "exact_error": row["last_error"],
                    "attempts": row["attempts"],
                    "scientific_effect": "excluded from reproduced baseline count; retained in landscape",
                }
            )
    write_csv(
        PACK / "patch_inventory.csv",
        patch_rows,
        ["system", "attempt", "kind", "description", "semantics_changed"],
    )
    write_csv(
        PACK / "failure_summary.csv",
        failure_rows,
        ["system", "stage", "status", "reason_code", "exact_error", "attempts", "scientific_effect"],
    )


def make_applicability() -> None:
    source = PROTOCOL / "tool_workload_applicability.csv"
    shutil.copyfile(source, PACK / "applicability_matrix.csv")


def eva_native_metrics() -> dict:
    ledger = PACK.parent / "eva_native_runtime_replay_v1/raw/validation_ledger.csv"
    with ledger.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    errors = [float(row["absolute_error"]) for row in rows]
    keygen_by_repeat = {}
    for row in rows:
        keygen_by_repeat.setdefault(row["key_repeat"], float(row["keygen_ms"]))
    return {
        "rms_error": math.sqrt(sum(value * value for value in errors) / len(errors)),
        "max_error": max(errors),
        "keygen_mean_ms": sum(keygen_by_repeat.values()) / len(keygen_by_repeat),
        "evaluation_mean_ms": sum(float(row["execute_ms"]) for row in rows) / len(rows),
        "total_sample_mean_ms": sum(float(row["total_sample_ms"]) for row in rows) / len(rows),
    }


def make_result_tables(builds: list[dict]) -> None:
    eva = read_json(ROOT / "docs/evidence/eva_native_runtime_replay_v1/summary.json")
    eva_metrics = eva_native_metrics()
    native = []
    for build in builds:
        row = {
            "provider": build["system"],
            "artifact_revision": build["artifact_revision"],
            "workload": "NO_EXACT_FROZEN_WORKLOAD_EXECUTION",
            "runtime": build["container_or_environment"],
            "objective": "OFFICIAL_ARTIFACT_BUILD_OR_AVAILABILITY_AUDIT",
            "build_status": build["status"],
            "compile_time": "NOT_SEPARATELY_RECORDED",
            "tuning_time": "NOT_EVALUATED",
            "plans_generated": "NOT_EVALUATED",
            "plans_executed": "NOT_EVALUATED",
            "selected_plan": "NOT_EVALUATED",
            "parameter_configuration": "NOT_EVALUATED",
            "key_generation": "NOT_EVALUATED",
            "evaluation_latency": "NOT_EVALUATED",
            "total_latency": "NOT_EVALUATED",
            "rms_error": "NOT_EVALUATED",
            "max_error": "NOT_EVALUATED",
            "output_values": "NOT_EVALUATED",
            "decision_flips": "NOT_EVALUATED",
            "security_state": "NOT_EVALUATED_NO_EXECUTED_CANDIDATE",
            "execution_failure": "NOT_RUN_NO_EXACT_WORKLOAD_MAPPING" if build["status"] == "PASS" else build["reason_code"],
            "latency_scope": "NOT_EVALUATED",
            "evidence": "docs/evidence/external_autotuner_comparison_v2/build_matrix.csv",
        }
        if build["system"] == "EVA":
            row.update(
                {
                    "workload": "seed0 development linear_poly3 native replay",
                    "runtime": "EVA v1.0.1 / Microsoft SEAL 3.6.4",
                    "objective": "CKKS vector compilation and parameter generation",
                    "compile_time": "NOT_SEPARATELY_RECORDED",
                    "tuning_time": "NOT_SEPARATELY_RECORDED",
                    "plans_generated": 1,
                    "plans_executed": 1,
                    "selected_plan": "native_v1.0.1_N16384_Q3x60_P60_scale20",
                    "parameter_configuration": "N=16384; Q=3x60 bits; P=60 bits; input scale=20 bits",
                    "key_generation": f"mean_ms={eva_metrics['keygen_mean_ms']:.9f}; key_runs={eva['accounting']['validation_key_runs']}",
                    "evaluation_latency": f"mean_execute_ms_per_sample={eva_metrics['evaluation_mean_ms']:.9f}",
                    "total_latency": f"mean_total_sample_ms={eva_metrics['total_sample_mean_ms']:.9f}",
                    "rms_error": f"{eva_metrics['rms_error']:.15g}",
                    "max_error": f"{eva_metrics['max_error']:.15g}",
                    "output_values": "docs/evidence/eva_native_runtime_replay_v1/raw/validation_ledger.csv",
                    "decision_flips": eva["validation"]["counts"]["decision_flips"],
                    "security_state": eva["security_interpretation"]["runtime_security_claim"],
                    "execution_failure": "NONE; FINAL_GATE_REJECTED",
                    "latency_scope": "NATIVE_ONLY_NOT_CROSS_RUNTIME_RANKED",
                    "evidence": "docs/evidence/eva_native_runtime_replay_v1/summary.json",
                }
            )
        native.append(row)
    native_fields = [
        "provider", "artifact_revision", "workload", "runtime", "objective",
        "build_status", "compile_time", "tuning_time", "plans_generated",
        "plans_executed", "selected_plan", "parameter_configuration",
        "key_generation", "evaluation_latency", "total_latency", "rms_error",
        "max_error", "output_values", "decision_flips", "security_state",
        "execution_failure", "latency_scope", "evidence",
    ]
    write_csv(
        PACK / "native_results.csv",
        native,
        native_fields,
    )
    common_fields = [
        "provider", "workload", "portability", "graph_identity", "operation_order_identity",
        "scale_schedule_identity", "rescale_modswitch_relinearization_identity", "logn_qp_identity",
        "packing_identity", "output_semantics_identity", "same_host_result", "headline_eligible", "reason",
    ]
    external_tools = [
        row for row in read_csv(PROTOCOL / "tool_workload_applicability.csv")
        if row["tool"] != "FlipGuard"
    ]
    build_by_name = {row["system"]: row for row in builds}
    common = []
    for tool in external_tools:
        name = tool["tool"]
        build = build_by_name[name]
        portability = "NATIVE_ONLY" if build["status"] == "PASS" else "REPRODUCTION_BLOCKED"
        common_row = {
            "provider": name,
            "workload": "Sobel; Harris; MLP-100; LeNet-5-small frozen contracts",
            "portability": portability,
            "graph_identity": "NOT_ESTABLISHED",
            "operation_order_identity": "NOT_ESTABLISHED",
            "scale_schedule_identity": "NOT_ESTABLISHED",
            "rescale_modswitch_relinearization_identity": "NOT_ESTABLISHED",
            "logn_qp_identity": "NOT_ESTABLISHED",
            "packing_identity": "NOT_ESTABLISHED",
            "output_semantics_identity": "NOT_ESTABLISHED",
            "same_host_result": "NOT_EVALUATED",
            "headline_eligible": "false",
            "reason": "No provider output satisfied every frozen PORTABLE_EXACT field",
        }
        if name == "EVA":
            common_row.update(
                {
                    "workload": "existing schedule-bound development replay plus four frozen contract audit",
                    "portability": "PORTABLE_PARAMETER_ONLY",
                    "graph_identity": "SEMANTIC_GRAPH_MISMATCH_FOR_FROZEN_CURRENT_WORKLOADS",
                    "scale_schedule_identity": "BOUND_FOR_EXISTING_DEVELOPMENT_REPLAY",
                    "rescale_modswitch_relinearization_identity": "PARTIAL",
                    "logn_qp_identity": "BOUND_FOR_EXISTING_DEVELOPMENT_REPLAY",
                    "packing_identity": "DIFFERENT_RUNTIME_REPRESENTATION",
                    "output_semantics_identity": "DEVELOPMENT_BINARY_SCORE_ONLY",
                    "reason": "Parameter materialization exists, but every PORTABLE_EXACT identity field is not satisfied",
                }
            )
        common.append(common_row)
    write_csv(PACK / "common_executor_results.csv", common, common_fields)
    gate = [
        {
            "provider": "EVA",
            "provider_objective": "vector compiler parameter generation",
            "workload": "seed0 development native replay",
            "selected_configuration": "N16384 Q=3x60 P=60 input-scale=20",
            "provider_only_result": "EXECUTION_PASS",
            "security_admission": "STATIC_PASS_RUNTIME_MODEL_NOT_EQUIVALENT",
            "validation_decision_flips": 11,
            "audit_decision_flips": "NOT_EVALUATED",
            "reserve_policy_status": "REJECTED",
            "final_flipguard_state": "REJECTED",
            "latency": "NATIVE_ONLY",
            "gate_overhead": "NOT_PAIRED",
            "evidence": "docs/evidence/eva_native_runtime_replay_v1/summary.json",
        },
        {
            "provider": "Orion",
            "provider_objective": "packed deep-learning compilation",
            "workload": "public configuration static audit",
            "selected_configuration": "three public configurations inspected",
            "provider_only_result": "PUBLIC_SOURCE_AVAILABLE",
            "security_admission": "NOT_ADMITTED",
            "validation_decision_flips": "NOT_EXECUTED",
            "audit_decision_flips": "NOT_EXECUTED",
            "reserve_policy_status": "NOT_EVALUATED",
            "final_flipguard_state": "PLAN_UNSUPPORTED",
            "latency": "NOT_EVALUATED",
            "gate_overhead": "STATIC_ONLY",
            "evidence": "docs/evidence/orion_external_adapter_audit_v1/manifest.json",
        },
    ]
    write_csv(
        PACK / "provider_gate_results.csv",
        gate,
        ["provider", "provider_objective", "workload", "selected_configuration", "provider_only_result", "security_admission", "validation_decision_flips", "audit_decision_flips", "reserve_policy_status", "final_flipguard_state", "latency", "gate_overhead", "evidence"],
    )
    write_csv(
        PACK / "decision_flip_summary.csv",
        [{"provider": row["provider"], "workload": row["workload"], "validation_flips": row["validation_decision_flips"], "audit_flips": row["audit_decision_flips"], "state": row["final_flipguard_state"]} for row in gate],
        ["provider", "workload", "validation_flips", "audit_flips", "state"],
    )
    write_csv(
        PACK / "tuning_cost_summary.csv",
        [
            {
                "provider": row["provider"],
                "workload": row["workload"],
                "plans_generated": row["plans_generated"],
                "plans_executed": row["plans_executed"],
                "tuning_wall_clock": row["tuning_time"],
                "comparison_scope": "NATIVE_ONLY" if row["provider"] == "EVA" else "NOT_EVALUATED",
            }
            for row in native
        ],
        ["provider", "workload", "plans_generated", "plans_executed", "tuning_wall_clock", "comparison_scope"],
    )
    write_csv(
        PACK / "latency_summary.csv",
        [
            {
                "provider": row["provider"],
                "workload": row["workload"],
                "native_latency": row["total_latency"],
                "common_executor_latency": "NOT_EVALUATED",
                "headline_eligible": "false",
                "reason": "no external PORTABLE_EXACT arm",
            }
            for row in native
        ],
        ["provider", "workload", "native_latency", "common_executor_latency", "headline_eligible", "reason"],
    )
    write_csv(
        PACK / "security_summary.csv",
        [
            {
                "provider": row["provider"],
                "candidate": "native_v1.0.1" if row["provider"] == "EVA" else ("public_configs" if row["provider"] == "Orion" else "NO_EXECUTED_CANDIDATE"),
                "static_policy": "PASS" if row["provider"] == "EVA" else ("FAIL_CLOSED" if row["provider"] == "Orion" else "NOT_EVALUATED"),
                "runtime_distribution_match": "false" if row["provider"] == "EVA" else "NOT_EVALUATED",
                "formal_security_state": row["security_state"] if row["provider"] == "EVA" else ("NOT_ADMITTED" if row["provider"] == "Orion" else "NOT_EVALUATED_NO_EXECUTED_CANDIDATE"),
                "headline_eligible": "false",
            }
            for row in native
        ],
        ["provider", "candidate", "static_policy", "runtime_distribution_match", "formal_security_state", "headline_eligible"],
    )


def svg(title: str, subtitle: str, items: list[str]) -> str:
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="680" viewBox="0 0 1200 680" role="img">',
        f'<title>{title}</title><desc>{subtitle}</desc>',
        '<rect width="1200" height="680" fill="#ffffff"/>',
        f'<text x="60" y="76" font-family="sans-serif" font-size="34" font-weight="700" fill="#0D2A52">{title}</text>',
        f'<text x="60" y="112" font-family="sans-serif" font-size="18" fill="#425466">{subtitle}</text>',
    ]
    for index, item in enumerate(items):
        y = 160 + index * 62
        lines.append(f'<rect x="60" y="{y}" width="1080" height="46" rx="6" fill="#eef5ff" stroke="#1f6feb"/>')
        lines.append(f'<text x="82" y="{y + 30}" font-family="sans-serif" font-size="18" fill="#0d2a52">{item}</text>')
    lines.append("</svg>\n")
    return "".join(lines)


def make_figures_and_tables(rows: list[dict], builds: list[dict]) -> None:
    figures = PACK / "figures"
    tables = PACK / "tables"
    figures.mkdir(exist_ok=True)
    tables.mkdir(exist_ok=True)
    figure_specs = {
        "01_ckks_research_landscape.svg": ("CKKS research landscape", "Twenty systems; objectives are not interchangeable", ["General compilers", "Scale management", "Bootstrap placement", "DNN adaptation", "Application-aware and agentic systems"]),
        "02_provider_plus_flipguard.svg": ("Provider plus FlipGuard", "Candidate generation and final decision admission are separate roles", ["Provider candidate", "Security admission", "Encrypted decision gate", "SAFE / REJECTED / FAILED / NO_SAFE", "No-retuning locked audit"]),
        "03_latency_decision_flip_plane.svg": ("Latency and decision outcomes", "Native timings are not ranked across runtimes", ["PORTABLE_EXACT: eligible", "NATIVE_ONLY: descriptive", "Provider execution pass can still be REJECTED", "Missing exact mapping remains not evaluated"]),
        "04_tuning_cost_by_provider.svg": ("Tuning cost accounting", "Plans generated and executed are reported separately", ["Compiler pass", "Search candidates", "Encrypted executions", "Key runs", "Wall-clock boundary"]),
        "05_stable_candidate_latency.svg": ("Stable-candidate latency", "Only SAFE-to-SAFE PORTABLE_EXACT arms enter a headline", ["No external arm met every exact-portability condition", "Existing FlipGuard bounded-catalog comparison remains separate", "No raw cross-runtime superiority claim"]),
        "06_applicability_portability_matrix.svg": ("Applicability and portability", "A buildable artifact is not automatically a fair baseline", ["EXACT_NATIVE", "SEMANTICALLY_MAPPABLE", "PLAN_UNSUPPORTED", "NOT_APPLICABLE_NO_BOOTSTRAP", "ARTIFACT_UNAVAILABLE or BUILD_BLOCKED"]),
    }
    for name, spec in figure_specs.items():
        (figures / name).write_text(svg(*spec), encoding="utf-8")
    shutil.copyfile(PACK / "landscape.csv", tables / "01_tool_taxonomy.csv")
    shutil.copyfile(PACK / "build_matrix.csv", tables / "02_artifact_build_status.csv")
    shutil.copyfile(PACK / "applicability_matrix.csv", tables / "03_common_workload_equivalence.csv")
    shutil.copyfile(PACK / "native_results.csv", tables / "04_native_provider_results.csv")
    shutil.copyfile(PACK / "provider_gate_results.csv", tables / "05_provider_flipguard_gate.csv")
    shutil.copyfile(PACK / "common_executor_results.csv", tables / "06_common_executor_results.csv")
    fairness = [
        {"limitation": "No external PORTABLE_EXACT arm", "effect": "No external common-executor latency headline"},
        {"limitation": "Native runtimes and security distributions differ", "effect": "Native latency is descriptive only"},
        {"limitation": "Current four workloads do not need bootstrapping", "effect": "Bootstrap managers are not performance baselines"},
        {"limitation": "Some official artifacts require GPU or hundreds of GB of memory", "effect": "Build or full reproduction is blocked on the audit host"},
        {"limitation": "Missing public artifact or license", "effect": "Related-work-only classification"},
    ]
    write_csv(tables / "07_fairness_limitations.csv", fairness, ["limitation", "effect"])


def make_claims(rows: list[dict], builds: list[dict]) -> dict:
    reproduced = sum(row["reproduced"] is True for row in builds)
    reproduction_blocked = sum(row["status"] == "REPRODUCTION_BLOCKED" for row in builds)
    required_passed = sum(row["set"] == "REQUIRED_REPRODUCTION" and row["status"] == "PASS" for row in builds)
    required_blocked = sum(row["set"] == "REQUIRED_REPRODUCTION" and row["status"] != "PASS" for row in builds)
    attempted = sum(int(row["attempts"]) > 0 for row in builds)
    exact_external = 0
    claims = {
        "schema_version": "flipguard_external_baseline_claim_admission_v2",
        "paper_claim_allowed": True,
        "claims": [
            {
                "claim_id": "landscape_breadth",
                "state": "SUPPORTED",
                "paper_admitted": True,
                "allowed_wording": "We audited 20 representative CKKS compiler and configuration systems using primary publication and official artifact sources.",
                "limitation": "The census is not every CKKS system and is current only to the audit date.",
            },
            {
                "claim_id": "artifact_reproduction",
                "state": "PARTIALLY_SUPPORTED" if reproduced else "BLOCKED",
                "paper_admitted": reproduced > 0,
                "allowed_wording": f"Official build or runtime smoke reproduction passed for {reproduced} audited systems; blocked systems and exact errors are reported.",
                "limitation": "A build smoke is not exact workload equivalence or a performance comparison.",
            },
            {
                "claim_id": "external_common_executor_latency",
                "state": "NOT_EVALUATED",
                "paper_admitted": False,
                "allowed_wording": "No external plan satisfied every PORTABLE_EXACT condition on the frozen workloads.",
                "limitation": "Cross-runtime native timing must not be used as a substitute.",
            },
            {
                "claim_id": "provider_decision_gate",
                "state": "PARTIALLY_SUPPORTED",
                "paper_admitted": True,
                "allowed_wording": "The same fail-closed gate rejected an executable EVA native candidate and blocked semantically incomplete Orion configurations in scoped audits.",
                "limitation": "This does not establish general external-provider interoperability.",
            },
            {
                "claim_id": "bootstrap_comparison",
                "state": "NOT_APPLICABLE",
                "paper_admitted": True,
                "allowed_wording": "Bootstrap-placement systems were audited but were not performance baselines because none of the four frozen workloads required bootstrapping.",
                "limitation": "No deeper workload was manufactured after observing applicability.",
            },
        ],
        "counts": {
            "landscape_systems": len(rows),
            "reproduced_systems": reproduced,
            "attempted_systems": attempted,
            "reproduction_blocked_systems": reproduction_blocked,
            "required_reproduction_passed": required_passed,
            "required_reproduction_blocked": required_blocked,
            "native_end_to_end_systems": 1,
            "external_exact_workload_mappings": 0,
            "provider_gate_systems": 2,
            "external_portable_exact_arms": exact_external,
        },
        "main_paper_baseline_set": [
            {"baseline": "Default", "scope": "existing controlled-primary evidence", "status": "ADMITTED_EXISTING_CORE"},
            {"baseline": "Latency-only", "scope": "existing controlled-primary ablation", "status": "ADMITTED_EXISTING_CORE"},
            {"baseline": "Security-V2 bounded catalog", "scope": "existing controlled-primary evidence", "status": "ADMITTED_EXISTING_CORE"},
            {"baseline": "FlipGuard direct", "scope": "existing controlled-primary evidence", "status": "ADMITTED_EXISTING_CORE"},
            {"baseline": "EVA", "scope": "native replay plus scoped FlipGuard gate; no cross-runtime latency ranking", "status": "SCOPED_PROVIDER_GATE_ONLY"},
        ],
        "prohibited": [
            "all state-of-the-art CKKS autotuners",
            "comprehensive comparison of every CKKS compiler",
            "global fastest configuration",
            "universal superiority",
            "cross-runtime raw latency superiority",
        ],
    }
    write_json(PACK / "claim_admission.json", claims)
    return claims


def make_provider_manifests() -> None:
    target = PACK / "provider_manifests"
    target.mkdir(exist_ok=True)
    for provider, evidence, portability in [
        ("eva", "docs/evidence/eva_native_runtime_replay_v1/manifest.json", "NATIVE_ONLY"),
        ("orion", "docs/evidence/orion_external_adapter_audit_v1/manifest.json", "NATIVE_ONLY_STATIC_AUDIT"),
    ]:
        source = ROOT / evidence
        write_json(
            target / f"{provider}.json",
            {
                "provider": provider.upper(),
                "source_evidence": evidence,
                "source_evidence_sha256": f"sha256:{sha256(source)}",
                "portability": portability,
                "portable_exact": False,
                "policy_retuning": 0,
            },
        )


def make_manifest(claims: dict) -> None:
    manifest = {
        "artifact_id": "external_autotuner_comparison_v2",
        "schema_version": "flipguard_external_autotuner_comparison_v2",
        "source_commit": SOURCE_COMMIT,
        "comparison_input_commit": comparison_input_commit(),
        "protocol_commit": "11d6689c683006b6f80d77aaf8f05bd563525748",
        "audit_date": "2026-08-05",
        "current_flipguard_evidence_modified": False,
        "policy_retuning": 0,
        "new_model_or_dataset": 0,
        "landscape_systems": claims["counts"]["landscape_systems"],
        "reproduced_systems": claims["counts"]["reproduced_systems"],
        "attempted_systems": claims["counts"]["attempted_systems"],
        "reproduction_blocked_systems": claims["counts"]["reproduction_blocked_systems"],
        "required_reproduction_passed": claims["counts"]["required_reproduction_passed"],
        "required_reproduction_blocked": claims["counts"]["required_reproduction_blocked"],
        "external_portable_exact_arms": claims["counts"]["external_portable_exact_arms"],
        "native_latency_cross_runtime_ranked": False,
        "bootstrap_workload_manufactured": False,
        "publication_status": "FINAL_FAIR_BASELINE_EVIDENCE",
    }
    write_json(PACK / "manifest.json", manifest)


def make_checksums() -> None:
    excluded = {"SHA256SUMS"}
    files = [path for path in sorted(PACK.rglob("*")) if path.is_file() and path.name not in excluded and "__pycache__" not in path.parts]
    lines = [f"{sha256(path)}  {path.relative_to(PACK)}" for path in files]
    (PACK / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    verify_frozen_dependencies()
    if args.verify_only:
        subprocess.run(["python3", str(PACK / "verify_external_autotuner_comparison_v2.py")], check=True, cwd=ROOT)
        return 0
    rows = landscape_rows()
    builds = build_rows()
    assert len(rows) == 20
    assert {row["system"] for row in rows} == {row["system"] for row in builds}
    make_landscape(rows)
    make_build_outputs(builds)
    make_applicability()
    copy_contracts()
    make_result_tables(builds)
    make_provider_manifests()
    make_figures_and_tables(rows, builds)
    claims = make_claims(rows, builds)
    make_manifest(claims)
    make_checksums()
    print(f"external_autotuner_comparison_v2=BUILT systems={len(rows)} reproduced={claims['counts']['reproduced_systems']} portable_exact=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
