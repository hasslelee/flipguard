#!/usr/bin/env python3
"""Freeze the pre-encryption JOURNAL_EXTENSION_V1 multiclass protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


SCHEMA = "flipguard_journal_multiclass_extension_protocol_v1"
SECURITY_ID = "security_guidelines_cic2025_table5_2_ternary_128_v2"
SECURITY_DIGEST = "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
DIRECT_ID = "flipguard_direct_synthesis_policy_v2"
DIRECT_DIGEST = "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
CATALOG_ADMITTED = [
    "deep_chain_8_scale45",
    "deep_chain_9_scale45",
    "short_chain_3",
    "short_chain_5",
    "short_chain_6_scale38",
    "short_chain_6_scale40",
    "short_chain_6_scale42",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: object) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path}")
    path.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def binding(root: Path, path: Path) -> dict:
    return {"path": str(path.relative_to(root)), "sha256": sha256(path)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", required=True)
    parser.add_argument(
        "--output",
        default="docs/evidence/journal_multiclass_extension_v1",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    if head != args.source_commit:
        raise SystemExit(f"source commit {args.source_commit} != HEAD {head}")
    output = root / args.output
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing protocol pack {output}")
    output.mkdir(parents=True)

    data_root = root / "datasets/journal_multiclass_extension_v1/mnist"
    preflight_root = root / "results/journal_multiclass_extension_v1/preflight"
    source = root / "results/source_datasets/mnist/mnist_784.arff.gz"
    split_path = data_root / "input_split_manifest.json"
    model_paths = {
        "mlp_100": data_root / "mnist_mlp_square_784_100_10_v1.json",
        "lenet5_small": data_root / "mnist_lenet5_small_square_v1.json",
    }
    preflight_paths = {
        "mlp_100": preflight_root / "mlp_configuration_validation.json",
        "lenet5_small": preflight_root / "lenet_configuration_validation.json",
    }
    required = [source, split_path, *model_paths.values(), *preflight_paths.values()]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("missing protocol inputs: " + ", ".join(missing))
    models = {name: read_json(path) for name, path in model_paths.items()}
    preflights = {name: read_json(path) for name, path in preflight_paths.items()}
    split = read_json(split_path)
    for name, preflight in preflights.items():
        if preflight["source_commit"] != head:
            raise SystemExit(f"{name} preflight source commit mismatch")
        if preflight["catalog_denominator"] != 7:
            raise SystemExit(f"{name} catalog denominator changed")
        if preflight["contract"]["multiclass_decision"]["schema_version"] != "decision_integrity_contract_v2":
            raise SystemExit(f"{name} multiclass schema changed")

    architecture = {
        "schema_version": SCHEMA,
        "models": {
            name: {
                "artifact": binding(root, model_paths[name]),
                "model_id": model["model_id"],
                "model_type": model["model_type"],
                "graph_adapter_id": model["graph_adapter_id"],
                "graph_formula": model["graph_formula"],
                "architecture": model["architecture"],
                "plaintext_accuracy": model["plaintext_accuracy"],
                "preflight": binding(root, preflight_paths[name]),
                "graph_facts": preflights[name]["contract"]["graph"],
            }
            for name, model in models.items()
        },
        "claim_scope": "FHE-compatible square-activation adapters; not packed/general CNN support",
    }
    training = {
        "schema_version": SCHEMA,
        "official_dataset": binding(root, source),
        "test_used_for_model_selection": False,
        "models": {
            name: {
                "training": model["training"],
                "training_history": model["training_history"],
                "plaintext_accuracy": model["plaintext_accuracy"],
            }
            for name, model in models.items()
        },
    }
    split_overlay = {
        "schema_version": SCHEMA,
        "source_manifest": binding(root, split_path),
        "source": binding(root, source),
        "selection_policy": split["policy_id"],
        "partitions": split["partitions"],
        "class_counts": split["class_counts"],
        "validation_audit_overlap_count": split["validation_audit_overlap_count"],
        "encrypted_scope": {
            "total": 1000,
            "configuration_validation": 500,
            "locked_audit": 500,
            "per_role_per_class": 50,
            "fresh_key_repeats": 3,
        },
        "audit_rebucketing": False,
    }
    contract = {
        "schema_version": "decision_integrity_contract_v2",
        "class_count": 10,
        "plaintext_logits": "z(x)=(z_1,...,z_K)",
        "plaintext_class": "c*=argmax_k z_k with lowest-class-index representation tie break",
        "ckks_logits": "zhat_k=z_k+Delta_k",
        "proposition": "for every j != c*, z_c*(x)-z_j(x) > B_c*(x)+B_j(x) implies argmax_k zhat_k(x)=c*",
        "proof": [
            "For each j != c*, zhat_c* >= z_c*-B_c*.",
            "Also zhat_j <= z_j+B_j.",
            "The strict premise gives z_c*-B_c* > z_j+B_j, hence zhat_c* > zhat_j for every competitor.",
            "Therefore c* is the unique CKKS argmax.",
        ],
        "uniform_bound_corollary": "2B < g(x), where g=z_top1-z_top2",
        "strict_boundary": "equality is rejected because it permits a CKKS tie",
        "tie_handling": "plaintext ties are V_amb; deterministic lowest-index tie break is representation only, not a certificate",
        "non_finite_handling": "NaN and Inf are FAILED",
        "margin_floor": 0.001,
        "margin_utilization_cap": 0.5,
        "interpretation": "predeclared reserve policy; not a theorem constant or optimum",
        "statuses": ["SAFE", "REJECTED", "FAILED", "NO_SAFE"],
    }
    candidate_space = {
        "schema_version": SCHEMA,
        "direct": {
            "maximum_encrypted_trials": 4,
            "first_safe_stopping": True,
            "numerical_repair_scale_bits": 4,
            "level_repair_q_primes": 1,
            "maximum_additional_levels": 2,
        },
        "security_v2_bounded_catalog": {
            "profiles": CATALOG_ADMITTED,
            "paths": ["rescale"],
            "denominator_per_model": 7,
            "global_oracle": False,
        },
        "comparators": [
            "direct_synthesis",
            "security_v2_bounded_catalog",
            "graph_only_fixed_logit_tolerance_0.001",
            "one_shot_direct",
            "latency_only_no_certification",
        ],
        "post_result_expansion": False,
    }
    policy = {
        "schema_version": SCHEMA,
        "security_policy_id": SECURITY_ID,
        "security_policy_digest": SECURITY_DIGEST,
        "direct_policy_id": DIRECT_ID,
        "direct_policy_digest": DIRECT_DIGEST,
        "relationship": "frozen constants reused; new model and packing adapters do not modify Direct Policy V2",
        "packing_adapter": "feature_ciphertext_sample_slots_v1",
        "policy_retuning": 0,
        "core_rc2_v3_v10_modified": False,
    }
    falsification = {
        "schema_version": SCHEMA,
        "hard_fail": [
            "source/model/split/policy/candidate digest mismatch",
            "validation and audit row overlap",
            "Security-V2 inadmissible candidate enters a formal run",
            "test data used for model or hyperparameter selection",
            "audit result changes model, literal, repair, alpha, floor, or trial budget",
            "existing frozen evidence would be overwritten",
        ],
        "scientific_negative_results_preserved": [
            "PLAN_UNSUPPORTED",
            "SECURITY_INADMISSIBLE",
            "NO_SAFE",
            "candidate-trial budget exhaustion",
            "locked-audit argmax flip",
            "reserve-policy rejection",
        ],
        "natural_activation_outcomes": {
            "A_LITERAL_EFFECT_SUPPORTED": "decision-aware and graph-only choose different admitted literals and the top-two-gap budget explains the difference",
            "B_ADMISSION_EFFECT_ONLY": "literal is equal but gate changes admission, coverage, or NO_SAFE",
            "C_NO_OBSERVED_ACTIVATION": "literal and admission are equal",
        },
        "audit_retuning_allowed": False,
    }
    files = {
        "model_architectures.json": architecture,
        "training_protocol.json": training,
        "input_split_manifest.json": split_overlay,
        "multiclass_contract.json": contract,
        "candidate_space.json": candidate_space,
        "policy_binding.json": policy,
        "falsification_rules.json": falsification,
    }
    for name, value in files.items():
        write_json(output / name, value)
    manifest = {
        "schema_version": SCHEMA,
        "source_commit": head,
        "research_scope": "JOURNAL_EXTENSION_V1 overlay",
        "core_predecessor": {
            "tag": "flipguard-thesis-v1.0.0-rc2",
            "commit": "6c5f8b234f9f9da91a189fa0f2dc180bb996abf5",
            "immutable": True,
        },
        "inputs": {
            "source": binding(root, source),
            "split": binding(root, split_path),
            "models": {name: binding(root, path) for name, path in model_paths.items()},
            "preflights": {name: binding(root, path) for name, path in preflight_paths.items()},
        },
        "files": {
            name: {"sha256": sha256(output / name)} for name in sorted(files)
        },
        "new_encrypted_execution_before_freeze": 0,
        "policy_retuning": 0,
        "ready_for_encrypted_execution": True,
    }
    write_json(output / "protocol_manifest.json", manifest)
    checksum_paths = sorted(path for path in output.iterdir() if path.name != "SHA256SUMS")
    lines = [f"{sha256(path).split(':', 1)[1]}  {path.name}" for path in checksum_paths]
    (output / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="ascii")
    print(f"protocol_manifest={sha256(output / 'protocol_manifest.json')}")


if __name__ == "__main__":
    main()
