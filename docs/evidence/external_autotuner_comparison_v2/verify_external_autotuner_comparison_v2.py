#!/usr/bin/env python3
"""Deterministically verify the maximal-fair external-baseline evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path


PACK = Path(__file__).resolve().parent
ROOT = PACK.parents[2]
REQUIRED = {"EVA", "HECATE", "ELASM", "HEIR", "Orion", "LOHEN", "DaCapo", "ANT-ACE"}
PROHIBITED = {
    "all state-of-the-art CKKS autotuners",
    "comprehensive comparison of every CKKS compiler",
    "global fastest configuration",
    "universal superiority",
    "cross-runtime raw latency superiority",
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest = load(PACK / "manifest.json")
    claims = load(PACK / "claim_admission.json")
    landscape = rows(PACK / "landscape.csv")
    builds = rows(PACK / "build_matrix.csv")
    applicability = rows(PACK / "applicability_matrix.csv")
    common = rows(PACK / "common_executor_results.csv")
    gate = rows(PACK / "provider_gate_results.csv")
    native = rows(PACK / "native_results.csv")

    assert manifest["publication_status"] == "FINAL_FAIR_BASELINE_EVIDENCE"
    assert manifest["current_flipguard_evidence_modified"] is False
    assert manifest["policy_retuning"] == 0
    assert manifest["new_model_or_dataset"] == 0
    assert manifest["native_latency_cross_runtime_ranked"] is False
    assert manifest["bootstrap_workload_manufactured"] is False
    assert re.fullmatch(r"[0-9a-f]{40}", manifest["comparison_input_commit"])
    assert len(landscape) == 20
    assert len(builds) == 20
    assert {row["system"] for row in landscape} == {row["system"] for row in builds}
    assert REQUIRED <= {row["system"] for row in builds}
    for row in builds:
        assert 0 <= int(row["attempts"]) <= 3
        assert row["algorithm_semantics_changed"].lower() == "false"
        if row["reproduced"].lower() == "true":
            assert row["status"] == "PASS"
        if int(row["attempts"]) > 0:
            assert row["log_sha256"] != "NR"
            for value in row["log_sha256"].split(";"):
                assert re.fullmatch(r"sha256:[0-9a-f]{64}", value)
    for row in builds:
        if row["system"] in REQUIRED and row["status"] != "PASS":
            assert row["reason_code"]
            assert row["last_error"]

    expected_applicability = {
        "EXACT_NATIVE", "EXACT_PORTABLE", "SEMANTICALLY_MAPPABLE",
        "DIFFERENT_MODEL", "NO_BOOTSTRAP_NOT_APPLICABLE", "PLAN_UNSUPPORTED",
        "ARTIFACT_UNAVAILABLE", "BUILD_BLOCKED",
    }
    assert len(applicability) == 16
    workload_fields = ["Sobel", "Harris", "MLP-100", "LeNet-5-small", "deeper_bootstrapping_workload"]
    for row in applicability:
        assert all(row[field] in expected_applicability for field in workload_fields)

    portable_exact = [row for row in common if row["portability"] == "PORTABLE_EXACT"]
    headline = [row for row in common if row["headline_eligible"].lower() == "true"]
    assert len(portable_exact) == manifest["external_portable_exact_arms"]
    assert all(row["portability"] == "PORTABLE_EXACT" for row in headline)
    assert claims["counts"]["external_portable_exact_arms"] == len(portable_exact)
    assert claims["counts"]["reproduced_systems"] == 8
    assert claims["counts"]["attempted_systems"] == 11
    assert claims["counts"]["reproduction_blocked_systems"] == 7
    assert claims["counts"]["required_reproduction_passed"] == 5
    assert claims["counts"]["required_reproduction_blocked"] == 3
    assert claims["counts"]["native_end_to_end_systems"] == 1
    assert claims["counts"]["external_exact_workload_mappings"] == 0
    assert claims["counts"]["provider_gate_systems"] == 2
    assert {row["baseline"] for row in claims["main_paper_baseline_set"]} == {
        "Default", "Latency-only", "Security-V2 bounded catalog", "FlipGuard direct", "EVA"
    }
    assert any(row["provider"] == "EVA" and row["final_flipguard_state"] == "REJECTED" for row in gate)
    assert any(row["provider"] == "Orion" and row["final_flipguard_state"] == "PLAN_UNSUPPORTED" for row in gate)
    assert len(native) == 20
    assert len(common) == 15
    assert sum(row["portability"] == "PORTABLE_EXACT" for row in common) == 0
    eva_native = next(row for row in native if row["provider"] == "EVA")
    assert eva_native["latency_scope"] == "NATIVE_ONLY_NOT_CROSS_RUNTIME_RANKED"
    assert int(eva_native["decision_flips"]) == 11
    assert float(eva_native["rms_error"]) > 0
    assert all(row["headline_eligible"].lower() == "false" for row in common)

    source_text = "\n".join(
        [
            json.dumps(claims["claims"], ensure_ascii=False),
            (ROOT / "docs/research/step_9a_ckks_tool_landscape_2026.md").read_text(encoding="utf-8", errors="replace"),
        ]
    )
    for phrase in PROHIBITED:
        assert phrase.lower() not in source_text.lower(), phrase
    assert set(claims["prohibited"]) == PROHIBITED
    assert "PORTABLE_EXACT" in source_text
    assert "NOT_APPLICABLE_NO_BOOTSTRAP" in source_text

    expected_files = {
        "manifest.json", "landscape.csv", "official_sources.json",
        "artifact_availability.csv", "build_matrix.csv", "applicability_matrix.csv",
        "patch_inventory.csv", "native_results.csv", "common_executor_results.csv",
        "provider_gate_results.csv", "decision_flip_summary.csv",
        "tuning_cost_summary.csv", "latency_summary.csv", "security_summary.csv",
        "failure_summary.csv", "claim_admission.json",
    }
    assert expected_files <= {path.name for path in PACK.iterdir() if path.is_file()}
    assert len(list((PACK / "workload_contracts").glob("*.json"))) == 4
    assert len(list((PACK / "figures").glob("*.svg"))) == 6
    assert len(list((PACK / "tables").glob("*.csv"))) == 7

    checksum_lines = (PACK / "SHA256SUMS").read_text(encoding="ascii").splitlines()
    assert checksum_lines
    for line in checksum_lines:
        expected, relative = line.split("  ", 1)
        path = PACK / relative
        assert path.is_file(), relative
        assert digest(path) == expected, relative

    print(
        "external_autotuner_comparison_v2=VERIFIED "
        f"systems={len(landscape)} reproduced={manifest['reproduced_systems']} "
        f"portable_exact={len(portable_exact)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
