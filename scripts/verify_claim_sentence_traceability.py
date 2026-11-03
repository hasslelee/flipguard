#!/usr/bin/env python3
"""Fail closed on claim-traceability omissions and prohibited admissions."""

from __future__ import annotations

import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "docs/review/final_manuscript_audit_v1/claim_sentence_traceability.csv"


def main() -> int:
    with TRACE.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or {row["document"] for row in rows} != {"journal_v10", "thesis_v10"}:
        raise SystemExit("claim_traceability=FAILED document_coverage")
    positives = [row for row in rows if row["positive_technical_claim"] == "YES"]
    required_fields = ("claim_id", "state", "permitted_scope", "required_citation")
    for row in positives:
        if any(not row[field] for field in required_fields):
            raise SystemExit(f"claim_traceability=FAILED empty_field:{row['document']}:{row['paragraph_sentence']}")

    joined = "\n".join(row["sentence_text"] for row in rows)
    prohibited = (
        r"50 independent workloads", r"global optimum", r"universally safe",
        r"theoretically optimal 0\.5", r"all structural audits passed",
        r"production speedup", r"arbitrary CNN support",
    )
    for pattern in prohibited:
        if re.search(pattern, joined, re.IGNORECASE):
            raise SystemExit(f"claim_traceability=FAILED prohibited_phrase:{pattern}")

    p1p2_positive = [
        row for row in positives
        if any(claim in row["claim_id"] for claim in ("p1_heir_over_direct_latency", "p2_catalog_over_direct_latency"))
        and not any(token in row["sentence_text"].lower() for token in ("차단", "제외", "blocked", "불안정", "사용하지"))
    ]
    if p1p2_positive:
        raise SystemExit("claim_traceability=FAILED p1p2_admission")
    print(f"claim_traceability=VERIFIED rows={len(rows)} positive={len(positives)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
