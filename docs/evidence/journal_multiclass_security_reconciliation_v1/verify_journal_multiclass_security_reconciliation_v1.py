#!/usr/bin/env python3
"""Verify candidate-specific journal multiclass security reconciliation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from verify_journal_multiclass_exact_estimator import verify as verify_estimator


SCHEMA = "flipguard_journal_multiclass_security_reconciliation_v1"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_sha256sums(pack: Path) -> None:
    expected = []
    for path in sorted(pack.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            expected.append(
                f"{digest(path).removeprefix('sha256:')}  {path.relative_to(pack)}\n"
            )
    require((pack / "SHA256SUMS").read_text() == "".join(expected), "SHA256SUMS mismatch")


def verify(pack: Path, repo: Path) -> dict:
    manifest = load(pack / "manifest.json")
    summary = load(pack / "reconciliation.json")
    require(manifest["schema_version"] == SCHEMA, "manifest schema")
    require(summary["schema_version"] == SCHEMA, "summary schema")
    require(summary["classification"] == "CLASS_S1_ESTIMATOR_ADAPTER_MISMATCH", "S1 class")
    require(summary["root_cause"] == "RESULT_SCOPE_AND_AGGREGATION_MISMATCH", "root cause")
    require(summary["original_estimator_input_journal_candidates"] == 0, "original scope")
    require(summary["security_amendment_required"] is False, "amendment status")
    require(summary["encrypted_replay_required"] is False, "replay status")
    require(summary["policy_retuning"] == 0 and summary["literal_changes"] == 0, "policy/literal change")
    require(
        summary["models"]["mlp_100"]["final_security_state"] == "SECURITY_CORRECTED_AND_REPLAYED",
        "MLP final state",
    )
    require(
        summary["models"]["lenet5_small"]["final_security_state"] == "SECURITY_CORRECTED_AND_REPLAYED",
        "LeNet final state",
    )
    require(summary["models"]["mlp_100"]["minimum_classical_bits"] >= 128, "MLP security bits")
    require(summary["models"]["lenet5_small"]["minimum_classical_bits"] >= 128, "LeNet security bits")
    require(summary["distribution_caveat"]["exact_distribution_claim_allowed"] is False, "distribution caveat")

    for binding in manifest["input_bindings"]:
        path = repo / binding["path"]
        require(path.is_file(), f"missing input: {binding['path']}")
        require(digest(path) == binding["sha256"], f"changed input: {binding['path']}")
    for name, record in manifest["generated_files"].items():
        require(digest(pack / name) == record["sha256"], f"changed generated file: {name}")

    materialization = repo / manifest["materialization"]["path"]
    for result in manifest["estimator_results"]:
        verified = verify_estimator(repo / result["path"], materialization)
        require(verified["summary"]["pass"] == 4 and verified["summary"]["fail"] == 0, "estimator result")

    with (pack / "candidate_security_summary.csv").open(newline="") as handle:
        candidate_rows = list(csv.DictReader(handle))
    with (pack / "object_security_summary.csv").open(newline="") as handle:
        object_rows = list(csv.DictReader(handle))
    with (pack / "attack_results.csv").open(newline="") as handle:
        attack_rows = list(csv.DictReader(handle))
    require(len(candidate_rows) == 8, "candidate summary rows")
    require(len(object_rows) == 16, "object summary rows")
    require(len(attack_rows) == 48, "attack rows")
    require(all(row["final_status"] == "PASS_ESTIMATOR_MODEL" for row in candidate_rows), "candidate failures")
    require(all(row["attack_status"] == "PASS" for row in attack_rows), "attack invocation failures")
    verify_sha256sums(pack)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pack",
        type=Path,
        default=Path("docs/evidence/journal_multiclass_security_reconciliation_v1"),
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    manifest = verify(args.pack.resolve(), args.repo.resolve())
    print(
        "journal_multiclass_security_reconciliation_v1=VERIFIED "
        f"classification={manifest['classification']} amendment=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
