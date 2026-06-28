#!/usr/bin/env python3

import csv
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


OUT = Path("seminar_assets/figures_en")

PRESENTATION = Path("results/presentation_ready/current")
FINAL_SUMMARY = Path("results/final_research_summary/current/summary.csv")
PARAMETER_SAFETY = Path("results/ckks_profile_parameter_analysis/current/profile_parameter_safety.csv")


COLORS = {
    "blue": "#2563eb",
    "green": "#16a34a",
    "orange": "#f97316",
    "red": "#dc2626",
    "gray": "#64748b",
    "light_blue": "#eff6ff",
    "light_gray": "#f8fafc",
    "dark": "#111827",
}


def read_rows(path):
    with path.open("r", newline="") as f:
        return list(csv.DictReader(f))


def read_metrics(path):
    if not path.exists():
        return {}
    rows = read_rows(path)
    return {(r["section"], r["metric"]): r["value"] for r in rows}


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / f"{name}.png"
    pdf = OUT / f"{name}.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {png}")
    print(f"wrote {pdf}")


def blank(title):
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.5, 0.93, title, ha="center", va="center", fontsize=26, fontweight="bold")
    return fig, ax


def box(ax, x, y, w, h, text, fc="#ffffff", ec="#2563eb", fontsize=14, weight="normal"):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.018,rounding_size=0.025",
        facecolor=fc,
        edgecolor=ec,
        linewidth=1.8,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        fontweight=weight,
        color=COLORS["dark"],
        wrap=True,
    )


def arrow(ax, x1, y1, x2, y2, color="#2563eb"):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>",
            mutation_scale=20,
            linewidth=2.0,
            color=color,
        )
    )


def figure_01_pipeline():
    fig, ax = blank("FlipGuard Overview")

    items = [
        ("Candidates", "11 × 2"),
        ("Encrypted\nInference", "CKKS"),
        ("Safety\nGuards", "flip = 0\nerror viol. = 0"),
        ("Latency\nRanking", "total ms"),
        ("Selected\nConfiguration", "fastest safe"),
    ]

    x0, y, w, h, gap = 0.06, 0.49, 0.15, 0.22, 0.045
    for i, (head, val) in enumerate(items):
        x = x0 + i * (w + gap)
        box(ax, x, y, w, h, f"{head}\n\n{val}", fc=COLORS["light_blue"], fontsize=16, weight="bold")
        if i < len(items) - 1:
            arrow(ax, x + w + 0.005, y + h / 2, x + w + gap - 0.006, y + h / 2)

    box(
        ax,
        0.16,
        0.20,
        0.68,
        0.13,
        "Goal: select the fastest execution configuration that preserves output accuracy and decisions",
        fc=COLORS["light_gray"],
        ec=COLORS["dark"],
        fontsize=17,
        weight="bold",
    )

    save(fig, "01_pipeline")


def figure_02_candidates():
    rows = read_rows(PRESENTATION / "candidate_catalog.csv")
    table_rows = [
        [
            r["display_name"],
            r["chain_length"],
            r["scale_bits"],
            r["log_n"],
            r["slots"],
        ]
        for r in rows
    ]

    fig, ax = blank("Execution Configuration Candidates")
    ax.axis("off")

    table = ax.table(
        cellText=table_rows,
        colLabels=["Candidate", "Chain", "Scale", "log N", "Slots"],
        loc="center",
        cellLoc="center",
        colLoc="center",
        bbox=[0.05, 0.12, 0.90, 0.72],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)

    for (r, c), cell in table.get_celld().items():
        cell.set_linewidth(0.7)
        if r == 0:
            cell.set_facecolor(COLORS["blue"])
            cell.set_text_props(color="white", weight="bold")
        else:
            cell.set_facecolor("#ffffff" if r % 2 else COLORS["light_blue"])

    ax.text(
        0.5,
        0.055,
        "11 parameter candidates × 2 paths = 22 execution configurations per workload",
        ha="center",
        fontsize=15,
        fontweight="bold",
    )

    save(fig, "02_candidates")


def figure_03_experiment_scale():
    fig, ax = blank("Experiment Scale")

    metrics = [
        ("Workloads", "10"),
        ("Candidates\nper workload", "22"),
        ("Repeated\nruns", "660"),
        ("Successful\nruns", "630"),
        ("Failed\nruns", "30"),
        ("Strict-safe\ncandidates", "150"),
    ]

    x0, y, w, h, gap = 0.055, 0.45, 0.13, 0.23, 0.028
    for i, (label, value) in enumerate(metrics):
        x = x0 + i * (w + gap)
        box(ax, x, y, w, h, f"{value}\n\n{label}", fc="#ffffff", ec=COLORS["blue"], fontsize=17, weight="bold")

    box(
        ax,
        0.18,
        0.20,
        0.64,
        0.12,
        "Same candidate set applied across all datasets and models",
        fc=COLORS["light_gray"],
        ec=COLORS["dark"],
        fontsize=17,
        weight="bold",
    )

    save(fig, "03_experiment_scale")


def figure_04_boundary():
    metrics = read_metrics(FINAL_SUMMARY)

    total = int(float(metrics.get(("boundary", "runs"), "10010")))
    stable = int(float(metrics.get(("boundary", "stable_runs"), "9900")))
    ambiguous = total - stable
    stable_flips = int(float(metrics.get(("boundary", "stable_decision_flips"), "0")))
    violations = int(float(metrics.get(("output_accuracy", "score_error_violations"), "0")))

    fig, ax = blank("Boundary Stress Test")

    ax.pie(
        [stable, ambiguous],
        labels=[f"stable\n{stable:,}", f"ambiguous\n{ambiguous:,}"],
        colors=[COLORS["blue"], COLORS["orange"]],
        startangle=90,
        radius=0.27,
        center=(0.33, 0.52),
        textprops={"fontsize": 13, "fontweight": "bold"},
    )
    ax.text(0.33, 0.52, f"{total:,}", ha="center", va="center", fontsize=22, fontweight="bold")

    box(ax, 0.62, 0.62, 0.25, 0.10, f"Stable flips\n{stable_flips}", fc="#ecfdf5", ec=COLORS["green"], fontsize=19, weight="bold")
    box(ax, 0.62, 0.47, 0.25, 0.10, f"Error violations\n{violations}", fc="#ecfdf5", ec=COLORS["green"], fontsize=19, weight="bold")
    box(ax, 0.62, 0.32, 0.25, 0.10, "z range\n[-0.05, 0.05]", fc=COLORS["light_gray"], ec=COLORS["gray"], fontsize=17, weight="bold")

    save(fig, "04_boundary")


def figure_05_speed():
    labels = ["baseline\nnon-rescale", "selected\nrescale", "unsafe\nnon-rescale"]
    total_ms = [147.0721, 117.7348, 77.2697]
    speedup = [1.0000, 1.2515, 1.9040]
    flips = [0, 0, 30]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.8))
    fig.suptitle("Repeated Speed Benchmark", fontsize=26, fontweight="bold")

    axes[0].bar(labels, total_ms)
    axes[0].set_title("Total latency (ms)", fontweight="bold")
    axes[0].set_ylim(0, 170)
    for i, v in enumerate(total_ms):
        axes[0].text(i, v + 4, f"{v:.1f}", ha="center", fontsize=12)

    axes[1].bar(labels, speedup)
    axes[1].set_title("Speedup", fontweight="bold")
    axes[1].set_ylim(0, 2.2)
    for i, v in enumerate(speedup):
        axes[1].text(i, v + 0.05, f"{v:.4f}x", ha="center", fontsize=12)

    axes[2].bar(labels, flips)
    axes[2].set_title("Decision flips", fontweight="bold")
    axes[2].set_ylim(0, 35)
    for i, v in enumerate(flips):
        axes[2].text(i, v + 1, f"{v}", ha="center", fontsize=12)

    for ax in axes:
        ax.grid(axis="y", alpha=0.25)

    fig.tight_layout(rect=[0, 0.02, 1, 0.90])
    save(fig, "05_speed")


def figure_06_strategy():
    rows = read_rows(PRESENTATION / "strategy_summary.csv")
    label_map = {
        "fixed_default_configuration": "fixed\ndefault",
        "fastest_without_safety_guard": "fastest\nonly",
        "output_error_guard_only": "error\nguard",
        "decision_guard_only": "decision\nguard",
        "rescale_only": "rescale\nonly",
        "proposed_dual_guard": "proposed",
    }

    labels = [label_map.get(r["strategy_id"], r["strategy_id"]) for r in rows]
    safe = [int(r["safe_selections"]) for r in rows]
    unsafe = [int(r["unsafe_selections"]) for r in rows]

    fig, ax = plt.subplots(figsize=(16, 8))
    x = list(range(len(labels)))
    ax.bar([i - 0.18 for i in x], safe, width=0.36, label="safe")
    ax.bar([i + 0.18 for i in x], unsafe, width=0.36, label="unsafe")
    ax.set_title("Strategy Comparison", fontsize=26, fontweight="bold", pad=20)
    ax.set_ylabel("Workloads")
    ax.set_ylim(0, 11)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=13)

    for i, (s, u) in enumerate(zip(safe, unsafe)):
        ax.text(i - 0.18, s + 0.2, str(s), ha="center", fontsize=11)
        ax.text(i + 0.18, u + 0.2, str(u), ha="center", fontsize=11)

    fig.tight_layout()
    save(fig, "06_strategy")


def figure_07_selected():
    rows = read_rows(PRESENTATION / "selected_configurations.csv")

    labels = [f"{r['dataset_id']}\n{r['model_id'].replace('mlp_square_linear_score', 'MLP').replace('linear_poly3', 'linear')}" for r in rows]
    total = [float(r["selected_mean_total_ms"]) for r in rows]
    speedup = [float(r["selected_total_speedup_vs_default"]) for r in rows]

    fig, ax1 = plt.subplots(figsize=(17, 8))
    x = list(range(len(labels)))

    ax1.bar(x, total, label="total latency (ms)")
    ax1.set_title("Selected Safe Configurations", fontsize=26, fontweight="bold", pad=20)
    ax1.set_ylabel("Total latency (ms)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=35, ha="right", fontsize=9)
    ax1.grid(axis="y", alpha=0.25)

    ax2 = ax1.twinx()
    ax2.plot(x, speedup, marker="o", linewidth=2.5, label="speedup")
    ax2.set_ylabel("Speedup vs default")
    ax2.set_ylim(0.8, max(speedup) + 0.4)

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left")

    fig.tight_layout()
    save(fig, "07_selected")


def figure_08_tradeoff():
    rows = read_rows(PARAMETER_SAFETY)

    fig, ax = plt.subplots(figsize=(16, 8))

    for r in rows:
        x = float(r["mean_total_ms_completed_candidates"])
        y = int(r["strict_safe_candidate_count"])
        label = r["profile"]

        if y == 0:
            color = COLORS["red"]
        elif y < max(16, y):
            color = COLORS["orange"]
        else:
            color = COLORS["blue"]

        if y == 0:
            color = COLORS["red"]
        elif y < 20 and y != 0:
            color = COLORS["orange"]
        else:
            color = COLORS["blue"]

        ax.scatter(x, y, s=130, color=color)
        ax.text(x + 4, y + 0.25, label, fontsize=9)

    ax.set_title("Safety-Latency Tradeoff", fontsize=26, fontweight="bold", pad=20)
    ax.set_xlabel("Mean total latency (ms)")
    ax.set_ylabel("Strict-safe candidates")
    ax.grid(alpha=0.25)

    fig.tight_layout()
    save(fig, "08_tradeoff")


def figure_09_mnist():
    rows = read_rows(PRESENTATION / "mnist_summary.csv")

    models = [r["model_id"].replace("linear_poly3", "linear").replace("mlp_square_linear_score", "MLP") for r in rows]
    accuracy = [float(r["raw_accuracy"]) for r in rows]
    speedup = [float(r["selected_total_speedup_vs_default"]) for r in rows]
    rejected_flips = [int(r["fastest_rejected_decision_flips"]) for r in rows]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.8))
    fig.suptitle("MNIST Pool16 Benchmark", fontsize=26, fontweight="bold")

    axes[0].bar(models, accuracy)
    axes[0].set_title("Accuracy")
    axes[0].set_ylim(0, 1.0)
    for i, v in enumerate(accuracy):
        axes[0].text(i, v + 0.02, f"{v:.4f}", ha="center")

    axes[1].bar(models, speedup)
    axes[1].set_title("Selected speedup")
    axes[1].set_ylim(0, max(speedup) + 0.3)
    for i, v in enumerate(speedup):
        axes[1].text(i, v + 0.04, f"{v:.4f}x", ha="center")

    axes[2].bar(models, rejected_flips)
    axes[2].set_title("Rejected flips")
    axes[2].set_ylim(0, max(rejected_flips) + 20)
    for i, v in enumerate(rejected_flips):
        axes[2].text(i, v + 3, str(v), ha="center")

    for ax in axes:
        ax.grid(axis="y", alpha=0.25)

    fig.tight_layout(rect=[0, 0.02, 1, 0.90])
    save(fig, "09_mnist")


def main():
    figure_01_pipeline()
    figure_02_candidates()
    figure_03_experiment_scale()
    figure_04_boundary()
    figure_05_speed()
    figure_06_strategy()
    figure_07_selected()
    figure_08_tradeoff()
    figure_09_mnist()


if __name__ == "__main__":
    main()
