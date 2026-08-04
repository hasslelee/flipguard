#!/usr/bin/env python3
"""Verify the frozen focused MLP paired-latency evidence pack."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA = "flipguard_journal_mlp_paired_latency_evidence_v1"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify(pack: Path, repo: Path) -> dict:
    pack, repo = pack.resolve(), repo.resolve()
    manifest = load(pack / "manifest.json")
    summary = load(pack / "analysis" / "summary.json")
    claim = load(pack / "analysis" / "claim_admission.json")
    require(manifest["schema_version"] == SCHEMA, "schema")
    require(manifest["evidence_id"] == "journal_mlp_paired_latency_v1", "evidence ID")
    require(manifest["execution_source_commit"] == "6fa773b8d46c0b28a6632f2415e44c2e763e18c5", "execution commit")
    require(manifest["successful_keysets"] == 3 and manifest["measurement_records"] == 5400, "population")
    require(manifest["policy_retuning"] == 0 and manifest["new_dataset_or_model"] == 0, "scope")
    require(summary["records"] == 5400 and summary["argmax_flips"] == 0, "summary")
    require(summary["reserve_policy_rejects"] == 0, "reserve results")
    require(claim["effect_class"] == "LITERAL_EFFECT_ONLY", "effect class")
    require(claim["latency_superiority_paper_admitted"] is False, "superiority gate")
    require(claim["graph_only_full_locked_audit_pass"] is False, "graph-only audit limitation")
    for keyset in range(1, 4):
        root = pack / "raw" / f"keyset_{keyset:02d}"
        completion = load(root / "completed.json")
        require(completion["records"] == 1800, f"keyset {keyset} count")
        require(completion["ledger_sha256"] == sha(root / "records.jsonl"), f"keyset {keyset} ledger")
        require(completion["result_sha256"] == sha(root / "result.json"), f"keyset {keyset} result")
        with (root / "records.jsonl").open(encoding="utf-8") as handle:
            require(sum(1 for line in handle if line.strip()) == 1800, f"keyset {keyset} rows")
    failures = load(pack / "preflight_failures.json")
    require(failures["encrypted_measurement_records_before_v1_3"] == 0, "preflight record count")
    require(len(failures["preserved_failures"]) == 4, "preserved preflight failures")
    protocol = load(pack / "protocol" / "execution_protocol.json")
    require(protocol["protocol_id"].endswith("_v1_3"), "final protocol")
    require(protocol["expected_measurement_records"] == 5400, "protocol records")
    for item in manifest["external_bindings"]:
        require(sha(repo / item["path"]) == item["sha256"], f"external binding {item['path']}")
    sums = {}
    for line in (pack / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        sums[name] = digest
    for path in sorted(pack.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            relative = str(path.relative_to(pack))
            require(sums.get(relative) == sha(path).removeprefix("sha256:"), f"checksum {relative}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    default = Path(__file__).resolve().parent
    if default.name == "scripts":
        default = Path("docs/evidence/journal_mlp_paired_latency_v1")
    parser.add_argument("--pack", type=Path, default=default)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    summary = verify(args.pack, args.repo)
    print(f"journal_mlp_paired_latency_evidence=VERIFIED records={summary['records']} effect={summary['effect_class']}")
