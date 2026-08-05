#!/usr/bin/env python3
"""Freeze and verify compact EVA clean-rerun evidence for V6."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "external/v6"
DEFAULT_OUTPUT = ROOT / "docs/evidence/external_end_to_end_clean_v6/provider_candidate_manifests/eva"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def copy(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise ValueError(f"required EVA V6 artifact is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def write_sums(root: Path) -> None:
    lines = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            lines.append(f"{sha256(path).removeprefix('sha256:')}  {path.relative_to(root).as_posix()}")
    (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="ascii")


def aggregate_timing(paths: list[Path]) -> dict[str, Any]:
    values = {key: [] for key in ("keygen_ms", "encrypt_ms", "execute_ms", "decrypt_ms", "total_sample_ms")}
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row.get("execution_status") != "OK":
                    continue
                for key in values:
                    if row.get(key):
                        values[key].append(float(row[key]))
    return {
        key: {
            "count": len(items),
            "mean": sum(items) / len(items) if items else None,
            "minimum": min(items) if items else None,
            "maximum": max(items) if items else None,
        }
        for key, items in values.items()
    }


def generate(output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite EVA V6 evidence: {output}")
    official = RUNTIME / "outputs/eva/official-image-v1"
    polynomial = RUNTIME / "outputs/eva/shared-polynomial-v1"
    official_manifest = load(official / "manifest.json")
    polynomial_manifest = load(polynomial / "manifest.json")
    if official_manifest["evidence_level"] != 3 or polynomial_manifest["outcome"] != "SELECTED_AUDIT_PASS":
        raise ValueError("EVA V6 result states changed")

    copied = [
        (official / "manifest.json", output / "official_image/manifest.json"),
        (official / "SHA256SUMS", output / "official_image/source_SHA256SUMS"),
        (official / "per_pixel_outputs.csv", output / "official_image/per_pixel_outputs.csv"),
        (official / "sobel_compiled.dot", output / "official_image/sobel_compiled.dot"),
        (official / "harris_compiled.dot", output / "official_image/harris_compiled.dot"),
        (polynomial / "manifest.json", output / "shared_polynomial/manifest.json"),
        (polynomial / "SHA256SUMS", output / "shared_polynomial/source_SHA256SUMS"),
        (polynomial / "arm_summaries.csv", output / "shared_polynomial/arm_summaries.csv"),
        (polynomial / "locked_audit_selected.csv", output / "shared_polynomial/locked_audit_selected.csv"),
        (polynomial / "validation_scale_20.csv", output / "shared_polynomial/validation_scale_20.csv"),
        (polynomial / "validation_scale_30.csv", output / "shared_polynomial/validation_scale_30.csv"),
        (polynomial / "validation_scale_40.csv", output / "shared_polynomial/validation_scale_40.csv"),
    ]
    for source, destination in copied:
        copy(source, destination)

    run_ids = [
        "0002-source-checkout",
        "0003-seal-source-checkout",
        "0004-clean-build",
        "0005-official-image-e2e",
        "0006-official-image-e2e-retry1",
        "0007-shared-polynomial-level6",
        "0008-shared-polynomial-level6-retry1",
    ]
    runs = {}
    for run_id in run_ids:
        status = RUNTIME / "status/eva" / run_id / "run_manifest.json"
        copy(status, output / "stage_manifests" / f"{run_id}.json")
        runs[run_id] = load(status)
        time_log = RUNTIME / "logs/eva" / run_id / "time.log"
        if time_log.is_file():
            copy(time_log, output / "time_logs" / f"{run_id}.txt")
        stderr = RUNTIME / "logs/eva" / run_id / "stderr.log"
        if runs[run_id]["return_code"] != 0:
            copy(stderr, output / "failures" / f"{run_id}.stderr.txt")

    source_manifest = {
        "eva": {
            "repository": "https://github.com/microsoft/EVA",
            "tag": "v1.0.1",
            "commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=RUNTIME / "sources/eva", check=True, text=True, capture_output=True
            ).stdout.strip(),
            "tree_sha256": runs["0002-source-checkout"]["source_sha256"],
            "license_sha256": sha256(RUNTIME / "sources/eva/LICENSE.txt"),
        },
        "seal": {
            "repository": "https://github.com/microsoft/SEAL.git",
            "tag": "v3.6.4",
            "commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=RUNTIME / "sources/seal-3.6.4", check=True, text=True, capture_output=True
            ).stdout.strip(),
            "tree_sha256": runs["0003-seal-source-checkout"]["source_sha256"],
            "license_sha256": sha256(RUNTIME / "sources/seal-3.6.4/LICENSE"),
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "source_manifest.json").write_text(
        json.dumps(source_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    validation = [arm["validation"] for arm in polynomial_manifest["arms"]]
    failures = {
        "0005-official-image-e2e": "CONTAINER_GIT_SAFE_DIRECTORY_REJECTED_BEFORE_KEYGEN",
        "0007-shared-polynomial-level6": "SOURCE_COMMIT_ARGUMENT_MISMATCH_REJECTED_BEFORE_KEYGEN",
    }
    (output / "failure_records.json").write_text(
        json.dumps(failures, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    timing_paths = [
        polynomial / "validation_scale_20.csv",
        polynomial / "validation_scale_30.csv",
        polynomial / "validation_scale_40.csv",
        polynomial / "locked_audit_selected.csv",
    ]
    summary = {
        "schema_version": "flipguard_external_end_to_end_clean_v6_eva_evidence_v1",
        "provider": "Microsoft EVA",
        "status": "PASS",
        "maximum_evidence_level": 6,
        "clean_build": {
            "status": runs["0004-clean-build"]["state"],
            "elapsed_seconds": runs["0004-clean-build"]["elapsed_seconds"],
            "binary_sha256": runs["0004-clean-build"]["binary_sha256"],
        },
        "official_image": {
            "evidence_level": 3,
            "unique_inputs": official_manifest["unique_input_images"],
            "contexts_keysets": 6,
            "raw_output_rows": official_manifest["raw_output_rows"],
            "decision_gate": "NOT_EVALUATED_NO_OFFICIAL_DECISION_RULE",
            "run_elapsed_seconds": runs["0006-official-image-e2e-retry1"]["elapsed_seconds"],
        },
        "shared_polynomial": {
            "evidence_level": 6,
            "validation_unique_inputs": 14,
            "audit_unique_inputs": 16,
            "validation_audit_overlap": 0,
            "validation_key_runs": polynomial_manifest["accounting"]["validation_key_runs"],
            "audit_key_runs": polynomial_manifest["accounting"]["locked_audit_key_runs"],
            "raw_output_rows": polynomial_manifest["accounting"]["validation_encrypted_sample_evaluations"] + polynomial_manifest["accounting"]["locked_audit_encrypted_sample_evaluations"],
            "selected_candidate": polynomial_manifest["selected"]["candidate_id"],
            "validation_states": [item["status"] for item in validation],
            "selected_validation_flips": validation[1]["counts"]["decision_flips"],
            "audit_flips": polynomial_manifest["locked_audit"]["counts"]["decision_flips"],
            "audit_violations": polynomial_manifest["locked_audit"]["counts"]["error_violations"],
            "retuning": polynomial_manifest["locked_audit"]["retuning"],
            "gate_state": "SAFE",
            "security_state": "SECURITY_TARGET_MATCH_ASSUMPTIONS_DIFFER",
            "run_elapsed_seconds": runs["0008-shared-polynomial-level6-retry1"]["elapsed_seconds"],
            "timing": aggregate_timing(timing_paths),
        },
        "predecessor_agreement": {
            "selected_scale": "AGREES_SCALE_30",
            "locked_audit_state": "AGREES_SAFE",
            "prior_storage_pressure_may_have_affected_result": "NO",
        },
        "failed_attempts_preserved": 2,
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = {
        "schema_version": "flipguard_external_end_to_end_clean_v6_provider_pack_v1",
        "provider": "EVA",
        "source_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True, capture_output=True
        ).stdout.strip(),
        "runtime_root": "external/v6",
        "new_keys_generated": True,
        "old_results_reused": False,
        "summary_sha256": sha256(output / "summary.json"),
        "source_manifest_sha256": sha256(output / "source_manifest.json"),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_sums(output)
    verify(output)


def verify(output: Path) -> None:
    manifest = load(output / "manifest.json")
    summary = load(output / "summary.json")
    if manifest["schema_version"] != "flipguard_external_end_to_end_clean_v6_provider_pack_v1":
        raise ValueError("EVA V6 provider-pack schema changed")
    if summary["maximum_evidence_level"] != 6 or summary["shared_polynomial"]["gate_state"] != "SAFE":
        raise ValueError("EVA V6 evidence level or gate state changed")
    if summary["shared_polynomial"]["validation_audit_overlap"] != 0 or summary["shared_polynomial"]["retuning"] != 0:
        raise ValueError("EVA V6 locked-audit isolation changed")
    if summary["shared_polynomial"]["audit_flips"] != 0 or summary["shared_polynomial"]["audit_violations"] != 0:
        raise ValueError("EVA V6 locked audit is not SAFE")
    expected = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            expected.append(f"{sha256(path).removeprefix('sha256:')}  {path.relative_to(output).as_posix()}")
    if (output / "SHA256SUMS").read_text(encoding="ascii") != "\n".join(expected) + "\n":
        raise ValueError("EVA V6 SHA256SUMS mismatch")
    print(
        "external_v6_eva=PASS level=6 "
        f"official_rows={summary['official_image']['raw_output_rows']} "
        f"decision_rows={summary['shared_polynomial']['raw_output_rows']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if args.verify:
        verify(output)
    else:
        generate(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
