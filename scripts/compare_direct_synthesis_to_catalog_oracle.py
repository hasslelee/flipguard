#!/usr/bin/env python3
"""Compare direct synthesis with the completed fixed-catalog oracle."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_ORACLE_ROOT = Path(
    "results/thesis_grade_protocol/"
    "tabular_validation_oracle_v1/full/summary"
)
DEFAULT_DIRECT_ROOT = Path(
    "results/thesis_grade_protocol/"
    "direct_tabular_autotune_v1/full_floor18_keys3/summary"
)
DEFAULT_OUTPUT_ROOT = Path(
    "results/thesis_grade_protocol/"
    "direct_vs_catalog_oracle_v1/full"
)

KEY_FIELDS = ("split_seed", "dataset_id", "model_id")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--oracle-root",
        type=Path,
        default=DEFAULT_ORACLE_ROOT,
    )
    parser.add_argument(
        "--direct-root",
        type=Path,
        default=DEFAULT_DIRECT_ROOT,
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
    )
    parser.add_argument("--alpha", type=float, default=0.5)
    parser.add_argument(
        "--expected-candidates-per-workload",
        type=int,
        default=22,
    )
    parser.add_argument("--allow-incomplete", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label}: expected an object")
    return value


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"{path}: missing CSV header")
        return list(reader)


def row_key(row: dict[str, str]) -> tuple[int, str, str]:
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
        key = row_key(row)
        if key in result:
            raise ValueError(f"{label}: duplicate workload {key}")
        result[key] = row
    return result


def as_int(row: dict[str, str], field: str) -> int:
    return int(row[field])


def as_float(row: dict[str, str], field: str) -> float:
    return float(row[field])


def optional_float(row: dict[str, str], field: str) -> float | None:
    value = row.get(field, "")
    return float(value) if value else None


def format_number(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.12g}"


def geometric_mean(values: list[float]) -> float | None:
    if not values:
        return None
    if any(value <= 0 for value in values):
        raise ValueError("geometric mean inputs must be positive")
    return math.exp(
        sum(math.log(value) for value in values) / len(values)
    )


def prepare_output(path: Path, force: bool) -> None:
    if path.exists():
        if not force:
            raise ValueError(
                f"{path} already exists; use --force to replace it"
            )
        shutil.rmtree(path)
    path.mkdir(parents=True)


def verify(args: argparse.Namespace) -> int:
    if args.force:
        raise ValueError("--verify and --force are mutually exclusive")
    summary_path = args.output_root / "summary.json"
    comparison_path = args.output_root / "comparison.csv"
    summary = load_json(summary_path)
    if summary.get("schema_version") != 1:
        raise ValueError("unsupported comparison summary schema")
    for item in summary["inputs"].values():
        path = Path(item["path"])
        if (
            not path.is_file()
            or sha256_file(path) != item["sha256"]
        ):
            raise ValueError(f"{path}: comparison input changed")

    with tempfile.TemporaryDirectory(
        prefix="flipguard-direct-oracle-verify-",
        dir="/tmp",
    ) as temporary:
        regenerated = Path(temporary) / "comparison"
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--oracle-root",
            str(args.oracle_root),
            "--direct-root",
            str(args.direct_root),
            "--output-root",
            str(regenerated),
            "--alpha",
            str(args.alpha),
            "--expected-candidates-per-workload",
            str(args.expected_candidates_per_workload),
        ]
        if args.allow_incomplete:
            command.append("--allow-incomplete")
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        for name in ("comparison.csv", "summary.json"):
            existing = args.output_root / name
            rebuilt = regenerated / name
            if existing.read_bytes() != rebuilt.read_bytes():
                raise ValueError(
                    f"{existing}: deterministic regeneration changed"
                )
    print(
        "direct_catalog_comparison=VERIFIED "
        f"workloads={summary['complete_oracle_workloads_compared']} "
        f"candidates="
        f"{summary['catalog_candidate_executions']}"
    )
    return 0


def main() -> int:
    args = parse_args()
    if args.expected_candidates_per_workload <= 0:
        raise ValueError(
            "--expected-candidates-per-workload must be positive"
        )
    if args.verify:
        return verify(args)

    oracle_summary_path = args.oracle_root / "summary.json"
    oracle_selection_path = (
        args.oracle_root / "oracle_selection.csv"
    )
    coverage_path = args.oracle_root / "validation_coverage.csv"
    direct_summary_path = args.direct_root / "summary.json"
    direct_results_path = args.direct_root / "workload_results.csv"

    oracle_summary = load_json(oracle_summary_path)
    direct_summary = load_json(direct_summary_path)
    oracle_incomplete = bool(
        oracle_summary.get("allow_incomplete")
    ) or (
        int(oracle_summary["actual_run_count"])
        != int(oracle_summary["expected_full_run_count"])
    )
    if oracle_incomplete and not args.allow_incomplete:
        raise ValueError(
            "oracle matrix is incomplete; use --allow-incomplete "
            "only for diagnostic checkpoint output"
        )
    if not bool(direct_summary.get("complete")):
        raise ValueError("direct synthesis matrix is incomplete")

    direct_rows = load_csv(direct_results_path)
    coverage_rows = load_csv(coverage_path)
    all_oracle_rows = load_csv(oracle_selection_path)
    oracle_rows = [
        row
        for row in all_oracle_rows
        if math.isclose(
            as_float(row, "alpha"),
            args.alpha,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
    ]

    direct_by_key = index_unique(direct_rows, "direct results")
    coverage_by_key = index_unique(
        coverage_rows,
        "validation coverage",
    )
    oracle_by_key = index_unique(
        oracle_rows,
        f"oracle alpha={args.alpha}",
    )

    if len(direct_by_key) != int(direct_summary["expected_runs"]):
        raise ValueError(
            "direct result row count does not match expected runs"
        )
    if set(direct_by_key) != set(coverage_by_key):
        raise ValueError(
            "direct workloads do not match validation coverage"
        )

    complete_oracle_keys = {
        key
        for key, row in oracle_by_key.items()
        if as_int(row, "candidate_count")
        == args.expected_candidates_per_workload
    }
    incomplete_oracle_keys = (
        set(oracle_by_key) - complete_oracle_keys
    )
    if not args.allow_incomplete and (
        incomplete_oracle_keys
        or complete_oracle_keys != set(direct_by_key)
    ):
        raise ValueError(
            "oracle does not contain a complete candidate set "
            "for every direct workload"
        )
    if not complete_oracle_keys:
        raise ValueError("no complete oracle workloads are available")

    output_rows: list[dict[str, str]] = []
    speedups: list[float] = []
    regrets: list[float] = []
    direct_faster = 0
    direct_equal = 0
    direct_slower = 0

    for key in sorted(complete_oracle_keys):
        direct = direct_by_key[key]
        coverage = coverage_by_key[key]
        oracle = oracle_by_key[key]
        direct_result_path = Path(direct["result_path"])
        direct_result = load_json(direct_result_path)
        direct_plan = require_dict(
            direct_result.get("plan"),
            f"{direct_result_path}: plan",
        )
        direct_contract = require_dict(
            direct_plan.get("contract"),
            f"{direct_result_path}: contract",
        )
        direct_decision = require_dict(
            direct_contract.get("decision"),
            f"{direct_result_path}: decision",
        )
        direct_model_binding = require_dict(
            direct_contract.get("model_artifact"),
            f"{direct_result_path}: model_artifact",
        )
        direct_validation_binding = require_dict(
            direct_contract.get("validation_data"),
            f"{direct_result_path}: validation_data",
        )

        if direct["status"] != "ok":
            raise ValueError(f"{key}: direct execution status is not ok")
        direct_outcome = direct["outcome"]
        if direct_outcome == "SELECTED":
            if (
                direct["selected_trial_status"] != "SAFE"
                or as_int(direct, "decision_flips") != 0
                or as_int(direct, "error_violations") != 0
            ):
                raise ValueError(
                    f"{key}: selected direct result is not SAFE"
                )
        elif direct_outcome != "NO_SAFE":
            raise ValueError(
                f"{key}: unsupported direct outcome {direct_outcome}"
            )

        if (
            direct["validation_sha256"]
            != coverage["validation_csv_digest"]
            or direct["model_sha256"]
            != coverage["model_artifact_digest"]
            or direct_validation_binding.get("sha256")
            != coverage["validation_csv_digest"]
            or direct_model_binding.get("sha256")
            != coverage["model_artifact_digest"]
            or direct_plan.get("contract_digest")
            != direct["contract_digest"]
        ):
            raise ValueError(f"{key}: artifact digest mismatch")
        if not math.isclose(
            float(direct_decision["safety_factor"]),
            args.alpha,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError(f"{key}: safety-factor mismatch")
        if not math.isclose(
            float(direct_decision["margin_floor"]),
            as_float(coverage, "margin_floor"),
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError(f"{key}: margin-floor mismatch")
        if (
            as_int(oracle, "safe_count")
            + as_int(oracle, "rejected_count")
            + as_int(oracle, "failed_count")
            != args.expected_candidates_per_workload
        ):
            raise ValueError(f"{key}: invalid catalog status counts")
        if (
            as_int(direct, "v_cert") != as_int(oracle, "v_cert")
            or as_int(direct, "v_amb") != as_int(oracle, "v_amb")
            or as_int(direct, "v_cert") != as_int(coverage, "v_cert")
            or as_int(direct, "v_amb") != as_int(coverage, "v_amb")
            or as_int(direct, "v_cert")
            != int(direct_decision["certifiable_samples"])
            or as_int(direct, "v_amb")
            != int(direct_decision["ambiguous_samples"])
        ):
            raise ValueError(f"{key}: coverage partition mismatch")

        oracle_mean = optional_float(
            oracle,
            "oracle_mean_total_ms",
        )
        direct_mean = (
            as_float(direct, "mean_total_ms")
            if direct_outcome == "SELECTED"
            else None
        )
        speedup: float | None = None
        regret: float | None = None
        if oracle["outcome"] == "SELECTED":
            if oracle_mean is None:
                raise ValueError(
                    f"{key}: selected oracle has no latency"
                )
            if direct_mean is not None:
                speedup = oracle_mean / direct_mean
                regret = (direct_mean - oracle_mean) / oracle_mean
                speedups.append(speedup)
                regrets.append(regret)
                if math.isclose(
                    direct_mean,
                    oracle_mean,
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                ):
                    direct_equal += 1
                elif direct_mean < oracle_mean:
                    direct_faster += 1
                else:
                    direct_slower += 1

        output_rows.append(
            {
                "split_seed": str(key[0]),
                "dataset_id": key[1],
                "model_id": key[2],
                "alpha": format_number(args.alpha),
                "catalog_outcome": oracle["outcome"],
                "catalog_candidate_count": oracle[
                    "candidate_count"
                ],
                "catalog_safe_count": oracle["safe_count"],
                "catalog_rejected_count": oracle[
                    "rejected_count"
                ],
                "catalog_failed_count": oracle["failed_count"],
                "v_cert": oracle["v_cert"],
                "v_amb": oracle["v_amb"],
                "coverage_rate": oracle["coverage_rate"],
                "catalog_oracle_candidate": oracle[
                    "oracle_candidate"
                ],
                "catalog_oracle_mean_total_ms": format_number(
                    oracle_mean
                ),
                "reference_candidate": oracle[
                    "reference_candidate"
                ],
                "reference_cryptographic_security_admitted": oracle[
                    "reference_cryptographic_security_admitted"
                ],
                "reference_execution_status": oracle[
                    "reference_execution_status"
                ],
                "reference_decision_certificate_status": oracle[
                    "reference_decision_certificate_status"
                ],
                "reference_latency_role": oracle[
                    "reference_latency_role"
                ],
                "reference_mean_total_ms": oracle[
                    "reference_mean_total_ms"
                ],
                "latency_only_candidate": oracle[
                    "latency_only_candidate"
                ],
                "latency_only_status": oracle[
                    "latency_only_status"
                ],
                "latency_only_mean_total_ms": oracle[
                    "latency_only_mean_total_ms"
                ],
                "direct_outcome": direct_outcome,
                "direct_candidate": direct[
                    "selected_candidate_id"
                ],
                "direct_contract_digest": direct[
                    "contract_digest"
                ],
                "direct_log_n": direct["log_n"],
                "direct_q_prime_count": direct[
                    "q_prime_count"
                ],
                "direct_log_default_scale": direct[
                    "log_default_scale"
                ],
                "direct_trials": direct["trials_used"],
                "direct_key_runs": direct[
                    "encrypted_key_runs"
                ],
                "direct_mean_total_ms": format_number(
                    direct_mean
                ),
                "diagnostic_speedup_vs_catalog": format_number(
                    speedup
                ),
                "diagnostic_bounded_regret": format_number(
                    regret
                ),
                "latency_evidence": "UNPAIRED_DIAGNOSTIC",
            }
        )

    prepare_output(args.output_root, args.force)
    comparison_path = args.output_root / "comparison.csv"
    with comparison_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(output_rows[0].keys()),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(output_rows)

    direct_trials_all = sum(
        int(row["direct_trials"]) for row in output_rows
    )
    development_rows = [
        row for row in output_rows if int(row["split_seed"]) == 0
    ]
    confirmatory_rows = [
        row for row in output_rows if int(row["split_seed"]) in {1, 2, 3, 4}
    ]
    direct_trials_development = sum(
        int(row["direct_trials"]) for row in development_rows
    )
    direct_trials_confirmatory = sum(
        int(row["direct_trials"]) for row in confirmatory_rows
    )
    security_admitted_catalog_candidates = (
        len(output_rows) * args.expected_candidates_per_workload
    )
    development_catalog_candidates = (
        len(development_rows) * args.expected_candidates_per_workload
    )
    confirmatory_catalog_candidates = (
        len(confirmatory_rows) * args.expected_candidates_per_workload
    )
    raw_catalog_executions = int(
        oracle_summary.get("raw_catalog_executions", 1100)
    )
    reference_statuses = Counter(
        row["reference_decision_certificate_status"]
        for row in output_rows
    )
    summary = {
        "schema_version": 1,
        "alpha": args.alpha,
        "allow_incomplete": args.allow_incomplete,
        "oracle_matrix_complete": not oracle_incomplete,
        "expected_workloads": len(direct_by_key),
        "oracle_workloads_at_alpha": len(oracle_by_key),
        "complete_oracle_workloads_compared": len(output_rows),
        "incomplete_oracle_workloads_excluded": len(
            incomplete_oracle_keys
        ),
        "expected_candidates_per_workload": (
            args.expected_candidates_per_workload
        ),
        "direct_selected": sum(
            row["direct_outcome"] == "SELECTED"
            for row in output_rows
        ),
        "catalog_selected": sum(
            row["catalog_outcome"] == "SELECTED"
            for row in output_rows
        ),
        "direct_trials": direct_trials_all,
        "direct_key_runs": sum(
            int(row["direct_key_runs"])
            for row in output_rows
        ),
        "catalog_candidate_executions": (
            security_admitted_catalog_candidates
        ),
        "raw_catalog_executions": raw_catalog_executions,
        "security_admitted_catalog_candidates":
            security_admitted_catalog_candidates,
        "security_excluded_catalog_candidates": (
            raw_catalog_executions
            - security_admitted_catalog_candidates
        ),
        "development_catalog_candidates":
            development_catalog_candidates,
        "confirmatory_catalog_candidates":
            confirmatory_catalog_candidates,
        "direct_trials_all": direct_trials_all,
        "direct_trials_development": direct_trials_development,
        "direct_trials_confirmatory": direct_trials_confirmatory,
        "formal_trial_reduction_all": (
            1.0
            - direct_trials_all
            / security_admitted_catalog_candidates
        ),
        "formal_trial_reduction_confirmatory": (
            1.0
            - direct_trials_confirmatory
            / confirmatory_catalog_candidates
        ),
        "reference_security_pass_count": sum(
            row["reference_cryptographic_security_admitted"]
            == "true"
            for row in output_rows
        ),
        "reference_safe_count": reference_statuses["SAFE"],
        "reference_rejected_count": reference_statuses["REJECTED"],
        "reference_failed_count": reference_statuses["FAILED"],
        "direct_faster_diagnostic_count": direct_faster,
        "direct_equal_diagnostic_count": direct_equal,
        "direct_slower_diagnostic_count": direct_slower,
        "diagnostic_geomean_speedup_vs_catalog": geometric_mean(
            speedups
        ),
        "diagnostic_mean_bounded_regret": (
            sum(regrets) / len(regrets) if regrets else None
        ),
        "latency_evidence": "UNPAIRED_DIAGNOSTIC",
        "paper_latency_claim_allowed": False,
        "inputs": {
            "oracle_summary": {
                "path": str(oracle_summary_path),
                "sha256": sha256_file(oracle_summary_path),
            },
            "oracle_selection": {
                "path": str(oracle_selection_path),
                "sha256": sha256_file(oracle_selection_path),
            },
            "validation_coverage": {
                "path": str(coverage_path),
                "sha256": sha256_file(coverage_path),
            },
            "direct_summary": {
                "path": str(direct_summary_path),
                "sha256": sha256_file(direct_summary_path),
            },
            "direct_results": {
                "path": str(direct_results_path),
                "sha256": sha256_file(direct_results_path),
            },
        },
        "claim_boundary": (
            "The fixed catalog is a bounded oracle. Latencies in this "
            "comparison were recorded in separate processes and are "
            "diagnostic only. A paired repeated protocol is required "
            "before any paper speedup or latency-regret claim."
        ),
    }
    summary_path = args.output_root / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        "direct_catalog_comparison="
        + ("CHECKPOINT" if oracle_incomplete else "COMPLETE")
        + f" workloads={len(output_rows)}/{len(direct_by_key)}"
        + " paper_latency_claim_allowed=false"
    )
    print(f"comparison_csv={comparison_path}")
    print(f"summary_json={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
