#!/usr/bin/env python3
"""Build the 50-instance direct/catalog validation identity audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_DIRECT_ROOT = Path(
    "results/thesis_grade_protocol/direct_tabular_autotune_v1/"
    "full_final_baseline_inputmodel_floor18_keys3/summary"
)
DEFAULT_ORACLE_ROOT = Path(
    "results/thesis_grade_protocol/security_v2_static_attestation/"
    "bounded_oracle_security_v2"
)
DEFAULT_OUTPUT_ROOT = Path(
    "results/thesis_grade_protocol/validation_identity_audit_v2"
)
DEFAULT_IDENTITY_BINARY = Path("bin/flipguard-validation-identity")
EXECUTION_SOURCE_COMMIT = "ebbdcb0112ea6dfeb6115239cba812e4d2707650"
FAILURE_REASON_CODE = "VALIDATION_IDENTITY_UNRESOLVED_FAIL_CLOSED"
DIRECT_EVIDENCE_MANIFEST = Path(
    "docs/evidence/direct_locked_audit_final_source_v1/manifest.json"
)
DEVELOPMENT_EVIDENCE_MANIFEST = Path(
    "docs/evidence/direct_locked_audit_seed0_development_v1/manifest.json"
)
KEY_FIELDS = ("split_seed", "dataset_id", "model_id")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--direct-root", type=Path, default=DEFAULT_DIRECT_ROOT)
    parser.add_argument("--oracle-root", type=Path, default=DEFAULT_ORACLE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--identity-binary",
        type=Path,
        default=DEFAULT_IDENTITY_BINARY,
    )
    parser.add_argument(
        "--execution-source-commit",
        default=EXECUTION_SOURCE_COMMIT,
    )
    parser.add_argument("--comparison-builder-commit", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path, prefix: bool = True) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    value = digest.hexdigest()
    return f"sha256:{value}" if prefix else value


def canonical_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected an object")
    return value


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"{path}: missing header")
        return list(reader)


def key(row: dict[str, str]) -> tuple[int, str, str]:
    return (
        int(row["split_seed"]),
        row["dataset_id"],
        row["model_id"],
    )


def index_unique(
    rows: list[dict[str, str]],
    label: str,
) -> dict[tuple[int, str, str], dict[str, str]]:
    result: dict[tuple[int, str, str], dict[str, str]] = {}
    for row in rows:
        row_key = key(row)
        if row_key in result:
            raise ValueError(f"{label}: duplicate workload {row_key}")
        result[row_key] = row
    return result


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def run_identity(
    binary: Path,
    *,
    model_path: str,
    validation_path: str,
    dataset_id: str,
    model_id: str,
    split_id: str,
    partition_role: str,
    margin_floor: float,
) -> dict[str, Any]:
    command = [
        str(binary.resolve()),
        "--model",
        model_path,
        "--validation",
        validation_path,
        "--dataset-id",
        dataset_id,
        "--model-id",
        model_id,
        "--split-id",
        split_id,
        "--partition-role",
        partition_role,
        "--margin-floor",
        format(margin_floor, ".17g"),
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise ValueError("identity binary returned a non-object")
    return value


def classify(
    *,
    source_raw_match: bool,
    prepared_raw_match: bool,
    ordered_row_ids_match: bool,
    feature_semantics_match: bool,
    decision_semantics_match: bool,
    policy_match: bool,
    split_match: bool,
) -> tuple[str, bool, str]:
    if not split_match:
        return (
            "WRONG_SPLIT_OR_MANIFEST",
            True,
            "split or manifest binding differs",
        )
    if (
        not feature_semantics_match
        or not decision_semantics_match
        or not policy_match
    ):
        return (
            "SEMANTIC_MISMATCH",
            True,
            "feature, decision, model, threshold, coverage, or policy differs",
        )
    if not ordered_row_ids_match:
        return (
            "ROW_ORDER_ONLY_MISMATCH",
            True,
            "row set may match but ordered row identity differs",
        )
    if source_raw_match and not prepared_raw_match:
        return (
            "SOURCE_AND_SEMANTICS_MATCH_PREPARED_BYTES_DIFFER",
            False,
            "source bytes and execution semantics match; deterministic "
            "prepared representation adds provenance/full-precision fields",
        )
    if not source_raw_match:
        return (
            "SOURCE_DIFFERS_SEMANTICS_MATCH",
            False,
            "source bytes differ but ordered execution semantics match",
        )
    return (
        "EXACT_SOURCE_AND_PREPARED_IDENTITY_MATCH",
        False,
        "source, prepared, and canonical semantics match",
    )


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def make_row(
    direct: dict[str, str],
    coverage: dict[str, str],
    direct_result: dict[str, Any],
    source_identity: dict[str, Any],
    prepared_identity: dict[str, Any],
    catalog_identity: dict[str, Any],
) -> tuple[dict[str, str], dict[str, Any]]:
    plan = direct_result["plan"]
    contract = plan["contract"]
    decision = contract["decision"]
    materialization = contract["input_materialization"]
    split_manifest = Path(coverage["split_manifest"])
    split_manifest_value = load_json(split_manifest)

    source_binding = contract["source_data"]
    prepared_binding = contract["validation_data"]
    model_binding = contract["model_artifact"]
    source_raw_match = (
        source_identity["file"]["raw_sha256"]
        == catalog_identity["file"]["raw_sha256"]
        == source_binding["sha256"]
        == coverage["validation_csv_digest"]
    )
    prepared_raw_match = (
        prepared_identity["file"]["raw_sha256"]
        == catalog_identity["file"]["raw_sha256"]
    )
    ordered_row_ids_match = (
        source_identity["file"]["ordered_row_id_digest"]
        == prepared_identity["file"]["ordered_row_id_digest"]
        == catalog_identity["file"]["ordered_row_id_digest"]
    )
    feature_semantics_match = (
        source_identity["feature_semantic_digest"]
        == prepared_identity["feature_semantic_digest"]
        == catalog_identity["feature_semantic_digest"]
    )
    decision_semantics_match = (
        source_identity["decision_semantic_digest"]
        == prepared_identity["decision_semantic_digest"]
        == catalog_identity["decision_semantic_digest"]
    )
    policy_match = (
        model_binding["sha256"]
        == coverage["model_artifact_digest"]
        == prepared_identity["model_sha256"]
        == catalog_identity["model_sha256"]
        and float(decision["threshold"]) == float(coverage["threshold"])
        and float(decision["margin_floor"])
        == float(coverage["margin_floor"])
        and int(decision["certifiable_samples"]) == int(coverage["v_cert"])
        == int(prepared_identity["v_cert"])
        == int(catalog_identity["v_cert"])
        and int(decision["ambiguous_samples"]) == int(coverage["v_amb"])
        == int(prepared_identity["v_amb"])
        == int(catalog_identity["v_amb"])
        and prepared_identity["stored_score_digest"]
        == decision["validation_digest"]
    )
    split_match = (
        contract["split_id"]
        == f"split_seed_{direct['split_seed']}"
        and int(split_manifest_value["split_seed"])
        == int(direct["split_seed"])
        and split_manifest_value["dataset_id"] == direct["dataset_id"]
        and split_manifest_value["model_id"] == direct["model_id"]
        and split_manifest_value["configuration_validation"]["csv_digest"]
        == coverage["validation_csv_digest"]
        and split_manifest_value["model_artifact_digest"]
        == coverage["model_artifact_digest"]
    )
    identity_class, rerun_required, reason = classify(
        source_raw_match=source_raw_match,
        prepared_raw_match=prepared_raw_match,
        ordered_row_ids_match=ordered_row_ids_match,
        feature_semantics_match=feature_semantics_match,
        decision_semantics_match=decision_semantics_match,
        policy_match=policy_match,
        split_match=split_match,
    )
    row = {
        "split_seed": direct["split_seed"],
        "dataset_id": direct["dataset_id"],
        "model_id": direct["model_id"],
        "split_id": contract["split_id"],
        "model_sha256": model_binding["sha256"],
        "split_manifest_sha256": sha256_file(split_manifest),
        "direct_source_path": source_binding["path"],
        "direct_source_raw_sha256": source_identity["file"]["raw_sha256"],
        "direct_prepared_path": prepared_binding["path"],
        "direct_prepared_raw_sha256": prepared_identity["file"]["raw_sha256"],
        "direct_materialization_schema": materialization["schema_version"],
        "source_feature_space": materialization["source_feature_space"],
        "preprocessing_method": materialization["preprocessing_method"],
        "source_replay_verified": bool_text(
            as_bool(materialization["source_replay_verified"])
        ),
        "direct_decision_validation_digest": decision["validation_digest"],
        "catalog_source_path": coverage["validation_csv"],
        "catalog_source_raw_sha256": catalog_identity["file"]["raw_sha256"],
        "catalog_decision_validation_digest": catalog_identity[
            "stored_score_digest"
        ],
        "direct_row_count": str(prepared_identity["file"]["row_count"]),
        "catalog_row_count": str(catalog_identity["file"]["row_count"]),
        "direct_ordered_row_id_digest": prepared_identity["file"][
            "ordered_row_id_digest"
        ],
        "catalog_ordered_row_id_digest": catalog_identity["file"][
            "ordered_row_id_digest"
        ],
        "direct_feature_semantic_digest": prepared_identity[
            "feature_semantic_digest"
        ],
        "catalog_feature_semantic_digest": catalog_identity[
            "feature_semantic_digest"
        ],
        "direct_decision_semantic_digest": prepared_identity[
            "decision_semantic_digest"
        ],
        "catalog_decision_semantic_digest": catalog_identity[
            "decision_semantic_digest"
        ],
        "validation_semantic_digest": prepared_identity[
            "validation_semantic_digest"
        ],
        "direct_V_cert": str(decision["certifiable_samples"]),
        "direct_V_amb": str(decision["ambiguous_samples"]),
        "catalog_V_cert": coverage["v_cert"],
        "catalog_V_amb": coverage["v_amb"],
        "threshold": str(decision["threshold"]),
        "alpha": str(decision["safety_factor"]),
        "margin_floor": str(decision["margin_floor"]),
        "source_raw_match": bool_text(source_raw_match),
        "prepared_raw_match": bool_text(prepared_raw_match),
        "ordered_row_ids_match": bool_text(ordered_row_ids_match),
        "feature_semantics_match": bool_text(feature_semantics_match),
        "decision_semantics_match": bool_text(decision_semantics_match),
        "policy_match": bool_text(policy_match),
        "identity_class": identity_class,
        "encrypted_rerun_required": bool_text(rerun_required),
        "reason": reason,
    }
    details = {
        "key": {
            "split_seed": int(direct["split_seed"]),
            "dataset_id": direct["dataset_id"],
            "model_id": direct["model_id"],
        },
        "direct_contract": {
            "model_artifact": model_binding,
            "validation_data": prepared_binding,
            "source_data": source_binding,
            "input_materialization": materialization,
            "decision": decision,
            "split_id": contract["split_id"],
        },
        "catalog": {
            "split_manifest_path": coverage["split_manifest"],
            "split_manifest_sha256": sha256_file(split_manifest),
            "configuration_validation_csv": coverage["validation_csv"],
            "validation_csv_digest": coverage["validation_csv_digest"],
            "model_artifact": coverage["model_artifact"],
            "model_artifact_digest": coverage["model_artifact_digest"],
            "row_count": int(coverage["sample_count"]),
            "v_cert": int(coverage["v_cert"]),
            "v_amb": int(coverage["v_amb"]),
            "threshold": float(coverage["threshold"]),
            "margin_floor": float(coverage["margin_floor"]),
        },
        "source_file": source_identity["file"],
        "prepared_file": prepared_identity["file"],
        "catalog_file": catalog_identity["file"],
        "classification": {
            "identity_class": identity_class,
            "encrypted_rerun_required": rerun_required,
            "reason": reason,
        },
    }
    return row, details


def prepare_output(path: Path, force: bool) -> None:
    if path.exists():
        if not force:
            raise ValueError(f"{path} exists; use --force")
        shutil.rmtree(path)
    path.mkdir(parents=True)


def write_sums(output_root: Path) -> None:
    names = [
        "validation_identity_matrix.csv",
        "mismatch_details.json",
        "summary.json",
        "verify_validation_identity_audit.py",
    ]
    lines = [
        f"{sha256_file(output_root / name, prefix=False)}  {name}"
        for name in names
    ]
    (output_root / "SHA256SUMS").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def generate(args: argparse.Namespace) -> int:
    if not args.identity_binary.is_file():
        raise ValueError(f"{args.identity_binary}: identity binary not found")
    direct_results_path = args.direct_root / "workload_results.csv"
    direct_summary_path = args.direct_root / "summary.json"
    coverage_path = args.oracle_root / "validation_coverage.csv"
    direct_rows = index_unique(
        load_csv(direct_results_path),
        "direct results",
    )
    coverage_rows = index_unique(
        load_csv(coverage_path),
        "catalog coverage",
    )
    if len(direct_rows) != 50 or set(direct_rows) != set(coverage_rows):
        raise ValueError("identity audit requires the exact 50-workload matrix")

    output_rows: list[dict[str, str]] = []
    details: list[dict[str, Any]] = []
    for row_key in sorted(direct_rows):
        direct = direct_rows[row_key]
        coverage = coverage_rows[row_key]
        direct_result = load_json(Path(direct["result_path"]))
        contract = direct_result["plan"]["contract"]
        decision = contract["decision"]
        role = direct["partition_role"]
        common = {
            "model_path": contract["model_artifact"]["path"],
            "dataset_id": direct["dataset_id"],
            "model_id": direct["model_id"],
            "split_id": contract["split_id"],
            "partition_role": role,
            "margin_floor": float(decision["margin_floor"]),
        }
        source_identity = run_identity(
            args.identity_binary,
            validation_path=contract["source_data"]["path"],
            **common,
        )
        prepared_identity = run_identity(
            args.identity_binary,
            validation_path=contract["validation_data"]["path"],
            **common,
        )
        catalog_identity = run_identity(
            args.identity_binary,
            validation_path=coverage["validation_csv"],
            **common,
        )
        row, detail = make_row(
            direct,
            coverage,
            direct_result,
            source_identity,
            prepared_identity,
            catalog_identity,
        )
        output_rows.append(row)
        details.append(detail)

    prepare_output(args.output_root, args.force)
    matrix_path = args.output_root / "validation_identity_matrix.csv"
    with matrix_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(output_rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(output_rows)

    original = next(
        detail
        for detail in details
        if detail["key"]
        == {
            "split_seed": 0,
            "dataset_id": "banknote",
            "model_id": "linear_poly3",
        }
    )
    comparator_stderr = (
        "Traceback (most recent call last):\n"
        '  File "/home/ckks2/flipguard/scripts/'
        'compare_direct_synthesis_to_catalog_oracle.py", line 677, '
        "in <module>\n"
        "    raise SystemExit(main())\n"
        "                     ^^^^^^\n"
        '  File "/home/ckks2/flipguard/scripts/'
        'compare_direct_synthesis_to_catalog_oracle.py", line 362, '
        "in main\n"
        '    raise ValueError(f"{key}: artifact digest mismatch")\n'
        "ValueError: (0, 'banknote', 'linear_poly3'): "
        "artifact digest mismatch\n"
    )
    mismatch_details = {
        "schema_version": 2,
        "reason_code": FAILURE_REASON_CODE,
        "failing_stage": "direct_vs_security_v2_bounded_catalog_comparator_v1",
        "execution_source_commit": args.execution_source_commit,
        "comparison_builder_commit": args.comparison_builder_commit,
        "comparator_source_commit": args.execution_source_commit,
        "comparator_stdout": "",
        "comparator_stderr": comparator_stderr,
        "original_failing_workload": original,
        "workloads": details,
    }
    canonical_json(
        args.output_root / "mismatch_details.json",
        mismatch_details,
    )

    class_counts = Counter(row["identity_class"] for row in output_rows)
    original_row = next(
        row
        for row in output_rows
        if row["split_seed"] == "0"
        and row["dataset_id"] == "banknote"
        and row["model_id"] == "linear_poly3"
    )
    summary = {
        "schema_version": 2,
        "audit_id": "validation_identity_audit_v2",
        "reason_code": FAILURE_REASON_CODE,
        "execution_source_commit": args.execution_source_commit,
        "comparison_builder_commit": args.comparison_builder_commit,
        "workload_partition_instances": len(output_rows),
        "identity_class_counts": dict(sorted(class_counts.items())),
        "direct_source_matches_catalog_source": sum(
            row["source_raw_match"] == "true" for row in output_rows
        ),
        "prepared_raw_digest_mismatches": sum(
            row["prepared_raw_match"] != "true" for row in output_rows
        ),
        "ordered_row_mismatches": sum(
            row["ordered_row_ids_match"] != "true"
            for row in output_rows
        ),
        "feature_semantic_mismatches": sum(
            row["feature_semantics_match"] != "true"
            for row in output_rows
        ),
        "decision_semantic_mismatches": sum(
            row["decision_semantics_match"] != "true"
            for row in output_rows
        ),
        "policy_mismatches": sum(
            row["policy_match"] != "true" for row in output_rows
        ),
        "encrypted_rerun_required_workloads": sum(
            row["encrypted_rerun_required"] == "true"
            for row in output_rows
        ),
        "original_failing_workload_regression": {
            "identity_class": original_row["identity_class"],
            "direct_source_raw_sha256": original_row[
                "direct_source_raw_sha256"
            ],
            "direct_prepared_raw_sha256": original_row[
                "direct_prepared_raw_sha256"
            ],
            "catalog_source_raw_sha256": original_row[
                "catalog_source_raw_sha256"
            ],
            "validation_semantic_digest": original_row[
                "validation_semantic_digest"
            ],
        },
        "preserved_evidence_manifests": {
            "direct_confirmatory": {
                "path": str(DIRECT_EVIDENCE_MANIFEST),
                "sha256": sha256_file(DIRECT_EVIDENCE_MANIFEST),
            },
            "seed0_development": {
                "path": str(DEVELOPMENT_EVIDENCE_MANIFEST),
                "sha256": sha256_file(DEVELOPMENT_EVIDENCE_MANIFEST),
            },
        },
        "identity_binary": {
            "path": str(args.identity_binary),
            "sha256": sha256_file(args.identity_binary),
        },
        "inputs": {
            "direct_results": {
                "path": str(direct_results_path),
                "sha256": sha256_file(direct_results_path),
            },
            "direct_summary": {
                "path": str(direct_summary_path),
                "sha256": sha256_file(direct_summary_path),
            },
            "catalog_validation_coverage": {
                "path": str(coverage_path),
                "sha256": sha256_file(coverage_path),
            },
        },
    }
    canonical_json(args.output_root / "summary.json", summary)
    verifier_source = Path(__file__).with_name(
        "verify_validation_identity_audit.py"
    )
    shutil.copyfile(
        verifier_source,
        args.output_root / "verify_validation_identity_audit.py",
    )
    write_sums(args.output_root)
    subprocess.run(
        [
            sys.executable,
            str(args.output_root / "verify_validation_identity_audit.py"),
            str(args.output_root),
        ],
        check=True,
    )
    print(
        "validation_identity_audit=COMPLETE "
        f"workloads={len(output_rows)} "
        f"classes={dict(sorted(class_counts.items()))}"
    )
    return 0


def verify(args: argparse.Namespace) -> int:
    subprocess.run(
        [
            sys.executable,
            str(args.output_root / "verify_validation_identity_audit.py"),
            str(args.output_root),
        ],
        check=True,
    )
    existing = load_json(args.output_root / "summary.json")
    with tempfile.TemporaryDirectory(
        prefix="flipguard-validation-identity-",
        dir="/tmp",
    ) as temporary:
        regenerated = Path(temporary) / "audit"
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--direct-root",
            str(args.direct_root),
            "--oracle-root",
            str(args.oracle_root),
            "--output-root",
            str(regenerated),
            "--identity-binary",
            str(args.identity_binary),
            "--execution-source-commit",
            args.execution_source_commit,
            "--comparison-builder-commit",
            str(existing["comparison_builder_commit"]),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
        for name in (
            "validation_identity_matrix.csv",
            "mismatch_details.json",
            "summary.json",
            "verify_validation_identity_audit.py",
            "SHA256SUMS",
        ):
            if (args.output_root / name).read_bytes() != (
                regenerated / name
            ).read_bytes():
                raise ValueError(f"{name}: deterministic regeneration changed")
    print("validation_identity_audit=DETERMINISTIC_PASS")
    return 0


def main() -> int:
    args = parse_args()
    if args.verify:
        if args.force:
            raise ValueError("--verify and --force are mutually exclusive")
        return verify(args)
    return generate(args)


if __name__ == "__main__":
    raise SystemExit(main())
