# FlipGuard NO_SAFE Control Evidence

This pack freezes three scope-separated controls.

## Budgeted abstention confirm

- Workloads: `40/40`
- Outcomes: `NO_SAFE=16`, `SELECTED=24`
- Unsafe selected: `0`
- Partition: disjoint locked-audit test
- Split seeds: `[1, 2, 3, 4]`
- Fresh-key repeats: `3`
- Trial budget: one encrypted candidate
- Claim boundary: `NO_SAFE` is budget-scoped, not global infeasibility

The pack includes every result JSON, every input/result binding sidecar, the
aggregate tables, and the exact source snapshots whose composite digest is
recorded by the budgeted control.

## Finite-domain control

- Domain: `short_chain_3` baseline and rescale-aware paths
- Candidate certificates: `100`
- States: `SAFE=0`, `REJECTED=75`, `FAILED=25`
- Restricted outcome: `NO_SAFE=50/50`
- Full catalog outcome on the same workloads: `SELECTED=50/50`

This control is retrospective and only proves the declared two-candidate
domain. It is not a global CKKS infeasibility claim.

## Disjoint finite-domain locked audit

- Workloads: `50`
- Candidate rows: `100`
- Fresh-key attempts: `300`
- Candidate states: `{'FAILED': 25, 'REJECTED': 75}`
- Restricted outcome: `NO_SAFE=50/50`
- Control result: `PASS`

The two fixed candidates were re-executed on each split's disjoint
`locked_audit_test` partition in independent processes. Validation status was
retained only for transition reporting and was not used to admit audit
candidates.


## Verification

```bash
python3 scripts/freeze_no_safe_control_evidence.py \
  --output-root docs/evidence/no_safe_controls_confirmatory_v1 \
  --verify
```

The manifest checks every copied file and every externally bound model,
validation/audit split, and full-oracle input.
