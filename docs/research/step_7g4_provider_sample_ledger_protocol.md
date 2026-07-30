# Step 7G.4: Provider Sample-Key Evidence Ledger

## Motivation

The frozen AWS HIT development trial recorded six numerical-budget
violations across 42 sample-key observations, but `TabularTrialResult` V1
stored only aggregate counts and maxima. The violating samples and key
repeats cannot be reconstructed without another encrypted run, which is
prohibited for the predeclared one-trial HIT contract.

## Scope

Future concrete provider requests (provider schema v2) capture an optional
sample-key ledger after encrypted execution. Existing direct synthesis and
provider schema v1 execution retain their prior output shape.

Each observation binds:

- sample ID and fresh-key repeat;
- plaintext score, CKKS score, and threshold;
- decision margin and `alpha * margin` error budget;
- absolute error and normalized budget usage;
- plaintext and CKKS decisions;
- flip and error-violation indicators.

The provider result verifier recomputes every derived field and the aggregate
flip, violation, maximum-error, maximum-usage, coverage, repeat, and encrypted
sample-evaluation counts. A mismatch fails closed.

## Noninterference

Ledger capture does not change CKKS parameters, Direct Policy V2, Security
Policy V2, alpha, margin floor, candidate stopping, repair, or certification.
It is not used for candidate repair or selection. The frozen HIT trial is not
rerun, and its aggregate-only localization limit remains part of the evidence.
