# Direct Locked Audit Seed-0 Evidence v1

## Result

- Frozen configurations audited: `10`
- Locked-audit PASS: `10/10`
- Configuration trials: `10`
- Fresh-key runs: `30`
- Retuning during audit: `0`
- Total audit V_cert: `1623`
- Total audit V_amb: `37`
- PASS results with zero flips and violations: `10/10`

The audit command evaluated each validation-selected CKKS literal exactly
once on the disjoint `locked_audit_test.csv` partition with three fresh
keypairs. It did not call synthesis or candidate repair.

## Reproduce

Regenerate the deterministic split artifacts, regenerate the selection run,
and execute:

```bash
scripts/run_direct_tabular_locked_audit_matrix.sh --seed0 --force
```

Verify this compact snapshot:

```bash
python3 scripts/freeze_direct_locked_audit_evidence.py \
  --output-root docs/evidence/direct_locked_audit_seed0_v1 \
  --verify
```

The large audit CSV files are not duplicated here. `manifest.json` binds them
and their tracked source test CSVs by SHA-256. The snapshot includes all ten
selection results, split manifests, locked-audit results, the execution
ledger, and aggregate CSV/JSON outputs.

## Claim Boundary

This is frozen preliminary evidence for one predeclared split seed and three
fresh keypairs. It supports no-retuning held-out decision stability for the
recorded workloads. It does not establish split independence, key
independence, distribution-wide safety, a sound analytical error bound, or
final latency claims.
