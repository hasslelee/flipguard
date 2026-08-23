# Targeted Execution Report

## Disposition

`NO_NEW_ENCRYPTED_EXECUTION`

- Exact external missing cases: 0
- New atomic workload cases: 0
- New encrypted candidate evaluations: 0
- New formal latency measurements: 0
- Reused V17 primary direct evaluations: 89
- Reused V17 finite-reference evaluations: 537
- Reused V17 formal latency rows: 68

The portable-exact HEIR subset, output-comparable EVA subset, and numerical-only
CoreLab subset already exist in `focused_external_comparison_v8`. Re-execution
would not change their declared eligibility.

The gate-off replay selects a candidate for all 68 primary cases. Candidate-
specific separate-input observations exist for 47 of those candidates. The 21
rejected initial literals were not advanced to that V17 stage, so their outcomes
remain `NOT_EVALUATED`. They were not imputed or selectively rerun. A complete
counterfactual extension would require 21 cases, exceeding the V18 fast budget
of 12, and is outside the protocol's permitted exact-external targeted-run gate.

No correctness worker, timing worker, CKKS binary, or latency harness was
started by V18.
