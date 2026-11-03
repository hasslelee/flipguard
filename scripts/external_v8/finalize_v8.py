#!/usr/bin/env python3
"""Normalize, freeze, and verify the focused V8 external comparison."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import html
import json
import math
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/evidence/focused_external_comparison_v8"
RESULTS = ROOT / "results/thesis_grade_protocol/focused_external_comparison_v8"
OUTPUTS = ROOT / "external/v8/outputs"
STATUS = ROOT / "external/v8/status"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def json_file(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def csv_file(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def truth(value: object) -> bool:
    return str(value).lower() in {"1", "true"}


def observed_or_not_evaluated(completed: bool, value: object) -> object:
    return value if completed else "NOT_EVALUATED"


def geometric_mean(values: list[float]) -> float:
    if not values or any(value <= 0 for value in values):
        raise ValueError("geometric mean requires positive values")
    return math.exp(statistics.fmean(math.log(value) for value in values))


def paired_ratio_summary(
    rows: list[dict[str, object]],
    numerator: str,
    denominator: str,
) -> dict[str, object]:
    grouped: dict[tuple[int, int, int], dict[str, float]] = {}
    for row in rows:
        key = (int(row["keyset"]), int(row["pass"]), int(row["row_id"]))
        grouped.setdefault(key, {})[str(row["arm"])] = float(row["total_ms"])
    ratios_by_input: dict[int, list[float]] = {}
    for (_, _, row_id), values in grouped.items():
        if numerator in values and denominator in values:
            ratios_by_input.setdefault(row_id, []).append(
                values[numerator] / values[denominator]
            )
    input_ratios = {
        row_id: geometric_mean(values)
        for row_id, values in ratios_by_input.items()
    }
    ids = sorted(input_ratios)
    observed = geometric_mean([input_ratios[row_id] for row_id in ids])
    generator = random.Random(20260807)
    bootstrap = []
    for _ in range(5000):
        bootstrap.append(geometric_mean([
            input_ratios[ids[generator.randrange(len(ids))]]
            for _ in ids
        ]))
    bootstrap.sort()
    return {
        "comparison": f"{numerator}/{denominator}",
        "unique_input_clusters": len(ids),
        "raw_pairs": sum(len(values) for values in ratios_by_input.values()),
        "geometric_mean_total_ratio": observed,
        "cluster_bootstrap_ci_low": bootstrap[int(0.025 * len(bootstrap))],
        "cluster_bootstrap_ci_high": bootstrap[min(len(bootstrap) - 1, int(0.975 * len(bootstrap)))],
        "bootstrap_repetitions": len(bootstrap),
    }


def copy_csv(source: Path, destination: Path) -> list[dict[str, str]]:
    rows = csv_file(source)
    shutil.copyfile(source, destination)
    return rows


def svg_text(x: float, y: float, value: object, size: int = 22, anchor: str = "start", color: str = "#172033", weight: int = 400) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="sans-serif" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="{anchor}" fill="{color}">{html.escape(str(value))}</text>'
    )


def write_svg(path: Path, title: str, subtitle: str, elements: list[str], width: int = 1200, height: int = 675) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        f'<title>{html.escape(title)}</title>',
        f'<desc>{html.escape(subtitle)}</desc>',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        svg_text(54, 58, title, 30, weight=700),
        svg_text(54, 91, subtitle, 17, color="#526072"),
        *elements,
        '</svg>',
    ]
    path.write_text("\n".join(content) + "\n", encoding="utf-8")


def bar_figure(path: Path, title: str, subtitle: str, labels: list[str], values: list[float], colors: list[str], value_labels: list[str] | None = None) -> None:
    if not labels or len(labels) != len(values) or len(colors) != len(values):
        raise ValueError("invalid bar figure data")
    width, height = 1200, 675
    left, right, top, bottom = 110, 55, 135, 105
    plot_width, plot_height = width - left - right, height - top - bottom
    maximum = max(values) or 1.0
    slot = plot_width / len(values)
    bar_width = min(150, slot * 0.58)
    elements = [
        f'<line x1="{left}" y1="{top + plot_height}" x2="{width - right}" y2="{top + plot_height}" stroke="#9ba7b5" stroke-width="2"/>'
    ]
    for index, (label, value, color) in enumerate(zip(labels, values, colors)):
        x = left + index * slot + (slot - bar_width) / 2
        bar_height = 0 if value == 0 else max(3, value / maximum * plot_height)
        y = top + plot_height - bar_height
        elements.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="{color}" rx="3"/>')
        elements.append(svg_text(x + bar_width / 2, y - 12, (value_labels or [format(item, ".6g") for item in values])[index], 20, "middle", weight=700))
        elements.append(svg_text(x + bar_width / 2, top + plot_height + 34, label, 18, "middle"))
    write_svg(path, title, subtitle, elements, width, height)


def build_publication_inputs(
    eva_manifest: dict[str, object],
    heir_manifest: dict[str, object],
    flipguard_manifest: dict[str, object],
    corelab_manifest: dict[str, object],
    common_data: dict[str, object],
    eva_rows: list[dict[str, object]],
    heir_rows: list[dict[str, object]],
    common_rows: list[dict[str, object]],
    accounting: list[dict[str, object]],
    execution: list[dict[str, object]],
    gate_rows: list[dict[str, object]],
    audit_rows: list[dict[str, object]],
    corelab_plan_status: list[dict[str, object]],
    pair_summaries: list[dict[str, object]],
) -> dict[str, object]:
    tables = RESULTS / "tables"
    figures = RESULTS / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)

    table_rows: list[tuple[str, list[dict[str, object]]]] = []
    table_rows.append(("table_01_external_provider_populations.csv", accounting))
    eva_table = []
    for arm in eva_manifest["arms"]:
        item = arm["validation"]
        eva_table.append({"role": "configuration_validation", "scale_bits": arm["scale_bits"], "candidate_id": arm["candidate_id"], "status": item["status"], "unique_inputs": item["unique_inputs"], "contexts": item["contexts"], "decision_flips": item["decision_flips"], "reserve_policy_violations": item["reserve_policy_violations"], "max_absolute_error": item["max_absolute_error"], "max_normalized_budget_usage": item["max_normalized_budget_usage"]})
    for item in eva_manifest["audits"]:
        eva_table.append({"role": "locked_audit", "scale_bits": item["scale_bits"], "candidate_id": item["candidate_id"], "status": item["status"], "unique_inputs": item["unique_inputs"], "contexts": item["contexts"], "decision_flips": item["decision_flips"], "reserve_policy_violations": item["reserve_policy_violations"], "max_absolute_error": item["max_absolute_error"], "max_normalized_budget_usage": item["max_normalized_budget_usage"]})
    table_rows.append(("table_02_eva_scale_and_locked_audit.csv", eva_table))
    shared_table = []
    for runtime, summaries in heir_manifest["runtime_summaries"].items():
        for item in summaries:
            shared_table.append({"provider": "Google HEIR", "runtime": runtime, "role": item["role"], "candidate_id": f"heir_{runtime}_shared_polynomial", "status": "SAFE" if not item["decision_flips"] and not item["reserve_policy_violations"] else "REJECTED", "unique_inputs": item["unique_inputs"], "fresh_key_runs": item["fresh_contexts"], "decision_flips": item["decision_flips"], "reserve_policy_violations": item["reserve_policy_violations"], "retuning": 0})
    shared_table.extend({**row, "runtime": "Lattigo v6.2.0", "role": "configuration_validation"} for row in gate_rows if row["provider"] != "Google HEIR")
    shared_table.extend({**row, "runtime": "Lattigo v6.2.0", "role": "locked_audit"} for row in audit_rows if row["provider"] in {"FlipGuard direct", "Security-V2 bounded catalog"})
    table_rows.append(("table_03_shared_polynomial_decision_results.csv", shared_table))
    table_rows.append(("table_04_corelab_plan_grid.csv", corelab_plan_status))
    gate_table = [{"record_type": "validation", **row} for row in gate_rows] + [{"record_type": "locked_audit", **row} for row in audit_rows]
    table_rows.append(("table_05_provider_decision_stability.csv", gate_table))
    table_rows.append(("table_06_common_executor_latency.csv", pair_summaries))
    table_rows.append(("table_07_execution_and_tuning_accounting.csv", execution))
    table_rows.append(("table_08_fairness_limitations.csv", [
        {"dimension": "cross_runtime_latency", "state": "BLOCKED", "limitation": "Native runtime timings are not used for cross-runtime ratios."},
        {"dimension": "common_executor_latency", "state": "BLOCKED_DIAGNOSTIC", "limitation": "Eight direct-arm flips on one near-threshold input block a stable-candidate latency claim."},
        {"dimension": "corelab_decision", "state": "NOT_EVALUATED", "limitation": "The official LinearRegression workload has no frozen natural decision output."},
        {"dimension": "corelab_plan_grid", "state": "PARTIALLY_SUPPORTED", "limitation": "70/72 plans completed; elasm_36 and elasm_41 failed before output."},
        {"dimension": "portability", "state": "SCOPED", "limitation": "PORTABLE_EXACT applies only to the frozen HEIR-generated Lattigo arm."},
        {"dimension": "assurance", "state": "FINITE_SCOPE", "limitation": "Observed validation and locked audit are not distribution-wide analytical guarantees."},
    ]))
    table_paths = []
    for name, data in table_rows:
        fields = sorted({key for row in data for key in row})
        path = tables / name
        write_csv(path, fields, data)
        table_paths.append(path)

    v7_rows = csv_file(ROOT / "docs/evidence/external_end_to_end_code_v7/execution_accounting.csv")
    v7_unique = {row["provider"]: int(row["unique_inputs"]) for row in v7_rows if row["provider"] in {"eva", "heir", "corelab"}}
    depth_labels = ["EVA V7", "EVA V8", "HEIR V7", "HEIR V8", "CoreLab V7", "CoreLab V8"]
    depth_exact = [v7_unique["eva"], 1000, v7_unique["heir"], 1000, v7_unique["corelab"], 200]
    depth_plot = [math.log10(value + 1) for value in depth_exact]
    bar_figure(figures / "figure_01_v7_to_v8_evidence_depth.svg", "V7 to V8 evidence-depth improvement", "Bar height uses log10(unique inputs + 1); labels report exact unique-input counts.", depth_labels, depth_plot, ["#8c98a8", "#1f6feb", "#8c98a8", "#1f6feb", "#8c98a8", "#1f6feb"], [str(value) for value in depth_exact])

    eva_flips = [next(arm for arm in eva_manifest["arms"] if arm["scale_bits"] == scale)["validation"]["decision_flips"] for scale in (20, 30, 40)]
    bar_figure(figures / "figure_02_eva_scale_decision_flips.svg", "EVA validation decision flips by scale", "Three predeclared native EVA scale arms; 500 validation inputs and three contexts per arm.", ["scale20", "scale30", "scale40"], eva_flips, ["#cf222e", "#2da44e", "#2da44e"])

    arm_stats = {}
    for arm in ("heir_generated", "flipguard_direct", "bounded_catalog"):
        rows_for_arm = [row for row in common_data["records"] if row["arm"] == arm]
        arm_stats[arm] = (statistics.fmean(float(row["total_ms"]) for row in rows_for_arm), sum(bool(row["decision_flip"]) for row in rows_for_arm))
    plane = [f'<line x1="100" y1="570" x2="1135" y2="570" stroke="#9ba7b5" stroke-width="2"/>', f'<line x1="100" y1="130" x2="100" y2="570" stroke="#9ba7b5" stroke-width="2"/>', svg_text(620, 635, "Mean total latency (ms)", 19, "middle"), svg_text(32, 350, "Flips", 19, "middle")]
    max_latency = max(value[0] for value in arm_stats.values())
    colors = {"heir_generated": "#2f9eca", "flipguard_direct": "#cf222e", "bounded_catalog": "#8250df"}
    for arm, (latency, flips) in arm_stats.items():
        x = 100 + latency / max_latency * 1010
        y = 570 - flips / 8 * 390
        anchor = "end" if x > 950 else "start" if x < 250 else "middle"
        label_x = x - 10 if anchor == "end" else x + 10 if anchor == "start" else x
        plane.extend([f'<circle cx="{x:.1f}" cy="{y:.1f}" r="13" fill="{colors[arm]}"/>', svg_text(label_x, y - 22, f"{arm}: {latency:.2f} ms, {flips} flips", 17, anchor, weight=700)])
    write_svg(figures / "figure_03_common_latency_decision_plane.svg", "Common-executor latency and decision outcomes", "Same Lattigo harness; direct-arm flips make latency ratios diagnostic only.", plane)

    points = []
    plan_records = {plan["plan_id"]: plan for plan in (json_file(path) for path in sorted((OUTPUTS / "corelab/linear-regression-multi-input-v8/plans").glob("*.json"))) if plan["status"] == "PASS"}
    plan_stats = []
    for plan in plan_records.values():
        latency = statistics.fmean(float(row["total_ms"]) for row in plan["records"])
        error = max(float(row["rms_error"]) for row in plan["records"])
        plan_stats.append((plan["mode"], plan["waterline"], latency, error))
    min_x, max_x = min(item[2] for item in plan_stats), max(item[2] for item in plan_stats)
    logs = [math.log10(max(item[3], 1e-18)) for item in plan_stats]
    min_y, max_y = min(logs), max(logs)
    points.extend([f'<line x1="100" y1="570" x2="1135" y2="570" stroke="#9ba7b5" stroke-width="2"/>', f'<line x1="100" y1="130" x2="100" y2="570" stroke="#9ba7b5" stroke-width="2"/>', svg_text(620, 635, "Mean per-input total latency (ms)", 19, "middle"), svg_text(80, 120, "log10(max RMS error)", 17)])
    for mode, waterline, latency, error in plan_stats:
        x = 100 + (latency - min_x) / max(max_x - min_x, 1e-12) * 1010
        log_error = math.log10(max(error, 1e-18))
        y = 570 - (log_error - min_y) / max(max_y - min_y, 1e-12) * 410
        color = "#1f6feb" if mode == "eva" else "#2da44e"
        points.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}"><title>{mode}_{waterline}: {latency:.6g} ms, RMS {error:.6g}</title></circle>')
    points.extend([svg_text(935, 135, "EVA", 17, color="#1f6feb", weight=700), svg_text(1030, 135, "ELASM", 17, color="#2da44e", weight=700)])
    write_svg(figures / "figure_04_corelab_error_latency.svg", "CoreLab plan error-latency distribution", "Seventy completed numerical plans over 200 unique inputs per plan; failed plans are reported separately.", points)

    flow = []
    boxes = [(55, "EVA scale30", "SAFE audit", "#2f9eca"), (330, "HEIR Lattigo", "SAFE audit", "#2f9eca"), (605, "FlipGuard direct", "8 common-repeat flips", "#cf222e"), (880, "Catalog fastest", "SAFE audit", "#8250df")]
    for x, name, state, color in boxes:
        flow.extend([f'<rect x="{x}" y="220" width="225" height="150" rx="6" fill="#f6f8fa" stroke="{color}" stroke-width="3"/>', svg_text(x + 112.5, 276, name, 20, "middle", weight=700), svg_text(x + 112.5, 317, "Decision-integrity gate", 15, "middle", color="#526072"), svg_text(x + 112.5, 350, state, 17, "middle", color=color, weight=700)])
        if x < 880:
            flow.append(f'<path d="M {x + 225} 295 H {x + 267}" stroke="#526072" stroke-width="2" marker-end="url(#arrow)"/>')
    flow.insert(0, '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#526072"/></marker></defs>')
    flow.append(svg_text(600, 455, "Provider outputs are admitted or rejected by the same finite-scope gate; no provider is forced to win.", 18, "middle"))
    write_svg(figures / "figure_05_provider_gate_outcomes.svg", "Provider to gate to final evidence state", "Validation, locked audit, and common-repeat outcomes remain distinct.", flow)

    matrix = [f'<rect x="55" y="130" width="1090" height="440" fill="#f6f8fa" stroke="#d0d7de"/>']
    headers = ["Provider", "Unique inputs", "Contexts/key runs", "Passes", "Recorded rows"]
    xs = [85, 390, 590, 800, 955]
    for x, header in zip(xs, headers): matrix.append(svg_text(x, 173, header, 18, weight=700))
    display_rows = [("EVA", "1,000", "15", "1", "7,500"), ("HEIR", "1,000", "12", "1", "6,000"), ("CoreLab", "200/plan", "72 attempts", "1", "14,000"), ("Common harness", "100", "9 arm-keysets", "6 + warm-up", "5,400")]
    for index, values in enumerate(display_rows):
        y = 235 + index * 78
        matrix.append(f'<line x1="70" y1="{y + 24}" x2="1130" y2="{y + 24}" stroke="#d8dee4"/>')
        for x, value in zip(xs, values): matrix.append(svg_text(x, y, value, 18))
    matrix.append(svg_text(85, 540, "Raw rows are execution observations, not unique-input counts.", 17, color="#cf222e", weight=700))
    write_svg(figures / "figure_06_execution_accounting.svg", "Unique inputs, contexts, passes, and raw rows", "Counts use distinct units and do not treat repeated execution rows as independent inputs.", matrix)

    figure_paths = sorted(figures.glob("*.svg"))
    publication_root = Path("results/thesis_grade_protocol/focused_external_comparison_v8")
    publication = {
        "schema_version": "flipguard_focused_external_v8_publication_inputs_v1",
        "status": "FINAL_VERIFIED_INPUTS",
        "source_evidence": "docs/evidence/focused_external_comparison_v8",
        "table_count": len(table_paths),
        "figure_count": len(figure_paths),
        "tables": [{"path": (publication_root / path.relative_to(RESULTS)).as_posix(), "sha256": sha256(path)} for path in table_paths],
        "figures": [{"path": (publication_root / path.relative_to(RESULTS)).as_posix(), "sha256": sha256(path)} for path in figure_paths],
        "speculative_values": 0,
        "cross_runtime_ratio_claim_allowed": False,
        "common_executor_latency_claim_allowed": False,
    }
    (RESULTS / "publication_inputs_manifest.json").write_text(json.dumps(publication, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return publication


def flatten_eva() -> tuple[list[dict[str, object]], dict[str, object] | None]:
    root = OUTPUTS / "eva/shared-polynomial-threshold-v8"
    if not (root / "manifest.json").is_file():
        return [], None
    rows: list[dict[str, object]] = []
    for path in sorted(root.glob("validation_scale_*.csv")) + sorted(root.glob("audit_scale_*.csv")):
        rows.extend(csv_file(path))
    return rows, json_file(root / "manifest.json")


def flatten_heir() -> tuple[list[dict[str, object]], dict[str, object] | None]:
    root = OUTPUTS / "heir/shared-polynomial-threshold-v8"
    if not (root / "manifest.json").is_file():
        return [], None
    rows: list[dict[str, object]] = []
    for path in sorted(root.glob("lattigo_*.jsonl")):
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    for path in sorted(root.glob("openfhe_*.csv")):
        rows.extend(csv_file(path))
    fields = sorted({key for row in rows for key in row})
    write_csv(EVIDENCE / "heir_shared_polynomial_records.csv", fields, rows)
    return rows, json_file(root / "manifest.json")


def flipguard_facts() -> tuple[dict[str, object] | None, list[dict[str, object]], list[dict[str, object]]]:
    root = OUTPUTS / "flipguard/shared-polynomial-threshold-v8"
    if not (root / "manifest.json").is_file():
        return None, [], []
    manifest = json_file(root / "manifest.json")
    gate_rows = []
    audit_rows = []
    paths = [("direct", root / "direct_validation.json")]
    paths.extend((path.stem.removesuffix("_validation"), path) for path in sorted((root / "catalog").glob("*_validation.json")))
    for arm, path in paths:
        result = json_file(path)
        trial = result["trial"]
        candidate = result["bound_candidate"]["candidate"]
        gate_rows.append({
            "provider": "FlipGuard direct" if arm == "direct" else "Security-V2 bounded catalog",
            "arm": arm, "workload": "shared_polynomial_threshold_v8", "candidate_id": candidate["id"],
            "status": trial["status"], "outcome": result["outcome"],
            "fresh_key_runs": trial["key_repeats_completed"], "unique_inputs": 500,
            "raw_observations": trial.get("encrypted_sample_evaluations", 1500),
            "decision_flips": trial["decision_flips"], "reserve_policy_violations": trial["error_violations"],
            "mean_total_ms": trial["mean_total_ms"], "security_state": candidate["security"]["final_admission"],
        })
    for arm, path in (("direct", root / "direct_locked_audit.json"), ("catalog_fastest_safe", root / "catalog_fastest_safe_locked_audit.json")):
        if path.is_file():
            result = json_file(path); trial = result["audit_trial"]
            audit_rows.append({
                "provider": "FlipGuard direct" if arm == "direct" else "Security-V2 bounded catalog",
                "arm": arm, "workload": "shared_polynomial_threshold_v8", "candidate_id": result["selected_candidate"]["id"],
                "outcome": result["outcome"], "status": trial["status"], "fresh_key_runs": trial["key_repeats_completed"],
                "unique_inputs": 500, "decision_flips": trial["decision_flips"],
                "reserve_policy_violations": trial["error_violations"], "retuning": result["retuning_performed"],
            })
    return manifest, gate_rows, audit_rows


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    end_timestamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    start_timestamp = (STATUS / "autonomous_start_timestamp.txt").read_text().strip() if (STATUS / "autonomous_start_timestamp.txt").is_file() else "NOT_RECORDED"
    run_manifest = json_file(ROOT / "external/v8/manifests/run_manifest.json")
    current_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True, capture_output=True,
    ).stdout.strip()
    comparison_digest = hashlib.sha256()
    for source in (
        ROOT / "scripts/external_v8/finalize_v8.py",
        ROOT / "docs/evidence/focused_external_comparison_v8/verify_focused_external_comparison_v8.py",
    ):
        comparison_digest.update(source.relative_to(ROOT).as_posix().encode("utf-8") + b"\0")
        comparison_digest.update(hashlib.sha256(source.read_bytes()).digest())
    environment_start = {
        "schema_version": "flipguard_focused_external_v8_environment_v1",
        "timestamp": start_timestamp, "hostname_redacted": True,
        "platform": platform.platform(), "python": platform.python_version(),
        "cpu_count": os.cpu_count(), "v7_binding": "external/v8/manifests/v7_binding.json",
    }
    (EVIDENCE / "environment_start.json").write_text(json.dumps(environment_start, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    environment_end = {**environment_start, "timestamp": end_timestamp, "phase": "final_freeze"}
    (EVIDENCE / "environment_end.json").write_text(json.dumps(environment_end, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    eva_rows, eva_manifest = flatten_eva()
    if eva_rows:
        write_csv(EVIDENCE / "eva_population_records.csv", list(eva_rows[0]), eva_rows)
    else:
        write_csv(EVIDENCE / "eva_population_records.csv", ["provider", "status", "reason"], [{"provider": "Microsoft EVA", "status": "NOT_EVALUATED", "reason": "MISSING_COMPLETED_MANIFEST"}])
    heir_rows, heir_manifest = flatten_heir()
    if not heir_rows:
        write_csv(EVIDENCE / "heir_shared_polynomial_records.csv", ["provider", "status", "reason"], [{"provider": "Google HEIR", "status": "NOT_EVALUATED", "reason": "MISSING_COMPLETED_MANIFEST"}])
    corelab_root = OUTPUTS / "corelab/linear-regression-multi-input-v8"
    corelab_manifest = json_file(corelab_root / "manifest.json") if (corelab_root / "manifest.json").is_file() else None
    if corelab_manifest:
        copy_csv(corelab_root / "records.csv", EVIDENCE / "corelab_multi_input_records.csv")
    else:
        write_csv(EVIDENCE / "corelab_multi_input_records.csv", ["provider", "status", "reason"], [{"provider": "CoreLab EVA/ELASM", "status": "NOT_EVALUATED", "reason": "MISSING_COMPLETED_MANIFEST"}])

    flipguard_manifest, gate_rows, flipguard_audits = flipguard_facts()
    eva_complete = bool(eva_manifest and eva_manifest.get("status") == "PASS")
    heir_complete = bool(heir_manifest and heir_manifest.get("status") == "PASS")
    corelab_complete = bool(
        corelab_manifest
        and corelab_manifest.get("status") in {"PASS", "PARTIAL_SCIENTIFIC_RESULT"}
        and corelab_manifest.get("raw_plan_input_rows", 0) > 0
    )
    corelab_claim_state = (
        "SUPPORTED" if corelab_manifest and corelab_manifest.get("status") == "PASS"
        else "PARTIALLY_SUPPORTED" if corelab_complete
        else "NOT_EVALUATED"
    )
    flipguard_complete = bool(flipguard_manifest and flipguard_manifest.get("status") == "PASS")
    common_path = OUTPUTS / "flipguard/shared-polynomial-threshold-v8/common_executor_paired_latency.json"
    common_data = json_file(common_path) if common_path.is_file() else None
    common_safe = False
    if heir_manifest:
        validation = next(
            row for row in heir_manifest["runtime_summaries"]["lattigo_v6_2"]
            if row["role"] == "configuration_validation"
        )
        safe = validation["decision_flips"] == 0 and validation["reserve_policy_violations"] == 0
        gate_rows.append({
            "provider": "Google HEIR", "arm": "heir_generated_lattigo_v8",
            "workload": "shared_polynomial_threshold_v8", "candidate_id": "heir_generated_lattigo_v8",
            "status": "SAFE" if safe else "REJECTED", "outcome": "SELECTED" if safe else "NO_SAFE",
            "fresh_key_runs": validation["fresh_contexts"], "unique_inputs": validation["unique_inputs"],
            "raw_observations": validation["raw_observations"], "decision_flips": validation["decision_flips"],
            "reserve_policy_violations": validation["reserve_policy_violations"], "mean_total_ms": "",
            "security_state": heir_manifest["lattigo_v6_2_parameters"]["final_admission"],
        })
    if common_data and heir_manifest and flipguard_manifest:
        heir_audit = next(
            row for row in heir_manifest["runtime_summaries"]["lattigo_v6_2"]
            if row["role"] == "locked_audit"
        )
        common_safe = (
            heir_audit["decision_flips"] == 0
            and heir_audit["reserve_policy_violations"] == 0
            and flipguard_manifest["direct"]["locked_audit_outcome"] == "LOCKED_AUDIT_PASS"
            and flipguard_manifest["catalog"]["locked_audit_outcome"] == "LOCKED_AUDIT_PASS"
            and all(not row["decision_flip"] and not row["reserve_violation"] for row in common_data["records"])
        )
    common_flip_rows = [row for row in common_data["records"] if row["decision_flip"]] if common_data else []
    common_violation_rows = [row for row in common_data["records"] if row["reserve_violation"]] if common_data else []
    write_csv(EVIDENCE / "provider_gate_records.csv", sorted({key for row in gate_rows for key in row}) or ["provider", "status"], gate_rows or [{"provider": "FlipGuard", "status": "NOT_EVALUATED"}])
    audit_rows: list[dict[str, object]] = list(flipguard_audits)
    if eva_manifest:
        audit_rows.extend({"provider": "Microsoft EVA", "arm": f"scale{row['scale_bits']}", "workload": "shared_polynomial_threshold_v8", "candidate_id": row["candidate_id"], "outcome": row["status"], "status": row["status"], "fresh_key_runs": row["contexts"], "unique_inputs": row["unique_inputs"], "decision_flips": row["decision_flips"], "reserve_policy_violations": row["reserve_policy_violations"], "retuning": row["retuning"]} for row in eva_manifest["audits"])
    if heir_manifest:
        for runtime, summaries in heir_manifest["runtime_summaries"].items():
            summary = next(row for row in summaries if row["role"] == "locked_audit")
            audit_rows.append({"provider": "Google HEIR", "arm": runtime, "workload": "shared_polynomial_threshold_v8", "candidate_id": f"heir_{runtime}_shared_polynomial", "outcome": "SAFE" if summary["decision_flips"] == 0 and summary["reserve_policy_violations"] == 0 else "REJECTED", "status": "SAFE" if summary["decision_flips"] == 0 and summary["reserve_policy_violations"] == 0 else "REJECTED", "fresh_key_runs": summary["fresh_contexts"], "unique_inputs": summary["unique_inputs"], "decision_flips": summary["decision_flips"], "reserve_policy_violations": summary["reserve_policy_violations"], "retuning": 0})
    write_csv(EVIDENCE / "audit_records.csv", sorted({key for row in audit_rows for key in row}) or ["provider", "status"], audit_rows or [{"provider": "none", "status": "NOT_EVALUATED"}])

    common_rows = []
    if common_data:
        for row in common_data["records"]:
            common_rows.append({
                **row, "runtime": "Lattigo v6.2.0", "workload": "shared_polynomial_threshold_v8",
                "portability": "PORTABLE_EXACT" if row["arm"] == "heir_generated" else "NATIVE_FLIPGUARD_ARM",
                "security_state": "PASS", "latency_state": "PAIRED_HEADLINE" if common_safe else "PAIRED_DIAGNOSTIC_UNSAFE_ARM",
            })
    write_csv(EVIDENCE / "common_executor_records.csv", list(common_rows[0]) if common_rows else ["provider", "status"], common_rows or [{"provider": "none", "status": "NOT_EVALUATED"}])
    mismatch_rows = [
        {"provider": "Microsoft EVA", "workload": "shared_polynomial_threshold_v8", "dimension": "runtime_and_modulus_schedule", "state": "NATIVE_ONLY", "reason": "EVA/SEAL native schedule is not an exact Lattigo literal"},
        {"provider": "CoreLab EVA/ELASM", "workload": "official_LinearRegression_multi_input_v8", "dimension": "output_semantics", "state": "NUMERICAL_ONLY", "reason": "official workload has no natural frozen threshold decision"},
        {"provider": "Google HEIR", "workload": "shared_polynomial_threshold_v8", "dimension": "operation_order", "state": "PORTABLE_EXACT", "reason": "the unmodified generated Lattigo evaluator is linked into the common harness"},
    ]
    write_csv(EVIDENCE / "operation_mismatch_records.csv", list(mismatch_rows[0]), mismatch_rows)

    latency_rows = []
    if eva_rows:
        for row in eva_rows:
            latency_rows.append({"provider": row["provider"], "runtime": "EVA/SEAL", "workload": row["workload"], "role": row["role"], "arm": f"scale{row['scale_bits']}", "context": row["context_index"], "row_id": row["row_id"], "timing_unit": "encrypted_batch_repeated_on_each_input_row", "evaluate_ms": row["evaluate_ms"], "total_ms": row["total_ms"], "comparison_state": "NATIVE_ONLY_NO_CROSS_RUNTIME_RATIO"})
    if heir_rows:
        for row in heir_rows:
            if str(row.get("runtime", "")).startswith("Lattigo"):
                latency_rows.append({"provider": "Google HEIR", "runtime": row["runtime"], "workload": "shared_polynomial_threshold_v8", "role": row["role"], "arm": "heir_generated", "context": row["context"], "row_id": row["row_id"], "timing_unit": "per_input", "evaluate_ms": row.get("evaluate_ms", ""), "total_ms": row.get("total_ms", ""), "comparison_state": "UNPAIRED_DIAGNOSTIC"})
    if common_data:
        for row in common_data["records"]:
            latency_rows.append({
                "provider": row["arm"], "runtime": "Lattigo v6.2.0 common harness",
                "workload": "shared_polynomial_threshold_v8", "role": "locked_audit_latency_subset",
                "arm": row["arm"], "context": row["keyset"], "row_id": row["row_id"],
                "timing_unit": "per_input", "evaluate_ms": row["evaluate_ms"],
                "total_ms": row["total_ms"], "comparison_state": "PAIRED_HEADLINE" if common_safe else "PAIRED_DIAGNOSTIC_UNSAFE_ARM",
            })
    write_csv(EVIDENCE / "latency_records.csv", list(latency_rows[0]) if latency_rows else ["provider", "status"], latency_rows or [{"provider": "none", "status": "NOT_EVALUATED"}])
    latency_summary = []
    for provider in sorted({str(row["provider"]) for row in latency_rows}):
        values = [float(row["total_ms"]) for row in latency_rows if row["provider"] == provider and str(row["total_ms"]) not in {"", "None"}]
        latency_summary.append({"provider": provider, "observations": len(values), "mean_total_ms": statistics.fmean(values) if values else "", "median_total_ms": statistics.median(values) if values else "", "p95_total_ms": sorted(values)[max(0, math.ceil(0.95 * len(values)) - 1)] if values else "", "comparison_state": "NO_CROSS_RUNTIME_RATIO"})
    write_csv(EVIDENCE / "latency_summary.csv", list(latency_summary[0]) if latency_summary else ["provider", "status"], latency_summary or [{"provider": "none", "status": "NOT_EVALUATED"}])
    pair_summaries = []
    if common_data:
        pair_summaries = [
            paired_ratio_summary(common_data["records"], "heir_generated", "flipguard_direct"),
            paired_ratio_summary(common_data["records"], "bounded_catalog", "flipguard_direct"),
            paired_ratio_summary(common_data["records"], "bounded_catalog", "heir_generated"),
        ]
        for summary in pair_summaries:
            summary["claim_state"] = "PAIRED_HEADLINE" if common_safe else "BLOCKED_DIAGNOSTIC_UNSAFE_ARM"
            summary["common_executor_decision_flips"] = len(common_flip_rows)
        write_csv(EVIDENCE / "common_executor_paired_summary.csv", list(pair_summaries[0]), pair_summaries)
    else:
        write_csv(EVIDENCE / "common_executor_paired_summary.csv", ["comparison", "status"], [{"comparison": "none", "status": "NOT_EVALUATED"}])

    error_summary = []
    if eva_manifest:
        for arm in eva_manifest["arms"]:
            error_summary.append({"provider": "Microsoft EVA", "arm": f"scale{arm['scale_bits']}", "role": "configuration_validation", "max_absolute_error": arm["validation"]["max_absolute_error"], "max_normalized_budget_usage": arm["validation"]["max_normalized_budget_usage"], "decision_flips": arm["validation"]["decision_flips"], "violations": arm["validation"]["reserve_policy_violations"]})
    if heir_manifest:
        for runtime, summaries in heir_manifest["runtime_summaries"].items():
            for item in summaries:
                error_summary.append({"provider": f"Google HEIR/{runtime}", "arm": runtime, "role": item["role"], "max_absolute_error": item["max_absolute_error"], "max_normalized_budget_usage": item["max_normalized_budget_usage"], "decision_flips": item["decision_flips"], "violations": item["reserve_policy_violations"]})
    write_csv(EVIDENCE / "numerical_error_summary.csv", list(error_summary[0]) if error_summary else ["provider", "status"], error_summary or [{"provider": "none", "status": "NOT_EVALUATED"}])

    accounting = [
        {"provider": "Microsoft EVA", "workload": "shared_polynomial_threshold_v8", "unique_inputs": observed_or_not_evaluated(eva_complete, 1000), "contexts": observed_or_not_evaluated(eva_complete, 15), "plans_or_arms": observed_or_not_evaluated(eva_complete, 5), "raw_rows": observed_or_not_evaluated(eva_complete, len(eva_rows)), "row_meaning": "input-context-arm observations"},
        {"provider": "Google HEIR", "workload": "shared_polynomial_threshold_v8", "unique_inputs": observed_or_not_evaluated(heir_complete, 1000), "contexts": observed_or_not_evaluated(heir_complete, 12), "plans_or_arms": observed_or_not_evaluated(heir_complete, 4), "raw_rows": observed_or_not_evaluated(heir_complete, len(heir_rows)), "row_meaning": "input-context-runtime-role observations"},
        {"provider": "CoreLab EVA/ELASM", "workload": "official_LinearRegression_multi_input_v8", "unique_inputs": observed_or_not_evaluated(corelab_complete, corelab_manifest["unique_inputs_per_completed_plan"] if corelab_manifest else None), "contexts": observed_or_not_evaluated(corelab_complete, corelab_manifest["fresh_contexts"] if corelab_manifest else None), "plans_or_arms": observed_or_not_evaluated(corelab_complete, corelab_manifest["plans_completed"] if corelab_manifest else None), "raw_rows": observed_or_not_evaluated(corelab_complete, corelab_manifest["raw_plan_input_rows"] if corelab_manifest else None), "row_meaning": "unique-input-plan observations; two failed plans emitted no rows"},
        {"provider": "FlipGuard", "workload": "shared_polynomial_threshold_v8", "unique_inputs": observed_or_not_evaluated(flipguard_complete, 1000), "contexts": observed_or_not_evaluated(flipguard_complete, 30), "plans_or_arms": "SEE_EXECUTION_ACCOUNTING" if flipguard_complete else "NOT_EVALUATED", "raw_rows": observed_or_not_evaluated(bool(common_data), len(common_data["records"]) if common_data else None), "row_meaning": "selection/audit summaries plus common-harness measurement rows; see execution accounting"},
    ]
    write_csv(EVIDENCE / "unique_input_accounting.csv", list(accounting[0]), accounting)
    execution = [
        {"provider": "Microsoft EVA", "phase": "native_validation_and_locked_audit", "workload": "shared_polynomial_threshold_v8", "unique_inputs": 1000, "validation_inputs": 500, "audit_inputs": 500, "validation_audit_overlap": 0, "plans_or_arms": 5, "candidate_trials": 5, "encrypted_candidate_executions": 5, "fresh_contexts_or_keysets": 15, "key_runs": 15, "measurement_passes": 1, "warmup_encrypted_sample_evaluations": 0, "recorded_encrypted_sample_evaluations": 7500, "total_encrypted_sample_evaluations": 7500, "raw_output_rows": len(eva_rows), "decision_bearing_rows": len(eva_rows), "execution_state": "PASS" if eva_complete else "NOT_EVALUATED"},
        {"provider": "Google HEIR", "phase": "native_and_translated_validation_and_locked_audit", "workload": "shared_polynomial_threshold_v8", "unique_inputs": 1000, "validation_inputs": 500, "audit_inputs": 500, "validation_audit_overlap": 0, "plans_or_arms": 4, "candidate_trials": 4, "encrypted_candidate_executions": 4, "fresh_contexts_or_keysets": 12, "key_runs": 12, "measurement_passes": 1, "warmup_encrypted_sample_evaluations": 0, "recorded_encrypted_sample_evaluations": 6000, "total_encrypted_sample_evaluations": 6000, "raw_output_rows": len(heir_rows), "decision_bearing_rows": len(heir_rows), "execution_state": "PASS" if heir_complete else "NOT_EVALUATED"},
        {"provider": "CoreLab EVA/ELASM", "phase": "native_numerical_plan_grid", "workload": "official_LinearRegression_multi_input_v8", "unique_inputs": 200, "validation_inputs": 200, "audit_inputs": "NOT_APPLICABLE_NUMERICAL_ONLY", "validation_audit_overlap": "NOT_APPLICABLE", "plans_or_arms": 72, "candidate_trials": 72, "encrypted_candidate_executions": 70, "fresh_contexts_or_keysets": 72, "key_runs": 70, "measurement_passes": 1, "warmup_encrypted_sample_evaluations": 0, "recorded_encrypted_sample_evaluations": 14000, "total_encrypted_sample_evaluations": 14000, "raw_output_rows": 14000, "decision_bearing_rows": 0, "execution_state": corelab_manifest["status"] if corelab_manifest else "NOT_EVALUATED"},
        {"provider": "FlipGuard direct", "phase": "direct_synthesis_trials", "workload": "shared_polynomial_threshold_v8", "unique_inputs": 500, "validation_inputs": 500, "audit_inputs": 0, "validation_audit_overlap": 0, "plans_or_arms": 2, "candidate_trials": 2, "encrypted_candidate_executions": 2, "fresh_contexts_or_keysets": 6, "key_runs": 6, "measurement_passes": 1, "warmup_encrypted_sample_evaluations": 0, "recorded_encrypted_sample_evaluations": 3000, "total_encrypted_sample_evaluations": 3000, "raw_output_rows": "SUMMARY_ONLY_NO_PER_SAMPLE_LEDGER", "decision_bearing_rows": 3000, "execution_state": "PASS" if flipguard_complete else "NOT_EVALUATED"},
        {"provider": "FlipGuard direct", "phase": "provider_literal_validation", "workload": "shared_polynomial_threshold_v8", "unique_inputs": 500, "validation_inputs": 500, "audit_inputs": 0, "validation_audit_overlap": 0, "plans_or_arms": 1, "candidate_trials": 1, "encrypted_candidate_executions": 1, "fresh_contexts_or_keysets": 3, "key_runs": 3, "measurement_passes": 1, "warmup_encrypted_sample_evaluations": 0, "recorded_encrypted_sample_evaluations": 1500, "total_encrypted_sample_evaluations": 1500, "raw_output_rows": "SUMMARY_ONLY_NO_PER_SAMPLE_LEDGER", "decision_bearing_rows": 1500, "execution_state": "PASS" if flipguard_complete else "NOT_EVALUATED"},
        {"provider": "FlipGuard direct", "phase": "locked_audit", "workload": "shared_polynomial_threshold_v8", "unique_inputs": 500, "validation_inputs": 0, "audit_inputs": 500, "validation_audit_overlap": 0, "plans_or_arms": 1, "candidate_trials": 1, "encrypted_candidate_executions": 1, "fresh_contexts_or_keysets": 3, "key_runs": 3, "measurement_passes": 1, "warmup_encrypted_sample_evaluations": 0, "recorded_encrypted_sample_evaluations": 1500, "total_encrypted_sample_evaluations": 1500, "raw_output_rows": "SUMMARY_ONLY_NO_PER_SAMPLE_LEDGER", "decision_bearing_rows": 1500, "execution_state": "PASS" if flipguard_complete else "NOT_EVALUATED"},
        {"provider": "Security-V2 bounded catalog", "phase": "catalog_validation", "workload": "shared_polynomial_threshold_v8", "unique_inputs": 500, "validation_inputs": 500, "audit_inputs": 0, "validation_audit_overlap": 0, "plans_or_arms": 7, "candidate_trials": 7, "encrypted_candidate_executions": 2, "fresh_contexts_or_keysets": 6, "key_runs": 6, "measurement_passes": 1, "warmup_encrypted_sample_evaluations": 0, "recorded_encrypted_sample_evaluations": 3000, "total_encrypted_sample_evaluations": 3000, "raw_output_rows": "SUMMARY_ONLY_NO_PER_SAMPLE_LEDGER", "decision_bearing_rows": 3000, "execution_state": "PARTIAL_PLAN_SUPPORT_2_OF_7" if flipguard_complete else "NOT_EVALUATED"},
        {"provider": "Security-V2 bounded catalog", "phase": "fastest_safe_locked_audit", "workload": "shared_polynomial_threshold_v8", "unique_inputs": 500, "validation_inputs": 0, "audit_inputs": 500, "validation_audit_overlap": 0, "plans_or_arms": 1, "candidate_trials": 1, "encrypted_candidate_executions": 1, "fresh_contexts_or_keysets": 3, "key_runs": 3, "measurement_passes": 1, "warmup_encrypted_sample_evaluations": 0, "recorded_encrypted_sample_evaluations": 1500, "total_encrypted_sample_evaluations": 1500, "raw_output_rows": "SUMMARY_ONLY_NO_PER_SAMPLE_LEDGER", "decision_bearing_rows": 1500, "execution_state": "PASS" if flipguard_complete else "NOT_EVALUATED"},
        {"provider": "Common Lattigo harness", "phase": "paired_latency", "workload": "shared_polynomial_threshold_v8", "unique_inputs": 100, "validation_inputs": 0, "audit_inputs": 100, "validation_audit_overlap": 0, "plans_or_arms": 3, "candidate_trials": 3, "encrypted_candidate_executions": 3, "fresh_contexts_or_keysets": 9, "key_runs": 9, "measurement_passes": 6, "warmup_encrypted_sample_evaluations": 900, "recorded_encrypted_sample_evaluations": 5400, "total_encrypted_sample_evaluations": 6300, "raw_output_rows": 5400, "decision_bearing_rows": 5400, "execution_state": "BLOCKED_DIAGNOSTIC_UNSAFE_ARM" if common_data and not common_safe else "PASS" if common_safe else "NOT_EVALUATED"},
    ]
    write_csv(EVIDENCE / "execution_accounting.csv", list(execution[0]), execution)

    security = [
        {"provider": "Microsoft EVA", "runtime": "SEAL native", "scheme": "CKKS", "log_n": "", "q": "", "p": "", "log_qp": "", "scale_bits": "20/30/40", "distribution": "native runtime model", "standard": "native compiler security_level=128", "state": "NATIVE_RUNTIME_SECURITY_NOT_EQUIVALENT_TO_LATTIGO_SECURITY_V2", "headline_eligible": False},
        {"provider": "Google HEIR", "runtime": "Lattigo v6.2.0", "scheme": "CKKS", "log_n": heir_manifest["lattigo_v6_2_parameters"]["log_n"] if heir_complete else "", "q": json.dumps(heir_manifest["lattigo_v6_2_parameters"]["q_primes"]) if heir_complete else "", "p": json.dumps(heir_manifest["lattigo_v6_2_parameters"]["p_primes"]) if heir_complete else "", "log_qp": heir_manifest["lattigo_v6_2_parameters"]["log_qp"] if heir_complete else "", "scale_bits": heir_manifest["lattigo_v6_2_parameters"]["log_default_scale"] if heir_complete else "", "distribution": "Xs=ring.Ternary(P=2/3); Xe=ring.DiscreteGaussian(sigma=3.2,bound=19.2)", "standard": "Security Guidelines Table 5.2 conservative admission", "state": heir_manifest["lattigo_v6_2_parameters"]["final_admission"] if heir_complete else "NOT_EVALUATED", "headline_eligible": heir_complete},
        {"provider": "Google HEIR", "runtime": "OpenFHE", "scheme": "CKKS", "log_n": "", "q": "", "p": "", "log_qp": "", "scale_bits": "", "distribution": "native runtime model", "standard": "not aligned to Security V2", "state": "NATIVE_RUNTIME_SECURITY_MODEL_NOT_ALIGNED", "headline_eligible": False},
        {"provider": "FlipGuard direct/catalog", "runtime": "Lattigo v6.2.0", "scheme": "CKKS", "log_n": "bound in provider candidate manifests", "q": "bound in provider candidate manifests", "p": "bound in provider candidate manifests", "log_qp": "recomputed by provider gate", "scale_bits": "bound in provider candidate manifests", "distribution": "Xs=ring.Ternary(P=2/3); Xe=ring.DiscreteGaussian(sigma=3.2,bound=19.2)", "standard": "Security Guidelines Table 5.2 conservative admission", "state": "PASS" if flipguard_complete else "NOT_EVALUATED", "headline_eligible": flipguard_complete},
        {"provider": "CoreLab EVA/ELASM", "runtime": "SEAL native", "scheme": "CKKS", "log_n": "", "q": "", "p": "", "log_qp": "", "scale_bits": "waterline 15..50", "distribution": "native runtime model", "standard": "not aligned to Security V2", "state": "NATIVE_RUNTIME_SECURITY_MODEL_NOT_ALIGNED", "headline_eligible": False},
    ]
    write_csv(EVIDENCE / "security_summary.csv", list(security[0]), security)
    portability = [
        {"provider": "Microsoft EVA", "state": "NATIVE_ONLY", "exact_graph": True, "common_executor": False},
        {"provider": "Google HEIR Lattigo", "state": "PORTABLE_EXACT" if common_data else "NOT_EVALUATED", "exact_graph": True, "common_executor": bool(common_data)},
        {"provider": "Google HEIR OpenFHE", "state": "NATIVE_ONLY", "exact_graph": True, "common_executor": False},
        {"provider": "CoreLab EVA/ELASM", "state": "DIFFERENT_MODEL_NUMERICAL_ONLY", "exact_graph": False, "common_executor": False},
    ]
    write_csv(EVIDENCE / "portability_summary.csv", list(portability[0]), portability)
    corelab_plan_status = []
    if corelab_manifest:
        for path in sorted((corelab_root / "plans").glob("*.json")):
            plan = json_file(path)
            corelab_plan_status.append({
                "plan_id": plan["plan_id"], "mode": plan["mode"],
                "waterline": plan["waterline"], "status": plan["status"],
                "unique_inputs": plan["unique_inputs"], "raw_output_rows": len(plan["records"]),
                "reason_code": plan.get("reason_code", ""), "exit_code": plan.get("exit_code", ""),
                "plan_sha256": plan.get("plan_sha256", ""),
                "constants_sha256": plan.get("constants_sha256", ""),
                "failure_log_sha256": plan.get("failure_log_sha256", ""),
            })
    write_csv(
        EVIDENCE / "corelab_plan_status.csv",
        list(corelab_plan_status[0]) if corelab_plan_status else ["plan_id", "status"],
        corelab_plan_status or [{"plan_id": "none", "status": "NOT_EVALUATED"}],
    )

    recovery_rows = [
        {"sequence": 1, "provider": "Microsoft EVA", "reason_code": "EVA_OUTPUT_OWNERSHIP_RECOVERY", "failure_class": "RECOVERABLE_IMPLEMENTATION_FAILURE", "action": "normalize Docker-owned output permissions without encrypted rerun", "encrypted_rerun": False, "candidate_changed": False, "policy_changed": False, "result": "PASS"},
        {"sequence": 2, "provider": "Google HEIR", "reason_code": "HEIR_BAZEL_WORKSPACE_CWD_RECOVERY", "failure_class": "RECOVERABLE_IMPLEMENTATION_FAILURE", "action": "invoke the exact preflight-built runner from its Bazel workspace; reuse completed Lattigo rows", "encrypted_rerun": "OPENFHE_ONLY_AFTER_PREEXECUTION_FAILURE", "candidate_changed": False, "policy_changed": False, "result": "PASS"},
        {"sequence": 3, "provider": "FlipGuard", "reason_code": "FLIPGUARD_PROVIDER_SCHEMA_LABEL_RECOVERY", "failure_class": "RECOVERABLE_IMPLEMENTATION_FAILURE", "action": "serialize the same direct literal with the supported provider schema", "encrypted_rerun": "TARGETED_AFTER_PREEXECUTION_FAILURE", "candidate_changed": False, "policy_changed": False, "result": "PASS"},
        {"sequence": 4, "provider": "FlipGuard locked audit", "reason_code": "CUSTOM_SPLIT_ID_AND_PATH_REPRESENTATION_NORMALIZATION", "failure_class": "RECOVERABLE_IMPLEMENTATION_FAILURE", "action": "bind the frozen named split ID and canonical paths without changing rows", "encrypted_rerun": "TARGETED_AFTER_PREEXECUTION_IDENTITY_FAILURE", "candidate_changed": False, "policy_changed": False, "result": "PASS"},
        {"sequence": 5, "provider": "Security-V2 bounded catalog", "reason_code": "SCHEMA2_MIXED_LOG_AND_CONCRETE_MODULI", "failure_class": "RECOVERABLE_IMPLEMENTATION_FAILURE", "action": "retain exact concrete Q/P and remove duplicate log hints", "encrypted_rerun": "TARGETED_AFTER_PREEXECUTION_SCHEMA_FAILURE", "candidate_changed": False, "policy_changed": False, "result": "PASS"},
        {"sequence": 6, "provider": "Security-V2 bounded catalog", "reason_code": "CATALOG_PLAN_UNSUPPORTED_CONTINUATION", "failure_class": "PARTIAL_SCIENTIFIC_RESULT", "action": "record five insufficient-depth profiles and continue the two supported profiles", "encrypted_rerun": False, "candidate_changed": False, "policy_changed": False, "result": "2_SAFE_5_PLAN_UNSUPPORTED"},
        {"sequence": 7, "provider": "CoreLab EVA/ELASM", "reason_code": "CORELAB_MONOLITHIC_NATIVE_MEMORY_GROWTH", "failure_class": "RECOVERABLE_IMPLEMENTATION_FAILURE", "action": "execute each frozen plan in a short-lived process and resume completed plan files", "encrypted_rerun": "ONLY_INCOMPLETE_PLANS", "candidate_changed": False, "policy_changed": False, "result": "PASS_PROCESS_ISOLATION"},
        {"sequence": 8, "provider": "CoreLab ELASM", "reason_code": "NATIVE_PLAN_EXECUTION_ABORT", "failure_class": "PARTIAL_SCIENTIFIC_RESULT", "action": "preserve elasm_36 and elasm_41 NTT mismatch failures with zero output rows; continue independent plans", "encrypted_rerun": "ELASM_36_ONE_DIAGNOSTIC_RETRY_ELASM_41_NO_RETRY", "candidate_changed": False, "policy_changed": False, "result": "70_PASS_2_EXECUTION_FAILED"},
    ]
    write_csv(EVIDENCE / "recovery_provenance.csv", list(recovery_rows[0]), recovery_rows)

    failures = []
    if corelab_manifest and corelab_manifest.get("plans_failed"):
        failures.append({"provider": "CoreLab EVA/ELASM", "reason_code": "NATIVE_PLAN_EXECUTION_ABORT", "count": corelab_manifest["plans_failed"], "unique_failure_inputs": 0, "affected_arm": "elasm_36;elasm_41", "claim_effect": "NUMERICAL_GRID_PARTIALLY_SUPPORTED"})
    if corelab_manifest and corelab_manifest["plans_unavailable"]:
        failures.append({"provider": "CoreLab EVA/ELASM", "reason_code": "PLAN_UNAVAILABLE_FROM_V7_EXECUTION", "count": corelab_manifest["plans_unavailable"], "unique_failure_inputs": 0, "affected_arm": "", "claim_effect": "NUMERICAL_GRID_PARTIAL"})
    if not common_data:
        failures.append({"provider": "common", "reason_code": "PAIRED_LATENCY_NOT_EVALUATED", "count": 1, "unique_failure_inputs": 0, "affected_arm": "", "claim_effect": "LATENCY_CLAIM_BLOCKED"})
    elif not common_safe:
        failures.append({"provider": "Common Lattigo harness", "reason_code": "COMMON_EXECUTOR_DECISION_FLIP", "count": len(common_flip_rows), "unique_failure_inputs": len({row["row_id"] for row in common_flip_rows}), "affected_arm": ";".join(sorted({row["arm"] for row in common_flip_rows})), "claim_effect": "PAIRED_LATENCY_CLAIM_BLOCKED_DIAGNOSTIC_ONLY"})
    write_csv(EVIDENCE / "failure_summary.csv", ["provider", "reason_code", "count", "unique_failure_inputs", "affected_arm", "claim_effect"], failures or [{"provider": "none", "reason_code": "NONE", "count": 0, "unique_failure_inputs": 0, "affected_arm": "", "claim_effect": "NONE"}])

    decision_providers = int(eva_complete) + int(heir_complete)
    locked_providers = decision_providers
    portable_exact = int(bool(common_data))
    graph_equivalent = int(bool(common_data))
    security_rows = sum(row["headline_eligible"] for row in security)
    path_a = bool(eva_complete and heir_complete and corelab_complete and flipguard_complete and decision_providers >= 2 and locked_providers >= 2 and graph_equivalent >= 1 and security_rows >= 2)
    classification = "EXTERNAL_COMPARISON_CLOSED" if path_a else "FINAL_VERIFIED_LIMITATION"
    claim_admission = {
        "schema_version": "flipguard_focused_external_v8_claim_admission_v1",
        "classification": classification,
        "paper_claim_allowed": False,
        "claims": {
            "eva_substantial_population_and_locked_audit": "SUPPORTED" if eva_complete else "NOT_EVALUATED",
            "heir_decision_bearing_shared_polynomial": "SUPPORTED" if heir_complete else "NOT_EVALUATED",
            "corelab_multi_input_numerical_grid": corelab_claim_state,
            "external_decision_bearing_providers_at_least_two": "SUPPORTED" if decision_providers >= 2 else "BLOCKED",
            "graph_equivalent_common_executor": "SUPPORTED" if graph_equivalent else "BLOCKED",
            "portable_exact": "SUPPORTED" if portable_exact else "NOT_EVALUATED",
            "paired_common_executor_latency": "SUPPORTED" if common_safe else "BLOCKED",
            "cross_runtime_speed_superiority": "BLOCKED",
        },
        "prohibited": ["raw rows as unique inputs", "cross-runtime latency ratio", "global optimum", "all external providers"],
    }
    (EVIDENCE / "claim_admission.json").write_text(json.dumps(claim_admission, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    limitations = """# Fairness limitations\n\n- Native EVA/SEAL, HEIR/OpenFHE, and CoreLab/SEAL timings are runtime-specific panels; no cross-runtime speed ratio is admitted.\n- The common Lattigo harness links HEIR's generated evaluator without changing its schedule and interleaves it with FlipGuard direct/catalog arms, but the arms necessarily use parameter-compatible independent keys. Eight decision flips on one near-threshold input in the direct arm make all common-harness latency ratios diagnostic only.\n- CoreLab's official LinearRegression graph has no natural frozen threshold output, so it contributes numerical multi-input evidence rather than a decision-integrity claim. Seventy plans completed; `elasm_36` and `elasm_41` failed before producing rows.\n- `PORTABLE_EXACT` applies only to the frozen HEIR-generated Lattigo arm on the exact shared polynomial; it is not a general compiler-portability claim.\n- All safety observations are finite-scope validation and locked-audit results, not distribution-wide or analytical guarantees.\n"""
    (EVIDENCE / "fairness_limitations.md").write_text(limitations, encoding="utf-8")
    report = f"""# Focused External Comparison V8 Checkpoint\n\n- Classification: `{classification}`\n- V7 predecessor: `a5e4ef8726784cbe504d3a8067469bf0b91d3886`\n- EVA unique inputs: `{1000 if eva_complete else 'NOT_EVALUATED'}`\n- HEIR unique inputs: `{1000 if heir_complete else 'NOT_EVALUATED'}`\n- CoreLab plans: `{corelab_manifest['plans_completed'] if corelab_complete else 'NOT_EVALUATED'}/72 completed; {corelab_manifest.get('plans_failed', 'NOT_EVALUATED') if corelab_manifest else 'NOT_EVALUATED'} native failures`\n- CoreLab unique inputs per completed plan: `{corelab_manifest['unique_inputs_per_completed_plan'] if corelab_complete else 'NOT_EVALUATED'}`\n- External decision-bearing providers: `{decision_providers}`\n- External locked-audit providers: `{locked_providers}`\n- GRAPH_EQUIVALENT common-executor rows: `{graph_equivalent}`\n- PORTABLE_EXACT external arms: `{portable_exact}`\n- Common-executor paired latency: `{'SUPPORTED' if common_safe else 'BLOCKED'}`\n- Common-executor decision flips: `{len(common_flip_rows) if common_data else 'NOT_EVALUATED'}` across `{len({row['row_id'] for row in common_flip_rows}) if common_data else 'NOT_EVALUATED'}` unique input(s)\n- Policy retuning: `0`\n- Manuscript modification: `0`\n"""
    (EVIDENCE / "CHECKPOINT_REPORT.md").write_text(report, encoding="utf-8")

    provider_manifest_dir = EVIDENCE / "provider_candidate_manifests"
    provider_manifest_dir.mkdir(exist_ok=True)
    if flipguard_manifest:
        source = OUTPUTS / "flipguard/shared-polynomial-threshold-v8/provider_requests"
        for path in source.glob("*.json"):
            shutil.copyfile(path, provider_manifest_dir / path.name)

    manifest = {
        "schema_version": "flipguard_focused_external_comparison_v8",
        "classification": classification,
        "predecessor_v7_manifest_sha256": "sha256:09d6e25b64bfbfc7c8e6d3945049b4492709e28695e95813508e97181f7c12cd",
        "source_commit": current_commit,
        "current_suite_commit": current_commit,
        "evidence_builder_commit": current_commit,
        "comparison_source_digest": "sha256:" + comparison_digest.hexdigest(),
        "execution_initial_commit": run_manifest["source_commit"],
        "execution_critical_source_digest": run_manifest["execution_critical_source_digest"],
        "audit_identity_repair_commit": "9de4ccf3a62d3a35ea2fb9762a937c329e74bb51",
        "catalog_plan_gate_commit": "be591718bbb185c8737889e68f26aeea483b8945",
        "corelab_failure_preservation_commit": "04f3f8d96c554fbe156826b063055ef7576d5268",
        "autonomous_start_timestamp": start_timestamp, "freeze_timestamp": end_timestamp,
        "providers": {"eva": eva_complete, "heir": heir_complete, "corelab": corelab_complete, "flipguard": flipguard_complete},
        "external_decision_bearing_provider_count": decision_providers,
        "external_locked_audit_provider_count": locked_providers,
        "portable_exact_count": portable_exact,
        "graph_equivalent_common_executor_count": graph_equivalent,
        "common_executor_record_count": len(common_data["records"]) if common_data else 0,
        "common_executor_decision_flips": len(common_flip_rows),
        "common_executor_unique_flip_inputs": len({row["row_id"] for row in common_flip_rows}),
        "common_executor_reserve_violations": len(common_violation_rows),
        "corelab_plans_attempted": corelab_manifest["plans_attempted"] if corelab_manifest else 0,
        "corelab_plans_completed": corelab_manifest["plans_completed"] if corelab_manifest else 0,
        "corelab_plans_failed": corelab_manifest.get("plans_failed", 0) if corelab_manifest else 0,
        "security_aligned_comparison_rows": security_rows,
        "raw_rows_are_not_unique_inputs": True,
        "cross_runtime_ratio_claim_allowed": False,
        "common_executor_latency_claim_allowed": common_safe,
        "policy_retuning": 0,
    }
    (EVIDENCE / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for name in ("provider_gate_records.csv", "audit_records.csv", "common_executor_records.csv", "common_executor_paired_summary.csv", "latency_summary.csv", "numerical_error_summary.csv", "unique_input_accounting.csv", "execution_accounting.csv", "security_summary.csv", "portability_summary.csv", "corelab_plan_status.csv", "recovery_provenance.csv", "failure_summary.csv"):
        shutil.copyfile(EVIDENCE / name, RESULTS / name)
    publication_inputs = build_publication_inputs(
        eva_manifest, heir_manifest, flipguard_manifest, corelab_manifest, common_data,
        eva_rows, heir_rows, common_rows, accounting, execution, gate_rows, audit_rows,
        corelab_plan_status, pair_summaries,
    )
    shutil.copyfile(RESULTS / "publication_inputs_manifest.json", EVIDENCE / "publication_inputs_manifest.json")
    (RESULTS / "claim_admission.json").write_text(json.dumps(claim_admission, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (RESULTS / "manifest.json").write_text(json.dumps({"schema_version": "flipguard_focused_external_v8_publication_inputs_v1", "source_evidence": "docs/evidence/focused_external_comparison_v8", "classification": classification, "table_count": publication_inputs["table_count"], "figure_count": publication_inputs["figure_count"], "speculative_values": 0}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    checksums = [f"{sha256(path)[7:]}  {path.relative_to(EVIDENCE).as_posix()}" for path in sorted(EVIDENCE.rglob("*")) if path.is_file() and path.name != "SHA256SUMS"]
    (EVIDENCE / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="ascii")
    result_checksums = [f"{sha256(path)[7:]}  {path.relative_to(RESULTS).as_posix()}" for path in sorted(RESULTS.rglob("*")) if path.is_file() and path.name != "SHA256SUMS"]
    (RESULTS / "SHA256SUMS").write_text("\n".join(result_checksums) + "\n", encoding="ascii")
    subprocess.run(["python3", str(EVIDENCE / "verify_focused_external_comparison_v8.py")], cwd=ROOT, check=True)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
