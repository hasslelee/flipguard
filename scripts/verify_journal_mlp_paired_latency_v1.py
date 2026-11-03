#!/usr/bin/env python3
"""Verify focused MLP paired-latency results and derived admission."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


SCHEMA = "flipguard_journal_mlp_paired_latency_analysis_v1"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify(output: Path, repo: Path) -> dict:
    output, repo = output.resolve(), repo.resolve()
    manifest = load(output / "manifest.json")
    summary = load(output / "summary.json")
    claim = load(output / "claim_admission.json")
    require(manifest["schema_version"] == SCHEMA, "manifest schema")
    require(summary["schema_version"] == SCHEMA and claim["schema_version"] == SCHEMA, "derived schema")
    require(summary["records"] == 5400 and summary["images"] == 100, "population")
    require(summary["keysets"] == 3 and summary["measurement_passes"] == 6, "repetitions")
    require(summary["all_candidate_identities_match"] is True, "candidate identity")
    require(summary["argmax_flips"] == 0 and summary["reserve_policy_rejects"] == 0, "decision outcomes")
    require(claim["gap_aware_full_locked_audit_pass"] is True, "direct full audit")
    require(claim["graph_only_full_locked_audit_pass"] is False, "graph-only audit limitation")
    require(claim["effect_class"] == "LITERAL_EFFECT_ONLY", "effect classification")
    require(claim["latency_superiority_paper_admitted"] is False, "gap-aware superiority gate")
    require(claim["le_net_catalog_latency"] == "BLOCKED_NOT_EVALUATED", "LeNet latency boundary")
    for item in [manifest["protocol"], manifest["orchestration"], manifest["direct_full_audit"], manifest["graph_only_validation"], *manifest["raw_bindings"]]:
        require(sha(repo / item["path"]) == item["sha256"], f"binding {item['path']}")
    with (output / "arm_summary.csv").open(newline="", encoding="utf-8") as handle:
        arms = list(csv.DictReader(handle))
    require(len(arms) == 3 and {row["arm_id"] for row in arms} == {"gap_aware", "graph_only", "catalog"}, "arm summary")
    require(all(int(row["observations"]) == 1800 for row in arms), "arm observations")
    with (output / "pair_summary.csv").open(newline="", encoding="utf-8") as handle:
        pairs = {row["pair_id"]: row for row in csv.DictReader(handle)}
    require(set(pairs) == {"graph_only_over_gap_aware", "catalog_over_gap_aware"}, "pair summary")
    require(int(pairs["graph_only_over_gap_aware"]["raw_pairs"]) == 1800, "graph pairs")
    require(int(pairs["catalog_over_gap_aware"]["raw_pairs"]) == 1800, "catalog pairs")
    require(float(pairs["catalog_over_gap_aware"]["total_ci_low"]) > 1, "catalog/direct CI")
    require(float(pairs["graph_only_over_gap_aware"]["total_ci_low"]) <= 1 <= float(pairs["graph_only_over_gap_aware"]["total_ci_high"]), "graph/direct CI includes one")
    sums = {}
    for line in (output / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        sums[name] = digest
    for path in output.iterdir():
        if path.is_file() and path.name != "SHA256SUMS":
            require(sums.get(path.name) == sha(path).removeprefix("sha256:"), f"checksum {path.name}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    default = Path(__file__).resolve().parent
    if default.name == "scripts":
        default = Path("results/journal_mlp_paired_latency_v1/analysis")
    parser.add_argument("--output", type=Path, default=default)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = verify(args.output, args.repo)
    print(f"journal_mlp_paired_latency=VERIFIED records={result['records']} effect={result['effect_class']}")
