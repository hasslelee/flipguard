# Step 7B.2a: Direct CKKS Configuration Synthesis

Status: implemented and validated as development evidence on 2026-07-27.
The seed-0 three-key locked audit is frozen as preliminary evidence. Final
multi-seed and repeated-latency evidence is not frozen.

## Research Decision

The built-in 11-profile catalog remains useful as a finite offline oracle. It
is no longer the first-party deployment algorithm.

The first-party path now accepts:

- a model artifact;
- a configuration-validation dataset;
- a split identity;
- a decision threshold and margin policy;
- a security target and encrypted-trial budget.

It returns a directly generated CKKS parameter literal or `NO_SAFE`. It does
not map the result to a built-in profile name.

## Workload Contract

`internal/ckksplanner.BuildTabularWorkloadContract` performs the following
before parameter generation:

1. hashes the exact model and validation artifacts;
2. derives the plaintext computation DAG from the model artifact;
3. re-evaluates every validation row and rejects score or decision mismatch;
4. partitions the exact ordered validation set into `V_cert` and `V_amb`;
5. derives the protected margin and output-error budget;
6. propagates empirical validation intervals through the DAG for an initial
   sensitivity signal;
7. derives the Lattigo scale and level demand for the exact rescale-aware
   execution path.

The interval-derived sensitivity is a planning signal. It is not presented as
a sound CKKS error bound. A candidate is `SAFE` only after encrypted validation
through the existing certification engine.

## Why Depth Is Not Chain Length

The current backend multiplies ciphertexts by non-integer model coefficients.
Lattigo v6 represents such scalar multiplications at the current Q-prime scale.
Consequently, one call to `RescaleTo` can consume multiple Q primes.

The `lattigo_v6_rescale_scale_trace_v1` analysis symbolically tracks:

- scale growth from ciphertext and scalar multiplications;
- Q primes consumed by each rescale;
- scale still present at the output;
- the Q primes needed for both consumed levels and terminal capacity.

For the current tabular implementations:

| Model | Multiplicative depth | Rescale levels consumed | Terminal scale exponent | Required Q primes |
|---|---:|---:|---:|---:|
| `linear_poly3` | 2 | 6 | 1 | 7 |
| `mlp_square_linear_score` | 1 | 3 | 3 | 6 |
| `mlp_square_poly3` | 3 | 9 | 1 | 10 |

This distinction is enforced by an end-to-end encrypted unit test. The earlier
`depth + margin` approximation failed that test and was replaced.

## Direct Parameter Generation

The initial scale is derived from:

```text
unit_error_budget =
    output_error_budget / aggregate_sensitivity

precision_target_bits =
    ceil(-log2(unit_error_budget))
```

An explicit policy guard is then applied. `LogQ` is generated from the traced
Q-prime demand, while `LogP` is generated large enough for the largest Q prime.
If Lattigo cannot generate the required number of distinct NTT-friendly primes
at that bit size, only this prime-generation exhaustion is retried, one bit at
a time. The analysis scale, backend lift, and validation-attempt count are
recorded. All other backend errors remain fatal. The smallest admitted `LogN`
that supports the slots and total declared `log2(QP)` is then selected.

Security admission uses the uniform-ternary, Gaussian-error, classical
128-bit limits in Table 4.2 of the 2024
[Security Guidelines for Implementing Homomorphic Encryption](https://doi.org/10.62056/anxra69p1):

| LogN | Maximum declared log2(QP) |
|---:|---:|
| 12 | 108 |
| 13 | 217 |
| 14 | 438 |
| 15 | 881 |

Lattigo parameter construction and this external security envelope are separate
checks. Successful construction alone is never reported as 128-bit security.

## Adaptive Execution

The planner evaluates one analysis-derived candidate first.

- A level/rescale failure appends one scale-sized Q prime.
- A numerical rejection raises the scale by the declared repair step.
- Every repair is rechecked against the security envelope and Lattigo.
- Execution stops at the first observed-validation `SAFE` candidate.
- Exhausted trial or repair budgets return `NO_SAFE`.

This is a sequential repair policy. It does not execute a predeclared
neighborhood.

## Commands

Generate a plan without encrypted execution:

```bash
go run ./cmd/flipguard-synthesize \
  --model datasets/tabular_suite/banknote/mlp_square_linear_score/model.json \
  --validation results/thesis_grade_protocol/tabular_splits_v1/split_seed_0/banknote/mlp_square_linear_score/configuration_validation.csv \
  --split-id split_seed_0
```

Generate, execute, certify, and select:

```bash
./scripts/run_direct_tabular_autotune.sh \
  datasets/tabular_suite/banknote/mlp_square_linear_score/model.json \
  results/thesis_grade_protocol/tabular_splits_v1/split_seed_0/banknote/mlp_square_linear_score/configuration_validation.csv \
  split_seed_0 \
  results/direct_tabular_autotune/development/banknote_mlp_seed0.json
```

The resumable matrix runner fixes the workload order and writes one
digest-bound result per workload:

```bash
# One-workload end-to-end smoke check.
scripts/run_direct_tabular_autotune_matrix.sh --smoke --force

# Development matrix: 5 datasets x 2 model forms x split seed 0.
scripts/run_direct_tabular_autotune_matrix.sh --seed0 --force

# Thesis matrix: the same 10 workloads x split seeds 0..4.
scripts/run_direct_tabular_autotune_matrix.sh --full --force

# Resume without repeating completed workloads.
scripts/run_direct_tabular_autotune_matrix.sh --full --resume

# Experimental low-floor policy. Backend feasibility automatically raises a
# floor that cannot supply enough NTT-friendly primes.
scripts/run_direct_tabular_autotune_matrix.sh \
  --seed0 \
  --precision-floor 18 \
  --force

# Negative ablation: fill precision without increasing the initial LogN tier.
scripts/run_direct_tabular_autotune_matrix.sh \
  --seed0 \
  --precision-floor 18 \
  --same-tier-precision \
  --force

# Fresh-key robustness: each configuration trial is certified over three
# independently generated keypairs.
scripts/run_direct_tabular_autotune_matrix.sh \
  --seed0 \
  --precision-floor 18 \
  --key-repeats 3 \
  --force
```

`run_status.csv` is the execution ledger. The summarizer validates the
workload identity and trial count in every successful result before writing
`summary/workload_results.csv`, `summary/encrypted_trials.csv`, and
`summary/summary.json`. Configuration trials and fresh-key runs are counted
separately. A checkpoint with fewer than the declared number of workloads is
reported as incomplete; any recorded execution failure makes the runner exit
nonzero.

## Development Evidence

One non-repeated development run on the same 205-row seed-0 validation split
produced:

| Model | Direct configuration | Status | Flip | Violations | Max error | Mean ms | Existing default-rescale mean ms | Ratio |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `mlp_square_linear_score` | `N13, Q=[33,30,30,30,30,30], P=[33], scale=30` | SAFE | 0 | 0 | `7.56e-7` | 118.51 | 279.99 | 2.36x |
| `linear_poly3` | `N14, Q=[33,30,30,30,30,30,30], P=[33], scale=30` | SAFE | 0 | 0 | `2.09e-4` | 158.43 | 147.26 | 0.93x |

The latency values were measured in separate processes and are not final
speedup evidence. The MLP result shows the intended structural opportunity:
the planner reduces both ring dimension and chain size. The linear result is a
negative control: its traced Q demand keeps `LogN=14`, and no speedup is
claimed.

The complete seed-0 development matrix subsequently produced:

- 10/10 `SELECTED` outcomes;
- 10 encrypted configuration trials in total, one per workload;
- zero flips and zero error-budget violations on `V_cert=1610`;
- `V_amb=36`, which was excluded by the predeclared margin policy;
- `N14/Q7/scale30` for all five `linear_poly3` workloads;
- `N13/Q6/scale30` for all five `mlp_square_linear_score` workloads.

The fixed catalog protocol would execute 22 configurations per workload, or
220 for the same ten-workload matrix. The direct path therefore used 95.45%
fewer encrypted configuration trials in this development run. This is an
execution-count comparison, not yet an oracle-quality claim.

The result also exposes a current limitation. Data-derived precision targets
varied from 7 to 15 bits, but the conservative 30-bit scale floor dominated
every workload. The current evidence demonstrates graph-dependent synthesis
and early stopping; it does not yet demonstrate dataset-dependent parameter
variation. The floor must only be lowered after backend feasibility,
security admission, forced-repair behavior, and locked-audit stability are
tested.

For the two banknote workloads whose 22-candidate catalog oracle is complete,
the non-repeated development comparison was:

| Model | Direct trials | Catalog trials | Direct mean ms | Bounded catalog oracle mean ms | Catalog/direct |
|---|---:|---:|---:|---:|---:|
| `linear_poly3` | 1 | 22 | 147.95 | 147.26 | 0.995x |
| `mlp_square_linear_score` | 1 | 22 | 113.96 | 210.07 | 1.843x |

The direct candidate is outside the fixed catalog. These timings came from
separate single runs, so they are diagnostic only and must not be reported as
final speedups.

### Low-floor adaptive development ablation

The requested 18-bit scale/Q-prime floor was not directly executable. Lattigo
could not generate the required number of distinct standard-ring NTT primes at
18 or 19 bits. Static feasibility raised the initial scale to 20 bits and
recorded:

- `analysis_scale_bits=18`;
- `backend_scale_lift_bits=2`;
- `backend_validation_attempts=3`.

The complete seed-0 ablation then produced:

- 10/10 final `SELECTED` outcomes;
- 14 encrypted configuration trials total;
- four initial `REJECTED` linear candidates with observed flips and
  error-budget violations;
- four feedback-triggered `repair_scale_1` candidates at scale 24, all SAFE;
- six initial candidates that were SAFE without repair;
- zero flips and zero error-budget violations for all final selections.

The selected linear configurations were data dependent: banknote, digits,
MNIST, and WDBC selected `N13/Q7/scale24` after one repair, while iris selected
`N13/Q7/scale20` directly. All five MLP workloads selected
`N13/Q6/scale20` directly. Fourteen trials are 93.64% fewer than the 220
configuration executions in the fixed-catalog protocol.

Single-run timing diagnostics showed a 1.856x geometric-mean improvement for
linear workloads relative to the conservative scale-30 direct run. MLP
workloads showed 0.930x, because both policies already use `N13/Q6`; reducing
only modulus bit sizes did not create a latency-tier change. This motivates a
lexicographic policy: minimize `LogN` and Q-prime count first, then retain
precision that fits within the same structural cost tier.

These are one-split, one-key-per-workload development results. The large
low-scale error variance makes independent keys, repeats, and locked audit
mandatory before changing the default policy.

### Same-tier precision negative ablation

A follow-up static policy maximized scale without increasing the
analysis-minimum `LogN`. It generated `N13/Q7/scale26` for linear workloads and
`N13/Q6/scale30` for MLP workloads. The static planner considered exact
parameter literals only; it did not encrypt every intermediate literal.

The encrypted result did not improve the search:

- 10/10 workloads were eventually selected;
- 14 encrypted trials were still required;
- banknote, digits, MNIST, and WDBC linear scale-26 candidates were REJECTED;
- their scale-30 repairs increased `LogN` to 14;
- only iris linear retained `N13/Q7/scale26`;
- all MLP scale-30 candidates were SAFE on the first trial.

This falsifies a simple monotonic assumption that increasing CKKS scale within
a security tier necessarily reduces the end-to-end observed error of this
rescale chain. The mode remains available only as a reproducible negative
ablation and is not the default planner policy. Candidate selection must be
evaluated across independent keys rather than inferred from scale alone.

### Fresh-key aggregation

`WorkloadContract` schema 2 adds `validation_key_repeats`. One encrypted
configuration trial now:

1. creates a fresh Lattigo context and keypair for every requested key run;
2. executes the exact digest-bound validation rows under each key;
3. appends every key-run score to the corresponding sample's
   `ApproxScores`;
4. builds one certificate over all sample-by-key observations;
5. reports both configuration trials and completed key runs.

The three-key smoke run completed one configuration trial and three key runs
with `SuccessRuns=3`. A three-key banknote linear floor-18 development run
used:

| Trial | Configuration | Key runs | Status | Flips | Violations | Max error |
|---:|---|---:|---|---:|---:|---:|
| 1 | `N13/Q7/scale20` | 3 | REJECTED | 10 | 27 | 0.01708 |
| 2 | `N13/Q7/scale24` | 3 | SAFE | 0 | 0 | 0.00702 |

The complete seed-0 three-key matrix then reproduced the single-key selection
structure:

- 10/10 final `SELECTED` outcomes;
- 14 encrypted configuration trials and 42 completed fresh-key runs;
- four scale-20 linear candidates rejected across three keys;
- four scale-24 linear repairs SAFE across all three keys;
- iris linear scale-20 SAFE across all three keys;
- all five MLP scale-20 candidates SAFE across all three keys;
- zero flips and zero error-budget violations in every final certificate.

The initial rejected candidates accumulated 191 flips and 852 error-budget
violations across the four affected linear workloads, demonstrating that the
repair trigger is not a cosmetic policy branch. This remains same-split
fresh-key evidence, not a key-independence or data-generalization claim.

### No-retuning locked audit

The selected literals from the seed-0, floor-18, three-key validation run were
then frozen. `flipguard-audit` verified the split manifest, artifact digests,
and exact disjoint `row_id` sets before evaluating each literal on
`locked_audit_test.csv`.

The audit path enforces:

1. exactly one selected candidate with exactly one matching SAFE validation
   trial;
2. exact model, validation, audit, and split-manifest bindings;
3. disjoint validation and audit row sets matching the manifest;
4. one audit configuration trial with no call to synthesis or repair;
5. a new context and keypair for each requested audit key run.

The complete seed-0 locked audit produced:

- 10/10 `LOCKED_AUDIT_PASS` outcomes;
- 10 configuration trials and 30 completed fresh-key runs;
- zero retuned workloads and zero execution failures;
- zero flips and zero protected error-budget violations in all ten audits;
- aggregate audit `V_cert=1623` and `V_amb=37`.

The frozen selected structure remained data dependent:

| Workloads | Frozen configuration | Audit outcome |
|---|---|---|
| banknote, digits, MNIST, WDBC linear | `N13/Q7/scale24` | 4/4 PASS |
| iris linear | `N13/Q7/scale20` | 1/1 PASS |
| all five MLP-square-linear | `N13/Q6/scale20` | 5/5 PASS |

The compact evidence pack is
[`direct_locked_audit_seed0_v1`](../evidence/direct_locked_audit_seed0_v1/README.md).
It contains the ten selection results, ten split manifests, ten audit results,
the execution ledger, aggregate outputs, provenance, and checksums. The
ignored split CSV files are reproducible from tracked source data and are
digest-bound in the manifest.

This resolves the seed-0 validation-to-audit leakage concern. It does not
resolve split robustness: only split seed 0 has been selected and audited.
Three fresh keys on each partition also do not establish key independence.
The next required empirical step is the predeclared five-split selection and
locked-audit matrix.

## Current Claim Boundary

Supported:

- direct parameter generation for the three current tabular model forms;
- the scalar-replicated packing strategy;
- the Lattigo v6 rescale-aware path;
- classical 128-bit admission under the recorded standard table;
- observed-validation certification and explicit `NO_SAFE`.

Not yet supported:

- automatic packing/layout synthesis;
- non-rescale scale-capacity synthesis;
- bootstrapping;
- a sound analytical CKKS output-error bound;
- distribution-wide safety;
- final latency or generality claims.
