#!/usr/bin/env python3
"""Verify normalized V7 evidence without promoting missing or unlike results."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path


DEFAULT_ROOT = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[3]
REQUIRED = {
    "artifact_execution_levels.csv",
    "audit_records.csv",
    "claim_admission.json",
    "clean_build_matrix.csv",
    "common_executor_records.csv",
    "execution_accounting.csv",
    "failure_summary.csv",
    "fairness_limitations.md",
    "flip_summary.csv",
    "latency_summary.csv",
    "license_inventory.csv",
    "native_execution_records.csv",
    "numerical_error_summary.csv",
    "official_pipeline_matrix.csv",
    "official_sources.json",
    "portability_summary.csv",
    "provider_gate_records.csv",
    "raw_result_index.json",
    "resource_samples.csv",
    "retry_and_patch_inventory.csv",
    "security_summary.csv",
    "source_checkout_manifest.csv",
}
REQUIRED_DIRECTORIES = {
    "input_manifests",
    "operation_manifests",
    "per_sample_outputs",
    "provider_candidate_manifests",
    "workload_contracts",
}
FINAL_REQUIRED = {
    "CHECKPOINT_REPORT.md",
    "SHA256SUMS",
    "downtime_and_restart_log.csv",
    "environment_end.json",
    "manifest.json",
    "predecessor_comparison.csv",
    "resource_samples_raw.csv",
}
MISSING = {
    "NOT_REPORTED",
    "NOT_EVALUATED",
    "NOT_APPLICABLE",
    "OUTPUT_UNAVAILABLE",
    "BUILD_BLOCKED",
    "HARDWARE_BLOCKED",
    "CREDENTIAL_BLOCKED",
    "NOT_SEPARATELY_RECORDED",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_checksums(root: Path) -> None:
    sums = root / "SHA256SUMS"
    if not sums.exists():
        return
    for line in sums.read_text(encoding="ascii").splitlines():
        digest, relative = line.split("  ", 1)
        path = root / relative
        if not path.is_file() or sha256(path) != digest:
            raise ValueError(f"checksum mismatch: {relative}")


def content_tree_sha256(root: Path) -> str:
    lines = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in {"manifest.json", "SHA256SUMS"}:
            continue
        lines.append(f"{sha256(path)}  {relative}")
    material = "\n".join(lines) + "\n"
    return f"sha256:{hashlib.sha256(material.encode()).hexdigest()}"


def verify(root: Path) -> dict[str, int | str]:
    missing_files = sorted(name for name in REQUIRED if not (root / name).is_file())
    if missing_files:
        raise FileNotFoundError(f"missing V7 normalized files: {missing_files}")
    missing_directories = sorted(
        name for name in REQUIRED_DIRECTORIES
        if not (root / name).is_dir() or not (root / name / "manifest.json").is_file()
    )
    if missing_directories:
        raise FileNotFoundError(f"missing V7 evidence directories: {missing_directories}")
    final_manifest_path = root / "manifest.json"
    if final_manifest_path.exists():
        missing_final = sorted(name for name in FINAL_REQUIRED if not (root / name).is_file())
        if missing_final:
            raise FileNotFoundError(f"missing final V7 files: {missing_final}")
        final_manifest = json.loads(final_manifest_path.read_text(encoding="utf-8"))
        environment_end = json.loads((root / "environment_end.json").read_text(encoding="utf-8"))
        if final_manifest["state"] != "FROZEN":
            raise ValueError("final V7 manifest is not frozen")
        if final_manifest["source_commit"] != environment_end["source_commit"]:
            raise ValueError("final V7 source binding drift")
        if final_manifest["prepared_report"]["source_commit"] != final_manifest["source_commit"]:
            raise ValueError("prepared/final V7 source binding drift")
        if final_manifest["paper_claim_allowed"] is not False:
            raise ValueError("final V7 paper claim gate opened automatically")
        if environment_end["pre_freeze_working_tree_porcelain"] != "":
            raise ValueError("V7 source tree was dirty before evidence freeze")
        freeze_time = dt.datetime.fromisoformat(environment_end["finalization_timestamp"])
        pause_time = dt.datetime.fromisoformat(environment_end["declared_hard_pause_timestamp"])
        if freeze_time < pause_time:
            raise ValueError("V7 evidence was frozen before the hard-pause boundary")
        if final_manifest["content_tree_sha256"] != content_tree_sha256(root):
            raise ValueError("final V7 content tree digest mismatch")
        expected_policies = {
            "security_policy": "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055",
            "direct_policy": "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603",
        }
        for policy_name, expected_digest in expected_policies.items():
            binding = final_manifest["policy_bindings"][policy_name]
            artifact = REPO / binding["path"]
            if binding["policy_sha256"] != expected_digest or binding["artifact_sha256"] != f"sha256:{sha256(artifact)}":
                raise ValueError(f"V7 frozen policy binding drift: {policy_name}")
        publication = json.loads((root / "publication_inputs_manifest.json").read_text())
        if publication["table_count"] != 8 or publication["figure_count"] != 8:
            raise ValueError("V7 publication-input count drift")
        if len(list((root / "tables").glob("*.csv"))) != 8:
            raise ValueError("V7 publication table count drift")
        if len(list((root / "figures").glob("*.svg"))) != 8:
            raise ValueError("V7 publication figure count drift")
        for item in publication["files"]:
            path = root / item["path"]
            if not path.is_file() or f"sha256:{sha256(path)}" != item["sha256"]:
                raise ValueError(f"V7 publication input checksum drift: {item['path']}")

    levels = {row["system"]: row for row in read_csv(root / "artifact_execution_levels.csv")}
    if len(levels) != 18:
        raise ValueError(f"expected 18 systems, found {len(levels)}")
    heir_capture = REPO / "external/v7/outputs/heir/dot-product-8f-output-capture-v1/decrypted_outputs.csv"
    expected_heir_level = 3 if heir_capture.is_file() else 2
    expected_levels = {"EVA": 6, "ELASM": 3, "HECATE": 1, "HEIR": expected_heir_level, "HECO": 2, "Orion": 0}
    for system, expected in expected_levels.items():
        if int(levels[system]["evidence_level"]) != expected:
            raise ValueError(f"{system} evidence level drift")
    if int(levels["ANT-ACE"]["evidence_level"]) != 0:
        raise ValueError("source-only ANT-ACE was promoted to a clean build")
    if int(levels["ELASM"]["encrypted_e2e_runs"]) != 70:
        raise ValueError("ELASM 70/72 result was not preserved")

    core_manifest_path = REPO / "external/v7/outputs/corelab/elasm-linear-regression-grid-v1/manifest.json"
    core_records_path = REPO / "external/v7/outputs/corelab/elasm-linear-regression-grid-v1/records.csv"
    core_manifest = json.loads(core_manifest_path.read_text(encoding="utf-8"))
    core_rows = read_csv(core_records_path)
    if len(core_rows) != 72 or core_manifest["plans_attempted"] != 72:
        raise ValueError("CoreLab frozen 72-plan denominator drift")
    failed_plans = {(row["mode"], int(row["waterline"])) for row in core_rows if row["execution_status"] != "PASS"}
    if failed_plans != {("elasm", 36), ("elasm", 41)}:
        raise ValueError(f"CoreLab plan failure set drift: {failed_plans}")
    if core_manifest["encrypted_end_to_end_runs"] != 70:
        raise ValueError("CoreLab E2E count drift")
    if core_manifest["ephemeral_key_context_retained"] is not False:
        raise ValueError("CoreLab ephemeral key material retention drift")

    claims = json.loads((root / "claim_admission.json").read_text(encoding="utf-8"))
    if claims["final_classification"] != "PARTIAL_EXTERNAL_EVIDENCE":
        raise ValueError("V7 classification was improperly promoted")
    expected_encrypted_systems = 3 if heir_capture.is_file() else 2
    if claims["encrypted_e2e_system_count"] != expected_encrypted_systems:
        raise ValueError("encrypted E2E system count drift")
    if claims["decision_bearing_provider_count"] != 1:
        raise ValueError("decision-bearing provider count drift")
    if claims["portable_exact_count"] != 0:
        raise ValueError("PORTABLE_EXACT was invented")
    if claims["paper_claim_allowed"] is not False:
        raise ValueError("V7 paper claim gate opened automatically")

    native_path = root / "native_execution_records.csv"
    native_rows = read_csv(native_path)
    elasm_native = [row for row in native_rows if row["system"] == "ELASM"]
    if len(elasm_native) != 72 or sum(row["execution_status"] == "PASS" for row in elasm_native) != 70:
        raise ValueError("ELASM/CoreLab mode accounting drift")
    required_native_fields = {
        "schema_version", "provider_id", "provider_commit", "runtime", "workload_id",
        "evidence_level", "input_id", "plaintext_output", "decrypted_output",
        "numerical_error", "execution_status", "gate_status", "security_status",
        "raw_output_digest",
    }
    with native_path.open(newline="", encoding="utf-8") as handle:
        native_fields = set(csv.DictReader(handle).fieldnames or [])
    if not required_native_fields <= native_fields:
        raise ValueError("native execution schema is incomplete")
    captured_heir_rows = [
        row for row in native_rows
        if row["provider_id"] == "HEIR" and row["actual_output_available"] == "True"
    ]
    if heir_capture.is_file():
        raw_heir_rows = read_csv(heir_capture)
        if len(captured_heir_rows) != len(raw_heir_rows) or any(row["decrypted_output"] in MISSING for row in captured_heir_rows):
            raise ValueError("HEIR raw output capture was not normalized")
        if {row["runtime"] for row in captured_heir_rows} != {"OpenFHE"}:
            raise ValueError("HEIR raw output availability was improperly promoted")
        if any(
            row["actual_output_available"] == "True"
            for row in native_rows
            if row["provider_id"] == "HEIR" and row["runtime"] == "Lattigo"
        ):
            raise ValueError("Lattigo raw output was invented from a suppressed test log")
    elif captured_heir_rows:
        raise ValueError("HEIR output was invented without a capture artifact")

    per_sample_manifest = json.loads(
        (root / "per_sample_outputs/manifest.json").read_text(encoding="utf-8")
    )
    expected_per_sample = {
        "eva_official": 24576,
        "eva_shared": 174,
        "corelab": 72,
        "heir": len(read_csv(heir_capture)) if heir_capture.is_file() else 0,
    }
    if per_sample_manifest["row_counts"] != expected_per_sample:
        raise ValueError(f"per-sample population drift: {per_sample_manifest['row_counts']}")
    if per_sample_manifest["total_rows"] != sum(expected_per_sample.values()):
        raise ValueError("per-sample total drift")
    required_provider_fields = set(per_sample_manifest["schema_fields"])
    for path in sorted((root / "per_sample_outputs").glob("*.csv")):
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if set(reader.fieldnames or []) != required_provider_fields:
                raise ValueError(f"provider execution schema drift: {path.name}")
            for row_number, row in enumerate(reader, start=2):
                if any(value == "" for value in row.values()):
                    raise ValueError(f"blank provider output field: {path.name}:{row_number}")

    shared_rows = read_csv(root / "per_sample_outputs/eva_shared_polynomial.csv")
    validation_ids = {
        row["input_id"] for row in shared_rows
        if row["split_role"].startswith("configuration_validation")
    }
    audit_ids = {
        row["input_id"] for row in shared_rows
        if row["split_role"].startswith("locked_audit")
    }
    if validation_ids & audit_ids or len(validation_ids) != 14 or len(audit_ids) != 16:
        raise ValueError("EVA shared validation/audit identity drift")

    operation_manifest = json.loads(
        (root / "operation_manifests/manifest.json").read_text(encoding="utf-8")
    )
    if operation_manifest["operation_count"] < 37:
        raise ValueError("V7 operation manifest lost stage records")

    security_rows = read_csv(root / "security_summary.csv")
    required_security_fields = {
        "log_n", "n", "q_prime_bits", "p_prime_bits", "q_primes_exact",
        "p_primes_exact", "log_q", "log_p", "log_qp", "scale_bits",
        "secret_distribution", "error_distribution", "ciphertext_q_admission",
        "evaluation_key_qp_admission", "final_admission", "security_state",
    }
    with (root / "security_summary.csv").open(newline="", encoding="utf-8") as handle:
        security_fields = set(csv.DictReader(handle).fieldnames or [])
    if not required_security_fields <= security_fields:
        raise ValueError("security summary schema is incomplete")
    if any(row["headline_eligible"] == "True" for row in security_rows):
        raise ValueError("unaligned external runtime was promoted to a security headline")

    resource_rows = read_csv(root / "resource_samples.csv")
    required_resource_fields = {
        "docker_disk_usage_bytes", "process_rss_kib", "workspace_size_bytes",
        "completed_inputs", "completed_keysets", "heartbeat_age_seconds",
        "raw_resource_ledger_sha256",
    }
    with (root / "resource_samples.csv").open(newline="", encoding="utf-8") as handle:
        resource_fields = set(csv.DictReader(handle).fieldnames or [])
    if not resource_rows or not required_resource_fields <= resource_fields:
        raise ValueError("resource sample schema is incomplete")
    if any(row["resource_gate"] not in {"GREEN", "YELLOW", "RED", "HARD_RESOURCE_STOP"} for row in resource_rows):
        raise ValueError("resource gate value drift")

    retry_rows = read_csv(root / "retry_and_patch_inventory.csv")
    ledger_rows = [row for row in retry_rows if row["amendment"] in {"completed_jobs", "failed_jobs", "supplementary_jobs"}]
    if not ledger_rows:
        raise ValueError("provider attempt ledger was not normalized")
    for provider in {row["provider_or_scope"] for row in ledger_rows}:
        numeric_attempts = [
            int(row["attempt"]) for row in ledger_rows
            if row["provider_or_scope"] == provider and row["attempt"].isdigit()
        ]
        if numeric_attempts and max(numeric_attempts) > 3:
            raise ValueError(f"provider retry budget exceeded: {provider}")

    gate_rows = read_csv(root / "provider_gate_records.csv")
    selected = [row for row in gate_rows if row["audit_status"] == "SAFE"]
    if len(selected) != 1 or selected[0]["candidate_id"] != "eva_native_scale30_N14_QP240_ef28317b2a3d":
        raise ValueError("EVA locked candidate drift")
    if selected[0]["retuning"] != "0":
        raise ValueError("EVA locked audit retuning is nonzero")

    common = read_csv(root / "common_executor_records.csv")
    if common:
        raise ValueError("common-executor row exists without PORTABLE_EXACT evidence")
    for path in sorted(root.glob("*.csv")):
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            for row_number, row in enumerate(reader, start=1):
                if any(value == "" for value in row):
                    raise ValueError(f"blank missing value in {path.name}:{row_number}")

    publication_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix in {".csv", ".json", ".md"}
    )
    if "/home/ckks2" in publication_text:
        raise ValueError("local absolute path leaked into normalized evidence")
    prohibited = (
        "achieves the global optimum",
        "universally superior",
        "all state-of-the-art ckks",
    )
    lowered = publication_text.lower()
    for phrase in prohibited:
        if phrase in lowered:
            raise ValueError(f"prohibited V7 overclaim: {phrase}")
    verify_checksums(root)
    return {
        "system_count": len(levels),
        "encrypted_e2e_system_count": claims["encrypted_e2e_system_count"],
        "decision_bearing_provider_count": claims["decision_bearing_provider_count"],
        "classification": claims["final_classification"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    print(json.dumps(verify(args.root.resolve()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
