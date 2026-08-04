#!/usr/bin/env python3
"""Validate FlipGuard's bilingual public README and GitHub assets."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]

EN_SECTIONS = [
    "Why FlipGuard?",
    "Key Ideas",
    "Architecture",
    "Results at a Glance",
    "Decision-Integrity Contracts",
    "Supported Scope",
    "Quick Start",
    "Reproducing the Results",
    "Repository Layout",
    "Research Artifacts",
    "Claim Boundaries",
    "Citation",
    "Contributing",
    "Security",
    "License",
]
KO_SECTIONS = [
    "왜 FlipGuard인가?",
    "핵심 아이디어",
    "아키텍처",
    "핵심 결과",
    "결정 무결성 계약",
    "지원 범위",
    "빠른 시작",
    "결과 재현",
    "저장소 구조",
    "연구 아티팩트",
    "주장 경계",
    "인용",
    "기여하기",
    "보안",
    "라이선스",
]

HEADLINE_TOKENS = [
    "90%",
    "700",
    "70",
    "560",
    "56",
    "40/40",
    "3.140660",
    "2.342334",
    "4.215313",
    "0.999780",
    "0.998648",
    "1.000920",
    "1.981795",
    "1.979758",
    "1.983842",
    "S29",
    "S32",
    "S40",
    "MLP-100",
    "LeNet-5-small",
]

ASSERTIVE_PROHIBITED = [
    "global optimum",
    "global optimizer",
    "universally safe",
    "universal 128-bit security",
    "universally 128-bit secure",
    "production speedup",
    "production-ready",
    "arbitrary cnn support",
    "complete analytical certificate",
    "complete analytical ckks certificate",
    "first direct ckks synthesizer",
    "first application-aware ckks",
    "state of the art",
]

NEGATIONS_EN = ("not ", "no ", "does not", "do not", "never", "neither", "without ", "outside", "cannot", "isn't", "failed to", "did not")
NEGATIONS_KO = ("아니", "아닙", "않", "없", "금지", "밖", "못", "제외", "확립하지", "주장하지", "의미하지")


@dataclass(frozen=True)
class Issue:
    code: str
    path: str
    line: int
    message: str


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def headings(text: str) -> list[str]:
    return [match.group(1).strip() for match in re.finditer(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE)]


def bash_blocks(text: str) -> list[str]:
    return [match.group(1).strip() for match in re.finditer(r"```bash\n(.*?)\n```", text, flags=re.DOTALL)]


def has_negation(line: str, language: str) -> bool:
    lower = re.sub(r"[*_`]", "", line).casefold()
    terms = NEGATIONS_KO if language == "ko" else NEGATIONS_EN
    return any(term.casefold() in lower for term in terms)


def registry_prohibited_phrases(root: Path = ROOT) -> set[str]:
    phrases: set[str] = set()
    paths = [
        root / "docs/evidence/paper_claim_admission_v1/claims.json",
        root / "docs/evidence/journal_multiclass_claim_admission_v2/claims.json",
    ]
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for claim in payload["claims"]:
            for key in ("prohibited_overclaim", "prohibited_wording"):
                value = claim.get(key, [])
                if isinstance(value, str):
                    value = [value]
                phrases.update(str(item).casefold() for item in value)
    return phrases


def scan_claim_language(text: str, language: str, path: str = "<text>", root: Path = ROOT) -> list[Issue]:
    issues: list[Issue] = []
    phrases = set(ASSERTIVE_PROHIBITED) | registry_prohibited_phrases(root)
    for number, line in enumerate(text.splitlines(), start=1):
        lower = line.casefold()
        for phrase in sorted(phrases):
            if phrase in lower and not has_negation(line, language):
                issues.append(Issue("PROHIBITED_CLAIM", path, number, f"assertive prohibited wording: {phrase}"))

        if re.search(r"\bS29\b.*\b(faster|speedup|superior|outperform)", line, flags=re.IGNORECASE) and not has_negation(line, language):
            issues.append(Issue("S29_SPEED_OVERCLAIM", path, number, "S29-over-S32 latency superiority is not admitted"))
        if "s29" in lower and "s32" in lower and ("빠르" in line or "우월" in line) and not has_negation(line, language):
            issues.append(Issue("S29_SPEED_OVERCLAIM", path, number, "S29-over-S32 latency superiority is not admitted"))
        if "lenet" in lower and "no_safe" in lower and not has_negation(line, language):
            issues.append(Issue("LENET_STATUS", path, number, "LeNet frozen-catalog status is PLAN_UNSUPPORTED, not NO_SAFE"))
        if re.search(r"\b(accepted|under review|submitted to)\b", lower) and not has_negation(line, language):
            issues.append(Issue("FAKE_PUBLICATION", path, number, "unverified publication-status wording"))
        if any(term in line for term in ("게재 확정", "수락됨", "심사 중", "투고됨")) and not has_negation(line, language):
            issues.append(Issue("FAKE_PUBLICATION", path, number, "unverified publication-status wording"))
    return issues


def markdown_targets(text: str) -> list[tuple[str, int]]:
    targets: list[tuple[str, int]] = []
    patterns = [
        r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+['\"][^'\"]*['\"])?\)",
        r"(?:href|src|srcset)=\"([^\"]+)\"",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            targets.append((match.group(1), line_number(text, match.start())))
    return targets


def resolve_target(source: Path, target: str) -> Path | None:
    if target.startswith(("http://", "https://", "mailto:", "#", "data:")):
        return None
    clean = target.split("#", 1)[0].split("?", 1)[0]
    if not clean:
        return None
    return (source.parent / clean).resolve()


def collect_link_report(paths: Iterable[Path], root: Path = ROOT) -> list[dict[str, object]]:
    report: list[dict[str, object]] = []
    for source in paths:
        text = source.read_text(encoding="utf-8")
        for target, number in markdown_targets(text):
            resolved = resolve_target(source, target)
            if resolved is None:
                continue
            try:
                relative = resolved.relative_to(root)
                inside_root = True
            except ValueError:
                relative = resolved
                inside_root = False
            report.append({
                "source": str(source.relative_to(root)),
                "line": number,
                "target": target,
                "resolved": str(relative),
                "inside_root": inside_root,
                "exists": resolved.exists(),
            })
    return report


def read_go_versions(root: Path) -> tuple[str, str]:
    text = (root / "go.mod").read_text(encoding="utf-8")
    go_match = re.search(r"^go\s+(\S+)", text, flags=re.MULTILINE)
    lattigo_match = re.search(r"github\.com/tuneinsight/lattigo/v6\s+v(\S+)", text)
    if not go_match or not lattigo_match:
        raise ValueError("go.mod is missing Go or Lattigo version")
    return go_match.group(1), lattigo_match.group(1)


def git_tags(root: Path) -> set[str]:
    result = subprocess.run(["git", "tag", "--list"], cwd=root, text=True, check=True, capture_output=True)
    return set(result.stdout.splitlines())


def lint_repository(root: Path = ROOT) -> list[Issue]:
    issues: list[Issue] = []
    en_path = root / "README.md"
    ko_path = root / "README_ko.md"
    if not en_path.exists():
        return [Issue("MISSING_README", "README.md", 0, "English README is missing")]
    if not ko_path.exists():
        return [Issue("MISSING_README", "README_ko.md", 0, "Korean README is missing")]

    en = en_path.read_text(encoding="utf-8")
    ko = ko_path.read_text(encoding="utf-8")
    for path, text in ((en_path, en), (ko_path, ko)):
        if path.stat().st_size > 500 * 1024:
            issues.append(Issue("README_SIZE", path.name, 0, "README exceeds 500 KiB"))
        for pattern in (r"/home/[^/\s]+/", r"file://", r"[A-Za-z]:\\Users\\"):
            for match in re.finditer(pattern, text):
                issues.append(Issue("LOCAL_PATH", path.name, line_number(text, match.start()), match.group(0)))
        for stale in ("plain simulation only", "real ckks backend will be added", "lattigo backend will be added", "logreg_small as the sole", "35-commit"):
            if stale in text.casefold():
                issues.append(Issue("STALE_CONTENT", path.name, 0, stale))
        for exposed in ("submission_form.hwp", "publication_form.hwp", "results/journal/", "docs/journal/"):
            if exposed.casefold() in text.casefold():
                issues.append(Issue("ANONYMOUS_ARTIFACT_LINK", path.name, 0, exposed))

    if "English | <a href=\"README_ko.md\">한국어</a>" not in en:
        issues.append(Issue("LANGUAGE_LINK", "README.md", 0, "English-to-Korean language switch missing"))
    if "<a href=\"README.md\">English</a> | 한국어" not in ko:
        issues.append(Issue("LANGUAGE_LINK", "README_ko.md", 0, "Korean-to-English language switch missing"))
    if headings(en) != EN_SECTIONS:
        issues.append(Issue("SECTION_STRUCTURE", "README.md", 0, f"expected {EN_SECTIONS}, found {headings(en)}"))
    if headings(ko) != KO_SECTIONS:
        issues.append(Issue("SECTION_STRUCTURE", "README_ko.md", 0, f"expected {KO_SECTIONS}, found {headings(ko)}"))
    if len(headings(en)) != len(headings(ko)):
        issues.append(Issue("SECTION_PARITY", "README.md", 0, "English and Korean section counts differ"))
    if bash_blocks(en) != bash_blocks(ko):
        issues.append(Issue("COMMAND_PARITY", "README.md", 0, "English and Korean bash commands differ"))

    for token in HEADLINE_TOKENS:
        if token not in en:
            issues.append(Issue("NUMBER_MISSING", "README.md", 0, f"missing public token {token}"))
        if token not in ko:
            issues.append(Issue("NUMBER_MISSING", "README_ko.md", 0, f"missing public token {token}"))

    issues.extend(scan_claim_language(en, "en", "README.md", root))
    issues.extend(scan_claim_language(ko, "ko", "README_ko.md", root))

    for path in (en_path, ko_path):
        text = path.read_text(encoding="utf-8")
        for target, number in markdown_targets(text):
            resolved = resolve_target(path, target)
            if resolved is not None and not resolved.exists():
                issues.append(Issue("BROKEN_LINK", path.name, number, f"missing relative target {target}"))

    public_docs = [
        en_path,
        ko_path,
        root / "CONTRIBUTING.md",
        root / "SECURITY.md",
        root / "CHANGELOG.md",
        root / "docs/ARCHITECTURE.md",
        root / "docs/DECISION_CONTRACTS.md",
        root / "docs/RESULTS.md",
        root / "docs/REPRODUCIBILITY.md",
        root / "docs/CLAIM_SCOPE.md",
        root / "docs/REPOSITORY_GUIDE.md",
    ]
    for item in collect_link_report(public_docs, root):
        if not item["inside_root"] or not item["exists"]:
            issues.append(Issue("BROKEN_PUBLIC_LINK", str(item["source"]), int(item["line"]), str(item["target"])))

    for svg in sorted((root / "docs/assets").rglob("*.svg")):
        try:
            document = ET.parse(svg)
            svg_root = document.getroot()
            namespace = "{http://www.w3.org/2000/svg}"
            if svg_root.find(namespace + "title") is None or svg_root.find(namespace + "desc") is None:
                issues.append(Issue("SVG_ACCESSIBILITY", str(svg.relative_to(root)), 0, "title or desc missing"))
            content = svg.read_text(encoding="utf-8")
            if re.search(r"(?:href|src)=['\"](?:https?:|data:)", content, flags=re.IGNORECASE):
                issues.append(Issue("SVG_EXTERNAL_RESOURCE", str(svg.relative_to(root)), 0, "external or embedded resource found"))
        except ET.ParseError as exc:
            issues.append(Issue("SVG_XML", str(svg.relative_to(root)), 0, str(exc)))

    go_version, lattigo_version = read_go_versions(root)
    if f"Go-{go_version}" not in en or f"Go-{go_version}" not in ko:
        issues.append(Issue("BADGE_VERSION", "README.md", 0, "Go badge does not match go.mod"))
    if f"Lattigo-{lattigo_version}" not in en or f"Lattigo-{lattigo_version}" not in ko:
        issues.append(Issue("BADGE_VERSION", "README.md", 0, "Lattigo badge does not match go.mod"))
    if "actions/workflows/ci.yml" in en and not (root / ".github/workflows/ci.yml").exists():
        issues.append(Issue("BADGE_WORKFLOW", "README.md", 0, "CI badge references a missing workflow"))
    if "license" in re.sub(r"## License.*", "", en, flags=re.DOTALL).casefold() and "img.shields.io/badge/license" in en.casefold() and not (root / "LICENSE").exists():
        issues.append(Issue("FALSE_LICENSE_BADGE", "README.md", 0, "license badge exists without LICENSE"))
    if "flipguard-thesis-v1.0.0-rc2" not in git_tags(root):
        issues.append(Issue("BADGE_TAG", "README.md", 0, "RC2 tag badge references a missing local tag"))

    public_registry = json.loads((root / "docs/public-number-registry.json").read_text(encoding="utf-8"))
    journal_registry = json.loads((root / public_registry["source_registry"]).read_text(encoding="utf-8"))
    for key, value in public_registry["values"].items():
        if journal_registry.get(key) != value:
            issues.append(Issue("NUMBER_REGISTRY", "docs/public-number-registry.json", 0, f"{key}: {value!r} != {journal_registry.get(key)!r}"))

    for path in (en_path, ko_path):
        text = path.read_text(encoding="utf-8")
        if "1,100" in text:
            for match in re.finditer("1,100", text):
                start = max(0, text.rfind("\n", 0, match.start() - 160))
                end = text.find("\n", match.end() + 200)
                context = text[start : end if end != -1 else len(text)].casefold()
                if "historical" not in context and "pre-security" not in context:
                    issues.append(Issue("FORMAL_DENOMINATOR", path.name, line_number(text, match.start()), "1,100 lacks historical pre-security qualification"))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    args = parser.parse_args()
    issues = lint_repository(ROOT)
    if args.json:
        print(json.dumps({"status": "PASS" if not issues else "FAIL", "issues": [asdict(issue) for issue in issues]}, indent=2, ensure_ascii=False))
    elif issues:
        for issue in issues:
            location = f"{issue.path}:{issue.line}" if issue.line else issue.path
            print(f"{location}: {issue.code}: {issue.message}", file=sys.stderr)
    else:
        print("public README and asset lint: PASS")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
