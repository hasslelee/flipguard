#!/usr/bin/env python3

import csv
from pathlib import Path


OUTPUT_ROOT = Path("results/presentation_ready/current")

SELECTED_PROFILES = Path("results/ckks_tabular_profile_sweep_summary/current/selected_profiles.csv")
STRATEGY_SUMMARY = Path("results/ckks_tabular_strategy_analysis/current/strategy_summary.csv")
MNIST_LINEAR_METRICS = Path("datasets/tabular_suite/mnist_pool16/linear_poly3/metrics.csv")
MNIST_MLP_METRICS = Path("datasets/tabular_suite/mnist_pool16/mlp_square_linear_score/metrics.csv")


CANDIDATES = [
    {
        "internal_name": "default",
        "display_name": "chain7_scale45_N14_default",
        "candidate_family": "baseline",
        "chain_length": 7,
        "scale_bits": 45,
        "log_n": 14,
        "slots": 8192,
        "q_prime_count": 7,
        "p_prime_count": 1,
        "description": "Baseline execution configuration used as the reference point.",
    },
    {
        "internal_name": "scale42",
        "display_name": "chain7_scale42_N14",
        "candidate_family": "scale_reduced_chain7",
        "chain_length": 7,
        "scale_bits": 42,
        "log_n": 14,
        "slots": 8192,
        "q_prime_count": 7,
        "p_prime_count": 1,
        "description": "Keeps the baseline chain length and reduces the scale to 42 bits.",
    },
    {
        "internal_name": "scale40",
        "display_name": "chain7_scale40_N14",
        "candidate_family": "scale_reduced_chain7",
        "chain_length": 7,
        "scale_bits": 40,
        "log_n": 14,
        "slots": 8192,
        "q_prime_count": 7,
        "p_prime_count": 1,
        "description": "Keeps the baseline chain length and reduces the scale to 40 bits.",
    },
    {
        "internal_name": "scale38",
        "display_name": "chain7_scale38_N14",
        "candidate_family": "scale_reduced_chain7",
        "chain_length": 7,
        "scale_bits": 38,
        "log_n": 14,
        "slots": 8192,
        "q_prime_count": 7,
        "p_prime_count": 1,
        "description": "Keeps the baseline chain length and reduces the scale to 38 bits.",
    },
    {
        "internal_name": "deep_chain_8_scale45",
        "display_name": "chain8_scale45_N15",
        "candidate_family": "deep_chain",
        "chain_length": 8,
        "scale_bits": 45,
        "log_n": 15,
        "slots": 16384,
        "q_prime_count": 8,
        "p_prime_count": 1,
        "description": "Increases chain capacity with log N 15 and scale 45.",
    },
    {
        "internal_name": "deep_chain_9_scale45",
        "display_name": "chain9_scale45_N15",
        "candidate_family": "deep_chain",
        "chain_length": 9,
        "scale_bits": 45,
        "log_n": 15,
        "slots": 16384,
        "q_prime_count": 9,
        "p_prime_count": 1,
        "description": "Largest chain-capacity candidate in the current experiment.",
    },
    {
        "internal_name": "short_chain_6_scale42",
        "display_name": "chain6_scale42_N14",
        "candidate_family": "reduced_chain6",
        "chain_length": 6,
        "scale_bits": 42,
        "log_n": 14,
        "slots": 8192,
        "q_prime_count": 6,
        "p_prime_count": 1,
        "description": "Reduces the chain length to 6 while keeping a 42-bit scale.",
    },
    {
        "internal_name": "short_chain_6_scale40",
        "display_name": "chain6_scale40_N14",
        "candidate_family": "reduced_chain6",
        "chain_length": 6,
        "scale_bits": 40,
        "log_n": 14,
        "slots": 8192,
        "q_prime_count": 6,
        "p_prime_count": 1,
        "description": "Reduces the chain length to 6 with a 40-bit scale.",
    },
    {
        "internal_name": "short_chain_6_scale38",
        "display_name": "chain6_scale38_N14",
        "candidate_family": "reduced_chain6",
        "chain_length": 6,
        "scale_bits": 38,
        "log_n": 14,
        "slots": 8192,
        "q_prime_count": 6,
        "p_prime_count": 1,
        "description": "Reduces the chain length to 6 with a 38-bit scale.",
    },
    {
        "internal_name": "short_chain_5",
        "display_name": "chain5_scale40_N14",
        "candidate_family": "aggressive_reduced_chain",
        "chain_length": 5,
        "scale_bits": 40,
        "log_n": 14,
        "slots": 8192,
        "q_prime_count": 5,
        "p_prime_count": 1,
        "description": "Aggressively reduces the chain length to 5.",
    },
    {
        "internal_name": "short_chain_3",
        "display_name": "chain3_scale35_N14",
        "candidate_family": "aggressive_reduced_chain",
        "chain_length": 3,
        "scale_bits": 35,
        "log_n": 14,
        "slots": 8192,
        "q_prime_count": 3,
        "p_prime_count": 1,
        "description": "Most aggressive low-latency candidate in the current experiment.",
    },
]


PATH_LABELS = {
    "rescale_aware": "rescale",
    "baseline_non_rescale": "non-rescale",
    "rescale": "rescale",
    "naive": "non-rescale",
}


STRATEGY_LABELS = {
    "fixed_default_safe_path": "fixed_default_configuration",
    "fastest_without_guard": "fastest_without_safety_guard",
    "output_error_guard_only": "output_error_guard_only",
    "decision_guard_only": "decision_guard_only",
    "rescale_path_only": "rescale_only",
    "proposed_dual_guard": "proposed_dual_guard",
}


def read_rows(path):
    if not path.exists():
        raise FileNotFoundError(f"missing file: {path}")

    with path.open("r", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        raise ValueError(f"no rows to write: {path}")

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_metric_file(path):
    rows = read_rows(path)
    return {row["metric"]: row["value"] for row in rows}


def candidate_display_name(internal_name):
    for row in CANDIDATES:
        if row["internal_name"] == internal_name:
            return row["display_name"]
    return internal_name


def path_display_name(path):
    return PATH_LABELS.get(path, path)


def build_candidate_catalog():
    rows = []

    for row in CANDIDATES:
        rows.append({
            "internal_name": row["internal_name"],
            "display_name": row["display_name"],
            "candidate_family": row["candidate_family"],
            "chain_length": str(row["chain_length"]),
            "scale_bits": str(row["scale_bits"]),
            "log_n": str(row["log_n"]),
            "slots": str(row["slots"]),
            "q_prime_count": str(row["q_prime_count"]),
            "p_prime_count": str(row["p_prime_count"]),
            "description": row["description"],
        })

    return rows


def build_execution_configuration_catalog():
    rows = []

    for candidate in CANDIDATES:
        for internal_path, display_path in [
            ("rescale_aware", "rescale"),
            ("baseline_non_rescale", "non-rescale"),
        ]:
            rows.append({
                "configuration_id": f"{candidate['display_name']}__{display_path}",
                "candidate_internal_name": candidate["internal_name"],
                "candidate_display_name": candidate["display_name"],
                "path_internal_name": internal_path,
                "path_display_name": display_path,
                "candidate_family": candidate["candidate_family"],
                "chain_length": str(candidate["chain_length"]),
                "scale_bits": str(candidate["scale_bits"]),
                "log_n": str(candidate["log_n"]),
                "slots": str(candidate["slots"]),
                "q_prime_count": str(candidate["q_prime_count"]),
                "p_prime_count": str(candidate["p_prime_count"]),
            })

    return rows


def build_selected_configurations():
    rows = read_rows(SELECTED_PROFILES)
    out = []

    for row in rows:
        out.append({
            "dataset_id": row["dataset_id"],
            "model_id": row["model_id"],
            "candidate_count": row["candidate_count"],
            "strict_safe_candidate_count": row["strict_safe_candidate_count"],
            "selected_candidate": candidate_display_name(row["selected_profile"]),
            "selected_path": path_display_name(row["selected_path"]),
            "selected_mean_eval_only_ms": row["selected_mean_eval_only_ms"],
            "selected_mean_total_ms": row["selected_mean_total_ms"],
            "selected_total_speedup_vs_default": row["selected_total_speedup_vs_default_safe"],
            "selected_eval_only_speedup_vs_default": row["selected_eval_only_speedup_vs_default_safe"],
            "fastest_rejected_candidate": candidate_display_name(row["fastest_rejected_profile"]),
            "fastest_rejected_path": path_display_name(row["fastest_rejected_path"]),
            "fastest_rejected_mean_total_ms": row["fastest_rejected_mean_total_ms"],
            "fastest_rejected_total_speedup_vs_default": row["fastest_rejected_total_speedup_vs_default_safe"],
            "fastest_rejected_decision_flips": row["fastest_rejected_max_decision_flips"],
            "fastest_rejected_score_error_violations": row["fastest_rejected_max_score_error_violations"],
        })

    return out


def build_strategy_summary():
    rows = read_rows(STRATEGY_SUMMARY)
    out = []

    for row in rows:
        out.append({
            "strategy_id": STRATEGY_LABELS.get(row["strategy_id"], row["strategy_id"]),
            "workloads": row["workloads"],
            "safe_selections": row["safe_selections"],
            "unsafe_selections": row["unsafe_selections"],
            "decision_flips": row["total_decision_flips"],
            "score_error_violations": row["total_score_error_violations"],
            "mean_total_ms": row["mean_total_ms"],
            "mean_speedup_vs_fixed_default": row["mean_speedup_vs_fixed_default"],
        })

    return out


def build_mnist_summary():
    linear = read_metric_file(MNIST_LINEAR_METRICS)
    mlp = read_metric_file(MNIST_MLP_METRICS)

    selected = build_selected_configurations()
    selected_by_model = {
        row["model_id"]: row
        for row in selected
        if row["dataset_id"] == "mnist_pool16"
    }

    rows = []

    for model_id, metrics in [
        ("linear_poly3", linear),
        ("mlp_square_linear_score", mlp),
    ]:
        selected_row = selected_by_model[model_id]
        rows.append({
            "dataset_id": "mnist_pool16",
            "model_id": model_id,
            "train_samples": metrics["train_samples"],
            "test_samples": metrics["test_samples"],
            "raw_accuracy": metrics["raw_accuracy"],
            "raw_auc": metrics["raw_auc"],
            "raw_f1": metrics["raw_f1"],
            "polynomial_decision_match_rate": metrics["polynomial_decision_match_rate"],
            "selected_candidate": selected_row["selected_candidate"],
            "selected_path": selected_row["selected_path"],
            "selected_mean_total_ms": selected_row["selected_mean_total_ms"],
            "selected_total_speedup_vs_default": selected_row["selected_total_speedup_vs_default"],
            "fastest_rejected_candidate": selected_row["fastest_rejected_candidate"],
            "fastest_rejected_path": selected_row["fastest_rejected_path"],
            "fastest_rejected_decision_flips": selected_row["fastest_rejected_decision_flips"],
        })

    return rows


def write_latex_table(path, rows, columns):
    lines = []
    lines.append(r"\begin{tabular}{" + "l" * len(columns) + "}")
    lines.append(r"\toprule")
    lines.append(" & ".join(columns) + r" \\")
    lines.append(r"\midrule")

    for row in rows:
        values = []
        for column in columns:
            value = str(row[column]).replace("_", r"\_")
            values.append(value)
        lines.append(" & ".join(values) + r" \\")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_readme():
    text = """FlipGuard presentation-ready terminology outputs

This directory contains presentation-ready names for execution configurations.

Terminology policy:
- Use execution configuration instead of profile in paper and seminar text.
- Use rescale and non-rescale as path labels.
- Keep internal legacy names only for backward compatibility with existing scripts and result directories.

Current experiment scale after adding MNIST:
- workloads: 10
- candidates per workload: 22
- repeated runs: 660
- successful runs: 630
- failed runs: 30
- strict safe candidates: 150
- workloads with selected fastest safe configuration: 10/10
"""

    (OUTPUT_ROOT / "README.txt").write_text(text, encoding="utf-8")


def main():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    candidate_catalog = build_candidate_catalog()
    execution_catalog = build_execution_configuration_catalog()
    selected = build_selected_configurations()
    strategy = build_strategy_summary()
    mnist = build_mnist_summary()

    write_rows(OUTPUT_ROOT / "candidate_catalog.csv", candidate_catalog)
    write_rows(OUTPUT_ROOT / "execution_configuration_catalog.csv", execution_catalog)
    write_rows(OUTPUT_ROOT / "selected_configurations.csv", selected)
    write_rows(OUTPUT_ROOT / "strategy_summary.csv", strategy)
    write_rows(OUTPUT_ROOT / "mnist_summary.csv", mnist)

    write_latex_table(
        OUTPUT_ROOT / "candidate_catalog_table.tex",
        candidate_catalog,
        [
            "display_name",
            "candidate_family",
            "chain_length",
            "scale_bits",
            "log_n",
            "slots",
        ],
    )

    write_latex_table(
        OUTPUT_ROOT / "selected_configurations_table.tex",
        selected,
        [
            "dataset_id",
            "model_id",
            "selected_candidate",
            "selected_path",
            "selected_mean_total_ms",
            "selected_total_speedup_vs_default",
        ],
    )

    write_readme()

    print(f"wrote {OUTPUT_ROOT / 'candidate_catalog.csv'}")
    print(f"wrote {OUTPUT_ROOT / 'execution_configuration_catalog.csv'}")
    print(f"wrote {OUTPUT_ROOT / 'selected_configurations.csv'}")
    print(f"wrote {OUTPUT_ROOT / 'strategy_summary.csv'}")
    print(f"wrote {OUTPUT_ROOT / 'mnist_summary.csv'}")
    print(f"wrote {OUTPUT_ROOT / 'candidate_catalog_table.tex'}")
    print(f"wrote {OUTPUT_ROOT / 'selected_configurations_table.tex'}")
    print(f"wrote {OUTPUT_ROOT / 'README.txt'}")


if __name__ == "__main__":
    main()
