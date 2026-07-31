#!/usr/bin/env python3
"""Build deterministic, claim-admitted FlipGuard V3 publication inputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path(
    "results/thesis_grade_protocol/paper_artifacts_v3/final"
)
VERIFIER = Path("scripts/verify_flipguard_v3_paper_artifacts.py")
MANUSCRIPT = Path("docs/research/flipguard_v2_manuscript_draft_ko.md")
PACKS = {
    "direct_confirmatory": Path(
        "docs/evidence/direct_locked_audit_final_source_v1/manifest.json"
    ),
    "direct_development": Path(
        "docs/evidence/direct_locked_audit_seed0_development_v1/manifest.json"
    ),
    "bounded_oracle": Path(
        "docs/evidence/security_v2_bounded_oracle_v1/manifest.json"
    ),
    "security_attestation": Path(
        "docs/evidence/security_v2_static_attestation_formal_v2/manifest.json"
    ),
    "exact_security_estimator": Path(
        "docs/evidence/exact_security_estimator_v1/manifest.json"
    ),
    "direct_ablation": Path(
        "docs/evidence/direct_synthesis_ablation_v1/manifest.json"
    ),
    "decision_activation": Path(
        "docs/evidence/decision_contract_activation_control_v1/manifest.json"
    ),
    "no_safe": Path(
        "docs/evidence/no_safe_controls_confirmatory_v1/manifest.json"
    ),
    "policy_sensitivity": Path(
        "docs/evidence/policy_sensitivity_v1/manifest.json"
    ),
    "margin_interpretation": Path(
        "docs/evidence/margin_utilization_interpretation_v1/manifest.json"
    ),
    "structural": Path(
        "docs/evidence/structural_extension_v1/manifest.json"
    ),
    "structural_failure": Path(
        "docs/evidence/structural_audit_failure_analysis_v1/manifest.json"
    ),
    "sobel": Path(
        "docs/evidence/non_tabular_sobel_holdout_v1/manifest.json"
    ),
    "harris": Path(
        "docs/evidence/non_tabular_harris_holdout_v1/manifest.json"
    ),
    "cnn_lite": Path(
        "docs/evidence/non_tabular_mnist_cnn_lite_holdout_v1/manifest.json"
    ),
    "training_seed": Path(
        "docs/evidence/independent_training_seed_extension_v1/manifest.json"
    ),
    "paired_latency": Path(
        "docs/evidence/paired_latency_final_v1/manifest.json"
    ),
    "paired_latency_admission": Path(
        "results/thesis_grade_protocol/"
        "paired_latency_claim_admission_v1/manifest.json"
    ),
    "validation_identity": Path(
        "docs/evidence/validation_identity_comparison_v2/manifest.json"
    ),
    "final_suite": Path(
        "docs/evidence/final_confirmatory_suite_v1/manifest.json"
    ),
    "claim_admission": Path(
        "docs/evidence/paper_claim_admission_v1/manifest.json"
    ),
}


def sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def canonical_commit(revision: str) -> str:
    value = subprocess.run(
        ["git", "rev-parse", "--verify", f"{revision}^{{commit}}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise ValueError(f"{revision}: not a canonical commit")
    return value


def read_json(relative: str | Path) -> dict[str, Any]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def read_csv(relative: str | Path) -> list[dict[str, str]]:
    with (ROOT / relative).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    def cell(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def write_table(
    root: Path,
    filename: str,
    title: str,
    caption: str,
    headers: list[str],
    rows: list[list[Any]],
) -> None:
    (root / "tables" / filename).write_text(
        f"# {title}\n\n{caption}\n\n{md_table(headers, rows)}",
        encoding="utf-8",
    )


def svg_document(title: str, body: str, metadata: str = "") -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="680"
 viewBox="0 0 1200 680" role="img" aria-labelledby="title desc" {metadata}>
<title id="title">{html.escape(title)}</title>
<desc id="desc">Deterministic publication input generated from frozen evidence.</desc>
<rect width="1200" height="680" fill="#ffffff"/>
<text x="60" y="65" font-family="sans-serif" font-size="30" font-weight="700"
 fill="#111827">{html.escape(title)}</text>
{body}
</svg>
"""


def bar_figure(
    title: str,
    labels: list[str],
    values: list[float],
    colors: list[str],
    suffix: str = "",
    metadata: str = "",
) -> str:
    maximum = max(values) if values else 1
    bars = []
    width = 940 / max(1, len(values))
    for index, (label, value, color) in enumerate(zip(labels, values, colors)):
        bar_height = 450 * value / maximum if maximum else 0
        x = 90 + index * width + width * 0.16
        y = 570 - bar_height
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{width*0.68:.1f}" '
            f'height="{bar_height:.1f}" fill="{color}"/>'
        )
        bars.append(
            f'<text x="{x+width*0.34:.1f}" y="{y-12:.1f}" '
            'font-family="sans-serif" font-size="20" text-anchor="middle" '
            f'fill="#111827">{value:g}{html.escape(suffix)}</text>'
        )
        bars.append(
            f'<text x="{x+width*0.34:.1f}" y="610" '
            'font-family="sans-serif" font-size="17" text-anchor="middle" '
            f'fill="#374151">{html.escape(label)}</text>'
        )
    return svg_document(
        title,
        '<line x1="70" y1="570" x2="1140" y2="570" stroke="#9ca3af"/>'
        + "".join(bars),
        metadata,
    )


def manuscript_claim_scan() -> dict[str, Any]:
    text = (ROOT / MANUSCRIPT).read_text(encoding="utf-8")
    if "NON_AUTHORITATIVE_SCAFFOLD" not in text:
        raise ValueError("manuscript scaffold status changed")
    for begin, end in (
        (
            "<!-- BEGIN FINAL_RESULT_SENTENCE -->",
            "<!-- END FINAL_RESULT_SENTENCE -->",
        ),
        (
            "<!-- BEGIN FINAL_CONCLUSION_SENTENCE -->",
            "<!-- END FINAL_CONCLUSION_SENTENCE -->",
        ),
    ):
        content = text.split(begin, 1)[1].split(end, 1)[0]
        if "NON_AUTHORITATIVE_SCAFFOLD" not in content:
            raise ValueError("unadmitted manuscript headline detected")
    return {
        "status": "PASS",
        "manuscript": str(MANUSCRIPT),
        "sha256": sha256(ROOT / MANUSCRIPT),
        "headline_claims_inserted": False,
    }


def build_tables(output: Path) -> None:
    claims_doc = read_json(
        "docs/evidence/paper_claim_admission_v1/claims.json"
    )
    claims = claims_doc["claims"]
    write_table(
        output,
        "01_claim_evidence_registry.md",
        "Claim and evidence registry",
        "Only rows marked admitted authorize paper-facing claims.",
        ["Claim", "State", "Admitted", "Scope"],
        [
            [
                item["claim_id"],
                item["state"],
                str(item["paper_admitted"]).lower(),
                item["scope"],
            ]
            for item in claims
        ],
    )
    write_table(
        output,
        "02_workload_model_input_scope.md",
        "Workload, model, and input scope",
        "Scopes are finite and adapter-specific.",
        ["Evidence family", "Declared scope", "Inference unit"],
        [
            ["Primary tabular", "5 datasets x 2 models x 5 partitions", "10 dataset-model clusters"],
            ["Structural polynomial", "mlp_square_poly3; 5 datasets x 5 partitions", "25 workload-partition instances"],
            ["Sobel", "BSDS500 finite single-patch scalar-replicated inputs", "50 image clusters per role"],
            ["Harris", "BSDS500 finite single-window scalar-replicated inputs", "50 image clusters per role"],
            ["CNN-lite", "MNIST digit-0-vs-1 scalar-replicated graph", "250 images per role"],
            ["Independent training seed", "3 datasets x 3 training/data seeds", "trained model instance grouped by dataset"],
        ],
    )

    development = read_json(
        "docs/evidence/direct_locked_audit_seed0_development_v1/outputs/summary.json"
    )
    confirmatory = read_json(
        "docs/evidence/direct_locked_audit_final_source_v1/outputs/summary.json"
    )
    write_table(
        output,
        "03_primary_direct_selection_locked_audit.md",
        "Primary direct selection and locked audit",
        "Seed 0 is development/descriptive and is not pooled into the formal confirmatory aggregate.",
        ["Population", "Instances", "Trials", "Selection key runs", "Audit PASS", "Audit flips", "Audit violations", "Retuning"],
        [
            ["development seed 0", 10, development["total_configuration_trials"], development["total_selection_key_runs"], development["locked_audit_passes"], 0, 0, development["retuned_runs"]],
            ["confirmatory seeds 1-4", 40, confirmatory["total_configuration_trials"], confirmatory["total_selection_key_runs"], confirmatory["locked_audit_passes"], 0, 0, confirmatory["retuned_runs"]],
        ],
    )

    suite = read_json("docs/evidence/final_confirmatory_suite_v1/manifest.json")
    accounting = suite["catalog_accounting"]
    trials = suite["formal_trial_accounting"]
    write_table(
        output,
        "04_formal_trial_reduction.md",
        "Formal trial reduction",
        "The denominator contains only Security-V2-admitted bounded-catalog candidates.",
        ["Population", "Direct trials", "Catalog candidates", "Reduction"],
        [
            ["all five partitions", trials["direct_trials_all"], accounting["security_admitted_catalog_candidates"], f"{100*trials['formal_trial_reduction_all']:.1f}%"],
            ["confirmatory seeds 1-4", trials["direct_trials_confirmatory"], accounting["confirmatory_catalog_candidates"], f"{100*trials['formal_trial_reduction_confirmatory']:.1f}%"],
        ],
    )

    latency = read_json(
        "results/thesis_grade_protocol/paired_latency_claim_admission_v1/"
        "seeds1_4_confirmatory_summary.json"
    )
    development_latency = read_json(
        "results/thesis_grade_protocol/paired_latency_claim_admission_v1/"
        "seed0_development_summary.json"
    )
    write_table(
        output,
        "05_paired_latency_confirmatory.md",
        "Paired latency",
        "Ratios are catalog/direct and uncertainty resamples 10 dataset-model clusters.",
        ["Population", "Instances", "Total ratio", "Cluster bootstrap 95% CI", "Eval-only ratio", "Failures"],
        [
            ["development seed 0", 10, f"{development_latency['catalog_over_direct']['geometric_mean_total_latency_ratio']:.6f}", f"[{development_latency['catalog_over_direct']['cluster_bootstrap_95_ci_total']['low']:.6f}, {development_latency['catalog_over_direct']['cluster_bootstrap_95_ci_total']['high']:.6f}]", f"{development_latency['catalog_over_direct']['geometric_mean_eval_only_ratio']:.6f}", 0],
            ["confirmatory seeds 1-4", 40, f"{latency['catalog_over_direct']['geometric_mean_total_latency_ratio']:.6f}", f"[{latency['catalog_over_direct']['cluster_bootstrap_95_ci_total']['low']:.6f}, {latency['catalog_over_direct']['cluster_bootstrap_95_ci_total']['high']:.6f}]", f"{latency['catalog_over_direct']['geometric_mean_eval_only_ratio']:.6f}", 0],
        ],
    )

    ablation = read_json("docs/evidence/direct_synthesis_ablation_v1/summary.json")
    write_table(
        output,
        "06_direct_synthesis_ablation.md",
        "Direct-synthesis ablation",
        "Development-only ablation; no universal repair claim.",
        ["Arm", "Trials", "Repairs", "SELECTED", "NO_SAFE", "Validation flips", "Audit PASS"],
        [
            [name, values["trials"], values["repairs"], values["selected"], values["no_safe"], values["validation_flips"], values["audit_pass"]]
            for name, values in ablation["arms"].items()
        ],
    )

    no_safe = read_json(
        "docs/evidence/no_safe_controls_confirmatory_v1/manifest.json"
    )["counts"]
    write_table(
        output,
        "07_no_safe_controls.md",
        "NO_SAFE controls",
        "Abstention is scoped to the declared budgets and finite domains.",
        ["Control", "Instances", "SELECTED", "NO_SAFE"],
        [
            ["confirmatory one-candidate budget", no_safe["budget_workloads"], no_safe["budget_selected"], no_safe["budget_no_safe"]],
            ["finite two-candidate domain", no_safe["finite_domain_workloads"], 0, no_safe["finite_audit_no_safe"]],
        ],
    )

    sensitivity = read_json(
        "docs/evidence/policy_sensitivity_v1/results/summary.json"
    )
    write_table(
        output,
        "08_policy_margin_utilization_sensitivity.md",
        "Policy and margin-utilization sensitivity",
        "Invariance in the tested range is not evidence that rho=0.5 is optimal.",
        ["Quantity", "Result", "Interpretation"],
        [
            ["rho grid", "0.1, 0.25, 0.5, 0.75, 0.9", "predeclared sensitivity"],
            ["candidate-state changes", sensitivity["alpha_certificate_diagnostics"]["candidate_state_changes_across_alpha"], "tested primary range"],
            ["bounded-oracle changes", sensitivity["alpha_certificate_diagnostics"]["oracle_candidate_changes_across_alpha"], "tested primary range"],
            ["direct initial literal changes", 0, "minimum synthesis floor dominance"],
            ["theorem", "e_c(x) < m(x)", "sufficient decision preservation"],
            ["operational policy", "e_c(x) < 0.5*m(x)", "50% margin utilization cap"],
        ],
    )

    structural = read_json(
        "docs/evidence/structural_extension_v1/summary/structural_protocol.json"
    )
    counts = structural["counts"]
    write_table(
        output,
        "09_structural_polynomial_holdout.md",
        "Structural polynomial holdout",
        "The one valid reserve-policy rejection is mandatory scientific evidence.",
        ["Instances", "Selection SELECTED", "Audit PASS", "Audit policy REJECT", "Audit FAILED", "Flips", "Violations", "Retuning"],
        [[counts["structural_instances"], counts["selection_selected"], counts["locked_audit_pass"], counts["locked_audit_rejected"], counts["locked_audit_failed"], counts["flip_count"], counts["violation_count"], counts["retuning"]]],
    )

    sobel = read_json("docs/evidence/non_tabular_sobel_holdout_v1/manifest.json")["summary"]
    harris = read_json("docs/evidence/non_tabular_harris_holdout_v1/manifest.json")["summary"]
    cnn = read_json("docs/evidence/non_tabular_mnist_cnn_lite_holdout_v1/summary.json")
    write_table(
        output,
        "10_scoped_non_tabular_extension.md",
        "Scoped non-tabular extension",
        "Each row is limited to its declared finite scalar-replicated input scope.",
        ["Adapter", "Validation samples", "Audit samples", "Selection", "Audit", "Flips", "Violations"],
        [
            ["Sobel", 400, 400, sobel["selection"]["outcome"], sobel["locked_audit"]["outcome"], sobel["locked_audit"]["flips"], sobel["locked_audit"]["violations"]],
            ["Harris", 200, 200, harris["selection"]["outcome"], harris["locked_audit"]["outcome"], harris["locked_audit"]["flips"], harris["locked_audit"]["violations"]],
            ["CNN-lite", cnn["selection"]["samples"], cnn["locked_audit"]["samples"], cnn["selection"]["outcome"], cnn["locked_audit"]["outcome"], cnn["locked_audit"]["flips"], cnn["locked_audit"]["violations"]],
        ],
    )

    training = read_json(
        "docs/evidence/independent_training_seed_extension_v1/summary.json"
    )
    write_table(
        output,
        "11_independent_training_seed_extension.md",
        "Independent training/data-seed extension",
        "Nine model instances do not establish universal model-seed generalization.",
        ["Datasets", "Seeds per dataset", "Models", "SELECTED", "Audit PASS", "Flips", "Violations", "Retuning"],
        [[3, 3, training["trained_model_digests"], training["selection"]["selected"], training["locked_audit"]["pass"], training["locked_audit"]["flips"], training["locked_audit"]["violations"], training["locked_audit"]["retuning"]]],
    )

    reattestation = read_json(
        "docs/evidence/security_v2_static_attestation_formal_v2/"
        "security_reattestation_v2.json"
    )
    estimator = read_json("docs/evidence/exact_security_estimator_v1/summary.json")
    write_table(
        output,
        "12_security_exact_qp_attestation.md",
        "Security and exact-Q/P attestation",
        "The estimator matches declared objects but not Lattigo's explicit Xe truncation exactly.",
        ["Check", "PASS/admitted", "FAIL/excluded", "Caveat"],
        [
            ["direct selected static re-attestation", reattestation["direct_selected"]["pass"], reattestation["direct_selected"]["fail"], f"minimum headroom {reattestation['direct_selected']['minimum_headroom_bits']} bits"],
            ["catalog profiles", len(reattestation["catalog_profiles"]["admitted"]), len(reattestation["catalog_profiles"]["excluded"]), "Q and QP checked separately"],
            ["estimator model objects", 17, 1, f"{len(estimator['models'])} models; excluded object remains sub-128"],
        ],
    )

    write_table(
        output,
        "13_failure_negative_result_taxonomy.md",
        "Failure and negative-result taxonomy",
        "Negative results are retained and lower the corresponding claim.",
        ["Class", "Observed instance", "Claim effect"],
        [
            ["NUMERICAL_REJECT", "one-shot development candidates", "bounded repair evaluated"],
            ["NO_SAFE", "16/40 budget controls and 50/50 finite-domain controls", "scoped abstention supported"],
            ["VALIDATION_NEAR_BUDGET_LIMIT_AUDIT_OVERRUN", "seed4/banknote/mlp_square_poly3", "structural claim partially supported"],
            ["POLICY_REJECTED_WITHOUT_FLIP", "audit utilization 0.5613686 > cap 0.5", "not cryptographic or observed decision failure"],
            ["VALIDATION_IDENTITY_UNRESOLVED_FAIL_CLOSED", "comparator v1 representation mismatch", "resolved as 50/50 semantic CLASS A in v2"],
            ["provider import/rejection", "Orion, HIT, EVA appendix evidence", "no general provider claim"],
        ],
    )


def build_figures(output: Path) -> None:
    figures = output / "figures"
    flow_labels = [
        "Graph + decision contract",
        "Direct synthesis",
        "Encrypted validation",
        "Bounded repair",
        "Certify / reject / NO_SAFE",
        "Locked audit",
    ]
    boxes = []
    for index, label in enumerate(flow_labels):
        x = 55 + index * 190
        boxes.append(
            f'<rect x="{x}" y="250" width="165" height="120" rx="6" '
            'fill="#e5eefc" stroke="#2563eb" stroke-width="2"/>'
            f'<text x="{x+82.5}" y="305" text-anchor="middle" '
            'font-family="sans-serif" font-size="15" fill="#111827">'
            f'{html.escape(label)}</text>'
        )
        if index < len(flow_labels) - 1:
            boxes.append(
                f'<path d="M{x+165} 310 H{x+187}" stroke="#111827" '
                'stroke-width="2"/>'
            )
    (figures / "figure_01_framework.svg").write_text(
        svg_document("FlipGuard core framework", "".join(boxes)),
        encoding="utf-8",
    )
    provider_body = (
        '<rect x="80" y="180" width="360" height="300" fill="#f3f4f6" stroke="#4b5563"/>'
        '<text x="260" y="230" text-anchor="middle" font-family="sans-serif" font-size="22">Candidate providers</text>'
        '<text x="260" y="290" text-anchor="middle" font-family="sans-serif" font-size="18">manual / catalog / external / direct</text>'
        '<path d="M440 330 H650" stroke="#111827" stroke-width="3"/>'
        '<rect x="650" y="160" width="460" height="340" fill="#dcfce7" stroke="#16a34a" stroke-width="3"/>'
        '<text x="880" y="225" text-anchor="middle" font-family="sans-serif" font-size="24">Decision-Integrity Layer</text>'
        '<text x="880" y="285" text-anchor="middle" font-family="sans-serif" font-size="18">finite validation / abstention / locked audit</text>'
    )
    (figures / "figure_02_decision_integrity_layer.svg").write_text(
        svg_document("Candidate provider versus Decision-Integrity Layer", provider_body),
        encoding="utf-8",
    )
    margin_body = (
        '<line x1="130" y1="400" x2="1070" y2="400" stroke="#111827" stroke-width="3"/>'
        '<circle cx="250" cy="400" r="10" fill="#2563eb"/><text x="250" y="445" text-anchor="middle" font-family="sans-serif">f_plain(x)</text>'
        '<circle cx="950" cy="400" r="10" fill="#dc2626"/><text x="950" y="445" text-anchor="middle" font-family="sans-serif">tau</text>'
        '<line x1="250" y1="335" x2="950" y2="335" stroke="#16a34a" stroke-width="6"/>'
        '<text x="600" y="310" text-anchor="middle" font-family="sans-serif" font-size="20">theorem region: e &lt; m</text>'
        '<line x1="250" y1="250" x2="600" y2="250" stroke="#7c3aed" stroke-width="8"/>'
        '<text x="425" y="220" text-anchor="middle" font-family="sans-serif" font-size="20">operational region: e &lt; 0.5m</text>'
    )
    (figures / "figure_03_margin_theorem_policy.svg").write_text(
        svg_document("Decision theorem versus 50% utilization policy", margin_body),
        encoding="utf-8",
    )
    (figures / "figure_04_trial_reduction.svg").write_text(
        bar_figure(
            "Direct trials versus Security-V2 bounded catalog",
            ["direct all", "catalog all", "direct confirmatory", "catalog confirmatory"],
            [70, 700, 56, 560],
            ["#2563eb", "#9ca3af", "#16a34a", "#6b7280"],
        ),
        encoding="utf-8",
    )
    latency = read_json(
        "results/thesis_grade_protocol/paired_latency_claim_admission_v1/"
        "seeds1_4_confirmatory_summary.json"
    )["catalog_over_direct"]
    (figures / "figure_05_paired_latency.svg").write_text(
        bar_figure(
            "Confirmatory paired latency ratio",
            ["direct baseline", "catalog/direct total", "catalog/direct eval-only"],
            [1, latency["geometric_mean_total_latency_ratio"], latency["geometric_mean_eval_only_ratio"]],
            ["#2563eb", "#dc2626", "#f59e0b"],
            "x",
        ),
        encoding="utf-8",
    )
    (figures / "figure_06_primary_locked_audit.svg").write_text(
        bar_figure(
            "Primary no-retuning locked audit",
            ["seed0 PASS", "seeds1-4 PASS", "flip", "violation", "retune"],
            [10, 40, 0, 0, 0],
            ["#60a5fa", "#16a34a", "#dc2626", "#f59e0b", "#7c3aed"],
        ),
        encoding="utf-8",
    )
    (figures / "figure_07_no_safe_controls.svg").write_text(
        bar_figure(
            "NO_SAFE controls",
            ["budget SELECTED", "budget NO_SAFE", "finite-domain NO_SAFE"],
            [24, 16, 50],
            ["#16a34a", "#f59e0b", "#dc2626"],
        ),
        encoding="utf-8",
    )
    (figures / "figure_08_structural_scope_matrix.svg").write_text(
        bar_figure(
            "Scoped structural and robustness evidence",
            ["poly audit PASS", "poly policy REJECT", "Sobel audit", "Harris audit", "CNN-lite audit", "training-seed audit"],
            [24, 1, 1, 1, 1, 9],
            ["#16a34a", "#dc2626", "#2563eb", "#7c3aed", "#f59e0b", "#0891b2"],
            metadata='data-structural-pass="24" data-rejected="1"',
        ),
        encoding="utf-8",
    )
    margin_svg = bar_figure(
        "Structural margin utilization",
        ["validation", "locked audit", "policy cap"],
        [0.4706530094839232, 0.5613686443055665, 0.5],
        ["#16a34a", "#dc2626", "#111827"],
        metadata='data-policy-reject-without-flip="1"',
    )
    (figures / "figure_09_margin_utilization_rejection.svg").write_text(
        margin_svg, encoding="utf-8"
    )
    (figures / "figure_10_claim_scope_map.svg").write_text(
        bar_figure(
            "Canonical paper claim scope",
            ["paper-admitted", "blocked or not admitted"],
            [11, 9],
            ["#16a34a", "#6b7280"],
        ),
        encoding="utf-8",
    )


def build(output: Path, source_commit: str) -> None:
    if output.exists():
        raise ValueError(f"{output} already exists")
    registry = read_json(
        "docs/evidence/paper_claim_admission_v1/claims.json"
    )
    if (
        registry["paper_claim_allowed"] is not True
        or sum(item["paper_admitted"] for item in registry["claims"]) != 11
    ):
        raise ValueError("canonical claim registry is not admissible")
    structural = read_json(
        "docs/evidence/structural_extension_v1/summary/structural_protocol.json"
    )
    counts = structural["counts"]
    if (
        counts["selection_selected"] != 25
        or counts["locked_audit_pass"] != 24
        or counts["locked_audit_rejected"] != 1
        or counts["flip_count"] != 0
        or counts["violation_count"] != 1
    ):
        raise ValueError("structural negative result changed")
    input_bindings = {}
    for pack_id, relative in PACKS.items():
        path = ROOT / relative
        if not path.is_file():
            raise ValueError(f"{relative}: missing required V3 input")
        input_bindings[pack_id] = {
            "path": str(relative),
            "sha256": sha256(path),
        }

    for directory in ("tables", "figures", "publication_inputs", "claim_blocks", "appendix"):
        (output / directory).mkdir(parents=True, exist_ok=True)
    build_tables(output)
    build_figures(output)
    shutil.copy2(
        ROOT / "docs/research/flipguard_v3_equation_list.md",
        output / "publication_inputs/equation_list.md",
    )
    shutil.copy2(
        ROOT / "docs/research/flipguard_v3_result_table_captions.md",
        output / "publication_inputs/result_table_captions.md",
    )
    shutil.copy2(
        ROOT / "docs/research/flipguard_v3_framework_figure_spec.md",
        output / "publication_inputs/framework_figure_spec.md",
    )
    shutil.copy2(
        ROOT / "docs/evidence/paper_claim_admission_v1/allowed_sentences.md",
        output / "claim_blocks/allowed_sentences.md",
    )
    shutil.copy2(
        ROOT / "docs/evidence/paper_claim_admission_v1/prohibited_sentences.md",
        output / "claim_blocks/prohibited_sentences.md",
    )
    (output / "appendix/auxiliary_provider_boundary.md").write_text(
        "# Auxiliary provider and EVA evidence\n\n"
        "Orion fail-closed import, AWS HIT rejection, EVA native scale "
        "sensitivity, scale-30 locked audit, and exact EVA Q/P "
        "materialization are appendix-only scoped interoperability evidence. "
        "They do not establish cross-runtime equivalence or general "
        "external-autotuner support.\n",
        encoding="utf-8",
    )
    shutil.copy2(ROOT / VERIFIER, output / VERIFIER.name)
    claim_scan = manuscript_claim_scan()
    publication_status = {
        "schema_version": 1,
        "status": "FINAL_ADMISSIBLE",
        "paper_claim_allowed": True,
        "claim_registry": input_bindings["claim_admission"],
        "manuscript_claim_scan": claim_scan,
        "generated_tables": 13,
        "generated_figures": 10,
        "thesis_prose_generated": False,
        "provider_eva_role": "APPENDIX_ONLY",
    }
    (output / "publication_status.json").write_text(
        json.dumps(publication_status, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 3,
        "artifact_id": "flipguard_paper_artifacts_v3",
        "profile": "final",
        "publication_status": "FINAL_ADMISSIBLE",
        "source_commit": source_commit,
        "paper_claim_allowed": True,
        "thesis_prose_generated": False,
        "formal_catalog_denominators": {
            "all": 700,
            "confirmatory": 560,
        },
        "seed_roles_separated": True,
        "margin_theorem_policy_separated": True,
        "structural_negative_result_preserved": True,
        "input_bindings": input_bindings,
        "manuscript_claim_scan": claim_scan,
        "files": {},
    }
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name not in {"manifest.json", "SHA256SUMS"}:
            manifest["files"][str(path.relative_to(output))] = {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths = sorted(
        path
        for path in output.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    (output / "SHA256SUMS").write_text(
        "".join(
            f"{sha256(path).removeprefix('sha256:')}  "
            f"{path.relative_to(output)}\n"
            for path in paths
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-commit", default="HEAD")
    parser.add_argument("--skip-verify", action="store_true")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    build(output, canonical_commit(args.source_commit))
    if not args.skip_verify:
        subprocess.run(
            [
                "python3",
                str(output / VERIFIER.name),
                "--artifact-root",
                str(output),
                "--repo-root",
                str(ROOT),
            ],
            cwd=ROOT,
            check=True,
        )
    print(f"paper_artifacts_v3=BUILT output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
