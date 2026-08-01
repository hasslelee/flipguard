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
EXPECTED_DIGESTS = {
    "rc2_source_commit": "6c5f8b234f9f9da91a189fa0f2dc180bb996abf5",
    "rc2_archive_sha256": "05ef70306a11ab577243b0c708489864f19ccd104e6036e28fc6bd1dab45c0be",
    "v3_manifest_sha256": "32d378b371b75d31b8e39ef2acce4c3c7353581ccfbd5e6c7d22b30ffaf4743b",
    "claim_admission_manifest_sha256": "d982f0f81915b760c537244fc71aa992bf521eaf65d57a67c2d96dbae0607b8d",
    "margin_interpretation_manifest_sha256": "12626638b1abb5d57155345ee84e7e145dc13bfc947767f4484b1e18475cdce0",
}
NEGATION_TOKENS = (
    "not ", "does not", "do not", "cannot", "no ", "금지", "아니", "않",
    "못", "제한", "주장하지", "평가하지", "뜻하지",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bib_keys(text: str) -> set[str]:
    return set(re.findall(r"@[A-Za-z]+\s*\{\s*([^,\s]+)", text))


def sentence_for(text: str, position: int) -> str:
    left = max(text.rfind(".", 0, position), text.rfind("다.", 0, position))
    right_candidates = [value for value in (
        text.find(".", position), text.find("다.", position)
    ) if value >= 0]
    right = min(right_candidates) + 2 if right_candidates else len(text)
    return text[left + 1:right].strip()


def prohibited_occurrences(text: str, claims: list[dict[str, Any]]) -> list[dict[str, str]]:
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
                sentence = sentence_for(text, position)
                if not any(token in sentence.casefold() for token in NEGATION_TOKENS):
                    findings.append({
                        "claim_id": claim["claim_id"],
                        "phrase": phrase,
                        "context": sentence,
                    })
                start = position + len(needle)
    return findings


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

    with (root / "docs/evidence/independent_training_seed_extension_v1/workload_summary.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        training_rows = list(csv.DictReader(handle))
    with (root / "docs/evidence/margin_utilization_interpretation_v1/alpha_sensitivity_summary.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        alpha_rows = list(csv.DictReader(handle))

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
    return {
        "formal_catalog_all": catalog["security_admitted_catalog_candidates"],
        "formal_catalog_confirmatory": catalog["confirmatory_catalog_candidates"],
        "raw_historical_catalog_executions": catalog["raw_catalog_executions"],
        "security_excluded_catalog_candidates": catalog["security_excluded_catalog_candidates"],
        "direct_trials_all": trials["direct_trials_all"],
        "direct_trials_confirmatory": trials["direct_trials_confirmatory"],
        "direct_trials_development": trials["direct_trials_development"],
        "formal_trial_reduction_all": trials["formal_trial_reduction_all"],
        "formal_trial_reduction_confirmatory": trials["formal_trial_reduction_confirmatory"],
        "confirmatory_instances": confirmatory["expected_runs"],
        "development_instances": development["expected_runs"],
        "confirmatory_locked_audit_pass": confirmatory["locked_audit_passes"],
        "development_locked_audit_pass": development["locked_audit_passes"],
        "primary_locked_audit_retuning": confirmatory["retuned_runs"] + development["retuned_runs"],
        "no_safe_budget": no_safe_counts["budget_no_safe"],
        "no_safe_budget_total": no_safe_counts["budget_workloads"],
        "no_safe_budget_selected": no_safe_counts["budget_selected"],
        "no_safe_finite_domain": no_safe_counts["finite_audit_no_safe"],
        "no_safe_finite_domain_total": no_safe_counts["finite_audit_workloads"],
        "paired_total_ratio_confirmatory": paired_ratio["geometric_mean_total_latency_ratio"],
        "paired_total_ci_low": paired_ratio["cluster_bootstrap_95_ci_total"]["low"],
        "paired_total_ci_high": paired_ratio["cluster_bootstrap_95_ci_total"]["high"],
        "paired_eval_ratio_confirmatory": paired_ratio["geometric_mean_eval_only_ratio"],
        "paired_total_ratio_development": round(
            paired_development["catalog_over_direct"]["geometric_mean_total_latency_ratio"], 6
        ),
        "paired_confirmatory_complete": paired_confirmatory["workload_partition_instances"],
        "paired_confirmatory_failures": paired_confirmatory["failure_count"],
        "paired_confirmatory_reference_safe": paired_confirmatory["reference_status"]["safe"],
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
        "structural_validation_margin_utilization": structural_utilization_display(
            margin["validation"]["margin_utilization_ratio"]
        ),
        "structural_audit_margin_utilization": structural_utilization_display(
            margin["locked_audit"]["margin_utilization_ratio"]
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
        "independent_training_datasets": len(training_datasets),
        "independent_training_seeds_per_dataset": len(training_seeds),
        "independent_training_seed_pass": training["locked_audit"]["pass"],
        "independent_training_seed_total": training["instances"],
        "security_direct_pass": direct_security["pass"],
        "security_direct_minimum_headroom_bits": direct_security["minimum_headroom_bits"],
        "security_catalog_profiles_admitted": len(security_profiles["admitted"]),
        "security_catalog_profiles_excluded": len(security_profiles["excluded"]),
        "security_estimator_objects_pass": next(iter(estimator_pass_counts)),
        "security_estimator_objects_excluded": next(iter(estimator_excluded_counts)),
        "security_estimator_models": len(estimator_models),
        "margin_utilization_cap": interpretation["primary_rho"],
        "reserved_margin_fraction": interpretation["reserved_margin_fraction"],
        "policy_sensitivity_candidate_state_changes": next(iter(alpha_candidate_changes)),
        "policy_sensitivity_oracle_changes": next(iter(alpha_oracle_changes)),
        "policy_sensitivity_initial_literal_changes": next(iter(alpha_literal_changes)),
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
        "citation_audit.csv", "figure_table_map.csv",
    ]
    for relative in required:
        if not (source / relative).is_file():
            errors.append(f"missing source: {relative}")
    if errors:
        return {"status": "FAIL", "errors": errors, "warnings": warnings}

    chapters = {name: (source / name).read_text(encoding="utf-8") for name in CHAPTERS}
    core_text = "\n".join(chapters.values())
    abstract = (source / "abstract_ko_en.md").read_text(encoding="utf-8")
    claims_doc = load_json(root / "docs/evidence/paper_claim_admission_v1/claims.json")
    claims = claims_doc["claims"]
    claim_by_id = {item["claim_id"]: item for item in claims}
    registry = load_json(source / "number_registry.json")
    validate_registry(root, registry, errors)

    headline_text = "\n".join((abstract, chapters["01_introduction.md"], chapters["08_results.md"], chapters["11_conclusion.md"]))
    for finding in prohibited_occurrences(headline_text, claims):
        errors.append(
            f"unscoped prohibited claim {finding['claim_id']}: "
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
    unresolved = [row["citation_key"] for row in audit_rows if not row["status"].startswith("VERIFIED")]
    if unresolved:
        errors.append(f"unresolved citations: {unresolved}")

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

    forbidden_placeholders = re.findall(r"\b(?:TODO|TBD|FIXME)\b|추후\s*삽입", core_text, flags=re.I)
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
