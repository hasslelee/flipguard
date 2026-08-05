# Comprehensive CKKS Comparison V3

This immutable overlay separates heterogeneous external evidence into four
tiers. It never treats compiler build smoke as end-to-end reproduction and
never ranks native absolute latency across runtimes.

## Frozen conclusion

- Landscape: 20 named external systems plus FlipGuard.
- Official artifact rows: 13 external repositories or archives audited.
- Build/runtime smoke: 10 external artifacts passed a documented smoke gate.
- Native external per-sample output: one scoped EVA replay.
- External provider gate: EVA native rejection and Orion static
  `PLAN_UNSUPPORTED` import.
- External `PORTABLE_EXACT` or defensible graph-equivalent common-executor
  arms: zero.
- Original-paper normalized results: 13 external systems, each bound to its
  own baseline and PDF locator.
- Completion: `EXHAUSTED_FEASIBLE_SET`.

The native, gate, and portability counts are intentionally lower than the
aspirational targets. Artifact absence, dependency closure, credential-gated
inputs, hardware requirements, missing raw outputs, graph mismatch, and
security non-equivalence are reported as evidence rather than converted to
zeroes or synthetic results.

## Reading order

1. `manifest.json` gives counts and the completion decision.
2. `landscape/systems.csv` is the 21-row multi-axis census.
3. `build_matrix.csv` distinguishes smoke from end-to-end execution.
4. `native_execution_records.csv`, `provider_gate_records.csv`, and
   `common_executor_records.csv` are separate evidence tiers.
5. `paper_reported_results.csv` contains only within-paper normalized values.
6. `fairness_limitations.md` defines the paper claim boundary.
7. `verify_comprehensive_ckks_comparison_v3.py` performs deterministic static
   verification without encrypted execution.

Frozen FlipGuard policies and predecessor evidence are referenced, not
modified. Raw official-paper PDFs are not redistributed; official URLs,
SHA-256 values, and page/table/figure locators are recorded instead.
