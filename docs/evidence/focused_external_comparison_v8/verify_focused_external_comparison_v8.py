#!/usr/bin/env python3
"""Deterministically verify the focused external-comparison V8 pack."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[3]
PACK = Path(__file__).resolve().parent
REQUIRED = (
    "manifest.json", "predecessor_v7.json", "environment_start.json", "environment_end.json",
    "eva_population_records.csv", "heir_shared_polynomial_records.csv", "corelab_multi_input_records.csv",
    "provider_gate_records.csv", "audit_records.csv", "common_executor_records.csv", "common_executor_paired_summary.csv",
    "operation_mismatch_records.csv", "latency_records.csv", "latency_summary.csv",
    "numerical_error_summary.csv", "unique_input_accounting.csv", "execution_accounting.csv",
    "security_summary.csv", "portability_summary.csv", "failure_summary.csv",
    "fairness_limitations.md", "claim_admission.json", "CHECKPOINT_REPORT.md", "SHA256SUMS",
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
        if int(row["raw_rows"]) > 0 and int(row["unique_inputs"]) <= 0:
            raise RuntimeError("raw row count masquerades as missing unique input population")
    if manifest["cross_runtime_ratio_claim_allowed"]:
        raise RuntimeError("cross-runtime ratio must remain blocked")
    claims = json.loads((PACK / "claim_admission.json").read_text())
    if claims["claims"]["paired_common_executor_latency"] == "SUPPORTED":
        common = rows("common_executor_records.csv")
        if len(common) != 5400 or {row["latency_state"] for row in common} != {"PAIRED_HEADLINE"}:
            raise RuntimeError("paired latency admitted without the frozen 5,400 common-harness records")
    text = "\n".join((PACK / name).read_text(encoding="utf-8", errors="ignore") for name in ("CHECKPOINT_REPORT.md", "fairness_limitations.md"))
    for phrase in ("global optimum", "all state-of-the-art", "universally safe"):
        if phrase in text.lower():
            raise RuntimeError(f"prohibited overclaim in V8 pack: {phrase}")
    print(json.dumps({"status": "PASS", "classification": manifest["classification"], "required_files": len(REQUIRED), "checksums": len(checksums)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
