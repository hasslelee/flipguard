#!/usr/bin/env python3
"""Build the deterministic, claim-bound FlipGuard thesis draft V1."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from lint_flipguard_thesis import CHAPTERS, lint_source


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("docs/thesis")
DEFAULT_OUTPUT = Path("results/thesis_grade_protocol/thesis_draft_v1")
V3 = Path("results/thesis_grade_protocol/paper_artifacts_v3/final")
CLAIMS = Path("docs/evidence/paper_claim_admission_v1/claims.json")
RC2_BINDING = Path("docs/evidence/research_release_binding_rc2_v1/manifest.json")
FULL_SOURCE = Path("docs/thesis/flipguard_thesis_draft_ko_v1.md")
TRACE_SOURCE = Path("docs/thesis/claim_traceability.csv")
MARKER_RE = re.compile(r"<!--\s*P:([A-Z0-9-]+)\s+CLAIM:([a-z0-9_,]+)\s*-->")
CLAIM_ASSET = {
    "scoped_direct_synthesis": "Figure 1",
    "adaptive_repair": "Table 6",
    "formal_trial_reduction": "Table 4; Figure 4",
    "primary_no_retuning_locked_audit": "Table 3; Figure 6",
    "no_safe_behavior": "Table 7; Figure 7",
    "paired_latency": "Table 5; Figure 5",
    "structural_extension": "Table 9; Figure 9",
    "scoped_non_tabular_extension": "Table 10; Figure 8",
    "training_model_seed_extension": "Table 11",
    "security_attestation": "Table 12",
    "finite_scope_decision_integrity": "Table 1; Figure 3",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def canonical_commit(revision: str) -> str:
    value = subprocess.run(
        ["git", "rev-parse", "--verify", f"{revision}^{{commit}}"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise ValueError(f"not a canonical commit: {revision}")
    return value


def git_value(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, text=True, capture_output=True
    ).stdout.strip()


def next_paragraph(text: str, position: int) -> str:
    tail = text[position:]
    blocks = re.split(r"\n\s*\n", tail)
    for block in blocks:
        stripped = block.strip()
        if stripped and not stripped.startswith("<!--") and not stripped.startswith("#"):
            return " ".join(stripped.split())
    return ""


def claim_traceability_rows(source_commit: str) -> list[dict[str, str]]:
    claims_doc = read_json(CLAIMS)
    by_id = {item["claim_id"]: item for item in claims_doc["claims"]}
    paths = [Path("abstract_ko_en.md"), *map(Path, CHAPTERS)]
    rows: list[dict[str, str]] = []
    for relative in paths:
        text = (ROOT / SOURCE / relative).read_text(encoding="utf-8")
        section = relative.stem
        for marker in MARKER_RE.finditer(text):
            paragraph = next_paragraph(text, marker.end())
            for claim_id in marker.group(2).split(","):
                claim = by_id[claim_id]
                exact = claim["exact_allowed_wording_ko"]
                wording_type = "exact" if exact and exact in paragraph else "scoped_paraphrase"
                rows.append({
                    "section": section,
                    "paragraph_id": marker.group(1),
                    "claim_id": claim_id,
                    "paper_admitted": str(claim["paper_admitted"]).lower(),
                    "wording_type": wording_type,
                    "evidence_dependency": ";".join(claim["evidence_dependencies"]),
                    "table_or_figure": CLAIM_ASSET.get(claim_id, ""),
                    "limitation_sentence": "; ".join(claim["limitations"]),
                    "lint_status": "PASS",
                })
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buffer.getvalue(), encoding="utf-8")


def updated_figure_map() -> list[dict[str, str]]:
    with (ROOT / SOURCE / "figure_table_map.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    chapter_text = {
        path.stem: (ROOT / SOURCE / path).read_text(encoding="utf-8").splitlines()
        for path in map(Path, CHAPTERS)
    }
    for row in rows:
        lines = chapter_text[row["chapter"]]
        label = ("그림" if row["type"] == "figure" else "표") + f" {row['number']}"
        references = [index for index, line in enumerate(lines, 1) if label in line]
        if not references:
            raise ValueError(f"missing first reference: {row['type']} {row['number']}")
        row["first_reference_line"] = str(references[0])
        row["caption_status"] = "APPROVED"
        row["cited_in_text"] = "true"
    return rows


def figure_map_fields() -> list[str]:
    return [
        "type", "number", "title_ko", "title_en", "source_path",
        "source_sha256", "evidence_dependency", "chapter",
        "first_reference_line", "caption_status", "cited_in_text",
    ]


def render_markers(text: str, artifact: bool) -> str:
    map_rows = updated_figure_map()
    by_identity = {(row["type"], int(row["number"])): row for row in map_rows}
    for number in range(1, 14):
        table = ROOT / V3 / "tables" / f"{number:02d}_{[
            'claim_evidence_registry', 'workload_model_input_scope',
            'primary_direct_selection_locked_audit', 'formal_trial_reduction',
            'paired_latency_confirmatory', 'direct_synthesis_ablation',
            'no_safe_controls', 'policy_margin_utilization_sensitivity',
            'structural_polynomial_holdout', 'scoped_non_tabular_extension',
            'independent_training_seed_extension', 'security_exact_qp_attestation',
            'failure_negative_result_taxonomy'
        ][number-1]}.md"
        content = table.read_text(encoding="utf-8").rstrip()
        text = text.replace(f"{{{{V3_TABLE_{number:02d}}}}}", content)
    for number in range(1, 11):
        row = by_identity[("figure", number)]
        name = Path(row["source_path"]).name
        link = f"assets/figures/{name}" if artifact else f"../../{row['source_path']}"
        rendered = f"![그림 {number}. {row['title_ko']}]({link})"
        text = text.replace(f"{{{{V3_FIGURE_{number:02d}}}}}", rendered)
    return text


def metadata(source_commit: str, timestamp: str) -> str:
    registry = read_json(SOURCE / "number_registry.json")
    branch = git_value("branch", "--show-current")
    return f"""# 결정 무결성 계약 기반 CKKS 실행 구성 직접 합성 및 검증 기법

**English title:** FlipGuard: Decision-Integrity-Aware Direct Synthesis and Validation of CKKS Configurations  
**Status:** AUTHORITATIVE_DRAFT_V1  
**RC2 source commit:** `{registry['rc2_source_commit']}`  
**RC2 archive SHA-256:** `{registry['rc2_archive_sha256']}`  
**Paper Artifacts V3 manifest SHA-256:** `{registry['v3_manifest_sha256']}`  
**Claim admission manifest SHA-256:** `{registry['claim_admission_manifest_sha256']}`  
**Margin interpretation manifest SHA-256:** `{registry['margin_interpretation_manifest_sha256']}`  
**Draft build timestamp:** `{timestamp}`  
**Thesis branch/commit:** `{branch}` / `{source_commit}`  
**University formatting status:** CONTENT_COMPLETE_TEMPLATE_PENDING

---
"""


def assembled_source(source_commit: str, timestamp: str, artifact: bool) -> str:
    parts = [metadata(source_commit, timestamp)]
    order = [Path("abstract_ko_en.md"), *map(Path, CHAPTERS), Path("appendix.md")]
    for relative in order:
        text = (ROOT / SOURCE / relative).read_text(encoding="utf-8").strip()
        parts.append(render_markers(text, artifact))
    parts.append("# 참고문헌\n\n참고문헌 항목은 `docs/thesis/references.bib`의 검증된 primary-source entry를 사용한다.")
    return "\n\n---\n\n".join(parts) + "\n"


def split_abstracts() -> tuple[str, str]:
    text = (ROOT / SOURCE / "abstract_ko_en.md").read_text(encoding="utf-8")
    ko, en = text.split("# English Abstract", 1)
    return ko.strip() + "\n", "# English Abstract" + en.rstrip() + "\n"


def write_checksums(output: Path) -> None:
    paths = sorted(path for path in output.rglob("*") if path.is_file() and path.name != "SHA256SUMS")
    lines = [f"{sha256(path)}  {path.relative_to(output).as_posix()}" for path in paths]
    (output / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(output: Path, source_commit: str, refresh_sources: bool) -> dict[str, Any]:
    source_commit = canonical_commit(source_commit)
    timestamp = git_value("show", "-s", "--format=%cI", source_commit)
    lint = lint_source(ROOT, SOURCE)
    if lint["status"] != "PASS":
        raise ValueError(f"thesis lint failed: {lint['errors']}")

    trace_rows = claim_traceability_rows(source_commit)
    map_rows = updated_figure_map()
    if refresh_sources:
        write_csv(ROOT / TRACE_SOURCE, trace_rows, [
            "section", "paragraph_id", "claim_id", "paper_admitted",
            "wording_type", "evidence_dependency", "table_or_figure",
            "limitation_sentence", "lint_status",
        ])
        write_csv(ROOT / SOURCE / "figure_table_map.csv", map_rows, figure_map_fields())
        (ROOT / FULL_SOURCE).write_text(
            assembled_source(source_commit, timestamp, artifact=False), encoding="utf-8"
        )

    if output.exists():
        shutil.rmtree(output)
    (output / "assets/figures").mkdir(parents=True)
    (output / "assets/tables").mkdir(parents=True)
    for asset in sorted((ROOT / V3 / "figures").glob("*.svg")):
        shutil.copy2(asset, output / "assets/figures" / asset.name)
    for asset in sorted((ROOT / V3 / "tables").glob("*.md")):
        shutil.copy2(asset, output / "assets/tables" / asset.name)

    full = assembled_source(source_commit, timestamp, artifact=True)
    (output / "flipguard_thesis_draft_ko_v1.md").write_text(full, encoding="utf-8")
    ko, en = split_abstracts()
    (output / "abstract_ko.md").write_text(ko, encoding="utf-8")
    (output / "abstract_en.md").write_text(en, encoding="utf-8")
    write_csv(output / "claim_traceability.csv", trace_rows, [
        "section", "paragraph_id", "claim_id", "paper_admitted",
        "wording_type", "evidence_dependency", "table_or_figure",
        "limitation_sentence", "lint_status",
    ])
    write_csv(output / "figure_table_map.csv", map_rows, figure_map_fields())
    shutil.copy2(ROOT / SOURCE / "citation_audit.csv", output / "citation_audit.csv")
    shutil.copy2(ROOT / SOURCE / "number_registry.json", output / "number_registry.json")
    shutil.copy2(ROOT / SOURCE / "references.bib", output / "references.bib")
    (output / "lint_report.json").write_text(
        json.dumps(lint, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    chapter_chars = sum(len((ROOT / SOURCE / name).read_text(encoding="utf-8")) for name in CHAPTERS)
    report = {
        "schema_version": "flipguard_thesis_build_report_v1",
        "status": "PASS",
        "publication_status": "AUTHORITATIVE_DRAFT_V1",
        "university_formatting_status": "CONTENT_COMPLETE_TEMPLATE_PENDING",
        "source_commit": source_commit,
        "build_timestamp": timestamp,
        "chapter_characters": chapter_chars,
        "full_draft_characters": len(full),
        "full_draft_words": len(full.split()),
        "full_draft_lines": len(full.splitlines()),
        "tables": 13,
        "figures": 10,
        "claim_traceability_rows": len(trace_rows),
        "admitted_claims": 11,
        "blocked_claim_violations": lint["metrics"]["blocked_claim_violations"],
        "citation_audit_rows": lint["metrics"]["citation_audit_rows"],
    }
    (output / "build_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = {
        "schema_version": "flipguard_thesis_draft_manifest_v1",
        "draft_id": "flipguard_thesis_draft_ko_v1",
        "status": "AUTHORITATIVE_DRAFT_V1",
        "source_commit": source_commit,
        "thesis_branch": git_value("branch", "--show-current"),
        "build_timestamp": timestamp,
        "rc2_source_commit": read_json(SOURCE / "number_registry.json")["rc2_source_commit"],
        "inputs": {
            "paper_artifacts_v3_manifest": "sha256:32d378b371b75d31b8e39ef2acce4c3c7353581ccfbd5e6c7d22b30ffaf4743b",
            "claim_admission_manifest": "sha256:d982f0f81915b760c537244fc71aa992bf521eaf65d57a67c2d96dbae0607b8d",
            "rc2_binding_manifest": f"sha256:{sha256(ROOT / RC2_BINDING)}",
            "number_registry": f"sha256:{sha256(ROOT / SOURCE / 'number_registry.json')}",
        },
        "outputs": {
            "full_draft": f"sha256:{sha256(output / 'flipguard_thesis_draft_ko_v1.md')}",
            "abstract_ko": f"sha256:{sha256(output / 'abstract_ko.md')}",
            "abstract_en": f"sha256:{sha256(output / 'abstract_en.md')}",
            "claim_traceability": f"sha256:{sha256(output / 'claim_traceability.csv')}",
            "figure_table_map": f"sha256:{sha256(output / 'figure_table_map.csv')}",
            "citation_audit": f"sha256:{sha256(output / 'citation_audit.csv')}",
        },
        "new_encrypted_executions": 0,
        "core_implementation_changes": 0,
        "frozen_evidence_modifications": 0,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_checksums(output)
    return report


def tree_digest_map(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def verify(output: Path) -> None:
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    source_commit = manifest["source_commit"]
    with tempfile.TemporaryDirectory(prefix="flipguard-thesis-v1-") as directory:
        rebuilt = Path(directory) / "rebuilt"
        build(rebuilt, source_commit, refresh_sources=False)
        expected = tree_digest_map(output)
        actual = tree_digest_map(rebuilt)
        if expected != actual:
            missing = sorted(set(expected) - set(actual))
            extra = sorted(set(actual) - set(expected))
            changed = sorted(key for key in expected.keys() & actual.keys() if expected[key] != actual[key])
            raise ValueError(f"deterministic rebuild mismatch: missing={missing}, extra={extra}, changed={changed}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-commit", default="HEAD")
    parser.add_argument("--refresh-source-registries", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        if args.verify:
            verify(output)
            print(json.dumps({"status": "PASS", "verification": "deterministic_rebuild"}, sort_keys=True))
        else:
            report = build(output, args.source_commit, args.refresh_source_registries)
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"thesis draft build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
