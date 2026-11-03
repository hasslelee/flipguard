#!/usr/bin/env python3
"""End-to-end static verifier for the immutable JOURNAL_EXTENSION_V1 overlay."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


BASE_COMMIT = "a4a8f7d7f5a7588d60c804c2cebec1781006f254"
RC2_COMMIT = "6c5f8b234f9f9da91a189fa0f2dc180bb996abf5"
IMMUTABLE_PATHS = [
    "docs/thesis",
    "results/thesis_grade_protocol/paper_artifacts_v3/final",
    "docs/evidence/research_completion_checkpoint_v10",
    "docs/evidence/security_v2_static_attestation",
    "docs/evidence/security_v2_static_attestation_formal_v2",
    "docs/evidence/security_v2_bounded_oracle_v1",
    "internal/ckksplanner/direct_policy.go",
    "internal/ckksplanner/security_policy.go",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("FAIL: " + message)


def output(command: list[str], root: Path) -> str:
    return subprocess.run(command, cwd=root, check=True, text=True, capture_output=True).stdout.strip()


def run(command: list[str], root: Path) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=root, check=True)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-go-theorem-tests", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]

    require(output(["git", "rev-parse", "flipguard-thesis-v1.0.0-rc2^{}"], root) == RC2_COMMIT, "RC2 tag binding")
    diff = subprocess.run(
        ["git", "diff", "--quiet", BASE_COMMIT, "--", *IMMUTABLE_PATHS], cwd=root
    )
    require(diff.returncode == 0, "immutable RC2/V3/V10/thesis paths changed since journal branch point")

    python = sys.executable
    commands = [
        [python, "scripts/build_security_v2_static_artifacts.py", "--verify"],
        [python, "scripts/verify_flipguard_v3_paper_artifacts.py"],
        [python, "docs/evidence/research_completion_checkpoint_v10/verify_research_completion_checkpoint_v10.py"],
        [python, "scripts/verify_journal_multiclass_extension_protocol_v1.py"],
        [python, "scripts/verify_journal_multiclass_analysis_plan_v1.py"],
        [python, "scripts/verify_journal_multiclass_extension_results_v1.py"],
        [python, "scripts/verify_journal_multiclass_activation_v1.py"],
        [python, "scripts/verify_journal_extension_paper_inputs_v1.py"],
    ]
    for command in commands:
        run(command, root)
    if not args.skip_go_theorem_tests:
        run(["go", "test", "./internal/certify", "-run", "Multiclass"], root)
        run(["go", "test", "./internal/ckksplanner", "-run", "Multiclass"], root)

    result = load(root / "docs/evidence/journal_multiclass_extension_results_v1/summary.json")
    require(result["policy_retuning"] == 0 and result["audit_retuning"] == 0, "result retuning")
    require(result["combined"]["models"] == 2, "mandatory model count")
    require(result["combined"]["security_v2_bounded_catalog_denominator"] == 14, "catalog denominator")
    require(result["combined"]["security_v2_bounded_catalog_encrypted_candidates"] == 6, "catalog executable count")
    for model in ["mlp_100", "lenet5_small"]:
        row = result["models"][model]
        require(row["direct_selection"]["status"] == "SAFE", f"{model} validation status")
        require(row["direct_selection"]["security"]["final_admission"] == "PASS", f"{model} security")
        require(row["locked_audit"]["candidate_identity_match"] is True, f"{model} audit identity")
        require(row["locked_audit"]["retuning_count"] == 0, f"{model} audit retuning")

    activation = load(root / "docs/evidence/journal_multiclass_activation_v1/activation_summary.json")
    require(activation["activation_class"] in {
        "A_LITERAL_EFFECT_SUPPORTED", "B_ADMISSION_EFFECT_ONLY", "C_NO_OBSERVED_ACTIVATION"
    }, "activation class")
    require(activation["lenet_graph_only"]["encrypted_execution"] == 0, "LeNet unsupported comparator execution")
    require(activation["latency_only_no_certification"]["latency_claim"] == "DESCRIPTIVE_UNPAIRED_ONLY", "extension latency scope")

    paper_root = root / "results/thesis_grade_protocol/journal_extension_paper_inputs_v1"
    paper = load(paper_root / "summary.json")
    status = load(paper_root / "publication_status.json")
    claims = load(paper_root / "publication_inputs/claim_registry.json")
    require(paper["tables"] == 8 and paper["figures"] == 8, "paper input counts")
    require(paper["new_paired_latency_execution"] == 0, "new paired latency execution")
    require(paper["core_rc2_v3_v10_modified"] is False, "core modification flag")
    require(status["kiisc_formatting_started"] is False, "KIISC formatting")
    require(status["formal_journal_latency_claim"] is False, "formal journal latency claim")
    claim_map = {claim["claim_id"]: claim for claim in claims["claims"]}
    require(claim_map["journal_extension_latency"]["state"] == "BLOCKED", "latency claim state")
    require(claim_map["arbitrary_packed_cnn"]["state"] == "BLOCKED", "packed-CNN claim state")
    for path in sorted((paper_root / "figures").glob("*.svg")):
        ET.fromstring(path.read_text(encoding="utf-8"))
    require(len(list((paper_root / "tables").glob("*.md"))) == 8, "table file count")
    require(len(list((paper_root / "figures").glob("*.svg"))) == 8, "figure file count")
    print("PASS: JOURNAL_EXTENSION_V1 final static gate")


if __name__ == "__main__":
    main()
