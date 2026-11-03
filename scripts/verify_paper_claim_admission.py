#!/usr/bin/env python3
"""Verify the canonical FlipGuard paper-claim admission registry."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


STATES = {
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "BLOCKED",
    "NOT_EVALUATED",
    "SUPERSEDED",
    "PILOT_ONLY",
}
REQUIRED_ADMITTED = {
    "scoped_direct_synthesis",
    "adaptive_repair",
    "formal_trial_reduction",
    "primary_no_retuning_locked_audit",
    "no_safe_behavior",
    "paired_latency",
    "structural_extension",
    "scoped_non_tabular_extension",
    "training_model_seed_extension",
    "security_attestation",
    "finite_scope_decision_integrity",
}
REQUIRED_BLOCKED = {
    "natural_data_margin_literal_effect",
    "instantiated_analytical_ckks_certificate",
    "distribution_wide_safety",
    "arbitrary_graph_support",
    "global_optimum",
    "cross_runtime_numerical_equivalence",
    "general_external_autotuner_integration",
    "production_latency",
    "universal_runtime_security",
}


def sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=Path("docs/evidence/paper_claim_admission_v1"),
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.evidence_root.resolve()
    repo_root = args.repo_root.resolve()
    manifest = json.loads((root / "manifest.json").read_text())
    if (
        manifest["evidence_id"] != "paper_claim_admission_v1"
        or manifest["paper_claim_allowed"] is not True
        or manifest["frozen_evidence_manifests_modified"] is not False
        or re.fullmatch(r"[0-9a-f]{40}", manifest["source_commit"]) is None
    ):
        raise ValueError("claim-admission manifest changed")
    for name, record in manifest["files"].items():
        path = root / name
        if (
            not path.is_file()
            or path.stat().st_size != record["bytes"]
            or sha256(path) != record["sha256"]
        ):
            raise ValueError(f"{name}: registry file changed")

    document = json.loads((root / "claims.json").read_text())
    claims = {item["claim_id"]: item for item in document["claims"]}
    admitted = {key for key, item in claims.items() if item["paper_admitted"]}
    blocked = set(claims) - admitted
    if admitted != REQUIRED_ADMITTED or blocked != REQUIRED_BLOCKED:
        raise ValueError("admitted or blocked claim set changed")
    if (
        document["paper_claim_allowed"] is not True
        or any(item["state"] not in STATES for item in claims.values())
        or any(
            not item["exact_allowed_wording_en"]
            or not item["exact_allowed_wording_ko"]
            for item in claims.values()
            if item["paper_admitted"]
        )
        or any(
            item["exact_allowed_wording_en"]
            or item["exact_allowed_wording_ko"]
            for item in claims.values()
            if not item["paper_admitted"]
        )
    ):
        raise ValueError("claim vocabulary or exact wording changed")
    if (
        manifest["admitted_claim_count"] != len(admitted)
        or manifest["blocked_or_not_admitted_claim_count"] != len(blocked)
    ):
        raise ValueError("claim counts changed")

    with (root / "claim_evidence_dependencies.csv").open(newline="") as handle:
        dependency_rows = list(csv.DictReader(handle))
    bound = {(row["claim_id"], row["dependency_id"]) for row in dependency_rows}
    for item in claims.values():
        for dependency in item["evidence_dependencies"]:
            if (item["claim_id"], dependency) not in bound:
                raise ValueError(
                    f"{item['claim_id']}: dependency {dependency} is unbound"
                )
    for row in dependency_rows:
        record = manifest["dependency_records"][row["dependency_id"]]
        if (
            row["verification_status"] != "DIGEST_BOUND"
            or row["manifest_sha256"]
            != record["manifest_sha256"]
            or sha256(repo_root / record["path"]) != record["manifest_sha256"]
        ):
            raise ValueError("dependency digest binding changed")

    allowed = (root / "allowed_sentences.md").read_text()
    forbidden_tokens = (
        "first CKKS",
        "global optimum",
        "universal speedup",
        "50 independent",
        "distribution-wide safety",
    )
    if any(token in allowed for token in forbidden_tokens):
        raise ValueError("allowed sentence contains a prohibited headline")

    expected = []
    for path in sorted(root.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS":
            expected.append(
                f"{sha256(path).removeprefix('sha256:')}  {path.name}\n"
            )
    if (root / "SHA256SUMS").read_text() != "".join(expected):
        raise ValueError("claim registry SHA256SUMS mismatch")
    print(
        "paper_claim_admission=VERIFIED "
        f"paper_claim_allowed=true admitted={len(admitted)} "
        f"blocked={len(blocked)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
