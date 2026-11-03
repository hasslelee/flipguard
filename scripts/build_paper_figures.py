#!/usr/bin/env python3

import csv
from pathlib import Path

EVIDENCE = Path("results/experiment_evidence_summary/current")
OUT = Path("results/paper_figures/current")


def read_csv(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def pct(value):
    return float(str(value).replace("%", "").strip())


def xnum(value):
    return float(str(value).replace("x", "").strip())


def safe_float(value, default=0.0):
    try:
        return float(str(value).strip())
    except Exception:
        return default


def short_name(name):
    mapping = {
        "Linear Regression": "Linear",
        "LogReg/Profile": "LogReg",
        "Polynomial Regression": "PolyReg",
        "Sobel Edge Detection": "Sobel",
        "Harris Corner Response": "Harris",
        "MLP-square": "MLP",
        "WDBC Breast Cancer / Linear+Poly3": "WDBC-LP",
    }
    return mapping.get(name, name.replace(" Regression", "").replace(" Detection", ""))


def svg_header(width, height):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>',
        '.title{font:700 22px Arial, sans-serif; fill:#111827;}',
        '.subtitle{font:400 13px Arial, sans-serif; fill:#4b5563;}',
        '.axis{stroke:#9ca3af; stroke-width:1;}',
        '.grid{stroke:#e5e7eb; stroke-width:1;}',
        '.label{font:400 12px Arial, sans-serif; fill:#374151;}',
        '.small{font:400 11px Arial, sans-serif; fill:#6b7280;}',
        '.value{font:700 12px Arial, sans-serif; fill:#111827;}',
        '.safe{fill:#2563eb;}',
        '.unsafe{fill:#dc2626;}',
        '.neutral{fill:#6b7280;}',
        '.light{fill:#dbeafe;}',
        '.card{fill:#f9fafb; stroke:#e5e7eb; stroke-width:1;}',
        '</style>',
    ]


def svg_footer():
    return ["</svg>"]


def write_svg(name, lines):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text("\n".join(lines) + "\n")
    print(f"Wrote {path}")


def text(x, y, content, cls="label", anchor="start"):
    escaped = (
        str(content)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{escaped}</text>'


def fig_core_repeated_speedup():
    rows = read_csv(EVIDENCE / "core_tuner_repeated_table.csv")
    data = []
    for r in rows:
        data.append({
            "name": short_name(r["workload"]),
            "speedup": pct(r["fastest_safe_speedup"]),
            "status": r["latency_only_status"],
            "flips": int(r["latency_only_flips"]),
            "violations": int(r["latency_only_violations"]),
        })

    width, height = 980, 560
    left, right, top, bottom = 90, 40, 90, 135
    chart_w = width - left - right
    chart_h = height - top - bottom
    max_v = max(d["speedup"] for d in data) * 1.18

    lines = svg_header(width, height)
    lines += [
        text(40, 40, "Figure 3. Repeated Core Tuner Result", "title"),
        text(40, 62, "Fastest-safe speedup preserves zero decision flips; latency-only is rejected in 4/6 workloads.", "subtitle"),
    ]

    for tick in range(0, int(max_v) + 10, 10):
        y = top + chart_h - (tick / max_v) * chart_h
        lines.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+chart_w}" y2="{y:.1f}" class="grid"/>')
        lines.append(text(left - 10, y + 4, f"{tick}%", "small", "end"))

    lines.append(f'<line x1="{left}" y1="{top+chart_h}" x2="{left+chart_w}" y2="{top+chart_h}" class="axis"/>')
    lines.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+chart_h}" class="axis"/>')

    gap = 24
    bar_w = (chart_w - gap * (len(data) - 1)) / len(data)

    for i, d in enumerate(data):
        x = left + i * (bar_w + gap)
        h = d["speedup"] / max_v * chart_h
        y = top + chart_h - h
        cls = "safe"
        lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="5" class="{cls}"/>')
        lines.append(text(x + bar_w / 2, y - 8, f'{d["speedup"]:.1f}%', "value", "middle"))
        lines.append(text(x + bar_w / 2, top + chart_h + 24, d["name"], "label", "middle"))

        if d["status"] == "REJECTED":
            note = f'latency-only rejected: flips={d["flips"]}, viol={d["violations"]}'
            lines.append(f'<circle cx="{x + bar_w/2:.1f}" cy="{top + chart_h + 45}" r="5" class="unsafe"/>')
            lines.append(text(x + bar_w / 2, top + chart_h + 65, note, "small", "middle"))
        else:
            lines.append(f'<circle cx="{x + bar_w/2:.1f}" cy="{top + chart_h + 45}" r="5" class="safe"/>')
            lines.append(text(x + bar_w / 2, top + chart_h + 65, "latency-only safe", "small", "middle"))

    lines += svg_footer()
    write_svg("fig3_core_repeated_speedup.svg", lines)


def fig_planner_candidate_reduction():
    rows = read_csv(EVIDENCE / "planner_guided_candidate_validation_table.csv")
    data = []
    for r in rows:
        data.append({
            "name": short_name(r["workload"]),
            "full": int(r["full_candidates"]),
            "planner": int(r["planner_guided_candidates"]),
            "overhead": r["overhead_vs_full_fastest_safe"],
        })

    width, height = 980, 560
    left, right, top, bottom = 90, 40, 90, 115
    chart_w = width - left - right
    chart_h = height - top - bottom
    max_v = max(d["full"] for d in data) * 1.25

    lines = svg_header(width, height)
    lines += [
        text(40, 40, "Figure 4. Planner-Guided Candidate Reduction", "title"),
        text(40, 62, "Planner-guided execution evaluates 35 of 77 candidates while preserving zero fastest-safe flips and violations.", "subtitle"),
    ]

    for tick in range(0, int(max_v) + 5, 5):
        y = top + chart_h - (tick / max_v) * chart_h
        lines.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+chart_w}" y2="{y:.1f}" class="grid"/>')
        lines.append(text(left - 10, y + 4, str(tick), "small", "end"))

    lines.append(f'<line x1="{left}" y1="{top+chart_h}" x2="{left+chart_w}" y2="{top+chart_h}" class="axis"/>')
    lines.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+chart_h}" class="axis"/>')

    group_gap = 28
    group_w = (chart_w - group_gap * (len(data) - 1)) / len(data)
    bar_w = group_w * 0.36

    total_full = sum(d["full"] for d in data)
    total_planner = sum(d["planner"] for d in data)
    reduction = 100.0 * (1.0 - total_planner / total_full)

    for i, d in enumerate(data):
        gx = left + i * (group_w + group_gap)
        h1 = d["full"] / max_v * chart_h
        h2 = d["planner"] / max_v * chart_h
        y1 = top + chart_h - h1
        y2 = top + chart_h - h2

        lines.append(f'<rect x="{gx:.1f}" y="{y1:.1f}" width="{bar_w:.1f}" height="{h1:.1f}" rx="4" class="neutral"/>')
        lines.append(f'<rect x="{gx + bar_w + 6:.1f}" y="{y2:.1f}" width="{bar_w:.1f}" height="{h2:.1f}" rx="4" class="safe"/>')
        lines.append(text(gx + bar_w / 2, y1 - 7, d["full"], "value", "middle"))
        lines.append(text(gx + bar_w + 6 + bar_w / 2, y2 - 7, d["planner"], "value", "middle"))
        lines.append(text(gx + group_w / 2, top + chart_h + 24, d["name"], "label", "middle"))
        lines.append(text(gx + group_w / 2, top + chart_h + 43, f'overhead {d["overhead"]}', "small", "middle"))

    lines.append(f'<rect x="700" y="86" width="220" height="72" rx="10" class="card"/>')
    lines.append(text(720, 113, f"Total: {total_full} -> {total_planner}", "value"))
    lines.append(text(720, 136, f"Reduction: {reduction:.2f}%", "value"))

    lines += svg_footer()
    write_svg("fig4_planner_candidate_reduction.svg", lines)


def fig_tabular_safety():
    rows = read_csv(EVIDENCE / "tabular_safety_table.csv")
    data = []
    for r in rows:
        label = r["dataset"].replace(" binary classification", "").replace(" even-vs-odd classification", "")
        model = r["model"].replace("Linear+Poly3", "LP").replace("MLP-square", "MLP")
        data.append({
            "name": f"{label} / {model}",
            "unsafe_flips": int(r["unsafe_flips"]),
            "unsafe_violations": int(r["unsafe_violations"]),
            "speedup": xnum(r["unsafe_total_speedup_vs_safe"]),
        })

    width, height = 1100, 650
    left, right, top, bottom = 260, 80, 80, 55
    chart_w = width - left - right
    row_h = 46
    max_v = max(d["unsafe_flips"] for d in data) * 1.15

    lines = svg_header(width, height)
    lines += [
        text(40, 40, "Figure 5. Real-Data Tabular Safety", "title"),
        text(40, 62, "Safe path passes 10/10 with 0 flips and 0 violations; fastest-without-guard is unsafe in 10/10.", "subtitle"),
    ]

    for i, d in enumerate(data):
        y = top + i * row_h
        w = d["unsafe_flips"] / max_v * chart_w
        lines.append(text(left - 12, y + 20, d["name"], "label", "end"))
        lines.append(f'<rect x="{left}" y="{y}" width="{w:.1f}" height="25" rx="4" class="unsafe"/>')
        lines.append(text(left + w + 8, y + 18, f'{d["unsafe_flips"]} flips, {d["unsafe_violations"]} violations, {d["speedup"]:.2f}x', "value"))

    lines.append(f'<rect x="760" y="500" width="290" height="88" rx="10" class="card"/>')
    lines.append(text(782, 530, "Safe path: 10/10 pass", "value"))
    lines.append(text(782, 553, "Safe flips / violations: 0 / 0", "value"))
    lines.append(text(782, 576, "Fastest-without-guard: 10/10 unsafe", "value"))

    lines += svg_footer()
    write_svg("fig5_tabular_safety.svg", lines)


def fig_strategy_comparison():
    rows = read_csv(EVIDENCE / "strategy_comparison_table.csv")
    data = []
    for r in rows:
        name = r["strategy"]
        name = name.replace("Fixed default safe path", "Fixed default")
        name = name.replace("Fastest without guard", "Fastest w/o guard")
        name = name.replace("Output-error guard only", "Output-error guard")
        data.append({
            "name": name,
            "speedup": xnum(r["speedup_vs_fixed_default"]),
            "safe": int(r["safe_selections"]),
            "unsafe": int(r["unsafe_selections"]),
            "flips": int(r["decision_flips"]),
            "violations": int(r["score_error_violations"]),
        })

    width, height = 980, 560
    left, right, top, bottom = 90, 40, 90, 135
    chart_w = width - left - right
    chart_h = height - top - bottom
    max_v = max(d["speedup"] for d in data) * 1.2

    lines = svg_header(width, height)
    lines += [
        text(40, 40, "Figure 6. Strategy Comparison and Ablation", "title"),
        text(40, 62, "The unguarded fastest strategy is much faster but unsafe; guard-based strategies preserve 10/10 safe selections.", "subtitle"),
    ]

    for tick in [0.0, 0.5, 1.0, 1.5, 2.0]:
        y = top + chart_h - (tick / max_v) * chart_h
        lines.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+chart_w}" y2="{y:.1f}" class="grid"/>')
        lines.append(text(left - 10, y + 4, f"{tick:.1f}x", "small", "end"))

    lines.append(f'<line x1="{left}" y1="{top+chart_h}" x2="{left+chart_w}" y2="{top+chart_h}" class="axis"/>')
    lines.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+chart_h}" class="axis"/>')

    gap = 20
    bar_w = (chart_w - gap * (len(data) - 1)) / len(data)

    for i, d in enumerate(data):
        x = left + i * (bar_w + gap)
        h = d["speedup"] / max_v * chart_h
        y = top + chart_h - h
        cls = "unsafe" if d["unsafe"] > 0 else "safe"
        lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="5" class="{cls}"/>')
        lines.append(text(x + bar_w / 2, y - 8, f'{d["speedup"]:.2f}x', "value", "middle"))
        lines.append(text(x + bar_w / 2, top + chart_h + 24, d["name"], "label", "middle"))
        lines.append(text(x + bar_w / 2, top + chart_h + 44, f'safe {d["safe"]}/10', "small", "middle"))
        if d["unsafe"] > 0:
            lines.append(text(x + bar_w / 2, top + chart_h + 63, f'flips {d["flips"]}', "small", "middle"))

    lines += svg_footer()
    write_svg("fig6_strategy_comparison.svg", lines)


def write_index():
    content = """# Paper figures index

Generated figures:

- `fig3_core_repeated_speedup.svg`: repeated core fastest-safe speedup and latency-only rejection status.
- `fig4_planner_candidate_reduction.svg`: full candidate ladder versus planner-guided executed candidates.
- `fig5_tabular_safety.svg`: real-data unsafe flips contrasted with safe-path 10/10 pass.
- `fig6_strategy_comparison.svg`: baseline/ablation strategy comparison.

Recommended paper usage:

- Domestic conference: use Figures 3, 4, and 5 plus one method overview drawn manually.
- Journal version: use Figures 3, 4, 5, 6 plus margin-coverage and method figures.
"""
    (OUT / "README.md").write_text(content)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fig_core_repeated_speedup()
    fig_planner_candidate_reduction()
    fig_tabular_safety()
    fig_strategy_comparison()
    write_index()


if __name__ == "__main__":
    main()
