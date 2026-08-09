#!/usr/bin/env python3
"""Shared, read-only helpers for the final manuscript audit overlay."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


@dataclass(frozen=True)
class DocxParagraph:
    document: str
    paragraph_index: int
    style: str
    text: str
    section: str


@dataclass(frozen=True)
class DocxTable:
    document: str
    table_index: int
    rows: tuple[tuple[str, ...], ...]


def _paragraph_text(paragraph: ET.Element) -> str:
    pieces: list[str] = []
    for node in paragraph.iter():
        if node.tag == f"{W_NS}t" and node.text:
            pieces.append(node.text)
        elif node.tag == f"{W_NS}tab":
            pieces.append("\t")
        elif node.tag in {f"{W_NS}br", f"{W_NS}cr"}:
            pieces.append("\n")
    return re.sub(r"[ \t]+", " ", "".join(pieces)).strip()


def _paragraph_style(paragraph: ET.Element) -> str:
    style = paragraph.find(f"{W_NS}pPr/{W_NS}pStyle")
    return "" if style is None else style.attrib.get(f"{W_NS}val", "")


def _looks_like_section(text: str, style: str) -> bool:
    if style.lower().startswith(("heading", "title")):
        return True
    patterns = (
        r"^(?:I|II|III|IV|V|VI|VII|VIII|IX|X)\.\s+",
        r"^\d+(?:\.\d+){0,2}\s+",
        r"^제\s*\d+\s*장",
        r"^(?:국문|영문)?\s*초록$",
        r"^(?:참고문헌|References|부록|Appendix)$",
    )
    return any(re.match(pattern, text, re.IGNORECASE) for pattern in patterns)


def extract_docx(path: Path, document: str) -> tuple[list[DocxParagraph], list[DocxTable]]:
    """Extract all body paragraphs in XML order, including paragraphs in cells."""
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    body = root.find(f"{W_NS}body")
    if body is None:
        raise ValueError(f"missing Word body: {path}")

    paragraphs: list[DocxParagraph] = []
    current_section = "FRONT_MATTER"
    for index, paragraph in enumerate(body.iter(f"{W_NS}p"), 1):
        text = _paragraph_text(paragraph)
        if not text:
            continue
        style = _paragraph_style(paragraph)
        if _looks_like_section(text, style):
            current_section = text
        paragraphs.append(
            DocxParagraph(document, index, style, text, current_section)
        )

    tables: list[DocxTable] = []
    for table_index, table in enumerate(body.iter(f"{W_NS}tbl"), 1):
        rows: list[tuple[str, ...]] = []
        for row in table.findall(f"{W_NS}tr"):
            cells: list[str] = []
            for cell in row.findall(f"{W_NS}tc"):
                text = " ".join(
                    value for value in (_paragraph_text(p) for p in cell.iter(f"{W_NS}p")) if value
                )
                cells.append(text)
            rows.append(tuple(cells))
        tables.append(DocxTable(document, table_index, tuple(rows)))
    return paragraphs, tables


def split_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"<!--.*?-->", "", text).strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9가-힣\[])|(?<=다\.)\s*", cleaned)
    return [part.strip() for part in parts if part.strip()]


def load_claims() -> dict[str, dict[str, Any]]:
    claims: dict[str, dict[str, Any]] = {}
    sources = [
        ROOT / "docs/evidence/paper_claim_admission_v1/claims.json",
        ROOT / "docs/evidence/journal_multiclass_claim_admission_v2/claims.json",
    ]
    for source in sources:
        payload = read_json(source)
        for claim in payload["claims"]:
            normalized = dict(claim)
            normalized["registry_source"] = relative(source)
            claims[claim["claim_id"]] = normalized
    v8_path = ROOT / "docs/evidence/focused_external_comparison_v8/claim_admission.json"
    for claim_id, state in read_json(v8_path)["claims"].items():
        claims.setdefault(
            claim_id,
            {
                "claim_id": claim_id,
                "state": state,
                "paper_admitted": state in {"SUPPORTED", "PARTIALLY_SUPPORTED"},
                "scope": "V8 external-comparison declared workload and runtime scope",
                "registry_source": relative(v8_path),
                "evidence": [relative(v8_path)],
            },
        )
    v9_path = ROOT / "docs/evidence/final_realistic_baseline_closure_v9/final_claim_admission.json"
    for claim_id, claim in read_json(v9_path)["claims"].items():
        normalized = dict(claim)
        normalized.update(
            {
                "claim_id": claim_id,
                "registry_source": relative(v9_path),
                "scope": claim.get("scope", "V9 external comparison scope"),
                "paper_admitted": claim.get("paper_admitted", False),
            }
        )
        claims[claim_id] = normalized
    return claims


CLAIM_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("formal_trial_reduction", ("70", "700", "90%", "trial", "후보 실행")),
    ("primary_no_retuning_locked_audit", ("40/40", "locked audit", "고정 감사", "재조정 없이")),
    ("no_safe_behavior", ("NO_SAFE", "abstain")),
    ("paired_latency", ("3.140", "3.14", "bounded-catalog", "catalog/direct")),
    ("structural_extension", ("24", "reserve-policy", "구조 확장")),
    ("scoped_non_tabular_extension", ("Sobel", "Harris", "CNN-lite")),
    ("training_model_seed_extension", ("training seed", "학습 seed", "9/9", "독립 학습")),
    ("multiclass_argmax_proposition", ("argmax", "top-two", "logit", "다중 클래스")),
    ("mlp100_finite_validation_audit", ("MLP-100", "784-100", "S29")),
    ("lenet5_small_finite_validation_audit", ("LeNet-5-small", "S44")),
    ("natural_top_two_gap_literal_effect", ("S32", "S29", "gap-aware")),
    ("p3_catalog_over_heir_latency", ("6.393", "catalog/HEIR", "P3")),
    ("direct_repeat_flip_classification", ("8회", "여덟", "V_amb", "near-boundary")),
    ("corelab_eva_elasm_numerical_grid", ("CoreLab", "NUMERICAL_ONLY", "14,000")),
    ("eva_substantial_population_and_locked_audit", ("S20", "S30", "S40", "133회", "1,000 unique")),
    ("heir_decision_bearing_shared_polynomial", ("HEIR-Lattigo", "HEIR-OpenFHE", "shared polynomial")),
    ("hecate_measured_provider", ("HECATE",)),
    ("orion_official_encrypted_self_test", ("Orion",)),
    ("security_attestation", ("Security-V2", "128-bit", "security admission", "보안 적합")),
    ("finite_scope_decision_integrity", ("decision-integrity", "결정 무결성", "decision stability", "결정 안정성", "판단 보존", "판단 반전")),
    ("scoped_direct_synthesis", ("직접 합성", "direct synthesis", "literal")),
    ("adaptive_repair", ("bounded repair", "제한적 수리", "repair")),
)


BACKGROUND_TERMS = (
    "CKKS",
    "CHET",
    "EVA",
    "HECO",
    "DaCapo",
    "AutoFHE",
    "FHE-Agent",
    "Application-Aware",
    "Lattigo",
    "관련 연구",
)


def classify_claims(sentence: str, claims: dict[str, dict[str, Any]]) -> list[str]:
    lowered = sentence.lower()
    matches: list[str] = []
    for claim_id, patterns in CLAIM_PATTERNS:
        if claim_id in claims and any(pattern.lower() in lowered for pattern in patterns):
            matches.append(claim_id)
    if matches:
        return list(dict.fromkeys(matches))
    if re.search(r"\[[0-9,\- ]+\]", sentence) or any(term.lower() in lowered for term in BACKGROUND_TERMS):
        return ["BACKGROUND"]
    return []


def is_positive_technical_sentence(sentence: str) -> bool:
    if len(sentence) < 25:
        return False
    lowered = sentence.lower()
    technical = (
        "ckks",
        "flipguard",
        "safe",
        "no_safe",
        "latency",
        "오차",
        "후보",
        "검증",
        "감사",
        "보존",
        "비율",
        "보안",
        "argmax",
        "margin",
        "trial",
        "catalog",
        "후보",
        "실험",
        "분석",
        "결과",
        "증거",
    )
    assertion = (
        "였다",
        "했다",
        "한다",
        "보였다",
        "확인",
        "감소",
        "통과",
        "지원",
        "나타",
        "사용",
        "선택",
        "생성",
        "입증",
        "평가",
        "측정",
        "preserv",
        "selected",
        "reduced",
        "passed",
    )
    return any(term in lowered for term in technical) and any(term in lowered for term in assertion)


def state_for_claim_ids(claim_ids: list[str], claims: dict[str, dict[str, Any]]) -> str:
    if not claim_ids:
        return "NOT_EVALUATED"
    if claim_ids == ["BACKGROUND"]:
        return "BACKGROUND"
    states = [str(claims[item].get("state", "NOT_EVALUATED")) for item in claim_ids if item in claims]
    if any(state.startswith("BLOCKED") for state in states):
        return "BLOCKED"
    if any(state in {"PARTIALLY_SUPPORTED", "PILOT_ONLY"} for state in states):
        return "PARTIALLY_SUPPORTED"
    if states and all(state == "SUPPORTED" for state in states):
        return "SUPPORTED"
    return "NOT_EVALUATED"


def checksum_lines(root: Path, paths: Iterable[Path]) -> str:
    lines = []
    for path in sorted(paths, key=lambda item: item.as_posix()):
        lines.append(f"{sha256_file(path)}  {path.relative_to(root).as_posix()}")
    return "\n".join(lines) + "\n"
