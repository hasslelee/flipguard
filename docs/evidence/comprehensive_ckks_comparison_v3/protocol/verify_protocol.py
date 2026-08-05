#!/usr/bin/env python3
"""Fail-closed verifier for the V3 comprehensive comparison protocol."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PACK = Path(__file__).resolve().parent


def load(name: str):
    return json.loads((PACK / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest = load("protocol_manifest.json")
    tiers = load(manifest["evidence_tiers"])
    objective = load(manifest["comparison_objective"])
    states = load(manifest["state_vocabulary"])
    rules = load(manifest["falsification_rules"])
    attempts = load(manifest["artifact_attempt_policy"])
    workloads = load(manifest["frozen_workload_inventory"])

    assert manifest["external_system_count"] == 20
    assert manifest["landscape_row_count_including_flipguard"] == 21
    assert manifest["maximum_build_recovery_attempts"] == 3
    assert manifest["result_independent_freeze"] is True
    assert manifest["frozen_policies"]["retuning_allowed"] is False
    assert manifest["native_absolute_cross_runtime_ranking_allowed"] is False
    assert manifest["missing_value_as_zero_allowed"] is False
    assert manifest["build_smoke_as_benchmark_reproduction_allowed"] is False
    assert manifest["bootstrap_workload_manufacture_allowed"] is False
    assert manifest["new_core_model_without_amendment_allowed"] is False
    assert re.fullmatch(r"[0-9a-f]{40}", manifest["source_commit"])

    predecessor = ROOT / manifest["predecessor"]["manifest_path"]
    assert sha256(predecessor) == manifest["predecessor"]["manifest_sha256"]
    predecessor_json = json.loads(predecessor.read_text(encoding="utf-8"))
    assert predecessor_json["external_portable_exact_arms"] == 0
    assert predecessor_json["reproduced_systems"] == 8

    assert len(tiers["tiers"]) == 4
    assert sum(tier["latency_headline_allowed"] for tier in tiers["tiers"]) == 1
    assert tiers["tiers"][-1]["id"] == "TIER_4_COMMON_EXECUTOR_COMPARISON"
    assert objective["global_optimality_claimed"] is False
    assert objective["empty_set_result"] == "NO_SAFE"
    assert set(objective["flipguard_roles"]) == {
        "PROVIDER_INDEPENDENT_DECISION_STABILITY_GATE",
        "BUILT_IN_DIRECT_SYNTHESIS_PROVIDER",
    }

    for axis in (
        "publication_state", "artifact_state", "build_state", "execution_state",
        "workload_mapping_state", "output_evidence_state", "decision_gate_state",
        "portability_state", "latency_comparability", "security_state", "missing_values",
    ):
        assert states[axis], axis
    assert "BUILD_SMOKE_PASS" in states["build_state"]
    assert "NATIVE_END_TO_END_PASS" in states["execution_state"]
    assert "PORTABLE_EXACT" in states["portability_state"]
    assert "MISSING_VALUE_CONVERTED_TO_ZERO" in rules["hard_fail_conditions"]
    assert rules["pipeline_continues_after_scientific_negative_result"] is True
    assert len(attempts["required_attempt"]) == 11
    assert len(attempts["conditional_attempt"]) == 7
    assert attempts["maximum_recovery_attempts"] == 3
    assert attempts["valid_completion"] == "EXHAUSTED_FEASIBLE_SET"
    assert len(workloads["workloads"]) == 7
    for workload in workloads["workloads"]:
        path = ROOT / workload["binding_path"]
        assert path.is_file(), workload["binding_path"]
        assert sha256(path) == workload["binding_sha256"], workload["workload_family"]

    for schema_name in (manifest["provider_execution_schema"], manifest["provider_candidate_schema"]):
        schema = json.loads((PACK / schema_name).read_text(encoding="utf-8"))
        assert schema["additionalProperties"] is False
        assert schema["required"]

    print("comprehensive_ckks_comparison_v3_protocol=PASS tiers=4 systems=21")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
