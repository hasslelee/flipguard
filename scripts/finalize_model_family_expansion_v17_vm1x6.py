#!/usr/bin/env python3
"""Build the final VM1x6 V17 evidence, tables, figures, and claim decision."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import shutil
import statistics
import subprocess
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def write_json(path: Path, value: object) -> None:
    write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def number(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    lo, hi = math.floor(position), math.ceil(position)
    return ordered[lo] if lo == hi else ordered[lo] * (hi - position) + ordered[hi] * (position - lo)


def svg_bars(path: Path, title: str, rows: list[tuple[str, float]], suffix: str = "") -> None:
    width, height = 1100, max(300, 90 + 38 * len(rows))
    max_value = max((abs(value) for _, value in rows), default=1.0) or 1.0
    bars = []
    for index, (label, value) in enumerate(rows):
        y = 70 + index * 38
        bar = 700 * abs(value) / max_value
        color = "#1f6feb" if value >= 0 else "#d1242f"
        bars.append(f'<text x="20" y="{y+18}" font-size="14">{label}</text><rect x="330" y="{y}" width="{bar:.2f}" height="24" fill="{color}"/><text x="{340+bar:.2f}" y="{y+18}" font-size="13">{value:.6g}{suffix}</text>')
    write(path, f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><title>{title}</title><rect width="100%" height="100%" fill="white"/><text x="20" y="35" font-family="sans-serif" font-size="22" font-weight="bold">{title}</text><g font-family="sans-serif">{"".join(bars)}</g></svg>\n''')


def copy_table(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    run_root = ROOT / "results/model_family_expansion_v17/runs" / args.run_id
    report_root = ROOT / "docs/reports/model_family_expansion_v17/runs" / args.run_id
    evidence_root = ROOT / "docs/evidence/model_family_expansion_v17/runs" / args.run_id
    final_results = ROOT / "results/model_family_expansion_v17/final_vm1x6"
    final_evidence = ROOT / "docs/evidence/model_family_expansion_v17/final_vm1x6"
    final_reports = ROOT / "docs/reports/model_family_expansion_v17/final_vm1x6"
    for path in (report_root, evidence_root, final_results, final_evidence, final_reports):
        path.mkdir(parents=True, exist_ok=True)
    verify = ["python3", "scripts/verify_model_family_expansion_v17_vm1x6.py", "--run-id", args.run_id]
    if not args.allow_partial:
        verify.append("--require-complete")
    subprocess.run(verify, cwd=ROOT, check=True)

    spec = importlib.util.spec_from_file_location("v17_reports", ROOT / "scripts/build_model_family_expansion_v17_reports.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load V17 report builder")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.RESULTS = run_root
    builder.REPORTS = report_root / "builder"
    builder.main()

    direct = read_csv(builder.REPORTS / "table_direct_vs_oracle.csv")
    latency = read_csv(builder.REPORTS / "table_paired_latency.csv")
    architectures = read_csv(builder.REPORTS / "table_primary_architectures.csv")
    training = read_csv(builder.REPORTS / "table_training_seed_robustness.csv")
    ablation = read_csv(builder.REPORTS / "table_2x2_ablation_effects.csv")
    manifest = load(run_root / "run_manifest.json")
    ledger = read_csv(run_root / "run_status.csv")

    primary = [row for row in direct if row["phase"] == "primary"]
    failures = [row for row in direct if row["direct_outcome"] != "SELECTED" or row["direct_independent_status"] not in {"", "SAFE"}]
    no_safe = [row for row in direct if row["direct_outcome"] == "NO_SAFE"]
    independent_failures = [row for row in direct if row["direct_independent_status"] not in {"", "SAFE"}]
    unsupported = [row for row in ledger if row["state"] == "UNSUPPORTED_RECORDED"]
    latency_terminal = [row for row in ledger if row["phase"].startswith("latency") and row["state"] in {"DONE", "FAILED_RECORDED", "UNSUPPORTED_RECORDED"}]

    formal_regret = []
    for row in latency:
        ratio = row.get("finite_over_direct_geomean_total", "")
        if ratio not in {"", "0", None}:
            value = 1 / float(ratio) - 1
            formal_regret.append({**row, "latency_regret": value})
    regrets = [float(row["latency_regret"]) for row in formal_regret]
    direct_trials = sum(int(row.get("direct_trials") or 0) for row in primary)
    exhaustive_trials = sum(int(row.get("exhaustive_denominator") or 0) for row in primary)
    reductions = 1 - direct_trials / exhaustive_trials if exhaustive_trials else None
    selection_ms = sum(float(row.get("selection_wall_clock_ms") or 0) for row in primary if row.get("selection_wall_clock_ms") not in {"", "PREDECESSOR_FROZEN"})
    exhaustive_ms = sum(float(row.get("exhaustive_wall_clock_ms") or 0) for row in primary if row.get("exhaustive_wall_clock_ms") not in {"", "PREDECESSOR_FROZEN"})
    wall_ratio = exhaustive_ms / selection_ms if selection_ms else None
    configs = Counter(row["candidate_id"] for row in direct if row.get("candidate_id"))

    table_root = final_results
    copy_table(builder.REPORTS / "table_primary_architectures.csv", table_root / "table_01_primary_architectures.csv")
    quality_fields = ["phase", "dataset", "model_id", "split_id", "plaintext_accuracy", "plaintext_balanced_accuracy", "plaintext_macro_f1", "plaintext_auroc", "plaintext_margin_quantiles"]
    write_csv(table_root / "table_02_plaintext_quality.csv", direct, quality_fields)
    stability_fields = ["phase", "dataset", "model_id", "split_id", "v_cert", "v_amb", "coverage", "selection_flips", "selection_violations", "direct_independent_status", "direct_independent_flips", "direct_independent_violations", "false_no_safe"]
    write_csv(table_root / "table_03_decision_stability.csv", direct, stability_fields)
    copy_table(builder.REPORTS / "table_direct_vs_oracle.csv", table_root / "table_04_direct_vs_exhaustive.csv")
    copy_table(builder.REPORTS / "table_paired_latency.csv", table_root / "table_05_formal_paired_latency.csv")
    write_csv(table_root / "table_06_latency_regret.csv", formal_regret, list(formal_regret[0]) if formal_regret else ["path", "latency_regret"])
    config_fields = ["phase", "dataset", "model_id", "split_id", "candidate_id", "log_n", "q_bits", "p_bits", "scale_bits", "path", "multiplicative_depth", "rotations", "packing_strategy", "aggregate_sensitivity"]
    write_csv(table_root / "table_07_selected_configurations.csv", direct, config_fields)
    copy_table(builder.REPORTS / "table_2x2_ablation_effects.csv", table_root / "table_08_ablation_factor_effects.csv")
    copy_table(builder.REPORTS / "table_training_seed_robustness.csv", table_root / "table_09_training_seed_robustness.csv")
    depth_rows = []
    for depth in (1, 2, 4, 6, 8):
        path = run_root / f"depth_ladder/results/D{depth}/result.json"
        item = load(path) if path.is_file() else {"outcome": "MISSING"}
        candidate = item.get("selected") or {}
        params = candidate.get("parameters") or {}
        depth_rows.append({"depth": depth, "outcome": item.get("outcome"), "trials": item.get("trials_used", ""), "false_no_safe": item.get("false_no_safe", ""), "candidate_id": candidate.get("id", ""), "log_n": params.get("log_n", ""), "q_bits": json.dumps(params.get("log_q", [])), "p_bits": json.dumps(params.get("log_p", [])), "scale_bits": params.get("log_default_scale", "")})
    write_csv(table_root / "table_10_depth_ladder.csv", depth_rows, list(depth_rows[0]))
    failure_rows = [{"source": "case", "dataset": row.get("dataset", ""), "model_id": row.get("model_id", ""), "split_id": row.get("split_id", ""), "state": row.get("direct_outcome", ""), "independent_state": row.get("direct_independent_status", ""), "false_no_safe": row.get("false_no_safe", ""), "reason": ""} for row in failures]
    failure_rows += [{"source": "ledger", "dataset": "", "model_id": row["case_id"], "split_id": row["phase"], "state": row["state"], "independent_state": "", "false_no_safe": "", "reason": row["reason"]} for row in ledger if row["state"] != "DONE"]
    write_csv(table_root / "table_11_failures_no_safe_exclusions.csv", failure_rows, ["source", "dataset", "model_id", "split_id", "state", "independent_state", "false_no_safe", "reason"])
    write_csv(table_root / "table_12_environment_and_run_binding.csv", [{"run_id": args.run_id, "environment_id": manifest["environment_id"], "guest_virtual_sockets": 1, "guest_cores_per_socket": 6, "guest_total_vcpu": 6, "scientific_protocol_digest": manifest["scientific_protocol_digest"], "execution_profile_digest": manifest["execution_profile_digest"], "source_tree_digest": manifest["source_tree_digest"], "binary_set_digest": manifest["binary_set_digest"], "old_result_import_count": 0}], ["run_id", "environment_id", "guest_virtual_sockets", "guest_cores_per_socket", "guest_total_vcpu", "scientific_protocol_digest", "execution_profile_digest", "source_tree_digest", "binary_set_digest", "old_result_import_count"])

    binding_rows = []
    for row in ledger:
        output = ROOT / row["output"]
        binding = output.parent / "result_binding.json"
        binding_rows.append({"phase": row["phase"], "case_id": row["case_id"], "state": row["state"], "output": row["output"], "output_sha256": sha(output) if output.is_file() else "", "binding": binding.relative_to(ROOT).as_posix() if binding.is_file() else "", "binding_sha256": sha(binding) if binding.is_file() else ""})
    write_csv(final_evidence / "expected_vs_observed_cases.csv", binding_rows, list(binding_rows[0]))
    copy_table(run_root / "run_status.csv", final_evidence / "final_run_status.csv")
    copy_table(table_root / "table_12_environment_and_run_binding.csv", final_evidence / "environment_binding.csv")
    write_csv(final_evidence / "result_binding.csv", binding_rows, list(binding_rows[0]))
    write_csv(final_evidence / "failure_inventory.csv", failure_rows, list(failure_rows[0]) if failure_rows else ["source", "dataset", "model_id", "split_id", "state", "independent_state", "false_no_safe", "reason"])
    write_csv(final_evidence / "unsupported_inventory.csv", unsupported, list(ledger[0]))
    write_csv(final_evidence / "no_safe_inventory.csv", no_safe, list(direct[0]) if direct else ["model_id"])
    write_csv(final_evidence / "independent_failure_inventory.csv", independent_failures, list(direct[0]) if direct else ["model_id"])
    exclusions = [row for row in ledger if row["phase"].startswith("latency") and row["state"] != "DONE"]
    write_csv(final_evidence / "comparison_exclusion_inventory.csv", exclusions, list(ledger[0]))
    write_json(final_evidence / "old_run_exclusion_manifest.json", {"old_run_id": manifest["supersedes_old_run_id"], "status": "SUPERSEDED_FOR_FINAL_EVALUATION", "admissibility": "EXPLORATORY_ONLY", "exclude_from_final_aggregation": True, "old_result_rows_imported": 0, "old_latency_samples_imported": 0})

    svg_bars(final_results / "figure_01_architecture_coverage.svg", "V17 primary architecture completion", [(row["primary_id"], float(row["v17_completed_cases"])) for row in architectures])
    svg_bars(final_results / "figure_02_candidate_reduction_vs_regret.svg", "Candidate reduction and formal latency regret", [(row.get("model_id", row.get("path", "case")), 100 * float(row["latency_regret"])) for row in formal_regret], "%")
    svg_bars(final_results / "figure_03_selection_wallclock.svg", "Selection wall-clock by model family", [(model, sum(float(row.get("selection_wall_clock_ms") or 0) for row in primary if row["model_id"] == model and row.get("selection_wall_clock_ms") not in {"", "PREDECESSOR_FROZEN"}) / 1000) for model in sorted({row["model_id"] for row in primary})], " s")
    copy_table(builder.REPORTS / "figure_depth_vs_selected_chain.svg", final_results / "figure_04_depth_vs_selected_chain.svg")
    svg_bars(final_results / "figure_05_configuration_diversity.svg", "Selected configuration frequency", [(key, float(value)) for key, value in configs.items()])
    copy_table(builder.REPORTS / "figure_margin_vs_configuration.svg", final_results / "figure_06_margin_vs_configuration.svg")
    svg_bars(final_results / "figure_07_training_seed_variation.svg", "Training-seed selected configuration count", [(model, float(len({row['candidate_id'] for row in training if row['model_id'] == model and row.get('candidate_id')}))) for model in sorted({row["model_id"] for row in training})])
    svg_bars(final_results / "figure_08_formal_paired_latency.svg", "Finite fastest-SAFE over direct total latency", [(row.get("model_id") or row.get("path", "case"), float(row.get("finite_over_direct_geomean_total") or 0)) for row in latency])
    high = sorted(formal_regret, key=lambda row: float(row["latency_regret"]), reverse=True)[:10]
    svg_bars(final_results / "figure_09_high_regret_case_study.svg", "Highest formal latency regret cases", [(row.get("model_id") or row.get("path", "case"), 100 * float(row["latency_regret"])) for row in high], "%")

    complete_families = sum(str(row.get("full_v17_metrics_complete", "")).lower() == "true" for row in architectures)
    packed_complete = any(row["model_id"] == "packed_cnn_lite_binary01_v17" and str(row["full_v17_metrics_complete"]).lower() == "true" for row in architectures)
    if complete_families >= 5 and packed_complete:
        broad_state = "SUPPORTED" if not independent_failures else "PARTIALLY_SUPPORTED"
    else:
        broad_state = "REQUIRES_CLAIM_NARROWING"
    regret_summary = {"median": number(regrets, 0.5), "iqr_low": number(regrets, 0.25), "iqr_high": number(regrets, 0.75), "p90": number(regrets, 0.9), "max": max(regrets) if regrets else None}
    facts = {
        "run_id": args.run_id, "environment_id": manifest["environment_id"], "ledger": dict(Counter(row["state"] for row in ledger)),
        "formal_latency_terminal": len(latency_terminal), "formal_latency_expected": 68,
        "complete_primary_families": complete_families, "candidate_trials_direct": direct_trials,
        "candidate_trials_exhaustive": exhaustive_trials, "candidate_reduction": reductions,
        "selection_wallclock_finite_over_direct": wall_ratio, "regret": regret_summary,
        "false_no_safe": len([row for row in direct if str(row.get("false_no_safe", "")).lower() == "true"]),
        "independent_evaluation_failures": len(independent_failures), "distinct_selected_configurations": len(configs),
        "broad_title_state": broad_state,
    }
    statements = """The partial measurements collected under the previous 2-vCPU topology
were preserved for provenance but excluded from the final evaluation.
All final cases were re-executed from the beginning under a homogeneous
1-socket, 6-core, 6-vCPU guest configuration.

기존 2 vCPU 환경에서 수집된 부분 결과는 이력 보존 목적으로
유지하였으나 최종 평가에서는 제외하였다. 최종 결과는 모두
1소켓·6코어·총 6 vCPU의 동일한 VM 환경에서 처음부터 다시
수행하여 수집하였다.
"""
    report_names = [
        "V17_VM1X6_FULL_RESULTS_REPORT.md", "V17_VM1X6_NEGATIVE_RESULTS.md",
        "V17_VM1X6_FORMAL_LATENCY_REPORT.md", "V17_VM1X6_SELECTION_QUALITY_REPORT.md",
        "V17_VM1X6_CONFIGURATION_ADAPTATION_REPORT.md", "V17_VM1X6_REVIEWER_RISK_ASSESSMENT.md",
        "V17_VM1X6_TITLE_AND_CLAIM_DECISION.md", "V17_VM1X6_PAPER_REPLACEMENT_PLAN.md",
        "V17_VM1X6_REPRODUCTION_GUIDE.md", "V17_VM1X6_FINAL_EXECUTION_REPORT.md",
    ]
    common = f"# FlipGuard V17 VM1X6\n\n{statements}\n## Verified summary\n\n```json\n{json.dumps(facts, indent=2, sort_keys=True)}\n```\n\n"
    sections = {
        report_names[0]: "All 204 protocol-defined rows are reported without mixing the superseded 2x1 run.",
        report_names[1]: f"Recorded case failures: {len(failures)}; false NO_SAFE: {facts['false_no_safe']}; independent-evaluation failures: {len(independent_failures)}.",
        report_names[2]: f"Formal latency terminal rows: {len(latency_terminal)}/68. Regret is signed and was not clamped: {json.dumps(regret_summary, sort_keys=True)}.",
        report_names[3]: f"Direct candidate evaluations: {direct_trials}; finite candidates: {exhaustive_trials}; reduction: {reductions}. Finite/direct selection wall-clock ratio: {wall_ratio}.",
        report_names[4]: f"Distinct selected configurations: {len(configs)}. Depth rows and all training-seed rows are retained in the publication tables.",
        report_names[5]: "Residual risks include one-host timing, finite candidate coverage, first-SAFE regret tails, explicit estimator assumptions, and any recorded unsupported graph.",
        report_names[6]: f"Broad-title decision: {broad_state}. The controlled 2x2 cells are counted as ablation, not four unrelated architectures.",
        report_names[7]: "Do not edit V16.1 automatically. Replace the environment section, V17 benchmark scope, candidate reduction, selection wall-clock, formal latency/regret, negative-result disclosure, and title/abstract/conclusion wording from these verified tables.",
        report_names[8]: f"Run: `{args.run_id}`. Resume: `GOMAXPROCS=6 taskset -c 0-5 scripts/run_model_family_expansion_v17_vm1x6_until_complete.sh {args.run_id}`. Verify with `python3 scripts/verify_model_family_expansion_v17_vm1x6.py --run-id {args.run_id} --require-complete`.",
        report_names[9]: f"Terminal ledger: {json.dumps(facts['ledger'], sort_keys=True)}. Commit/push were not performed by this workflow.",
    }
    for name in report_names:
        write(final_reports / name, common + "## Focus\n\n" + sections[name] + "\n")
    write_json(final_reports / "final_summary.json", facts)

    files = sorted(path for root in (final_results, final_evidence, final_reports) for path in root.rglob("*") if path.is_file() and path.name not in {"manifest.json", "SHA256SUMS"})
    final_manifest = {"schema_version": "flipguard_v17_vm1x6_final_evidence_v1", "state": "FINAL_COMPLETE" if not args.allow_partial else "PARTIAL_QA", "run_id": args.run_id, "environment_id": manifest["environment_id"], "facts": facts, "files": [{"path": path.relative_to(ROOT).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha(path)} for path in files]}
    write_json(final_evidence / "manifest.json", final_manifest)
    all_files = files + [final_evidence / "manifest.json"]
    for root in (final_results, final_evidence, final_reports):
        selected = [path for path in all_files if path.is_relative_to(root)]
        write(root / "SHA256SUMS", "".join(f"{sha(path).removeprefix('sha256:')}  {path.relative_to(root).as_posix()}\n" for path in selected))
    print(json.dumps({"status": final_manifest["state"], "manifest_sha256": sha(final_evidence / "manifest.json"), "facts": facts}, sort_keys=True))


if __name__ == "__main__":
    main()
