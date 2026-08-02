#!/usr/bin/env python3
"""Freeze the focused MLP-100 paired-latency amendment before execution."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
from pathlib import Path

from verify_journal_mlp_paired_latency_protocol_v1 import (
    SCHEMA,
    critical_digest,
    expected_rows,
    sha,
    verify,
)


DEFAULT_OUTPUT = Path("docs/evidence/journal_mlp_paired_latency_protocol_v1")
BINARY = Path("results/journal_mlp_paired_latency_v1/bin/flipguard-journal-mlp-paired-latency")
MODEL = Path("datasets/journal_multiclass_extension_v1/mnist/mnist_mlp_square_784_100_10_v1.json")
AUDIT = Path("datasets/journal_multiclass_extension_v1/mnist/locked_audit.csv")
SELECTION = Path("results/journal_multiclass_extension_v1/encrypted/mnist_mlp_square_784_100_10_v1/selection_result.json")
GRAPH_ONLY = Path("results/journal_multiclass_extension_v1/comparators/mlp_graph_only_fixed_logit_tolerance_v1/result.json")
CATALOG = Path("results/journal_multiclass_extension_v1/encrypted/mnist_mlp_square_784_100_10_v1/catalog_result.json")
RECONCILIATION = Path("docs/evidence/journal_multiclass_security_reconciliation_v1/manifest.json")
VERIFIER = Path("scripts/verify_journal_mlp_paired_latency_protocol_v1.py")


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def binding(repo: Path, path: Path) -> dict:
    return {"path": str(path), "sha256": sha(repo / path)}


def build(
    repo: Path,
    output: Path,
    source_commit: str,
    binary_relative: Path = BINARY,
    protocol_id: str = "journal_mlp100_paired_latency_amendment_v1",
) -> None:
    if output.exists():
        raise RuntimeError(f"refusing to overwrite frozen protocol: {output}")
    if len(source_commit) != 40:
        raise RuntimeError("full execution source commit is required")
    binary_path = repo / binary_relative
    if not binary_path.exists():
        raise RuntimeError(f"frozen binary is missing: {binary_path}")

    selection = load(repo / SELECTION)["result"]["selected"]
    graph_only = load(repo / GRAPH_ONLY)["candidate"]
    catalog_result = load(repo / CATALOG)
    if catalog_result["fastest_safe_profile"] != "short_chain_5":
        raise RuntimeError("frozen fastest-safe catalog arm changed")
    catalog_entry = next(
        entry for entry in catalog_result["entries"]
        if entry["static"]["profile_name"] == catalog_result["fastest_safe_profile"]
    )
    if catalog_entry["trial"]["status"] != "SAFE":
        raise RuntimeError("frozen catalog arm is not SAFE")
    catalog = catalog_entry["static"]["candidate"]
    candidate_ids = [selection["id"], graph_only["id"], catalog["id"]]
    if "_S29_" not in candidate_ids[0] or "_S32_" not in candidate_ids[1]:
        raise RuntimeError("frozen S29/S32 arm identities changed")
    rows = expected_rows(repo / AUDIT)

    output.mkdir(parents=True)
    protocol = {
        "schema_version": SCHEMA,
        "protocol_id": protocol_id,
        "execution_source_commit": source_commit,
        "execution_critical_source_digest": critical_digest(repo),
        "frozen_binary_sha256": sha(binary_path),
        "model": binding(repo, MODEL),
        "locked_audit": binding(repo, AUDIT),
        "security_reconciliation": binding(repo, RECONCILIATION),
        "selected_rows": rows,
        "selection_rule": "SHA-256 class-stratified rank; 10 locked-audit images per class",
        "selection_rank_domain": "journal_mlp100_paired_latency_subset_v1",
        "fresh_keysets": 3,
        "warmup_runs": 1,
        "measurement_runs": 6,
        "margin_floor": 0.001,
        "margin_utilization_cap": 0.5,
        "concurrent_ckks_processes": 0,
        "outlier_removal": False,
        "image_order": "identical frozen selected_rows order within every keyset/pass block",
        "arm_order": "balanced_cyclic_and_reverse_image_rotated_v1",
        "process_restart_policy": "one new process per fresh keyset; preserve failed attempts",
        "measurement_unit": "single-image encrypted inference",
        "expected_measurement_records": 100 * 3 * 3 * 6,
        "arms": [
            {
                "id": "gap_aware", "role": "natural_top_two_gap_direct",
                "candidate": selection, "profile_source": "synthesized_literal",
                "source": binding(repo, SELECTION),
            },
            {
                "id": "graph_only", "role": "graph_only_fixed_logit_tolerance",
                "candidate": graph_only, "profile_source": "synthesized_literal",
                "source": binding(repo, GRAPH_ONLY),
            },
            {
                "id": "catalog", "role": "security_v2_bounded_catalog_fastest_safe",
                "candidate": catalog, "profile_source": "builtin_catalog_concrete_literal",
                "profile_name": "short_chain_5", "source": binding(repo, CATALOG),
            },
        ],
    }
    (output / "execution_protocol.json").write_text(canonical(protocol), encoding="utf-8")
    subset = {
        "schema_version": SCHEMA,
        "source_role": "locked_audit",
        "source": binding(repo, AUDIT),
        "rank_domain": protocol["selection_rank_domain"],
        "selection_rule": protocol["selection_rule"],
        "selected_images": 100,
        "per_class": 10,
        "decision_integrity_audit_population_unchanged": 500,
        "rows": rows,
    }
    (output / "latency_subset_manifest.json").write_text(canonical(subset), encoding="utf-8")
    (output / "analysis_plan.json").write_text(canonical({
        "schema_version": SCHEMA,
        "primary_pairs": [
            {"numerator": "graph_only", "denominator": "gap_aware", "metrics": ["total_ms", "evaluation_only_ms"]},
            {"numerator": "catalog", "denominator": "gap_aware", "metrics": ["total_ms", "evaluation_only_ms"]},
        ],
        "summary": ["mean", "median", "p95", "standard_deviation", "IQR", "within_image_CV", "arm_position_effect"],
        "confidence_interval": "deterministic class-stratified image-cluster bootstrap 95% CI",
        "bootstrap_seed": 20260802,
        "bootstrap_repetitions": 10000,
        "latency_effect_supported": "different literals; both full locked audits PASS; total ratio CI lower bound > 1",
        "literal_effect_only": "different literals but total ratio CI includes 1 or effect is negligible",
        "no_observed_effect": "literal or latency difference is not reproduced",
        "raw_measurements_are_not_independent": True,
    }), encoding="utf-8")
    (output / "falsification_rules.json").write_text(canonical({
        "schema_version": SCHEMA,
        "no_posthoc_arm_change": True,
        "no_posthoc_sample_change": True,
        "no_posthoc_pass_change": True,
        "no_outlier_removal": True,
        "individual_failure_policy": "preserve and report; complete independent observations when integrity is intact",
        "security_gate": "all arms require Security-V2 PASS and matched estimator PASS before execution",
        "le_net_catalog_latency_claim": "BLOCKED_NOT_EVALUATED",
    }), encoding="utf-8")
    shutil.copyfile(repo / VERIFIER, output / VERIFIER.name)
    (output / "README.md").write_text(
        "# Focused MLP-100 Paired Latency Protocol V1\n\n"
        "This immutable pre-execution pack freezes the S29 gap-aware, S32 graph-only, and "
        "Security-V2 bounded-catalog fastest-safe arms. Every selected image is a real timed "
        "encrypted inference; a packed-batch latency is never copied across image rows.\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": SCHEMA,
        "protocol_id": protocol["protocol_id"],
        "execution_source_commit": source_commit,
        "execution_protocol_sha256": sha(output / "execution_protocol.json"),
        "latency_subset_manifest_sha256": sha(output / "latency_subset_manifest.json"),
        "frozen_binary": binding(repo, binary_relative),
        "host_preflight": {
            "hostname": platform.node(), "system": platform.system(),
            "release": platform.release(), "machine": platform.machine(),
            "logical_cpus": os.cpu_count(),
        },
        "security_reconciliation_class": "CLASS_S1_ESTIMATOR_ADAPTER_MISMATCH",
        "security_amendment": False,
        "policy_retuning": 0,
        "new_dataset_or_model": 0,
    }
    if protocol_id.endswith("_v1_1"):
        manifest["predecessor"] = {
            "path": "docs/evidence/journal_mlp_paired_latency_protocol_v1",
            "status": "PRESERVED_RECOVERABLE_IMPLEMENTATION_FAILURE",
            "reason": "strict parser omitted declared analysis metadata; encrypted measurement records=0",
        }
    elif protocol_id.endswith("_v1_2"):
        manifest["predecessor"] = {
            "path": "docs/evidence/journal_mlp_paired_latency_protocol_v1_1",
            "status": "PRESERVED_RECOVERABLE_IMPLEMENTATION_FAILURE",
            "reason": "copied verifier did not default to its own pack; encrypted measurement records=0",
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
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--binary", type=Path, default=BINARY)
    parser.add_argument(
        "--protocol-id",
        default="journal_mlp100_paired_latency_amendment_v1",
    )
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    output = args.output.resolve()
    if args.verify:
        protocol = verify(output, repo)
        print(f"journal_mlp_paired_latency_protocol=VERIFIED rows={len(protocol['selected_rows'])}")
    else:
        build(repo, output, args.source_commit, args.binary, args.protocol_id)
        print(f"journal_mlp_paired_latency_protocol=FROZEN output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
