#!/usr/bin/env python3
"""Build the final V9 baseline, claim, and publication-input overlays."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "docs/evidence/final_realistic_baseline_closure_v9"
RESULTS = ROOT / "results/thesis_grade_protocol/final_realistic_baseline_closure_v9"
V8 = ROOT / "docs/evidence/focused_external_comparison_v8"
V8_RESULTS = ROOT / "results/thesis_grade_protocol/focused_external_comparison_v8"
BASE_COMMIT = "cd2662cc38508ff858b188b3f2f7141dff882e43"
FREEZE_TIMESTAMP = "2026-08-08T21:10:20+09:00"


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix == ".csv":
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        shutil.copyfile(source, destination)


def environment() -> dict[str, object]:
    frozen = PACK / "environment.json"
    if frozen.is_file():
        payload = load_json(frozen)
        if payload.get("schema_version") == "flipguard_v9_environment_v1":
            payload["captured_for_commit"] = BASE_COMMIT
            return payload
    memory = {}
    for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
        key, value = line.split(":", 1)
        if key in {"MemTotal", "SwapTotal"}:
            memory[key] = value.strip()
    cpu = "UNKNOWN"
    for line in Path("/proc/cpuinfo").read_text(encoding="ascii").splitlines():
        if line.startswith("model name"):
            cpu = line.split(":", 1)[1].strip()
            break
    disk = os.statvfs(ROOT)
    return {
        "schema_version": "flipguard_v9_environment_v1",
        "captured_for_commit": BASE_COMMIT,
        "host_os": platform.platform(),
        "architecture": platform.machine(),
        "logical_cpus": os.cpu_count(),
        "cpu_model": cpu,
        "memory": memory,
        "filesystem_available_bytes_at_freeze": disk.f_bavail * disk.f_frsize,
        "filesystem_available_inodes_at_freeze": disk.f_favail,
        "virtualization": "VMware",
        "orion_container": "python:3.11-slim; torch 2.2.2+cpu; torchvision 0.17.2+cpu",
        "active_external_services_at_final_freeze": 0,
    }


def baseline_rows() -> list[dict[str, object]]:
    return [
        {"system": "Conservative default", "role": "internal baseline", "evidence_tier": "INTERNAL_MEASURED", "workload": "controlled primary", "runtime": "Lattigo v6.2.0", "measurement_state": "MEASURED", "decision_bearing": "YES", "unique_input_or_instance_scope": "50 workload-partition instances", "security_state": "SECURITY_V2_ADMITTED_WHERE_EXECUTED", "portability": "NATIVE", "main_paper_eligible": "YES", "evidence": "docs/evidence/direct_synthesis_ablation_v1", "limitation": "finite declared primary scope"},
        {"system": "Latency-only", "role": "internal ablation", "evidence_tier": "INTERNAL_MEASURED", "workload": "controlled primary", "runtime": "Lattigo v6.2.0", "measurement_state": "MEASURED", "decision_bearing": "NO_GATE", "unique_input_or_instance_scope": "50 workload-partition instances", "security_state": "SECURITY_V2_FILTERED", "portability": "NATIVE", "main_paper_eligible": "YES_AS_ABLATION", "evidence": "docs/evidence/direct_synthesis_ablation_v1", "limitation": "not a decision-preserving selector"},
        {"system": "Security-V2 bounded catalog", "role": "internal bounded comparison", "evidence_tier": "INTERNAL_MEASURED", "workload": "controlled primary and shared polynomial", "runtime": "Lattigo v6.2.0", "measurement_state": "MEASURED", "decision_bearing": "YES", "unique_input_or_instance_scope": "700 formal candidates; 500+500 shared-polynomial inputs", "security_state": "PASS", "portability": "NATIVE", "main_paper_eligible": "YES", "evidence": "docs/evidence/security_v2_bounded_oracle_v1; docs/evidence/focused_external_comparison_v8", "limitation": "bounded catalog, not a global oracle"},
        {"system": "FlipGuard direct", "role": "proposed direct provider and gate", "evidence_tier": "INTERNAL_MEASURED", "workload": "controlled primary and shared polynomial", "runtime": "Lattigo v6.2.0", "measurement_state": "MEASURED_WITH_REPEAT_AMBIGUITY", "decision_bearing": "YES", "unique_input_or_instance_scope": "50 primary instances; 500+500 shared-polynomial inputs", "security_state": "PASS", "portability": "NATIVE", "main_paper_eligible": "YES_WITH_V_CERT_SCOPE", "evidence": "docs/evidence/final_realistic_baseline_closure_v9/direct_repeat_flip_forensics", "limitation": "one V_amb input flips in eight measurement repeats"},
        {"system": "Microsoft EVA", "role": "external compiler/provider", "evidence_tier": "EXTERNAL_DECISION_BEARING", "workload": "shared polynomial threshold", "runtime": "SEAL native", "measurement_state": "MEASURED", "decision_bearing": "YES", "unique_input_or_instance_scope": "500 validation + 500 locked audit", "security_state": "NATIVE_RUNTIME_MODEL_NOT_SECURITY_V2_EQUIVALENT", "portability": "NATIVE_ONLY", "main_paper_eligible": "YES_FOR_DECISION_RESULTS", "evidence": "docs/evidence/focused_external_comparison_v8", "limitation": "no raw cross-runtime latency ranking"},
        {"system": "Google HEIR Lattigo", "role": "external compiler/provider", "evidence_tier": "EXTERNAL_DECISION_BEARING", "workload": "exact shared polynomial threshold", "runtime": "Lattigo v6.2.0 common executor", "measurement_state": "MEASURED", "decision_bearing": "YES", "unique_input_or_instance_scope": "500 validation + 500 locked audit; 100 latency inputs", "security_state": "PASS", "portability": "PORTABLE_EXACT", "main_paper_eligible": "YES", "evidence": "docs/evidence/final_realistic_baseline_closure_v9/pairwise_latency_claim_admission.json", "limitation": "one exact shared workload; HEIR is not an autotuner"},
        {"system": "Google HEIR OpenFHE", "role": "external compiler/provider", "evidence_tier": "EXTERNAL_DECISION_BEARING", "workload": "shared polynomial threshold", "runtime": "OpenFHE native", "measurement_state": "MEASURED", "decision_bearing": "YES", "unique_input_or_instance_scope": "500 validation + 500 locked audit", "security_state": "NATIVE_RUNTIME_MODEL_NOT_SECURITY_V2_ALIGNED", "portability": "NATIVE_ONLY", "main_paper_eligible": "YES_FOR_NATIVE_DECISION_RESULTS", "evidence": "docs/evidence/focused_external_comparison_v8", "limitation": "no cross-runtime latency ratio"},
        {"system": "CoreLab EVA mode", "role": "external numerical scale plan", "evidence_tier": "EXTERNAL_NUMERICAL_ONLY", "workload": "official LinearRegression", "runtime": "SEAL native", "measurement_state": "36_OF_36_PLANS_COMPLETED", "decision_bearing": "NO", "unique_input_or_instance_scope": "200 inputs per completed plan", "security_state": "NATIVE_RUNTIME_MODEL_NOT_SECURITY_V2_ALIGNED", "portability": "DIFFERENT_MODEL_NUMERICAL_ONLY", "main_paper_eligible": "YES_AS_NUMERICAL_PANEL", "evidence": "docs/evidence/focused_external_comparison_v8/corelab_plan_status.csv", "limitation": "not a threshold-decision comparison"},
        {"system": "CoreLab ELASM mode", "role": "external numerical scale plan", "evidence_tier": "EXTERNAL_NUMERICAL_ONLY", "workload": "official LinearRegression", "runtime": "SEAL native", "measurement_state": "34_OF_36_PLANS_COMPLETED", "decision_bearing": "NO", "unique_input_or_instance_scope": "200 inputs per completed plan", "security_state": "NATIVE_RUNTIME_MODEL_NOT_SECURITY_V2_ALIGNED", "portability": "DIFFERENT_MODEL_NUMERICAL_ONLY", "main_paper_eligible": "YES_AS_PARTIAL_NUMERICAL_PANEL", "evidence": "docs/evidence/focused_external_comparison_v8/corelab_plan_status.csv", "limitation": "two native plan failures preserved"},
        {"system": "HECATE", "role": "scale-management related work", "evidence_tier": "RELATED_WORK_PAPER_ONLY", "workload": "not executed in V9", "runtime": "official compiler inspected", "measurement_state": "HECATE_PAPER_BASELINE_ONLY", "decision_bearing": "NOT_EVALUATED", "unique_input_or_instance_scope": "NOT_EVALUATED", "security_state": "NOT_EVALUATED", "portability": "OFFICIAL_STANDALONE_MODE_NOT_EXPOSED", "main_paper_eligible": "RELATED_WORK_ONLY", "evidence": "docs/evidence/final_realistic_baseline_closure_v9/hecate_feasibility.json", "limitation": "paper-derived pass composition was prohibited"},
        {"system": "Orion", "role": "DNN compiler related work plus feasibility self-test", "evidence_tier": "RELATED_WORK_WITH_AUXILIARY_OFFICIAL_SELF_TEST", "workload": "official untrained seed-42 MLP self-test", "runtime": "Orion Lattigo backend in Python 3.11", "measurement_state": "10_INPUT_SELF_TEST_PASS_FULL_EXTENSION_BLOCKED", "decision_bearing": "AUXILIARY_ONLY", "unique_input_or_instance_scope": "10 ordered preflight inputs", "security_state": "NATIVE_CONFIG_ONLY_NOT_FORMAL_SECURITY_V2_COMPARISON", "portability": "NATIVE_ONLY", "main_paper_eligible": "NO_AS_MEASURED_BASELINE", "evidence": "docs/evidence/final_realistic_baseline_closure_v9/orion_preflight.json", "limitation": "no official trained MLP weights; no validation/audit extension"},
    ]


def nonexecution_rows() -> list[dict[str, object]]:
    values = [
        ("DaCapo", "bootstrapping placement", "deep GPU DNNs", "HEaaN GPU", "bootstrapping applicability", "NO", "YES", "Current exact workload needs no bootstrap; paper treats scale managers as complementary.", "RELATED_WORK_ONLY"),
        ("AutoFHE", "architecture/polynomial/bootstrap co-search", "CIFAR CNNs", "GPU RNS-CKKS", "application adaptation", "NO", "YES", "Official search is a different optimization unit and requires a substantially larger GPU budget.", "RELATED_WORK_ONLY"),
        ("LOHEN", "layer-wise ciphertext configuration", "GPU CNN inference", "Liberate-FHE GPU", "configuration breadth", "NO", "YES", "Different model suite, runtime, hardware, and layer-level optimization unit.", "RELATED_WORK_ONLY"),
        ("SLOTHE", "non-arithmetic transformer-function approximation", "encrypted transformers", "GPU FHE", "application adaptation", "NO", "YES", "Not a CKKS parameter-provider equivalent for the frozen workload.", "RELATED_WORK_ONLY"),
        ("ANT-ACE", "ONNX CNN compilation", "CNN models", "compiler/runtime specific", "compiler breadth", "NO", "UNKNOWN", "No pre-frozen exact common workload or validated environment in the V9 window.", "RELATED_WORK_ONLY"),
        ("HEaaN.MLIR", "MLIR compilation for HEaaN", "HEaaN workloads", "HEaaN", "compiler breadth", "NO", "UNKNOWN", "No exact frozen common workload and runtime-equivalent decision output.", "RELATED_WORK_ONLY"),
        ("HALO", "scale and bootstrap management", "bootstrap-requiring graphs", "artifact-specific", "bootstrapping applicability", "NO", "UNKNOWN", "No bootstrap requirement in the exact V9 polynomial workload.", "RELATED_WORK_ONLY"),
        ("ReSBM", "rescaling/bootstrap management", "bootstrap-requiring graphs", "artifact-specific", "bootstrapping applicability", "NO", "UNKNOWN", "No bootstrap requirement and no approved protocol amendment.", "RELATED_WORK_ONLY"),
        ("Orbit", "bootstrapping optimization", "bootstrap workloads", "artifact unavailable for exact V9 mapping", "bootstrapping applicability", "NO", "UNKNOWN", "Official exact common-workload artifact was not available for this final comparison.", "RELATED_WORK_ONLY"),
        ("FHE-Agent", "agentic FHE program/configuration generation", "agent-generated tasks", "preprint artifact", "provider interoperability", "NO", "UNKNOWN", "No verified exact candidate/output path for the frozen workload in V9.", "RELATED_WORK_ONLY"),
        ("FHECrafter", "agentic FHE construction", "agent-generated tasks", "artifact-specific", "provider interoperability", "NO", "UNKNOWN", "No verified official exact-workload artifact in the frozen comparison window.", "RELATED_WORK_ONLY"),
    ]
    fields = ["system", "primary_optimization_objective", "official_workload", "runtime_hardware", "closest_flipguard_research_question", "exact_shared_workload_available", "decision_bearing_output_available", "reason_not_executed_v9", "evidence_tier"]
    return [dict(zip(fields, row)) for row in values]


def paired_table() -> list[dict[str, object]]:
    pairwise = load_json(PACK / "pairwise_latency_claim_admission.json")
    return [{
        "pair_id": row["pair_id"], "comparison": row["comparison"], "unique_input_clusters": row["unique_input_clusters"],
        "raw_pairs": row["raw_pairs"], "geometric_mean_total_ratio": row["geometric_mean_total_ratio"],
        "cluster_bootstrap_ci_low": row["cluster_bootstrap_ci_low"], "cluster_bootstrap_ci_high": row["cluster_bootstrap_ci_high"],
        "validation_state": row["validation_state"], "locked_audit_state": row["locked_audit_state"],
        "measurement_repeat_flips": json.dumps(row["measurement_repeat_flips"], sort_keys=True),
        "security_v2": row["security_v2"], "claim_state": row["state"], "reason": row["reason"],
    } for row in pairwise["claims"]]


def corelab_table() -> list[dict[str, object]]:
    rows = load_csv(V8 / "corelab_plan_status.csv")
    output = [{
        "provider_mode": f"CoreLab {row['mode'].upper()}", "plan_id": row["plan_id"], "waterline": row["waterline"],
        "status": row["status"], "unique_inputs": row["unique_inputs"], "raw_output_rows": row["raw_output_rows"],
        "reason_code": row["reason_code"] or "NONE",
    } for row in rows]
    output.append({"provider_mode": "HECATE", "plan_id": "NOT_EXECUTED", "waterline": "NOT_EVALUATED", "status": "HECATE_PAPER_BASELINE_ONLY", "unique_inputs": "NOT_EVALUATED", "raw_output_rows": 0, "reason_code": "OFFICIAL_STANDALONE_HECATE_MODE_NOT_EXPOSED"})
    return output


def svg(title: str, subtitle: str, items: list[tuple[str, str, str]]) -> str:
    height = 160 + 86 * len(items)
    boxes = []
    for index, (label, value, color) in enumerate(items):
        y = 118 + index * 86
        boxes.append(f'<rect x="48" y="{y}" width="864" height="62" rx="6" fill="#f6f8fa" stroke="{color}" stroke-width="2"/><text x="72" y="{y+27}" font-size="17" font-weight="700" fill="#0d1117">{label}</text><text x="72" y="{y+49}" font-size="14" fill="#57606a">{value}</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="{height}" viewBox="0 0 960 {height}" role="img" aria-labelledby="title desc">
<title id="title">{title}</title><desc id="desc">{subtitle}</desc>
<rect width="960" height="{height}" fill="#ffffff"/><text x="48" y="48" font-family="Arial,sans-serif" font-size="28" font-weight="700" fill="#0d2a52">{title}</text><text x="48" y="78" font-family="Arial,sans-serif" font-size="15" fill="#57606a">{subtitle}</text>
<g font-family="Arial,sans-serif">{''.join(boxes)}</g></svg>\n'''


def build() -> None:
    PACK.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    tables = PACK / "tables"; figures = PACK / "figures"
    result_tables = RESULTS / "tables"; result_figures = RESULTS / "figures"
    for directory in (tables, figures, result_tables, result_figures):
        directory.mkdir(parents=True, exist_ok=True)

    write_json(PACK / "environment.json", environment())
    baseline = baseline_rows()
    fields = list(baseline[0])
    write_csv(PACK / "final_baseline_matrix.csv", fields, baseline)
    nonexecution = nonexecution_rows()
    write_csv(PACK / "nonexecution_justification.csv", list(nonexecution[0]), nonexecution)

    accounting = load_csv(V8 / "execution_accounting.csv")
    extra = {field: "NOT_APPLICABLE" for field in accounting[0]}
    extra.update({"provider": "Orion", "phase": "official_untrained_self_test_preflight", "workload": "official_Orion_MLP_seed42", "unique_inputs": "10", "validation_inputs": "NOT_EVALUATED", "audit_inputs": "NOT_EVALUATED", "validation_audit_overlap": "NOT_EVALUATED", "plans_or_arms": "1", "candidate_trials": "NOT_APPLICABLE", "encrypted_candidate_executions": "1", "fresh_contexts_or_keysets": "1", "key_runs": "1", "measurement_passes": "1", "warmup_encrypted_sample_evaluations": "0", "recorded_encrypted_sample_evaluations": "10", "total_encrypted_sample_evaluations": "10", "raw_output_rows": "10", "decision_bearing_rows": "10", "execution_state": "OFFICIAL_SELF_TEST_ONLY_FULL_EXTENSION_BLOCKED"})
    accounting.append(extra)
    hecate = {field: "NOT_EVALUATED" for field in accounting[0]}
    hecate.update({"provider": "HECATE", "phase": "official_mode_feasibility", "workload": "NOT_EVALUATED", "unique_inputs": "NOT_EVALUATED", "plans_or_arms": "0", "candidate_trials": "0", "encrypted_candidate_executions": "0", "fresh_contexts_or_keysets": "0", "key_runs": "0", "measurement_passes": "0", "warmup_encrypted_sample_evaluations": "0", "recorded_encrypted_sample_evaluations": "0", "total_encrypted_sample_evaluations": "0", "raw_output_rows": "0", "decision_bearing_rows": "0", "execution_state": "HECATE_PAPER_BASELINE_ONLY"})
    accounting.append(hecate)
    write_csv(PACK / "execution_accounting.csv", list(accounting[0]), accounting)

    claims = {
        "schema_version": "flipguard_final_realistic_baseline_v9_claims_v1",
        "external_comparison_manuscript_ready": True,
        "repository_wide_paper_claim_allowed_unchanged": False,
        "claims": {
            "literature_baseline_practice": {"state": "SUPPORTED", "paper_admitted": True},
            "direct_repeat_flip_classification": {"state": "SUPPORTED", "paper_admitted": True, "wording": "Eight repeated flips arose from one declared ambiguous input and are reported as F4 near-boundary ambiguity."},
            "direct_repeated_stability_on_v_amb": {"state": "BLOCKED", "paper_admitted": False},
            "direct_finite_v_cert_locked_audit": {"state": "SUPPORTED", "paper_admitted": True, "scope": "original finite V_cert audit only"},
            "p1_heir_over_direct_latency": {"state": "BLOCKED_UNSTABLE_ARM", "paper_admitted": False},
            "p2_catalog_over_direct_latency": {"state": "BLOCKED_UNSTABLE_ARM", "paper_admitted": False},
            "p3_catalog_over_heir_latency": {"state": "SUPPORTED", "paper_admitted": True, "wording": "On the exact shared polynomial in the common Lattigo executor, catalog total latency divided by HEIR total latency was 6.393517 with a cluster-bootstrap 95% CI of [6.361222, 6.427118]."},
            "corelab_eva_elasm_numerical_grid": {"state": "PARTIALLY_SUPPORTED", "paper_admitted": True},
            "hecate_measured_provider": {"state": "NOT_EVALUATED", "paper_admitted": False},
            "orion_official_encrypted_self_test": {"state": "PILOT_ONLY", "paper_admitted": False},
            "orion_trained_decision_provider": {"state": "BLOCKED", "paper_admitted": False},
            "cross_runtime_speed_superiority": {"state": "BLOCKED", "paper_admitted": False},
            "global_optimality": {"state": "BLOCKED", "paper_admitted": False},
        },
        "prohibited": ["all state-of-the-art autotuners", "comprehensive execution of every CKKS compiler", "global optimum", "universal superiority", "direct synthesis always wins", "build success equals experimental reproduction"],
    }
    write_json(PACK / "final_claim_admission.json", claims)

    change_map = """# V9 Manuscript Change Map

## Required replacements

- Replace the single blocked common-executor latency claim with three independently audited pairs. P1 and P2 remain blocked because the direct arm flips on one `V_amb` input; P3 is admitted.
- State that the eight direct measurement flips are four passes across three keysets for one near-boundary input, not eight independent failed inputs.
- Preserve the original zero-flip finite `V_cert` locked audit while excluding repeated-stability claims for `V_amb`.
- Present CoreLab EVA/ELASM as a numerical error-latency plan grid, not a decision-bearing provider panel.
- Keep HECATE as an official-paper baseline because the pinned artifact exposes no standalone HECATE mode.
- Describe Orion only as a successful ten-input official untrained self-test; do not present it as a trained-model baseline.
- Report the direct trial distribution once: 50 instances, 70 trials, mean 1.4, median 1, IQR 1, maximum 2, 30 one-trial, 20 two-trial, and 20 repaired instances.

## Admitted common-executor sentence

On the exact shared polynomial and common Lattigo v6.2.0 executor, the Security-V2 bounded-catalog total latency divided by HEIR-generated total latency had a geometric mean of 6.393517 (cluster-bootstrap 95% CI [6.361222, 6.427118]) over 100 frozen input clusters and 1,800 paired measurements.

## Scope sentence

The result is limited to one exact shared workload, its frozen inputs, one host, and Security-V2-aligned Lattigo candidates; it does not establish HEIR as globally optimal or universally faster.
"""
    (PACK / "manuscript_change_map.md").write_text(change_map, encoding="utf-8")
    fairness = """# Fairness Limitations

- Native EVA, HEIR-OpenFHE, and CoreLab timings are not combined into a raw cross-runtime speed ranking.
- Only `PORTABLE_EXACT` common-Lattigo arms are eligible for the P1-P3 paired panel.
- P1 and P2 are blocked because one direct-arm `V_amb` input changes decision in repeated measurements; this negative result is not removed.
- P3 excludes the unstable direct arm and is independently complete, paired, Security-V2 aligned, and zero-flip.
- CoreLab LinearRegression is a numerical plan comparison without a natural threshold decision.
- HECATE was not reconstructed from paper prose when the pinned official CLI exposed no standalone mode.
- Orion's ten-input run uses the official deterministic seed-42 self-test weights, not a distributed trained model, and is not counted as a measured baseline.
- The final set is representative and claim-aligned, not an execution census of every CKKS compiler.
"""
    (PACK / "fairness_limitations.md").write_text(fairness, encoding="utf-8")

    copy(PACK / "literature_baseline_practice.csv", tables / "table_01_baseline_practice.csv")
    copy(PACK / "final_baseline_matrix.csv", tables / "table_02_final_baseline_tiers.csv")
    copy(V8_RESULTS / "tables/table_02_eva_scale_and_locked_audit.csv", tables / "table_03_eva_scale_and_locked_audit.csv")
    copy(V8_RESULTS / "tables/table_03_shared_polynomial_decision_results.csv", tables / "table_04_heir_common_executor_candidates.csv")
    pair_rows = paired_table()
    write_csv(tables / "table_05_pairwise_latency_claims.csv", list(pair_rows[0]), pair_rows)
    corelab = corelab_table()
    write_csv(tables / "table_06_corelab_eva_hecate_elasm_grid.csv", list(corelab[0]), corelab)
    copy(ROOT / "docs/evidence/comprehensive_ckks_comparison_v3/tables/08_internal_trial_distribution.csv", tables / "table_07_internal_direct_trial_distribution.csv")

    figure_specs = {
        "figure_01_provider_roles_and_gate.svg": ("Provider roles and the FlipGuard gate", "Provider generation and decision-integrity admission are separate roles.", [("Candidate providers", "Default, catalog, EVA, HEIR, and FlipGuard direct", "#1f6feb"), ("FlipGuard gate", "Security admission, encrypted validation, bounded repair, and abstention", "#2f9eca"), ("Locked audit", "Replay the selected literal without retuning", "#2da44e")]),
        "figure_02_eva_scale_error_and_flips.svg": ("EVA scale, error, and decision outcome", "Native-runtime numerical and decision evidence remain separate from common-executor latency.", [("Scale 20", "Rejected: numerical error and decision flips", "#cf222e"), ("Scale 30", "Finite validation and locked audit SAFE", "#2da44e"), ("Scale 40", "Finite validation and locked audit SAFE", "#2da44e")]),
        "figure_03_common_executor_pairwise_admission.svg": ("Exact common-executor pairwise admission", "Each pair is admitted independently; direct-arm ambiguity does not leak into P3.", [("P1 HEIR / direct", "BLOCKED_UNSTABLE_ARM", "#cf222e"), ("P2 catalog / direct", "BLOCKED_UNSTABLE_ARM", "#cf222e"), ("P3 catalog / HEIR", "PAPER_ADMITTED: 6.393517 [6.361222, 6.427118]", "#2da44e")]),
        "figure_04_corelab_error_latency_grid.svg": ("CoreLab numerical plan grid", "EVA and ELASM use the official LinearRegression workload; no threshold claim is attached.", [("CoreLab EVA", "36/36 plans complete, 200 inputs per plan", "#1f6feb"), ("CoreLab ELASM", "34/36 plans complete; two failures preserved", "#bf8700"), ("HECATE", "Paper baseline only: no standalone official mode", "#57606a")]),
        "figure_05_external_evidence_depth.svg": ("External-provider evidence depth", "Measured, numerical-only, feasibility-only, and paper-only tiers are not conflated.", [("Decision-bearing measured", "EVA and HEIR", "#2da44e"), ("Numerical plan grid", "CoreLab EVA and ELASM", "#1f6feb"), ("Auxiliary self-test", "Orion: 10 encrypted inputs, untrained official weights", "#bf8700"), ("Paper only", "HECATE and objective-incompatible systems", "#57606a")]),
    }
    for name, (title, subtitle, items) in figure_specs.items():
        (figures / name).write_text(svg(title, subtitle, items), encoding="utf-8")

    for path in sorted(tables.glob("*.csv")):
        copy(path, result_tables / path.name)
    for path in sorted(figures.glob("*.svg")):
        copy(path, result_figures / path.name)
    publication = {
        "schema_version": "flipguard_v9_publication_inputs_v1",
        "status": "FINAL_VERIFIED_MARKDOWN_CSV_SVG_INPUTS",
        "source_commit": BASE_COMMIT,
        "table_count": len(list(result_tables.glob("*.csv"))),
        "figure_count": len(list(result_figures.glob("*.svg"))),
        "tables": [{"path": str(path.relative_to(ROOT)), "sha256": sha256(path)} for path in sorted(result_tables.glob("*.csv"))],
        "figures": [{"path": str(path.relative_to(ROOT)), "sha256": sha256(path)} for path in sorted(result_figures.glob("*.svg"))],
        "docx_hwp_created": False,
        "orion_main_figure_created": False,
    }
    write_json(RESULTS / "publication_inputs_manifest.json", publication)
    write_json(RESULTS / "manifest.json", {"schema_version": "flipguard_v9_result_overlay_v1", "evidence_pack": "docs/evidence/final_realistic_baseline_closure_v9", "publication_inputs": publication})

    manifest = {
        "schema_version": "flipguard_final_realistic_baseline_closure_v9",
        "completion_state": "FINAL_BASELINE_V8_SUFFICIENT_OPTIONALS_BLOCKED",
        "mandatory_closure_states": ["DIRECT_REPEAT_FLIP_CLASSIFIED", "PAIRWISE_LATENCY_CLAIMS_CLASSIFIED", "FINAL_BASELINE_SET_FROZEN", "EXTERNAL_COMPARISON_READY_FOR_MANUSCRIPT"],
        "external_comparison_manuscript_ready": True,
        "repository_wide_paper_claim_allowed_unchanged": False,
        "source_commit": BASE_COMMIT,
        "predecessor_commit": "d32fae893bc381729b1eb2139ebdb4e444362552",
        "predecessor_v8_manifest_sha256": "sha256:a3c345aaf95b29753d5a62c80cd86d8fdae158bc5bbe38f1f83bbd363c92f867",
        "security_policy_id": "security_guidelines_cic2025_table5_2_ternary_128_v2",
        "security_policy_digest": "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055",
        "direct_policy_id": "flipguard_direct_synthesis_policy_v2",
        "direct_policy_digest": "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603",
        "start_timestamp": "2026-08-08T20:41:46+09:00",
        "freeze_timestamp": FREEZE_TIMESTAMP,
        "direct_repeat_flip_class": "F4_NEAR_BOUNDARY_AMBIGUITY",
        "direct_repeat_flips": 8,
        "direct_repeat_unique_inputs": 1,
        "targeted_replay_performed": False,
        "pairwise_states": {"P1": "BLOCKED_UNSTABLE_ARM", "P2": "BLOCKED_UNSTABLE_ARM", "P3": "PAPER_ADMITTED"},
        "p3_ratio": 6.393517225744701,
        "p3_ci": [6.361221883796193, 6.427118084866673],
        "hecate_status": "HECATE_PAPER_BASELINE_ONLY",
        "hecate_plans_attempted": 0,
        "orion_status": "ORION_OFFICIAL_SELF_TEST_ONLY_FULL_EXTENSION_BLOCKED",
        "orion_preflight_inputs": 10,
        "orion_preflight_flips": 0,
        "orion_full_run_performed": False,
        "external_measured_decision_providers": ["Microsoft EVA", "Google HEIR Lattigo", "Google HEIR OpenFHE"],
        "external_numerical_modes": ["CoreLab EVA", "CoreLab ELASM"],
        "optional_measured_providers_added": 0,
        "policy_retuning": 0,
        "new_dataset_or_trained_model": 0,
        "publication_inputs_manifest_sha256": sha256(RESULTS / "publication_inputs_manifest.json"),
    }
    write_json(PACK / "manifest.json", manifest)
    report = f"""# Final Realistic Baseline Closure V9

- Completion state: `{manifest['completion_state']}`
- Direct repeat classification: `F4_NEAR_BOUNDARY_AMBIGUITY` (8 flips, 1 unique input, no replay)
- P1: `BLOCKED_UNSTABLE_ARM`
- P2: `BLOCKED_UNSTABLE_ARM`
- P3: `PAPER_ADMITTED`, ratio 6.393517, 95% CI [6.361222, 6.427118]
- HECATE: `HECATE_PAPER_BASELINE_ONLY`, 0 plans attempted
- Orion: 10-input official encrypted self-test PASS with 0 flips; full trained-model extension blocked because no official trained MLP weights are distributed
- External comparison manuscript readiness: `true`
- Repository-wide paper flag: unchanged

## Verification

- `go test ./...`: PASS after isolating the ignored HEIR/Bazel build cache from the root Go module
- `go vet ./...`: PASS
- Python unittest: 349 tests PASS in 1,994.372 seconds
- Python bytecode compilation: PASS with bytecode redirected outside frozen evidence trees
- V7, V8, direct-forensic, and V9 deterministic verifiers: PASS
- V9 evidence checksums: PASS
- V9 publication-input checksums and SVG parsing: PASS

## Recovery record

- The first root Go test traversed ignored HEIR/Bazel Go-toolchain test fixtures and failed outside FlipGuard packages. A local untracked nested-module boundary isolated that cache; the unchanged root command then passed.
- Orion attempt 1 failed on Python 3.12/Torch Dynamo compatibility before encrypted inference.
- Orion attempt 2 failed because the isolated Python 3.11 image lacked the `git` provenance executable.
- Orion attempt 3 completed actual keygen, encryption, evaluation, decryption, and ten-logit extraction.

## Remaining manuscript risks

- P1 and P2 are not admissible repeated-stability claims because the direct arm flips on one declared ambiguous input.
- P3 covers one exact shared polynomial and one measured host.
- HECATE has no separately invocable official mode in the pinned artifact.
- Orion full trained-model validation/audit is blocked by absent official trained MLP weights.
- Native-runtime timings remain non-comparable as raw speed rankings.

- Next action: rewrite the manuscript using only `final_claim_admission.json` and the V9 publication inputs
- Run disposition: `PAUSE_FOR_FINAL_MANUSCRIPT_REWRITE`
"""
    (PACK / "CHECKPOINT_REPORT.md").write_text(report, encoding="utf-8")
    state = {"schema_version": "flipguard_v9_final_state_v1", "current_stage": "FINAL_EVIDENCE_FROZEN", "completion_state": manifest["completion_state"], "external_comparison_manuscript_ready": True, "run_disposition": "PAUSE_FOR_FINAL_MANUSCRIPT_REWRITE", "freeze_timestamp": FREEZE_TIMESTAMP}
    write_json(ROOT / "external/v9/status/final_state.json", state)
    (ROOT / "external/v9/status/current_stage.txt").write_text("FINAL_EVIDENCE_FROZEN\n", encoding="ascii")

    checksum_paths = [path for path in PACK.rglob("*") if path.is_file() and path.name != "SHA256SUMS" and "__pycache__" not in path.parts]
    (PACK / "SHA256SUMS").write_text("".join(f"{sha256(path).removeprefix('sha256:')}  {path.relative_to(PACK)}\n" for path in sorted(checksum_paths)), encoding="ascii")
    result_paths = [path for path in RESULTS.rglob("*") if path.is_file() and path.name != "SHA256SUMS"]
    (RESULTS / "SHA256SUMS").write_text("".join(f"{sha256(path).removeprefix('sha256:')}  {path.relative_to(RESULTS)}\n" for path in sorted(result_paths)), encoding="ascii")
    print(json.dumps({"status": "PASS", "completion_state": manifest["completion_state"], "tables": publication["table_count"], "figures": publication["figure_count"]}, sort_keys=True))


if __name__ == "__main__":
    build()
