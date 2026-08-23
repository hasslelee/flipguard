# V18 Figure and Table Data Map

| Publication item | Source | Statistical unit | Key boundary |
|---|---|---|---|
| Table 1: decision gate on/off | `results/comparison_extension_v18/table_decision_gate_effect.csv` | protocol-defined case | separate-input N is 47/68 for gate-off candidates |
| Table 2: initial-only/full | `results/comparison_extension_v18/table_repair_ablation.csv` | case | B=4 is candidate-evaluation budget, not four repairs |
| Table 3: numerical objectives | `results/comparison_extension_v18/table_numerical_objective_diagnostics.csv` | case | diagnostic, not a named tuner |
| Table 4: external subset | `results/comparison_extension_v18/table_exact_external_comparator_subset.csv` | frozen external workload | comparator class must remain visible |
| Table 5: finite reference | `results/comparison_extension_v18/table_finite_reference_quality.csv` | case | offline finite reference, not global exhaustive search |
| Table 6: stability cost | `results/comparison_extension_v18/table_cost_of_decision_stability.csv` | case | formal gate-off inference latency is unmeasured |
| Figure 1: error-latency overlay | `results/comparison_extension_v18/figure_error_latency_decision_overlay.csv` | candidate nested in case | candidate rows are not independent samples |
| Figure 2: component ablation | `results/comparison_extension_v18/figure_component_ablation.csv` | case | C2/C3 are internal causal ablations |
| Figure 3: cost vs avoided instability | `results/comparison_extension_v18/figure_additional_cost_vs_avoided_instability.csv` | case aggregate/model family | use changed-literal and all-case summaries separately |
| Figure 4: proposed vs finite latency | `results/comparison_extension_v18/figure_proposed_vs_finite_latency_gap.csv` | case; bootstrap cluster=dataset-model | ratio direction is finite/direct |
| Figure 5: external eligibility | `results/comparison_extension_v18/figure_external_comparator_eligibility.csv` | system/workload subset | never merge native runtime latencies |

The machine-readable headline values are in
`results/comparison_extension_v18/metrics.json`; candidate and case provenance
are in `candidate_level_ledger.csv` and `case_level_ledger.csv`.
