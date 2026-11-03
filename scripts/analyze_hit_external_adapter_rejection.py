#!/usr/bin/env python3
"""Freeze a no-rerun analysis of the source-replayed HIT rejection."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PACK = Path("docs/evidence/hit_external_adapter_replay_v1")
DEFAULT_OUTPUT = Path(
    "docs/evidence/hit_external_adapter_rejection_analysis_v1"
)
SCHEMA_VERSION = "flipguard_hit_external_rejection_analysis_v1"
FAILURE_CLASS = "EXTERNAL_SELECTOR_PRECISION_BUDGET_REJECT"

FREEZER_PATH = REPO_ROOT / (
    "scripts/freeze_hit_external_adapter_evidence.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_hit_adapter_for_analysis",
    FREEZER_PATH,
)
assert SPEC is not None and SPEC.loader is not None
HIT_FREEZER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HIT_FREEZER)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-pack", type=Path, default=SOURCE_PACK)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def absolute(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        + "\n"
    ).encode("ascii")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def require_clean_origin() -> str:
    status = git("status", "--short")
    if status:
        raise ValueError(
            "HIT rejection analysis requires a clean tree:\n" + status
        )
    head = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    origin = git("rev-parse", f"origin/{branch}")
    if head != origin:
        raise ValueError(f"HEAD {head} does not match origin {origin}")
    return head


def fmt_float(value: float) -> str:
    return format(value, ".17g")


def build_analysis(
    source_pack: Path,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    source_pack = absolute(source_pack)
    source_summary = HIT_FREEZER.verify(source_pack)
    selection_path = source_pack / "run/selection.json"
    selection = load_json(selection_path)
    trial = selection["trial"]
    if (
        selection["outcome"] != "NO_SAFE"
        or trial["status"] != "REJECTED"
        or trial["failure_signal"] != "NUMERICAL_REJECT"
        or trial["decision_flips"] != 0
        or trial["error_violations"] <= 0
    ):
        raise ValueError("source HIT result is not the preserved rejection")
    contract = selection["validation_contract"]
    validation_path = REPO_ROOT / contract["validation_data"]["path"]
    if sha256_path(validation_path) != \
            contract["validation_data"]["sha256"]:
        raise ValueError("validation artifact digest changed")
    threshold = float(contract["decision"]["threshold"])
    alpha = float(contract["decision"]["safety_factor"])
    margin_floor = float(contract["decision"]["margin_floor"])

    rows: list[dict[str, str]] = []
    margins: list[float] = []
    with validation_path.open(
        "r",
        encoding="ascii",
        newline="",
    ) as handle:
        for raw in csv.DictReader(handle):
            score = float(raw["polynomial_score"])
            margin = abs(score - threshold)
            margins.append(margin)
            rows.append({
                "row_id": raw["row_id"],
                "plaintext_score": fmt_float(score),
                "threshold": fmt_float(threshold),
                "decision_margin": fmt_float(margin),
                "safety_factor": fmt_float(alpha),
                "error_budget": fmt_float(alpha * margin),
                "plaintext_decision": raw["plaintext_decision"],
                "encrypted_score_available":
                    "false",
                "key_repeat_localization":
                    "NOT_AVAILABLE_TABULAR_TRIAL_RESULT_V1",
                "violation_membership":
                    "NOT_RECOVERABLE_FROM_FROZEN_AGGREGATE",
            })
    if len(rows) != contract["decision"]["validation_samples"]:
        raise ValueError("validation row count changed")
    if min(margins) <= margin_floor:
        raise ValueError("unexpected ambiguous validation row")

    observations = len(rows) * trial["key_repeats_completed"]
    flip_boundary = 1.0 / alpha
    maximum_usage = float(trial["max_error_budget_usage"])
    minimum_budget = alpha * min(margins)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "classification": "EXPLANATORY_POST_HOC_NO_RERUN",
        "failure_class": FAILURE_CLASS,
        "source_evidence": {
            "path": source_pack.relative_to(REPO_ROOT).as_posix(),
            "manifest_sha256": sha256_path(source_pack / "manifest.json"),
            "selection_sha256": sha256_path(selection_path),
            "candidate_id": source_summary["candidate_identity"],
        },
        "workload": {
            "dataset_id": contract["dataset_id"],
            "model_id": contract["model_id"],
            "split_id": contract["split_id"],
            "validation_rows": len(rows),
            "key_repeats": trial["key_repeats_completed"],
            "observation_count": observations,
        },
        "decision_contract": {
            "threshold": threshold,
            "margin_floor": margin_floor,
            "safety_factor": alpha,
            "minimum_margin": min(margins),
            "median_margin": statistics.median(margins),
            "maximum_margin": max(margins),
            "minimum_error_budget": minimum_budget,
            "normalized_flip_guarantee_boundary": flip_boundary,
        },
        "observed_aggregate": {
            "status": trial["status"],
            "decision_flips": trial["decision_flips"],
            "error_violations": trial["error_violations"],
            "violation_observation_fraction":
                trial["error_violations"] / observations,
            "max_observed_error": trial["max_observed_error"],
            "max_normalized_budget_usage": maximum_usage,
            "max_error_over_minimum_budget_upper_bound":
                trial["max_observed_error"] / minimum_budget,
            "all_observations_below_guaranteed_flip_boundary":
                maximum_usage < flip_boundary,
        },
        "interpretation": {
            "why_rejected": (
                "six encrypted sample-key observations exceeded the "
                "predeclared alpha-times-margin safety budget"
            ),
            "why_no_flip": (
                "the maximum normalized budget usage remained below "
                "1/alpha=2, so every absolute error remained below its "
                "decision margin"
            ),
            "policy_use": (
                "explanatory only; no candidate repair, reselection, "
                "retuning, or encrypted rerun"
            ),
        },
        "localization_limit": {
            "sample_level_encrypted_scores":
                "NOT_AVAILABLE_TABULAR_TRIAL_RESULT_V1",
            "violating_sample_count": None,
            "violating_key_repeat_count": None,
            "same_rows_across_repeats": None,
            "reason": (
                "the frozen TabularTrialResult stores aggregate violation "
                "counts and maxima but no sample-key observation ledger"
            ),
        },
        "claim_effects": {
            "decision_integrity_gate_value": "PARTIALLY_SUPPORTED",
            "lossless_external_literal_import": "SUPPORTED",
            "external_candidate_certification": "BLOCKED",
            "hit_candidate_quality": "NOT_EVALUATED_SINGLE_NEGATIVE",
            "general_external_autotuner_integration": "NOT_EVALUATED",
        },
        "encrypted_executions_added": 0,
        "policy_modifications": 0,
        "paper_claim_allowed": False,
    }
    return rows, summary


def render_csv(rows: list[dict[str, str]]) -> bytes:
    output = io.StringIO(newline="")
    fields = list(rows[0])
    writer = csv.DictWriter(
        output,
        fieldnames=fields,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("ascii")


def write_checksums(root: Path) -> None:
    lines = []
    for path in sorted(
        item
        for item in root.rglob("*")
        if item.is_file() and item.name != "SHA256SUMS"
    ):
        lines.append(
            f"{sha256_path(path).removeprefix('sha256:')}  "
            f"{path.relative_to(root).as_posix()}\n"
        )
    (root / "SHA256SUMS").write_text("".join(lines), encoding="ascii")


def verify_checksums(root: Path) -> None:
    expected: set[str] = set()
    for line in (root / "SHA256SUMS").read_text(
        encoding="ascii"
    ).splitlines():
        digest, relative = line.split("  ", 1)
        target = root / relative
        if not target.is_file() or sha256_path(target) != f"sha256:{digest}":
            raise ValueError(f"HIT rejection analysis changed: {relative}")
        expected.add(relative)
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if actual != expected:
        raise ValueError("HIT rejection analysis file set changed")


def generate(source_pack: Path, output_root: Path) -> None:
    source_pack = absolute(source_pack)
    output_root = absolute(output_root)
    if output_root.exists():
        raise FileExistsError(
            f"refusing to overwrite HIT rejection analysis: {output_root}"
        )
    source_commit = require_clean_origin()
    rows, summary = build_analysis(source_pack)
    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=output_root.name + ".",
        dir=output_root.parent,
    ) as temporary:
        root = Path(temporary)
        (root / "plaintext_margin_analysis.csv").write_bytes(
            render_csv(rows)
        )
        (root / "summary.json").write_bytes(canonical_json(summary))
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "evidence_id": "hit_external_adapter_rejection_analysis_v1",
            "analysis_commit": source_commit,
            "classification": summary["classification"],
            "failure_class": summary["failure_class"],
            "source_manifest_sha256": summary["source_evidence"][
                "manifest_sha256"
            ],
            "source_selection_sha256": summary["source_evidence"][
                "selection_sha256"
            ],
            "summary_sha256": sha256_path(root / "summary.json"),
            "encrypted_executions_added": 0,
            "policy_modifications": 0,
            "paper_claim_allowed": False,
        }
        (root / "manifest.json").write_bytes(canonical_json(manifest))
        (root / "README.md").write_text(
            "# HIT External Candidate Rejection Analysis V1\n\n"
            "Explanatory post-hoc analysis of the frozen seed-0 HIT "
            "candidate rejection. It uses no new encrypted execution and "
            "does not alter any candidate or policy. The original trial "
            "schema preserves aggregate errors but cannot localize the six "
            "violations to sample-key observations. "
            "`paper_claim_allowed=false`.\n",
            encoding="ascii",
        )
        write_checksums(root)
        verify(root, source_pack)
        shutil.move(str(root), output_root)


def verify(
    output_root: Path = DEFAULT_OUTPUT,
    source_pack: Path = SOURCE_PACK,
) -> dict[str, Any]:
    output_root = absolute(output_root)
    source_pack = absolute(source_pack)
    verify_checksums(output_root)
    expected_rows, expected_summary = build_analysis(source_pack)
    if (output_root / "plaintext_margin_analysis.csv").read_bytes() != \
            render_csv(expected_rows):
        raise ValueError("HIT plaintext-margin analysis changed")
    summary = load_json(output_root / "summary.json")
    if summary != expected_summary:
        raise ValueError("HIT rejection summary changed")
    manifest = load_json(output_root / "manifest.json")
    if (
        manifest["schema_version"] != SCHEMA_VERSION
        or manifest["summary_sha256"] != sha256_path(
            output_root / "summary.json"
        )
        or manifest["encrypted_executions_added"] != 0
        or manifest["policy_modifications"] != 0
        or manifest["paper_claim_allowed"] is not False
    ):
        raise ValueError("HIT rejection analysis gate changed")
    return summary


def main() -> int:
    args = parse_args()
    if args.verify:
        summary = verify(args.output_root, args.source_pack)
        print(
            "hit_external_rejection_analysis=VERIFIED "
            f"violations={summary['observed_aggregate']['error_violations']} "
            "encrypted_executions_added=0 paper_claim_allowed=false"
        )
        return 0
    generate(args.source_pack, args.output_root)
    print(
        "hit_external_rejection_analysis=FROZEN "
        f"output={absolute(args.output_root)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
