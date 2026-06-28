#!/usr/bin/env python3

import csv
from pathlib import Path

import matplotlib.pyplot as plt


STRATEGY_SUMMARY = Path("results/ckks_tabular_strategy_analysis/current/strategy_summary.csv")
PROFILE_SUMMARY = Path("results/ckks_tabular_profile_sweep_summary/current/profile_summary.csv")
SELECTED_PROFILES = Path("results/ckks_tabular_profile_sweep_summary/current/selected_profiles.csv")
OUTPUT_DIR = Path("results/ckks_tabular_extended_figures/current")


def read_rows(path):
    with path.open("r", newline="") as f:
        return list(csv.DictReader(f))


def plot_strategy_safe_counts(rows):
    labels = [row["strategy_id"].replace("_", "\n") for row in rows]
    safe_counts = [int(row["safe_selections"]) for row in rows]
    unsafe_counts = [int(row["unsafe_selections"]) for row in rows]

    x = list(range(len(rows)))
    width = 0.38

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar([i - width / 2 for i in x], safe_counts, width, label="Safe selections")
    ax.bar([i + width / 2 for i in x], unsafe_counts, width, label="Unsafe selections")
    ax.set_ylabel("Workload count")
    ax.set_title("Selection safety by strategy")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.legend()
    fig.tight_layout()

    fig.savefig(OUTPUT_DIR / "strategy_safe_vs_unsafe_counts.png", dpi=300)
    fig.savefig(OUTPUT_DIR / "strategy_safe_vs_unsafe_counts.pdf")


def plot_latency_error_scatter(rows):
    usable = [
        row for row in rows
        if row["mean_total_ms"] != "" and row["max_y_error"] != ""
    ]

    safe_x = [
        float(row["mean_total_ms"])
        for row in usable
        if row["strict_safe"] == "true"
    ]
    safe_y = [
        float(row["max_y_error"])
        for row in usable
        if row["strict_safe"] == "true"
    ]

    rejected_x = [
        float(row["mean_total_ms"])
        for row in usable
        if row["strict_safe"] != "true"
    ]
    rejected_y = [
        float(row["max_y_error"])
        for row in usable
        if row["strict_safe"] != "true"
    ]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(safe_x, safe_y, label="Strict safe")
    ax.scatter(rejected_x, rejected_y, label="Rejected")
    ax.set_xlabel("Mean total latency (ms)")
    ax.set_ylabel("Maximum output error")
    ax.set_title("Latency-error tradeoff across CKKS candidates")
    ax.legend()
    fig.tight_layout()

    fig.savefig(OUTPUT_DIR / "latency_error_tradeoff.png", dpi=300)
    fig.savefig(OUTPUT_DIR / "latency_error_tradeoff.pdf")


def plot_selected_profile_distribution(rows):
    counts = {}

    for row in rows:
        key = f"{row['selected_profile']}\n{row['selected_path']}"
        counts[key] = counts.get(key, 0) + 1

    labels = list(counts.keys())
    values = [counts[label] for label in labels]

    x = list(range(len(labels)))

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x, values)
    ax.set_ylabel("Selected workload count")
    ax.set_title("Distribution of selected fastest safe profiles")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    fig.tight_layout()

    fig.savefig(OUTPUT_DIR / "selected_profile_distribution.png", dpi=300)
    fig.savefig(OUTPUT_DIR / "selected_profile_distribution.pdf")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    strategy_rows = read_rows(STRATEGY_SUMMARY)
    profile_rows = read_rows(PROFILE_SUMMARY)
    selected_rows = read_rows(SELECTED_PROFILES)

    plot_strategy_safe_counts(strategy_rows)
    plot_latency_error_scatter(profile_rows)
    plot_selected_profile_distribution(selected_rows)

    print(f"wrote {OUTPUT_DIR / 'strategy_safe_vs_unsafe_counts.png'}")
    print(f"wrote {OUTPUT_DIR / 'latency_error_tradeoff.png'}")
    print(f"wrote {OUTPUT_DIR / 'selected_profile_distribution.png'}")


if __name__ == "__main__":
    main()
