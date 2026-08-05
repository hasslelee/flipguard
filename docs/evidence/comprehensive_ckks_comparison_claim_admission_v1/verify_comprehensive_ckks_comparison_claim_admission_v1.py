#!/usr/bin/env python3
"""Verify the comprehensive CKKS comparison without executing CKKS."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path


def find_root() -> Path:
    for candidate in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
        if (candidate / "go.mod").is_file() and (candidate / "scripts").is_dir():
            return candidate
    raise RuntimeError("repository root not found")


ROOT = find_root()
PACK = ROOT / "docs/evidence/comprehensive_ckks_comparison_v3"
CLAIMS = ROOT / "docs/evidence/comprehensive_ckks_comparison_claim_admission_v1"
RESULTS = ROOT / "results/thesis_grade_protocol/comprehensive_ckks_comparison_v3"
PAPER = ROOT / "results/thesis_grade_protocol/comprehensive_ckks_comparison_paper_inputs_v1"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_checksums(root: Path, ignored_prefixes: tuple[str, ...] = ()) -> None:
    lines = (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert lines, f"empty checksum file: {root}"
    for line in lines:
        digest, rel = line.split("  ", 1)
        if rel.startswith(ignored_prefixes):
            continue
        path = root / rel
        assert path.is_file(), f"missing checksummed file: {path}"
        assert sha256(path) == digest, f"checksum mismatch: {path}"


def verify() -> dict:
    manifest = read_json(PACK / "manifest.json")
    systems = read_csv(PACK / "landscape/systems.csv")
    artifacts = read_csv(PACK / "landscape/artifact_matrix.csv")
    builds = read_csv(PACK / "build_matrix.csv")
    native = read_csv(PACK / "native_execution_records.csv")
    gates = read_csv(PACK / "provider_gate_records.csv")
    common = read_csv(PACK / "common_executor_records.csv")
    reported = read_csv(PACK / "paper_reported_results.csv")
    applicability = read_csv(PACK / "applicability_matrix.csv")
    trials = read_json(PACK / "internal_trial_distribution.json")
    claims = read_json(PACK / "claim_admission.json")["claims"]
    source_checksum_audit = read_json(PACK / "official_sources/local_checksum_audit.json")
    execution_schema = read_json(PACK / "protocol/schemas/provider_execution_record.schema.json")
    candidate_schema = read_json(PACK / "protocol/schemas/provider_candidate_manifest.schema.json")

    assert manifest["schema_version"] == "flipguard_comprehensive_ckks_comparison_v3"
    assert manifest["completion"]["status"] == "EXHAUSTED_FEASIBLE_SET"
    assert manifest["completion"]["frozen_flipguard_evidence_modified"] is False
    assert manifest["completion"]["policy_retuning"] is False
    assert manifest["completion"]["graph_or_algorithm_changed_to_fill_targets"] is False
    assert len(systems) == 21 and len({row["system"] for row in systems}) == 21
    assert len(applicability) == 21
    assert {row["system"] for row in systems} == {row["system"] for row in builds}
    assert {row["system"] for row in systems} == {row["system"] for row in artifacts}
    assert set(native[0]) == set(execution_schema["required"])
    assert all(row["schema_version"] == execution_schema["properties"]["schema_version"]["const"] for row in native)
    assert all(row["split_role"] in execution_schema["properties"]["split_role"]["enum"] for row in native)
    candidate_paths = sorted((PACK / "provider_candidate_manifests").glob("*.json"))
    assert len(candidate_paths) == 4
    for path in candidate_paths:
        candidate = read_json(path)
        assert set(candidate) == set(candidate_schema["required"]), f"candidate schema fields: {path}"
        assert candidate["schema_version"] == candidate_schema["properties"]["schema_version"]["const"]
    assert len(list((PACK / "workload_contracts").glob("*.json"))) == 4
    assert (PACK / "workload_contracts/official_workload_contract_index.csv").is_file()

    allowed_publication = {"PEER_REVIEWED", "WORKSHOP_PEER_REVIEWED", "PREPRINT", "TECHNICAL_REPORT"}
    assert all(row["publication_state"] in allowed_publication for row in systems)
    official = [row for row in artifacts if row["artifact_state"] != "PAPER_ONLY" and row["system"] != "FlipGuard"]
    assert len(official) == manifest["counts"]["external_official_artifact_rows"]
    assert all(int(row["attempts"]) >= 1 for row in official), "available artifact was not attempted"
    assert sum(row["status"] == "PASS" and row["system"] != "FlipGuard" for row in builds) == 10
    assert all(row["smoke_gate_pass"] == str(row["status"] == "PASS") for row in builds)

    orbit = next(row for row in builds if row["system"] == "Orbit")
    resbm = next(row for row in builds if row["system"] == "ReSBM")
    assert orbit["status"] == "PASS" and "SCHEDULE" in orbit["reason_code"]
    assert resbm["status"] == "PASS" and "CREDENTIAL_GATED_INPUT" in resbm["reason_code"]
    assert "native output" not in resbm["notes"].lower() or "OUTPUT_UNAVAILABLE" in resbm["notes"]
    log_expectations = {
        "orbit_build_and_quick.log": "fd36de1e1f7b409c00b4bd2c30df68778cd841412fbb4297ea4c4f9affa04c94",
        "resbm_attempt1_build_and_mode_smoke.log": "3208727f34f702d85b5d98cd13aa668372798a5756088b950b366a2426b44d28",
        "resbm_attempt2_ossutil_config_block.log": "5cb9b8b83778a4daed33c8cfdc3045d2b1e0a3e7722dd932deb85041e1275b27",
        "resbm_attempt3_http_403.log": "342a5a22119fec9e7cc616d8572db0260d3a8fab09d7ad69997b2eeb303fda3a",
    }
    for name, digest in log_expectations.items():
        assert sha256(PACK / "artifact_audit/build_logs" / name) == digest
    redactions = read_json(PACK / "artifact_audit/log_redaction_manifest.json")
    assert redactions["schema_version"] == "flipguard_build_log_redaction_v1"
    assert len(redactions["redactions"]) == 1
    redaction = redactions["redactions"][0]
    assert redaction["source_raw_sha256"] == "sha256:530a24139e75a91195e125a1aeceaeadf737298ecd15b3e1b6f34ff368c7ade6"
    assert redaction["public_copy_sha256"] == "sha256:" + log_expectations["resbm_attempt1_build_and_mode_smoke.log"]
    assert redaction["execution_output_changed"] is False

    external_native = [row for row in native if row["provider_id"] != "FlipGuard" and row["execution_status"] == "NATIVE_END_TO_END_PASS"]
    assert [row["provider_id"] for row in external_native] == ["EVA"]
    raw_external = [row for row in external_native if row["plaintext_output"] not in {"NOT_EVALUATED", "OUTPUT_UNAVAILABLE"}]
    assert len(raw_external) == 1
    assert len(gates) == 2 and {row["provider"] for row in gates} == {"EVA", "Orion"}
    assert next(row for row in gates if row["provider"] == "EVA")["final_flipguard_state"] == "REJECTED"
    assert next(row for row in gates if row["provider"] == "Orion")["final_flipguard_state"] == "PLAN_UNSUPPORTED"

    external_common = [row for row in common if row["provider"] != "FlipGuard internal providers"]
    assert not any(row["headline_eligible"].lower() == "true" for row in external_common)
    assert all(row["level"] == "NOT_EVALUATED" for row in external_common)
    assert manifest["counts"]["external_portable_exact"] == 0
    assert manifest["counts"]["external_graph_equivalent_common_executor"] == 0

    external_reported = [row for row in reported if row["system"] != "FlipGuard"]
    assert len({row["system"] for row in external_reported}) >= 12
    assert all(row["source_locator"] and row["official_paper"] for row in reported)
    assert all(row["pdf_sha256"] == "NOT_APPLICABLE" or re.fullmatch(r"[0-9a-f]{64}", row["pdf_sha256"]) for row in reported)
    assert all(float(row["normalized_baseline_over_system"]) > 0 for row in reported)
    assert source_checksum_audit["status"] == "PASS"
    assert source_checksum_audit["verified_records"] == len(external_reported) == 13
    assert set(source_checksum_audit["systems"]) == {row["system"] for row in external_reported}
    assert source_checksum_audit["raw_pdfs_committed"] is False

    assert trials["instances"] == 50 and trials["candidate_trials"] == 70
    assert trials["one_trial_instances"] == 30 and trials["two_trial_instances"] == 20
    assert trials["three_trial_instances"] == 0 and trials["four_trial_instances"] == 0
    assert trials["repair_causes"] == {"NUMERICAL_REJECT": 20}
    assert trials["selection_key_runs"] == 210
    assert trials["encrypted_sample_evaluations"] == 36825
    assert trials["actual_tuning_wall_clock"] == "NOT_SEPARATELY_RECORDED"

    assert len(list((PACK / "figures").glob("*.svg"))) == 10
    assert len(list((PACK / "tables").glob("*.csv"))) == 9
    for svg in (PACK / "figures").glob("*.svg"):
        text = svg.read_text(encoding="utf-8")
        assert text.startswith("<svg") and "<title" in text and "<desc" in text
    assert read_json(PAPER / "manifest.json")["figures"] == 10
    assert read_json(PAPER / "manifest.json")["tables"] == 9
    for name in [
        "native_execution_records.csv", "provider_gate_records.csv", "common_executor_records.csv",
        "paper_reported_results.csv", "tuning_cost_records.csv", "latency_summary.csv",
        "decision_flip_summary.csv", "security_summary.csv", "portability_summary.csv",
        "failure_summary.csv", "fastest_stable_candidates.csv", "internal_trial_distribution.json",
    ]:
        assert (RESULTS / name).read_bytes() == (PACK / name).read_bytes(), f"raw result mirror mismatch: {name}"

    blocked = {row["claim_id"] for row in claims if not row["paper_admitted"]}
    assert blocked == {"external_common_executor_latency", "external_fastest_stable_selection"}
    assert next(row for row in claims if row["claim_id"] == "native_provider_output")["state"] == "PARTIALLY_SUPPORTED"
    all_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in [PACK / "fairness_limitations.md", PACK / "claim_admission.json"])
    prohibited_actual = [
        "all state-of-the-art autotuners were reproduced",
        "globally fastest CKKS configuration",
        "build smoke equals reproduction",
        "cross-runtime absolute speedup",
    ]
    assert not any(phrase.lower() in all_text.lower() for phrase in prohibited_actual)

    verify_checksums(PACK)
    verify_checksums(PACK / "landscape")
    verify_checksums(PACK / "official_sources")
    verify_checksums(PACK / "artifact_audit")
    verify_checksums(RESULTS)
    verify_checksums(PAPER)
    verify_checksums(CLAIMS)
    return {
        "status": "PASS", "systems": 21, "external_smoke_pass": 10,
        "external_native": 1, "external_gates": 2, "external_common_executor": 0,
        "reported_systems": len({row["system"] for row in external_reported}),
        "completion": "EXHAUSTED_FEASIBLE_SET",
    }


def main() -> int:
    try:
        result = verify()
    except (AssertionError, OSError, ValueError, KeyError) as error:
        print(f"comprehensive_ckks_comparison_v3=FAIL reason={error}", file=sys.stderr)
        return 1
    print("comprehensive_ckks_comparison_v3=PASS " + " ".join(f"{key}={value}" for key, value in result.items() if key != "status"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
