#!/usr/bin/env python3
"""Freeze deterministic summaries from journal multiclass encrypted ledgers."""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import io
import json
from collections import defaultdict
from pathlib import Path


SCHEMA = "flipguard_journal_multiclass_extension_results_v1"
PROTOCOL_DIGEST = "sha256:caf39e2b38f8c1a46bb1fece30d68d758b613e2459e51e6af9898e535620b269"
SECURITY_DIGEST = "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
DIRECT_DIGEST = "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
MODELS = {
    "mlp_100": "mnist_mlp_square_784_100_10_v1",
    "lenet5_small": "mnist_lenet5_small_square_v1",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def csv_text(fieldnames: list[str], rows: list[dict]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def label_map(key_run_path: Path, expected_role: str) -> dict[str, int]:
    key_run = load(key_run_path)
    require(key_run["key_run"] == 1, f"{key_run_path}: expected key run 1")
    records = key_run["records"]
    require(len(records) == 500, f"{key_run_path}: expected 500 records")
    require({row["role"] for row in records} == {expected_role}, f"{key_run_path}: role")
    result = {row["sample_id"]: int(row["label"]) for row in records}
    require(len(result) == 500, f"{key_run_path}: sample identities")
    return result


def add_observations(
    rows: list[dict],
    model_name: str,
    model_id: str,
    role: str,
    candidate_id: str,
    trial: dict,
    labels: dict[str, int],
    boundaries: list[float],
) -> None:
    observations = trial["aggregation"]["observations"]
    require(len(observations) == 1500, f"{model_name} {role}: observation count")
    for observation in observations:
        sample_id = observation["sample_id"]
        require(sample_id in labels, f"{model_name} {role}: unknown sample {sample_id}")
        errors = [float(value) for value in observation["per_logit_absolute_error"]]
        top1 = int(observation["plaintext_top_1"])
        top2 = int(observation["plaintext_top_2"])
        gap = float(observation["top_two_gap"])
        pairwise_error = errors[top1] + errors[top2]
        minimum_cap = float(observation["minimum_cap_required"])
        plain_logits = [float(value) for value in observation["plain_logits"]]
        replayed_cap = max(
            (errors[top1] + errors[class_index])
            / (plain_logits[top1] - plain_logits[class_index])
            for class_index in range(len(plain_logits))
            if class_index != top1
        )
        require(abs(minimum_cap - replayed_cap) <= 1e-12, f"{model_name} cap replay")
        rows.append(
            {
                "model_name": model_name,
                "model_id": model_id,
                "role": role,
                "candidate_id": candidate_id,
                "sample_id": sample_id,
                "key_run": int(observation["key_run"]),
                "label": labels[sample_id],
                "plaintext_top_1": top1,
                "plaintext_top_2": top2,
                "ckks_top_1": int(observation["ckks_top_1"]),
                "top_two_gap": format(gap, ".17g"),
                "pairwise_decision_budget": format(float(observation["pairwise_decision_budget"]), ".17g"),
                "pairwise_observed_error": format(pairwise_error, ".17g"),
                "minimum_cap_required": format(minimum_cap, ".17g"),
                "margin_utilization_cap": "0.5",
                "certifiable": str(bool(observation["certifiable"])).lower(),
                "plaintext_tie": str(bool(observation["plaintext_tie"])).lower(),
                "argmax_flip": str(bool(observation["argmax_flip"])).lower(),
                "reserve_policy_pass": str(bool(observation["reserve_policy_pass"])).lower(),
                "reserve_policy_rejection": str(bool(observation["reserve_policy_violation"])).lower(),
                "gap_bin": bisect.bisect_left(boundaries, gap) + 1,
                "plaintext_logits": json.dumps(observation["plain_logits"], separators=(",", ":")),
                "ckks_logits": json.dumps(observation["ckks_logits"], separators=(",", ":")),
                "per_logit_absolute_error": json.dumps(errors, separators=(",", ":")),
            }
        )


def summarize_groups(observations: list[dict], group_fields: list[str]) -> list[dict]:
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for row in observations:
        grouped[tuple(row[field] for field in group_fields)].append(row)
    summaries = []
    for key in sorted(grouped):
        rows = grouped[key]
        summary = dict(zip(group_fields, key))
        summary.update(
            {
                "unique_samples": len({row["sample_id"] for row in rows}),
                "fresh_key_observations": len(rows),
                "argmax_flips": sum(row["argmax_flip"] == "true" for row in rows),
                "reserve_policy_rejections": sum(row["reserve_policy_rejection"] == "true" for row in rows),
                "plaintext_correct": sum(int(row["plaintext_top_1"]) == int(row["label"]) for row in rows),
                "ckks_correct": sum(int(row["ckks_top_1"]) == int(row["label"]) for row in rows),
                "max_pairwise_observed_error": format(max(float(row["pairwise_observed_error"]) for row in rows), ".17g"),
                "max_minimum_cap_required": format(max(float(row["minimum_cap_required"]) for row in rows), ".17g"),
                "min_top_two_gap": format(min(float(row["top_two_gap"]) for row in rows), ".17g"),
                "max_top_two_gap": format(max(float(row["top_two_gap"]) for row in rows), ".17g"),
            }
        )
        summaries.append(summary)
    return summaries


def key_run_bindings(root: Path, result_root: Path) -> list[dict]:
    bindings = []
    for path in sorted(result_root.rglob("*.json")):
        require(not path.name.endswith(".tmp"), f"temporary ledger present: {path}")
        bindings.append({"path": str(path.relative_to(root)), "sha256": sha256(path)})
    return bindings


def collect(root: Path, execution_source_commit: str) -> dict[str, object]:
    encrypted = root / "results/journal_multiclass_extension_v1/encrypted"
    analysis_plan_path = root / "docs/evidence/journal_multiclass_analysis_plan_v1/analysis_plan.json"
    analysis_plan = load(analysis_plan_path)
    observations: list[dict] = []
    summaries = {}
    latency_rows = []
    negative_results = []
    raw_inputs = {}
    validation_id_sets = {}
    audit_id_sets = {}

    for model_name, model_id in MODELS.items():
        result_root = encrypted / model_id
        selection_path = result_root / "selection_result.json"
        audit_path = result_root / "locked_audit_result.json"
        catalog_path = result_root / "catalog_result.json"
        for path in [selection_path, audit_path, catalog_path]:
            require(path.is_file(), f"missing completed result {path}")
        selection = load(selection_path)
        audit = load(audit_path)
        catalog = load(catalog_path)
        for label, envelope in [("selection", selection), ("audit", audit), ("catalog", catalog)]:
            require(envelope["source_commit"] == execution_source_commit, f"{model_name} {label} source commit")

        result = selection["result"]
        require(result["outcome"] == "SELECTED", f"{model_name}: selection outcome")
        require(result["selected"] is not None, f"{model_name}: selected literal")
        selected = result["selected"]
        require(selected["security"]["final_admission"] == "PASS", f"{model_name}: security admission")
        require(result["plan"]["direct_policy_digest"] == DIRECT_DIGEST, f"{model_name}: direct policy")
        require(result["plan"]["security_policy_digest"] == SECURITY_DIGEST, f"{model_name}: security policy")
        require(result["encrypted_key_runs"] == 3 * result["trials_used"], f"{model_name}: selection key accounting")
        require(result["encrypted_sample_evaluations"] == 500 * result["encrypted_key_runs"], f"{model_name}: selection evaluation accounting")
        selected_trial = result["trials"][-1]
        require(selected_trial["candidate"]["id"] == selected["id"], f"{model_name}: selected trial identity")

        audit_result = audit["result"]
        require(audit_result["candidate_identity_match"] is True, f"{model_name}: audit identity")
        require(audit_result["retuning_count"] == 0, f"{model_name}: audit retuning")
        require(audit_result["selected_candidate"]["id"] == selected["id"], f"{model_name}: audit literal")
        audit_trial = audit_result["trial"]
        require(audit_trial["key_repeats_completed"] == 3, f"{model_name}: audit keys")
        require(audit_trial["encrypted_sample_evaluations"] == 1500, f"{model_name}: audit evaluations")

        trial_root = result_root / f"trial_01_{selected['id']}"
        validation_key = trial_root / "key_run_01.json"
        audit_key = result_root / "locked_audit/key_run_01.json"
        validation_labels = label_map(validation_key, "configuration_validation")
        audit_labels = label_map(audit_key, "locked_audit")
        validation_ids = set(validation_labels)
        audit_ids = set(audit_labels)
        require(not validation_ids.intersection(audit_ids), f"{model_name}: validation/audit overlap")
        validation_id_sets[model_name] = validation_ids
        audit_id_sets[model_name] = audit_ids

        boundaries = analysis_plan["models"][model_name]["boundary_values"]
        add_observations(
            observations,
            model_name,
            model_id,
            "configuration_validation",
            selected["id"],
            selected_trial,
            validation_labels,
            boundaries,
        )
        add_observations(
            observations,
            model_name,
            model_id,
            "locked_audit",
            selected["id"],
            audit_trial,
            audit_labels,
            boundaries,
        )

        require(catalog["formal_denominator"] == 7, f"{model_name}: catalog denominator")
        require(len(catalog["entries"]) == 7, f"{model_name}: catalog entries")
        require(catalog["safe"] + catalog["rejected"] + catalog["failed"] + catalog["plan_unsupported"] == 7, f"{model_name}: catalog accounting")
        expected_encrypted = 6 if model_name == "mlp_100" else 0
        require(catalog["encrypted_candidates"] == expected_encrypted, f"{model_name}: catalog execution count")
        expected_unsupported = 1 if model_name == "mlp_100" else 7
        require(catalog["plan_unsupported"] == expected_unsupported, f"{model_name}: catalog unsupported count")

        summaries[model_name] = {
            "model_id": model_id,
            "plaintext_accuracy": {
                "configuration_validation": selected_trial["plaintext_accuracy"],
                "locked_audit": audit_trial["plaintext_accuracy"],
            },
            "direct_selection": {
                "outcome": result["outcome"],
                "candidate_id": selected["id"],
                "candidate_parameters": selected["parameters"],
                "security": selected["security"],
                "trials": result["trials_used"],
                "repairs": result["repairs"],
                "fresh_key_runs": result["encrypted_key_runs"],
                "encrypted_sample_evaluations": result["encrypted_sample_evaluations"],
                "status": selected_trial["status"],
                "argmax_flips": selected_trial["aggregation"]["argmax_flips"],
                "reserve_policy_rejections": selected_trial["aggregation"]["reserve_policy_violations"],
            },
            "locked_audit": {
                "status": audit_trial["status"],
                "candidate_identity_match": audit_result["candidate_identity_match"],
                "retuning_count": audit_result["retuning_count"],
                "fresh_key_runs": audit_trial["key_repeats_completed"],
                "encrypted_sample_evaluations": audit_trial["encrypted_sample_evaluations"],
                "argmax_flips": audit_trial["aggregation"]["argmax_flips"],
                "reserve_policy_rejections": audit_trial["aggregation"]["reserve_policy_violations"],
            },
            "security_v2_bounded_catalog": {
                "formal_denominator": catalog["formal_denominator"],
                "encrypted_candidates": catalog["encrypted_candidates"],
                "safe": catalog["safe"],
                "rejected": catalog["rejected"],
                "failed": catalog["failed"],
                "plan_unsupported": catalog["plan_unsupported"],
                "fastest_safe_profile": catalog.get("fastest_safe_profile", ""),
                "fastest_safe_mean_total_ms": catalog.get("fastest_safe_mean_total_ms", 0),
            },
        }

        for arm, role, trial in [
            ("direct_selected", "configuration_validation", selected_trial),
            ("direct_selected", "locked_audit", audit_trial),
        ]:
            latency_rows.append(
                {
                    "model_name": model_name,
                    "model_id": model_id,
                    "arm": arm,
                    "profile": selected["id"],
                    "role": role,
                    "status": trial["status"],
                    "fresh_key_runs": trial["key_repeats_completed"],
                    "mean_total_ms": format(float(trial["mean_total_ms"]), ".17g"),
                    "median_total_ms": format(float(trial["median_total_ms"]), ".17g"),
                    "p95_total_ms": format(float(trial["p95_total_ms"]), ".17g"),
                    "mean_eval_only_ms": format(float(trial["mean_eval_only_ms"]), ".17g"),
                    "comparison_status": "DESCRIPTIVE_UNPAIRED_EXTENSION_TIMING",
                }
            )
        for entry in catalog["entries"]:
            static = entry["static"]
            if entry.get("trial") is None:
                latency_rows.append(
                    {
                        "model_name": model_name,
                        "model_id": model_id,
                        "arm": "security_v2_bounded_catalog",
                        "profile": static["profile_name"],
                        "role": "configuration_validation",
                        "status": static["static_status"],
                        "fresh_key_runs": 0,
                        "mean_total_ms": "",
                        "median_total_ms": "",
                        "p95_total_ms": "",
                        "mean_eval_only_ms": "",
                        "comparison_status": "STATIC_PLAN_UNSUPPORTED",
                    }
                )
            else:
                trial = entry["trial"]
                latency_rows.append(
                    {
                        "model_name": model_name,
                        "model_id": model_id,
                        "arm": "security_v2_bounded_catalog",
                        "profile": static["profile_name"],
                        "role": "configuration_validation",
                        "status": trial["status"],
                        "fresh_key_runs": trial["key_repeats_completed"],
                        "mean_total_ms": format(float(trial["mean_total_ms"]), ".17g"),
                        "median_total_ms": format(float(trial["median_total_ms"]), ".17g"),
                        "p95_total_ms": format(float(trial["p95_total_ms"]), ".17g"),
                        "mean_eval_only_ms": format(float(trial["mean_eval_only_ms"]), ".17g"),
                        "comparison_status": "DESCRIPTIVE_UNPAIRED_EXTENSION_TIMING",
                    }
                )

        preflight = load(root / f"results/journal_multiclass_extension_v1/preflight/{'mlp' if model_name == 'mlp_100' else 'lenet'}_configuration_validation.json")
        graph_only_status = preflight["graph_only_fixed_tolerance_status"]
        if graph_only_status != "PLAN_OK_SECURITY_ADMITTED":
            negative_results.append(
                {
                    "model_name": model_name,
                    "result_class": graph_only_status,
                    "component": "graph_only_fixed_logit_tolerance_0.001",
                    "reason": preflight["graph_only_fixed_tolerance_failure_reason"],
                    "policy_modified": False,
                }
            )
        if catalog["plan_unsupported"]:
            negative_results.append(
                {
                    "model_name": model_name,
                    "result_class": "BOUNDED_CATALOG_PLAN_UNSUPPORTED",
                    "component": "security_v2_bounded_catalog",
                    "reason": f"{catalog['plan_unsupported']} of {catalog['formal_denominator']} admitted profiles lack the required Q levels",
                    "policy_modified": False,
                }
            )

        raw_inputs[model_name] = key_run_bindings(root, result_root)

    require(validation_id_sets["mlp_100"] == validation_id_sets["lenet5_small"], "models use different validation samples")
    require(audit_id_sets["mlp_100"] == audit_id_sets["lenet5_small"], "models use different audit samples")

    class_rows = summarize_groups(observations, ["model_name", "role", "label"])
    gap_rows = summarize_groups(observations, ["model_name", "role", "gap_bin"])
    total_direct_trials = sum(summary["direct_selection"]["trials"] for summary in summaries.values())
    total_direct_repairs = sum(summary["direct_selection"]["repairs"] for summary in summaries.values())
    total_direct_key_runs = sum(
        summary["direct_selection"]["fresh_key_runs"] + summary["locked_audit"]["fresh_key_runs"]
        for summary in summaries.values()
    )
    total_direct_evals = sum(
        summary["direct_selection"]["encrypted_sample_evaluations"]
        + summary["locked_audit"]["encrypted_sample_evaluations"]
        for summary in summaries.values()
    )
    total_catalog_keys = sum(int(row["fresh_key_runs"]) for row in latency_rows if row["arm"] == "security_v2_bounded_catalog")
    catalog_denominator = sum(summary["security_v2_bounded_catalog"]["formal_denominator"] for summary in summaries.values())
    catalog_executable = sum(summary["security_v2_bounded_catalog"]["encrypted_candidates"] for summary in summaries.values())
    summary = {
        "schema_version": SCHEMA,
        "execution_source_commit": execution_source_commit,
        "policy_retuning": 0,
        "audit_retuning": 0,
        "models": summaries,
        "combined": {
            "models": 2,
            "configuration_validation_samples_per_model": 500,
            "locked_audit_samples_per_model": 500,
            "direct_trials": total_direct_trials,
            "direct_repairs": total_direct_repairs,
            "direct_selection_and_audit_key_runs": total_direct_key_runs,
            "direct_selection_and_audit_encrypted_sample_evaluations": total_direct_evals,
            "security_v2_bounded_catalog_denominator": catalog_denominator,
            "security_v2_bounded_catalog_encrypted_candidates": catalog_executable,
            "security_v2_bounded_catalog_key_runs": total_catalog_keys,
            "candidate_space_screening_reduction": 1.0 - total_direct_trials / catalog_denominator,
            "encrypted_executable_trial_reduction": 1.0 - total_direct_trials / catalog_executable,
            "bounded_catalog_fastest_safe_model_coverage": "1/2",
            "argmax_flips": sum(
                summary[role]["argmax_flips"]
                for summary in summaries.values()
                for role in ["direct_selection", "locked_audit"]
            ),
            "reserve_policy_rejections": sum(
                summary[role]["reserve_policy_rejections"]
                for summary in summaries.values()
                for role in ["direct_selection", "locked_audit"]
            ),
        },
        "latency_claim_status": "DESCRIPTIVE_UNPAIRED_FOR_JOURNAL_EXTENSION; core RC2 paired claim is unchanged",
        "negative_results": negative_results,
        "claim_scope": "two frozen MNIST standard-model adapters and 1,000 finite encrypted rows; not arbitrary packed CNN support",
    }

    observation_fields = [
        "model_name", "model_id", "role", "candidate_id", "sample_id", "key_run", "label",
        "plaintext_top_1", "plaintext_top_2", "ckks_top_1", "top_two_gap",
        "pairwise_decision_budget", "pairwise_observed_error", "minimum_cap_required",
        "margin_utilization_cap", "certifiable", "plaintext_tie", "argmax_flip",
        "reserve_policy_pass", "reserve_policy_rejection", "gap_bin", "plaintext_logits",
        "ckks_logits", "per_logit_absolute_error",
    ]
    class_fields = [
        "model_name", "role", "label", "unique_samples", "fresh_key_observations",
        "argmax_flips", "reserve_policy_rejections", "plaintext_correct", "ckks_correct",
        "max_pairwise_observed_error", "max_minimum_cap_required", "min_top_two_gap", "max_top_two_gap",
    ]
    gap_fields = [
        "model_name", "role", "gap_bin", "unique_samples", "fresh_key_observations",
        "argmax_flips", "reserve_policy_rejections", "plaintext_correct", "ckks_correct",
        "max_pairwise_observed_error", "max_minimum_cap_required", "min_top_two_gap", "max_top_two_gap",
    ]
    latency_fields = [
        "model_name", "model_id", "arm", "profile", "role", "status", "fresh_key_runs",
        "mean_total_ms", "median_total_ms", "p95_total_ms", "mean_eval_only_ms", "comparison_status",
    ]
    return {
        "summary.json": canonical_json(summary),
        "observations.csv": csv_text(observation_fields, observations),
        "class_summary.csv": csv_text(class_fields, class_rows),
        "gap_bin_summary.csv": csv_text(gap_fields, gap_rows),
        "latency_summary.csv": csv_text(latency_fields, sorted(latency_rows, key=lambda row: (row["model_name"], row["arm"], row["profile"], row["role"]))),
        "negative_results.json": canonical_json({"schema_version": SCHEMA, "results": negative_results}),
        "raw_inputs": raw_inputs,
        "analysis_plan_binding": {"path": str(analysis_plan_path.relative_to(root)), "sha256": sha256(analysis_plan_path)},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-source-commit", required=True)
    parser.add_argument(
        "--output",
        default="docs/evidence/journal_multiclass_extension_results_v1",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / args.output
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing evidence pack {output}")
    try:
        collected = collect(root, args.execution_source_commit)
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        raise SystemExit("FAIL: " + str(error)) from error
    output.mkdir(parents=True)
    generated_names = [
        "summary.json", "observations.csv", "class_summary.csv", "gap_bin_summary.csv",
        "latency_summary.csv", "negative_results.json",
    ]
    for name in generated_names:
        (output / name).write_text(collected[name], encoding="utf-8")
    manifest = {
        "schema_version": SCHEMA,
        "execution_source_commit": args.execution_source_commit,
        "security_policy_digest": SECURITY_DIGEST,
        "direct_policy_digest": DIRECT_DIGEST,
        "protocol_manifest_digest": PROTOCOL_DIGEST,
        "analysis_plan": collected["analysis_plan_binding"],
        "raw_inputs": collected["raw_inputs"],
        "generated_files": {
            name: {"path": name, "sha256": sha256(output / name)} for name in generated_names
        },
        "frozen_core_modified": False,
        "policy_retuning": 0,
    }
    (output / "manifest.json").write_text(canonical_json(manifest), encoding="utf-8")
    checksum_names = [*generated_names, "manifest.json"]
    checksum_lines = [f"{sha256(output / name)[7:]}  {name}" for name in checksum_names]
    (output / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="ascii")
    print(f"wrote {output.relative_to(root)}")
    print("manifest_sha256=" + sha256(output / "manifest.json"))


if __name__ == "__main__":
    main()
