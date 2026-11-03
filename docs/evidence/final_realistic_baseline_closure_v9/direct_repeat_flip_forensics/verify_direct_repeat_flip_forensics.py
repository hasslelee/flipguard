#!/usr/bin/env python3
"""Verify V9 direct repeated-flip forensic evidence against immutable V8 records."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PACK = Path(__file__).resolve().parent
V8 = ROOT / "docs/evidence/focused_external_comparison_v8"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    value.update(path.read_bytes())
    return "sha256:" + value.hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    manifest = json.loads((PACK / "manifest.json").read_text(encoding="utf-8"))
    source = V8 / "common_executor_records.csv"
    assert manifest["source_records_sha256"] == digest(source)
    raw = rows(source)
    direct = [row for row in raw if row["arm"] == "flipguard_direct" and row["row_id"] == "711"]
    affected = rows(PACK / "affected_observations.csv")
    matrix = rows(PACK / "input_keyset_pass_matrix.csv")
    assert len(direct) == len(matrix) == 18
    assert len(affected) == 8
    assert {(row["keyset_context_id"], row["pass_index"]) for row in affected} == {
        (row["keyset"], row["pass"]) for row in direct if row["decision_flip"] == "True"
    }
    classification = json.loads((PACK / "final_classification.json").read_text(encoding="utf-8"))
    assert classification["classification"] == "F4_NEAR_BOUNDARY_AMBIGUITY"
    assert classification["plaintext_margin"] < classification["declared_ambiguity_margin_floor"]
    assert classification["targeted_encrypted_replay_performed"] is False
    identity = json.loads((PACK / "candidate_identity.json").read_text(encoding="utf-8"))
    assert identity["identity_match"] is True
    with (PACK / "SHA256SUMS").open(encoding="ascii") as handle:
        for line in handle:
            expected, relative = line.rstrip("\n").split("  ", 1)
            assert digest(PACK / relative) == "sha256:" + expected
    print("PASS: direct repeat flip forensics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
