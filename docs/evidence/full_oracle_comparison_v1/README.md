# Full Oracle Comparison Evidence: full_oracle_comparison_v1

## Result

- Oracle candidate executions: `1,100/1,100`
- Successful executions: `1,050`
- Explicit execution failures: `50`
- Certificate rows: `5,500`
- Certificate states: `SAFE=3,750`, `REJECTED=1,500`, `FAILED=250`
- Oracle outcomes: `SELECTED=250`
- Direct outcomes at alpha 0.5: `SELECTED=50/50`
- Direct configuration trials / key runs: `70 / 210`
- Planner false NO_SAFE: `0/250`
- Planner optimum recall: `68.00%`
- Planner mean pruning: `68.18%`
- Planner mean bounded regret: `0.7366%`

## Reproduce

```bash
scripts/run_thesis_grade_tabular_validation_oracle.sh --full --resume --quiet-skips
python3 scripts/compare_direct_synthesis_to_catalog_oracle.py --force
scripts/run_thesis_grade_planner_oracle_comparison.sh --full
```

Verify this snapshot:

```bash
python3 scripts/freeze_full_oracle_comparison_evidence.py \
  --output-root docs/evidence/full_oracle_comparison_v1 \
  --verify
```

The snapshot copies all aggregate oracle, direct-comparison, and
planner-comparison CSV/JSON outputs. To keep the repository compact,
individual candidate logs and raw records are not duplicated.
`manifest.json` binds all 3200 external run artifacts by
path, byte size, and SHA-256.

## Claim Boundary

This is a bounded exhaustive oracle over the frozen 22-candidate catalog, not
a global CKKS optimum. Direct and catalog latencies were recorded in separate
processes and remain `UNPAIRED_DIAGNOSTIC`; the diagnostic ratio is not a paper
speedup claim. The planner retained at least one SAFE candidate in every
evaluated group, but its MLP optimum recall is 36%, so it is not a reliable
fastest-SAFE oracle substitute.
