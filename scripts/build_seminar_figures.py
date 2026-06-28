#!/usr/bin/env python3

import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib import font_manager


OUT = Path("seminar_assets/figures")

PRESENTATION = Path("results/presentation_ready/current")
FINAL_SUMMARY = Path("results/final_research_summary/current/summary.csv")
PARAMETER_SAFETY = Path("results/ckks_profile_parameter_analysis/current/profile_parameter_safety.csv")


def configure_font():
    preferred = [
        "Noto Sans CJK KR",
        "Noto Sans KR",
        "NanumGothic",
        "Malgun Gothic",
        "AppleGothic",
    ]
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in preferred:
        if name in installed:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


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


def add_box(ax, x, y, w, h, text, fc="#ffffff", ec="#2563eb", lw=1.6, fontsize=12):
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.018,rounding_size=0.03",
        facecolor=fc,
        edgecolor=ec,
        linewidth=lw,
    )
    ax.add_patch(box)
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        color="#111827",
        wrap=True,
    )
    return box


def add_arrow(ax, x1, y1, x2, y2, color="#2563eb"):
    arrow = FancyArrowPatch(
        (x1, y1),
        (x2, y2),
        arrowstyle="-|>",
        mutation_scale=18,
        linewidth=2,
        color=color,
    )
    ax.add_patch(arrow)


def blank_fig(title, subtitle=None):
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.5, 0.94, title, ha="center", va="center", fontsize=25, fontweight="bold")
    if subtitle:
        ax.text(0.5, 0.895, subtitle, ha="center", va="center", fontsize=14, color="#4b5563")
    return fig, ax


def figure_01_overview():
    fig, ax = blank_fig(
        "FlipGuard 연구 개요",
        "관련연구 조사 단계에서 실제 CKKS 실행 구성 선택 실험으로의 확장",
    )

    items = [
        ("출발점", "CKKS 암호화 추론은\n속도 개선이 필요함"),
        ("문제", "가장 빠른 실행 구성이\n항상 안전하지는 않음"),
        ("전환", "속도 중심 최적화에서\n안전 조건 기반 선택으로 전환"),
        ("구현", "동일 후보군을 여러 작업에 적용하고\n결과를 반복 측정"),
        ("결과", "안전 조건을 만족하는\n가장 빠른 실행 구성 선택"),
    ]

    x0 = 0.05
    y = 0.52
    w = 0.16
    h = 0.22
    gap = 0.035

    for i, (head, body) in enumerate(items):
        x = x0 + i * (w + gap)
        add_box(ax, x, y, w, h, f"{head}\n\n{body}", fc="#eff6ff", ec="#2563eb", fontsize=12)
        if i < len(items) - 1:
            add_arrow(ax, x + w + 0.005, y + h / 2, x + w + gap - 0.008, y + h / 2)

    add_box(
        ax,
        0.08,
        0.18,
        0.84,
        0.18,
        "세미나 핵심 질문\n"
        "동일한 CKKS 실행 구성 후보군에서, 출력 정확도와 판단 안정성을 만족하는 가장 빠른 구성을 선택할 수 있는가?",
        fc="#f8fafc",
        ec="#0f172a",
        fontsize=16,
    )
    save(fig, "01_research_overview")


def figure_02_candidate_catalog():
    rows = read_rows(PRESENTATION / "candidate_catalog.csv")

    fig, ax = blank_fig(
        "CKKS 실행 구성 후보군",
        "11개 parameter candidate와 2개 execution path를 결합하여 작업당 22개 실행 구성을 평가",
    )

    ax.axis("off")

    display_rows = []
    for r in rows:
        display_rows.append([
            r["display_name"],
            r["candidate_family"],
            r["chain_length"],
            r["scale_bits"],
            r["log_n"],
            r["slots"],
        ])

    table = ax.table(
        cellText=display_rows,
        colLabels=["실행 구성 후보", "계열", "체인", "스케일", "log N", "slots"],
        loc="center",
        cellLoc="center",
        colLoc="center",
        bbox=[0.04, 0.11, 0.92, 0.70],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)

    for (row, col), cell in table.get_celld().items():
        cell.set_linewidth(0.8)
        if row == 0:
            cell.set_facecolor("#1d4ed8")
            cell.set_text_props(color="white", weight="bold")
        else:
            cell.set_facecolor("#ffffff" if row % 2 else "#eff6ff")

    ax.text(
        0.5,
        0.055,
        "default는 외부 표준값이 아니라, 본 연구에서 비교 기준으로 설정한 chain7_scale45_N14_default 실행 구성이다.",
        ha="center",
        fontsize=13,
        color="#1f2937",
    )
    save(fig, "02_execution_configuration_candidates")


def figure_03_experiment_design():
    fig, ax = blank_fig("실험 설계와 검증 범위")

    items = [
        ("경계 스트레스 실험", "결정 경계 주변에서\n안전성 조건 확인"),
        ("반복 속도 실험", "안전 경로와 위험 경로의\n지연시간 비교"),
        ("공개 데이터 추론", "WDBC 등 실제 데이터에서\n평문 판단 보존 확인"),
        ("다중 작업 검증", "10개 작업 × 22개 구성 × 3회\n총 660회 실행"),
    ]

    x0 = 0.07
    y = 0.47
    w = 0.19
    h = 0.27
    gap = 0.045

    for i, (head, body) in enumerate(items):
        x = x0 + i * (w + gap)
        add_box(ax, x, y, w, h, f"{head}\n\n{body}", fc="#ffffff", ec="#2563eb", fontsize=13)
        if i < len(items) - 1:
            add_arrow(ax, x + w + 0.005, y + h / 2, x + w + gap - 0.008, y + h / 2)

    add_box(
        ax,
        0.12,
        0.18,
        0.76,
        0.16,
        "기록 지표: 판단 뒤집힘 수, 출력 오차 위반 수, 최대 출력 오차, 평가 구간 지연시간, 전체 지연시간, 계산 실패 여부",
        fc="#f8fafc",
        ec="#64748b",
        fontsize=14,
    )
    save(fig, "03_experiment_design")


def figure_04_boundary_results():
    metrics = read_metrics(FINAL_SUMMARY)

    runs = int(float(metrics.get(("boundary", "runs"), "10010")))
    stable = int(float(metrics.get(("boundary", "stable_runs"), "9900")))
    ambiguous = runs - stable
    stable_flips = int(float(metrics.get(("boundary", "stable_decision_flips"), "0")))
    violations = int(float(metrics.get(("output_accuracy", "score_error_violations"), "0")))

    fig, ax = blank_fig("결정 경계 스트레스 테스트 결과")

    labels = ["안정 구간", "모호 구간"]
    values = [stable, ambiguous]

    ax.pie(
        values,
        labels=[f"{labels[0]}\n{stable:,}", f"{labels[1]}\n{ambiguous:,}"],
        colors=["#2563eb", "#f97316"],
        startangle=90,
        radius=0.27,
        center=(0.35, 0.52),
        textprops={"fontsize": 12},
    )
    ax.text(0.35, 0.52, f"총 {runs:,}회", ha="center", va="center", fontsize=17, fontweight="bold")

    add_box(ax, 0.63, 0.58, 0.28, 0.12, f"안정 구간 판단 뒤집힘\n{stable_flips}", fc="#ecfdf5", ec="#16a34a", fontsize=16)
    add_box(ax, 0.63, 0.42, 0.28, 0.12, f"출력 오차 위반\n{violations}", fc="#ecfdf5", ec="#16a34a", fontsize=16)
    add_box(
        ax,
        0.16,
        0.17,
        0.70,
        0.13,
        "해석: 안정 구간에서는 판단이 보존되었고, 모호 구간은 안전한 실행 구성 선별에서 별도로 관리해야 할 경계 영역으로 확인되었다.",
        fc="#f8fafc",
        ec="#0f172a",
        fontsize=14,
    )
    save(fig, "04_boundary_stress_results")


def figure_05_strategy_comparison():
    rows = read_rows(PRESENTATION / "strategy_summary.csv")
    label_map = {
        "fixed_default_configuration": "고정 기준",
        "fastest_without_safety_guard": "최저 지연만 선택",
        "output_error_guard_only": "출력 오차 조건만",
        "decision_guard_only": "판단 안정성 조건만",
        "rescale_only": "rescale만",
        "proposed_dual_guard": "제안 기법",
    }

    labels = [label_map.get(r["strategy_id"], r["strategy_id"]) for r in rows]
    safe = [int(r["safe_selections"]) for r in rows]
    unsafe = [int(r["unsafe_selections"]) for r in rows]

    fig, ax = plt.subplots(figsize=(16, 9))
    x = range(len(labels))
    ax.bar([i - 0.18 for i in x], safe, width=0.36, label="안전 선택")
    ax.bar([i + 0.18 for i in x], unsafe, width=0.36, label="위험 선택")
    ax.set_title("기준 전략 비교 및 절제 연구", fontsize=24, fontweight="bold", pad=20)
    ax.set_ylabel("작업 수")
    ax.set_ylim(0, 11)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=12)

    ax.text(
        0.5,
        -0.22,
        "제안 기법은 10개 작업 모두에서 안전한 실행 구성을 선택한 반면, 최저 지연만 선택하는 전략은 모든 작업에서 위험 구성을 선택하였다.",
        transform=ax.transAxes,
        ha="center",
        fontsize=13,
        color="#111827",
    )
    fig.tight_layout()
    save(fig, "05_strategy_comparison")


def figure_06_selected_configurations():
    rows = read_rows(PRESENTATION / "selected_configurations.csv")
    labels = [f"{r['dataset_id']}\n{r['model_id'].replace('_linear_score','')}" for r in rows]
    total = [float(r["selected_mean_total_ms"]) for r in rows]
    speedup = [float(r["selected_total_speedup_vs_default"]) for r in rows]

    fig, ax1 = plt.subplots(figsize=(17, 9))
    x = range(len(rows))
    ax1.bar(x, total, label="선택된 실행 구성 전체 지연시간")
    ax1.set_title("작업별 선택된 안전 실행 구성", fontsize=24, fontweight="bold", pad=20)
    ax1.set_ylabel("전체 지연시간 (ms)")
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(labels, rotation=35, ha="right", fontsize=9)
    ax1.grid(axis="y", alpha=0.25)

    ax2 = ax1.twinx()
    ax2.plot(list(x), speedup, marker="o", linewidth=2.5, label="기준 대비 속도 향상")
    ax2.set_ylabel("기준 대비 속도 향상")
    ax2.set_ylim(0.8, max(speedup) + 0.4)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    fig.tight_layout()
    save(fig, "06_selected_safe_configurations")


def figure_07_safety_latency_tradeoff():
    rows = read_rows(PARAMETER_SAFETY)

    fig, ax = plt.subplots(figsize=(16, 9))

    for r in rows:
        x = float(r["mean_total_ms_completed_candidates"])
        y = int(r["strict_safe_candidate_count"])
        name = r["profile"]
        if y == 0:
            color = "#dc2626"
        elif y < 18:
            color = "#f97316"
        else:
            color = "#2563eb"
        ax.scatter(x, y, s=130, color=color)
        ax.text(x + 5, y + 0.2, name, fontsize=9)

    ax.set_title("CKKS 실행 구성의 안전성-지연시간 관계", fontsize=24, fontweight="bold", pad=20)
    ax.set_xlabel("완료된 후보의 평균 전체 지연시간 (ms)")
    ax.set_ylabel("엄격 안전 통과 수")
    ax.grid(alpha=0.25)

    ax.text(
        0.5,
        -0.15,
        "짧은 chain은 지연시간을 낮추지만 안전 통과 수가 감소하며, 제안 기법은 안전 조건을 만족하지 않는 후보를 선택하지 않는다.",
        transform=ax.transAxes,
        ha="center",
        fontsize=13,
    )
    fig.tight_layout()
    save(fig, "07_safety_latency_tradeoff")


def figure_08_mnist_summary():
    rows = read_rows(PRESENTATION / "mnist_summary.csv")

    models = [r["model_id"].replace("_", "\n") for r in rows]
    acc = [float(r["raw_accuracy"]) for r in rows]
    speedup = [float(r["selected_total_speedup_vs_default"]) for r in rows]
    rejected_flips = [int(r["fastest_rejected_decision_flips"]) for r in rows]

    fig, axes = plt.subplots(1, 3, figsize=(17, 6))
    fig.suptitle("MNIST pooled 4x4 경량 벤치마크 결과", fontsize=24, fontweight="bold")

    axes[0].bar(models, acc)
    axes[0].set_title("원본 모델 정확도")
    axes[0].set_ylim(0, 1.0)

    axes[1].bar(models, speedup)
    axes[1].set_title("선택된 안전 구성의 기준 대비 속도 향상")
    axes[1].set_ylim(0, max(speedup) + 0.3)

    axes[2].bar(models, rejected_flips)
    axes[2].set_title("가장 빠른 거부 구성의 판단 뒤집힘")
    axes[2].set_ylim(0, max(rejected_flips) + 20)

    for ax in axes:
        ax.grid(axis="y", alpha=0.25)

    fig.text(
        0.5,
        0.02,
        "MNIST를 4×4 평균 풀링 특성으로 변환하여, 표 형식 데이터뿐 아니라 이미지 기반 입력 분포에서도 검증 범위를 확장하였다.",
        ha="center",
        fontsize=13,
    )
    fig.tight_layout(rect=[0, 0.05, 1, 0.93])
    save(fig, "08_mnist_pool16_summary")


def figure_09_final_message():
    fig, ax = blank_fig("세미나 핵심 결론")

    messages = [
        ("1", "동일 후보군 적용", "모든 데이터셋과 모델에 동일한 22개 실행 구성 후보 적용"),
        ("2", "안전 조건 검증", "출력 오차, 판단 뒤집힘, 계산 실패 여부를 함께 검사"),
        ("3", "최저 지연 선택의 위험", "가장 빠른 후보는 10개 작업 모두에서 위험 구성으로 선택됨"),
        ("4", "제안 기법의 효과", "10개 작업 모두에서 가장 빠른 안전 실행 구성 선택 성공"),
    ]

    for i, (num, head, body) in enumerate(messages):
        y = 0.68 - i * 0.15
        add_box(ax, 0.13, y, 0.10, 0.09, num, fc="#2563eb", ec="#2563eb", fontsize=22)
        ax.text(0.27, y + 0.055, head, fontsize=17, fontweight="bold", va="center")
        ax.text(0.27, y + 0.022, body, fontsize=13, va="center", color="#374151")

    add_box(
        ax,
        0.14,
        0.10,
        0.72,
        0.12,
        "FlipGuard는 CKKS 암호화 추론을 단순 지연시간 최적화가 아니라, 안전 조건을 만족하는 실행 구성 선택 문제로 재정의한다.",
        fc="#eff6ff",
        ec="#2563eb",
        fontsize=16,
    )
    save(fig, "09_final_message")


def main():
    configure_font()
    figure_01_overview()
    figure_02_candidate_catalog()
    figure_03_experiment_design()
    figure_04_boundary_results()
    figure_05_strategy_comparison()
    figure_06_selected_configurations()
    figure_07_safety_latency_tradeoff()
    figure_08_mnist_summary()
    figure_09_final_message()


if __name__ == "__main__":
    main()
