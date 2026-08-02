#!/usr/bin/env python3
"""Freeze candidate-specific multiclass security reconciliation evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
from pathlib import Path

from verify_journal_multiclass_exact_estimator import verify as verify_estimator
from verify_journal_multiclass_security_reconciliation_v1 import verify


SCHEMA = "flipguard_journal_multiclass_security_reconciliation_v1"
OUTPUT = Path("docs/evidence/journal_multiclass_security_reconciliation_v1")
MATERIALIZATION = Path("results/journal_multiclass_security_reconciliation_v1/materialization.json")
RESULTS = [
    Path("results/journal_multiclass_security_reconciliation_v1/current-3e48ef4.json"),
    Path("results/journal_multiclass_security_reconciliation_v1/guidelines-pinned-8f1ff7e.json"),
]
VERIFIER = Path("scripts/verify_journal_multiclass_security_reconciliation_v1.py")


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def csv_text(fields: list[str], rows: list[dict]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def build(repo: Path, output: Path, source_commit: str) -> None:
    if output.exists():
        raise RuntimeError(f"refusing to overwrite frozen security reconciliation: {output}")
    output.mkdir(parents=True)
    materialization_path = repo / MATERIALIZATION
    materialization = load(materialization_path)
    estimator_results = [verify_estimator(repo / path, materialization_path) for path in RESULTS]

    original_summary = load(repo / "docs/evidence/exact_security_estimator_v1/summary.json")
    original_manifest = load(repo / "docs/evidence/exact_security_estimator_v1/manifest.json")
    with (repo / "docs/evidence/exact_security_estimator_v1/joined_results.csv").open(newline="") as handle:
        original_rows = list(csv.DictReader(handle))
    original_failures = [row for row in original_rows if row["estimator_status"] == "FAIL_ESTIMATOR_MODEL"]
    if len(original_failures) != 2:
        raise RuntimeError("expected one original failed object in each estimator model")
    if any("mnist_" in row["candidate_ids"] for row in original_rows):
        raise RuntimeError("original estimator unexpectedly contains journal candidates")
    if original_summary["source_signature_rows"] != 14:
        raise RuntimeError("unexpected original estimator source scope")

    materialized_by_arm = {
        (row["model_id"], row["arm"]): row for row in materialization["candidates"]
    }
    candidate_rows = []
    object_rows = []
    attack_rows = []
    minimum_by_arm: dict[tuple[str, str], float] = {}
    for result in estimator_results:
        estimator = result["estimator"]
        for candidate in result["candidates"]:
            key = (candidate["model_id"], candidate["arm"])
            source = materialized_by_arm[key]
            minimum = float(candidate["minimum_log2_rop"])
            minimum_by_arm[key] = min(minimum_by_arm.get(key, minimum), minimum)
            candidate_rows.append(
                {
                    "estimator_model": estimator["model_id"],
                    "estimator_commit": estimator["git_commit"],
                    "model_id": candidate["model_id"],
                    "arm": candidate["arm"],
                    "candidate_id": candidate["candidate_id"],
                    "log_n": source["parameters"]["log_n"],
                    "actual_log_q": format(source["actual_log_q"], ".16g"),
                    "actual_log_p": format(source["actual_log_p"], ".16g"),
                    "actual_log_qp": format(source["actual_log_qp"], ".16g"),
                    "security_v2_cap": source["security_policy_v2"]["max_allowed_log_qp"],
                    "security_v2_headroom": source["security_policy_v2"]["headroom_bits"],
                    "minimum_log2_rop": format(minimum, ".16g"),
                    "final_status": candidate["final_status"],
                }
            )
            for obj in candidate["objects"]:
                object_rows.append(
                    {
                        "estimator_model": estimator["model_id"],
                        "model_id": candidate["model_id"],
                        "arm": candidate["arm"],
                        "candidate_id": candidate["candidate_id"],
                        "object_type": obj["object_type"],
                        "exact_modulus_bit_length": obj["exact_modulus_bit_length"],
                        "exact_log2_modulus": obj["exact_log2_modulus"],
                        "minimum_log2_rop": obj["minimum_log2_rop"],
                        "status": obj["status"],
                    }
                )
                for attack in obj["attacks"]:
                    attack_rows.append(
                        {
                            "estimator_model": estimator["model_id"],
                            "model_id": candidate["model_id"],
                            "arm": candidate["arm"],
                            "candidate_id": candidate["candidate_id"],
                            "object_type": obj["object_type"],
                            "attack": attack["attack"],
                            "attack_status": attack["status"],
                            "log2_rop": attack["log2_rop"],
                            "beta": attack.get("beta", ""),
                            "dimension": attack.get("dimension", ""),
                            "samples": attack.get("samples", ""),
                        }
                    )

    direct_mlp = materialized_by_arm[("mnist_mlp_square_784_100_10_v1", "gap_aware_direct")]
    direct_lenet = materialized_by_arm[("mnist_lenet5_small_square_v1", "gap_aware_direct")]
    summary = {
        "schema_version": SCHEMA,
        "classification": "CLASS_S1_ESTIMATOR_ADAPTER_MISMATCH",
        "root_cause": "RESULT_SCOPE_AND_AGGREGATION_MISMATCH",
        "root_cause_detail": (
            "The pre-existing exact-estimator run consumed 14 pre-journal core rows. Its global run status was "
            "falsified by a Security-V2-inadmissible N14/QP441 catalog identity, while the journal candidates were "
            "absent. That global status was incorrectly attributed to MLP-100 and LeNet-5-small."
        ),
        "original_estimator": {
            "manifest_sha256": digest(repo / "docs/evidence/exact_security_estimator_v1/manifest.json"),
            "source_rows": original_summary["source_signature_rows"],
            "unique_modulus_identities": original_summary["unique_modulus_identities"],
            "global_status": [model["run_status"] for model in original_summary["models"]],
            "failed_objects": original_failures,
            "static_admitted_estimator_failures": [
                model["static_admitted_estimator_failures"] for model in original_summary["models"]
            ],
            "paper_claim_allowed": original_manifest["paper_claim_allowed"],
        },
        "original_estimator_input_journal_candidates": 0,
        "corrected_static_replay": {
            "candidate_count": 4,
            "estimator_models": [result["estimator"]["model_id"] for result in estimator_results],
            "q_objects": 4,
            "qp_objects": 4,
            "attacks_per_model": 24,
            "attack_failures": 0,
            "candidate_failures": 0,
        },
        "models": {
            "mlp_100": {
                "candidate_id": direct_mlp["candidate_id"],
                "literal": direct_mlp["parameters"],
                "exact_q_primes": direct_mlp["exact_q_primes"],
                "exact_p_primes": direct_mlp["exact_p_primes"],
                "actual_log_q": direct_mlp["actual_log_q"],
                "actual_log_p": direct_mlp["actual_log_p"],
                "actual_log_qp": direct_mlp["actual_log_qp"],
                "security_policy_v2": direct_mlp["security_policy_v2"],
                "minimum_classical_bits": minimum_by_arm[(direct_mlp["model_id"], direct_mlp["arm"])],
                "final_security_state": "SECURITY_CORRECTED_AND_REPLAYED",
            },
            "lenet5_small": {
                "candidate_id": direct_lenet["candidate_id"],
                "literal": direct_lenet["parameters"],
                "exact_q_primes": direct_lenet["exact_q_primes"],
                "exact_p_primes": direct_lenet["exact_p_primes"],
                "actual_log_q": direct_lenet["actual_log_q"],
                "actual_log_p": direct_lenet["actual_log_p"],
                "actual_log_qp": direct_lenet["actual_log_qp"],
                "security_policy_v2": direct_lenet["security_policy_v2"],
                "minimum_classical_bits": minimum_by_arm[(direct_lenet["model_id"], direct_lenet["arm"])],
                "final_security_state": "SECURITY_CORRECTED_AND_REPLAYED",
            },
        },
        "paired_arms": {
            "gap_aware_direct_minimum_bits": minimum_by_arm[("mnist_mlp_square_784_100_10_v1", "gap_aware_direct")],
            "graph_only_minimum_bits": minimum_by_arm[("mnist_mlp_square_784_100_10_v1", "graph_only_fixed_tolerance")],
            "catalog_minimum_bits": minimum_by_arm[("mnist_mlp_square_784_100_10_v1", "bounded_catalog_fastest_safe")],
            "all_pass": True,
        },
        "distribution_caveat": {
            "xs": "runtime ring.Ternary P=2/3 maps exactly to estimator ND.Uniform(-1,1)",
            "xe": "runtime ring.DiscreteGaussian sigma=3.2 bound=19.2 maps to untruncated estimator ND.DiscreteGaussian(3.2)",
            "exact_distribution_claim_allowed": False,
            "quantum_cost_model": "NOT_EVALUATED",
        },
        "security_amendment_required": False,
        "encrypted_replay_required": False,
        "policy_retuning": 0,
        "literal_changes": 0,
        "allowed_security_wording": (
            "The journal candidates pass Security Policy V2 and both declared classical estimator models using "
            "exact materialized Q and QP; the Lattigo error truncation is not modeled exactly."
        ),
        "prohibited_security_wording": [
            "universal 128-bit security",
            "exact runtime-distribution equivalence",
            "quantum 128-bit security",
        ],
    }
    (output / "reconciliation.json").write_text(canonical(summary), encoding="utf-8")
    (output / "materialized_candidates.json").write_text(canonical(materialization), encoding="utf-8")
    (output / "candidate_security_summary.csv").write_text(
        csv_text(list(candidate_rows[0]), candidate_rows), encoding="utf-8"
    )
    (output / "object_security_summary.csv").write_text(
        csv_text(list(object_rows[0]), object_rows), encoding="utf-8"
    )
    (output / "attack_results.csv").write_text(
        csv_text(list(attack_rows[0]), attack_rows), encoding="utf-8"
    )
    shutil.copyfile(repo / VERIFIER, output / VERIFIER.name)
    (output / "README.md").write_text(
        "# Journal Multiclass Security Reconciliation V1\n\n"
        "Candidate-specific exact-Q/P static replay for the frozen MLP-100, graph-only, catalog, and LeNet arms. "
        "The pack preserves the original global failure while correcting its journal-candidate attribution.\n",
        encoding="utf-8",
    )

    inputs = [
        MATERIALIZATION,
        *RESULTS,
        Path("docs/evidence/exact_security_estimator_v1/manifest.json"),
        Path("docs/evidence/exact_security_estimator_v1/summary.json"),
        Path("docs/evidence/exact_security_estimator_v1/joined_results.csv"),
        Path("docs/evidence/journal_multiclass_extension_checkpoint_v1/manifest.json"),
    ]
    manifest = {
        "schema_version": SCHEMA,
        "source_commit": source_commit,
        "classification": summary["classification"],
        "materialization": {"path": MATERIALIZATION.as_posix(), "sha256": digest(repo / MATERIALIZATION)},
        "estimator_results": [
            {"path": path.as_posix(), "sha256": digest(repo / path)} for path in RESULTS
        ],
        "input_bindings": [
            {"path": path.as_posix(), "sha256": digest(repo / path)} for path in inputs
        ],
        "generated_files": {},
        "security_amendment_required": False,
        "encrypted_replay_required": False,
        "policy_retuning": 0,
    }
    generated = [
        "README.md",
        "reconciliation.json",
        "materialized_candidates.json",
        "candidate_security_summary.csv",
        "object_security_summary.csv",
        "attack_results.csv",
        VERIFIER.name,
    ]
    manifest["generated_files"] = {
        name: {"sha256": digest(output / name)} for name in generated
    }
    (output / "manifest.json").write_text(canonical(manifest), encoding="utf-8")
    sums = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            sums.append(f"{digest(path).removeprefix('sha256:')}  {path.relative_to(output)}\n")
    (output / "SHA256SUMS").write_text("".join(sums), encoding="utf-8")
    verify(output, repo)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    output = args.output.resolve()
    if args.verify:
        verify(output, repo)
        print("journal_multiclass_security_reconciliation_v1=VERIFIED")
        return 0
    build(repo, output, args.source_commit)
    print(f"journal_multiclass_security_reconciliation_v1=FROZEN path={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
