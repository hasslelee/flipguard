# Direct Locked Audit Evidence: direct_locked_audit_final_source_v1

## Result

- Split seeds in this pack: `1,2,3,4`
- Frozen configurations audited: `40`
- Locked-audit PASS: `40/40`
- Configuration trials: `56`
- Fresh-key runs: `120`
- Retuning during audit: `0`
- Total audit V_cert: `6499`
- Total audit V_amb: `141`
- Matrix complete: `true`
- Expected model IDs: `linear_poly3,mlp_square_linear_score`
- Normalized error-budget usage limit: `1.0`
- Source replay required: `true`
- Extra protocol/analysis artifacts: `1`

The audit command evaluated each validation-selected CKKS literal exactly
once on the disjoint `locked_audit_test.csv` partition with
3 fresh keypair(s). It did not call synthesis or candidate
repair.

## Reproduce

Regenerate the deterministic split artifacts, regenerate the selection run,
and execute:

```bash
scripts/run_thesis_final_confirmatory_suite.sh
```

Verify this compact snapshot:

```bash
python3 scripts/freeze_direct_locked_audit_evidence.py \
  --output-root docs/evidence/direct_locked_audit_final_source_v1 \
  --verify
```

The exact model artifact, upstream source test CSV, and source/materialized CSVs for both selection and locked audit are included and bound by SHA-256. The snapshot includes
40 selection results and the matching split manifests,
locked-audit results, execution ledger, and aggregate CSV/JSON outputs.

## Claim Boundary

This is frozen confirmatory evidence for the recorded split set and
3 fresh keypair(s). It supports no-retuning held-out decision
stability for the recorded workloads. It does not establish split
independence, key
independence, distribution-wide safety, a sound analytical error bound, or
final latency claims.
