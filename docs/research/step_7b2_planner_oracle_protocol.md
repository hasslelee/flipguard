# Step 7B.2 Legacy Catalog-Pruning Planner Baseline

Status: full 1,100-candidate oracle projection complete on 2026-07-28.
This is an evaluation-only baseline, not FlipGuard's primary contribution.

## Reviewer concern

Candidate pruning alone does not show that the planner preserves useful SAFE
configurations. The planner may miss the exhaustive fastest-SAFE candidate or
incorrectly return `NO_SAFE`.

## Literature precedent

FHE compiler and scale-management systems such as HECATE, ELASM, and HECO
evaluate optimization quality and runtime trade-offs over explicit workload
sets. FlipGuard therefore reports search reduction together with optimality
loss, abstention errors, and planning overhead.

Primary references:

- HECATE, CGO 2022:
  <https://doi.org/10.1109/CGO53902.2022.9741265>
- ELASM, USENIX Security 2023:
  <https://www.usenix.org/conference/usenixsecurity23/presentation/lee-yongwoo>
- HECO, USENIX Security 2023:
  <https://www.usenix.org/conference/usenixsecurity23/presentation/viand>

## Implementation requirement

The planner is evaluated by projecting its resolved candidate IDs onto
`candidate_certificates.csv`. It must not execute CKKS again. Consequently,
the exhaustive oracle and planner comparison use identical score-error,
decision, failure, and latency observations.

The graph summaries follow the current scalar-ciphertext tabular runtime:

| Model | Ct-Ct depth | Total mul ops | Add ops | Rescale sites |
|---|---:|---:|---:|---:|
| `linear_poly3` | 2 | `input_dim + 4` | `input_dim + 2` | 2 |
| `mlp_square_linear_score` | 1 | `hidden*input_dim + 2*hidden + 1` | `hidden*input_dim + hidden + 1` | 1 |

For every split and alpha, the decision budget is:

```text
protected_margin = min margin(x) for x in V_cert
decision_budget = alpha * protected_margin
```

The executable profile catalog is restricted to profiles already present in
the oracle input. Any resolved `profile__path` identity outside that matrix is
an error.

## Frozen selection rule

`mean_total_ms` is the selection metric for Step 7B.2 and the subsequent full
validation oracle. It is minimized among SAFE candidates. Candidate ID is the
deterministic tie breaker. Median and p95 remain reported robustness metrics,
not post-hoc selection alternatives.

## Metrics and undefined cases

- SAFE recall: `|SAFE_oracle intersect C_planner| / |SAFE_oracle|`.
- Optimum recall: one when the exhaustive fastest-SAFE candidate is present in
  the planner set, zero otherwise.
- Latency regret:
  `(T(planner_fastest_safe) - T(oracle_fastest_safe)) /
  T(oracle_fastest_safe)`.
- Pruning ratio: `1 - |C_planner| / |C_oracle|`.
- False `NO_SAFE`: oracle has at least one SAFE candidate while the planner
  projection has none.
- If the oracle outcome is `NO_SAFE`, SAFE recall, optimum recall, and latency
  regret are undefined and serialized as blank CSV values. They are not zero.
- If only the planner outcome is `NO_SAFE`, latency regret is undefined and
  false `NO_SAFE` is true.

## Falsification test

Step 7B.2 weakens the planner claim if any of the following occurs:

- a planner candidate is outside the exhaustive matrix;
- optimum recall is repeatedly low;
- false `NO_SAFE` occurs;
- latency regret is materially positive across workloads;
- planning overhead is not negligible relative to the saved validation work.

## Reproduction

```bash
./scripts/run_thesis_grade_planner_oracle_comparison.sh --smoke
```

The command writes:

```text
results/thesis_grade_protocol/planner_oracle_comparison_v1/smoke/
  planner_candidates.csv
  planner_summary.csv
  comparison.csv
  summary.json
```

After the full validation oracle is complete, run the same script with
`--full`. The script reads existing oracle records and performs no CKKS
execution.

## Full result

The strict full run produced 250 comparison rows over 50 workloads and five
alpha values. It projected 1,750 planner-candidate rows onto the same frozen
oracle observations.

| Scope | False NO_SAFE | Optimum recall | Mean SAFE recall | Mean latency regret | Max latency regret | Mean pruning |
|---|---:|---:|---:|---:|---:|---:|
| All 250 rows | 0 | 68.00% | 19.44% | 0.7366% | 8.6847% | 68.18% |
| `linear_poly3` | 0 | 100.00% | 16.67% | 0.0000% | 0.0000% | 72.73% |
| `mlp_square_linear_score` | 0 | 36.00% | 22.22% | 1.4731% | 8.6847% | 63.64% |

Mean planning overhead was 149.091 microseconds. Results were identical across
the five evaluated alpha values because the candidate certificate states did
not change over the frozen alpha sweep.

The legacy planner is therefore supported as a high-pruning candidate provider that
retained at least one SAFE candidate in every evaluated group. It is not
supported as a reliable fastest-SAFE oracle substitute: it missed the
exhaustive optimum in 64% of the MLP rows. The complete outputs are:

```text
results/thesis_grade_protocol/planner_oracle_comparison_v1/full/
  planner_candidates.csv
  planner_summary.csv
  comparison.csv
  summary.json
```

The checksum-bound compact snapshot is:

```text
docs/evidence/full_oracle_comparison_v1/
```

It includes the full planner tables and binds the underlying oracle run
artifacts in its manifest.
