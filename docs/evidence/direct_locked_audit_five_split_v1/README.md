# Direct Locked Audit Evidence: direct_locked_audit_five_split_v1

## Result

- Split seeds in this pack: `0,1,2,3,4`
- Frozen configurations audited: `50`
- Locked-audit PASS: `50/50`
- Configuration trials: `50`
- Fresh-key runs: `150`
- Retuning during audit: `0`
- Total audit V_cert: `8122`
- Total audit V_amb: `178`
- Matrix complete: `true`

The audit command evaluated each validation-selected CKKS literal exactly
once on the disjoint `locked_audit_test.csv` partition with three fresh
keypairs. It did not call synthesis or candidate repair.

## Reproduce

Regenerate the deterministic split artifacts, regenerate the selection run,
and execute:

```bash
scripts/run_direct_tabular_locked_audit_matrix.sh --full --selection-run full_floor18_keys3 --key-repeats 3 --resume
```

Verify this compact snapshot:

```bash
python3 scripts/freeze_direct_locked_audit_evidence.py \
  --output-root docs/evidence/direct_locked_audit_five_split_v1 \
  --verify
```

The large audit CSV files are not duplicated here. `manifest.json` binds them
and their tracked source test CSVs by SHA-256. The snapshot includes
50 selection results and the matching split manifests,
locked-audit results, execution ledger, and aggregate CSV/JSON outputs.

## Claim Boundary

This is frozen preliminary evidence for the recorded split set and three
fresh keypairs. It supports no-retuning held-out decision stability for the
recorded workloads. It does not establish split independence, key
independence, distribution-wide safety, a sound analytical error bound, or
final latency claims.
