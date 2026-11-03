#!/usr/bin/env python3
"""Fairness and claim linter for the comprehensive CKKS comparison."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


PROHIBITED_AFFIRMATIVE = (
    "all state-of-the-art ckks autotuners",
    "every ckks compiler",
    "universal superiority",
    "globally fastest",
    "all providers cause decision flips",
    "build smoke equals reproduction",
    "paper-reported speedup equals our measured speedup",
    "cross-runtime raw-latency ranking",
)


def text_findings(text: str) -> list[str]:
    lowered = text.lower()
    return [phrase for phrase in PROHIBITED_AFFIRMATIVE if phrase in lowered]


def audit(root: Path) -> dict:
    pack = root / "docs/evidence/comprehensive_ckks_comparison_v3"
    findings = []
    fairness = (pack / "fairness_limitations.md").read_text(encoding="utf-8")
    objective = (root / "docs/research/step_10a_final_research_message_and_comparison_objective.md").read_text(encoding="utf-8")
    combined = fairness + "\n" + objective
    for phrase in text_findings(combined):
        findings.append({"code": "PROHIBITED_AFFIRMATIVE", "detail": phrase})
    required_terms = [
        "구성 생성기", "결정 안정성 판정 계층", "실행 구성 직접 합성",
        "제한적 보정", "설정 고정 최종 검증", "선택 중단", "고정 후보군",
    ]
    for term in required_terms:
        if term not in objective:
            findings.append({"code": "KOREAN_TERMINOLOGY", "detail": term})
    native = list(csv.DictReader((pack / "native_execution_records.csv").open(newline="", encoding="utf-8")))
    for row in native:
        if row["provider_id"] not in {"FlipGuard"} and row["total_time_ms"] not in {"NOT_EVALUATED"}:
            if row["provider_id"] != "EVA":
                findings.append({"code": "UNSCOPED_NATIVE_LATENCY", "detail": row["provider_id"]})
    common = list(csv.DictReader((pack / "common_executor_records.csv").open(newline="", encoding="utf-8")))
    if any(row["headline_eligible"].lower() == "true" for row in common if row["provider"] != "FlipGuard internal providers"):
        findings.append({"code": "UNVERIFIED_EXTERNAL_HEADLINE", "detail": "external common-executor row"})
    reported = list(csv.DictReader((pack / "paper_reported_results.csv").open(newline="", encoding="utf-8")))
    if any(not row["source_locator"] for row in reported):
        findings.append({"code": "MISSING_SOURCE_LOCATOR", "detail": "paper-reported row"})
    if "not a head-to-head runtime ranking" not in json.loads((pack / "protocol/paper_reported_source_records.json").read_text())["normalization_rule"]:
        findings.append({"code": "REPORTED_RESULT_SCOPE", "detail": "normalization disclaimer"})
    return {"status": "PASS" if not findings else "FAIL", "findings": findings}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    result = audit(Path(args.root))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
