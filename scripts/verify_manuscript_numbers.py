#!/usr/bin/env python3
"""Verify critical manuscript-facing values and source digests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs/evidence/final_manuscript_audit_v1/authoritative_number_registry.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = {row["number_id"]: row for row in payload["numbers"]}
    expected = {
        "formal_catalog_candidates_all": 700,
        "direct_trials_all": 70,
        "formal_trial_reduction": 0.9,
        "confirmatory_locked_audit_pass": 40,
        "primary_catalog_direct_total_ratio": 3.14065956642714,
        "common_latency_p3_ratio": 6.393517225744701,
        "direct_repeated_flips": 8,
        "direct_affected_unique_ambiguous_inputs": 1,
        "corelab_numerical_rows": 14000,
    }
    for number_id, value in expected.items():
        if number_id not in rows or rows[number_id]["exact_value"] != value:
            raise SystemExit(f"manuscript_numbers=FAILED number={number_id}")
    for row in rows.values():
        source = ROOT / row["source_evidence_file"]
        if not source.is_file() or sha256(source) != row["source_evidence_sha256"]:
            raise SystemExit(f"manuscript_numbers=FAILED source={row['source_evidence_file']}")
    if rows["direct_repeated_flips"]["statistical_unit"] == rows["direct_affected_unique_ambiguous_inputs"]["statistical_unit"]:
        raise SystemExit("manuscript_numbers=FAILED raw_unique_conflation")
    print(f"manuscript_numbers=VERIFIED count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
