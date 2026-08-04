#!/usr/bin/env python3
"""Freeze raw, derived, and negative preflight evidence for MLP paired latency."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from verify_journal_mlp_paired_latency_evidence_v1 import verify


SCHEMA = "flipguard_journal_mlp_paired_latency_evidence_v1"
DEFAULT_OUTPUT = Path("docs/evidence/journal_mlp_paired_latency_v1")
PROTOCOL = Path("docs/evidence/journal_mlp_paired_latency_protocol_v1_3")
EXECUTION = Path("results/journal_mlp_paired_latency_v1/execution")
ANALYSIS = Path("results/journal_mlp_paired_latency_v1/analysis")
BINARY = Path("results/journal_mlp_paired_latency_v1/bin/v1_3/flipguard-journal-mlp-paired-latency")
VERIFIER = Path("scripts/verify_journal_mlp_paired_latency_evidence_v1.py")


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def copy_file(repo: Path, source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(repo / source, target)


def build(repo: Path, output: Path, evidence_commit: str) -> None:
    if output.exists():
        raise RuntimeError(f"refusing to overwrite evidence pack: {output}")
    output.mkdir(parents=True)
    shutil.copytree(repo / PROTOCOL, output / "protocol")
    shutil.copytree(repo / ANALYSIS, output / "analysis")
    orchestration = load(repo / EXECUTION / "orchestration_complete.json")
    for item in orchestration["keysets"]:
        source_root = repo / item["path"]
        target_root = output / "raw" / f"keyset_{item['keyset']:02d}"
        target_root.mkdir(parents=True)
        for name in ["run_manifest.json", "records.jsonl", "result.json", "completed.json"]:
            shutil.copyfile(source_root / name, target_root / name)
        log_path = repo / item["log"]
        shutil.copyfile(log_path, target_root / "process.log")
    shutil.copyfile(repo / EXECUTION / "orchestration_complete.json", output / "raw" / "orchestration_complete.json")

    failures = []
    for path in sorted((repo / EXECUTION).glob("keyset_01_attempt_0[1-4].log")):
        target = output / "raw" / "preflight_failures" / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        message = path.read_text(encoding="utf-8").strip()
        failures.append({
            "source_path": str(path.relative_to(repo)),
            "frozen_path": str(target.relative_to(output)),
            "sha256": sha(target), "message": message,
            "classification": "RECOVERABLE_IMPLEMENTATION_FAILURE",
        })
    failure_summary = {
        "schema_version": SCHEMA,
        "preserved_failures": failures,
        "encrypted_measurement_records_before_v1_3": 0,
        "candidate_or_policy_changes": 0,
        "resolution": "V1.3 binary preflight parses all protocol evidence fields before attempt creation",
    }
    (output / "preflight_failures.json").write_text(canonical(failure_summary), encoding="utf-8")
    shutil.copyfile(repo / VERIFIER, output / VERIFIER.name)
    (output / "README.md").write_text(
        "# Journal MLP Paired Latency Evidence V1\n\n"
        "This pack preserves three successful fresh-key process blocks, all 5,400 single-image "
        "timing records, deterministic image-cluster analysis, and every pre-measurement parser "
        "failure. The S29/S32 result is LITERAL_EFFECT_ONLY; no S29 latency-superiority claim is admitted.\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": SCHEMA,
        "evidence_id": "journal_mlp_paired_latency_v1",
        "execution_source_commit": "6fa773b8d46c0b28a6632f2415e44c2e763e18c5",
        "execution_current_suite_commit": load(output / "raw" / "keyset_01" / "run_manifest.json")["current_source_commit"],
        "evidence_builder_commit": evidence_commit,
        "binary_sha256": sha(repo / BINARY),
        "protocol_sha256": sha(output / "protocol" / "execution_protocol.json"),
        "successful_keysets": 3, "measurement_records": 5400,
        "latency_images": 100, "measurement_passes": 6,
        "policy_retuning": 0, "new_dataset_or_model": 0,
        "effect_class": load(output / "analysis" / "claim_admission.json")["effect_class"],
        "external_bindings": [
            {"path": str(BINARY), "sha256": sha(repo / BINARY)},
            {"path": "results/journal_multiclass_extension_v1/encrypted/mnist_mlp_square_784_100_10_v1/locked_audit_result.json", "sha256": sha(repo / "results/journal_multiclass_extension_v1/encrypted/mnist_mlp_square_784_100_10_v1/locked_audit_result.json")},
            {"path": "results/journal_multiclass_extension_v1/comparators/mlp_graph_only_fixed_logit_tolerance_v1/result.json", "sha256": sha(repo / "results/journal_multiclass_extension_v1/comparators/mlp_graph_only_fixed_logit_tolerance_v1/result.json")},
        ],
    }
    (output / "manifest.json").write_text(canonical(manifest), encoding="utf-8")
    sums = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            sums.append(f"{sha(path).removeprefix('sha256:')}  {path.relative_to(output)}\n")
    (output / "SHA256SUMS").write_text("".join(sums), encoding="utf-8")
    verify(output, repo)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--evidence-commit", required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    output = args.output.resolve()
    build(repo, output, args.evidence_commit)
    print(f"journal_mlp_paired_latency_evidence=FROZEN output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
