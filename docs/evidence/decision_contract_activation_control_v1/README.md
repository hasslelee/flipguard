# Decision-Contract Activation Control V1

This finite-domain development control holds graph, interval calibration,
aggregate sensitivity, and frozen policies constant while changing the
minimum certifiable decision margin.

- Static synthesis effect: `SUPPORTED`.
- Encrypted control: `SUPPORTED`.
- Natural-data synthesis effect: `BLOCKED`.
- Selection: 4/4 SELECTED.
- No-retuning locked audit: 4/4 PASS.
- Audit flips/violations: 0/0.

Two pre-encryption CSV-schema failures are preserved under `recovery/` as
superseded implementation-recovery evidence. They completed zero key runs and
did not inform a policy change.

`paper_claim_allowed=false`.
