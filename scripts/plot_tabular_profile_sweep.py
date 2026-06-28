#!/usr/bin/env python3

import csv
from pathlib import Path

import matplotlib.pyplot as plt


INPUT = Path("results/ckks_tabular_profile_sweep_summary/current/selected_profiles.csv")
OUTPUT_DIR = Path("results/ckks_tabular_profile_sweep_summary/current/figures")


def read_rows(path):
    with path.open("r", newline="") as f:
        return list(csv.DictReader(f))


def workload_label(row):
    return f"{row['dataset_id']}\n{row['model_id']}"


def plot_latency(rows):
    labels = [workload_label(row) for row in rows]
    selected = [float(row["selected_mean_total_ms"]) for row in rows]
    rejected = [float(row["fastest_rejected_mean_total_ms"]) for row in rows]

    x = list(range(len(rows)))
    width = 0.38

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar([i - width / 2 for i in x], selected, width, label="Selected safe")
    ax.bar([i + width / 2 for i in x], rejected, width, label="Fastest rejected")

    ax.set_ylabel("Mean total latency (ms)")
    ax.set_title("Selected safe profile versus fastest rejected profile")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.legend()
    fig.tight_layout()

    fig.savefig(OUTPUT_DIR / "latency_selected_vs_rejected.png", dpi=300)
    fig.savefig(OUTPUT_DIR / "latency_selected_vs_rejected.pdf")


def plot_speedup_and_flips(rows):
    speedups = [float(row["fastest_rejected_total_speedup_vs_default_safe"]) for row in rows]
    flips = [float(row["fastest_rejected_max_decision_flips"]) for row in rows]
    labels = [workload_label(row).replace("\n", " / ") for row in rows]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(speedups, flips)

    for x, y, label in zip(speedups, flips, labels):
        ax.annotate(label, (x, y), textcoords="offset points", xytext=(5, 5), fontsize=8)

    ax.set_xlabel("Fastest rejected total-latency speedup")
    ax.set_ylabel("Decision flips")
    ax.set_title("Raw speed gain versus decision instability")
    fig.tight_layout()

    fig.savefig(OUTPUT_DIR / "speedup_vs_decision_flips.png", dpi=300)
    fig.savefig(OUTPUT_DIR / "speedup_vs_decision_flips.pdf")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_rows(INPUT)

    plot_latency(rows)
    plot_speedup_and_flips(rows)

    print(f"wrote {OUTPUT_DIR / 'latency_selected_vs_rejected.png'}")
    print(f"wrote {OUTPUT_DIR / 'speedup_vs_decision_flips.png'}")


if __name__ == "__main__":
    main()
