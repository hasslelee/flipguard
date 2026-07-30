#!/usr/bin/env python3
"""Freeze a static sample/key analysis of the native EVA rejection."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import statistics
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
EVA_FREEZER_PATH = (
    REPO_ROOT / "scripts/freeze_eva_native_runtime_evidence.py"
)
EVA_SPEC = importlib.util.spec_from_file_location(
    "freeze_eva_native_runtime_evidence_for_rejection_analysis",
    EVA_FREEZER_PATH,
)
assert EVA_SPEC is not None and EVA_SPEC.loader is not None
EVA = importlib.util.module_from_spec(EVA_SPEC)
EVA_SPEC.loader.exec_module(EVA)

BASE = EVA.VERIFIER
EVA_PACK = REPO_ROOT / "docs/evidence/eva_native_runtime_replay_v1"
MATCHED_PACK = REPO_ROOT / "docs/evidence/hit_direct_matched_workload_v1"
OUTPUT_DEFAULT = (
    REPO_ROOT / "docs/evidence/eva_native_rejection_analysis_v1"
)
ANALYZER_PATH = Path("scripts/freeze_eva_native_rejection_analysis.py")
SCHEMA = "flipguard_eva_native_rejection_analysis_v1"


def sha256_path(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return (
        ordered[lower] * (1.0 - fraction)
        + ordered[upper] * fraction
    )


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = statistics.mean(left)
    right_mean = statistics.mean(right)
    numerator = sum(
        (x - left_mean) * (y - right_mean)
        for x, y in zip(left, right)
    )
    denominator = math.sqrt(
        sum((x - left_mean) ** 2 for x in left)
        * sum((y - right_mean) ** 2 for y in right)
    )
    return numerator / denominator if denominator else None


def affine_fit(
    left: list[float], right: list[float]
) -> tuple[float | None, float | None, float | None]:
    left_mean = statistics.mean(left)
    right_mean = statistics.mean(right)
    denominator = sum((value - left_mean) ** 2 for value in left)
    if not denominator:
        return None, None, None
    slope = sum(
        (x - left_mean) * (y - right_mean)
        for x, y in zip(left, right)
    ) / denominator
    intercept = right_mean - slope * left_mean
    residuals = [
        y - (intercept + slope * x) for x, y in zip(left, right)
    ]
    return slope, intercept, statistics.pstdev(residuals)


def load_ledger() -> list[dict[str, str]]:
    path = EVA_PACK / "raw/validation_ledger.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    require(len(rows) == 42, "native EVA ledger observation count changed")
    require(
        all(row["execution_status"] == "OK" for row in rows),
        "native EVA ledger contains execution failure",
    )
    return rows


def build_records() -> tuple[
    dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]
]:
    result = EVA.verify(EVA_PACK)
    require(
        result["validation_status"] == "REJECTED",
        "native EVA validation status changed",
    )
    summary = load_json(EVA_PACK / "summary.json")
    contract = load_json(EVA_PACK / "contract.json")
    raw_manifest = load_json(EVA_PACK / "raw/manifest.json")
    matched = load_json(MATCHED_PACK / "summary.json")
    rows = load_ledger()

    counts = summary["validation"]["counts"]
    require(counts["observations"] == 42, "summary observations changed")
    require(counts["key_repeats"] == 3, "summary key repeats changed")
    require(counts["decision_flips"] == 11, "summary flips changed")
    require(counts["error_violations"] == 36, "summary violations changed")
    require(
        summary["locked_audit"]["status"] == "NOT_EVALUATED",
        "native EVA audit boundary changed",
    )
    require(
        summary["policy_modifications"] == 0,
        "native EVA policy modification changed",
    )
    require(
        matched["identity"]["raw_validation_source_sha256"]
        == contract["workload"]["validation_sha256"],
        "EVA/direct raw validation identity changed",
    )
    require(
        matched["identity"]["raw_validation_source_byte_identical"] is True,
        "EVA/direct raw validation bytes are not identical",
    )
    direct_arms = [
        arm
        for arm in matched["arms"]
        if arm["provider"] == "direct_synthesizer"
    ]
    require(len(direct_arms) == 1, "matched direct arm count changed")
    direct = direct_arms[0]
    require(direct["selection_status"] == "SAFE", "direct arm changed")

    key_groups: dict[int, list[dict[str, str]]] = defaultdict(list)
    sample_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key_groups[int(row["key_repeat"])].append(row)
        sample_groups[row["row_id"]].append(row)
    require(sorted(key_groups) == [1, 2, 3], "key identities changed")
    require(len(sample_groups) == 14, "sample count changed")
    require(
        all(len(group) == 14 for group in key_groups.values()),
        "per-key sample count changed",
    )
    require(
        all(len(group) == 3 for group in sample_groups.values()),
        "per-sample key count changed",
    )

    key_rows: list[dict[str, Any]] = []
    for key_repeat, group in sorted(key_groups.items()):
        plaintext = [float(row["plaintext_score"]) for row in group]
        output = [float(row["native_ckks_score"]) for row in group]
        absolute = [float(row["absolute_error"]) for row in group]
        signed = [
            float(row["native_ckks_score"])
            - float(row["plaintext_score"])
            for row in group
        ]
        usage = [
            float(row["normalized_budget_usage"]) for row in group
        ]
        slope, intercept, residual_std = affine_fit(plaintext, output)
        key_rows.append(
            {
                "key_repeat": key_repeat,
                "observations": len(group),
                "decision_flips": sum(
                    row["decision_flip"] == "true" for row in group
                ),
                "error_violations": sum(
                    row["error_violation"] == "true" for row in group
                ),
                "mean_absolute_error": statistics.mean(absolute),
                "median_absolute_error": statistics.median(absolute),
                "max_absolute_error": max(absolute),
                "mean_signed_error": statistics.mean(signed),
                "native_output_mean": statistics.mean(output),
                "native_output_std": statistics.pstdev(output),
                "normalized_usage_mean": statistics.mean(usage),
                "normalized_usage_max": max(usage),
                "plaintext_to_native_slope": slope,
                "plaintext_to_native_intercept": intercept,
                "affine_residual_std": residual_std,
            }
        )

    sample_rows: list[dict[str, Any]] = []
    for row_id, group in sorted(
        sample_groups.items(), key=lambda item: int(item[0])
    ):
        plaintext = float(group[0]["plaintext_score"])
        margin = float(group[0]["decision_margin"])
        budget = float(group[0]["error_budget"])
        output = [float(row["native_ckks_score"]) for row in group]
        absolute = [float(row["absolute_error"]) for row in group]
        violation_count = sum(
            row["error_violation"] == "true" for row in group
        )
        sample_rows.append(
            {
                "row_id": row_id,
                "plaintext_score": plaintext,
                "decision_margin": margin,
                "alpha_margin_budget": budget,
                "key_observations": len(group),
                "decision_flips": sum(
                    row["decision_flip"] == "true" for row in group
                ),
                "error_violations": violation_count,
                "mean_absolute_error": statistics.mean(absolute),
                "median_absolute_error": statistics.median(absolute),
                "max_absolute_error": max(absolute),
                "native_output_mean": statistics.mean(output),
                "native_output_std": statistics.pstdev(output),
                "native_output_min": min(output),
                "native_output_max": max(output),
                "any_key_violation": violation_count > 0,
                "all_keys_violation": violation_count == len(group),
            }
        )

    dot = (EVA_PACK / "raw/compiled_program.dot").read_text(
        encoding="utf-8"
    )
    rescale_60_count = dot.count('label="Rescale(60)"')
    require(rescale_60_count == 2, "EVA rescale schedule changed")
    plaintext_delta = max(
        abs(
            float(row["eva_plaintext_score"])
            - float(row["plaintext_score"])
        )
        for row in rows
    )
    all_errors = [float(row["absolute_error"]) for row in rows]
    all_margins = [float(row["decision_margin"]) for row in rows]
    sample_mean_errors = [
        float(row["mean_absolute_error"]) for row in sample_rows
    ]
    sample_margins = [
        float(row["decision_margin"]) for row in sample_rows
    ]
    all_repeat_violations = sum(
        bool(row["all_keys_violation"]) for row in sample_rows
    )
    any_repeat_violations = sum(
        bool(row["any_key_violation"]) for row in sample_rows
    )
    max_key_mean = max(
        float(row["mean_absolute_error"]) for row in key_rows
    )
    min_key_mean = min(
        float(row["mean_absolute_error"]) for row in key_rows
    )

    analysis = {
        "schema_version": SCHEMA,
        "analysis_id": "eva_native_rejection_analysis_v1",
        "analysis_type": (
            "EXPLANATORY_POST_HOC_STATIC_NO_RERUN_NO_POLICY_CHANGE"
        ),
        "status": "PARTIAL_SCIENTIFIC_RESULT",
        "failure_class": (
            "NATIVE_EXTERNAL_CANDIDATE_DECISION_NUMERICAL_REJECT"
        ),
        "workload": {
            "role": contract["workload"]["role"],
            "dataset": contract["workload"]["dataset_id"],
            "model": contract["workload"]["model_id"],
            "split": contract["workload"]["split_id"],
            "validation_samples": 14,
            "key_repeats": 3,
        },
        "preserved_result": {
            "encrypted_observations": 42,
            "execution_failures": 0,
            "decision_flips": 11,
            "error_violations": 36,
            "max_absolute_error": counts["max_absolute_error"],
            "max_normalized_budget_usage": counts[
                "max_normalized_budget_usage"
            ],
            "validation_status": "REJECTED",
            "locked_audit_status": "NOT_EVALUATED",
            "retuning": 0,
        },
        "sample_key_scope": {
            "keys_with_any_violation": sum(
                int(row["error_violations"]) > 0 for row in key_rows
            ),
            "keys_with_any_flip": sum(
                int(row["decision_flips"]) > 0 for row in key_rows
            ),
            "samples_with_any_key_violation": any_repeat_violations,
            "samples_with_all_keys_violation": all_repeat_violations,
            "samples_with_any_flip": sum(
                int(row["decision_flips"]) > 0 for row in sample_rows
            ),
            "max_to_min_key_mean_absolute_error_ratio": (
                max_key_mean / min_key_mean
            ),
        },
        "identity_checks": {
            "raw_validation_source_byte_identical_to_direct": True,
            "raw_validation_source_sha256": contract["workload"][
                "validation_sha256"
            ],
            "model_sha256": contract["workload"]["model_sha256"],
            "native_eva_plaintext_vs_bound_score_max_abs_delta": (
                plaintext_delta
            ),
            "compiled_program_semantic_sha256": raw_manifest[
                "compiled_program_identity"
            ]["semantic_sha256"],
            "source_graph_or_plaintext_score_mismatch_supported": False,
        },
        "schedule_observation": {
            "native_runtime": "EVA_v1.0.1_SEAL_v3.6.4",
            "log_n": int(
                math.log2(
                    contract["compiler_binding"]["poly_modulus_degree"]
                )
            ),
            "q_prime_bits": contract["compiler_binding"]["prime_bits"][:-1],
            "p_prime_bits": contract["compiler_binding"]["prime_bits"][-1:],
            "declared_input_scale_bits": contract["compiler_binding"][
                "input_scale_bits"
            ],
            "compiled_rescale_60_operations": rescale_60_count,
            "direct_matched_runtime": "Lattigo_v6.2.0",
            "direct_log_n": direct["log_n"],
            "direct_log_q": direct["log_q"],
            "direct_log_p": direct["log_p"],
            "direct_scale_bits": direct["log_default_scale"],
            "direct_required_rescale_levels": direct[
                "required_rescale_levels"
            ],
        },
        "correlation_diagnostics": {
            "observation_level_margin_vs_absolute_error_pearson": pearson(
                all_margins, all_errors
            ),
            "sample_level_margin_vs_mean_absolute_error_pearson": pearson(
                sample_margins, sample_mean_errors
            ),
            "interpretation": (
                "descriptive only; repeated-key observations are not "
                "independent statistical samples"
            ),
        },
        "direct_matched_diagnostic": {
            "comparison_class": (
                "UNPAIRED_DIAGNOSTIC_DIFFERENT_RUNTIME_AND_SCHEDULE"
            ),
            "candidate_id": direct["candidate_id"],
            "validation_status": direct["selection_status"],
            "decision_flips": direct["decision_flips"],
            "error_violations": direct["error_violations"],
            "max_observed_error": direct["max_observed_error"],
            "max_normalized_budget_usage": direct[
                "max_normalized_budget_usage"
            ],
            "locked_audit_outcome": direct["locked_audit_outcome"],
            "causal_parameter_claim_allowed": False,
            "cross_runtime_numerical_equivalence_claim_allowed": False,
        },
        "causal_assessment": {
            "single_bad_key_explanation": "CONTRADICTED",
            "single_bad_sample_explanation": "CONTRADICTED",
            "source_or_plaintext_mismatch_explanation": "CONTRADICTED",
            "low_scale_relative_to_schedule_hypothesis": (
                "CONSISTENT_WITH_EVIDENCE_NOT_CAUSALLY_ESTABLISHED"
            ),
            "runtime_distribution_contribution": "NOT_IDENTIFIED",
            "schedule_contribution": "NOT_IDENTIFIED",
            "required_followup_for_causal_claim": (
                "prospectively predeclared scale/schedule/runtime ablation; "
                "the frozen candidate must not be retuned"
            ),
        },
        "claim_effect": {
            "native_eva_seal_execution": "SUPPORTED",
            "native_eva_seal_decision_certification": "BLOCKED",
            "native_eva_seal_locked_audit": "NOT_EVALUATED",
            "general_external_compiler_interoperability": (
                "PARTIALLY_SUPPORTED"
            ),
            "paper_claim_allowed": False,
        },
        "encrypted_executions_added": 0,
        "policy_modifications": 0,
    }
    return analysis, key_rows, sample_rows


def write_csv(
    path: Path, rows: list[dict[str, Any]], fields: list[str]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def write_checksums(root: Path) -> None:
    lines = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "SHA256SUMS":
            continue
        relative = path.relative_to(root).as_posix()
        lines.append(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}"
        )
    (root / "SHA256SUMS").write_text(
        "\n".join(lines) + "\n", encoding="ascii"
    )


def verify_checksums(root: Path) -> None:
    sums = root / "SHA256SUMS"
    require(sums.is_file(), "missing SHA256SUMS")
    expected: dict[str, str] = {}
    for line in sums.read_text(encoding="ascii").splitlines():
        digest, relative = line.split("  ", 1)
        expected[relative] = digest
    actual = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    require(sorted(expected) == actual, "analysis file inventory changed")
    for relative, digest in expected.items():
        require(
            hashlib.sha256((root / relative).read_bytes()).hexdigest()
            == digest,
            f"analysis checksum changed: {relative}",
        )


def freeze(
    output: Path,
    analysis_commit: str,
    *,
    analyzer_digest: str | None = None,
) -> None:
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite EVA rejection analysis: {output}"
        )
    analysis, key_rows, sample_rows = build_records()
    output.mkdir(parents=True)
    write_csv(
        output / "per_key_summary.csv",
        key_rows,
        [
            "key_repeat",
            "observations",
            "decision_flips",
            "error_violations",
            "mean_absolute_error",
            "median_absolute_error",
            "max_absolute_error",
            "mean_signed_error",
            "native_output_mean",
            "native_output_std",
            "normalized_usage_mean",
            "normalized_usage_max",
            "plaintext_to_native_slope",
            "plaintext_to_native_intercept",
            "affine_residual_std",
        ],
    )
    write_csv(
        output / "per_sample_summary.csv",
        sample_rows,
        [
            "row_id",
            "plaintext_score",
            "decision_margin",
            "alpha_margin_budget",
            "key_observations",
            "decision_flips",
            "error_violations",
            "mean_absolute_error",
            "median_absolute_error",
            "max_absolute_error",
            "native_output_mean",
            "native_output_std",
            "native_output_min",
            "native_output_max",
            "any_key_violation",
            "all_keys_violation",
        ],
    )
    (output / "analysis.json").write_bytes(canonical_json(analysis))
    key_one = key_rows[0]
    key_three = key_rows[2]
    scope = analysis["sample_key_scope"]
    readme = f"""# EVA Native Rejection Analysis V1

This static post-hoc analysis preserves the native EVA/SEAL validation
rejection without any encrypted rerun, candidate change, or policy change.

- Executions: 42/42 successful across 14 rows and 3 fresh keys.
- Decision result: 11 flips, 36 budget violations, `REJECTED`.
- Key-repeat violations: {key_rows[0]["error_violations"]},
  {key_rows[1]["error_violations"]}, {key_rows[2]["error_violations"]}.
- Mean absolute error changed from
  {key_one["mean_absolute_error"]:.6f} on repeat 1 to
  {key_three["mean_absolute_error"]:.6f} on repeat 3.
- Every sample violated under at least one key; {scope["samples_with_all_keys_violation"]}
  of 14 violated under all three keys.
- EVA plaintext and the bound score agree within
  {analysis["identity_checks"]["native_eva_plaintext_vs_bound_score_max_abs_delta"]:.3e}.

The pattern contradicts a single-bad-key, single-bad-sample, or plaintext
source-mismatch explanation. It is consistent with insufficient numerical
precision for this schedule, but no causal scale, schedule, or runtime claim
is made without a prospective ablation.

`paper_claim_allowed=false`.
"""
    (output / "README.md").write_text(readme, encoding="ascii")
    source_records = {
        "analyzer": {
            "path": ANALYZER_PATH.as_posix(),
            "sha256": (
                analyzer_digest
                if analyzer_digest is not None
                else sha256_path(REPO_ROOT / ANALYZER_PATH)
            ),
        },
        "eva_evidence_manifest": {
            "path": EVA_PACK.relative_to(REPO_ROOT).joinpath(
                "manifest.json"
            ).as_posix(),
            "sha256": sha256_path(EVA_PACK / "manifest.json"),
        },
        "eva_validation_ledger": {
            "path": EVA_PACK.relative_to(REPO_ROOT).joinpath(
                "raw/validation_ledger.csv"
            ).as_posix(),
            "sha256": sha256_path(
                EVA_PACK / "raw/validation_ledger.csv"
            ),
        },
        "eva_compiled_program": {
            "path": EVA_PACK.relative_to(REPO_ROOT).joinpath(
                "raw/compiled_program.dot"
            ).as_posix(),
            "sha256": sha256_path(
                EVA_PACK / "raw/compiled_program.dot"
            ),
        },
        "matched_direct_summary": {
            "path": MATCHED_PACK.relative_to(REPO_ROOT).joinpath(
                "summary.json"
            ).as_posix(),
            "sha256": sha256_path(MATCHED_PACK / "summary.json"),
        },
    }
    manifest = {
        "schema_version": SCHEMA,
        "evidence_id": "eva_native_rejection_analysis_v1",
        "classification": (
            "POST_HOC_STATIC_NATIVE_EXTERNAL_NUMERICAL_REJECTION"
        ),
        "analysis_commit": analysis_commit,
        "status": analysis["status"],
        "source_records": source_records,
        "files": {
            name: sha256_path(output / name)
            for name in (
                "README.md",
                "analysis.json",
                "per_key_summary.csv",
                "per_sample_summary.csv",
            )
        },
        "encrypted_executions_added": 0,
        "policy_modifications": 0,
        "claim_states": analysis["claim_effect"],
        "paper_claim_allowed": False,
    }
    (output / "manifest.json").write_bytes(canonical_json(manifest))
    write_checksums(output)


def verify(output: Path = OUTPUT_DEFAULT) -> dict[str, Any]:
    verify_checksums(output)
    manifest = load_json(output / "manifest.json")
    require(manifest["schema_version"] == SCHEMA, "analysis schema changed")
    require(
        manifest["paper_claim_allowed"] is False,
        "analysis paper gate changed",
    )
    require(
        manifest["encrypted_executions_added"] == 0,
        "analysis added encrypted executions",
    )
    require(
        manifest["policy_modifications"] == 0,
        "analysis changed frozen policy",
    )
    for name, record in manifest["source_records"].items():
        path = REPO_ROOT / record["path"]
        if name == "analyzer":
            continue
        require(path.is_file(), f"missing bound source: {record['path']}")
        require(
            sha256_path(path) == record["sha256"],
            f"bound source changed: {name}",
        )
    analyzer = manifest["source_records"]["analyzer"]
    current_analyzer = REPO_ROOT / analyzer["path"]
    if sha256_path(current_analyzer) != analyzer["sha256"]:
        historical = subprocess.run(
            [
                "git",
                "show",
                f"{manifest['analysis_commit']}:{analyzer['path']}",
            ],
            cwd=REPO_ROOT,
            check=True,
            stdout=subprocess.PIPE,
        ).stdout
        require(
            "sha256:" + hashlib.sha256(historical).hexdigest()
            == analyzer["sha256"],
            "historical analyzer binding changed",
        )
    with tempfile.TemporaryDirectory(
        prefix="flipguard-eva-native-rejection-", dir="/tmp"
    ) as temporary:
        rebuilt = Path(temporary) / "rebuilt"
        freeze(
            rebuilt,
            manifest["analysis_commit"],
            analyzer_digest=analyzer["sha256"],
        )
        left = {
            path.relative_to(output).as_posix(): path.read_bytes()
            for path in output.rglob("*")
            if path.is_file()
        }
        right = {
            path.relative_to(rebuilt).as_posix(): path.read_bytes()
            for path in rebuilt.rglob("*")
            if path.is_file()
        }
        require(left == right, "reconstructed rejection analysis changed")
    return manifest


def clean_source_gate() -> str:
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    if status:
        raise ValueError("analysis freeze requires a clean tree:\n" + status)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    origin = subprocess.run(
        ["git", "rev-parse", f"origin/{branch}"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    require(head == origin, "analysis freeze HEAD differs from origin")
    return head


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--analysis-commit")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    output = (
        args.output
        if args.output.is_absolute()
        else REPO_ROOT / args.output
    )
    if args.verify:
        manifest = verify(output)
        print(
            "eva_native_rejection_analysis=VERIFIED "
            f"status={manifest['status']} paper_claim_allowed=false"
        )
        return
    head = clean_source_gate()
    if args.analysis_commit and args.analysis_commit != head:
        raise ValueError("requested analysis commit differs from clean HEAD")
    freeze(output, head)
    print(
        f"eva_native_rejection_analysis=FROZEN output={output} "
        f"analysis_commit={head}"
    )


if __name__ == "__main__":
    main()
