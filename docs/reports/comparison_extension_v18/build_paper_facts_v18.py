#!/usr/bin/env python3
"""Build the deterministic, manuscript-facing V18 facts overlay."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / "docs/reports/comparison_extension_v18"
RESULT = ROOT / "results/comparison_extension_v18"
V17 = ROOT / "results/model_family_expansion_v17/final_vm1x6"
V8 = ROOT / "docs/evidence/focused_external_comparison_v8"
V18_EVIDENCE = ROOT / "docs/evidence/comparison_extension_v18"

EXPECTED_PACKAGE_PAYLOAD = "884d979087b62a1f4e2ca066902f4deb603589dbff6fd5349c57bead5539aded"
EXPECTED_MANIFEST_SHA256 = "a86427207d5525a83036f0a99e3bf6888f9e21b0219a489af3d1ac8fb1fa7e50"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def quantile(values: Iterable[float], q: float) -> float:
    data = sorted(values)
    if not data:
        raise ValueError("empty quantile")
    if len(data) == 1:
        return data[0]
    position = (len(data) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return data[low]
    return data[low] + (data[high] - data[low]) * (position - low)


def stats(values: Iterable[float]) -> dict[str, float | int]:
    data = list(values)
    q1, q3 = quantile(data, 0.25), quantile(data, 0.75)
    return {
        "n": len(data),
        "median": statistics.median(data),
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1,
        "p90": quantile(data, 0.90),
        "minimum": min(data),
        "maximum": max(data),
    }


def bit_list(value: str) -> list[int]:
    return [int(part) for part in value.split(";") if part]


def true(value: str) -> bool:
    return value.lower() == "true"


def external_facts() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    eligibility = read_csv(V18_EVIDENCE / "comparator_eligibility_matrix.csv")
    security_rows = read_csv(V8 / "security_summary.csv")
    heir = read_csv(V8 / "heir_shared_polynomial_records.csv")
    heir_audit = [
        row for row in heir
        if row["runtime"] == "Lattigo-v6.2.0-translation" and row["role"] == "locked_audit"
    ]
    common = [row for row in read_csv(V8 / "common_executor_records.csv") if row["arm"] == "heir_generated"]
    latency_summary = next(
        row for row in read_csv(V8 / "latency_summary.csv") if row["provider"] == "heir_generated"
    )
    eva = read_csv(V8 / "eva_population_records.csv")
    core_status = read_csv(V8 / "corelab_plan_status.csv")

    heir_sec = next(
        row for row in security_rows
        if row["provider"] == "Google HEIR" and row["runtime"] == "Lattigo v6.2.0"
    )
    common_totals = sorted(float(row["total_ms"]) for row in common)
    common_mean = statistics.mean(common_totals)
    common_median = statistics.median(common_totals)
    common_p95 = common_totals[math.ceil(0.95 * len(common_totals)) - 1]
    assert math.isclose(common_mean, float(latency_summary["mean_total_ms"]), rel_tol=0, abs_tol=1e-12)
    assert math.isclose(common_median, float(latency_summary["median_total_ms"]), rel_tol=0, abs_tol=1e-12)
    assert math.isclose(common_p95, float(latency_summary["p95_total_ms"]), rel_tol=0, abs_tol=1e-12)
    heir_summary = {
        "workload": "shared_polynomial_threshold_v8",
        "candidate_id": "heir_lattigo_v6_2_shared_polynomial",
        "runtime": "Lattigo v6.2.0",
        "log_n": int(heir_sec["log_n"]),
        "q": json.loads(heir_sec["q"]),
        "p": json.loads(heir_sec["p"]),
        "log_qp": float(heir_sec["log_qp"]),
        "scale_bits": int(heir_sec["scale_bits"]),
        "security_state": heir_sec["state"],
        "audit_unique_inputs": len({row["row_id"] for row in heir_audit}),
        "audit_observations": len(heir_audit),
        "audit_contexts": len({row["context"] for row in heir_audit}),
        "audit_decision_flip_events": sum(true(row["decision_flip"]) for row in heir_audit),
        "audit_reserve_violation_events": sum(true(row["reserve_violation"]) for row in heir_audit),
        "audit_max_absolute_error": max(float(row["absolute_error"]) for row in heir_audit),
        "common_executor_observations": len(common),
        "common_executor_mean_total_ms": common_mean,
        "common_executor_median_total_ms": common_median,
        "common_executor_p95_total_ms": common_p95,
        "latency_claim_state": "BLOCKED_DIAGNOSTIC_UNSAFE_PAIRED_DIRECT_ARM",
    }

    eva_summaries = []
    for scale, role in [
        (20, "configuration_validation"),
        (30, "configuration_validation"),
        (30, "locked_audit"),
        (40, "configuration_validation"),
        (40, "locked_audit"),
    ]:
        group = [row for row in eva if int(row["scale_bits"]) == scale and row["role"] == role]
        eva_summaries.append(
            {
                "scale_bits": scale,
                "role": role,
                "candidate_id": group[0]["candidate_id"],
                "unique_inputs": len({row["row_id"] for row in group}),
                "observations": len(group),
                "contexts": len({row["context_index"] for row in group}),
                "decision_flip_events": sum(true(row["decision_flip"]) for row in group),
                "decision_flip_unique_inputs": len({row["row_id"] for row in group if true(row["decision_flip"])}),
                "reserve_violation_events": sum(true(row["reserve_policy_violation"]) for row in group),
                "reserve_violation_unique_inputs": len({row["row_id"] for row in group if true(row["reserve_policy_violation"])}),
                "max_absolute_error": max(float(row["absolute_error"]) for row in group),
                "median_native_total_ms": statistics.median(float(row["total_ms"]) for row in group),
            }
        )

    core_counts = Counter((row["mode"], row["status"]) for row in core_status)
    external = []
    for row in eligibility:
        system = row["system"]
        entry: dict[str, Any] = {
            "system": system,
            "classification": row["classification"],
            "workload": row["workload_subset"],
            "decision_result": "NOT_AVAILABLE",
            "numerical_result": "NOT_AVAILABLE",
            "latency_result": "NOT_COMPARABLE",
            "configuration": "NOT_AVAILABLE",
            "paper_use": row["reason"],
        }
        if system == "HEIR":
            entry.update(
                decision_result="500 locked-audit inputs x 3 contexts; 0 flips; 0 reserve violations",
                numerical_result=f"locked-audit max absolute error={heir_summary['audit_max_absolute_error']:.17g}",
                latency_result=(
                    f"common-Lattigo diagnostic mean/median/p95 total ms="
                    f"{heir_summary['common_executor_mean_total_ms']:.9f}/"
                    f"{heir_summary['common_executor_median_total_ms']:.9f}/"
                    f"{heir_summary['common_executor_p95_total_ms']:.9f}; paired claim blocked"
                ),
                configuration=(
                    f"LogN=14; Q={heir_summary['q']}; P={heir_summary['p']}; "
                    f"scale=45; logQP={heir_summary['log_qp']:.12f}"
                ),
            )
        elif system == "EVA":
            e20 = next(item for item in eva_summaries if item["scale_bits"] == 20)
            e30a = next(item for item in eva_summaries if item["scale_bits"] == 30 and item["role"] == "locked_audit")
            e40a = next(item for item in eva_summaries if item["scale_bits"] == 40 and item["role"] == "locked_audit")
            entry.update(
                decision_result=(
                    f"S20 validation: {e20['decision_flip_events']}/1500 flip events over "
                    f"{e20['decision_flip_unique_inputs']}/500 unique inputs; "
                    "S30/S40 locked audit: 0/1500 flips each"
                ),
                numerical_result=(
                    f"max abs error S20 validation={e20['max_absolute_error']:.17g}; "
                    f"S30 audit={e30a['max_absolute_error']:.17g}; "
                    f"S40 audit={e40a['max_absolute_error']:.17g}"
                ),
                latency_result="native SEAL latency only; no Lattigo speed ratio",
                configuration="native EVA scale settings S20/S30/S40",
            )
        elif system == "ELASM":
            entry.update(
                decision_result="No matching threshold/argmax output contract",
                numerical_result=f"34/36 ELASM plans completed; 6800 rows over 200 inputs per completed plan",
                latency_result="native CoreLab/SEAL numerical panel only",
                configuration="waterline 15..50 plan grid",
            )
        elif system == "HECATE":
            entry.update(
                decision_result="No exact V17 decision-bearing output",
                numerical_result="No exact HECATE decision row admitted to V18",
                latency_result="not a V18 direct decision baseline",
                configuration="official objective documented; exact V17 mapping unavailable",
            )
        external.append(entry)

    assert core_counts[("eva", "PASS")] == 36
    assert core_counts[("elasm", "PASS")] == 34
    assert core_counts[("elasm", "EXECUTION_FAILED")] == 2
    return external, {"heir": heir_summary, "eva": eva_summaries, "corelab_status_counts": {f"{a}:{b}": n for (a, b), n in sorted(core_counts.items())}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPORT,
        help="Directory for the nine deterministic manuscript-facing outputs.",
    )
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = V18_EVIDENCE / "manifest.json"
    assert sha256(manifest_path) == EXPECTED_MANIFEST_SHA256
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["package_payload_sha256"] == EXPECTED_PACKAGE_PAYLOAD

    cases = [row for row in read_csv(RESULT / "case_level_ledger.csv") if row["scope"] == "primary"]
    candidates = read_csv(RESULT / "candidate_level_ledger.csv")
    numerical = read_csv(RESULT / "table_numerical_objective_diagnostics.csv")
    metrics = json.loads((RESULT / "metrics.json").read_text(encoding="utf-8"))
    assert len(cases) == 68
    direct_candidates = {
        (row["case_id"], row["candidate_id"]): row
        for row in candidates if row["candidate_source"] == "direct"
    }
    finite_candidates = {
        (row["case_id"], row["candidate_id"]): row
        for row in candidates if row["candidate_source"] == "finite_reference"
    }

    categories: dict[str, list[str]] = defaultdict(list)
    gate_rows = []
    stability_rows = []
    changed = []
    observed_gateoff_status = Counter()
    full_separate_status = Counter()
    formal_differences = []
    for case in cases:
        flips = int(case["c2_selection_flips"])
        violations = int(case["c2_selection_violations"])
        if flips and violations:
            category = "FLIP_AND_VIOLATION"
        elif flips:
            category = "FLIP_ONLY"
        elif violations:
            category = "VIOLATION_ONLY"
        else:
            category = "NO_FLIP_NO_VIOLATION"
        categories[category].append(case["case_id"])
        observed_gateoff_status[case["c2_separate_status"]] += 1
        full_separate_status[case["c1_separate_status"]] += 1
        gate = direct_candidates[(case["case_id"], case["c2_candidate_id"])]
        full = direct_candidates[(case["case_id"], case["c1_candidate_id"])]
        finite = finite_candidates[(case["case_id"], case["c6_fastest_acceptable_candidate"])]
        extra = int(case["c1_candidate_evaluations"]) - int(case["c2_candidate_evaluations"])
        ratio: float | str = "SAME_LITERAL"
        if case["c1_candidate_id"] != case["c2_candidate_id"]:
            ratio = float(full["selection_stage_mean_total_ms"]) / float(gate["selection_stage_mean_total_ms"])
        before_q, after_q = bit_list(gate["ordered_q"]), bit_list(full["ordered_q"])
        before_p, after_p = bit_list(gate["ordered_p"]), bit_list(full["ordered_p"])
        row = {
            "case_id": case["case_id"],
            "category": category,
            "gate_off_selection_flips": flips,
            "gate_off_reserve_violations": violations,
            "gate_off_candidate_id": case["c2_candidate_id"],
            "full_candidate_id": case["c1_candidate_id"],
            "gate_off_candidate_evaluations": int(case["c2_candidate_evaluations"]),
            "full_candidate_evaluations": int(case["c1_candidate_evaluations"]),
            "additional_candidate_evaluations": extra,
            "gate_off_separate_input_status": case["c2_separate_status"],
            "full_separate_input_status": case["c1_separate_status"],
            "gate_off_log_n": int(gate["log_n"]),
            "full_log_n": int(full["log_n"]),
            "gate_off_q_bits": gate["ordered_q"],
            "full_q_bits": full["ordered_q"],
            "gate_off_q_chain_length": len(before_q),
            "full_q_chain_length": len(after_q),
            "gate_off_p_bits": gate["ordered_p"],
            "full_p_bits": full["ordered_p"],
            "gate_off_scale_bits": int(gate["initial_scale"]),
            "full_scale_bits": int(full["initial_scale"]),
            "gate_off_path": gate["path"],
            "full_path": full["path"],
            "q_prime_count_delta": len(after_q) - len(before_q),
            "q_total_bits_delta": sum(after_q) - sum(before_q),
            "scale_bits_delta": int(full["initial_scale"]) - int(gate["initial_scale"]),
            "log_n_delta": int(full["log_n"]) - int(gate["log_n"]),
            "selection_stage_full_over_gate_off_observed_latency_ratio": ratio,
            "latency_measurement_class": "SELECTION_STAGE_OBSERVATIONAL_NOT_FORMAL",
            "gate_off_full_selection_wall_clock_pair": "NOT_RECONSTRUCTABLE_FROM_V17_STAGE_BOUNDARIES",
        }
        gate_rows.append({key: row[key] for key in [
            "case_id", "category", "gate_off_selection_flips", "gate_off_reserve_violations",
            "gate_off_candidate_id", "full_candidate_id", "gate_off_separate_input_status",
        ]})
        stability_rows.append(row)
        if extra:
            changed.append(row)
        formal_differences.append(
            float(full["formal_paired_median_total_ms"]) - float(finite["formal_paired_median_total_ms"])
        )

    assert len(categories["NO_FLIP_NO_VIOLATION"]) == 47
    assert len(categories["FLIP_ONLY"]) == 0
    assert len(categories["VIOLATION_ONLY"]) == 1
    assert len(categories["FLIP_AND_VIOLATION"]) == 20
    assert len(changed) == 21
    assert observed_gateoff_status == Counter({"SAFE": 47, "NOT_EVALUATED": 21})
    assert full_separate_status == Counter({"SAFE": 68})
    changed_ratios = [float(row["selection_stage_full_over_gate_off_observed_latency_ratio"]) for row in changed]
    wall_stats = metrics["selection_wall_clock_ratio_finite_over_direct_case_distribution"]

    fastest_cross = Counter()
    minimum_cross = Counter()
    for row in numerical:
        fastest_cross[(int(row["fastest_executable_flips"]) > 0, int(row["fastest_executable_violations"]) > 0)] += 1
        minimum_cross[(int(row["minimum_error_flips"]) > 0, int(row["minimum_error_violations"]) > 0)] += 1
    traditional_summary = {
        "fastest_executable_union_unstable_cases": sum(n for (flip, violation), n in fastest_cross.items() if flip or violation),
        "fastest_executable_flip_cases": sum(n for (flip, _), n in fastest_cross.items() if flip),
        "fastest_executable_violation_cases": sum(n for (_, violation), n in fastest_cross.items() if violation),
        "minimum_error_union_unstable_cases": sum(n for (flip, violation), n in minimum_cross.items() if flip or violation),
        "minimum_error_flip_cases": sum(n for (flip, _), n in minimum_cross.items() if flip),
        "minimum_error_violation_cases": sum(n for (_, violation), n in minimum_cross.items() if violation),
        "pareto_candidate_count": sum(int(row["pareto_candidates"]) for row in numerical),
        "unstable_pareto_candidate_count": sum(int(row["unstable_pareto_candidates"]) for row in numerical),
        "unstable_pareto_case_count": sum(int(row["unstable_pareto_candidates"]) > 0 for row in numerical),
        "fastest_executable_differs_from_proposed_cases": sum(row["fastest_executable_candidate"] != row["proposed_candidate"] for row in numerical),
        "minimum_error_differs_from_proposed_cases": sum(row["minimum_error_candidate"] != row["proposed_candidate"] for row in numerical),
        "finite_fastest_acceptable_differs_from_proposed_cases": sum(row["finite_fastest_acceptable_candidate"] != row["proposed_candidate"] for row in numerical),
    }
    representative = {
        "case_id": "primary|digits_binary|linear_poly3|outer_fold_2_training_seed_0",
        "candidate_id": "synth_repair_scale_2_rescale_N14_Q7_S28_bbf9e9983d20",
        "max_absolute_error": 0.001058334440351416,
        "rms_error": 0.0010357391543471598,
        "decision_flips": 0,
        "reserve_policy_violations": 18,
        "sample_id": "239",
        "key_repeat": 3,
        "margin": 0.0014297481310502347,
        "observed_error": 0.0010361468174261423,
        "rho_margin_budget": 0.0007148740655251173,
        "normalized_budget_usage": 1.4494116759782454,
    }

    traditional_rows = []
    for row in numerical:
        traditional_rows.append(
            {
                **row,
                "fastest_executable_unstable": int(row["fastest_executable_flips"]) > 0 or int(row["fastest_executable_violations"]) > 0,
                "minimum_error_unstable": int(row["minimum_error_flips"]) > 0 or int(row["minimum_error_violations"]) > 0,
                "fastest_executable_differs_from_proposed": row["fastest_executable_candidate"] != row["proposed_candidate"],
                "minimum_error_differs_from_proposed": row["minimum_error_candidate"] != row["proposed_candidate"],
                "representative_small_error_violation": row["case_id"] == representative["case_id"],
            }
        )

    external_rows, external_detail = external_facts()
    finite = metrics["finite_reference"]
    facts = {
        "schema_version": "flipguard_paper_facts_v18_locked_v1",
        "status": "V18 PAPER FACTS LOCKED — READY FOR MANUSCRIPT INTEGRATION",
        "source_binding": {
            "v18_package_payload_sha256": EXPECTED_PACKAGE_PAYLOAD,
            "v18_manifest_sha256": EXPECTED_MANIFEST_SHA256,
            "v18_protocol_sha256": metrics["protocol_sha256"],
            "scientific_execution_source_commit": "cefc44b0d7e351db2a34886dd758a2d31a3e4c12",
            "aggregation_tooling_commit": "86b0403208abbc741a65934358a5dea4a66e4d88",
            "new_encrypted_candidate_evaluations": 0,
        },
        "gate_off_cross_table": {
            "no_flip_no_violation": {"count": len(categories["NO_FLIP_NO_VIOLATION"]), "case_ids": categories["NO_FLIP_NO_VIOLATION"]},
            "flip_only": {"count": len(categories["FLIP_ONLY"]), "case_ids": categories["FLIP_ONLY"]},
            "violation_only": {"count": len(categories["VIOLATION_ONLY"]), "case_ids": categories["VIOLATION_ONLY"]},
            "flip_and_violation": {"count": len(categories["FLIP_AND_VIOLATION"]), "case_ids": categories["FLIP_AND_VIOLATION"]},
            "union_flip_or_violation": {"count": 21, "case_ids": sorted(categories["FLIP_ONLY"] + categories["VIOLATION_ONLY"] + categories["FLIP_AND_VIOLATION"])},
        },
        "cost": {
            "gate_off_candidate_evaluations": 68,
            "full_candidate_evaluations": 89,
            "additional_candidate_evaluations": 21,
            "cases_with_zero_additional_evaluations": 47,
            "cases_recovered_with_exactly_one_additional_evaluation": 21,
            "cases_requiring_two_or_more_additional_evaluations": 0,
            "gate_off_full_selection_wall_clock_pair": "NOT_RECONSTRUCTABLE_FROM_V17_STAGE_BOUNDARIES",
            "finite_reference_over_full_selection_wall_clock_ratio": wall_stats,
            "finite_reference_over_full_selection_wall_clock_ratio_direction": "finite_reference/full_method",
            "changed_case_selection_stage_full_over_gate_off_latency_ratio": stats(changed_ratios),
            "changed_case_latency_measurement_class": "SELECTION_STAGE_OBSERVATIONAL_NOT_FORMAL",
        },
        "configuration_change": {
            "changed_case_count": 21,
            "scale_plus_4_case_count": sum(row["scale_bits_delta"] == 4 for row in changed),
            "q_prime_plus_1_case_count": sum(row["q_prime_count_delta"] == 1 for row in changed),
            "scale_plus_4_and_q_prime_plus_1_case_count": sum(row["scale_bits_delta"] == 4 and row["q_prime_count_delta"] == 1 for row in changed),
            "log_n_changed_case_count": sum(row["log_n_delta"] != 0 for row in changed),
            "q_chain_length_changed_case_count": sum(row["gate_off_q_chain_length"] != row["full_q_chain_length"] for row in changed),
            "q_total_bits_delta": stats(float(row["q_total_bits_delta"]) for row in changed),
            "scale_bits_delta": stats(float(row["scale_bits_delta"]) for row in changed),
            "case_literals": changed,
        },
        "gate_off_separate_input": {
            "observed_case_count": 47,
            "pass": observed_gateoff_status["SAFE"],
            "rejected": observed_gateoff_status["REJECTED"],
            "failed": observed_gateoff_status["FAILED"],
            "not_evaluated": observed_gateoff_status["NOT_EVALUATED"],
            "not_evaluated_reason": "The 21 initial literals were rejected during selection and V17 promoted only selected literals to candidate-specific separate-input evaluation.",
            "not_evaluated_counted_as_failure": False,
        },
        "traditional_objectives": {**traditional_summary, "representative_small_error_violation": representative},
        "external_comparators": external_detail,
        "external_class_counts": metrics["external_comparator_counts"],
        "finite_reference": {
            "direct_evaluations": 89,
            "finite_reference_evaluations": 537,
            "candidate_evaluation_reduction": metrics["candidate_evaluation_reduction"],
            "false_no_safe": finite["false_no_safe"],
            "formal_latency_regret": finite["formal_latency_regret"],
            "formal_total_latency_difference_ms": stats(formal_differences),
            "finite_over_direct_total_latency_ratio": finite["formal_finite_over_direct_total_ratio_cluster_bootstrap"],
            "superiority_claim": False,
            "claim_state": "NEAR_REFERENCE_SELECTION_QUALITY_NO_SUPERIORITY",
        },
    }

    write_csv(output_dir / "V18_GATE_EFFECT_TABLE.csv", gate_rows)
    write_csv(output_dir / "V18_STABILITY_COST_TABLE.csv", stability_rows)
    write_csv(output_dir / "V18_EXTERNAL_COMPARISON_TABLE.csv", external_rows)
    write_csv(output_dir / "V18_TRADITIONAL_OBJECTIVE_DIAGNOSTICS.csv", traditional_rows)
    (output_dir / "PAPER_FACTS_V18_LOCKED.json").write_text(
        json.dumps(facts, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    ratio = facts["cost"]["changed_case_selection_stage_full_over_gate_off_latency_ratio"]
    regret = facts["finite_reference"]["formal_latency_regret"]
    difference = facts["finite_reference"]["formal_total_latency_difference_ms"]
    cluster = facts["finite_reference"]["finite_over_direct_total_latency_ratio"]
    locked_md = f"""# V18 Paper Facts Locked

Status: `V18 PAPER FACTS LOCKED — READY FOR MANUSCRIPT INTEGRATION`

## Immutable binding

- V18 package payload SHA-256: `{EXPECTED_PACKAGE_PAYLOAD}`
- V18 manifest SHA-256: `{EXPECTED_MANIFEST_SHA256}`
- New encrypted candidate evaluations: `0`

## 1. Gate-off cross table

| Gate-off state | Cases |
|---|---:|
| No flip, no violation | 47 |
| Flip only | 0 |
| Violation only | 1 |
| Flip and violation | 20 |
| Union: flip or violation | 21 |

The exact case IDs are recorded in `PAPER_FACTS_V18_LOCKED.json` and
`V18_GATE_EFFECT_TABLE.csv`. The violation-only case is
`primary|mnist_binary01|packed_cnn_lite_binary01_v17|v17_p6_packed_cnn_lite`.

## 2. Gate-off versus full cost

Gate-off used 68 candidate evaluations; the full method used 89. Forty-seven
cases needed no additional evaluation, 21 recovered with exactly one additional
evaluation, and none required two or more. An exact paired gate-off/full
selection wall-clock cannot be reconstructed because V17 did not record a
stage-complete wall-clock boundary after the rejected first trial. It is locked
as `NOT_RECONSTRUCTABLE_FROM_V17_STAGE_BOUNDARIES`, not estimated.

For context, the separately measured finite-reference/full selection wall-clock
ratio over 66 cases had median `{wall_stats['median']:.9f}`, IQR
`{wall_stats['iqr']:.9f}`, and p90 `{wall_stats['p90']:.9f}`. Its direction is
finite-reference divided by full method; it is not a gate-off/full statistic.

For the 21 changed cases, the observed selected-candidate mean-total-latency
ratio full/gate-off had median `{ratio['median']:.9f}`, IQR
`{ratio['iqr']:.9f}`, p90 `{ratio['p90']:.9f}`, and maximum
`{ratio['maximum']:.9f}`. These are selection-stage observations, not formal
paired inference latency.

## 3. Configuration change

All 21 changes increased scale by 4 bits. Q-prime count increased in 0 cases,
so scale +4 and Q-prime +1 co-occurred in 0 cases. LogN and Q-chain length
changed in 0 cases. The Q-chain retained its prime count while total declared Q
bits increased by 28 in 20 `linear_poly3` cases and 24 in the packed-CNN case.
Every before/after literal is in `V18_STABILITY_COST_TABLE.csv` and the JSON.

## 4. Gate-off separate-input outcome

Candidate-specific separate-input results are observed for 47 cases: 47 PASS,
0 REJECTED, and 0 FAILED. The remaining 21 are `NOT_EVALUATED` because their
initial literals failed the selection gate and V17 advanced only selected
literals to that stage. `NOT_EVALUATED` is not counted as failure.

## 5. Traditional objectives

The fastest executable candidate had flips and violations in 18/68 cases; no
flip-only or violation-only fastest case occurred. It differed from the proposed
selection in 23 cases. The minimum-error candidate had no flip or violation in
68/68 cases but differed from the proposed selection in all 68. The 279
case-level error-latency Pareto candidates included 28 unstable candidates in 20
cases. The finite fastest acceptable candidate differed from the proposed
candidate in 5 cases.

Representative small-error violation: in
`{representative['case_id']}`, candidate `{representative['candidate_id']}` had
maximum absolute error `{representative['max_absolute_error']:.17g}` and zero
flips but 18 reserve violations. For sample 239/key repeat 3, absolute error
`{representative['observed_error']:.17g}` exceeded rho x margin budget
`{representative['rho_margin_budget']:.17g}` (usage
`{representative['normalized_budget_usage']:.9f}`).

## 6. External comparison

HEIR's exact shared-polynomial Lattigo arm uses LogN 14, Q
`{external_detail['heir']['q']}`, P `{external_detail['heir']['p']}`, scale 45,
and Security-V2 state PASS. Its locked audit has 500 inputs x 3 contexts, zero
flips, zero violations, and maximum absolute error
`{external_detail['heir']['audit_max_absolute_error']:.17g}`. Common-Lattigo
diagnostic mean/median/p95 total latency is
`{external_detail['heir']['common_executor_mean_total_ms']:.9f}` /
`{external_detail['heir']['common_executor_median_total_ms']:.9f}` /
`{external_detail['heir']['common_executor_p95_total_ms']:.9f}` ms. The paired
speed claim remains blocked because the paired direct arm was unstable.

EVA S20 validation produced 133 flip events over 1,500 observations, affecting
114/500 unique inputs, and maximum absolute error 1.2114988677117884. S30 and
S40 each had zero flips and violations on the 500-input x 3-context locked
audit; audit maximum errors were 0.0020735645861611196 and
3.0338053744749516e-06. EVA latency remains native-SEAL-only. HECATE lacks an
exact V17 decision output, while ELASM's 34/36 completed CoreLab plans expose
numerical error and native latency but no matching threshold/argmax contract.

The seven related-work-only entries are CHET (no verified exact executable
mapping), DaCapo (bootstrapping objective not applicable), Orion (model/packing
identity mismatch), FHE-Agent (no verified official runnable artifact), Lattigo
(backend library), Microsoft SEAL (manual example), and OpenFHE (context API
guide).

## 7. Finite reference

- Direct / finite evaluations: 89 / 537
- Offline finite-reference burden avoided: 83.426443%
- False NO_SAFE: 0
- Formal latency regret median/IQR/p90/max:
  `{regret['median']:.12f}` / `{regret['iqr']:.12f}` /
  `{regret['p90']:.12f}` / `{regret['maximum']:.12f}`
- Formal direct-minus-finite median-total difference in ms, median/IQR/p90/max:
  `{difference['median']:.9f}` / `{difference['iqr']:.9f}` /
  `{difference['p90']:.9f}` / `{difference['maximum']:.9f}`
- Dataset-model cluster finite/direct total-latency ratio:
  `{cluster['estimate']:.12f}`, 95% CI
  `[{cluster['ci_low']:.12f}, {cluster['ci_high']:.12f}]`

The confidence interval includes 1. The admitted conclusion is near-reference
selection quality, not latency superiority, practical exhaustive-search
speedup, or global optimality.
"""
    (output_dir / "PAPER_FACTS_V18_LOCKED.md").write_text(locked_md, encoding="utf-8")

    storyline = """# V18 Paper Storyline (KO/EN)

## Korean

V18의 중심 비교는 외부 시스템 수를 늘리는 것이 아니라 결정 안정성
검사의 인과적 역할을 분리하는 것이다. 동일한 직접 합성 순서에서 이
검사를 제거하면 68개 첫 후보가 모두 실행 가능했지만, 20개 사례에서는
판단 반전이, 21개 사례에서는 운용 오차 예산 위반이 관찰되었다.
FlipGuard는 21회의 추가 암호화 후보 평가로 21개 구성을 변경했고, 최종
68개 구성은 모두 분리 입력 평가를 통과했다.

이 비용은 제한적이었다. 변경된 구성은 모두 scale이 4 bit 증가했지만
Q prime 수, Q-chain 길이, LogN은 증가하지 않았다. 관측된 후보 latency
ratio는 selection-stage 진단이며 formal paired latency가 아니다. 유한
참조는 운영 baseline이 아니라 false NO_SAFE와 선택 품질을 확인하는
오프라인 기준이다. Direct는 89회, 유한 참조는 537회를 사용했고, 최종
latency는 참조의 가장 빠른 적합 구성과 통계적으로 구별되는 우월성을
보이지 않았다.

외부 비교는 적격성에 따라 분리한다. HEIR는 하나의 exact workload,
EVA는 output-comparable workload, HECATE/ELASM은 numerical-only evidence,
나머지 7개는 관련 연구로만 사용한다. 이 구조는 비교 폭보다 공정한
동일성 조건을 우선한다.

## English

V18 does not maximize the number of named external systems. It isolates the
causal role of the decision-stability gate under the same direct-synthesis
sequence. Removing the gate made all 68 initial candidates execution-valid,
but 20 cases exhibited decision flips and 21 violated the operational error
budget. FlipGuard spent 21 additional encrypted candidate evaluations, changed
21 configurations, and all 68 final configurations passed separate-input
evaluation.

The adaptation was bounded: every changed configuration added four scale bits,
while Q-prime count, Q-chain length, and LogN remained unchanged. Candidate
latency ratios are selection-stage observations, not formal paired gate-off
latency. The finite reference is an offline test of missed feasibility and
selection quality, not an operating baseline. Direct selection used 89
evaluations versus 537, while final latency showed near-reference quality but no
statistically admitted superiority.

External results are stratified by eligibility: one exact HEIR workload, one
output-comparable EVA workload, two numerical-only HECATE/ELASM entries, and
seven related-work-only systems or guides. Fair identity takes precedence over
baseline count.
"""
    (output_dir / "V18_PAPER_STORYLINE_KO_EN.md").write_text(storyline, encoding="utf-8")

    replacement = """# V18 Manuscript Replacement Plan

1. Replace any finite-reference-as-practical-baseline wording with “offline
   finite reference for missed feasibility and selection-quality measurement.”
2. Lead the result section with the 47/0/1/20 gate cross table. State that the
   union contains 21 cases and list the case-level CSV as artifact support.
3. Follow with the 68-versus-89 evaluation cost and 21/21 one-step recovery.
4. State that scale increased by four bits in 21 cases, but Q-prime count,
   Q-chain length, and LogN did not change. Do not describe this as +1 Q prime.
5. Label full/gate-off candidate latency as selection-stage observational.
   Formal gate-off/full selection wall-clock and formal inference latency are
   not available.
6. Report gate-off separate-input results as 47 PASS and 21 NOT_EVALUATED. Do
   not combine NOT_EVALUATED with REJECTED or FAILED.
7. Use the traditional-objective diagnostic to show 18 unstable fastest
   candidates and 28 unstable Pareto candidates, while disclosing that the
   minimum-error candidate was stable in all 68 cases.
8. Put HEIR and EVA in separate exact/output-comparable rows. Keep the HEIR
   latency as blocked diagnostic and EVA latency native-runtime-only.
9. Report both normalized regret and absolute median-total difference. Explain
   that absolute milliseconds are heterogeneous across model families.
10. Conclude with near-reference selection quality; do not claim superiority,
    global optimality, or improvement over all CKKS tuners.

No V17/V18 number is replaced in-place by this plan. Manuscript editing consumes
the locked JSON and CSV overlay in a later stage.
"""
    (output_dir / "V18_MANUSCRIPT_REPLACEMENT_PLAN.md").write_text(replacement, encoding="utf-8")

    mapping = """# V18 Figure and Table Map

| Manuscript item | Locked source | Main message | Required qualification |
|---|---|---|---|
| Gate cross table | `V18_GATE_EFFECT_TABLE.csv` | 47 neither, 0 flip-only, 1 violation-only, 20 both | case is the statistical unit |
| Stability cost table | `V18_STABILITY_COST_TABLE.csv` | 68 vs 89; 21 one-step recoveries; literal before/after | candidate latency is selection-stage observational |
| Traditional objective table | `V18_TRADITIONAL_OBJECTIVE_DIAGNOSTICS.csv` | 18 unstable fastest; 28 unstable Pareto candidates | minimum-error is stable 68/68 |
| External comparator table | `V18_EXTERNAL_COMPARISON_TABLE.csv` | exact/output/numerical/related-work separation | no raw cross-runtime speed ranking |
| Figure: gate-state composition | `V18_GATE_EFFECT_TABLE.csv` | union=21 | do not plot raw flip events as independent samples |
| Figure: configuration delta | `V18_STABILITY_COST_TABLE.csv` | scale +4; prime count/LogN unchanged | distinguish Q bit-width from Q-prime count |
| Figure: candidate objective plane | existing `figure_error_latency_decision_overlay.csv` plus locked diagnostics | unstable fastest/Pareto candidates | diagnostic, not named-system emulation |
| Figure: finite-reference quality | existing `figure_proposed_vs_finite_latency_gap.csv` plus locked JSON | near-reference regret and CI | no superiority claim |

All headline values must be read from `PAPER_FACTS_V18_LOCKED.json`; prose may
round only after retaining the ratio direction and statistical unit.
"""
    (output_dir / "V18_FIGURE_TABLE_MAP.md").write_text(mapping, encoding="utf-8")

    print(
        "V18_PAPER_FACTS_BUILD_PASS "
        f"cases={len(cases)} changed={len(changed)} external={len(external_rows)} new_encrypted=0"
    )


if __name__ == "__main__":
    main()
