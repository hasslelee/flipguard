#!/usr/bin/env python3
"""Audit developer-facing terminology without modifying manuscript artifacts."""

import csv
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audits"

TERMS = {
    "Security-V2": ("policy", "사전에 고정한 보안 적합성 정책(Security-V2)", "KEEP_FIRST_ONLY"),
    "held-out": ("evaluation_role", "구성 고정 독립 평가", "REPLACE"),
    "confirmatory": ("evaluation_role", "정책 동결 후 확증", "REPLACE"),
    "development/ablation": ("evaluation_role", "개발·소거분석", "REPLACE"),
    "workload-partition": ("statistical_unit", "모델·데이터 분할 사례", "REPLACE"),
    "arm": ("measurement", "비교 구성", "REPLACE"),
    "profile": ("configuration", "사전 정의 구성", "REPLACE"),
    "path": ("configuration", "실행 방식", "CONTEXTUAL_REPLACE"),
    "admission": ("system_action", "적합성 판정", "REPLACE"),
    "validation": ("evaluation_role", "구성-선택 평가", "REPLACE"),
    "materialization": ("implementation", "실행 구성 구체화", "REPLACE"),
    "provenance": ("artifact", "생성 이력", "REPLACE"),
    "digest": ("artifact", "SHA-256 요약값", "KEEP_REPRO_SECTION"),
    "manifest": ("artifact", "재현성 명세", "KEEP_REPRO_SECTION"),
    "tier": ("presentation", "평가 계층", "REPLACE"),
    "evidence layer": ("presentation", "근거 계층", "REPLACE"),
    "candidate evaluation": ("statistical_unit", "후보 구성 평가", "REPLACE"),
    "context": ("cryptographic_repeat", "독립 키 집합 실행", "CONTEXTUAL_REPLACE"),
    "keyset": ("cryptographic_repeat", "독립 키 집합", "REPLACE"),
    "measurement pass": ("measurement", "측정 반복", "REPLACE"),
    "paired protocol": ("measurement", "동일 입력·호스트·순서를 사용한 짝지은 측정", "REPLACE"),
    "dataset-model cluster": ("statistical_unit", "데이터셋-모델 군집", "REPLACE"),
    "numerical-only evidence": ("claim_scope", "판단 안정성을 포함하지 않은 수치 오차 근거", "REPLACE"),
    "robustness": ("claim_scope", "추가 조건에서의 재현 여부", "REPLACE"),
    "PLAN_UNSUPPORTED": ("status", "현재 후보군에서 요구 연산 깊이를 지원하지 않음", "KEEP_WITH_DEFINITION"),
    "raw row": ("statistical_unit", "원시 기록 행", "REPLACE"),
    "scope boundary": ("claim_scope", "주장 범위", "REPLACE"),
    "comparator": ("comparison", "비교 구성", "REPLACE"),
    "retuning": ("system_action", "평가 결과를 이용한 재조정", "REPLACE"),
    "freeze": ("protocol", "사전 고정", "REPLACE"),
    "frozen": ("protocol", "사전 고정된", "REPLACE"),
    "first-SAFE": ("selection_rule", "고정 순서에서 처음 SAFE인 구성", "KEEP_WITH_DEFINITION"),
    "bounded repair": ("system_action", "횟수와 방향이 고정된 제한적 보정", "REPLACE"),
    "graph adapter": ("implementation", "지원 계산 그래프 변환기", "REPLACE"),
    "optional comparison interface": ("architecture", "선택적 비교 입력 경로", "REPLACE"),
    "formal denominator": ("statistics", "사전에 정한 비교 후보 수", "REPLACE"),
    "historical pre-security": ("accounting", "보안 필터 적용 전 과거 실행 기록", "REPLACE"),
}


def zip_text(path: Path) -> list[tuple[str, str]]:
    rows = []
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.endswith(".xml") and (name.startswith("word/") or name.startswith("ppt/slides/"))]
        for member in sorted(members):
            root = ElementTree.fromstring(archive.read(member))
            text = " ".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))
            if text.strip(): rows.append((member, text))
    return rows


def text_sections(path: Path) -> list[tuple[str, str]]:
    if path.suffix.lower() in {".docx", ".pptx"}: return zip_text(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    sections, current, lines = [], "document", []
    for line in text.splitlines():
        if line.startswith("#"):
            if lines: sections.append((current, " ".join(lines)))
            current, lines = line.lstrip("# ").strip() or "section", []
        else: lines.append(line)
    if lines: sections.append((current, " ".join(lines)))
    return sections


def sentence(text: str, start: int) -> str:
    left = max(text.rfind(".", 0, start), text.rfind("다.", 0, start), text.rfind("\n", 0, start))
    right_candidates = [pos for pos in (text.find(".", start), text.find("다.", start), text.find("\n", start)) if pos >= 0]
    right = min(right_candidates) + 2 if right_candidates else min(len(text), start + 240)
    return re.sub(r"\s+", " ", text[left + 1:right]).strip()[:360]


def targets() -> list[Path]:
    result = []
    for pattern in ("docs/*v16_1.docx", "docs/*v16_1.pptx", "docs/V16_1_PRE_HWP_CHANGELOG.md", "docs/manuscript_revision_v16_1/**/*.md", "docs/reports/**/*.md"):
        result.extend(path for path in ROOT.glob(pattern) if path.is_file())
    return sorted(set(result))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    occurrences = []
    for path in targets():
        for section_name, text in text_sections(path):
            for term, (category, korean, decision) in TERMS.items():
                for match in re.finditer(re.escape(term), text, flags=re.IGNORECASE):
                    occurrences.append({"file": path.relative_to(ROOT).as_posix(), "page_or_section": section_name, "original_term": match.group(0), "surrounding_sentence": sentence(text, match.start()), "category": category, "recommended_korean": korean, "keep_or_replace": decision, "reason": "paper-facing prose should define the concept before exposing an internal identifier"})
    csv_path = OUT / "paper_terminology_occurrences_v17.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        fields = ["file", "page_or_section", "original_term", "surrounding_sentence", "category", "recommended_korean", "keep_or_replace", "reason"]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n"); writer.writeheader(); writer.writerows(occurrences)
    contract = {"schema_version": "flipguard_paper_terminology_contract_v17", "rule": "easy Korean first; English/internal identifier once at first definition or in reproducibility", "terms": {term: {"category": values[0], "recommended_korean": values[1], "disposition": values[2]} for term, values in TERMS.items()}, "manuscript_automatic_modification": False}
    (OUT / "paper_terminology_contract_v17.json").write_text(json.dumps(contract, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    counts = {}
    for item in occurrences: counts[item["original_term"].lower()] = counts.get(item["original_term"].lower(), 0) + 1
    report = ["# Paper Terminology Audit V17", "", "## Scope", "", "This audit is read-only with respect to DOCX, HWP-facing DOCX, PPTX, and frozen evidence. It identifies implementation-facing vocabulary that should be replaced when V17 results are later integrated into a manuscript.", "", "## Findings", "", f"- Files scanned: {len(targets())}", f"- Occurrences recorded: {len(occurrences)}", f"- Terms in the contract: {len(TERMS)}", "- Internal model IDs remain permitted once in the reproducibility section; paper-facing model names are required elsewhere.", "", "## Required editorial rule", "", "Use easy Korean first, give the exact English term or identifier once when necessary, and explain its role in the study. SAFE, REJECTED, FAILED, NO_SAFE, and PLAN_UNSUPPORTED remain distinct states and must not be translated into one generic failure label.", "", "## Highest-frequency terms", ""]
    for term, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:20]: report.append(f"- `{term}`: {count}")
    report.extend(["", "## Non-action", "", "No manuscript, presentation, policy, code result, or frozen evidence file was edited by this audit.", ""])
    (OUT / "PAPER_TERMINOLOGY_AUDIT_V17.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"status": "PASS", "files": len(targets()), "occurrences": len(occurrences)}, sort_keys=True))


if __name__ == "__main__":
    main()
