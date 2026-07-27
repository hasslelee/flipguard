# Step 7B.3 Full Validation Execution

Status: execution protocol active; final evidence is incomplete until all
1,100 candidate runs are present and strict summarization passes.

## Frozen matrix

- Split seeds: `0,1,2,3,4`
- Datasets: `banknote`, `digits_binary`, `iris_binary`, `mnist_pool16`, `wdbc`
- Primary models: `linear_poly3`, `mlp_square_linear_score`
- Profiles: 11 built-in profiles
- Execution paths: `baseline_non_rescale`, `rescale_aware`
- Candidate runs: `50 * 22 = 1,100`
- Alpha evaluations per candidate: `0.1,0.25,0.5,0.75,0.9`
- Final certificate rows: `5,500`
- Frozen selection metric: `mean_total_ms`

The 50 configuration-validation splits contain 8,230 input rows. Across all
22 candidates, the full study performs 181,060 encrypted inferences.

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

Step 7B.3 passes only when:

- `actual_run_count = 1,100`;
- `candidate_certificate_rows = 5,500`;
- `oracle_rows = 250`;
- every expected profile/path identity occurs exactly once;
- failed runs remain explicit `FAILED` rows;
- strict summarization runs without `--allow-incomplete`;
- the planner/oracle comparison is regenerated from the completed oracle.

The `--full` planner/oracle wrapper refuses to run while the oracle summary is
incomplete or was produced with `--allow-incomplete`.

No partial checkpoint number may be used in a paper claim.
