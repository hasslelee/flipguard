# HIT-Direct Matched-Workload Diagnostic V1

This no-rerun post-hoc diagnostic compares the frozen FlipGuard direct and
source-replayed AWS HIT results on the same raw seed-0 iris/linear validation
artifact. Model, raw source, graph, threshold, alpha, and margin floor match.

The direct arm is SAFE and passes locked audit. The HIT arm is REJECTED and is
not audited. Timing ratios are unpaired diagnostics only; no speedup or causal
parameter claim is allowed.

`paper_claim_allowed=false`.
