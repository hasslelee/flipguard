# Direct Locked Audit Evidence: direct_locked_audit_seeds1_2_checkpoint_v1

## Result

- Split seeds in this pack: `1,2`
- Frozen configurations audited: `20`
- Locked-audit PASS: `20/20`
- Configuration trials: `20`
- Fresh-key runs: `60`
- Retuning during audit: `0`
- Total audit V_cert: `3252`
- Total audit V_amb: `68`
- Matrix complete: `false`

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
  --output-root docs/evidence/direct_locked_audit_seeds1_2_checkpoint_v1 \
  --verify
```

The large audit CSV files are not duplicated here. `manifest.json` binds them
and their tracked source test CSVs by SHA-256. The snapshot includes all ten
selection results, split manifests, locked-audit results, the execution
ledger, and aggregate CSV/JSON outputs.

## Claim Boundary

This is frozen preliminary evidence for the recorded split checkpoint and three
fresh keypairs. It supports no-retuning held-out decision stability for the
recorded workloads. It does not establish split independence, key
independence, distribution-wide safety, a sound analytical error bound, or
final latency claims.
