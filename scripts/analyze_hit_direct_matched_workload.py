#!/usr/bin/env python3
"""Freeze a no-rerun matched-workload diagnostic for direct and AWS HIT."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DEFAULT = (
    REPO_ROOT / "docs/evidence/hit_direct_matched_workload_v1"
)
DIRECT_SELECTION = (
    REPO_ROOT
    / "docs/evidence/direct_locked_audit_seed0_development_v1"
    / "inputs/selections/seed0__iris_binary__linear_poly3.json"
)
DIRECT_AUDIT = (
    REPO_ROOT
    / "docs/evidence/direct_locked_audit_seed0_development_v1"
    / "outputs/audit_results/seed0__iris_binary__linear_poly3.json"
)
DIRECT_MANIFEST = (
    REPO_ROOT
    / "docs/evidence/direct_locked_audit_seed0_development_v1/manifest.json"
)
FINAL_MANIFEST = (
    REPO_ROOT / "docs/evidence/final_confirmatory_suite_v1/manifest.json"
)
HIT_SELECTION = (
    REPO_ROOT / "docs/evidence/hit_external_adapter_replay_v1/run/selection.json"
)
HIT_RUN_MANIFEST = (
    REPO_ROOT
    / "docs/evidence/hit_external_adapter_replay_v1/run/run_manifest.json"
)
HIT_MANIFEST = (
    REPO_ROOT / "docs/evidence/hit_external_adapter_replay_v1/manifest.json"
)
HIT_ANALYSIS_MANIFEST = (
    REPO_ROOT
    / "docs/evidence/hit_external_adapter_rejection_analysis_v1/manifest.json"
)

EXPECTED_SOURCE_DIGESTS = {
    DIRECT_SELECTION: (
        "sha256:df20396b04f3fae71c518e75a26ad9e18cd0007fd64d3d32175ed6a8561d9842"
    ),
    DIRECT_AUDIT: (
        "sha256:b2bffbab11324a9cb55953f5eb8c545d0d203460ce7021cd0171b25beb6abc80"
    ),
    DIRECT_MANIFEST: (
        "sha256:40e054b9b1317c5af1a2e177ea3068878ef9d89b9d3afae5aeffaabc2ab3b8b6"
    ),
    FINAL_MANIFEST: (
        "sha256:2d10bf8001ede604c195393bcb565e7f873d2b28d9248abdf6b2d7ac90ab85f9"
    ),
    HIT_SELECTION: (
        "sha256:7e6c85feed9081d1bd329e147f3ba72a7bc8b065f0d8eed29fa2cf82d599c129"
    ),
    HIT_RUN_MANIFEST: (
        "sha256:482e852770a49768d8e695fb1dc6ae04cb15e58ac509db9772d67e66e45b3a0a"
    ),
    HIT_MANIFEST: (
        "sha256:eff6b7270744d6cc699c05eb86c64398d2cfe2354ef810daae5d0e20d3de1986"
    ),
    HIT_ANALYSIS_MANIFEST: (
        "sha256:cdf659d54515e4bddafc0bb59daefb6291c18120eeef0902f2d2cb08ad99293a"
    ),
}


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


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label}: got {actual!r}, expected {expected!r}")


def require_close(
    actual: float, expected: float, tolerance: float, label: str
) -> None:
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance):
        raise ValueError(
            f"{label}: got {actual!r}, expected {expected!r}, "
            f"abs_tol={tolerance}"
        )


def write_checksums(root: Path) -> None:
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name == "SHA256SUMS":
            continue
        rows.append(
            f"{sha256_path(path).removeprefix('sha256:')}  "
            f"{path.relative_to(root).as_posix()}"
        )
    (root / "SHA256SUMS").write_text("\n".join(rows) + "\n", encoding="ascii")


def verify_checksums(root: Path) -> None:
    checksum_path = root / "SHA256SUMS"
    expected = {}
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        digest, relative = line.split("  ", 1)
        expected[relative] = "sha256:" + digest
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    require_equal(actual_paths, set(expected), "checksum file set")
    for relative, digest in expected.items():
        require_equal(
            sha256_path(root / relative), digest, f"checksum {relative}"
        )


def verify_source_digests() -> dict[str, str]:
    records = {}
    for path, expected in EXPECTED_SOURCE_DIGESTS.items():
        actual = sha256_path(path)
        require_equal(actual, expected, f"source digest {path}")
        records[path.relative_to(REPO_ROOT).as_posix()] = actual
    return records


def candidate_arm(
    arm_id: str,
    provider: str,
    trial: dict[str, Any],
    *,
    selection_outcome: str,
    locked_audit_outcome: str,
    locked_audit_retuning: int,
) -> dict[str, Any]:
    candidate = trial["candidate"]
    parameters = candidate["parameters"]
    security = candidate["security"]
    return {
        "arm_id": arm_id,
        "provider": provider,
        "candidate_id": candidate["id"],
        "path": candidate["path"],
        "log_n": parameters["log_n"],
        "log_q": security["log_q"],
        "log_p": security["log_p"],
        "log_qp": security["log_qp"],
        "log_default_scale": parameters["log_default_scale"],
        "required_rescale_levels": candidate["required_rescale_levels"],
        "security_v2_admission": security["final_admission"],
        "security_headroom_bits": security["headroom_bits"],
        "candidate_trials": 1,
        "fresh_key_runs": trial["key_repeats_completed"],
        "selection_status": trial["status"],
        "selection_outcome": selection_outcome,
        "decision_flips": trial["decision_flips"],
        "error_violations": trial["error_violations"],
        "max_observed_error": trial["max_observed_error"],
        "max_normalized_budget_usage": trial["max_error_budget_usage"],
        "mean_total_ms": trial["mean_total_ms"],
        "median_total_ms": trial["median_total_ms"],
        "p95_total_ms": trial["p95_total_ms"],
        "locked_audit_outcome": locked_audit_outcome,
        "locked_audit_retuning": locked_audit_retuning,
    }


def build_analysis() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    direct = load_json(DIRECT_SELECTION)
    direct_audit = load_json(DIRECT_AUDIT)
    hit = load_json(HIT_SELECTION)
    hit_run = load_json(HIT_RUN_MANIFEST)
    hit_manifest = load_json(HIT_MANIFEST)

    direct_contract = direct["plan"]["contract"]
    hit_contract = hit["validation_contract"]
    require_equal(
        direct_contract["workload_id"],
        hit_contract["workload_id"],
        "workload identity",
    )
    require_equal(
        direct_contract["dataset_id"],
        hit_contract["dataset_id"],
        "dataset identity",
    )
    require_equal(
        direct_contract["model_id"],
        hit_contract["model_id"],
        "model identity",
    )
    require_equal(
        direct_contract["split_id"],
        hit_contract["split_id"],
        "split identity",
    )
    require_equal(
        direct_contract["model_artifact"]["sha256"],
        hit_contract["model_artifact"]["sha256"],
        "model digest identity",
    )
    require_equal(
        direct_contract["source_data"]["sha256"],
        hit_contract["validation_data"]["sha256"],
        "raw validation source identity",
    )
    require_equal(
        direct_contract["graph"], hit_contract["graph"], "graph identity"
    )
    require_equal(
        direct["plan"]["security_policy_digest"],
        hit["bound_candidate"]["security_policy_digest"],
        "Security V2 policy identity",
    )
    require_equal(
        direct["plan"]["direct_policy_digest"],
        hit_run["direct_policy_digest"],
        "Direct V2 policy identity",
    )

    exact_decision_fields = (
        "threshold",
        "margin_floor",
        "safety_factor",
        "validation_samples",
        "certifiable_samples",
        "ambiguous_samples",
    )
    for field in exact_decision_fields:
        require_equal(
            direct_contract["decision"][field],
            hit_contract["decision"][field],
            f"decision field {field}",
        )
    numeric_decision_fields = ("protected_margin", "output_error_budget")
    decision_deltas = {}
    for field in numeric_decision_fields:
        direct_value = float(direct_contract["decision"][field])
        hit_value = float(hit_contract["decision"][field])
        require_close(direct_value, hit_value, 1e-12, field)
        decision_deltas[field] = abs(direct_value - hit_value)

    direct_trial = direct["trials"][-1]
    hit_trial = hit["trial"]
    require_equal(direct["outcome"], "SELECTED", "direct selection outcome")
    require_equal(direct_trial["status"], "SAFE", "direct selection status")
    require_equal(hit["outcome"], "NO_SAFE", "HIT selection outcome")
    require_equal(hit_trial["status"], "REJECTED", "HIT selection status")
    require_equal(
        direct_audit["outcome"], "LOCKED_AUDIT_PASS", "direct audit outcome"
    )
    require_equal(
        direct_audit["retuning_performed"], False, "direct audit retuning"
    )
    require_equal(
        hit_manifest["locked_audit"]["key_runs"], 0, "HIT audit key runs"
    )
    require_equal(
        hit_manifest["locked_audit"]["retuning"], 0, "HIT audit retuning"
    )

    arms = [
        candidate_arm(
            "flipguard_direct_v2",
            "direct_synthesizer",
            direct_trial,
            selection_outcome=direct["outcome"],
            locked_audit_outcome=direct_audit["outcome"],
            locked_audit_retuning=0,
        ),
        candidate_arm(
            "aws_hit_source_replay_v1",
            "source_replayed_public_parameter_selector",
            hit_trial,
            selection_outcome=hit["outcome"],
            locked_audit_outcome="NOT_RUN_SELECTION_REJECTED",
            locked_audit_retuning=0,
        ),
    ]
    direct_arm, hit_arm = arms
    ratios = {
        "hit_over_direct_max_observed_error": (
            hit_arm["max_observed_error"] / direct_arm["max_observed_error"]
        ),
        "hit_over_direct_max_normalized_budget_usage": (
            hit_arm["max_normalized_budget_usage"]
            / direct_arm["max_normalized_budget_usage"]
        ),
        "hit_over_direct_mean_total_ms_unpaired": (
            hit_arm["mean_total_ms"] / direct_arm["mean_total_ms"]
        ),
        "hit_over_direct_median_total_ms_unpaired": (
            hit_arm["median_total_ms"] / direct_arm["median_total_ms"]
        ),
        "hit_over_direct_p95_total_ms_unpaired": (
            hit_arm["p95_total_ms"] / direct_arm["p95_total_ms"]
        ),
    }
    summary = {
        "schema_version": "flipguard_hit_direct_matched_workload_summary_v1",
        "classification": "UNPAIRED_POST_HOC_MATCHED_WORKLOAD_DIAGNOSTIC",
        "workload": {
            "workload_id": direct_contract["workload_id"],
            "dataset_id": direct_contract["dataset_id"],
            "model_id": direct_contract["model_id"],
            "split_id": direct_contract["split_id"],
            "validation_rows": direct_contract["decision"][
                "validation_samples"
            ],
            "fresh_key_runs_per_arm": 3,
        },
        "identity": {
            "raw_validation_source_byte_identical": True,
            "raw_validation_source_sha256": direct_contract["source_data"][
                "sha256"
            ],
            "model_byte_identical": True,
            "model_sha256": direct_contract["model_artifact"]["sha256"],
            "graph_semantics_identical": True,
            "threshold_alpha_margin_floor_identical": True,
            "decision_numeric_max_abs_delta": max(decision_deltas.values()),
            "decision_numeric_tolerance": 1e-12,
            "prepared_artifact_identity": (
                "NOT_APPLICABLE_HIT_CONTRACT_BINDS_RAW_SOURCE_ARTIFACT"
            ),
            "comparison_scope": (
                "SAME_SOURCE_WORKLOAD_INDEPENDENT_ENCRYPTED_RUNS"
            ),
        },
        "arms": arms,
        "descriptive_ratios": ratios,
        "interpretation": {
            "decision_gate_observation": (
                "the direct literal is SAFE while the source-replayed HIT "
                "literal is REJECTED on the same raw validation workload"
            ),
            "locked_audit_boundary": (
                "direct replay passes; HIT audit is not run because "
                "validation is REJECTED"
            ),
            "causal_parameter_claim_allowed": False,
            "paired_latency_claim_allowed": False,
            "reason": (
                "the two arms were executed in separate processes at "
                "different times without paired randomized order or shared "
                "fresh-key draws"
            ),
        },
        "encrypted_executions_added": 0,
        "policy_modifications": 0,
        "paper_claim_allowed": False,
    }
    return summary, arms


def write_comparison_csv(path: Path, arms: list[dict[str, Any]]) -> None:
    fields = list(arms[0])
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(arms)


def freeze(output: Path, analysis_commit: str) -> None:
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite matched-workload evidence: {output}"
        )
    source_digests = verify_source_digests()
    summary, arms = build_analysis()
    output.mkdir(parents=True)
    (output / "summary.json").write_bytes(canonical_json(summary))
    write_comparison_csv(output / "comparison.csv", arms)
    manifest = {
        "schema_version": "flipguard_hit_direct_matched_workload_evidence_v1",
        "evidence_id": "hit_direct_matched_workload_v1",
        "classification": summary["classification"],
        "analysis_commit": analysis_commit,
        "source_digests": source_digests,
        "summary_sha256": sha256_path(output / "summary.json"),
        "comparison_sha256": sha256_path(output / "comparison.csv"),
        "claim_states": {
            "matched_workload_provider_comparison": "PARTIALLY_SUPPORTED",
            "decision_integrity_gate_value": "PARTIALLY_SUPPORTED",
            "encrypted_external_candidate_certification": "BLOCKED",
            "unpaired_latency_claim": "BLOCKED",
            "hit_candidate_quality": "NOT_EVALUATED",
        },
        "encrypted_executions_added": 0,
        "policy_modifications": 0,
        "paper_claim_allowed": False,
        "block_reason": (
            "single development workload and independent unpaired encrypted "
            "runs cannot establish HIT quality, causal parameter effects, "
            "latency speedup, or general external-provider performance"
        ),
    }
    (output / "manifest.json").write_bytes(canonical_json(manifest))
    readme = """# HIT-Direct Matched-Workload Diagnostic V1

This no-rerun post-hoc diagnostic compares the frozen FlipGuard direct and
source-replayed AWS HIT results on the same raw seed-0 iris/linear validation
artifact. Model, raw source, graph, threshold, alpha, and margin floor match.

The direct arm is SAFE and passes locked audit. The HIT arm is REJECTED and is
not audited. Timing ratios are unpaired diagnostics only; no speedup or causal
parameter claim is allowed.

`paper_claim_allowed=false`.
"""
    (output / "README.md").write_text(readme, encoding="ascii")
    write_checksums(output)


def compare_trees(left: Path, right: Path) -> None:
    left_files = {
        path.relative_to(left).as_posix(): sha256_path(path)
        for path in left.rglob("*")
        if path.is_file()
    }
    right_files = {
        path.relative_to(right).as_posix(): sha256_path(path)
        for path in right.rglob("*")
        if path.is_file()
    }
    require_equal(left_files, right_files, "deterministic rebuild")


def verify(output: Path = OUTPUT_DEFAULT) -> dict[str, Any]:
    verify_checksums(output)
    manifest = load_json(output / "manifest.json")
    require_equal(
        manifest["schema_version"],
        "flipguard_hit_direct_matched_workload_evidence_v1",
        "evidence schema",
    )
    require_equal(
        manifest["source_digests"],
        verify_source_digests(),
        "source digest bindings",
    )
    require_equal(
        manifest["summary_sha256"],
        sha256_path(output / "summary.json"),
        "summary digest",
    )
    require_equal(
        manifest["comparison_sha256"],
        sha256_path(output / "comparison.csv"),
        "comparison digest",
    )
    require_equal(
        manifest["paper_claim_allowed"], False, "paper claim admission"
    )
    require_equal(
        manifest["encrypted_executions_added"],
        0,
        "encrypted executions added",
    )
    require_equal(
        manifest["policy_modifications"], 0, "policy modifications"
    )
    summary = load_json(output / "summary.json")
    expected_summary, _ = build_analysis()
    require_equal(summary, expected_summary, "recomputed summary")
    require_equal(
        summary["interpretation"]["paired_latency_claim_allowed"],
        False,
        "paired latency boundary",
    )
    with tempfile.TemporaryDirectory(
        prefix="flipguard-hit-direct-matched-",
        dir="/tmp",
    ) as temporary:
        rebuilt = Path(temporary) / "rebuilt"
        freeze(rebuilt, manifest["analysis_commit"])
        compare_trees(output, rebuilt)
    return manifest


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
            "hit_direct_matched_workload=VERIFIED "
            f"classification={manifest['classification']} "
            "paper_claim_allowed=false"
        )
        return
    if not args.analysis_commit:
        raise ValueError("--analysis-commit is required when freezing")
    freeze(output, args.analysis_commit)
    print(f"hit_direct_matched_workload=FROZEN output={output}")


if __name__ == "__main__":
    main()
