# Step 7B.3 Full Validation Execution

Status: COMPLETE on 2026-07-28. All 1,100 candidate runs are present and
strict summarization passes.

## Frozen matrix

- Partition seeds: `0,1,2,3,4`
- Datasets: `banknote`, `digits_binary`, `iris_binary`, `mnist_pool16`, `wdbc`
- Primary models: `linear_poly3`, `mlp_square_linear_score`
- Profiles: 11 built-in profiles
- Execution paths: `baseline_non_rescale`, `rescale_aware`
- Candidate runs: `50 * 22 = 1,100`
- Alpha evaluations per candidate: `0.1,0.25,0.5,0.75,0.9`
- Final certificate rows: `5,500`
- Frozen selection metric: `mean_total_ms`

These are 10 dataset-model workloads x 5 deterministic repeated partitions
of fixed held-out artifacts, or 50 workload-partition instances. Seed 0 is
development/ablation evidence. Seeds 1-4 are post-freeze repeated-partition
evaluation, and every partition audit is a no-retuning locked audit. They are
not independent training seeds, models, or datasets, and the 50 rows must not
be treated as independent samples for inferential statistics.

The 50 configuration-validation partitions contain 8,230 input rows. Across all
22 candidates, the full study performs 181,060 encrypted inferences.

## Final execution result

The strict full ledger contains:

- all 1,100 expected candidate identities across all 50 workloads;
- 1,050 successful executions and 50 explicit execution failures;
- 5,500 candidate-certificate rows and 250 oracle rows;
- certificate states `SAFE=3,750`, `REJECTED=1,500`, and `FAILED=250`;
- all 250 alpha-specific oracle outcomes are `SELECTED`;
- summary digest
  `sha256:d77d052a2e81315bc84d4f0299646eb8b22c594a7896486413910e5e4a6f7f4e`.

An unbounded resume skipped all 1,100 terminal identities and reproduced the
same strict summary digest with `validation_oracle_run=PASS`.

At alpha 0.5, all 50 direct results bind to the same model,
validation digest, and `V_cert`/`V_amb` partition as their complete catalog
oracles. Direct synthesis used 70 encrypted configuration trials and 210
fresh-key runs, versus 1,100 catalog candidate executions. The direct timing
was lower in all 50 unpaired records, with a diagnostic geometric-mean catalog
to direct ratio of 1.603x. This is not a speedup claim because the processes and
measurement runs were not paired.

## Checkpoint execution

The full matrix order is deterministic:

```text
seed -> dataset -> model -> profile -> execution path
```

The runner supports a bounded number of newly executed candidates:

```bash
./scripts/run_thesis_grade_tabular_validation_oracle.sh \
  --full \
  --resume \
  --max-new-runs 10 \
  --quiet-skips
```

`--max-new-runs` does not change the matrix or discard failed candidates. It
only limits work performed by one invocation. Completed successful candidates are
recognized from all three required facts:

1. an `ok,0` identity in `run_status.csv`;
2. an existing candidate `summary.csv`;
3. an existing candidate `records.csv`.

A recorded non-zero `FAILED` result with its stdout log is also terminal
evidence and is skipped on resume. This prevents repeated known failures from
consuming every later chunk quota. To deliberately repeat terminal failures,
use:

```bash
./scripts/run_thesis_grade_tabular_validation_oracle.sh \
  --full \
  --resume \
  --retry-failed
```

`--retry-failed` replaces the prior status row for that candidate; it does not
create duplicate identities.

`--quiet-skips` suppresses one line per prior terminal candidate while
retaining aggregate `candidate_skipped_ok` and `candidate_skipped_failed`
counts. It is recommended once several checkpoints have accumulated.

After a bounded invocation, the runner writes an incomplete summary with input
and status digests and prints:

```text
validation_oracle_checkpoint=PASS
```

This is an execution checkpoint, not thesis-grade evidence.

## Completion gate

An unbounded resume performs strict matrix validation:

```bash
./scripts/run_thesis_grade_tabular_validation_oracle.sh \
  --full \
  --resume
```

Step 7B.3 passed with:

- `actual_run_count = 1,100`;
- `candidate_certificate_rows = 5,500`;
- `oracle_rows = 250`;
- every expected profile/path identity occurs exactly once;
- failed runs remain explicit `FAILED` rows;
- strict summarization runs without `--allow-incomplete`;
- the planner/oracle comparison regenerated from the completed oracle.

The completed planner comparison contains 250 rows and reports zero false
`NO_SAFE` outcomes. Partial checkpoint numbers remain excluded from paper
claims.

## Direct-synthesis comparison boundary

The completed fixed catalog is a bounded oracle, not the deployment candidate
space. A directly synthesized literal may be outside all 22 catalog
candidates and must not be projected to the nearest profile.

The completed comparison applies the following procedure:

1. select the fastest SAFE catalog candidate using the frozen
   `mean_total_ms` rule;
2. keep the direct literal frozen from its configuration-validation run;
3. remeasure the catalog oracle, CKKS reference, and direct literal under the
   same process, paired input, warm-up, and repetition protocol, using one
   fixed parameter-compatible key set per arm;
4. report encrypted tuning work separately from selected-configuration
   inference latency;
5. report direct-versus-catalog bounded regret only within the declared
   candidate domain.

Existing timings from different processes remain diagnostic. They cannot be
combined into the final latency table.

The executable paired protocol and its technically valid key policy are frozen
in
[`step_7b4_paired_selected_latency_protocol.md`](step_7b4_paired_selected_latency_protocol.md).

The final digest-bound comparison is at:

```text
results/thesis_grade_protocol/direct_vs_catalog_oracle_v1/full/
  comparison.csv
  summary.json
```

It reports `complete_oracle_workloads_compared=50`,
`oracle_matrix_complete=true`, and
`paper_latency_claim_allowed=false`.

The compact evidence snapshot copies the complete aggregate tables and binds
all 3,200 non-duplicated raw run artifacts by SHA-256:

```text
docs/evidence/full_oracle_comparison_v1/
```

Verify it with:

```bash
python3 scripts/freeze_full_oracle_comparison_evidence.py \
  --output-root docs/evidence/full_oracle_comparison_v1 \
  --verify
```

The comparison tool refuses an incomplete oracle by default:

```bash
python3 scripts/compare_direct_synthesis_to_catalog_oracle.py \
  --force
```

During execution only, a diagnostic checkpoint can be generated with:

```bash
python3 scripts/compare_direct_synthesis_to_catalog_oracle.py \
  --allow-incomplete \
  --output-root \
    results/thesis_grade_protocol/direct_vs_catalog_oracle_v1/checkpoint \
  --force
```

Checkpoint mode excludes any workload with fewer than 22 catalog candidates.
It also verifies the model and validation digests and requires identical
`V_cert`/`V_amb` partitions. Its outputs are permanently labeled
`UNPAIRED_DIAGNOSTIC` with `paper_latency_claim_allowed=false`.
