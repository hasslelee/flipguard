#!/usr/bin/env python3
"""Freeze the affc38b journal multiclass extension checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from verify_journal_multiclass_extension_checkpoint_v1 import verify


SCHEMA = "flipguard_journal_multiclass_extension_checkpoint_v1"
SOURCE_COMMIT = "affc38b54f5abed8b491442fbed4b74949c2a05b"
DEFAULT_OUTPUT = Path("docs/evidence/journal_multiclass_extension_checkpoint_v1")
VERIFIER = Path("scripts/verify_journal_multiclass_extension_checkpoint_v1.py")

INPUTS = [
    "docs/evidence/journal_multiclass_extension_v1/protocol_manifest.json",
    "docs/evidence/journal_multiclass_extension_v1/model_architectures.json",
    "docs/evidence/journal_multiclass_extension_v1/input_split_manifest.json",
    "docs/evidence/journal_multiclass_extension_v1/multiclass_contract.json",
    "docs/evidence/journal_multiclass_extension_results_v1/manifest.json",
    "docs/evidence/journal_multiclass_extension_results_v1/summary.json",
    "docs/evidence/journal_multiclass_activation_v1/manifest.json",
    "docs/evidence/journal_multiclass_activation_v1/activation_summary.json",
    "docs/evidence/exact_security_estimator_v1/manifest.json",
    "docs/evidence/exact_security_estimator_v1/summary.json",
    "results/thesis_grade_protocol/journal_extension_paper_inputs_v1/publication_inputs/claim_registry.json",
    "datasets/journal_multiclass_extension_v1/mnist/input_split_manifest.json",
    "datasets/journal_multiclass_extension_v1/mnist/mnist_mlp_square_784_100_10_v1.json",
    "datasets/journal_multiclass_extension_v1/mnist/mnist_lenet5_small_square_v1.json",
]


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def literal(candidate: dict) -> dict:
    parameters = candidate["parameters"]
    return {
        "candidate_id": candidate["id"],
        "path": candidate["path"],
        "log_n": parameters["log_n"],
        "log_q": parameters["log_q"],
        "log_p": parameters["log_p"],
        "log_default_scale": parameters["log_default_scale"],
    }


def build(repo: Path, output: Path) -> None:
    if output.exists():
        raise RuntimeError(f"refusing to overwrite frozen checkpoint: {output}")
    output.mkdir(parents=True)

    results = load(repo / "docs/evidence/journal_multiclass_extension_results_v1/summary.json")
    activation = load(repo / "docs/evidence/journal_multiclass_activation_v1/activation_summary.json")
    mlp_selection = load(
        repo
        / "results/journal_multiclass_extension_v1/encrypted/mnist_mlp_square_784_100_10_v1/selection_result.json"
    )["result"]["selected"]
    lenet_selection = load(
        repo
        / "results/journal_multiclass_extension_v1/encrypted/mnist_lenet5_small_square_v1/selection_result.json"
    )["result"]["selected"]
    graph_only = load(
        repo
        / "results/journal_multiclass_extension_v1/comparators/mlp_graph_only_fixed_logit_tolerance_v1/result.json"
    )["candidate"]
    exact = load(repo / "docs/evidence/exact_security_estimator_v1/summary.json")
    exact_run_statuses = {model["run_status"] for model in exact["models"]}
    if exact_run_statuses != {"FALSIFIED_UNDER_ESTIMATOR_MODEL"}:
        raise RuntimeError("unexpected pre-reconciliation exact-estimator status")

    checkpoint = {
        "schema_version": SCHEMA,
        "checkpoint_id": "JOURNAL_EXTENSION_V1_PRE_SECURITY_RECONCILIATION",
        "source_commit": SOURCE_COMMIT,
        "models": {
            "mlp_100": {
                "model_artifact": {
                    "path": INPUTS[-2],
                    "sha256": digest(repo / INPUTS[-2]),
                },
                "direct_literal": literal(mlp_selection),
                "graph_only_literal": literal(graph_only),
                "validation": results["models"]["mlp_100"]["direct_selection"]["status"],
                "locked_audit": results["models"]["mlp_100"]["locked_audit"]["status"],
                "argmax_flips": 0,
                "catalog_status": "6_SAFE_1_PLAN_UNSUPPORTED_WITHIN_FROZEN_CATALOG",
                "security_policy_v2": "PASS",
            },
            "lenet5_small": {
                "model_artifact": {
                    "path": INPUTS[-1],
                    "sha256": digest(repo / INPUTS[-1]),
                },
                "direct_literal": literal(lenet_selection),
                "validation": results["models"]["lenet5_small"]["direct_selection"]["status"],
                "locked_audit": results["models"]["lenet5_small"]["locked_audit"]["status"],
                "argmax_flips": 0,
                "catalog_status": "PLAN_UNSUPPORTED_WITHIN_FROZEN_CATALOG",
                "security_policy_v2": "PASS",
            },
        },
        "split_manifest": {
            "path": INPUTS[-3],
            "sha256": digest(repo / INPUTS[-3]),
            "encrypted_images": 1000,
            "configuration_validation": 500,
            "locked_audit": 500,
            "overlap": 0,
        },
        "natural_gap_activation": activation["activation_class"],
        "extension_paired_latency": "BLOCKED_NOT_EVALUATED",
        "security_state": {
            "security_policy_v2": "PASS",
            "global_exact_estimator_run_status": exact_run_statuses.pop(),
            "journal_candidate_attribution": "NOT_ESTABLISHED_AT_CHECKPOINT",
            "reconciliation_required": True,
            "preserved_interpretation": (
                "The pre-existing exact-estimator pack reports a global falsification; "
                "candidate-specific journal attribution is unresolved in this checkpoint."
            ),
        },
        "blocked_claims": [
            "exact 128-bit security for journal multiclass candidates",
            "journal extension paired latency",
            "arbitrary packed CNN support",
            "LeNet direct-versus-catalog latency superiority",
        ],
        "frozen_core_modified": False,
        "policy_retuning": 0,
    }
    (output / "checkpoint.json").write_text(canonical(checkpoint), encoding="utf-8")

    verifier_source = repo / VERIFIER
    shutil.copyfile(verifier_source, output / verifier_source.name)
    readme = """# Journal Multiclass Extension Checkpoint V1

This immutable pack binds the complete `affc38b` JOURNAL_EXTENSION_V1 state
before candidate-specific exact-estimator reconciliation. It preserves the
original global estimator failure and does not attribute it to either journal
candidate until the reconciliation overlay establishes that scope.

No encrypted execution or policy retuning was performed while freezing this pack.
"""
    (output / "README.md").write_text(readme, encoding="utf-8")

    bindings = [
        {"path": path, "sha256": digest(repo / path)}
        for path in INPUTS
    ]
    manifest = {
        "schema_version": SCHEMA,
        "source_commit": SOURCE_COMMIT,
        "pre_security_reconciliation": True,
        "checkpoint_sha256": digest(output / "checkpoint.json"),
        "input_bindings": bindings,
        "generated_files": {
            name: {"sha256": digest(output / name)}
            for name in [
                "README.md",
                "checkpoint.json",
                verifier_source.name,
            ]
        },
        "new_encrypted_execution": 0,
        "policy_retuning": 0,
    }
    (output / "manifest.json").write_text(canonical(manifest), encoding="utf-8")
    sums = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            sums.append(
                f"{digest(path).removeprefix('sha256:')}  {path.relative_to(output)}\n"
            )
    (output / "SHA256SUMS").write_text("".join(sums), encoding="utf-8")
    verify(output, repo)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    output = args.output.resolve()
    if args.verify:
        verify(output, repo)
        print("journal_multiclass_extension_checkpoint_v1=VERIFIED")
        return 0
    build(repo, output)
    print(f"journal_multiclass_extension_checkpoint_v1=FROZEN path={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
