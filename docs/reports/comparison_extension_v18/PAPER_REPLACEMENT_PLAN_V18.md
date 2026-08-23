# V18 Paper Replacement Plan

The manuscript is not modified by this stage. The following replacements are
approved inputs for a later editing pass.

## Main comparison narrative

Replace any framing of the finite reference as an operating baseline with:

> The exhaustive finite set is used offline to test missed feasibility and
> selection quality. It is not presented as a practical user workflow or a
> global CKKS optimum.

Lead the comparison section with the causal ablations: full method versus gate
off, and full method versus initial-only. Follow those with finite-reference
quality. Move system-name breadth to the compatibility-qualified external
subsection.

## Tables

1. Insert `table_decision_gate_effect.csv` as the primary causal result.
2. Insert `table_repair_ablation.csv` immediately after the adjustment algorithm.
3. Use `table_numerical_objective_diagnostics.csv` to show that fast/Pareto does not automatically imply stability.
4. Use `table_finite_reference_quality.csv` for rank, false NO_SAFE, and regret.
5. Use `table_exact_external_comparator_subset.csv` with an explicit eligibility column.
6. Use `table_cost_of_decision_stability.csv`; label inference latency as unmeasured for the gate-off arm.

## Figures

Use the five V18 figure-data files only after plotting scripts preserve case as
the statistical unit. Cross-runtime points must be faceted rather than ranked on
one latency axis. The HEIR common-executor ratios must remain diagnostic.

## Numbers and wording to retire

- Do not call 83.426443% an improvement over existing tuners.
- Do not call the finite reference exhaustive over the CKKS space.
- Do not state that all gate-off candidates failed on separate inputs.
- Do not state that HEIR caused the eight common-executor flips.
- Do not state that the gate increases formal inference latency; that arm was not measured.

## Legacy evidence

Keep V17 and earlier 70/700, 40/40, and 3.1407 results in their labeled legacy
controlled-study roles. Do not combine their denominators with V18's 89/537 or
68-case primary population.
