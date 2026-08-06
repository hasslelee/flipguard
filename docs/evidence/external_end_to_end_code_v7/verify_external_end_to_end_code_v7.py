#!/usr/bin/env python3
"""Verify normalized V7 evidence without promoting missing or unlike results."""

from __future__ import annotations

import argparse
import csv
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
    "latency_summary.csv",
    "license_inventory.csv",
    "native_execution_records.csv",
    "numerical_error_summary.csv",
    "official_pipeline_matrix.csv",
    "official_sources.json",
    "portability_summary.csv",
    "provider_gate_records.csv",
    "retry_and_patch_inventory.csv",
    "security_summary.csv",
    "source_checkout_manifest.csv",
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


def verify(root: Path) -> dict[str, int | str]:
    missing_files = sorted(name for name in REQUIRED if not (root / name).is_file())
    if missing_files:
        raise FileNotFoundError(f"missing V7 normalized files: {missing_files}")

    levels = {row["system"]: row for row in read_csv(root / "artifact_execution_levels.csv")}
    if len(levels) != 18:
        raise ValueError(f"expected 18 systems, found {len(levels)}")
    expected_levels = {"EVA": 6, "ELASM": 3, "HECATE": 1, "HEIR": 3, "HECO": 2, "Orion": 0}
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
    if claims["encrypted_e2e_system_count"] != 3:
        raise ValueError("encrypted E2E system count drift")
    if claims["decision_bearing_provider_count"] != 1:
        raise ValueError("decision-bearing provider count drift")
    if claims["portable_exact_count"] != 0:
        raise ValueError("PORTABLE_EXACT was invented")
    if claims["paper_claim_allowed"] is not False:
        raise ValueError("V7 paper claim gate opened automatically")

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
        for path in sorted(root.iterdir())
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
