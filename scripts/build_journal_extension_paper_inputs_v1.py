#!/usr/bin/env python3
"""Build deterministic journal-extension tables and SVG publication inputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import math
from pathlib import Path


SCHEMA = "flipguard_journal_extension_paper_inputs_v1"
OUTPUT = "results/thesis_grade_protocol/journal_extension_paper_inputs_v1"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(value).replace("\n", " ").replace("|", "\\|") for value in row) + " |")
    return "\n".join(lines) + "\n"


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def extract_first_table(text: str, required_header: str) -> str:
    lines = text.splitlines()
    start = next((index for index, line in enumerate(lines) if line.startswith("|") and required_header in line), None)
    require(start is not None, f"missing table header {required_header}")
    end = start
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    require(end - start >= 3, f"short table {required_header}")
    return "\n".join(lines[start:end]) + "\n"


def svg_start(title: str, description: str, width: int = 1200, height: int = 700, data: str = "") -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc" {data}>',
        f'<title id="title">{esc(title)}</title>',
        f'<desc id="desc">{esc(description)}</desc>',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="55" y="58" font-family="sans-serif" font-size="30" font-weight="700" fill="#111827">{esc(title)}</text>',
    ]


def svg_text(x: float, y: float, text: object, size: int = 18, weight: int = 400, anchor: str = "start", color: str = "#111827") -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}" font-family="sans-serif" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" fill="{color}">{esc(text)}</text>'


def svg_box(x: float, y: float, width: float, height: float, fill: str, stroke: str, title: str, lines: list[str]) -> list[str]:
    output = [f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="2"/>']
    output.append(svg_text(x + width / 2, y + 34, title, 19, 700, "middle"))
    for index, line in enumerate(lines):
        output.append(svg_text(x + width / 2, y + 64 + index * 25, line, 15, 400, "middle", "#374151"))
    return output


def close_svg(lines: list[str]) -> str:
    return "\n".join([*lines, "</svg>", ""])


def operation_scale_rows(root: Path, summary: dict) -> list[dict]:
    comparison = read_csv(root / "docs/evidence/final_confirmatory_suite_v1/snapshots/final_comparison_rows.csv")
    primary_mlp = [row for row in comparison if row["model_id"] == "mlp_square_linear_score"]
    require(primary_mlp and {row["direct_log_n"] for row in primary_mlp} == {"13"}, "primary MLP LogN")
    mlp_preflight = load(root / "results/journal_multiclass_extension_v1/preflight/mlp_configuration_validation.json")
    lenet_preflight = load(root / "results/journal_multiclass_extension_v1/preflight/lenet_configuration_validation.json")
    rows = [
        {
            "model": "Primary MLP-4",
            "input": "4/8/16",
            "hidden": "4",
            "outputs": 1,
            "add_ops": "20-68",
            "mul_ops": "24-72",
            "rescale_ops": 1,
            "depth": 1,
            "log_n": 13,
            "q_count": 6,
            "scale_bits": 20,
            "trials": 1,
            "repairs": 0,
            "selected_total_ms": "core workload-dependent",
        }
    ]
    for name, preflight_key, label in [("mlp_100", mlp_preflight, "MNIST MLP-100"), ("lenet5_small", lenet_preflight, "MNIST LeNet-5-small")]:
        graph = preflight_key["contract"]["graph"]
        selection = summary["models"][name]["direct_selection"]
        parameters = selection["candidate_parameters"]
        rows.append(
            {
                "model": label,
                "input": "784",
                "hidden": "100" if name == "mlp_100" else "conv6/16; FC120/64",
                "outputs": 10,
                "add_ops": graph["add_ops"],
                "mul_ops": graph["mul_ops"],
                "rescale_ops": graph["rescale_ops"],
                "depth": graph["multiplicative_depth"],
                "log_n": parameters["log_n"],
                "q_count": len(parameters["log_q"]),
                "scale_bits": parameters["log_default_scale"],
                "trials": selection["trials"],
                "repairs": selection["repairs"],
                "selected_total_ms": "see descriptive timing table",
            }
        )
    return rows


def build_figures(summary: dict, activation: dict, scale_rows: list[dict], gap_rows: list[dict]) -> dict[str, str]:
    figures: dict[str, str] = {}

    lines = svg_start("FlipGuard evaluation hierarchy", "Core RC2 evidence remains immutable; the journal overlay adds two standard multiclass models.")
    levels = [
        ("Controlled primary", "5 datasets x 2 graphs", "50 repeated-partition instances", "#dbeafe", "#2563eb"),
        ("Structural holdouts", "poly3; Sobel; Harris; CNN-lite", "finite adapter scopes", "#dcfce7", "#16a34a"),
        ("Robustness", "3 datasets x 3 training seeds", "9 independent trained models", "#fef3c7", "#d97706"),
        ("Journal extension", "MLP-100 and LeNet-5-small", "10-class; 1,000 shared test rows", "#f3e8ff", "#7c3aed"),
    ]
    for index, (title, a, b, fill, stroke) in enumerate(levels):
        y = 95 + index * 135
        lines += svg_box(180, y, 840, 100, fill, stroke, title, [a, b])
        if index < len(levels) - 1:
            lines += [f'<line x1="600" y1="{y+100}" x2="600" y2="{y+130}" stroke="#6b7280" stroke-width="2"/>', f'<polygon points="594,{y+122} 606,{y+122} 600,{y+132}" fill="#6b7280"/>']
    figures["figures/figure_01_evaluation_hierarchy.svg"] = close_svg(lines)

    lines = svg_start("Binary threshold and multiclass argmax contracts", "The theorem condition is separated from the predeclared 50-percent utilization policy.")
    lines += svg_box(60, 105, 510, 480, "#eff6ff", "#2563eb", "Binary threshold", [
        "m(x) = |f_plain(x) - tau|", "e(x) = |f_ckks(x) - f_plain(x)|", "e(x) < m(x) => decision preserved", "operational: e(x) < rho m(x)", "primary rho = 0.5 (policy, not theorem)",
    ])
    lines += svg_box(630, 105, 510, 480, "#f0fdf4", "#16a34a", "Multiclass argmax", [
        "c* = argmax_k z_k", "for every j != c*:", "z_c* - z_j > B_c* + B_j", "=> argmax_k zhat_k = c*", "uniform bound: 2B < top-two gap", "ties and non-finite values are rejected",
    ])
    lines.append(svg_text(600, 635, "Strict inequalities are required; equality does not rule out an approximate tie.", 18, 600, "middle", "#991b1b"))
    figures["figures/figure_02_binary_multiclass_contracts.svg"] = close_svg(lines)

    lines = svg_start("Benchmark-practice comparison", "A feature map, not a claim of benchmark equivalence.")
    headers = ["Work", "Std. ML graph", "Decision gate", "NO_SAFE", "Locked audit", "Search accounting"]
    xs = [70, 300, 480, 650, 800, 970]
    for x, header in zip(xs, headers):
        lines.append(svg_text(x, 105, header, 15, 700, "middle" if x > 70 else "start"))
    matrix = [
        ("EVA", [1, 0, 0, 0, 1]), ("HECATE", [1, 0, 0, 0, 1]), ("ELASM", [1, 0, 0, 0, 1]),
        ("DaCapo", [1, 1, 0, 0, 1]), ("AutoFHE", [1, 1, 0, 0, 1]),
        ("FHE-Agent", [1, 1, 1, 0, 1]), ("FlipGuard extension", [1, 1, 1, 1, 1]),
    ]
    for row_index, (work, values) in enumerate(matrix):
        y = 145 + row_index * 68
        lines.append(f'<rect x="50" y="{y-27}" width="1090" height="52" fill="{"#f9fafb" if row_index % 2 == 0 else "#ffffff"}"/>')
        lines.append(svg_text(70, y+5, work, 17, 700 if work.startswith("FlipGuard") else 400))
        for index, value in enumerate(values):
            color = "#16a34a" if value else "#d1d5db"
            lines.append(f'<circle cx="{xs[index+1]}" cy="{y}" r="11" fill="{color}"/>')
    lines.append(svg_text(70, 650, "Dots summarize declared practices only; details and citations are in Table 2.", 15, 400, "start", "#4b5563"))
    figures["figures/figure_03_benchmark_comparison.svg"] = close_svg(lines)

    lines = svg_start("Controlled graph-scale points", "Operation counts and selected CKKS literal scale across three disclosed graph points.")
    maximum = max(float(row["mul_ops"].split("-")[-1]) for row in scale_rows)
    colors = ["#2563eb", "#16a34a", "#d97706"]
    for index, (row, color) in enumerate(zip(scale_rows, colors)):
        y = 150 + index * 160
        value = float(row["mul_ops"].split("-")[-1])
        width = 820 * math.log10(value + 1) / math.log10(maximum + 1)
        lines.append(svg_text(65, y, row["model"], 19, 700))
        lines.append(f'<rect x="285" y="{y-27}" width="{width:.1f}" height="42" fill="{color}"/>')
        lines.append(svg_text(300 + width, y+2, f"mul={row['mul_ops']}; depth={row['depth']}; N=2^{row['log_n']}; Q={row['q_count']}", 16, 400))
    lines.append(svg_text(65, 640, "Bar length uses log10(multiplication count); it is not a latency axis.", 16, 400, "start", "#4b5563"))
    figures["figures/figure_04_graph_scale_map.svg"] = close_svg(lines)

    validation_gap = [row for row in gap_rows if row["role"] == "configuration_validation"]
    lines = svg_start("Validation top-two-gap bins", "Five frozen bins are derived from configuration validation and replayed unchanged on audit.")
    palette = {"mlp_100": "#2563eb", "lenet5_small": "#d97706"}
    for model_index, model in enumerate(["mlp_100", "lenet5_small"]):
        model_rows = sorted((row for row in validation_gap if row["model_name"] == model), key=lambda row: int(row["gap_bin"]))
        for row in model_rows:
            bin_index = int(row["gap_bin"])
            x = 120 + (bin_index - 1) * 200 + model_index * 65
            count = int(row["unique_samples"])
            height = count * 3.8
            lines.append(f'<rect x="{x}" y="{590-height:.1f}" width="55" height="{height:.1f}" fill="{palette[model]}"/>')
            lines.append(svg_text(x+27.5, 615, f"B{bin_index}", 14, 400, "middle"))
        lines.append(svg_text(450 + model_index * 300, 105, model.replace("_", "-"), 17, 700, "middle", palette[model]))
    lines.append(svg_text(600, 665, "Unique validation samples per bin; key repetitions are not independent samples.", 16, 400, "middle", "#4b5563"))
    figures["figures/figure_05_top_two_gap_distribution.svg"] = close_svg(lines)

    lines = svg_start("Gap-bin admission and argmax behavior", "Validation-derived bins are applied without audit rebucketing.")
    all_gap = sorted(gap_rows, key=lambda row: (row["model_name"], row["role"], int(row["gap_bin"])))
    y = 120
    for row in all_gap:
        role = "VAL" if row["role"] == "configuration_validation" else "AUDIT"
        label = f"{row['model_name']} {role} B{row['gap_bin']}"
        rejections = int(row["reserve_policy_rejections"])
        flips = int(row["argmax_flips"])
        color = "#16a34a" if rejections == 0 and flips == 0 else "#dc2626"
        lines.append(svg_text(70, y, label, 13, 400))
        lines.append(f'<rect x="330" y="{y-16}" width="{max(4, int(row["unique_samples"])*5)}" height="20" fill="{color}"/>')
        lines.append(svg_text(860, y, f"samples={row['unique_samples']} reject={rejections} flip={flips}", 13, 400))
        y += 25
    figures["figures/figure_06_gap_bin_behavior.svg"] = close_svg(lines)

    lines = svg_start("Direct trials and Security-V2 bounded catalog", "Candidate-space screening is separated from encrypted executable-candidate accounting.")
    for index, model in enumerate(["mlp_100", "lenet5_small"]):
        row = summary["models"][model]
        x = 120 + index * 550
        direct = row["direct_selection"]["trials"]
        denominator = row["security_v2_bounded_catalog"]["formal_denominator"]
        executable = row["security_v2_bounded_catalog"]["encrypted_candidates"]
        lines += svg_box(x, 130, 430, 390, "#f9fafb", "#6b7280", model.replace("_", "-"), [
            f"direct encrypted trials: {direct}", f"bounded admitted profiles: {denominator}",
            f"catalog executable: {executable}", f"catalog static unsupported: {denominator-executable}",
            "screening and execution are separate units",
        ])
    lines.append(svg_text(600, 610, "No global-oracle or paired-latency claim is made for this extension.", 18, 600, "middle", "#991b1b"))
    figures["figures/figure_07_direct_vs_bounded_catalog.svg"] = close_svg(lines)

    lines = svg_start("Standard-model locked-audit outcomes", "The selected literal is replayed on 500 disjoint images with three fresh keys and zero retuning.")
    for index, model in enumerate(["mlp_100", "lenet5_small"]):
        audit = summary["models"][model]["locked_audit"]
        x = 100 + index * 550
        status_color = "#16a34a" if audit["status"] == "SAFE" else "#dc2626"
        lines += svg_box(x, 130, 450, 380, "#ffffff", status_color, model.replace("_", "-"), [
            f"status: {audit['status']}", f"argmax flips: {audit['argmax_flips']}",
            f"reserve rejects: {audit['reserve_policy_rejections']}", f"fresh keys: {audit['fresh_key_runs']}",
            f"encrypted evaluations: {audit['encrypted_sample_evaluations']}", "retuning: 0",
        ])
    lines.append(svg_text(600, 615, "Finite evidence for two disclosed adapters; not arbitrary packed-CNN generalization.", 17, 600, "middle", "#4b5563"))
    figures["figures/figure_08_standard_model_locked_audit.svg"] = close_svg(lines)
    return figures


def collect(root: Path, source_commit: str) -> dict[str, object]:
    result_pack = root / "docs/evidence/journal_multiclass_extension_results_v1"
    activation_pack = root / "docs/evidence/journal_multiclass_activation_v1"
    result_summary = load(result_pack / "summary.json")
    activation = load(activation_pack / "activation_summary.json")
    result_manifest = load(result_pack / "manifest.json")
    activation_manifest = load(activation_pack / "manifest.json")
    number_registry = load(root / "docs/thesis/number_registry.json")
    mlp_model = load(root / "datasets/journal_multiclass_extension_v1/mnist/mnist_mlp_square_784_100_10_v1.json")
    lenet_model = load(root / "datasets/journal_multiclass_extension_v1/mnist/mnist_lenet5_small_square_v1.json")
    split = load(root / "datasets/journal_multiclass_extension_v1/mnist/input_split_manifest.json")
    gap_rows = read_csv(result_pack / "gap_bin_summary.csv")
    ablation_rows = read_csv(activation_pack / "ablation_summary.csv")
    scale_rows = operation_scale_rows(root, result_summary)

    require(result_summary["combined"]["models"] == 2, "result model count")
    require(sum(split["class_counts"]["configuration_validation"]) == 500, "validation split size")
    require(sum(split["class_counts"]["locked_audit"]) == 500, "audit split size")
    require(split["validation_audit_overlap_count"] == 0, "split overlap")
    require(number_registry["formal_catalog_all"] == 700, "immutable core denominator")
    require(number_registry["direct_trials_all"] == 70, "immutable core direct trials")

    inventory_rows = [
        ["Controlled binary primary", "5 datasets x 2 graphs x 5 deterministic partitions", 50, "10 dataset-model clusters", "RC2/V3 immutable"],
        ["Security-V2 formal catalog", "7 profiles x 2 paths x 50", 700, "candidate", "400 of raw 1,100 excluded"],
        ["Primary direct selection", "all five deterministic partitions", 70, "encrypted candidate trial", "90% vs formal 700"],
        [
            "Primary paired latency",
            f"{number_registry['paired_arms']} arms x {number_registry['combined_descriptive_instances']} workloads x {number_registry['paired_measurement_runs']} measurement runs x {number_registry['paired_rows_per_workload']} selected rows",
            number_registry["paired_raw_records"],
            "raw latency record; 10 clusters inferential",
            "balanced cyclic/reverse order; RC2 claim unchanged",
        ],
        ["NO_SAFE controls", "budget 40 plus finite-domain 50", 90, "control instance", "finite candidate domains"],
        ["Polynomial structural", "5 datasets x 5 partitions", 25, "workload-partition instance", "24 audit PASS; 1 reserve reject"],
        ["Sobel/Harris/CNN-lite", "finite scalar-replicated adapters", 1700, "encrypted observation", "not packed/general CNN"],
        ["Independent training seeds", "3 datasets x 3 seeds", 9, "trained model", "9 audit PASS"],
        ["Journal MLP-100", "MNIST 10-class; 500 validation + 500 audit", 1000, "unique image; 3 fresh-key repeats", result_summary["models"]["mlp_100"]["locked_audit"]["status"]],
        ["Journal LeNet-5-small", "MNIST 10-class; same disjoint split", 1000, "unique image; 3 fresh-key repeats", result_summary["models"]["lenet5_small"]["locked_audit"]["status"]],
    ]
    tables: dict[str, str] = {}
    tables["tables/01_complete_experiment_inventory.md"] = "# Complete experiment inventory\n\n" + markdown_table(
        ["Evidence family", "Declared scope", "Count", "Correct unit", "Status/limit"], inventory_rows
    )

    related = extract_first_table((root / "docs/research/step_8a_evaluation_breadth_audit.md").read_text(encoding="utf-8"), "Work")
    tables["tables/02_related_work_benchmark_comparison.md"] = (
        "# Related-work benchmark comparison\n\nPrimary-source audit; `NR` is never imputed. This table compares practices, not equivalent implementations.\n\n" + related
    )

    model_rows = [
        ["MLP-100", "784 -> 100 -> square -> 10", mlp_model["plaintext_accuracy"]["official_test_10000"], "feature ciphertext sample slots", "square", "no packed-production claim"],
        ["LeNet-5-small", "conv6 -> avgpool -> conv16 -> avgpool -> FC120 -> FC64 -> 10", lenet_model["plaintext_accuracy"]["official_test_10000"], "feature ciphertext sample slots", "square after conv/FC", "FHE-compatible disclosed adapter"],
    ]
    scale_table = markdown_table(
        ["Scale point", "Input", "Hidden", "Outputs", "Add ops", "Mul ops", "Rescales", "Depth", "LogN", "Q", "Scale", "Trials", "Repairs"],
        [[row["model"], row["input"], row["hidden"], row["outputs"], row["add_ops"], row["mul_ops"], row["rescale_ops"], row["depth"], row["log_n"], row["q_count"], row["scale_bits"], row["trials"], row["repairs"]] for row in scale_rows],
    )
    tables["tables/03_standard_multiclass_model_specification.md"] = (
        "# Standard multiclass model specification and controlled graph scale\n\n" +
        markdown_table(["Model", "Architecture", "Plaintext test accuracy", "Packing scope", "Activation", "Claim boundary"], model_rows) +
        "\n## Controlled graph-scale points\n\n" + scale_table
    )

    direct_rows = []
    for model in ["mlp_100", "lenet5_small"]:
        value = result_summary["models"][model]
        direct = value["direct_selection"]
        audit = value["locked_audit"]
        catalog = value["security_v2_bounded_catalog"]
        direct_rows.append([
            model, direct["status"], direct["trials"], direct["repairs"], direct["fresh_key_runs"],
            direct["argmax_flips"], direct["reserve_policy_rejections"], audit["status"], audit["argmax_flips"],
            audit["reserve_policy_rejections"], catalog["formal_denominator"], catalog["encrypted_candidates"],
            catalog["safe"], catalog["plan_unsupported"], catalog["fastest_safe_profile"] or "NONE",
        ])
    tables["tables/04_multiclass_direct_catalog_result.md"] = "# Multiclass direct and bounded-catalog result\n\n" + markdown_table(
        ["Model", "Validation", "Direct trials", "Repairs", "Selection keys", "Val flips", "Val rejects", "Audit", "Audit flips", "Audit rejects", "Formal catalog", "Catalog executed", "Catalog SAFE", "Static unsupported", "Fastest SAFE"], direct_rows
    ) + "\nCatalog timing is descriptive and unpaired. The extension does not alter the RC2 paired-latency claim.\n"

    tables["tables/05_multiclass_ablation.md"] = "# Multiclass synthesis ablation\n\n" + markdown_table(
        ["Model", "Arm", "Static status", "Encrypted status", "Candidate", "Trials", "Keys", "Flips", "Reserve rejects", "Interpretation"],
        [[row[field] for field in ["model", "arm", "static_status", "encrypted_status", "candidate_id", "trials", "fresh_key_runs", "argmax_flips", "reserve_policy_rejections", "interpretation"]] for row in ablation_rows],
    )

    tables["tables/06_margin_gap_activation_analysis.md"] = (
        "# Natural top-two-gap activation analysis\n\n" +
        markdown_table(["Study", "Result", "Literal changed", "MLP graph-only", "LeNet graph-only", "Claim boundary"], [[
            activation["study_id"], activation["activation_class"], activation["literal_changed"],
            activation["graph_only_fixed_tolerance"]["status"], activation["lenet_graph_only"]["status"], activation["scope"],
        ]]) + "\n" +
        markdown_table(["Model", "Role", "Gap bin", "Unique samples", "Key observations", "Flips", "Reserve rejects", "Min gap", "Max gap", "Max cap required"], [
            [row["model_name"], row["role"], row["gap_bin"], row["unique_samples"], row["fresh_key_observations"], row["argmax_flips"], row["reserve_policy_rejections"], row["min_top_two_gap"], row["max_top_two_gap"], row["max_minimum_cap_required"]]
            for row in gap_rows
        ])
    )

    extension_claims = [
        ["multiclass_argmax_contract", "SUPPORTED", True, "per-class strict sufficient condition and uniform-bound corollary", "finite empirical evidence is not an analytical CKKS error certificate"],
        ["mnist_mlp_100", "SUPPORTED" if result_summary["models"]["mlp_100"]["locked_audit"]["status"] == "SAFE" else "PARTIALLY_SUPPORTED", True, "frozen 784-100-square-10 adapter", "one model and finite 1,000-image scope"],
        ["mnist_lenet5_small", "SUPPORTED" if result_summary["models"]["lenet5_small"]["locked_audit"]["status"] == "SAFE" else "PARTIALLY_SUPPORTED", True, "disclosed FHE-compatible LeNet-5-small adapter", "not original/packed/full LeNet"],
        ["natural_data_margin_literal_effect", activation["claim_state"], activation["activation_class"] == "A_LITERAL_EFFECT_SUPPORTED", activation["scope"], "no universal activation claim"],
        ["bounded_catalog_multiclass", "PARTIALLY_SUPPORTED", True, "formal denominator 14; executable coverage 6/14", "LeNet has no executable admitted catalog profile"],
        ["journal_extension_latency", "BLOCKED", False, "descriptive unpaired timing only", "no paired standard-model latency claim"],
        ["arbitrary_packed_cnn", "BLOCKED", False, "not evaluated", "feature-ciphertext sample-slot adapter only"],
        ["core_rc2_claims", "SUPPORTED", True, "unchanged V3/RC2 admission", "journal overlay cannot alter core claims"],
    ]
    claim_registry = {
        "schema_version": "flipguard_journal_extension_claim_registry_v1",
        "vocabulary": ["SUPPORTED", "PARTIALLY_SUPPORTED", "BLOCKED", "NOT_EVALUATED", "SUPERSEDED", "PILOT_ONLY"],
        "claims": [
            {
                "claim_id": row[0],
                "state": row[1],
                "paper_admitted": row[2],
                "scope": row[3],
                "limitation": row[4],
                "source_commit": source_commit,
            }
            for row in extension_claims
        ],
        "core_claim_registry_modified": False,
        "blocked_claims_must_not_appear_as_headlines": True,
    }
    tables["tables/07_updated_claim_evidence_matrix.md"] = "# Updated claim-evidence matrix\n\n" + markdown_table(
        ["Claim", "State", "Journal text admitted", "Exact scope", "Limitation"], extension_claims
    )

    scorecard = extract_first_table((root / "docs/research/step_8e_kiisc_reviewer_scorecard.md").read_text(encoding="utf-8"), "Criterion")
    tables["tables/08_kiisc_competitiveness_rubric.md"] = (
        "# KIISC reviewer-quality rubric\n\nThese are reviewer-quality diagnostics, not acceptance or award probabilities.\n\n" + scorecard
    )

    figures = build_figures(result_summary, activation, scale_rows, gap_rows)
    scale_csv = io.StringIO(newline="")
    fields = list(scale_rows[0])
    writer = csv.DictWriter(scale_csv, fieldnames=fields, lineterminator="\n")
    writer.writeheader(); writer.writerows(scale_rows)
    summary = {
        "schema_version": SCHEMA,
        "source_commit": source_commit,
        "status": "JOURNAL_EXTENSION_V1_COMPLETE",
        "core_rc2_v3_v10_modified": False,
        "policy_retuning": 0,
        "standard_models": 2,
        "unique_encrypted_images_per_model": 1000,
        "fresh_key_repeats_per_role": 3,
        "multiclass_locked_audit": {
            model: result_summary["models"][model]["locked_audit"] for model in ["mlp_100", "lenet5_small"]
        },
        "natural_activation": activation["activation_class"],
        "formal_catalog_denominator": result_summary["combined"]["security_v2_bounded_catalog_denominator"],
        "catalog_executable_candidates": result_summary["combined"]["security_v2_bounded_catalog_encrypted_candidates"],
        "extension_latency_claim": "BLOCKED_FORMAL; DESCRIPTIVE_UNPAIRED_ONLY",
        "new_paired_latency_execution": 0,
        "tables": 8,
        "figures": 8,
    }
    publication_status = {
        "schema_version": SCHEMA,
        "status": "JOURNAL_EXTENSION_V1_OVERLAY",
        "paper_claim_allowed": True,
        "condition": "Only rows marked admitted in table 07 may be used; RC2/V3/V10 and the authoritative thesis remain immutable.",
        "kiisc_formatting_started": False,
        "formal_journal_latency_claim": False,
    }
    inputs = [
        result_pack / "manifest.json", activation_pack / "manifest.json",
        root / "results/thesis_grade_protocol/paper_artifacts_v3/final/manifest.json",
        root / "docs/evidence/research_completion_checkpoint_v10/manifest.json",
        root / "docs/thesis/number_registry.json",
        root / "datasets/journal_multiclass_extension_v1/mnist/input_split_manifest.json",
        root / "datasets/journal_multiclass_extension_v1/mnist/mnist_mlp_square_784_100_10_v1.json",
        root / "datasets/journal_multiclass_extension_v1/mnist/mnist_lenet5_small_square_v1.json",
        root / "docs/research/step_8a_evaluation_breadth_audit.md",
        root / "docs/research/step_8e_kiisc_reviewer_scorecard.md",
    ]
    for path in inputs:
        require(path.is_file(), f"missing input {path}")
    return {
        "files": {
            **tables, **figures,
            "publication_inputs/graph_scale_analysis.csv": scale_csv.getvalue(),
            "publication_inputs/claim_registry.json": canonical(claim_registry),
            "summary.json": canonical(summary),
            "publication_status.json": canonical(publication_status),
        },
        "inputs": [{"path": str(path.relative_to(root)), "sha256": digest(path)} for path in inputs],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", default=OUTPUT)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / args.output
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing paper-input overlay {output}")
    try:
        collected = collect(root, args.source_commit)
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        raise SystemExit("FAIL: " + str(error)) from error
    output.mkdir(parents=True)
    for name, content in sorted(collected["files"].items()):
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    manifest = {
        "schema_version": SCHEMA,
        "source_commit": args.source_commit,
        "inputs": collected["inputs"],
        "generated_files": {
            name: {"path": name, "sha256": digest(output / name), "bytes": (output / name).stat().st_size}
            for name in sorted(collected["files"])
        },
        "frozen_core_modified": False,
        "policy_retuning": 0,
    }
    (output / "manifest.json").write_text(canonical(manifest), encoding="utf-8")
    names = [*sorted(collected["files"]), "manifest.json"]
    (output / "SHA256SUMS").write_text(
        "".join(f"{digest(output / name)[7:]}  {name}\n" for name in names), encoding="ascii"
    )
    print(f"wrote {output.relative_to(root)}")
    print("manifest_sha256=" + digest(output / "manifest.json"))


if __name__ == "__main__":
    main()
