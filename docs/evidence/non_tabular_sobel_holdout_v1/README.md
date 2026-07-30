# Non-Tabular BSDS500 Sobel Holdout Evidence V1

This pack freezes the predeclared BSDS500 Sobel selection and no-retuning
locked audit. The first analysis-derived candidate was numerically rejected;
the single frozen +4-bit repair was SAFE. The byte-identical selected literal
remained SAFE on disjoint test images.

The raw JSON and flattened CSV ledgers retain every patch-by-key CKKS score.
`scripts/freeze_bsds500_sobel_evidence.py --verify` rebuilds this pack and
recomputes all margins, decisions, errors, budgets, flips, violations, and
aggregate maxima.

Claim scope is one Sobel patch graph under scalar-replicated packing. This pack
does not support arbitrary graphs, packed full-image execution, edge-detection
accuracy, or CNN generalization. `paper_claim_allowed` remains false.
