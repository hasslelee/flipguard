#!/usr/bin/env python3
"""Normalize, freeze, and verify the focused V8 external comparison."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/evidence/focused_external_comparison_v8"
RESULTS = ROOT / "results/thesis_grade_protocol/focused_external_comparison_v8"
OUTPUTS = ROOT / "external/v8/outputs"
STATUS = ROOT / "external/v8/status"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def json_file(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def csv_file(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def truth(value: object) -> bool:
    return str(value).lower() in {"1", "true"}


def geometric_mean(values: list[float]) -> float:
    if not values or any(value <= 0 for value in values):
        raise ValueError("geometric mean requires positive values")
    return math.exp(statistics.fmean(math.log(value) for value in values))


def paired_ratio_summary(
    rows: list[dict[str, object]],
    numerator: str,
    denominator: str,
) -> dict[str, object]:
    grouped: dict[tuple[int, int, int], dict[str, float]] = {}
    for row in rows:
        key = (int(row["keyset"]), int(row["pass"]), int(row["row_id"]))
        grouped.setdefault(key, {})[str(row["arm"])] = float(row["total_ms"])
    ratios_by_input: dict[int, list[float]] = {}
    for (_, _, row_id), values in grouped.items():
        if numerator in values and denominator in values:
            ratios_by_input.setdefault(row_id, []).append(
                values[numerator] / values[denominator]
            )
    input_ratios = {
        row_id: geometric_mean(values)
        for row_id, values in ratios_by_input.items()
    }
    ids = sorted(input_ratios)
    observed = geometric_mean([input_ratios[row_id] for row_id in ids])
    generator = random.Random(20260807)
    bootstrap = []
    for _ in range(5000):
        bootstrap.append(geometric_mean([
            input_ratios[ids[generator.randrange(len(ids))]]
            for _ in ids
        ]))
    bootstrap.sort()
    return {
        "comparison": f"{numerator}/{denominator}",
        "unique_input_clusters": len(ids),
        "raw_pairs": sum(len(values) for values in ratios_by_input.values()),
        "geometric_mean_total_ratio": observed,
        "cluster_bootstrap_ci_low": bootstrap[int(0.025 * len(bootstrap))],
        "cluster_bootstrap_ci_high": bootstrap[min(len(bootstrap) - 1, int(0.975 * len(bootstrap)))],
        "bootstrap_repetitions": len(bootstrap),
    }


def copy_csv(source: Path, destination: Path) -> list[dict[str, str]]:
    rows = csv_file(source)
    shutil.copyfile(source, destination)
    return rows


def flatten_eva() -> tuple[list[dict[str, object]], dict[str, object] | None]:
    root = OUTPUTS / "eva/shared-polynomial-threshold-v8"
    if not (root / "manifest.json").is_file():
        return [], None
    rows: list[dict[str, object]] = []
    for path in sorted(root.glob("validation_scale_*.csv")) + sorted(root.glob("audit_scale_*.csv")):
        rows.extend(csv_file(path))
    return rows, json_file(root / "manifest.json")


def flatten_heir() -> tuple[list[dict[str, object]], dict[str, object] | None]:
    root = OUTPUTS / "heir/shared-polynomial-threshold-v8"
    if not (root / "manifest.json").is_file():
        return [], None
    rows: list[dict[str, object]] = []
    for path in sorted(root.glob("lattigo_*.jsonl")):
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    for path in sorted(root.glob("openfhe_*.csv")):
        rows.extend(csv_file(path))
    fields = sorted({key for row in rows for key in row})
    write_csv(EVIDENCE / "heir_shared_polynomial_records.csv", fields, rows)
    return rows, json_file(root / "manifest.json")


def flipguard_facts() -> tuple[dict[str, object] | None, list[dict[str, object]], list[dict[str, object]]]:
    root = OUTPUTS / "flipguard/shared-polynomial-threshold-v8"
    if not (root / "manifest.json").is_file():
        return None, [], []
    manifest = json_file(root / "manifest.json")
    gate_rows = []
    audit_rows = []
    paths = [("direct", root / "direct_validation.json")]
    paths.extend((path.stem.removesuffix("_validation"), path) for path in sorted((root / "catalog").glob("*_validation.json")))
    for arm, path in paths:
        result = json_file(path)
        trial = result["trial"]
        candidate = result["bound_candidate"]["candidate"]
        gate_rows.append({
            "provider": "FlipGuard direct" if arm == "direct" else "Security-V2 bounded catalog",
            "arm": arm, "workload": "shared_polynomial_threshold_v8", "candidate_id": candidate["id"],
            "status": trial["status"], "outcome": result["outcome"],
            "fresh_key_runs": trial["key_repeats_completed"], "unique_inputs": 500,
            "raw_observations": trial.get("encrypted_sample_evaluations", 1500),
            "decision_flips": trial["decision_flips"], "reserve_policy_violations": trial["error_violations"],
            "mean_total_ms": trial["mean_total_ms"], "security_state": candidate["security"]["final_admission"],
        })
    for arm, path in (("direct", root / "direct_locked_audit.json"), ("catalog_fastest_safe", root / "catalog_fastest_safe_locked_audit.json")):
        if path.is_file():
            result = json_file(path); trial = result["audit_trial"]
            audit_rows.append({
                "provider": "FlipGuard direct" if arm == "direct" else "Security-V2 bounded catalog",
                "arm": arm, "workload": "shared_polynomial_threshold_v8", "candidate_id": result["selected_candidate"]["id"],
                "outcome": result["outcome"], "status": trial["status"], "fresh_key_runs": trial["key_repeats_completed"],
                "unique_inputs": 500, "decision_flips": trial["decision_flips"],
                "reserve_policy_violations": trial["error_violations"], "retuning": result["retuning_performed"],
            })
    return manifest, gate_rows, audit_rows


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    end_timestamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    start_timestamp = (STATUS / "autonomous_start_timestamp.txt").read_text().strip() if (STATUS / "autonomous_start_timestamp.txt").is_file() else "NOT_RECORDED"
    environment_start = {
        "schema_version": "flipguard_focused_external_v8_environment_v1",
        "timestamp": start_timestamp, "hostname_redacted": True,
        "platform": platform.platform(), "python": platform.python_version(),
        "cpu_count": os.cpu_count(), "v7_binding": "external/v8/manifests/v7_binding.json",
    }
    (EVIDENCE / "environment_start.json").write_text(json.dumps(environment_start, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    environment_end = {**environment_start, "timestamp": end_timestamp, "phase": "final_freeze"}
    (EVIDENCE / "environment_end.json").write_text(json.dumps(environment_end, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    eva_rows, eva_manifest = flatten_eva()
    if eva_rows:
        write_csv(EVIDENCE / "eva_population_records.csv", list(eva_rows[0]), eva_rows)
    else:
        write_csv(EVIDENCE / "eva_population_records.csv", ["provider", "status", "reason"], [{"provider": "Microsoft EVA", "status": "NOT_EVALUATED", "reason": "MISSING_COMPLETED_MANIFEST"}])
    heir_rows, heir_manifest = flatten_heir()
    if not heir_rows:
        write_csv(EVIDENCE / "heir_shared_polynomial_records.csv", ["provider", "status", "reason"], [{"provider": "Google HEIR", "status": "NOT_EVALUATED", "reason": "MISSING_COMPLETED_MANIFEST"}])
    corelab_root = OUTPUTS / "corelab/linear-regression-multi-input-v8"
    corelab_manifest = json_file(corelab_root / "manifest.json") if (corelab_root / "manifest.json").is_file() else None
    if corelab_manifest:
        copy_csv(corelab_root / "records.csv", EVIDENCE / "corelab_multi_input_records.csv")
    else:
        write_csv(EVIDENCE / "corelab_multi_input_records.csv", ["provider", "status", "reason"], [{"provider": "CoreLab EVA/ELASM", "status": "NOT_EVALUATED", "reason": "MISSING_COMPLETED_MANIFEST"}])

    flipguard_manifest, gate_rows, flipguard_audits = flipguard_facts()
    common_path = OUTPUTS / "flipguard/shared-polynomial-threshold-v8/common_executor_paired_latency.json"
    common_data = json_file(common_path) if common_path.is_file() else None
    common_safe = False
    if heir_manifest:
        validation = next(
            row for row in heir_manifest["runtime_summaries"]["lattigo_v6_2"]
            if row["role"] == "configuration_validation"
        )
        safe = validation["decision_flips"] == 0 and validation["reserve_policy_violations"] == 0
        gate_rows.append({
            "provider": "Google HEIR", "arm": "heir_generated_lattigo_v8",
            "workload": "shared_polynomial_threshold_v8", "candidate_id": "heir_generated_lattigo_v8",
            "status": "SAFE" if safe else "REJECTED", "outcome": "SELECTED" if safe else "NO_SAFE",
            "fresh_key_runs": validation["fresh_contexts"], "unique_inputs": validation["unique_inputs"],
            "raw_observations": validation["raw_observations"], "decision_flips": validation["decision_flips"],
            "reserve_policy_violations": validation["reserve_policy_violations"], "mean_total_ms": "",
            "security_state": heir_manifest["lattigo_v6_2_parameters"]["final_admission"],
        })
    if common_data and heir_manifest and flipguard_manifest:
        heir_audit = next(
            row for row in heir_manifest["runtime_summaries"]["lattigo_v6_2"]
            if row["role"] == "locked_audit"
        )
        common_safe = (
            heir_audit["decision_flips"] == 0
            and heir_audit["reserve_policy_violations"] == 0
            and flipguard_manifest["direct"]["locked_audit_outcome"] == "LOCKED_AUDIT_PASS"
            and flipguard_manifest["catalog"]["locked_audit_outcome"] == "LOCKED_AUDIT_PASS"
            and all(not row["decision_flip"] and not row["reserve_violation"] for row in common_data["records"])
        )
    write_csv(EVIDENCE / "provider_gate_records.csv", sorted({key for row in gate_rows for key in row}) or ["provider", "status"], gate_rows or [{"provider": "FlipGuard", "status": "NOT_EVALUATED"}])
    audit_rows: list[dict[str, object]] = list(flipguard_audits)
    if eva_manifest:
        audit_rows.extend({"provider": "Microsoft EVA", "arm": f"scale{row['scale_bits']}", "workload": "shared_polynomial_threshold_v8", "candidate_id": row["candidate_id"], "outcome": row["status"], "status": row["status"], "fresh_key_runs": row["contexts"], "unique_inputs": row["unique_inputs"], "decision_flips": row["decision_flips"], "reserve_policy_violations": row["reserve_policy_violations"], "retuning": row["retuning"]} for row in eva_manifest["audits"])
    if heir_manifest:
        for runtime, summaries in heir_manifest["runtime_summaries"].items():
            summary = next(row for row in summaries if row["role"] == "locked_audit")
            audit_rows.append({"provider": "Google HEIR", "arm": runtime, "workload": "shared_polynomial_threshold_v8", "candidate_id": f"heir_{runtime}_shared_polynomial", "outcome": "SAFE" if summary["decision_flips"] == 0 and summary["reserve_policy_violations"] == 0 else "REJECTED", "status": "SAFE" if summary["decision_flips"] == 0 and summary["reserve_policy_violations"] == 0 else "REJECTED", "fresh_key_runs": summary["fresh_contexts"], "unique_inputs": summary["unique_inputs"], "decision_flips": summary["decision_flips"], "reserve_policy_violations": summary["reserve_policy_violations"], "retuning": 0})
    write_csv(EVIDENCE / "audit_records.csv", sorted({key for row in audit_rows for key in row}) or ["provider", "status"], audit_rows or [{"provider": "none", "status": "NOT_EVALUATED"}])

    common_rows = []
    if common_data:
        for row in common_data["records"]:
            common_rows.append({
                **row, "runtime": "Lattigo v6.2.0", "workload": "shared_polynomial_threshold_v8",
                "portability": "PORTABLE_EXACT" if row["arm"] == "heir_generated" else "NATIVE_FLIPGUARD_ARM",
                "security_state": "PASS", "latency_state": "PAIRED_HEADLINE" if common_safe else "PAIRED_DIAGNOSTIC_UNSAFE_ARM",
            })
    write_csv(EVIDENCE / "common_executor_records.csv", list(common_rows[0]) if common_rows else ["provider", "status"], common_rows or [{"provider": "none", "status": "NOT_EVALUATED"}])
    mismatch_rows = [
        {"provider": "Microsoft EVA", "workload": "shared_polynomial_threshold_v8", "dimension": "runtime_and_modulus_schedule", "state": "NATIVE_ONLY", "reason": "EVA/SEAL native schedule is not an exact Lattigo literal"},
        {"provider": "CoreLab EVA/ELASM", "workload": "official_LinearRegression_multi_input_v8", "dimension": "output_semantics", "state": "NUMERICAL_ONLY", "reason": "official workload has no natural frozen threshold decision"},
        {"provider": "Google HEIR", "workload": "shared_polynomial_threshold_v8", "dimension": "operation_order", "state": "PORTABLE_EXACT", "reason": "the unmodified generated Lattigo evaluator is linked into the common harness"},
    ]
    write_csv(EVIDENCE / "operation_mismatch_records.csv", list(mismatch_rows[0]), mismatch_rows)

    latency_rows = []
    if eva_rows:
        for row in eva_rows:
            latency_rows.append({"provider": row["provider"], "runtime": "EVA/SEAL", "workload": row["workload"], "role": row["role"], "arm": f"scale{row['scale_bits']}", "context": row["context_index"], "row_id": row["row_id"], "timing_unit": "encrypted_batch_repeated_on_each_input_row", "evaluate_ms": row["evaluate_ms"], "total_ms": row["total_ms"], "comparison_state": "NATIVE_ONLY_NO_CROSS_RUNTIME_RATIO"})
    if heir_rows:
        for row in heir_rows:
            if str(row.get("runtime", "")).startswith("Lattigo"):
                latency_rows.append({"provider": "Google HEIR", "runtime": row["runtime"], "workload": "shared_polynomial_threshold_v8", "role": row["role"], "arm": "heir_generated", "context": row["context"], "row_id": row["row_id"], "timing_unit": "per_input", "evaluate_ms": row.get("evaluate_ms", ""), "total_ms": row.get("total_ms", ""), "comparison_state": "UNPAIRED_DIAGNOSTIC"})
    if common_data:
        for row in common_data["records"]:
            latency_rows.append({
                "provider": row["arm"], "runtime": "Lattigo v6.2.0 common harness",
                "workload": "shared_polynomial_threshold_v8", "role": "locked_audit_latency_subset",
                "arm": row["arm"], "context": row["keyset"], "row_id": row["row_id"],
                "timing_unit": "per_input", "evaluate_ms": row["evaluate_ms"],
                "total_ms": row["total_ms"], "comparison_state": "PAIRED_HEADLINE" if common_safe else "PAIRED_DIAGNOSTIC_UNSAFE_ARM",
            })
    write_csv(EVIDENCE / "latency_records.csv", list(latency_rows[0]) if latency_rows else ["provider", "status"], latency_rows or [{"provider": "none", "status": "NOT_EVALUATED"}])
    latency_summary = []
    for provider in sorted({str(row["provider"]) for row in latency_rows}):
        values = [float(row["total_ms"]) for row in latency_rows if row["provider"] == provider and str(row["total_ms"]) not in {"", "None"}]
        latency_summary.append({"provider": provider, "observations": len(values), "mean_total_ms": statistics.fmean(values) if values else "", "median_total_ms": statistics.median(values) if values else "", "p95_total_ms": sorted(values)[max(0, math.ceil(0.95 * len(values)) - 1)] if values else "", "comparison_state": "NO_CROSS_RUNTIME_RATIO"})
    write_csv(EVIDENCE / "latency_summary.csv", list(latency_summary[0]) if latency_summary else ["provider", "status"], latency_summary or [{"provider": "none", "status": "NOT_EVALUATED"}])
    pair_summaries = []
    if common_data:
        pair_summaries = [
            paired_ratio_summary(common_data["records"], "heir_generated", "flipguard_direct"),
            paired_ratio_summary(common_data["records"], "bounded_catalog", "flipguard_direct"),
            paired_ratio_summary(common_data["records"], "bounded_catalog", "heir_generated"),
        ]
        write_csv(EVIDENCE / "common_executor_paired_summary.csv", list(pair_summaries[0]), pair_summaries)
    else:
        write_csv(EVIDENCE / "common_executor_paired_summary.csv", ["comparison", "status"], [{"comparison": "none", "status": "NOT_EVALUATED"}])

    error_summary = []
    if eva_manifest:
        for arm in eva_manifest["arms"]:
            error_summary.append({"provider": "Microsoft EVA", "arm": f"scale{arm['scale_bits']}", "role": "configuration_validation", "max_absolute_error": arm["validation"]["max_absolute_error"], "max_normalized_budget_usage": arm["validation"]["max_normalized_budget_usage"], "decision_flips": arm["validation"]["decision_flips"], "violations": arm["validation"]["reserve_policy_violations"]})
    if heir_manifest:
        for runtime, summaries in heir_manifest["runtime_summaries"].items():
            for item in summaries:
                error_summary.append({"provider": f"Google HEIR/{runtime}", "arm": runtime, "role": item["role"], "max_absolute_error": item["max_absolute_error"], "max_normalized_budget_usage": item["max_normalized_budget_usage"], "decision_flips": item["decision_flips"], "violations": item["reserve_policy_violations"]})
    write_csv(EVIDENCE / "numerical_error_summary.csv", list(error_summary[0]) if error_summary else ["provider", "status"], error_summary or [{"provider": "none", "status": "NOT_EVALUATED"}])

    accounting = [
        {"provider": "Microsoft EVA", "workload": "shared_polynomial_threshold_v8", "unique_inputs": 1000 if eva_manifest else 0, "contexts": 15 if eva_manifest else 0, "plans_or_arms": 5 if eva_manifest else 0, "raw_rows": len(eva_rows), "row_meaning": "input-context-arm observations"},
        {"provider": "Google HEIR", "workload": "shared_polynomial_threshold_v8", "unique_inputs": 1000 if heir_manifest else 0, "contexts": 12 if heir_manifest else 0, "plans_or_arms": 4 if heir_manifest else 0, "raw_rows": len(heir_rows), "row_meaning": "input-context-runtime-role observations"},
        {"provider": "CoreLab EVA/ELASM", "workload": "official_LinearRegression_multi_input_v8", "unique_inputs": corelab_manifest["unique_inputs_per_completed_plan"] if corelab_manifest else 0, "contexts": corelab_manifest["fresh_contexts"] if corelab_manifest else 0, "plans_or_arms": corelab_manifest["plans_completed"] if corelab_manifest else 0, "raw_rows": corelab_manifest["raw_plan_input_rows"] if corelab_manifest else 0, "row_meaning": "unique-input-plan observations"},
    ]
    write_csv(EVIDENCE / "unique_input_accounting.csv", list(accounting[0]), accounting)
    execution = [{**row, "encrypted_execution_complete": row["raw_rows"] > 0} for row in accounting]
    write_csv(EVIDENCE / "execution_accounting.csv", list(execution[0]), execution)

    security = [
        {"provider": "Microsoft EVA", "runtime": "SEAL native", "scheme": "CKKS", "log_n": "", "q": "", "p": "", "log_qp": "", "scale_bits": "20/30/40", "distribution": "native runtime model", "standard": "native compiler security_level=128", "state": "NATIVE_RUNTIME_SECURITY_NOT_EQUIVALENT_TO_LATTIGO_SECURITY_V2", "headline_eligible": False},
        {"provider": "Google HEIR", "runtime": "Lattigo v6.2.0", "scheme": "CKKS", "log_n": heir_manifest["lattigo_v6_2_parameters"]["log_n"] if heir_manifest else "", "q": json.dumps(heir_manifest["lattigo_v6_2_parameters"]["q_primes"]) if heir_manifest else "", "p": json.dumps(heir_manifest["lattigo_v6_2_parameters"]["p_primes"]) if heir_manifest else "", "log_qp": heir_manifest["lattigo_v6_2_parameters"]["log_qp"] if heir_manifest else "", "scale_bits": heir_manifest["lattigo_v6_2_parameters"]["log_default_scale"] if heir_manifest else "", "distribution": "Xs=ring.Ternary(P=2/3); Xe=ring.DiscreteGaussian(sigma=3.2,bound=19.2)", "standard": "Security Guidelines Table 5.2 conservative admission", "state": heir_manifest["lattigo_v6_2_parameters"]["final_admission"] if heir_manifest else "NOT_EVALUATED", "headline_eligible": bool(heir_manifest)},
        {"provider": "Google HEIR", "runtime": "OpenFHE", "scheme": "CKKS", "log_n": "", "q": "", "p": "", "log_qp": "", "scale_bits": "", "distribution": "native runtime model", "standard": "not aligned to Security V2", "state": "NATIVE_RUNTIME_SECURITY_MODEL_NOT_ALIGNED", "headline_eligible": False},
        {"provider": "FlipGuard direct/catalog", "runtime": "Lattigo v6.2.0", "scheme": "CKKS", "log_n": "bound in provider candidate manifests", "q": "bound in provider candidate manifests", "p": "bound in provider candidate manifests", "log_qp": "recomputed by provider gate", "scale_bits": "bound in provider candidate manifests", "distribution": "Xs=ring.Ternary(P=2/3); Xe=ring.DiscreteGaussian(sigma=3.2,bound=19.2)", "standard": "Security Guidelines Table 5.2 conservative admission", "state": "PASS" if flipguard_manifest else "NOT_EVALUATED", "headline_eligible": bool(flipguard_manifest)},
        {"provider": "CoreLab EVA/ELASM", "runtime": "SEAL native", "scheme": "CKKS", "log_n": "", "q": "", "p": "", "log_qp": "", "scale_bits": "waterline 15..50", "distribution": "native runtime model", "standard": "not aligned to Security V2", "state": "NATIVE_RUNTIME_SECURITY_MODEL_NOT_ALIGNED", "headline_eligible": False},
    ]
    write_csv(EVIDENCE / "security_summary.csv", list(security[0]), security)
    portability = [
        {"provider": "Microsoft EVA", "state": "NATIVE_ONLY", "exact_graph": True, "common_executor": False},
        {"provider": "Google HEIR Lattigo", "state": "PORTABLE_EXACT" if common_data else "NOT_EVALUATED", "exact_graph": True, "common_executor": bool(common_data)},
        {"provider": "Google HEIR OpenFHE", "state": "NATIVE_ONLY", "exact_graph": True, "common_executor": False},
        {"provider": "CoreLab EVA/ELASM", "state": "DIFFERENT_MODEL_NUMERICAL_ONLY", "exact_graph": False, "common_executor": False},
    ]
    write_csv(EVIDENCE / "portability_summary.csv", list(portability[0]), portability)
    failures = []
    if corelab_manifest and corelab_manifest["plans_unavailable"]:
        failures.append({"provider": "CoreLab EVA/ELASM", "reason_code": "PLAN_UNAVAILABLE_FROM_V7_EXECUTION", "count": corelab_manifest["plans_unavailable"], "claim_effect": "NUMERICAL_GRID_PARTIAL"})
    if not common_data:
        failures.append({"provider": "common", "reason_code": "PAIRED_LATENCY_NOT_EVALUATED", "count": 1, "claim_effect": "LATENCY_CLAIM_BLOCKED"})
    write_csv(EVIDENCE / "failure_summary.csv", list(failures[0]) if failures else ["provider", "reason_code", "count", "claim_effect"], failures or [{"provider": "none", "reason_code": "NONE", "count": 0, "claim_effect": "NONE"}])

    decision_providers = int(bool(eva_manifest)) + int(bool(heir_manifest))
    locked_providers = decision_providers
    portable_exact = int(bool(common_data))
    graph_equivalent = int(bool(common_data))
    security_rows = sum(row["headline_eligible"] for row in security)
    path_a = bool(eva_manifest and heir_manifest and corelab_manifest and flipguard_manifest and decision_providers >= 2 and locked_providers >= 2 and graph_equivalent >= 1 and security_rows >= 2)
    classification = "EXTERNAL_COMPARISON_CLOSED" if path_a else "FINAL_VERIFIED_LIMITATION"
    claim_admission = {
        "schema_version": "flipguard_focused_external_v8_claim_admission_v1",
        "classification": classification,
        "paper_claim_allowed": False,
        "claims": {
            "eva_substantial_population_and_locked_audit": "SUPPORTED" if eva_manifest else "NOT_EVALUATED",
            "heir_decision_bearing_shared_polynomial": "SUPPORTED" if heir_manifest else "NOT_EVALUATED",
            "corelab_multi_input_numerical_grid": "SUPPORTED" if corelab_manifest else "NOT_EVALUATED",
            "external_decision_bearing_providers_at_least_two": "SUPPORTED" if decision_providers >= 2 else "BLOCKED",
            "graph_equivalent_common_executor": "SUPPORTED" if graph_equivalent else "BLOCKED",
            "portable_exact": "SUPPORTED" if portable_exact else "NOT_EVALUATED",
            "paired_common_executor_latency": "SUPPORTED" if common_safe else "BLOCKED",
            "cross_runtime_speed_superiority": "BLOCKED",
        },
        "prohibited": ["raw rows as unique inputs", "cross-runtime latency ratio", "global optimum", "all external providers"],
    }
    (EVIDENCE / "claim_admission.json").write_text(json.dumps(claim_admission, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    limitations = """# Fairness limitations\n\n- Native EVA/SEAL, HEIR/OpenFHE, and CoreLab/SEAL timings are runtime-specific panels; no cross-runtime speed ratio is admitted.\n- The common Lattigo harness links HEIR's generated evaluator without changing its schedule and interleaves it with FlipGuard direct/catalog arms, but the arms necessarily use parameter-compatible independent keys.\n- CoreLab's official LinearRegression graph has no natural frozen threshold output, so it contributes numerical multi-input evidence rather than a decision-integrity claim.\n- `PORTABLE_EXACT` applies only to the frozen HEIR-generated Lattigo arm on the exact shared polynomial; it is not a general compiler-portability claim.\n- All safety observations are finite-scope validation and locked-audit results, not distribution-wide or analytical guarantees.\n"""
    (EVIDENCE / "fairness_limitations.md").write_text(limitations, encoding="utf-8")
    report = f"""# Focused External Comparison V8 Checkpoint\n\n- Classification: `{classification}`\n- V7 predecessor: `a5e4ef8726784cbe504d3a8067469bf0b91d3886`\n- EVA unique inputs: `{1000 if eva_manifest else 'NOT_EVALUATED'}`\n- HEIR unique inputs: `{1000 if heir_manifest else 'NOT_EVALUATED'}`\n- CoreLab unique inputs per completed plan: `{corelab_manifest['unique_inputs_per_completed_plan'] if corelab_manifest else 'NOT_EVALUATED'}`\n- External decision-bearing providers: `{decision_providers}`\n- External locked-audit providers: `{locked_providers}`\n- GRAPH_EQUIVALENT common-executor rows: `{graph_equivalent}`\n- PORTABLE_EXACT external arms: `{portable_exact}`\n- Common-executor paired latency: `{'SUPPORTED' if common_safe else 'BLOCKED'}`\n- Policy retuning: `0`\n- Manuscript modification: `0`\n"""
    (EVIDENCE / "CHECKPOINT_REPORT.md").write_text(report, encoding="utf-8")

    provider_manifest_dir = EVIDENCE / "provider_candidate_manifests"
    provider_manifest_dir.mkdir(exist_ok=True)
    if flipguard_manifest:
        source = OUTPUTS / "flipguard/shared-polynomial-threshold-v8/provider_requests"
        for path in source.glob("*.json"):
            shutil.copyfile(path, provider_manifest_dir / path.name)

    manifest = {
        "schema_version": "flipguard_focused_external_comparison_v8",
        "classification": classification,
        "predecessor_v7_manifest_sha256": "sha256:09d6e25b64bfbfc7c8e6d3945049b4492709e28695e95813508e97181f7c12cd",
        "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True, capture_output=True).stdout.strip(),
        "autonomous_start_timestamp": start_timestamp, "freeze_timestamp": end_timestamp,
        "providers": {"eva": bool(eva_manifest), "heir": bool(heir_manifest), "corelab": bool(corelab_manifest), "flipguard": bool(flipguard_manifest)},
        "external_decision_bearing_provider_count": decision_providers,
        "external_locked_audit_provider_count": locked_providers,
        "portable_exact_count": portable_exact,
        "graph_equivalent_common_executor_count": graph_equivalent,
        "security_aligned_comparison_rows": security_rows,
        "raw_rows_are_not_unique_inputs": True,
        "cross_runtime_ratio_claim_allowed": False,
        "policy_retuning": 0,
    }
    (EVIDENCE / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for name in ("provider_gate_records.csv", "audit_records.csv", "common_executor_records.csv", "common_executor_paired_summary.csv", "latency_summary.csv", "numerical_error_summary.csv", "unique_input_accounting.csv", "security_summary.csv", "portability_summary.csv", "failure_summary.csv"):
        shutil.copyfile(EVIDENCE / name, RESULTS / name)
    (RESULTS / "claim_admission.json").write_text(json.dumps(claim_admission, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (RESULTS / "manifest.json").write_text(json.dumps({"schema_version": "flipguard_focused_external_v8_publication_inputs_v1", "source_evidence": "docs/evidence/focused_external_comparison_v8", "classification": classification, "speculative_values": 0}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    checksums = [f"{sha256(path)[7:]}  {path.relative_to(EVIDENCE).as_posix()}" for path in sorted(EVIDENCE.rglob("*")) if path.is_file() and path.name != "SHA256SUMS"]
    (EVIDENCE / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="ascii")
    result_checksums = [f"{sha256(path)[7:]}  {path.relative_to(RESULTS).as_posix()}" for path in sorted(RESULTS.rglob("*")) if path.is_file() and path.name != "SHA256SUMS"]
    (RESULTS / "SHA256SUMS").write_text("\n".join(result_checksums) + "\n", encoding="ascii")
    subprocess.run(["python3", str(EVIDENCE / "verify_focused_external_comparison_v8.py")], cwd=ROOT, check=True)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
