# Non-Tabular BSDS500 Harris Holdout Evidence V1

This pack freezes the predeclared BSDS500 Harris selection and no-retuning
locked audit. The first analysis-derived candidate was SAFE. The byte-identical
selected literal remained SAFE on 50 disjoint test-image clusters.

The raw JSON and flattened CSV ledgers retain every patch-by-key CKKS score.
`scripts/freeze_bsds500_harris_evidence.py --verify` rebuilds this pack and
recomputes all margins, decisions, errors, budgets, flips, violations, source
closure, and aggregate maxima.

Claim scope is one scalar-replicated 5x5 Harris response graph. This pack does
not support arbitrary graphs, packed full-image execution, corner-detection
accuracy, or CNN generalization. `paper_claim_allowed` remains false.
