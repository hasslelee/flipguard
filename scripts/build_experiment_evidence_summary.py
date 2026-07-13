#!/usr/bin/env python3

import csv
from pathlib import Path
from typing import Dict, Iterable, List


OUTPUT_DIR = Path("results/experiment_evidence_summary/current")

CORE_TUNER_SUMMARY = Path("results/tuner_benchmark_summary/summary.csv")
TABULAR_SUITE_SUMMARY = Path("results/ckks_tabular_suite_summary/current/summary.csv")
SELECTED_PROFILES = Path("results/ckks_tabular_profile_sweep_summary/current/selected_profiles.csv")
STRATEGY_SUMMARY = Path("results/ckks_tabular_strategy_analysis/current/strategy_summary.csv")
OPERATION_COUNTS = Path("results/ckks_tabular_operation_analysis/current/operation_counts.csv")
MARGIN_COVERAGE = Path("results/ckks_tabular_margin_coverage/current/coverage.csv")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generated = []

    if CORE_TUNER_SUMMARY.exists():
        core_rows = build_core_tuner_table(read_csv(CORE_TUNER_SUMMARY))
        write_csv(OUTPUT_DIR / "core_tuner_table.csv", core_rows)
        write_md_table(
            OUTPUT_DIR / "core_tuner_table.md",
            "Core workload tuner summary",
            core_rows,
            [
                "workload",
                "candidates",
                "safe",
                "rejected",
                "failed",
                "reference",
                "fastest_safe",
                "fastest_safe_speedup",
                "latency_only",
                "latency_only_status",
                "latency_only_flips",
                "latency_only_violations",
            ],
        )
        generated.extend(["core_tuner_table.csv", "core_tuner_table.md"])

    tabular_rows = build_tabular_safety_table(read_csv(TABULAR_SUITE_SUMMARY))
    write_csv(OUTPUT_DIR / "tabular_safety_table.csv", tabular_rows)
    write_md_table(
        OUTPUT_DIR / "tabular_safety_table.md",
        "Real-data tabular safety table",
        tabular_rows,
        [
            "dataset",
            "model",
            "plain_accuracy",
            "safe_ckks_accuracy",
            "safe_flips",
            "safe_violations",
            "safe_total_ms",
            "unsafe_candidate",
            "unsafe_flips",
            "unsafe_violations",
            "unsafe_total_speedup_vs_safe",
            "unsafe_status",
        ],
    )
    generated.extend(["tabular_safety_table.csv", "tabular_safety_table.md"])

    selected_rows = build_selected_profile_table(read_csv(SELECTED_PROFILES))
    write_csv(OUTPUT_DIR / "selected_profile_table.csv", selected_rows)
    write_md_table(
        OUTPUT_DIR / "selected_profile_table.md",
        "Repeated profile sweep selected configurations",
        selected_rows,
        [
            "workload",
            "candidates",
            "strict_safe_candidates",
            "selected_candidate",
            "selected_total_ms",
            "selected_speedup_vs_default_safe",
            "fastest_rejected_candidate",
            "fastest_rejected_total_ms",
            "fastest_rejected_speedup_vs_default_safe",
            "fastest_rejected_flips",
            "fastest_rejected_violations",
        ],
    )
    generated.extend(["selected_profile_table.csv", "selected_profile_table.md"])

    strategy_rows = build_strategy_table(read_csv(STRATEGY_SUMMARY))
    write_csv(OUTPUT_DIR / "strategy_comparison_table.csv", strategy_rows)
    write_md_table(
        OUTPUT_DIR / "strategy_comparison_table.md",
        "Strategy comparison",
        strategy_rows,
        [
            "strategy",
            "workloads",
            "safe_selections",
            "unsafe_selections",
            "decision_flips",
            "score_error_violations",
            "mean_total_ms",
            "speedup_vs_fixed_default",
        ],
    )
    generated.extend(["strategy_comparison_table.csv", "strategy_comparison_table.md"])

    operation_rows = build_operation_table(read_csv(OPERATION_COUNTS))
    write_csv(OUTPUT_DIR / "operation_counts_table.csv", operation_rows)
    write_md_table(
        OUTPUT_DIR / "operation_counts_table.md",
        "Tabular encrypted operation counts",
        operation_rows,
        [
            "workload",
            "selected_candidate",
            "input_dim",
            "hidden_units",
            "ct_ct_mults",
            "ct_pt_mults",
            "ct_adds",
            "rotations",
            "approx_depth",
            "notes",
        ],
    )
    generated.extend(["operation_counts_table.csv", "operation_counts_table.md"])

    margin_rows = []
    if MARGIN_COVERAGE.exists():
        margin_rows = build_margin_coverage_table(read_csv(MARGIN_COVERAGE))
        write_csv(OUTPUT_DIR / "margin_coverage_table.csv", margin_rows)
        write_md_table(
            OUTPUT_DIR / "margin_coverage_table.md",
            "Tabular decision-margin coverage",
            margin_rows,
            [
                "workload",
                "samples",
                "gamma_min",
                "v_cert",
                "v_amb",
                "coverage_pct",
                "p5_gamma",
                "p10_gamma",
                "median_gamma",
                "min_cert_gamma",
                "max_y_error",
                "max_usage_vs_alpha_margin",
            ],
        )
        generated.extend(["margin_coverage_table.csv", "margin_coverage_table.md"])

    write_key_claims(
        OUTPUT_DIR / "key_claims.md",
        tabular_rows=tabular_rows,
        selected_rows=selected_rows,
        strategy_rows=strategy_rows,
        core_rows=core_rows if CORE_TUNER_SUMMARY.exists() else [],
        margin_rows=margin_rows,
    )
    generated.append("key_claims.md")

    write_readme(OUTPUT_DIR / "README.md", generated)
    generated.append("README.md")

    print("Wrote experiment evidence summary:")
    for name in generated:
        print(f"  {OUTPUT_DIR / name}")


def build_core_tuner_table(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out = []
    for row in rows:
        out.append(
            {
                "workload": row["label"],
                "candidates": row["candidate_count"],
                "safe": row["safe_count"],
                "rejected": row["rejected_count"],
                "failed": row["failed_count"],
                "reference": candidate_ms(
                    row["reference_candidate"],
                    row["reference_ms"],
                ),
                "fastest_safe": candidate_ms(
                    row["fastest_safe_candidate"],
                    row["fastest_safe_ms"],
                ),
                "fastest_safe_speedup": percent(
                    row["fastest_safe_speedup_vs_reference_pct"]
                ),
                "latency_only": candidate_ms(
                    row["latency_only_candidate"],
                    row["latency_only_ms"],
                ),
                "latency_only_status": row["latency_only_status"],
                "latency_only_flips": row["latency_only_flips"],
                "latency_only_violations": row["latency_only_violations"],
            }
        )
    return out


def build_tabular_safety_table(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out = []
    for row in rows:
        out.append(
            {
                "dataset_id": row["dataset_id"],
                "dataset": row["dataset_name"],
                "model": model_label(row["model_id"]),
                "plain_accuracy": acc(row["plain_accuracy"]),
                "safe_candidate": f'{row["safe_profile"]}+{row["safe_path"]}',
                "safe_ckks_accuracy": acc(row["safe_ckks_accuracy"]),
                "safe_flips": row["safe_decision_flips"],
                "safe_violations": row["safe_score_error_violations"],
                "safe_max_error": sci(row["safe_max_y_error"]),
                "safe_eval_ms": ms(row["safe_mean_eval_only_ms"]),
                "safe_total_ms": ms(row["safe_mean_total_eval_ms"]),
                "safe_status": row["safe_status"],
                "unsafe_candidate": f'{row["unsafe_profile"]}+{row["unsafe_path"]}',
                "unsafe_ckks_accuracy": acc(row["unsafe_ckks_accuracy"]),
                "unsafe_flips": row["unsafe_decision_flips"],
                "unsafe_violations": row["unsafe_score_error_violations"],
                "unsafe_max_error": sci(row["unsafe_max_y_error"]),
                "unsafe_eval_ms": ms(row["unsafe_mean_eval_only_ms"]),
                "unsafe_total_ms": ms(row["unsafe_mean_total_eval_ms"]),
                "unsafe_total_speedup_vs_safe": times(
                    row["unsafe_total_speedup_vs_safe"]
                ),
                "unsafe_eval_speedup_vs_safe": times(
                    row["unsafe_eval_only_speedup_vs_safe"]
                ),
                "unsafe_status": row["unsafe_status"],
            }
        )
    return out


def build_selected_profile_table(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out = []
    for row in rows:
        out.append(
            {
                "dataset_id": row["dataset_id"],
                "model_id": row["model_id"],
                "workload": f'{dataset_label(row["dataset_id"])} / {model_label(row["model_id"])}',
                "candidates": row["candidate_count"],
                "strict_safe_candidates": row["strict_safe_candidate_count"],
                "selected_candidate": f'{row["selected_profile"]}+{row["selected_path"]}',
                "selected_eval_ms": ms(row["selected_mean_eval_only_ms"]),
                "selected_eval_std_ms": ms(row["selected_std_eval_only_ms"]),
                "selected_total_ms": ms(row["selected_mean_total_ms"]),
                "selected_total_std_ms": ms(row["selected_std_total_ms"]),
                "selected_speedup_vs_default_safe": times(
                    row["selected_total_speedup_vs_default_safe"]
                ),
                "selected_eval_speedup_vs_default_safe": times(
                    row["selected_eval_only_speedup_vs_default_safe"]
                ),
                "fastest_rejected_candidate": f'{row["fastest_rejected_profile"]}+{row["fastest_rejected_path"]}',
                "fastest_rejected_total_ms": ms(row["fastest_rejected_mean_total_ms"]),
                "fastest_rejected_speedup_vs_default_safe": times(
                    row["fastest_rejected_total_speedup_vs_default_safe"]
                ),
                "fastest_rejected_eval_speedup_vs_default_safe": times(
                    row["fastest_rejected_eval_only_speedup_vs_default_safe"]
                ),
                "fastest_rejected_flips": row["fastest_rejected_max_decision_flips"],
                "fastest_rejected_violations": row[
                    "fastest_rejected_max_score_error_violations"
                ],
            }
        )
    return out


def build_strategy_table(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    order = {
        "fixed_default_safe_path": 0,
        "rescale_path_only": 1,
        "decision_guard_only": 2,
        "output_error_guard_only": 3,
        "proposed_dual_guard": 4,
        "fastest_without_guard": 5,
    }

    out = []
    for row in sorted(rows, key=lambda r: order.get(r["strategy_id"], 99)):
        out.append(
            {
                "strategy_id": row["strategy_id"],
                "strategy": strategy_label(row["strategy_id"]),
                "workloads": row["workloads"],
                "safe_selections": row["safe_selections"],
                "unsafe_selections": row["unsafe_selections"],
                "failed_or_incomplete": row["failed_or_incomplete_selections"],
                "missing": row["missing_selections"],
                "decision_flips": row["total_decision_flips"],
                "score_error_violations": row["total_score_error_violations"],
                "mean_total_ms": ms(row["mean_total_ms"]),
                "std_total_ms": ms(row["std_total_ms"]),
                "speedup_vs_fixed_default": times(row["mean_speedup_vs_fixed_default"]),
            }
        )
    return out


def build_operation_table(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out = []
    for row in rows:
        out.append(
            {
                "dataset_id": row["dataset_id"],
                "model_id": row["model_id"],
                "workload": f'{dataset_label(row["dataset_id"])} / {model_label(row["model_id"])}',
                "selected_candidate": f'{row["selected_profile"]}+{row["selected_path"]}',
                "input_dim": row["input_dim"],
                "hidden_units": row["hidden_units"],
                "encrypted_inputs": row["encrypted_input_ciphertexts"],
                "outputs": row["output_ciphertexts"],
                "ct_ct_mults": row["ciphertext_ciphertext_multiplications"],
                "ct_pt_mults": row["ciphertext_plaintext_multiplications"],
                "ct_adds": row["ciphertext_additions"],
                "rotations": row["rotations"],
                "approx_depth": row["approximate_multiplicative_depth"],
                "notes": row["notes"],
            }
        )
    return out


def build_margin_coverage_table(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out = []
    for row in rows:
        out.append(
            {
                "dataset_id": row["dataset_id"],
                "model_id": row["model_id"],
                "workload": f'{dataset_label(row["dataset_id"])} / {model_label(row["model_id"])}',
                "samples": row["samples"],
                "gamma_min": row["gamma_min"],
                "v_cert": row["v_cert"],
                "v_amb": row["v_amb"],
                "coverage_pct": row["coverage_pct"] + "%",
                "min_gamma": row["min_gamma"],
                "p1_gamma": row["p1_gamma"],
                "p5_gamma": row["p5_gamma"],
                "p10_gamma": row["p10_gamma"],
                "median_gamma": row["median_gamma"],
                "p90_gamma": row["p90_gamma"],
                "min_cert_gamma": row["min_cert_gamma"],
                "max_y_error": row["max_y_error"],
                "p95_y_error": row["p95_y_error"],
                "max_usage_vs_alpha_margin": row["max_usage_vs_alpha_margin"],
                "safety_factor": row["safety_factor"],
            }
        )
    return out


def write_key_claims(
    path: Path,
    *,
    tabular_rows: List[Dict[str, str]],
    selected_rows: List[Dict[str, str]],
    strategy_rows: List[Dict[str, str]],
    core_rows: List[Dict[str, str]],
    margin_rows: List[Dict[str, str]],
) -> None:
    safe_tabular = sum(1 for r in tabular_rows if r["safe_status"] == "pass")
    safe_flips = sum(int(r["safe_flips"]) for r in tabular_rows)
    safe_violations = sum(int(r["safe_violations"]) for r in tabular_rows)
    unsafe_rejected = sum(1 for r in tabular_rows if r["unsafe_status"] == "rejected")
    unsafe_flips = sum(int(r["unsafe_flips"]) for r in tabular_rows)
    unsafe_violations = sum(int(r["unsafe_violations"]) for r in tabular_rows)

    proposed = first_by(strategy_rows, "strategy_id", "proposed_dual_guard")
    fastest = first_by(strategy_rows, "strategy_id", "fastest_without_guard")
    fixed = first_by(strategy_rows, "strategy_id", "fixed_default_safe_path")

    selected_with_speedup = [
        parse_times(r["selected_speedup_vs_default_safe"])
        for r in selected_rows
        if parse_times(r["selected_speedup_vs_default_safe"]) > 1.0
    ]

    total_margin_samples = sum(int(r["samples"]) for r in margin_rows)
    total_v_cert = sum(int(r["v_cert"]) for r in margin_rows)
    total_v_amb = sum(int(r["v_amb"]) for r in margin_rows)
    min_margin_coverage = min(
        (float(r["coverage_pct"].rstrip("%")) for r in margin_rows),
        default=0.0,
    )
    max_margin_usage = max(
        (float(r["max_usage_vs_alpha_margin"]) for r in margin_rows),
        default=0.0,
    )

    lines = []
    lines.append("# Experiment evidence key claims\n")
    lines.append("## Core decision-stability condition\n")
    lines.append(
        "FlipGuard treats configuration selection as a decision-stability-constrained optimization problem. "
        "For a plaintext score `f(x)`, decrypted CKKS score `f_hat_i(x; c)`, threshold `tau`, "
        "and decision margin `gamma(x)=|f(x)-tau|`, a candidate configuration `c` is treated as safe "
        "only when the observed CKKS error stays within the budgeted margin on the certified validation set.\n"
    )
    lines.append("```text\n")
    lines.append("e_i(x; c)     = |f_hat_i(x; c) - f(x)|\n")
    lines.append("E_max(x; c)   = max_i e_i(x; c)\n")
    lines.append("gamma(x)      = |f(x) - tau|\n")
    lines.append("epsilon_bud   = alpha * gamma(x)\n")
    lines.append("SAFE(c)       => E_max(x; c) < epsilon_bud, flips=0, violations=0\n")
    lines.append("```\n\n")

    lines.append("## Tabular safety result\n")
    lines.append(
        f"- Real-data tabular workloads in `tabular_safety_table`: {len(tabular_rows)}\n"
    )
    lines.append(f"- Safe path pass workloads: {safe_tabular}/{len(tabular_rows)}\n")
    lines.append(f"- Safe decision flips: {safe_flips}\n")
    lines.append(f"- Safe score error violations: {safe_violations}\n")
    lines.append(f"- Rejected unsafe workloads: {unsafe_rejected}/{len(tabular_rows)}\n")
    lines.append(f"- Unsafe decision flips: {unsafe_flips}\n")
    lines.append(f"- Unsafe score error violations: {unsafe_violations}\n\n")

    if margin_rows:
        lines.append("## Tabular decision-margin coverage result\n")
        lines.append(f"- Margin coverage workloads: {len(margin_rows)}\n")
        lines.append(f"- Total evaluated samples: {total_margin_samples}\n")
        lines.append(f"- V_cert samples: {total_v_cert}\n")
        lines.append(f"- V_amb samples: {total_v_amb}\n")
        lines.append(f"- Minimum workload coverage: {min_margin_coverage:.2f}%\n")
        lines.append(
            f"- Maximum observed max_y_error / (alpha * min_cert_gamma): "
            f"{max_margin_usage:.10f}\n"
        )
        lines.append(
            "- Interpretation: decision-stability certification should be stated over "
            "V_cert under the configured gamma_min and safety factor, while V_amb is "
            "reported separately as near-boundary validation samples.\n\n"
        )

    lines.append("## Repeated profile sweep result\n")
    lines.append(
        f"- Repeated selected-profile workloads, including MNIST pool16 if present: {len(selected_rows)}\n"
    )
    if selected_with_speedup:
        lines.append(
            f"- Selected safe configurations faster than fixed default: {len(selected_with_speedup)}/{len(selected_rows)}\n"
        )
        lines.append(
            f"- Selected safe speedup range over fixed default among improved workloads: "
            f"{min(selected_with_speedup):.4f}x--{max(selected_with_speedup):.4f}x\n"
        )
    lines.append("\n")

    lines.append("## Strategy comparison result\n")
    if fixed:
        lines.append(
            f"- Fixed default safe path: safe={fixed['safe_selections']}/{fixed['workloads']}, "
            f"flips={fixed['decision_flips']}, violations={fixed['score_error_violations']}, "
            f"mean_total={fixed['mean_total_ms']}\n"
        )
    if proposed:
        lines.append(
            f"- Proposed dual guard: safe={proposed['safe_selections']}/{proposed['workloads']}, "
            f"unsafe={proposed['unsafe_selections']}, flips={proposed['decision_flips']}, "
            f"violations={proposed['score_error_violations']}, "
            f"speedup_vs_fixed_default={proposed['speedup_vs_fixed_default']}\n"
        )
    if fastest:
        lines.append(
            f"- Fastest without guard: safe={fastest['safe_selections']}/{fastest['workloads']}, "
            f"unsafe={fastest['unsafe_selections']}, flips={fastest['decision_flips']}, "
            f"violations={fastest['score_error_violations']}, "
            f"speedup_vs_fixed_default={fastest['speedup_vs_fixed_default']}\n"
        )
    lines.append("\n")

    if core_rows:
        lines.append("## Core workload tuner result\n")
        for row in core_rows:
            lines.append(
                f"- {row['workload']}: fastest_safe={row['fastest_safe']}, "
                f"speedup={row['fastest_safe_speedup']}, "
                f"latency_only_status={row['latency_only_status']}, "
                f"latency_only_flips={row['latency_only_flips']}, "
                f"latency_only_violations={row['latency_only_violations']}\n"
            )

    path.write_text("".join(lines))


def write_readme(path: Path, generated: Iterable[str]) -> None:
    lines = []
    lines.append("# FlipGuard experiment evidence summary\n\n")
    lines.append(
        "This directory contains experiment evidence tables generated from the current FlipGuard outputs.\n\n"
    )
    lines.append("## Generated files\n\n")
    for name in generated:
        lines.append(f"- `{name}`\n")
    lines.append("\n")
    lines.append("## Interpretation discipline\n\n")
    lines.append(
        "Use these tables to support the main FlipGuard claim: configuration selection must be constrained by "
        "decision stability, not optimized by latency alone. Do not claim full input-space guarantees. "
        "The safety claim is limited to the evaluated workload, validation set, threshold, margin cutoff, "
        "and safety-factor settings used to produce the underlying experiment outputs.\n"
    )
    path.write_text("".join(lines))


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    if not rows:
        raise ValueError(f"no rows to write: {path}")

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_md_table(
    path: Path,
    title: str,
    rows: List[Dict[str, str]],
    columns: List[str],
) -> None:
    lines = []
    lines.append(f"# {title}\n\n")
    lines.append("| " + " | ".join(columns) + " |\n")
    lines.append("| " + " | ".join(["---"] * len(columns)) + " |\n")
    for row in rows:
        lines.append("| " + " | ".join(md_cell(row.get(col, "")) for col in columns) + " |\n")
    path.write_text("".join(lines))


def first_by(rows: List[Dict[str, str]], key: str, value: str) -> Dict[str, str]:
    for row in rows:
        if row.get(key) == value:
            return row
    return {}


def md_cell(value: str) -> str:
    return str(value).replace("|", "\\|")


def model_label(model_id: str) -> str:
    labels = {
        "linear_poly3": "Linear+Poly3",
        "mlp_square_linear_score": "MLP-square",
    }
    return labels.get(model_id, model_id)


def dataset_label(dataset_id: str) -> str:
    labels = {
        "wdbc": "WDBC",
        "iris_binary": "Iris",
        "digits_binary": "Digits",
        "banknote": "Banknote",
        "mnist_pool16": "MNIST-pool16",
    }
    return labels.get(dataset_id, dataset_id)


def strategy_label(strategy_id: str) -> str:
    labels = {
        "fixed_default_safe_path": "Fixed default safe path",
        "rescale_path_only": "Rescale path only",
        "decision_guard_only": "Decision guard only",
        "output_error_guard_only": "Output-error guard only",
        "proposed_dual_guard": "Proposed dual guard",
        "fastest_without_guard": "Fastest without guard",
    }
    return labels.get(strategy_id, strategy_id)


def candidate_ms(candidate: str, value: str) -> str:
    return f"{candidate} ({ms(value)})"


def parse_float(value: str) -> float:
    return float(value)


def parse_times(value: str) -> float:
    return float(value.rstrip("x"))


def ms(value: str) -> str:
    return f"{parse_float(value):.3f} ms"


def acc(value: str) -> str:
    return f"{parse_float(value):.4f}"


def percent(value: str) -> str:
    return f"{parse_float(value):.2f}%"


def times(value: str) -> str:
    return f"{parse_float(value):.4f}x"


def sci(value: str) -> str:
    return f"{parse_float(value):.3e}"


if __name__ == "__main__":
    main()
