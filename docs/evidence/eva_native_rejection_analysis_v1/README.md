# EVA Native Rejection Analysis V1

This static post-hoc analysis preserves the native EVA/SEAL validation
rejection without any encrypted rerun, candidate change, or policy change.

- Executions: 42/42 successful across 14 rows and 3 fresh keys.
- Decision result: 11 flips, 36 budget violations, `REJECTED`.
- Key-repeat violations: 14,
  13, 9.
- Mean absolute error changed from
  1.579557 on repeat 1 to
  0.095808 on repeat 3.
- Every sample violated under at least one key; 8
  of 14 violated under all three keys.
- EVA plaintext and the bound score agree within
  4.209e-13.

The pattern contradicts a single-bad-key, single-bad-sample, or plaintext
source-mismatch explanation. It is consistent with insufficient numerical
precision for this schedule, but no causal scale, schedule, or runtime claim
is made without a prospective ablation.

`paper_claim_allowed=false`.
