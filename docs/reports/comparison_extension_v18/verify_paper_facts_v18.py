#!/usr/bin/env python3
"""Verify the immutable binding and manuscript-facing V18 facts overlay."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / "docs/reports/comparison_extension_v18"
EVIDENCE = ROOT / "docs/evidence/comparison_extension_v18"

EXPECTED_MANIFEST_SHA256 = "a86427207d5525a83036f0a99e3bf6888f9e21b0219a489af3d1ac8fb1fa7e50"
EXPECTED_PACKAGE_PAYLOAD = "884d979087b62a1f4e2ca066902f4deb603589dbff6fd5349c57bead5539aded"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    manifest_path = EVIDENCE / "manifest.json"
    assert sha256(manifest_path) == EXPECTED_MANIFEST_SHA256
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["package_payload_sha256"] == EXPECTED_PACKAGE_PAYLOAD

    facts = json.loads((REPORT / "PAPER_FACTS_V18_LOCKED.json").read_text(encoding="utf-8"))
    assert facts["status"] == "V18 PAPER FACTS LOCKED — READY FOR MANUSCRIPT INTEGRATION"
    assert facts["source_binding"]["v18_package_payload_sha256"] == EXPECTED_PACKAGE_PAYLOAD
    assert facts["source_binding"]["v18_manifest_sha256"] == EXPECTED_MANIFEST_SHA256
    assert facts["source_binding"]["new_encrypted_candidate_evaluations"] == 0

    cross = facts["gate_off_cross_table"]
    expected_cross = {
        "no_flip_no_violation": 47,
        "flip_only": 0,
        "violation_only": 1,
        "flip_and_violation": 20,
        "union_flip_or_violation": 21,
    }
    for key, expected in expected_cross.items():
        assert cross[key]["count"] == expected
        assert len(cross[key]["case_ids"]) == expected
        assert len(cross[key]["case_ids"]) == len(set(cross[key]["case_ids"]))

    cost = facts["cost"]
    assert cost["gate_off_candidate_evaluations"] == 68
    assert cost["full_candidate_evaluations"] == 89
    assert cost["additional_candidate_evaluations"] == 21
    assert cost["cases_with_zero_additional_evaluations"] == 47
    assert cost["cases_recovered_with_exactly_one_additional_evaluation"] == 21
    assert cost["cases_requiring_two_or_more_additional_evaluations"] == 0
    assert cost["gate_off_full_selection_wall_clock_pair"] == "NOT_RECONSTRUCTABLE_FROM_V17_STAGE_BOUNDARIES"
    assert cost["changed_case_latency_measurement_class"] == "SELECTION_STAGE_OBSERVATIONAL_NOT_FORMAL"

    change = facts["configuration_change"]
    assert change["changed_case_count"] == 21
    assert change["scale_plus_4_case_count"] == 21
    assert change["q_prime_plus_1_case_count"] == 0
    assert change["scale_plus_4_and_q_prime_plus_1_case_count"] == 0
    assert change["log_n_changed_case_count"] == 0
    assert change["q_chain_length_changed_case_count"] == 0
    assert len(change["case_literals"]) == 21

    separate = facts["gate_off_separate_input"]
    assert separate["observed_case_count"] == 47
    assert (separate["pass"], separate["rejected"], separate["failed"]) == (47, 0, 0)
    assert separate["not_evaluated"] == 21
    assert separate["not_evaluated_counted_as_failure"] is False

    traditional = facts["traditional_objectives"]
    assert traditional["fastest_executable_union_unstable_cases"] == 18
    assert traditional["minimum_error_union_unstable_cases"] == 0
    assert traditional["pareto_candidate_count"] == 279
    assert traditional["unstable_pareto_candidate_count"] == 28
    assert traditional["unstable_pareto_case_count"] == 20
    assert traditional["fastest_executable_differs_from_proposed_cases"] == 23
    assert traditional["minimum_error_differs_from_proposed_cases"] == 68

    assert facts["external_class_counts"] == {
        "EXACT_COMPARABLE": 1,
        "NUMERICAL_ONLY": 2,
        "OUTPUT_COMPARABLE": 1,
        "RELATED_WORK_ONLY": 7,
    }
    heir = facts["external_comparators"]["heir"]
    assert (heir["audit_unique_inputs"], heir["audit_observations"], heir["audit_contexts"]) == (500, 1500, 3)
    assert (heir["audit_decision_flip_events"], heir["audit_reserve_violation_events"]) == (0, 0)
    assert abs(heir["common_executor_p95_total_ms"] - 59.866485) < 1e-12
    eva_s20 = next(
        row for row in facts["external_comparators"]["eva"]
        if row["scale_bits"] == 20 and row["role"] == "configuration_validation"
    )
    assert (eva_s20["unique_inputs"], eva_s20["observations"], eva_s20["contexts"]) == (500, 1500, 3)
    assert (eva_s20["decision_flip_events"], eva_s20["decision_flip_unique_inputs"]) == (133, 114)
    finite = facts["finite_reference"]
    assert finite["direct_evaluations"] == 89
    assert finite["finite_reference_evaluations"] == 537
    assert abs(finite["candidate_evaluation_reduction"] - 0.8342644320297952) < 1e-15
    assert finite["false_no_safe"] == 0
    assert finite["superiority_claim"] is False
    assert finite["claim_state"] == "NEAR_REFERENCE_SELECTION_QUALITY_NO_SUPERIORITY"

    gate_rows = read_csv(REPORT / "V18_GATE_EFFECT_TABLE.csv")
    stability_rows = read_csv(REPORT / "V18_STABILITY_COST_TABLE.csv")
    external_rows = read_csv(REPORT / "V18_EXTERNAL_COMPARISON_TABLE.csv")
    traditional_rows = read_csv(REPORT / "V18_TRADITIONAL_OBJECTIVE_DIAGNOSTICS.csv")
    assert len(gate_rows) == 68
    assert len(stability_rows) == 68
    assert len(external_rows) == 11
    assert len(traditional_rows) == 68
    assert sum(row["gate_off_separate_input_status"] == "SAFE" for row in gate_rows) == 47
    assert sum(row["gate_off_separate_input_status"] == "NOT_EVALUATED" for row in gate_rows) == 21
    assert all(row["gate_off_separate_input_status"] not in {"REJECTED", "FAILED"} for row in gate_rows)
    assert sum(int(row["additional_candidate_evaluations"]) == 1 for row in stability_rows) == 21
    assert sum(int(row["additional_candidate_evaluations"]) >= 2 for row in stability_rows) == 0

    print(
        "V18_PAPER_FACTS_VERIFY_PASS "
        "cases=68 changed=21 external=11 payload_sha256=" + EXPECTED_PACKAGE_PAYLOAD
    )


if __name__ == "__main__":
    main()
