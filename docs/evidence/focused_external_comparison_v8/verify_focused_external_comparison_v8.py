#!/usr/bin/env python3
"""Deterministically verify the focused external-comparison V8 pack."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
PACK = Path(__file__).resolve().parent
REQUIRED = (
    "manifest.json", "predecessor_v7.json", "environment_start.json", "environment_end.json",
    "eva_population_records.csv", "heir_shared_polynomial_records.csv", "corelab_multi_input_records.csv",
    "provider_gate_records.csv", "audit_records.csv", "common_executor_records.csv", "common_executor_paired_summary.csv",
    "operation_mismatch_records.csv", "latency_records.csv", "latency_summary.csv",
    "numerical_error_summary.csv", "unique_input_accounting.csv", "execution_accounting.csv",
    "security_summary.csv", "portability_summary.csv", "corelab_plan_status.csv",
    "recovery_provenance.csv", "failure_summary.csv",
    "fairness_limitations.md", "claim_admission.json", "publication_inputs_manifest.json",
    "CHECKPOINT_REPORT.md", "SHA256SUMS",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(name: str) -> list[dict[str, str]]:
    with (PACK / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    missing = [name for name in REQUIRED if not (PACK / name).is_file()]
    if missing:
        raise RuntimeError(f"missing V8 evidence: {missing}")
    checksums = {}
    for line in (PACK / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        digest, name = line.split("  ", 1); checksums[name] = digest
    for name, expected in checksums.items():
        if sha256(PACK / name) != expected:
            raise RuntimeError(f"checksum mismatch: {name}")
    predecessor = json.loads((PACK / "predecessor_v7.json").read_text())
    if predecessor["evidence_manifest_sha256"] != "sha256:09d6e25b64bfbfc7c8e6d3945049b4492709e28695e95813508e97181f7c12cd":
        raise RuntimeError("V7 predecessor binding drift")
    subprocess.run(["python3", str(ROOT / "docs/evidence/external_end_to_end_code_v7/verify_external_end_to_end_code_v7.py")], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    manifest = json.loads((PACK / "manifest.json").read_text())
    accounting = rows("unique_input_accounting.csv")
    for row in accounting:
        if row["raw_rows"] == "NOT_EVALUATED":
            if row["unique_inputs"] != "NOT_EVALUATED":
                raise RuntimeError("missing provider has a false numeric input population")
            continue
        if int(row["raw_rows"]) > 0 and int(row["unique_inputs"]) <= 0:
            raise RuntimeError("raw row count masquerades as missing unique input population")
    if manifest["cross_runtime_ratio_claim_allowed"]:
        raise RuntimeError("cross-runtime ratio must remain blocked")
    claims = json.loads((PACK / "claim_admission.json").read_text())
    if claims["claims"]["paired_common_executor_latency"] == "SUPPORTED":
        common = rows("common_executor_records.csv")
        if len(common) != 5400 or {row["latency_state"] for row in common} != {"PAIRED_HEADLINE"}:
            raise RuntimeError("paired latency admitted without the frozen 5,400 common-harness records")
    common = rows("common_executor_records.csv")
    if len(common) != 5400:
        raise RuntimeError(f"unexpected common-executor record count: {len(common)}")
    flips = [row for row in common if row["decision_flip"].lower() == "true"]
    violations = [row for row in common if row["reserve_violation"].lower() == "true"]
    if len(flips) != 8 or {row["arm"] for row in flips} != {"flipguard_direct"} or {row["row_id"] for row in flips} != {"711"}:
        raise RuntimeError("common-executor decision-flip negative result drift")
    if violations:
        raise RuntimeError("unexpected common-executor reserve violation drift")
    if {row["latency_state"] for row in common} != {"PAIRED_DIAGNOSTIC_UNSAFE_ARM"}:
        raise RuntimeError("unsafe common-executor rows were not forced to diagnostic status")
    if claims["claims"]["paired_common_executor_latency"] != "BLOCKED":
        raise RuntimeError("common-executor flips did not block the paired latency claim")

    corelab = rows("corelab_plan_status.csv")
    if len(corelab) != 72:
        raise RuntimeError(f"unexpected CoreLab plan count: {len(corelab)}")
    passed = [row for row in corelab if row["status"] == "PASS"]
    failed = [row for row in corelab if row["status"] == "EXECUTION_FAILED"]
    if len(passed) != 70 or {row["plan_id"] for row in failed} != {"elasm_36", "elasm_41"}:
        raise RuntimeError("CoreLab 70 PASS / 2 native-failure matrix drift")
    if any(int(row["raw_output_rows"]) != 200 for row in passed):
        raise RuntimeError("completed CoreLab plan does not contain 200 input rows")
    if any(int(row["raw_output_rows"]) != 0 or row["reason_code"] != "NATIVE_PLAN_EXECUTION_ABORT" for row in failed):
        raise RuntimeError("failed CoreLab plan contains output or lacks a failure reason")
    if len(rows("corelab_multi_input_records.csv")) != 14000:
        raise RuntimeError("CoreLab raw numerical population is not 14,000 rows")
    if claims["claims"]["corelab_multi_input_numerical_grid"] != "PARTIALLY_SUPPORTED":
        raise RuntimeError("CoreLab partial scientific result was not preserved")

    execution = {(row["provider"], row["phase"]): row for row in rows("execution_accounting.csv")}
    expected_execution = {
        ("FlipGuard direct", "direct_synthesis_trials"): ("2", "6", "3000"),
        ("FlipGuard direct", "provider_literal_validation"): ("1", "3", "1500"),
        ("FlipGuard direct", "locked_audit"): ("1", "3", "1500"),
        ("Security-V2 bounded catalog", "catalog_validation"): ("2", "6", "3000"),
        ("Security-V2 bounded catalog", "fastest_safe_locked_audit"): ("1", "3", "1500"),
    }
    for key, expected in expected_execution.items():
        row = execution.get(key)
        actual = (row["encrypted_candidate_executions"], row["key_runs"], row["total_encrypted_sample_evaluations"]) if row else None
        if actual != expected:
            raise RuntimeError(f"execution accounting drift for {key}: {actual} != {expected}")
    common_execution = execution.get(("Common Lattigo harness", "paired_latency"))
    if not common_execution or (
        common_execution["recorded_encrypted_sample_evaluations"],
        common_execution["warmup_encrypted_sample_evaluations"],
        common_execution["total_encrypted_sample_evaluations"],
        common_execution["raw_output_rows"],
    ) != ("5400", "900", "6300", "5400"):
        raise RuntimeError("common-harness warm-up/measurement accounting drift")

    recovery = rows("recovery_provenance.csv")
    if len(recovery) != 8 or any(row["candidate_changed"].lower() != "false" or row["policy_changed"].lower() != "false" for row in recovery):
        raise RuntimeError("recovery provenance is incomplete or changes frozen semantics")
    failures = rows("failure_summary.csv")
    common_failure = next((row for row in failures if row["reason_code"] == "COMMON_EXECUTOR_DECISION_FLIP"), None)
    if not common_failure or (common_failure["count"], common_failure["unique_failure_inputs"], common_failure["affected_arm"]) != ("8", "1", "flipguard_direct"):
        raise RuntimeError("common-executor negative result missing from failure summary")

    if manifest["execution_initial_commit"] != "f4db86960f2a9a1e3fc02643836257b40f0f08f3" or manifest["execution_critical_source_digest"] != "sha256:c4e29067a997ab04c53acbe8100a25d0124a7f0a23d7fda070826ced264d9d1b":
        raise RuntimeError("execution-critical provenance drift")
    if (manifest["common_executor_decision_flips"], manifest["common_executor_unique_flip_inputs"], manifest["corelab_plans_completed"], manifest["corelab_plans_failed"]) != (8, 1, 70, 2):
        raise RuntimeError("manifest negative-result accounting drift")

    publication = json.loads((PACK / "publication_inputs_manifest.json").read_text())
    if publication["status"] != "FINAL_VERIFIED_INPUTS" or publication["table_count"] != 8 or publication["figure_count"] != 6:
        raise RuntimeError("publication input count/status drift")
    publication_root = (ROOT / "results/thesis_grade_protocol/focused_external_comparison_v8").resolve()
    for kind, expected_suffix in (("tables", ".csv"), ("figures", ".svg")):
        for entry in publication[kind]:
            path = (ROOT / entry["path"]).resolve()
            if publication_root not in path.parents or path.suffix != expected_suffix or not path.is_file():
                raise RuntimeError(f"invalid publication input path: {entry['path']}")
            if "sha256:" + sha256(path) != entry["sha256"]:
                raise RuntimeError(f"publication input checksum mismatch: {entry['path']}")
            if kind == "figures":
                ET.parse(path)
    if publication["cross_runtime_ratio_claim_allowed"] or publication["common_executor_latency_claim_allowed"]:
        raise RuntimeError("publication inputs incorrectly admit a blocked latency claim")
    text = "\n".join((PACK / name).read_text(encoding="utf-8", errors="ignore") for name in ("CHECKPOINT_REPORT.md", "fairness_limitations.md"))
    for phrase in ("global optimum", "all state-of-the-art", "universally safe"):
        if phrase in text.lower():
            raise RuntimeError(f"prohibited overclaim in V8 pack: {phrase}")
    print(json.dumps({"status": "PASS", "classification": manifest["classification"], "required_files": len(REQUIRED), "checksums": len(checksums)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
