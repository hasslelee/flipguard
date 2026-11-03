#!/usr/bin/env python3
"""Build a static, fail-closed inventory for conditional analytical V2."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "results/thesis_grade_protocol/"
    "conditional_analytical_readiness_v2"
)
DEVELOPMENT_SELECTIONS = (
    REPO_ROOT
    / "docs/evidence/direct_locked_audit_seed0_development_v1/"
    "inputs/selections"
)
CONFIRMATORY_SELECTIONS = (
    REPO_ROOT
    / "docs/evidence/direct_locked_audit_final_source_v1/"
    "inputs/selections"
)
DEVELOPMENT_MANIFEST = (
    REPO_ROOT
    / "docs/evidence/direct_locked_audit_seed0_development_v1/manifest.json"
)
CONFIRMATORY_MANIFEST = (
    REPO_ROOT
    / "docs/evidence/direct_locked_audit_final_source_v1/manifest.json"
)
DERIVATION_SOURCE = (
    REPO_ROOT / "research/analyticalv2/derivation.go"
)
DERIVATION_TEST = (
    REPO_ROOT / "research/analyticalv2/derivation_test.go"
)

PRIMITIVE_GAPS = (
    (
        "input_encode_encrypt",
        "input",
        "absolute decoded-slot error after encode and public-key encrypt",
    ),
    (
        "model_scalar_encoding",
        "mul_model_scalar",
        "absolute encoded coefficient error and multiply residual",
    ),
    (
        "fixed_scalar_encoding",
        "mul_fixed_scalar",
        "absolute encoded fixed-coefficient error and multiply residual",
    ),
    (
        "plaintext_encoding_at_level",
        "encode_plaintext_at_level",
        "absolute encoding error at the concrete level and scale",
    ),
    (
        "ciphertext_addition",
        "add_ciphertexts",
        "absolute residual, including a justification when exactly zero",
    ),
    (
        "ciphertext_plaintext_addition",
        "add_ciphertext_plaintext",
        "absolute residual, including level and scale preconditions",
    ),
    (
        "ciphertext_multiplication",
        "mul_ciphertexts",
        "absolute multiplication residual beyond operand uncertainty",
    ),
    (
        "relinearization",
        "relinearize",
        "absolute key-switching residual for the exact Q/P decomposition",
    ),
    (
        "rescale",
        "rescale_to_default",
        "absolute RNS rounding and scale-adjustment residual",
    ),
    (
        "level_alignment",
        "align_level_to",
        "absolute modulus-drop or alignment residual",
    ),
)


def sha256_path(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    ).encode("ascii")


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(canonical_json(value))


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def literal_signature(selected: dict[str, Any]) -> str:
    parameters = selected["parameters"]
    value = {
        "path": selected["path"],
        "log_n": parameters["log_n"],
        "log_q": parameters["log_q"],
        "log_p": parameters["log_p"],
        "log_default_scale": parameters["log_default_scale"],
    }
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def selection_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sources = (
        ("development_seed0", DEVELOPMENT_SELECTIONS),
        ("confirmatory_seeds1_4", CONFIRMATORY_SELECTIONS),
    )
    for role, root in sources:
        paths = sorted(root.glob("*.json"))
        expected = 10 if role == "development_seed0" else 40
        if len(paths) != expected:
            raise ValueError(
                f"{role} selection count {len(paths)} != {expected}"
            )
        for path in paths:
            record = json.loads(path.read_text(encoding="ascii"))
            if record["outcome"] != "SELECTED":
                raise ValueError(
                    f"{path}: expected SELECTED, got {record['outcome']}"
                )
            contract = record["plan"]["contract"]
            selected = record["selected"]
            model_type = contract["model_type"]
            graph_supported = model_type == "linear_poly3"

            blockers = [
                "NO_SCOPED_ABSOLUTE_INPUT_ENCRYPTION_BOUND",
                "NO_SCOPED_ABSOLUTE_PLAINTEXT_ENCODING_BOUND",
                "NO_SCOPED_ABSOLUTE_MULTIPLY_RELINEARIZE_RESCALE_BOUND",
                "OBSERVED_VS_BOUND_AUDIT_NOT_RUN",
            ]
            if not graph_supported:
                blockers.insert(
                    0,
                    "MODEL_OPERATION_GRAPH_NOT_IMPLEMENTED_IN_ANALYTICAL_V2",
                )

            rows.append(
                {
                    "role": role,
                    "workload_id": contract["workload_id"],
                    "dataset_id": contract["dataset_id"],
                    "model_type": model_type,
                    "candidate_id": selected["id"],
                    "path": selected["path"],
                    "literal_signature": literal_signature(selected),
                    "security_admission": selected["security"][
                        "final_admission"
                    ],
                    "graph_contract_supported": graph_supported,
                    "primitive_bounds_complete": False,
                    "proof_eligible": False,
                    "observed_vs_bound_audit": "NOT_RUN_NO_BOUND",
                    "analytical_claim_state": "BLOCKED",
                    "block_reasons": ";".join(blockers),
                    "selection_sha256": sha256_path(path),
                }
            )
    rows.sort(key=lambda row: (row["role"], row["workload_id"]))
    return rows


def write_csv(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, Any]],
) -> None:
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build(output: Path, source_commit: str) -> None:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    rows = selection_rows()
    development = [
        row for row in rows if row["role"] == "development_seed0"
    ]
    confirmatory = [
        row for row in rows if row["role"] == "confirmatory_seeds1_4"
    ]
    linear = [
        row for row in rows if row["model_type"] == "linear_poly3"
    ]
    mlp = [
        row
        for row in rows
        if row["model_type"] == "mlp_square_linear_score"
    ]

    summary = {
        "schema_version": "flipguard_conditional_analytical_readiness_v2",
        "source_commit": source_commit,
        "derivation_source": {
            "path": str(DERIVATION_SOURCE.relative_to(REPO_ROOT)),
            "sha256": sha256_path(DERIVATION_SOURCE),
        },
        "derivation_test": {
            "path": str(DERIVATION_TEST.relative_to(REPO_ROOT)),
            "sha256": sha256_path(DERIVATION_TEST),
            "fixed_seed_property_cases": 2000,
        },
        "bound_inputs": {
            "development_manifest": {
                "path": str(DEVELOPMENT_MANIFEST.relative_to(REPO_ROOT)),
                "sha256": sha256_path(DEVELOPMENT_MANIFEST),
            },
            "confirmatory_manifest": {
                "path": str(CONFIRMATORY_MANIFEST.relative_to(REPO_ROOT)),
                "sha256": sha256_path(CONFIRMATORY_MANIFEST),
            },
        },
        "primary_candidates": len(rows),
        "development_seed0_candidates": len(development),
        "confirmatory_seeds1_4_candidates": len(confirmatory),
        "linear_poly3_candidates": len(linear),
        "mlp_square_linear_score_candidates": len(mlp),
        "graph_contract_supported_candidates": sum(
            int(row["graph_contract_supported"]) for row in rows
        ),
        "primitive_bound_complete_candidates": 0,
        "proof_eligible_candidates": 0,
        "observed_vs_bound_audits_completed": 0,
        "conditional_propagation_lemma": "SUPPORTED",
        "instantiated_ckks_analytical_certificate": "BLOCKED",
        "paper_claim_allowed": False,
        "block_reason": (
            "No selected candidate has a scoped absolute derivation for "
            "input encryption, plaintext encoding, multiplication, "
            "relinearization, and rescale residuals; MLP graph propagation "
            "is also not implemented."
        ),
        "encrypted_executions": 0,
        "policy_modifications": 0,
    }
    write_json(output / "summary.json", summary)

    candidate_fields = [
        "role",
        "workload_id",
        "dataset_id",
        "model_type",
        "candidate_id",
        "path",
        "literal_signature",
        "security_admission",
        "graph_contract_supported",
        "primitive_bounds_complete",
        "proof_eligible",
        "observed_vs_bound_audit",
        "analytical_claim_state",
        "block_reasons",
        "selection_sha256",
    ]
    write_csv(
        output / "candidate_readiness.csv",
        candidate_fields,
        rows,
    )

    gap_rows = [
        {
            "primitive_id": primitive_id,
            "operation": operation,
            "required_derivation": required,
            "current_status": "MISSING",
            "diagnostic_substitution_allowed": "false",
            "blocks_instantiated_certificate": "true",
        }
        for primitive_id, operation, required in PRIMITIVE_GAPS
    ]
    write_csv(
        output / "primitive_gap_matrix.csv",
        list(gap_rows[0].keys()),
        gap_rows,
    )

    summary_md = f"""# Conditional Analytical V2 Readiness

- primary selected candidates: {len(rows)}
- development seed 0: {len(development)}
- confirmatory seeds 1-4: {len(confirmatory)}
- `linear_poly3`: {len(linear)}; graph contract implemented
- `mlp_square_linear_score`: {len(mlp)}; graph contract missing
- complete primitive-bound derivations: 0/{len(rows)}
- proof-eligible candidates: 0/{len(rows)}
- observed-versus-bound audits: 0/{len(rows)}
- encrypted executions in this audit: 0

## Claim States

- conditional outward-rounded propagation lemma: `SUPPORTED`
- instantiated CKKS analytical certificate: `BLOCKED`

The V2 engine requires a digest-bound absolute source at every graph node.
Empirical maxima and standard deviations are diagnostic-only and cannot
produce proof metadata. No current candidate is promoted from observed
decision evidence to analytical evidence.
"""
    (output / "summary.md").write_text(
        summary_md,
        encoding="ascii",
    )

    checksums = []
    for path in sorted(output.iterdir()):
        if path.name == "SHA256SUMS":
            continue
        checksums.append(
            f"{sha256_path(path).removeprefix('sha256:')}  {path.name}\n"
        )
    (output / "SHA256SUMS").write_text(
        "".join(checksums),
        encoding="ascii",
    )


def compare_trees(expected: Path, actual: Path) -> None:
    expected_files = sorted(
        path.relative_to(expected)
        for path in expected.rglob("*")
        if path.is_file()
    )
    actual_files = sorted(
        path.relative_to(actual)
        for path in actual.rglob("*")
        if path.is_file()
    )
    if expected_files != actual_files:
        raise ValueError("readiness artifact file set changed")
    for relative in expected_files:
        if (expected / relative).read_bytes() != (
            actual / relative
        ).read_bytes():
            raise ValueError(
                f"readiness artifact content changed: {relative}"
            )


def verify_existing(output: Path) -> None:
    summary = json.loads(
        (output / "summary.json").read_text(encoding="ascii")
    )
    with tempfile.TemporaryDirectory(
        prefix="flipguard-analytical-readiness-",
        dir="/tmp",
    ) as temporary:
        rebuilt = Path(temporary) / "rebuilt"
        build(rebuilt, summary["source_commit"])
        compare_trees(output, rebuilt)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument("--source-commit")
    parser.add_argument(
        "--verify-existing",
        action="store_true",
    )
    args = parser.parse_args()

    output = args.output
    if not output.is_absolute():
        output = REPO_ROOT / output

    if args.verify_existing:
        verify_existing(output)
        print("conditional_analytical_readiness_v2=VERIFIED")
        return

    build(
        output,
        args.source_commit or git_head(),
    )
    print(
        "conditional_analytical_readiness_v2=BUILT "
        f"output={output}"
    )


if __name__ == "__main__":
    main()
