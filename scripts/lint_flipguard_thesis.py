#!/usr/bin/env python3
"""Fail-closed lint for the authoritative FlipGuard thesis draft."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path("docs/thesis")
CHAPTERS = [f"{number:02d}_{name}.md" for number, name in (
    (1, "introduction"),
    (2, "background"),
    (3, "related_work"),
    (4, "problem_and_assurance_model"),
    (5, "flipguard_design"),
    (6, "implementation"),
    (7, "evaluation_methodology"),
    (8, "results"),
    (9, "discussion_limitations"),
    (10, "reproducibility_security"),
    (11, "conclusion"),
)]
AUXILIARY_MARKDOWN = [
    "00_thesis_contract.md",
    "advisor_defense_qa.md",
    "reviewer_attack_checklist.md",
    "university_template_requirements.md",
]
EXPECTED_DIGESTS = {
    "rc2_source_commit": "6c5f8b234f9f9da91a189fa0f2dc180bb996abf5",
    "rc2_archive_sha256": "05ef70306a11ab577243b0c708489864f19ccd104e6036e28fc6bd1dab45c0be",
    "v3_manifest_sha256": "32d378b371b75d31b8e39ef2acce4c3c7353581ccfbd5e6c7d22b30ffaf4743b",
    "claim_admission_manifest_sha256": "d982f0f81915b760c537244fc71aa992bf521eaf65d57a67c2d96dbae0607b8d",
    "margin_interpretation_manifest_sha256": "12626638b1abb5d57155345ee84e7e145dc13bfc947767f4484b1e18475cdce0",
}
NEGATION_TOKENS = (
    "not ", "does not", "do not", "cannot", "no ", "금지", "아니", "않",
    "못", "제한", "주장하지", "평가하지", "뜻하지", "not_evaluated",
    "blocked", "partially_supported",
)
NUMBER_MARKER_RE = re.compile(r"\{\{N:([a-z0-9_]+)(?:\|([^}]+))?\}\}")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_number_markers(text: str, registry: dict[str, Any]) -> str:
    """Render evidence-derived number markers and reject unknown keys or formats."""
    def replacement(match: re.Match[str]) -> str:
        key, format_spec = match.group(1), match.group(2)
        if key not in registry:
            raise ValueError(f"unknown thesis number key: {key}")
        value = registry[key]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"thesis number key is not numeric: {key}")
        try:
            return format(value, format_spec or "")
        except ValueError as exc:
            raise ValueError(f"invalid number format for {key}: {format_spec}") from exc

    rendered = NUMBER_MARKER_RE.sub(replacement, text)
    if "{{N:" in rendered:
        raise ValueError("malformed thesis number marker")
    return rendered


def bib_keys(text: str) -> set[str]:
    return set(re.findall(r"@[A-Za-z]+\s*\{\s*([^,\s]+)", text))


def sentence_for(text: str, position: int) -> str:
    left = max(text.rfind(".", 0, position), text.rfind("다.", 0, position))
    right_candidates = [value for value in (
        text.find(".", position), text.find("다.", position)
    ) if value >= 0]
    right = min(right_candidates) + 2 if right_candidates else len(text)
    return text[left + 1:right].strip()


def line_for(text: str, position: int) -> str:
    """Return a Markdown logical line for table rows and structured QA entries."""
    left = text.rfind("\n", 0, position)
    right = text.find("\n", position)
    return text[left + 1:right if right >= 0 else len(text)].strip()


def prohibited_occurrences(
    text: str,
    claims: list[dict[str, Any]],
    context_mode: str = "sentence",
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    lowered = text.casefold()
    for claim in claims:
        for phrase in claim.get("prohibited_overclaim", []):
            needle = phrase.casefold()
            start = 0
            while True:
                position = lowered.find(needle, start)
                if position < 0:
                    break
                sentence = (
                    line_for(text, position)
                    if context_mode == "line"
                    else sentence_for(text, position)
                )
                scoped_question = context_mode == "line" and "?" in sentence
                if not scoped_question and not any(
                    token in sentence.casefold() for token in NEGATION_TOKENS
                ):
                    findings.append({
                        "claim_id": claim["claim_id"],
                        "phrase": phrase,
                        "context": sentence,
                    })
                start = position + len(needle)
    return findings


def extract_release_qa_counts(lines: list[str]) -> tuple[int, int]:
    """Validate the RC2 soak ledger and return cycle and clean-clone counts."""
    cycles = [line for line in lines if line.startswith("cycle=")]
    clean_clones = [line for line in cycles if "deep=clean_clone_pass" in line]
    soak_end = next(
        (line for line in reversed(lines) if line.startswith("qa_soak_end=")), ""
    )
    if (
        not cycles
        or f"cycles={len(cycles)}" not in soak_end
        or "status=PASS" not in soak_end
        or any("status=PASS" not in line for line in cycles)
    ):
        raise ValueError("RC2 soak ledger is incomplete or contains a failed cycle")
    return len(cycles), len(clean_clones)


def extract_authoritative_numbers(root: Path) -> dict[str, int | float]:
    """Reconstruct every headline number from immutable evidence inputs."""
    suite = load_json(root / "docs/evidence/final_confirmatory_suite_v1/manifest.json")
    confirmatory = load_json(
        root / "docs/evidence/direct_locked_audit_final_source_v1/outputs/summary.json"
    )
    development = load_json(
        root / "docs/evidence/direct_locked_audit_seed0_development_v1/outputs/summary.json"
    )
    no_safe = load_json(root / "docs/evidence/no_safe_controls_confirmatory_v1/manifest.json")
    paired_confirmatory = load_json(
        root / "results/thesis_grade_protocol/paired_latency_claim_admission_v1/"
        "seeds1_4_confirmatory_summary.json"
    )
    paired_development = load_json(
        root / "results/thesis_grade_protocol/paired_latency_claim_admission_v1/"
        "seed0_development_summary.json"
    )
    structural = load_json(root / "docs/evidence/structural_extension_v1/manifest.json")
    margin = load_json(
        root / "docs/evidence/margin_utilization_interpretation_v1/"
        "structural_rejection_interpretation.json"
    )
    policy = load_json(root / "docs/evidence/policy_sensitivity_v1/results/summary.json")
    sobel = load_json(root / "docs/evidence/non_tabular_sobel_holdout_v1/summary.json")
    harris = load_json(root / "docs/evidence/non_tabular_harris_holdout_v1/summary.json")
    cnn = load_json(root / "docs/evidence/non_tabular_mnist_cnn_lite_holdout_v1/summary.json")
    training = load_json(root / "docs/evidence/independent_training_seed_extension_v1/summary.json")
    security = load_json(
        root / "docs/evidence/security_v2_static_attestation_formal_v2/"
        "security_reattestation_v2.json"
    )
    estimator = load_json(root / "docs/evidence/exact_security_estimator_v1/summary.json")
    interpretation = load_json(
        root / "docs/evidence/margin_utilization_interpretation_v1/policy_interpretation.json"
    )
    direct_policy = load_json(
        root / "docs/evidence/security_v2_static_attestation_formal_v2/"
        "direct_synthesis_policy_v2.json"
    )
    security_policy = load_json(
        root / "docs/evidence/security_v2_static_attestation_formal_v2/security_policy_v2.json"
    )["policy"]
    ablation = load_json(root / "docs/evidence/direct_synthesis_ablation_v1/summary.json")
    paired_manifest = load_json(root / "docs/evidence/paired_latency_final_v1/manifest.json")
    paired_frozen_summary = load_json(
        root / "docs/evidence/paired_latency_final_v1/summary/summary.json"
    )
    validation_identity = load_json(
        root / "docs/evidence/validation_identity_comparison_v2/manifest.json"
    )
    claim_admission = load_json(root / "docs/evidence/paper_claim_admission_v1/claims.json")
    release_soak_path = (
        root / "results/thesis_grade_protocol/release_candidate_v2/qa_soak.log"
    )
    release_soak_lines = release_soak_path.read_text(encoding="utf-8").splitlines()
    release_soak_cycles, release_clean_clone_rebuilds = extract_release_qa_counts(
        release_soak_lines
    )

    with (root / "docs/evidence/independent_training_seed_extension_v1/workload_summary.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        training_rows = list(csv.DictReader(handle))
    with (root / "docs/evidence/margin_utilization_interpretation_v1/alpha_sensitivity_summary.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        alpha_rows = list(csv.DictReader(handle))
    with (root / "docs/evidence/security_v2_bounded_oracle_v1/oracle/selection_changes_security_v2.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        security_selection_rows = list(csv.DictReader(handle))
    with (root / "docs/evidence/security_v2_bounded_oracle_v1/oracle/oracle_selection_security_v2.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        security_oracle_rows = list(csv.DictReader(handle))
    with (root / "docs/evidence/direct_locked_audit_final_source_v1/outputs/locked_audit_results.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        confirmatory_audit_rows = list(csv.DictReader(handle))
    with (root / "docs/evidence/direct_locked_audit_seed0_development_v1/outputs/locked_audit_results.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        development_audit_rows = list(csv.DictReader(handle))
    with (root / "docs/evidence/paired_latency_final_v1/summary/records.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        paired_record_rows = list(csv.DictReader(handle))

    estimator_models = estimator["models"]
    estimator_pass_counts = {
        model["cross_classification_counts"]["PASS__PASS_ESTIMATOR_MODEL"]
        for model in estimator_models
    }
    estimator_excluded_counts = {
        model["cross_classification_counts"]["FAIL__FAIL_ESTIMATOR_MODEL"]
        for model in estimator_models
    }
    if len(estimator_pass_counts) != 1 or len(estimator_excluded_counts) != 1:
        raise ValueError("security estimator models disagree on object accounting")

    alpha_candidate_changes = {int(row["natural_candidate_state_changes"]) for row in alpha_rows}
    alpha_oracle_changes = {int(row["bounded_oracle_selection_changes"]) for row in alpha_rows}
    alpha_literal_changes = {int(row["direct_initial_literal_changes"]) for row in alpha_rows}
    if any(len(values) != 1 for values in (
        alpha_candidate_changes, alpha_oracle_changes, alpha_literal_changes
    )):
        raise ValueError("alpha-sensitivity rows disagree on invariant counts")

    protocol = policy["protocol"]
    catalog = suite["catalog_accounting"]
    trials = suite["formal_trial_accounting"]
    no_safe_counts = no_safe["counts"]
    structural_counts = structural["counts"]
    paired_ratio = paired_confirmatory["catalog_over_direct"]
    security_profiles = security["catalog_profiles"]
    direct_security = security["direct_selected"]
    paired_protocol = paired_frozen_summary["protocol"]
    selection_key_repeats = {
        confirmatory["total_selection_key_runs"] // confirmatory["total_configuration_trials"],
        development["total_selection_key_runs"] // development["total_configuration_trials"],
    }
    audit_key_repeats = {
        confirmatory["total_fresh_key_runs"] // confirmatory["expected_runs"],
        development["total_fresh_key_runs"] // development["expected_runs"],
    }
    if len(selection_key_repeats | audit_key_repeats) != 1:
        raise ValueError("selection and audit fresh-key repetition policies disagree")

    sobel_validation = (
        sobel["selection"]["encrypted_sample_evaluations"]
        // sobel["selection"]["fresh_key_runs"]
    )
    sobel_audit = (
        sobel["locked_audit"]["encrypted_sample_evaluations"]
        // sobel["locked_audit"]["fresh_key_runs"]
    )
    harris_validation = (
        harris["selection"]["encrypted_sample_evaluations"]
        // harris["selection"]["fresh_key_runs"]
    )
    harris_audit = (
        harris["locked_audit"]["encrypted_sample_evaluations"]
        // harris["locked_audit"]["fresh_key_runs"]
    )

    # The thesis contract fixes structural utilization from the six-decimal
    # normalized-budget presentation (usage = utilization / rho). Keep that
    # declared display convention distinct from V3's direct seven-decimal
    # rounding of the full-precision overlay value.
    def structural_utilization_display(value: float) -> float:
        return round(value / interpretation["primary_rho"], 6) * interpretation["primary_rho"]

    training_datasets = {row["dataset_id"] for row in training_rows}
    training_seeds = {row["training_seed"] for row in training_rows}
    ablation_arms = ablation["arms"]
    admitted_claims = [claim for claim in claim_admission["claims"] if claim["paper_admitted"]]
    blocked_claims = [claim for claim in claim_admission["claims"] if not claim["paper_admitted"]]
    return {
        "formal_catalog_all": catalog["security_admitted_catalog_candidates"],
        "formal_catalog_confirmatory": catalog["confirmatory_catalog_candidates"],
        "formal_catalog_development": catalog["development_catalog_candidates"],
        "raw_historical_catalog_executions": catalog["raw_catalog_executions"],
        "security_excluded_catalog_candidates": catalog["security_excluded_catalog_candidates"],
        "direct_trials_all": trials["direct_trials_all"],
        "direct_trials_confirmatory": trials["direct_trials_confirmatory"],
        "direct_trials_development": trials["direct_trials_development"],
        "max_encrypted_trials": direct_policy["policy"]["max_encrypted_trials"],
        "primary_alpha": direct_policy["policy"]["primary_alpha"],
        "primary_margin_floor": direct_policy["policy"]["primary_margin_floor"],
        "numerical_repair_scale_bits": direct_policy["policy"]["numerical_repair_scale_bits"],
        "level_repair_q_primes": direct_policy["policy"]["level_repair_q_primes"],
        "max_additional_levels": direct_policy["policy"]["max_additional_levels"],
        "formal_trial_reduction_all": trials["formal_trial_reduction_all"],
        "formal_trial_reduction_confirmatory": trials["formal_trial_reduction_confirmatory"],
        "confirmatory_instances": confirmatory["expected_runs"],
        "development_instances": development["expected_runs"],
        "combined_descriptive_instances": confirmatory["expected_runs"] + development["expected_runs"],
        "confirmatory_locked_audit_pass": confirmatory["locked_audit_passes"],
        "development_locked_audit_pass": development["locked_audit_passes"],
        "confirmatory_selection_key_runs": confirmatory["total_selection_key_runs"],
        "development_selection_key_runs": development["total_selection_key_runs"],
        "confirmatory_audit_key_runs": confirmatory["total_fresh_key_runs"],
        "development_audit_key_runs": development["total_fresh_key_runs"],
        "fresh_key_repeats": next(iter(selection_key_repeats)),
        "confirmatory_audit_flips": sum(
            int(row["decision_flips"]) for row in confirmatory_audit_rows
        ),
        "confirmatory_audit_violations": sum(
            int(row["error_violations"]) for row in confirmatory_audit_rows
        ),
        "development_audit_flips": sum(
            int(row["decision_flips"]) for row in development_audit_rows
        ),
        "development_audit_violations": sum(
            int(row["error_violations"]) for row in development_audit_rows
        ),
        "primary_audit_flips": (
            confirmatory["expected_runs"] - confirmatory["zero_flip_passes"]
            + development["expected_runs"] - development["zero_flip_passes"]
        ),
        "primary_audit_violations": (
            confirmatory["expected_runs"] - confirmatory["zero_violation_passes"]
            + development["expected_runs"] - development["zero_violation_passes"]
        ),
        "primary_audit_failed": (
            confirmatory["failed_executions"] + development["failed_executions"]
        ),
        "primary_locked_audit_retuning": confirmatory["retuned_runs"] + development["retuned_runs"],
        "no_safe_budget": no_safe_counts["budget_no_safe"],
        "no_safe_budget_total": no_safe_counts["budget_workloads"],
        "no_safe_budget_selected": no_safe_counts["budget_selected"],
        "no_safe_finite_domain": no_safe_counts["finite_audit_no_safe"],
        "no_safe_finite_domain_total": no_safe_counts["finite_audit_workloads"],
        "no_safe_finite_selected": (
            no_safe_counts["finite_audit_workloads"] - no_safe_counts["finite_audit_no_safe"]
        ),
        "paired_total_ratio_confirmatory": paired_ratio["geometric_mean_total_latency_ratio"],
        "paired_total_ci_low": paired_ratio["cluster_bootstrap_95_ci_total"]["low"],
        "paired_total_ci_high": paired_ratio["cluster_bootstrap_95_ci_total"]["high"],
        "paired_eval_ratio_confirmatory": paired_ratio["geometric_mean_eval_only_ratio"],
        "paired_total_ratio_development": round(
            paired_development["catalog_over_direct"]["geometric_mean_total_latency_ratio"], 6
        ),
        "paired_development_catalog_total_mean_ms": paired_development["arm_latency"]["catalog"]["total_ms"]["mean"],
        "paired_development_direct_total_mean_ms": paired_development["arm_latency"]["direct"]["total_ms"]["mean"],
        "paired_development_failures": paired_development["failure_count"],
        "paired_confirmatory_complete": paired_confirmatory["workload_partition_instances"],
        "paired_confirmatory_failures": paired_confirmatory["failure_count"],
        "paired_confirmatory_reference_safe": paired_confirmatory["reference_status"]["safe"],
        "paired_cluster_bootstrap_replicates": paired_ratio[
            "cluster_bootstrap_95_ci_total"
        ]["replicates"],
        "paired_arms": len({row["arm_id"] for row in paired_record_rows}),
        "paired_warmup_runs": paired_protocol["warmup_runs"],
        "paired_measurement_runs": paired_protocol["measurement_runs"],
        "paired_rows_per_workload": paired_protocol["max_rows"],
        "primary_dataset_model_clusters": len(protocol["datasets"]) * len(protocol["models"]),
        "primary_datasets": len(protocol["datasets"]),
        "primary_model_graphs": len(protocol["models"]),
        "deterministic_partitions": len(protocol["split_seeds"]),
        "structural_instances": structural_counts["structural_instances"],
        "structural_selected": structural_counts["selection_selected"],
        "structural_audit_pass": structural_counts["locked_audit_pass"],
        "structural_reserve_reject": structural_counts["locked_audit_rejected"],
        "structural_failed": structural_counts["locked_audit_failed"],
        "structural_flip": structural_counts["flip_count"],
        "structural_violation": structural_counts["violation_count"],
        "structural_retuning": structural_counts["retuning"],
        "structural_selection_trials": structural_counts["selection_trials"],
        "structural_selection_repairs": structural_counts["selection_repairs"],
        "structural_selection_key_runs": structural_counts["selection_key_runs"],
        "structural_audit_key_runs": structural_counts["locked_audit_key_runs"],
        "structural_selection_failed": structural_counts["selection_failed"],
        "structural_selection_no_safe": structural_counts["selection_no_safe"],
        "structural_validation_margin_utilization": structural_utilization_display(
            margin["validation"]["margin_utilization_ratio"]
        ),
        "structural_audit_margin_utilization": structural_utilization_display(
            margin["locked_audit"]["margin_utilization_ratio"]
        ),
        "structural_audit_margin_utilization_full_precision": (
            margin["locked_audit"]["margin_utilization_ratio"]
        ),
        "structural_audit_margin_utilization_v3_display": round(
            margin["locked_audit"]["margin_utilization_ratio"], 7
        ),
        "sobel_validation_samples": sobel_validation,
        "sobel_audit_samples": sobel_audit,
        "sobel_validation_images": sobel["source"]["validation_images"],
        "sobel_audit_images": sobel["source"]["audit_images"],
        "harris_validation_samples": harris_validation,
        "harris_audit_samples": harris_audit,
        "harris_validation_images": harris["source"]["validation_images"],
        "harris_audit_images": harris["source"]["audit_images"],
        "cnn_lite_validation_samples": cnn["selection"]["samples"],
        "cnn_lite_audit_samples": cnn["locked_audit"]["samples"],
        "cnn_lite_selection_evaluations": cnn["selection"]["encrypted_sample_evaluations"],
        "cnn_lite_audit_evaluations": cnn["locked_audit"]["encrypted_sample_evaluations"],
        "cnn_lite_selection_flips": cnn["selection"]["flips"],
        "cnn_lite_audit_flips": cnn["locked_audit"]["flips"],
        "cnn_lite_selection_violations": cnn["selection"]["violations"],
        "cnn_lite_audit_violations": cnn["locked_audit"]["violations"],
        "cnn_lite_retuning": cnn["locked_audit"]["retuning"],
        "cnn_lite_validation_accuracy": cnn["plaintext_task"]["validation_accuracy"],
        "cnn_lite_audit_accuracy": cnn["plaintext_task"]["audit_accuracy"],
        "independent_training_datasets": len(training_datasets),
        "independent_training_seeds_per_dataset": len(training_seeds),
        "independent_training_seed_pass": training["locked_audit"]["pass"],
        "independent_training_seed_total": training["instances"],
        "security_direct_pass": direct_security["pass"],
        "security_direct_minimum_headroom_bits": direct_security["minimum_headroom_bits"],
        "security_catalog_profiles_admitted": len(security_profiles["admitted"]),
        "security_catalog_profiles_excluded": len(security_profiles["excluded"]),
        "security_catalog_profiles_total": (
            len(security_profiles["admitted"]) + len(security_profiles["excluded"])
        ),
        "catalog_execution_paths": 2,
        "security_admitted_catalog_identities": len(security_profiles["admitted"]) * 2,
        "security_estimator_objects_pass": next(iter(estimator_pass_counts)),
        "security_estimator_objects_excluded": next(iter(estimator_excluded_counts)),
        "security_estimator_models": len(estimator_models),
        "security_target_bits": security_policy["security_bits"],
        "security_runtime_error_sigma": security_policy["error_sigma"],
        "security_runtime_error_bound": security_policy["runtime_xe"]["bound"],
        "security_table_error_sigma": security_policy["table_error_sigma"],
        "margin_utilization_cap": interpretation["primary_rho"],
        "reserved_margin_fraction": interpretation["reserved_margin_fraction"],
        "policy_sensitivity_candidate_state_changes": next(iter(alpha_candidate_changes)),
        "policy_sensitivity_oracle_changes": next(iter(alpha_oracle_changes)),
        "policy_sensitivity_initial_literal_changes": next(iter(alpha_literal_changes)),
        "validation_identity_class_a": validation_identity["identity_class_counts"][
            "SOURCE_AND_SEMANTICS_MATCH_PREPARED_BYTES_DIFFER"
        ],
        "ablation_full_trials": ablation_arms["full_flipguard"]["trials"],
        "ablation_full_repairs": ablation_arms["full_flipguard"]["repairs"],
        "ablation_full_selected": ablation_arms["full_flipguard"]["selected"],
        "ablation_full_audit_pass": ablation_arms["full_flipguard"]["audit_pass"],
        "ablation_one_shot_trials": ablation_arms["one_shot_direct"]["trials"],
        "ablation_one_shot_selected": ablation_arms["one_shot_direct"]["selected"],
        "ablation_one_shot_no_safe": ablation_arms["one_shot_direct"]["no_safe"],
        "ablation_one_shot_flips": ablation_arms["one_shot_direct"]["validation_flips"],
        "ablation_latency_only_trials": ablation_arms["latency_only_no_certification"]["trials"],
        "ablation_latency_only_selected": ablation_arms["latency_only_no_certification"]["selected"],
        "ablation_latency_only_flips": ablation_arms["latency_only_no_certification"]["validation_flips"],
        "ablation_latency_only_audit_pass": ablation_arms["latency_only_no_certification"]["audit_pass"],
        "paired_raw_records": paired_manifest["counts"]["raw_records"],
        "paired_catalog_total_mean_ms": paired_confirmatory["arm_latency"]["catalog"]["total_ms"]["mean"],
        "paired_catalog_total_median_ms": paired_confirmatory["arm_latency"]["catalog"]["total_ms"]["median"],
        "paired_catalog_total_p95_ms": paired_confirmatory["arm_latency"]["catalog"]["total_ms"]["p95"],
        "paired_direct_total_mean_ms": paired_confirmatory["arm_latency"]["direct"]["total_ms"]["mean"],
        "paired_direct_total_median_ms": paired_confirmatory["arm_latency"]["direct"]["total_ms"]["median"],
        "paired_direct_total_p95_ms": paired_confirmatory["arm_latency"]["direct"]["total_ms"]["p95"],
        "paired_catalog_eval_mean_ms": paired_confirmatory["arm_latency"]["catalog"]["eval_only_ms"]["mean"],
        "paired_direct_eval_mean_ms": paired_confirmatory["arm_latency"]["direct"]["eval_only_ms"]["mean"],
        "paired_workload_ratio_min": paired_ratio["workload_partition_ratio"]["min"],
        "paired_workload_ratio_median": paired_ratio["workload_partition_ratio"]["median"],
        "paired_workload_ratio_max": paired_ratio["workload_partition_ratio"]["max"],
        "paired_cluster_ratio_min": paired_ratio["cluster_ratio"]["min"],
        "paired_cluster_ratio_median": paired_ratio["cluster_ratio"]["median"],
        "paired_cluster_ratio_max": paired_ratio["cluster_ratio"]["max"],
        "paired_catalog_cv_median": paired_confirmatory["arm_latency"]["catalog"]["within_workload_total_cv"]["median"],
        "paired_catalog_cv_max": paired_confirmatory["arm_latency"]["catalog"]["within_workload_total_cv"]["max"],
        "paired_direct_cv_median": paired_confirmatory["arm_latency"]["direct"]["within_workload_total_cv"]["median"],
        "paired_direct_cv_max": paired_confirmatory["arm_latency"]["direct"]["within_workload_total_cv"]["max"],
        "paired_position_effect_1": paired_confirmatory["position_effect"]["1"],
        "paired_position_effect_2": paired_confirmatory["position_effect"]["2"],
        "paired_position_effect_3": paired_confirmatory["position_effect"]["3"],
        "sobel_initial_violations": sobel["selection"]["initial_violations"],
        "sobel_repairs": sobel["selection"]["repairs"],
        "sobel_audit_flips": sobel["locked_audit"]["flips"],
        "sobel_audit_violations": sobel["locked_audit"]["violations"],
        "sobel_audit_retuning": sobel["locked_audit"]["retuning"],
        "harris_windows_per_image": harris["source"]["patches_per_image"],
        "harris_repairs": harris["selection"]["repairs"],
        "harris_audit_flips": harris["locked_audit"]["flips"],
        "harris_audit_violations": harris["locked_audit"]["violations"],
        "harris_audit_retuning": harris["locked_audit"]["retuning"],
        "training_selection_trials": training["selection"]["trials"],
        "training_selection_key_runs": training["selection"]["key_runs"],
        "training_audit_key_runs": training["locked_audit"]["key_runs"],
        "training_selection_evaluations": training["selection"]["encrypted_sample_evaluations"],
        "training_audit_evaluations": training["locked_audit"]["encrypted_sample_evaluations"],
        "training_repairs": training["selection"]["repairs"],
        "training_selection_flips": training["selection"]["flips"],
        "training_selection_violations": training["selection"]["violations"],
        "training_audit_flips": training["locked_audit"]["flips"],
        "training_audit_violations": training["locked_audit"]["violations"],
        "training_flips": training["selection"]["flips"] + training["locked_audit"]["flips"],
        "training_violations": training["selection"]["violations"] + training["locked_audit"]["violations"],
        "training_retuning": training["locked_audit"]["retuning"],
        "paper_admitted_claims": len(admitted_claims),
        "paper_blocked_claims": len(blocked_claims),
        "security_selection_changes_all": len(security_selection_rows),
        "security_selection_cells_all": len(security_oracle_rows),
        "security_selection_changes_primary": sum(
            float(row["alpha"]) == interpretation["primary_rho"]
            for row in security_selection_rows
        ),
        "security_selection_cells_primary": sum(
            float(row["alpha"]) == interpretation["primary_rho"]
            for row in security_oracle_rows
        ),
        "release_soak_cycles": release_soak_cycles,
        "release_clean_clone_rebuilds": release_clean_clone_rebuilds,
    }


def validate_registry(root: Path, registry: dict[str, Any], errors: list[str]) -> None:
    for key, value in extract_authoritative_numbers(root).items():
        if registry.get(key) != value:
            errors.append(
                f"number registry/evidence mismatch: {key}={registry.get(key)!r}, "
                f"evidence={value!r}"
            )
    for key, value in EXPECTED_DIGESTS.items():
        if registry.get(key) != value:
            errors.append(f"binding mismatch: {key}")


def lint_source(root: Path = ROOT, source_dir: Path = DEFAULT_SOURCE) -> dict[str, Any]:
    source = root / source_dir
    errors: list[str] = []
    warnings: list[str] = []
    required = CHAPTERS + [
        "00_thesis_contract.md", "appendix.md", "abstract_ko_en.md",
        "advisor_defense_qa.md", "number_registry.json", "references.bib",
        "citation_audit.csv", "figure_table_map.csv", "claim_traceability.csv",
        "reviewer_attack_checklist.md", "university_template_requirements.md",
    ]
    for relative in required:
        if not (source / relative).is_file():
            errors.append(f"missing source: {relative}")
    if errors:
        return {"status": "FAIL", "errors": errors, "warnings": warnings}

    raw_chapters = {name: (source / name).read_text(encoding="utf-8") for name in CHAPTERS}
    raw_abstract = (source / "abstract_ko_en.md").read_text(encoding="utf-8")
    raw_appendix = (source / "appendix.md").read_text(encoding="utf-8")
    raw_auxiliary = {
        name: (source / name).read_text(encoding="utf-8")
        for name in AUXILIARY_MARKDOWN
    }
    claims_doc = load_json(root / "docs/evidence/paper_claim_admission_v1/claims.json")
    claims = claims_doc["claims"]
    claim_by_id = {item["claim_id"]: item for item in claims}
    registry = load_json(source / "number_registry.json")
    validate_registry(root, registry, errors)
    raw_headline = "\n".join((
        raw_abstract,
        raw_chapters["08_results.md"],
        raw_chapters["11_conclusion.md"],
    ))
    number_markers = list(NUMBER_MARKER_RE.finditer(raw_headline))
    number_marker_keys = {match.group(1) for match in number_markers}
    required_number_keys = {
        "formal_catalog_all", "formal_catalog_confirmatory",
        "direct_trials_all", "direct_trials_confirmatory",
        "formal_trial_reduction_all", "confirmatory_locked_audit_pass",
        "development_locked_audit_pass", "no_safe_budget",
        "no_safe_finite_domain", "paired_total_ratio_confirmatory",
        "paired_total_ci_low", "paired_total_ci_high",
        "paired_eval_ratio_confirmatory", "structural_selected",
        "structural_audit_pass", "structural_reserve_reject",
        "independent_training_seed_pass", "security_direct_pass",
    }
    if required_number_keys - number_marker_keys:
        errors.append(
            "headline numbers are not registry-generated: "
            f"{sorted(required_number_keys-number_marker_keys)}"
        )
    release_number_keys = {
        match.group(1)
        for match in NUMBER_MARKER_RE.finditer(raw_chapters["10_reproducibility_security.md"])
    }
    required_release_keys = {"release_soak_cycles", "release_clean_clone_rebuilds"}
    if required_release_keys - release_number_keys:
        errors.append(
            "release QA numbers are not registry-generated: "
            f"{sorted(required_release_keys-release_number_keys)}"
        )
    for literal in (
        "3.14065956642714", "3.140660", "2.3423342246526992",
        "4.21531336367743", "2.624674483419857", "70/700",
        "56/560", "40/40", "10/10", "16/40", "25/25", "24 PASS",
    ):
        if literal in raw_headline:
            errors.append(f"raw headline number bypasses registry marker: {literal}")
    try:
        chapters = {
            name: render_number_markers(text, registry)
            for name, text in raw_chapters.items()
        }
        abstract = render_number_markers(raw_abstract, registry)
        appendix = render_number_markers(raw_appendix, registry)
        auxiliary = {
            name: render_number_markers(text, registry)
            for name, text in raw_auxiliary.items()
        }
    except ValueError as exc:
        errors.append(str(exc))
        chapters = raw_chapters
        abstract = raw_abstract
        appendix = raw_appendix
        auxiliary = raw_auxiliary
    core_text = "\n".join(chapters.values())

    core_claim_text = "\n".join((core_text, abstract, appendix))
    for finding in prohibited_occurrences(core_claim_text, claims):
        errors.append(
            f"unscoped prohibited claim {finding['claim_id']}: "
            f"{finding['phrase']} :: {finding['context']}"
        )
    defense_claim_text = re.sub(
        r"^## Q\d+\..*$", "", auxiliary["advisor_defense_qa.md"], flags=re.M
    )
    reviewer_claim_cells: list[str] = []
    for line in auxiliary["reviewer_attack_checklist.md"].splitlines():
        if not re.match(r"^\|\s*\d+\s*\|", line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 6:
            reviewer_claim_cells.extend((cells[2], cells[4]))
    for filename, claim_text in (
        ("advisor_defense_qa.md", defense_claim_text),
        ("reviewer_attack_checklist.md", "\n".join(reviewer_claim_cells)),
    ):
        for finding in prohibited_occurrences(claim_text, claims):
            errors.append(
                f"{filename}: unscoped prohibited claim {finding['claim_id']}: "
                f"{finding['phrase']} :: {finding['context']}"
            )

    marker_pattern = re.compile(r"<!--\s*P:([A-Z0-9-]+)\s+CLAIM:([a-z0-9_,]+)\s*-->")
    used_claims: set[str] = set()
    marker_count = 0
    for filename, text in chapters.items():
        for match in marker_pattern.finditer(text):
            marker_count += 1
            for claim_id in match.group(2).split(","):
                used_claims.add(claim_id)
                claim = claim_by_id.get(claim_id)
                if claim is None:
                    errors.append(f"{filename}: unknown claim marker {claim_id}")
                elif not claim["paper_admitted"]:
                    errors.append(f"{filename}: blocked claim used as positive marker {claim_id}")
    admitted = {item["claim_id"] for item in claims if item["paper_admitted"]}
    missing_claims = admitted - used_claims
    if missing_claims:
        errors.append(f"admitted claims without trace marker: {sorted(missing_claims)}")

    figure_markers = set(re.findall(r"\{\{V3_FIGURE_(\d{2})\}\}", core_text))
    table_markers = set(re.findall(r"\{\{V3_TABLE_(\d{2})\}\}", core_text))
    if figure_markers != {f"{value:02d}" for value in range(1, 11)}:
        errors.append(f"figure marker set mismatch: {sorted(figure_markers)}")
    if table_markers != {f"{value:02d}" for value in range(1, 14)}:
        errors.append(f"table marker set mismatch: {sorted(table_markers)}")
    for number in range(1, 11):
        marker = f"{{{{V3_FIGURE_{number:02d}}}}}"
        owner = next((text for text in chapters.values() if marker in text), "")
        if owner and owner.find(f"그림 {number}") > owner.find(marker):
            errors.append(f"figure {number} is placed before first reference")
    for number in range(1, 14):
        marker = f"{{{{V3_TABLE_{number:02d}}}}}"
        owner = next((text for text in chapters.values() if marker in text), "")
        if owner and owner.find(f"표 {number}") > owner.find(marker):
            errors.append(f"table {number} is placed before first reference")

    references = (source / "references.bib").read_text(encoding="utf-8")
    known_keys = bib_keys(references)
    cited_keys = set(re.findall(r"@([A-Za-z0-9_:-]+)", core_text + "\n" + abstract))
    missing_bib = cited_keys - known_keys
    if missing_bib:
        errors.append(f"citation keys missing from BibTeX: {sorted(missing_bib)}")
    with (source / "citation_audit.csv").open(newline="", encoding="utf-8") as handle:
        audit_rows = list(csv.DictReader(handle))
    audit_keys = {row["citation_key"] for row in audit_rows}
    if cited_keys - audit_keys:
        errors.append(f"cited keys missing from citation audit: {sorted(cited_keys-audit_keys)}")
    if audit_keys - cited_keys:
        errors.append(f"citation audit rows not cited by the thesis: {sorted(audit_keys-cited_keys)}")
    if audit_keys - known_keys:
        errors.append(f"citation audit keys missing from BibTeX: {sorted(audit_keys-known_keys)}")
    if known_keys - audit_keys:
        errors.append(f"BibTeX keys missing from citation audit: {sorted(known_keys-audit_keys)}")
    if len(audit_keys) != len(audit_rows):
        errors.append("duplicate citation keys in citation audit")
    for row in audit_rows:
        if row["primary_source_verified"].casefold() != "true":
            errors.append(f"citation lacks primary-source verification: {row['citation_key']}")
        if not row["DOI/ePrint/official URL"].strip():
            errors.append(f"citation lacks official locator: {row['citation_key']}")
        if not row["exact_supported_point"].strip() or not row["unsupported_extension"].strip():
            errors.append(f"citation boundary is incomplete: {row['citation_key']}")
    unresolved = [row["citation_key"] for row in audit_rows if not row["status"].startswith("VERIFIED")]
    if unresolved:
        errors.append(f"unresolved citations: {unresolved}")

    related_work_lines = chapters["03_related_work.md"].splitlines()
    comparison_rows = [
        line for line in related_work_lines
        if line.startswith("|")
        and not line.startswith("| ---")
        and "연구군" not in line
    ]
    if len(comparison_rows) != 7:
        errors.append(
            f"related-work comparison row count is {len(comparison_rows)}, expected 7"
        )
    for index, row in enumerate(comparison_rows, 1):
        if not re.search(r"@[A-Za-z0-9_:-]+", row):
            errors.append(f"related-work comparison row {index} lacks a primary citation")

    with (source / "figure_table_map.csv").open(newline="", encoding="utf-8") as handle:
        map_rows = list(csv.DictReader(handle))
    if len(map_rows) != 23:
        errors.append(f"figure/table map row count is {len(map_rows)}, expected 23")
    identities: set[tuple[str, str]] = set()
    for row in map_rows:
        identity = (row["type"], row["number"])
        if identity in identities:
            errors.append(f"duplicate figure/table identity: {identity}")
        identities.add(identity)
        asset = root / row["source_path"]
        if not asset.is_file() or sha256(asset) != row["source_sha256"]:
            errors.append(f"asset digest mismatch: {row['source_path']}")
        if row["cited_in_text"].casefold() != "true":
            errors.append(f"orphan asset: {identity}")
        chapter_path = source / f"{row['chapter']}.md"
        if not chapter_path.is_file():
            errors.append(f"figure/table chapter does not exist: {row['chapter']}")
            continue
        chapter_lines = chapter_path.read_text(encoding="utf-8").splitlines()
        korean_type = "그림" if row["type"] == "figure" else "표"
        label = f"{korean_type} {int(row['number'])}"
        references = [index for index, line in enumerate(chapter_lines, 1) if label in line]
        marker = f"{{{{V3_{row['type'].upper()}_{int(row['number']):02d}}}}}"
        placements = [index for index, line in enumerate(chapter_lines, 1) if marker in line]
        if not references:
            errors.append(f"missing in-text reference: {identity}")
        elif row["first_reference_line"] != str(references[0]):
            errors.append(f"stale first-reference line: {identity}")
        if len(placements) != 1:
            errors.append(f"asset placement count is {len(placements)}, expected 1: {identity}")
        elif references and placements[0] <= references[0]:
            errors.append(f"asset is not placed after its first reference: {identity}")

    with (source / "claim_traceability.csv").open(newline="", encoding="utf-8") as handle:
        trace_rows = list(csv.DictReader(handle))
    expected_trace: set[tuple[str, str, str]] = set()
    for filename, text in {"abstract_ko_en.md": raw_abstract, **raw_chapters}.items():
        for match in marker_pattern.finditer(text):
            for claim_id in match.group(2).split(","):
                expected_trace.add((Path(filename).stem, match.group(1), claim_id))
    actual_trace = {
        (row["section"], row["paragraph_id"], row["claim_id"])
        for row in trace_rows
    }
    if len(actual_trace) != len(trace_rows):
        errors.append("duplicate claim traceability row")
    if actual_trace != expected_trace:
        errors.append(
            "claim traceability differs from source markers: "
            f"missing={sorted(expected_trace-actual_trace)}, extra={sorted(actual_trace-expected_trace)}"
        )
    for row in trace_rows:
        claim = claim_by_id.get(row["claim_id"])
        if claim is None or row["paper_admitted"].casefold() != "true":
            errors.append(f"non-admitted claim in traceability: {row['claim_id']}")
        if row["wording_type"] not in {"exact", "scoped_paraphrase"}:
            errors.append(f"invalid claim wording type: {row['paragraph_id']}")
        if row["lint_status"] != "PASS":
            errors.append(f"claim traceability row is not PASS: {row['paragraph_id']}")

    defense = auxiliary["advisor_defense_qa.md"]
    defense_parts = re.split(r"^## Q(\d+)\. ", defense, flags=re.M)
    question_numbers = [int(defense_parts[index]) for index in range(1, len(defense_parts), 2)]
    if question_numbers != list(range(1, 31)):
        errors.append(f"advisor Q&A numbering mismatch: {question_numbers}")
    for index in range(1, len(defense_parts), 2):
        question_number = defense_parts[index]
        answer = defense_parts[index + 1]
        for field in ("**Claim ID:**", "**Evidence:**", "**금지 과장:**", "**짧은 구두 답변:**"):
            if field not in answer:
                errors.append(f"advisor Q{question_number} lacks {field}")
        if "**Claim ID:**" in answer and "**Evidence:**" in answer:
            claim_text = answer.split("**Claim ID:**", 1)[1].split("**Evidence:**", 1)[0]
            defense_claim_ids = re.findall(r"`([a-z0-9_]+)`", claim_text)
            if not defense_claim_ids:
                errors.append(f"advisor Q{question_number} lacks a canonical claim ID")
            for claim_id in defense_claim_ids:
                if claim_id not in claim_by_id:
                    errors.append(
                        f"advisor Q{question_number} cites unknown claim ID: {claim_id}"
                    )
        if "**Evidence:**" in answer and "**금지 과장:**" in answer:
            evidence_text = answer.split("**Evidence:**", 1)[1].split("**금지 과장:**", 1)[0]
            for evidence_path in re.findall(r"`([^`]+/[^`]+)`", evidence_text):
                if "*" not in evidence_path and not (root / evidence_path.rstrip("/")).exists():
                    errors.append(
                        f"advisor Q{question_number} cites missing evidence path: {evidence_path}"
                    )
        prose = answer.split("**Claim ID:**", 1)[0]
        sentence_count = len(re.findall(r"(?:다|이다|한다|된다|않다|없다|있다)\.", prose))
        if not 3 <= sentence_count <= 8:
            errors.append(
                f"advisor Q{question_number} has {sentence_count} answer sentences; expected 3--8"
            )

    reviewer = auxiliary["reviewer_attack_checklist.md"]
    reviewer_rows = re.findall(r"^\|\s*(\d+)\s*\|.*\|\s*([A-Z_]+)\s*\|$", reviewer, flags=re.M)
    reviewer_numbers = [int(number) for number, _ in reviewer_rows]
    allowed_reviewer_states = {"CLOSED_FOR_DRAFT", "DISCLOSED_RESIDUAL_RISK", "BLOCKED_CLAIM"}
    if reviewer_numbers != list(range(1, 19)):
        errors.append(f"reviewer attack checklist numbering mismatch: {reviewer_numbers}")
    invalid_reviewer_states = sorted({state for _, state in reviewer_rows} - allowed_reviewer_states)
    if invalid_reviewer_states:
        errors.append(f"invalid reviewer attack states: {invalid_reviewer_states}")

    forbidden_placeholders = re.findall(
        r"\b(?:TODO|TBD|FIXME)\b|추후\s*삽입",
        "\n".join((core_claim_text, *auxiliary.values())),
        flags=re.I,
    )
    if forbidden_placeholders:
        errors.append(f"placeholder tokens remain: {sorted(set(forbidden_placeholders))}")
    if sum(len(value) for value in chapters.values()) < 45_000:
        errors.append("chapter content is below 45,000 characters")
    if "e_c(x)<m(x)" not in abstract or "e_c(x)<0.5m(x)" not in abstract:
        errors.append("abstract does not separate theorem and operational policy")
    if "24 PASS" not in abstract or "REJECT" not in abstract:
        errors.append("abstract omits the structural negative result")
    if "seed 0" not in core_text.casefold() or "seeds 1--4" not in core_text:
        errors.append("seed roles are not explicit")
    for match in re.finditer(r"1,?800.{0,80}(?:independent|독립)", core_text, flags=re.I | re.S):
        context = sentence_for(core_text, match.start()).casefold()
        if not any(token in context for token in NEGATION_TOKENS):
            errors.append("raw latency pairs are described as independent")
    for match in re.finditer(r"1,100", core_text):
        context = core_text[max(0, match.start()-120):match.end()+120].casefold()
        if not any(word in context for word in (
            "historical", "pre-security", "실행 이력", "역사", "아니", "않", "사용되지"
        )):
            errors.append("1,100 appears without historical/pre-security context")

    binding = load_json(root / "docs/evidence/research_release_binding_rc2_v1/release_binding_rc2.json")
    if binding["source_commit"] != EXPECTED_DIGESTS["rc2_source_commit"]:
        errors.append("RC2 binding source mismatch")
    binding_text_requirements = {
        "00_thesis_contract.md": (
            binding["tag"],
            binding["source_commit"],
            binding["archive"]["sha256"].removeprefix("sha256:"),
            binding["paper_artifacts_v3"]["manifest_sha256"].removeprefix("sha256:"),
            binding["claim_admission"]["manifest_sha256"].removeprefix("sha256:"),
            EXPECTED_DIGESTS["margin_interpretation_manifest_sha256"],
        ),
        "06_implementation.md": (
            binding["tag"],
            binding["source_commit"],
            binding["archive"]["sha256"].removeprefix("sha256:"),
        ),
        "10_reproducibility_security.md": (
            binding["tag"],
            binding["source_commit"],
            binding["archive"]["sha256"].removeprefix("sha256:"),
            binding["v10"]["manifest_sha256"].removeprefix("sha256:"),
            binding["paper_artifacts_v3"]["manifest_sha256"].removeprefix("sha256:"),
            binding["claim_admission"]["manifest_sha256"].removeprefix("sha256:"),
        ),
        "appendix.md": (
            binding["tag"],
            binding["source_commit"],
            binding["archive"]["sha256"].removeprefix("sha256:"),
            binding["paper_artifacts_v3"]["manifest_sha256"].removeprefix("sha256:"),
            binding["claim_admission"]["manifest_sha256"].removeprefix("sha256:"),
            EXPECTED_DIGESTS["margin_interpretation_manifest_sha256"],
        ),
    }
    binding_texts = {
        "00_thesis_contract.md": auxiliary["00_thesis_contract.md"],
        "06_implementation.md": chapters["06_implementation.md"],
        "10_reproducibility_security.md": chapters["10_reproducibility_security.md"],
        "appendix.md": appendix,
    }
    for filename, tokens in binding_text_requirements.items():
        for token in tokens:
            if token not in binding_texts[filename]:
                errors.append(f"{filename}: missing or stale release binding token {token}")
    if claims_doc.get("paper_claim_allowed") is not True:
        errors.append("paper claim registry does not allow admitted-claim writing")

    status = "PASS" if not errors else "FAIL"
    return {
        "schema_version": "flipguard_thesis_lint_v1",
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "metrics": {
            "chapter_characters": sum(len(value) for value in chapters.values()),
            "chapter_words": sum(len(value.split()) for value in chapters.values()),
            "claim_markers": marker_count,
            "admitted_claims_referenced": len(used_claims),
            "blocked_claim_violations": sum("prohibited claim" in error or "blocked claim" in error for error in errors),
            "citations_used": len(cited_keys),
            "citation_audit_rows": len(audit_rows),
            "related_work_comparison_rows": len(comparison_rows),
            "claim_traceability_rows": len(trace_rows),
            "advisor_questions": len(question_numbers),
            "reviewer_attacks": len(reviewer_rows),
            "headline_number_markers": len(number_markers),
            "headline_number_keys": len(number_marker_keys),
            "figures": len(figure_markers),
            "tables": len(table_markers),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    result = lint_source(ROOT, args.source_dir)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.json_output:
        output = args.json_output if args.json_output.is_absolute() else ROOT / args.json_output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
