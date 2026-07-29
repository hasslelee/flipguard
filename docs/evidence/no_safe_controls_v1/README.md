# FlipGuard NO_SAFE Control Evidence

This pack freezes two scope-separated controls.

## Budgeted abstention pilot

- Workloads: `10/10`
- Outcomes: `NO_SAFE=4`, `SELECTED=6`
- Unsafe selected: `0`
- Partition: disjoint locked-audit test, split seed 0
- Trial budget: one encrypted candidate
- Claim boundary: `NO_SAFE` is budget-scoped, not global infeasibility

The pack includes all 10 result JSON files, all 10 input/result binding
sidecars, the aggregate tables, and the exact source snapshots whose composite
digest is recorded by the pilot.

## Finite-domain control

- Domain: `short_chain_3` baseline and rescale-aware paths
- Candidate certificates: `100`
- States: `SAFE=0`, `REJECTED=75`, `FAILED=25`
- Restricted outcome: `NO_SAFE=50/50`
- Full catalog outcome on the same workloads: `SELECTED=50/50`

This control is retrospective and only proves the declared two-candidate
domain. It is not a global CKKS infeasibility claim.

## Verification

```bash
python3 scripts/freeze_no_safe_control_evidence.py \
  --output-root docs/evidence/no_safe_controls_v1 \
  --verify
```

The manifest checks every copied file and every externally bound model,
validation split, and full-oracle input.
