#!/usr/bin/env python3
"""Create the deterministic V18 comparison-extension package manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "docs/evidence/comparison_extension_v18"
PACKAGE_ROOTS = [
    ROOT / "docs/checkpoints/comparison_extension_v18",
    EVIDENCE,
    ROOT / "docs/reports/comparison_extension_v18",
    ROOT / "results/comparison_extension_v18",
]
EXCLUDED = {EVIDENCE / "manifest.json", EVIDENCE / "SHA256SUMS"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def payload_files() -> list[Path]:
    files = []
    for root in PACKAGE_ROOTS:
        files.extend(path for path in root.rglob("*") if path.is_file())
    return sorted(set(files) - EXCLUDED, key=lambda path: path.relative_to(ROOT).as_posix())


def main() -> None:
    plan = EVIDENCE / "targeted_run_plan.json"
    (EVIDENCE / "targeted_run_plan.sha256").write_text(
        f"{sha256(plan)}  targeted_run_plan.json\n", encoding="ascii"
    )
    files = payload_files()
    records = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in files
    ]
    canonical = "".join(f"{item['sha256']}  {item['path']}\n" for item in records).encode()
    payload_digest = hashlib.sha256(canonical).hexdigest()
    metrics = json.loads((ROOT / "results/comparison_extension_v18/metrics.json").read_text(encoding="utf-8"))
    manifest = {
        "schema_version": "flipguard_comparison_extension_v18_manifest_v1",
        "status": "V18 COMPARISON EXTENSION COMPLETE — OFFLINE REPLAY SUFFICIENT",
        "scientific_execution_source_commit": "cefc44b0d7e351db2a34886dd758a2d31a3e4c12",
        "aggregation_tooling_commit": "86b0403208abbc741a65934358a5dea4a66e4d88",
        "protocol_sha256": metrics["protocol_sha256"],
        "v17_cases_reused": metrics["v17_cases_all_scope"],
        "v17_primary_cases_reused": metrics["v17_cases_primary"],
        "v17_direct_candidate_evaluations_reused": metrics["direct_candidate_evaluations"],
        "v17_finite_reference_evaluations_reused": metrics["finite_reference_candidate_evaluations"],
        "v17_formal_latency_rows_reused": metrics["formal_latency_rows"],
        "new_encrypted_candidate_evaluations": 0,
        "package_file_count": len(records),
        "package_payload_sha256": payload_digest,
        "files": records,
    }
    (EVIDENCE / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    sums = payload_files() + [EVIDENCE / "manifest.json"]
    (EVIDENCE / "SHA256SUMS").write_text(
        "".join(f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}\n" for path in sorted(sums)),
        encoding="ascii",
    )
    print(
        "V18_FREEZE_PASS "
        f"files={len(records)} payload_sha256={payload_digest} manifest_sha256={sha256(EVIDENCE / 'manifest.json')}"
    )


if __name__ == "__main__":
    main()
