#!/usr/bin/env python3
"""Freeze the predeclared natural multiclass decision-contract activation study."""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import io
import json
from pathlib import Path


SCHEMA = "flipguard_journal_multiclass_activation_v1"
RESULTS_SCHEMA = "flipguard_journal_multiclass_extension_results_v1"
COMPARATOR_SCHEMA = "flipguard_journal_multiclass_graph_only_comparator_v1"
COMPARATOR_ID = "graph_only_fixed_logit_tolerance_0.001"
COMPARATOR_SOURCE_COMMIT = "2f61bf5b32e19c0031a94dd5f2ad49f2d6634033"
COMPARATOR_BINARY_DIGEST = "sha256:a18a7ae7391f40444b17ca8b945facdb595bec092c8d2afbe8dfd2c3d11d77b9"
PROTOCOL_DIGEST = "sha256:caf39e2b38f8c1a46bb1fece30d68d758b613e2459e51e6af9898e535620b269"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def csv_text(fields: list[str], rows: list[dict]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def parameter_signature(candidate: dict) -> dict:
    params = candidate["parameters"]
    return {
        "path": candidate["path"],
        "log_n": params["log_n"],
        "log_q": params["log_q"],
        "log_p": params["log_p"],
        "log_default_scale": params["log_default_scale"],
    }


def trial_candidate_id(trial: dict) -> str:
    candidate = trial.get("candidate")
    require(isinstance(candidate, dict), "graph-only trial candidate object")
    candidate_id = candidate.get("id")
    require(isinstance(candidate_id, str) and candidate_id, "graph-only trial candidate ID")
    return candidate_id


def summarize_gap_bins(observations: list[dict], boundaries: list[float]) -> list[dict]:
    bins: dict[int, list[dict]] = {index: [] for index in range(1, len(boundaries) + 2)}
    for row in observations:
        gap = float(row["top_two_gap"])
        index = bisect.bisect_left(boundaries, gap) + 1
        bins[index].append(row)
    output = []
    for index, rows in bins.items():
        require(rows, f"empty graph-only gap bin {index}")
        output.append(
            {
                "gap_bin": index,
                "unique_samples": len({row["sample_id"] for row in rows}),
                "fresh_key_observations": len(rows),
                "argmax_flips": sum(bool(row["argmax_flip"]) for row in rows),
                "reserve_policy_rejections": sum(bool(row["reserve_policy_violation"]) for row in rows),
                "min_top_two_gap": format(min(float(row["top_two_gap"]) for row in rows), ".17g"),
                "max_top_two_gap": format(max(float(row["top_two_gap"]) for row in rows), ".17g"),
                "max_minimum_cap_required": format(max(float(row["minimum_cap_required"]) for row in rows), ".17g"),
            }
        )
    return output


def collect(root: Path) -> dict[str, str | list[dict]]:
    result_pack = root / "docs/evidence/journal_multiclass_extension_results_v1"
    result_manifest = load(result_pack / "manifest.json")
    result_summary = load(result_pack / "summary.json")
    require(result_manifest["schema_version"] == RESULTS_SCHEMA, "result evidence schema")

    comparator_root = root / "results/journal_multiclass_extension_v1/comparators/mlp_graph_only_fixed_logit_tolerance_v1"
    comparator = load(comparator_root / "result.json")
    comparator_manifest = load(comparator_root / "run_manifest.json")
    require(comparator["schema_version"] == COMPARATOR_SCHEMA, "comparator result schema")
    require(comparator_manifest["schema_version"] == COMPARATOR_SCHEMA, "comparator manifest schema")
    require(comparator["comparator_id"] == COMPARATOR_ID, "comparator ID")
    require(comparator_manifest["comparator_id"] == COMPARATOR_ID, "comparator manifest ID")
    require(comparator["comparator_source_commit"] == comparator_manifest["comparator_source_commit"], "comparator source commit")
    require(comparator_manifest["comparator_source_commit"] == COMPARATOR_SOURCE_COMMIT, "frozen comparator source")
    require(comparator_manifest["binary_sha256"] == COMPARATOR_BINARY_DIGEST, "frozen comparator binary")
    require(comparator_manifest["protocol_manifest_sha256"] == PROTOCOL_DIGEST, "frozen comparator protocol")
    require(comparator_manifest["no_audit_retuning"] is True, "comparator no-retuning declaration")
    require(comparator_manifest["fresh_key_repeats"] == 3, "comparator key repeats")

    trial = comparator["trial"]
    graph_candidate = comparator["candidate"]
    require(trial_candidate_id(trial) == graph_candidate["id"], "graph-only candidate identity")
    require(trial["key_repeats_completed"] == 3, "graph-only completed key repeats")
    require(trial["encrypted_sample_evaluations"] == 1500, "graph-only sample evaluation accounting")
    require(graph_candidate["security"]["final_admission"] == "PASS", "graph-only Security-V2 admission")

    direct_summary = result_summary["models"]["mlp_100"]["direct_selection"]
    direct_selection = load(
        root / "results/journal_multiclass_extension_v1/encrypted/mnist_mlp_square_784_100_10_v1/selection_result.json"
    )["result"]
    direct_candidate = direct_selection["selected"]
    require(direct_candidate["id"] == direct_summary["candidate_id"], "direct candidate evidence binding")
    require(direct_selection["trials_used"] == 1, "one-shot direct derivation")
    require(direct_selection["trials"][0]["status"] == "SAFE", "one-shot direct status")

    direct_signature = parameter_signature(direct_candidate)
    graph_signature = parameter_signature(graph_candidate)
    literal_changed = direct_signature != graph_signature
    graph_safe = trial["status"] == "SAFE"
    if literal_changed and graph_safe:
        activation_class = "A_LITERAL_EFFECT_SUPPORTED"
        claim_state = "SUPPORTED"
    elif not literal_changed and trial["status"] != direct_selection["trials"][0]["status"]:
        activation_class = "B_ADMISSION_EFFECT_ONLY"
        claim_state = "PARTIALLY_SUPPORTED"
    else:
        activation_class = "C_NO_OBSERVED_ACTIVATION"
        claim_state = "NOT_EVALUATED"

    mlp_preflight = load(root / "results/journal_multiclass_extension_v1/preflight/mlp_configuration_validation.json")
    lenet_preflight = load(root / "results/journal_multiclass_extension_v1/preflight/lenet_configuration_validation.json")
    require(mlp_preflight["graph_only_fixed_tolerance_status"] == "PLAN_OK_SECURITY_ADMITTED", "MLP graph-only preflight")
    require(lenet_preflight["graph_only_fixed_tolerance_status"] == "PLAN_UNSUPPORTED_SECURITY_ENVELOPE", "LeNet graph-only negative result")
    contract = mlp_preflight["decision_aware_plan"]["contract"]["multiclass_decision"]
    fixed_contract = mlp_preflight["graph_only_fixed_tolerance_plan"]["contract"]["multiclass_decision"]
    require(float(contract["protected_top_two_gap"]) > 0, "natural protected gap")
    require(fixed_contract == contract, "graph-only execution must retain the same decision gate")
    graph_policy = mlp_preflight["graph_only_fixed_tolerance_plan"]["policy"]
    require(graph_policy["synthesis_budget_mode"] == "graph_fixed_tolerance", "graph-only budget mode")
    require(float(graph_policy["fixed_output_error_budget"]) == 0.001, "fixed logit tolerance")

    analysis_plan = load(root / "docs/evidence/journal_multiclass_analysis_plan_v1/analysis_plan.json")
    boundaries = analysis_plan["models"]["mlp_100"]["boundary_values"]
    gap_rows = summarize_gap_bins(trial["aggregation"]["observations"], boundaries)

    catalog = load(root / "results/journal_multiclass_extension_v1/encrypted/mnist_mlp_square_784_100_10_v1/catalog_result.json")
    executable = [entry for entry in catalog["entries"] if entry.get("trial") is not None]
    require(len(executable) == 6, "MLP executable catalog entries")
    fastest_executable = min(executable, key=lambda entry: float(entry["trial"]["mean_total_ms"]))
    fastest_safe = min(
        (entry for entry in executable if entry["trial"]["status"] == "SAFE"),
        key=lambda entry: float(entry["trial"]["mean_total_ms"]),
    )

    summary = {
        "schema_version": SCHEMA,
        "study_id": "natural_data_margin_literal_effect",
        "activation_class": activation_class,
        "claim_state": claim_state,
        "scope": "MNIST MLP 784-100-square-10 configuration-validation rows only",
        "direct": {
            "candidate_id": direct_candidate["id"],
            "literal": direct_signature,
            "status": direct_selection["trials"][0]["status"],
            "trials": direct_selection["trials_used"],
            "repairs": direct_selection["repairs"],
            "synthesis_input": "graph plus frozen natural top-two-gap decision contract",
            "protected_top_two_gap": contract["protected_top_two_gap"],
            "per_logit_error_budget": contract["per_logit_error_budget"],
        },
        "graph_only_fixed_tolerance": {
            "candidate_id": graph_candidate["id"],
            "literal": graph_signature,
            "status": trial["status"],
            "fresh_key_runs": trial["key_repeats_completed"],
            "encrypted_sample_evaluations": trial["encrypted_sample_evaluations"],
            "argmax_flips": trial["aggregation"]["argmax_flips"],
            "reserve_policy_rejections": trial["aggregation"]["reserve_policy_violations"],
            "fixed_per_logit_tolerance": graph_policy["fixed_output_error_budget"],
        },
        "literal_changed": literal_changed,
        "explanation": (
            "The frozen natural gap permits a larger per-logit synthesis budget than the fixed 0.001 comparator; "
            "the resulting Security-V2-admitted literals differ."
            if activation_class == "A_LITERAL_EFFECT_SUPPORTED"
            else "No claim beyond the recorded activation class is admitted."
        ),
        "lenet_graph_only": {
            "status": lenet_preflight["graph_only_fixed_tolerance_status"],
            "reason": lenet_preflight["graph_only_fixed_tolerance_failure_reason"],
            "encrypted_execution": 0,
        },
        "one_shot_direct": {
            "mlp_100": "SELECTED_FIRST_TRIAL",
            "lenet5_small": "SELECTED_FIRST_TRIAL",
            "derived_from_frozen_direct_ledger": True,
        },
        "latency_only_no_certification": {
            "scope": "MLP admitted executable catalog profiles",
            "fastest_executable_profile": fastest_executable["static"]["profile_name"],
            "fastest_executable_status_under_decision_gate": fastest_executable["trial"]["status"],
            "fastest_safe_profile": fastest_safe["static"]["profile_name"],
            "same_profile_in_this_scope": fastest_executable["static"]["profile_name"] == fastest_safe["static"]["profile_name"],
            "latency_claim": "DESCRIPTIVE_UNPAIRED_ONLY",
        },
        "prohibited_inference": [
            "universal natural-data activation",
            "LeNet graph-only encrypted comparison",
            "paired speedup from extension timings",
            "global optimality",
        ],
    }

    ablation_rows = [
        {
            "model": "mlp_100",
            "arm": "full_flipguard",
            "static_status": "PLAN_OK_SECURITY_ADMITTED",
            "encrypted_status": direct_selection["trials"][0]["status"],
            "candidate_id": direct_candidate["id"],
            "trials": 1,
            "fresh_key_runs": 3,
            "argmax_flips": direct_selection["trials"][0]["aggregation"]["argmax_flips"],
            "reserve_policy_rejections": direct_selection["trials"][0]["aggregation"]["reserve_policy_violations"],
            "interpretation": "decision-aware synthesis and validation",
        },
        {
            "model": "mlp_100",
            "arm": "graph_only_fixed_tolerance",
            "static_status": "PLAN_OK_SECURITY_ADMITTED",
            "encrypted_status": trial["status"],
            "candidate_id": graph_candidate["id"],
            "trials": 1,
            "fresh_key_runs": 3,
            "argmax_flips": trial["aggregation"]["argmax_flips"],
            "reserve_policy_rejections": trial["aggregation"]["reserve_policy_violations"],
            "interpretation": activation_class,
        },
        {
            "model": "lenet5_small",
            "arm": "graph_only_fixed_tolerance",
            "static_status": lenet_preflight["graph_only_fixed_tolerance_status"],
            "encrypted_status": "NOT_EXECUTED",
            "candidate_id": "",
            "trials": 0,
            "fresh_key_runs": 0,
            "argmax_flips": "",
            "reserve_policy_rejections": "",
            "interpretation": "scientific static negative result",
        },
    ]
    ablation_fields = [
        "model", "arm", "static_status", "encrypted_status", "candidate_id", "trials",
        "fresh_key_runs", "argmax_flips", "reserve_policy_rejections", "interpretation",
    ]
    gap_fields = [
        "gap_bin", "unique_samples", "fresh_key_observations", "argmax_flips",
        "reserve_policy_rejections", "min_top_two_gap", "max_top_two_gap",
        "max_minimum_cap_required",
    ]
    return {
        "activation_summary.json": canonical(summary),
        "ablation_summary.csv": csv_text(ablation_fields, ablation_rows),
        "graph_only_gap_bin_summary.csv": csv_text(gap_fields, gap_rows),
        "input_bindings": [
            {"path": str((result_pack / "manifest.json").relative_to(root)), "sha256": digest(result_pack / "manifest.json")},
            {"path": str((comparator_root / "result.json").relative_to(root)), "sha256": digest(comparator_root / "result.json")},
            {"path": str((comparator_root / "run_manifest.json").relative_to(root)), "sha256": digest(comparator_root / "run_manifest.json")},
            {"path": "results/journal_multiclass_extension_v1/preflight/mlp_configuration_validation.json", "sha256": digest(root / "results/journal_multiclass_extension_v1/preflight/mlp_configuration_validation.json")},
            {"path": "results/journal_multiclass_extension_v1/preflight/lenet_configuration_validation.json", "sha256": digest(root / "results/journal_multiclass_extension_v1/preflight/lenet_configuration_validation.json")},
            {"path": "docs/evidence/journal_multiclass_analysis_plan_v1/analysis_plan.json", "sha256": digest(root / "docs/evidence/journal_multiclass_analysis_plan_v1/analysis_plan.json")},
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs/evidence/journal_multiclass_activation_v1")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / args.output
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing evidence pack {output}")
    try:
        content = collect(root)
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        raise SystemExit("FAIL: " + str(error)) from error
    output.mkdir(parents=True)
    generated = ["activation_summary.json", "ablation_summary.csv", "graph_only_gap_bin_summary.csv"]
    for name in generated:
        (output / name).write_text(content[name], encoding="utf-8")
    manifest = {
        "schema_version": SCHEMA,
        "inputs": content["input_bindings"],
        "generated_files": {name: {"path": name, "sha256": digest(output / name)} for name in generated},
        "frozen_core_modified": False,
        "policy_retuning": 0,
        "audit_based_change": 0,
    }
    (output / "manifest.json").write_text(canonical(manifest), encoding="utf-8")
    names = [*generated, "manifest.json"]
    (output / "SHA256SUMS").write_text(
        "".join(f"{digest(output / name)[7:]}  {name}\n" for name in names), encoding="ascii"
    )
    print(f"wrote {output.relative_to(root)}")
    print("manifest_sha256=" + digest(output / "manifest.json"))


if __name__ == "__main__":
    main()
