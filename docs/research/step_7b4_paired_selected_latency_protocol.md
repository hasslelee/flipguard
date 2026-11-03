# Step 7B.4 Paired Selected-Literal Latency Protocol

Status: FINAL PROTOCOL FROZEN after the seed-0 pilot on 2026-07-28.
The 50-workload final execution is pending a clean source commit.

## Purpose and claim boundary

The completed 1,100-candidate catalog and direct-autotune runs measured
latencies in separate processes. Those values are useful diagnostics but
cannot support a paper speedup claim.

Step 7B.4 remeasures three frozen roles within each workload:

1. `direct`: the exact literal selected by direct synthesis and adaptive
   repair;
2. `catalog`: the fastest SAFE candidate in the declared 22-candidate bounded
   catalog at alpha 0.5;
3. `reference`: the declared CKKS reference profile/path.

The catalog is an evaluation-only bounded oracle. This experiment may
support a direct-versus-bounded-catalog latency statement only over the
declared five datasets, two model graphs, and five split seeds.

## Key comparability

Different CKKS parameter literals cannot share cryptographic keys. Requiring
one identical key across `LogN`, `Q`, and `P` changes would be technically
invalid.

The executable protocol therefore:

- creates one parameter-compatible key set per arm;
- keeps that key set fixed through warm-up and every measured observation for
  the workload;
- loads and executes all three arms in one process;
- creates fresh arm-specific key sets for the next workload;
- pairs observations by workload, measurement pass, and row ID.

Key generation/setup time is reported separately per arm and excluded from
both evaluation-only and end-to-end inference latency.

## Frozen inputs

The workload identities and role assignments come from:

```text
results/thesis_grade_protocol/direct_vs_catalog_oracle_v1/full/
  comparison.csv
results/thesis_grade_protocol/direct_tabular_autotune_v1/
  full_floor18_keys3/summary/workload_results.csv
```

Each workload result binds the direct selection JSON, model artifact,
configuration-validation CSV, catalog candidate, and reference candidate by
path and SHA-256.

The final matrix is:

- split seeds: `0,1,2,3,4`;
- datasets: `banknote`, `digits_binary`, `iris_binary`, `mnist_pool16`,
  `wdbc`;
- models: `linear_poly3`, `mlp_square_linear_score`;
- workloads: 50;
- arms per workload: 3.

## Frozen measurement schedule

The seed-0 pilot used 10 workloads, four evenly spaced rows, one warm-up pass,
and three measured passes. It produced 360 raw observations with zero decision
flips in every arm.

Pilot stability diagnostics were:

- normalized mean total latency by measured pass: 0.9963, 0.9864, 1.0172;
- normalized mean total latency by order position: 1.0005, 0.9966, 1.0029;
- median within-workload total-latency CV: direct 0.1130, catalog 0.0969,
  reference 0.0896;
- identical catalog/reference literal sanity check: five workloads,
  geometric-mean total ratio 0.9950.

The pilot catalog/direct total-latency ratio was 1.9769, with a 95% pilot
workload-bootstrap interval of 1.9225 to 2.0379. The model-stratified pilot
ratios were 1.9976 for `linear_poly3` and 1.9564 for
`mlp_square_linear_score`. These values select the final repetition count and
are not paper estimates.

The final counts are fixed from this pilot:

- evenly spaced validation rows per workload: 6;
- complete warm-up passes per arm: 1;
- complete measured passes per arm: 6;
- measured observations per arm/workload: 36;
- total measured raw observations: `50 * 3 * 6 * 6 = 5,400`;
- total warm-up executions: `50 * 3 * 6 = 900`.

Six balanced cyclic-and-reverse arm orders are used once per measured pass.
The starting order rotates by pass and row, so every selected row experiences
all six arm orders exactly once. Each arm occupies each order position exactly
twice per pass.
No measured observation is removed as an outlier.

## Metrics and inference unit

Every raw record contains:

- measurement pass, row ID, order, and arm identity;
- encode/encrypt, model, polynomial, evaluation-only, decrypt/decode, and
  total milliseconds;
- plaintext and CKKS scores, absolute error, and decision-flip status.

Per-arm reporting includes mean, median, p95, standard deviation, and IQR for
total and evaluation-only latency. Setup/key generation time is reported
separately.

The primary pair is `catalog/direct`; a ratio greater than one means direct
synthesis is faster. `reference/direct` is secondary, and
`reference/catalog` is a comparator/sanity pair.

The primary aggregate unit is one workload instance, not one raw repeated
timing. Overall ratios are equal-weight geometric means of the 50 workload
ratios. A deterministic 95% workload-bootstrap interval uses:

```text
seed = 20260728
replicates = 10,000
```

Results are also separated by model family, dataset, and split seed. Raw timing
rows must not be treated as 4,500 independent generalization samples.

## Failure and falsification rules

The final run is incomplete if any of the following occurs:

- fewer than 50 workload results validate;
- a source/input/candidate digest changes during resume;
- an arm fails to execute;
- an expected paired observation is absent or duplicated.

A decision flip is retained in the raw output and weakens the frozen-selection
claim; it is never silently discarded. The direct latency advantage is not
supported if the 95% workload-bootstrap interval for `catalog/direct` total
latency includes or falls below 1.0.

Even a passing result does not establish global parameter optimality,
production latency stability, or generalization beyond the declared
workloads.

## Executable protocol

Pilot:

```bash
python3 scripts/run_paired_tabular_latency.py \
  --mode pilot \
  --output-root \
    results/thesis_grade_protocol/paired_tabular_latency_v1/pilot_seed0 \
  --warmup-runs 1 \
  --measurement-runs 3 \
  --max-rows 4 \
  --max-workloads 10
```

Frozen final run:

```bash
python3 scripts/run_paired_tabular_latency.py \
  --mode final \
  --output-root \
    results/thesis_grade_protocol/paired_tabular_latency_v1/full \
  --warmup-runs 1 \
  --measurement-runs 6 \
  --max-rows 6
```

The orchestrator resumes validated workload JSON files by default, writes one
log per workload, and regenerates checksum-bound aggregate CSV/JSON outputs.

## Evidence freeze

The pilot evidence is frozen separately and remains ineligible for a paper
latency claim:

```bash
python3 scripts/freeze_paired_latency_evidence.py --force
```

After the final run completes, freeze it with:

```bash
python3 scripts/freeze_paired_latency_evidence.py \
  --input-root \
    results/thesis_grade_protocol/paired_tabular_latency_v1/full \
  --output-root docs/evidence/paired_latency_final_v1 \
  --evidence-id paired_latency_final_v1 \
  --force
```

The independent verifier recomputes the workload-level geometric means and
10,000-replicate bootstrap intervals. It permits a scoped paper latency claim
only for a final clean-source run with zero decision flips and a
`catalog/direct` total-latency confidence-interval lower bound above 1.0.
