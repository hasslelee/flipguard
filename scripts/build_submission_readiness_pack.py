#!/usr/bin/env python3

from pathlib import Path

OUT = Path("results/paper_grade_evidence_pack/current")


def write(name, content):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(content.rstrip() + "\n")


def md_table(headers, rows):
    out = []
    out.append("| " + " | ".join(headers) + " |")
    out.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        out.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(out)


def build_camera_ready_figure_specs():
    rows = [
        ["Figure 1", "FlipGuard overview", "Candidate ladder -> CKKS execution -> decision-stability validation -> fastest-safe selection.", "Method overview"],
        ["Figure 2", "Decision-stability condition", "Threshold tau, margin gamma, CKKS error, SAFE/REJECTED decision.", "Method"],
        ["Figure 3", "Repeated core tuner result", "Fastest-safe speedup across 6 workloads and latency-only rejected cases.", "Main experiment"],
        ["Figure 4", "Planner-guided candidate reduction", "Full ladder 77 candidates vs planner-guided 35 executed candidates.", "Planner result"],
        ["Figure 5", "Real-data tabular safety", "Safe path 10/10 pass with 0/0 flips/violations; fastest-without-guard unsafe 10/10.", "Real-data result"],
        ["Figure 6", "Margin coverage and claim boundary", "V_cert=2645, V_amb=61, minimum coverage 93.52%.", "Limitations"],
    ]

    content = "# Camera-ready figure specifications\n\n"
    content += "## Final figure candidates\n\n"
    content += md_table(["ID", "Title", "Main message", "Placement"], rows)
    content += "\n\n## Conference version recommendation\n\n"
    content += "Use 4 figures: FlipGuard overview, repeated core tuner result, planner-guided candidate reduction, and real-data tabular safety.\n\n"
    content += "## Journal version recommendation\n\n"
    content += "Use all 6 figures and include margin coverage plus the decision-stability condition figure.\n\n"
    content += "## Important warning\n\n"
    content += "Do not use AI-generated infographic text as final evidence. For submission, regenerate final figures from CSV/Markdown data using Python or LaTeX/TikZ so all numbers are exact and readable.\n"
    write("camera_ready_figure_specs.md", content)


def build_experiment_section_outline():
    rows = [
        ["4.1 Experimental setup", "Implementation, Lattigo backend, candidate ladder, timing protocol, safety factor.", "Candidate/profile definitions"],
        ["4.2 Core workload evaluation", "Evaluate Linear, LogReg, Polynomial, Sobel, Harris, MLP-square.", "Core one-shot and repeated tables"],
        ["4.3 Fastest-safe vs latency-only", "Show why latency-only minimization is unsafe for threshold/sign inference.", "Rejected latency-only rows and flip/violation counts"],
        ["4.4 Planner-guided validation reduction", "Show candidate validation cost reduction while preserving fastest-safe stability.", "77 -> 35 candidates, 54.55% reduction"],
        ["4.5 Real-data tabular safety", "Show safe path 10/10 pass and unsafe fastest path 10/10 rejected.", "Tabular safety and strategy comparison"],
        ["4.6 Margin coverage", "Define V_cert and V_amb and state the safety claim boundary.", "Margin coverage table"],
        ["4.7 Summary", "Connect all results back to decision-stability-constrained optimization.", "Claim-to-evidence matrix"],
    ]

    content = "# Paper experiment-section outline\n\n"
    content += "## Recommended section structure\n\n"
    content += md_table(["Section", "Purpose", "Primary evidence"], rows)
    content += "\n\n## Main narrative\n\n"
    content += "1. CKKS tuning should not be latency-only.\n"
    content += "2. Some latency-only candidates are safe, but many are rejected.\n"
    content += "3. Fastest-safe selection improves latency while preserving decisions.\n"
    content += "4. Planner-guided execution reduces candidate validation cost.\n"
    content += "5. Real-data tabular results show the same safety/performance tension.\n"
    content += "6. The safety claim is explicitly scoped to V_cert under the configured threshold, gamma_min, and safety factor.\n"
    write("paper_experiment_section_outline.md", content)


def build_artifact_reproducibility_checklist():
    rows = [
        ["Repository clean state", "git status --short"],
        ["Unit tests", "go test ./..."],
        ["One-shot summary", "python3 scripts/build_tuner_benchmark_summary.py"],
        ["Repeated core tuner", "bash scripts/run_core_tuner_repeated.sh 3"],
        ["Planner demo", "go run ./cmd/flipguard -experiment tuner_planner_demo"],
        ["Planner validation summary", "python3 scripts/build_planner_guided_validation_summary.py"],
        ["Planner-guided actual execution", "bash scripts/run_planner_guided_actual_execution.sh"],
        ["Experiment evidence summary", "python3 scripts/build_experiment_evidence_summary.py"],
        ["Paper-grade evidence pack", "python3 scripts/build_paper_grade_evidence_pack.py"],
        ["Submission-readiness pack", "python3 scripts/build_submission_readiness_pack.py"],
        ["Final repository check", "git status --short"],
    ]

    content = "# Artifact reproducibility checklist\n\n"
    content += "## Exact reproduction sequence\n\n"
    content += md_table(["Step", "Command"], rows)
    content += "\n\n## Paper artifact note\n\n"
    content += "Every submitted number should be traceable to the commit hash, full-refresh log, CSV/Markdown files under results/experiment_evidence_summary/current, and paper-facing files under results/paper_grade_evidence_pack/current.\n"
    write("artifact_reproducibility_checklist.md", content)


def build_readiness_scorecard_v2():
    rows = [
        ["Problem novelty", "10", "9.0/10", "Clear decision-stability-constrained CKKS tuning problem."],
        ["Implementation completeness", "10", "8.5/10", "Tuner, CKKS backend probes, planner-guided execution, repeated summaries, evidence builders."],
        ["Workload diversity", "10", "9.5/10", "Core 6 workloads plus real-data tabular 10 workloads."],
        ["Baseline / ablation strength", "10", "8.5/10", "Strategy comparison is now organized as paper-facing baseline/ablation evidence."],
        ["Repeated evaluation", "8", "8.0/10", "Repeated core tuner uses 3 repeats per workload."],
        ["Planner-guided evidence", "8", "8.0/10", "Actual planner-guided execution reduces candidate validation by 54.55%."],
        ["Real-data evidence", "10", "10.0/10", "Safe path passes 10/10 real-data workloads with zero flips and zero violations."],
        ["Claim-boundary discipline", "8", "8.5/10", "V_cert/V_amb, limitation, and novelty boundary are explicit."],
        ["Reproducibility", "8", "8.5/10", "Full-refresh command and artifact checklist are generated."],
        ["Related-work positioning", "8", "8.0/10", "Related-work matrix, positioning statement, and novelty boundary exist."],
        ["Figure/table readiness", "10", "8.5/10", "Camera-ready figure specs and experiment-section outline exist."],
    ]

    weighted = [(10, 9.0), (10, 8.5), (10, 9.5), (10, 8.5), (8, 8.0), (8, 8.0), (10, 10.0), (8, 8.5), (8, 8.5), (8, 8.0), (10, 8.5)]
    score = sum(w * s / 10.0 for w, s in weighted) / sum(w for w, _ in weighted) * 100.0

    content = "# Submission-readiness scorecard v2\n\n"
    content += "## Target\n\n"
    content += "- Domestic excellent-paper / journal-submission target: **95/100**\n"
    content += f"- Current estimated readiness after related-work, figure, and reproducibility packs: **{score:.1f}/100**\n"
    content += f"- Remaining gap to 95: **{95.0 - score:.1f} points**\n\n"
    content += "## Score table\n\n"
    content += md_table(["Criterion", "Weight", "Score", "Evidence / gap"], rows)
    content += "\n\n## Remaining work to reach 95+\n\n"
    content += "1. Render final camera-ready figures from CSV data.\n"
    content += "2. Write the actual paper sections using the claim-to-evidence matrix.\n"
    content += "3. Add final citations in BibTeX format.\n"
    content += "4. Add an appendix with reproducibility commands and raw evidence paths.\n"
    content += "5. Polish Korean/English title, abstract, contribution bullets, and limitation paragraph.\n"
    write("readiness_scorecard_v2.md", content)


def main():
    build_camera_ready_figure_specs()
    build_experiment_section_outline()
    build_artifact_reproducibility_checklist()
    build_readiness_scorecard_v2()

    print("Wrote submission-readiness pack:")
    for name in [
        "camera_ready_figure_specs.md",
        "paper_experiment_section_outline.md",
        "artifact_reproducibility_checklist.md",
        "readiness_scorecard_v2.md",
    ]:
        print(f"  {OUT / name}")


if __name__ == "__main__":
    main()
