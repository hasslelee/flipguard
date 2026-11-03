#!/usr/bin/env python3
"""Fail-closed validation for the result-independent V18 protocol."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = ROOT / "docs/evidence/comparison_extension_v18/protocol_v18.json"
EXPECTED_SHA256 = "4adf230d43d6120cd805f51e970d1dfcd452c229ae7d8a03ea85c1adc971db44"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert sha256(PROTOCOL) == EXPECTED_SHA256, "protocol digest mismatch"
    data = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert data["status"] == "PROTOCOL_FROZEN"
    assert data["populations"]["primary"]["case_count"] == 68
    assert data["populations"]["all_scope"]["case_count"] == 131
    assert set(data["comparators"]) == {
        "C1_PROPOSED_FULL",
        "C2_DECISION_GATE_OFF",
        "C3_INITIAL_ONLY",
        "C4_PREEXISTING_DEFAULT_OR_LATENCY_ONLY",
        "C5_TRADITIONAL_OBJECTIVE_DIAGNOSTICS",
        "C6_FINITE_REFERENCE",
        "C7_EXTERNAL_NATIVE_BASELINES",
    }
    c1 = data["comparators"]["C1_PROPOSED_FULL"]
    assert c1["candidate_evaluation_budget"] == 4
    assert "candidate evaluations" in c1["repair_count_interpretation"]
    bootstrap = data["analysis"]["bootstrap"]
    assert bootstrap == {
        "allowed": True,
        "unit": "workload/model cluster when a repeated-split structure exists",
        "replications": 10000,
        "seed": 20260824,
    }
    gate = data["targeted_execution_gate"]
    assert gate["maximum_atomic_cases"] == 12
    assert gate["maximum_candidate_evaluations"] == 36
    assert "policy retuning" in data["prohibited"]
    print(f"V18_PROTOCOL_VERIFY_PASS sha256={EXPECTED_SHA256}")


if __name__ == "__main__":
    main()
