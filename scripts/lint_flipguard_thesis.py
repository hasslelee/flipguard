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


def validate_registry(root: Path, registry: dict[str, Any], errors: list[str]) -> None:
    expected = {
        "formal_catalog_all": 700,
        "formal_catalog_confirmatory": 560,
        "direct_trials_all": 70,
        "direct_trials_confirmatory": 56,
        "formal_trial_reduction_all": 0.9,
        "formal_trial_reduction_confirmatory": 0.9,
        "confirmatory_locked_audit_pass": 40,
        "development_locked_audit_pass": 10,
        "no_safe_budget": 16,
        "no_safe_budget_total": 40,
        "no_safe_finite_domain": 50,
        "paired_total_ratio_confirmatory": 3.14065956642714,
        "paired_total_ci_low": 2.3423342246526992,
        "paired_total_ci_high": 4.21531336367743,
        "paired_eval_ratio_confirmatory": 2.624674483419857,
        "structural_selected": 25,
        "structural_audit_pass": 24,
        "structural_reserve_reject": 1,
        "structural_flip": 0,
        "independent_training_seed_pass": 9,
        "sobel_validation_samples": 400,
        "sobel_audit_samples": 400,
        "harris_validation_samples": 200,
        "harris_audit_samples": 200,
        "cnn_lite_validation_samples": 250,
        "cnn_lite_audit_samples": 250,
    }
    for key, value in expected.items():
        if registry.get(key) != value:
            errors.append(f"number registry mismatch: {key}={registry.get(key)!r}, expected {value!r}")
    for key, value in EXPECTED_DIGESTS.items():
        if registry.get(key) != value:
            errors.append(f"binding mismatch: {key}")

    latency = load_json(
        root / "results/thesis_grade_protocol/paired_latency_claim_admission_v1/"
        "seeds1_4_confirmatory_summary.json"
    )
    ratio = latency["catalog_over_direct"]
    evidence_values = {
        "paired_total_ratio_confirmatory": ratio["geometric_mean_total_latency_ratio"],
        "paired_total_ci_low": ratio["cluster_bootstrap_95_ci_total"]["low"],
        "paired_total_ci_high": ratio["cluster_bootstrap_95_ci_total"]["high"],
        "paired_eval_ratio_confirmatory": ratio["geometric_mean_eval_only_ratio"],
    }
    for key, value in evidence_values.items():
        if registry.get(key) != value:
            errors.append(f"registry/evidence mismatch: {key}")

    for name, prefix in (("sobel", "non_tabular_sobel"), ("harris", "non_tabular_harris")):
        summary = load_json(root / f"docs/evidence/{prefix}_holdout_v1/summary.json")
        validation = summary["selection"]["encrypted_sample_evaluations"] // summary["selection"]["fresh_key_runs"]
        audit = summary["locked_audit"]["encrypted_sample_evaluations"] // summary["locked_audit"]["fresh_key_runs"]
        if registry[f"{name}_validation_samples"] != validation:
            errors.append(f"registry/evidence mismatch: {name}_validation_samples")
        if registry[f"{name}_audit_samples"] != audit:
            errors.append(f"registry/evidence mismatch: {name}_audit_samples")
    cnn = load_json(root / "docs/evidence/non_tabular_mnist_cnn_lite_holdout_v1/summary.json")
    if registry["cnn_lite_validation_samples"] != cnn["selection"]["samples"]:
        errors.append("registry/evidence mismatch: cnn_lite_validation_samples")
    if registry["cnn_lite_audit_samples"] != cnn["locked_audit"]["samples"]:
        errors.append("registry/evidence mismatch: cnn_lite_audit_samples")


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
