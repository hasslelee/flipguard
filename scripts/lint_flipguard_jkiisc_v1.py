#!/usr/bin/env python3
"""Lint the authorless JKIISC FlipGuard manuscript against frozen claims."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


NEGATION_MARKERS = (
    " not ",
    " no ",
    "does not",
    "do not",
    "cannot",
    "blocked",
    "prohibited",
    "금지",
    "않",
    "아니",
    "없",
    "뜻하지",
    "입증하지",
    "평가하지",
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def claim_phrases(root: Path) -> set[str]:
    phrases: set[str] = set()
    for path in [
        root / "docs/evidence/paper_claim_admission_v1/claims.json",
        root / "docs/evidence/journal_multiclass_claim_admission_v2/claims.json",
    ]:
        for claim in load_json(path)["claims"]:
            key = "prohibited_overclaim" if "prohibited_overclaim" in claim else "prohibited_wording"
            phrases.update(str(value).lower() for value in claim[key])
    return phrases


def affirmative_prohibited_hits(root: Path, text: str) -> list[dict]:
    hits: list[dict] = []
    lines = text.splitlines()
    for phrase in sorted(claim_phrases(root)):
        for line_index, line in enumerate(lines):
            lowered = " " + line.lower() + " "
            if phrase not in lowered:
                continue
            context = lowered
            if line.startswith("|"):
                context = " ".join(lines[max(0, line_index - 3) : line_index + 1]).lower()
            if not any(marker in context for marker in NEGATION_MARKERS):
                hits.append({"phrase": phrase, "line": line_index + 1})
    return hits


def audit_manuscript(root: Path, text: str, *, rendered: bool) -> dict:
    findings: list[dict] = []

    def check(condition: bool, code: str, detail: str) -> None:
        if not condition:
            findings.append({"code": code, "detail": detail})

    abstracts = (root / "docs/journal/abstract_ko_en.md").read_text(encoding="utf-8")
    korean = abstracts.split("# English abstract", 1)[0].split("# 국문 요약", 1)[1]
    korean = korean.split("**주요어:**", 1)[0].strip()
    english = abstracts.split("# English abstract", 1)[1].split("**Keywords:**", 1)[0].strip()
    keyword_line = abstracts.split("**Keywords:**", 1)[1].strip().splitlines()[0]
    check(len(korean) <= 700, "KO_ABSTRACT_LIMIT", str(len(korean)))
    check(len(english.split()) <= 250, "EN_ABSTRACT_LIMIT", str(len(english.split())))
    check(len([word for word in keyword_line.split(",") if word.strip()]) <= 5, "KEYWORD_LIMIT", keyword_line)

    expected_title = "결정 무결성 계약 기반 CKKS 실행 구성 직접 합성 및 검증"
    expected_english_title = "FlipGuard: Direct Synthesis and Validation of CKKS Configurations under Decision-Integrity Contracts"
    check(expected_title in text, "KOREAN_TITLE", expected_title)
    check(expected_english_title in text, "ENGLISH_TITLE", expected_english_title)
    check(not re.search(r"(?im)^\s*(author|authors?|저자|소속|affiliation)\s*[:：]", text), "AUTHORLESS", "author metadata found")
    check(not re.search(r"\b(?:TODO|TBD|PLACEHOLDER)\b", text, flags=re.I), "PLACEHOLDER", "placeholder found")

    for hit in affirmative_prohibited_hits(root, text):
        findings.append({"code": "PROHIBITED_CLAIM", "detail": f"{hit['phrase']} at line {hit['line']}"})

    required_numbers = [
        "70/700",
        "56/560",
        "90%",
        "40/40",
        "3.140660",
        "[2.342334, 4.215313]",
        "0.999780",
        "[0.998648, 1.000920]",
        "1.981795",
        "[1.979758, 1.983842]",
        "24 PASS",
        "1 reserve-policy REJECT",
        "16건에서 NO_SAFE",
        "50/50에서 NO_SAFE",
    ]
    for value in required_numbers:
        check(value in text, "NUMBER_REGISTRY", value)
    check("1,100 historical" in text or "Historical 1,100" in text, "HISTORICAL_1100", "1,100 context")
    check("formal denominator는 700" in text, "FORMAL_700", "formal denominator")
    check("Confirmatory denominator는 560" in text, "FORMAL_560", "confirmatory denominator")
    check("e_c(x)<m(x)" in text, "THEOREM_CONDITION", "e<m")
    check("e_c(x)<rho*m(x)" in text, "RESERVE_POLICY", "e<rho*m")
    check("0.5는 CKKS 이론에서 도출된 상수나 최적값이 아니라" in text, "RHO_INTERPRETATION", "rho caveat")
    check("PLAN_UNSUPPORTED_WITHIN_FROZEN_CATALOG" in text, "LENET_CATALOG_STATUS", "LeNet status")
    check("S29의 S32 대비 latency superiority는 인정하지 않는다" in text, "MLP_NO_SUPERIORITY", "S29/S32 boundary")
    check("Xe truncation exact equivalence" in text, "XE_CAVEAT", "Xe caveat")
    check("Quantum cost model" in text, "QUANTUM_CAVEAT", "quantum caveat")

    captions = re.findall(r"\*\*Fig\. ([1-9][0-9]*)\. ([^*]+)\*\*", text)
    table_titles = re.findall(r"\*\*Table ([1-9][0-9]*)\. ([^*]+)\*\*", text)
    check([int(number) for number, _ in captions] == list(range(1, 7)), "FIGURE_SEQUENCE", repr(captions))
    check([int(number) for number, _ in table_titles] == list(range(1, 8)), "TABLE_SEQUENCE", repr(table_titles))
    for number, title in [*captions, *table_titles]:
        check(not re.search(r"[가-힣]", title), "ENGLISH_CAPTION", f"{number}:{title}")
    table_lines = [line for line in text.splitlines() if line.startswith("|")]
    for index, line in enumerate(table_lines, 1):
        check(not re.search(r"[가-힣]", line), "ENGLISH_TABLE_CONTENT", f"table line {index}")
    references = text.split("# References", 1)[1] if "# References" in text else ""
    check(bool(references), "REFERENCES_SECTION", "missing")
    check(not re.search(r"[가-힣]", references), "ENGLISH_REFERENCES", "Hangul in references")

    body = text.split("# References", 1)[0]
    cited = {int(value) for value in re.findall(r"\[([1-9][0-9]*)\]", body)}
    listed = {int(value) for value in re.findall(r"(?m)^\[([1-9][0-9]*)\]", references)}
    check(cited == set(range(1, 13)), "CITATION_COVERAGE", repr(sorted(cited)))
    check(listed == set(range(1, 13)), "REFERENCE_SEQUENCE", repr(sorted(listed)))
    with (root / "docs/journal/reference_map.csv").open(newline="", encoding="utf-8") as handle:
        reference_rows = list(csv.DictReader(handle))
    check({int(row["number"]) for row in reference_rows} == listed, "REFERENCE_MAP", "number mismatch")
    check(all(row["status"] in {"VERIFIED", "PREPRINT_VERIFIED"} for row in reference_rows), "REFERENCE_STATUS", "unverified source")

    with (root / "docs/journal/figure_table_map.csv").open(newline="", encoding="utf-8") as handle:
        map_rows = list(csv.DictReader(handle))
    check(len([row for row in map_rows if row["type"] == "Figure"]) == 6, "FIGURE_MAP_COUNT", "expected 6")
    check(len([row for row in map_rows if row["type"] == "Table"]) == 7, "TABLE_MAP_COUNT", "expected 7")
    for row in map_rows:
        source = root / row["source_path"]
        check(source.is_file(), "MAP_SOURCE", row["source_path"])
        if source.is_file():
            check(sha256(source) == row["source_sha256"], "MAP_DIGEST", row["source_path"])
        marker = f"Fig. {row['number']}" if row["type"] == "Figure" else f"Table {row['number']}"
        check(marker in text, "MAP_CITATION", marker)

    placeholders = set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", text))
    expected_placeholders = {"ABSTRACTS", *(f"FIGURE_{index:02d}" for index in range(1, 7))}
    if rendered:
        check(not placeholders, "RENDERED_PLACEHOLDER", repr(sorted(placeholders)))
        check(len(re.findall(r"!\[Fig\. [1-6]\]", text)) == 6, "RENDERED_FIGURES", "expected 6 images")
    else:
        check(placeholders == expected_placeholders, "SOURCE_PLACEHOLDERS", repr(sorted(placeholders)))

    chapters = re.findall(r"(?m)^# (I|II|III|IV|V|VI|VII|VIII)\. ", text)
    check(chapters == ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"], "CHAPTER_SEQUENCE", repr(chapters))
    check("50 independent workload가 아니다" in text, "INDEPENDENCE_CAVEAT", "primary unit caveat")
    check("5,400 raw records나 1,800 pairs를 독립 표본으로 취급하지 않는다" in text, "PAIR_INDEPENDENCE", "paired unit caveat")

    return {
        "abstract": {"english_words": len(english.split()), "korean_characters": len(korean)},
        "citations": len(cited),
        "figures": len(captions),
        "findings": findings,
        "rendered": rendered,
        "status": "PASS" if not findings else "FAIL",
        "tables": len(table_titles),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manuscript", default="docs/journal/01_manuscript_ko.md")
    parser.add_argument("--rendered", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = audit_manuscript(root, (root / args.manuscript).read_text(encoding="utf-8"), rendered=args.rendered)
    payload = json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    if args.output:
        (root / args.output).write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
