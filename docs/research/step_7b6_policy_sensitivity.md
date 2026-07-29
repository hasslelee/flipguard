# Step 7B.6 Safety-Factor and Margin-Floor Sensitivity

Status: STATIC REPEATED-PARTITION GRID COMPLETE on 2026-07-29.
`delta=0.0005` is secondary policy sensitivity only.

## Question and claim boundary

The main protocol uses safety factor \(\alpha=0.5\) and margin floor
\(\delta=0.001\). These constants are policy choices, not universal
theoretical optima.

This study separates two effects:

1. the empirical certificate/oracle state observed at the five already
   executed alpha values;
2. the effect of alpha and margin floor on certifiable coverage and the
   directly synthesized initial literal.

The static synthesis grid does not recertify encrypted candidates at every
margin floor. It identifies policy sensitivity and follow-up candidates.

## Frozen grid

- alpha: `0.1, 0.25, 0.5, 0.75, 0.9`;
- margin floor:
  `0, 1e-5, 1e-4, 5e-4, 1e-3, 2e-3, 5e-3, 1e-2, 5e-2`;
- partitions: configuration validation and locked audit;
- split seeds: 0–4;
- datasets: five;
- models: `linear_poly3`, `mlp_square_linear_score`;
- static plans: `5 * 9 * 2 * 5 * 5 * 2 = 4,500`;
- synthesis floor: scale/Q-prime 18 bits, P 30 bits;
- precision slack: none.

The outputs are at:

```text
results/thesis_grade_protocol/policy_sensitivity_v1/full/
  synthesis_plans.csv
  synthesis_aggregate.csv
  alpha_certificate_sensitivity.csv
  summary.json
```

Verify them with:

```bash
python3 scripts/analyze_thesis_policy_sensitivity.py --verify
```

The publication-facing snapshot is:

```text
docs/evidence/policy_sensitivity_v1/
```

Verify the frozen file set, external bindings, and semantic checkpoints with:

```bash
python3 scripts/freeze_policy_sensitivity_evidence.py --verify
```

## Alpha result

Across the previously executed 1,100 candidate identities:

| Alpha | SAFE | REJECTED | FAILED | Oracle SELECTED |
|---:|---:|---:|---:|---:|
| 0.10 | 750 | 300 | 50 | 50/50 |
| 0.25 | 750 | 300 | 50 | 50/50 |
| 0.50 | 750 | 300 | 50 | 50/50 |
| 0.75 | 750 | 300 | 50 | 50/50 |
| 0.90 | 750 | 300 | 50 | 50/50 |

No candidate certificate state and no bounded-oracle candidate changes over
this alpha grid. At the current floor 0.001, the directly synthesized initial
signatures are also identical at every alpha:

```text
linear_poly3:             N13 / Q7 / scale20, 25/25
mlp_square_linear_score:  N13 / Q6 / scale20, 25/25
```

This is evidence of empirical robustness on the tested grid. It does not show
that 0.5 is theoretically optimal. The invariance occurs partly because the
minimum synthesis floor is active at \(\delta=0.001\).

## Margin-floor result at alpha 0.5

### Configuration validation

| Floor | Vcert / total | Coverage | Minimum workload coverage | Plan infeasible |
|---:|---:|---:|---:|---:|
| 0 | 8,230 / 8,230 | 100.00% | 100.00% | 0 |
| 0.0005 | 8,142 / 8,230 | 98.93% | 96.30% | 0 |
| 0.001 | 8,043 / 8,230 | 97.73% | 91.85% | 0 |
| 0.002 | 7,831 / 8,230 | 95.15% | 84.44% | 0 |
| 0.005 | 7,228 / 8,230 | 87.83% | 66.67% | 0 |
| 0.01 | 6,151 / 8,230 | 74.74% | 33.33% | 0 |
| 0.05 | 2,525 / 7,960* | 31.72% | 0.37% | 1 |

\* The aggregate denominator contains only the 49 feasible plans. One
`digits_binary/mlp_square_linear_score` split has no certifiable sample.

### Locked audit

| Floor | Vcert / total | Coverage | Minimum workload coverage | Plan infeasible |
|---:|---:|---:|---:|---:|
| 0 | 8,300 / 8,300 | 100.00% | 100.00% | 0 |
| 0.0005 | 8,203 / 8,300 | 98.83% | 95.93% | 0 |
| 0.001 | 8,122 / 8,300 | 97.86% | 92.22% | 0 |
| 0.002 | 7,894 / 8,300 | 95.11% | 85.56% | 0 |
| 0.005 | 7,282 / 8,300 | 87.73% | 66.30% | 0 |
| 0.01 | 6,164 / 8,300 | 74.27% | 32.56% | 0 |
| 0.05 | 2,485 / 7,760* | 32.02% | 0.37% | 2 |

\* Two `digits_binary/mlp_square_linear_score` audit splits have no
certifiable sample.

## Challenger policy

At alpha 0.5, floor 0.0005 and floor 0.001 synthesize exactly the same 50
initial signatures:

```text
N13_Q7_S20 = 25
N13_Q6_S20 = 25
```

Lowering the floor from 0.001 to 0.0005 adds:

- 99 certifiable validation samples;
- 81 certifiable locked-audit samples;
- no static parameter cost;
- no infeasible workload.

Therefore 0.0005 is retained only as
`SECONDARY_POLICY_SENSITIVITY`. Primary `delta=0.001` is frozen. Encrypted
validation and locked-audit observations under 0.0005 are diagnostic and may
not select or replace the primary policy.

The diagnostic records still report selection/NO_SAFE, audit outcomes, trial
cost, LogN, LogQP, flips, and violations. They do not produce an adoption
decision.

Diagnostic cost thresholds are retained as:

- total encrypted configuration trials no more than 1.10 times the baseline;
- no workload moves to a larger `LogN`;
- summed selected `declared_log_qp` no more than 1.10 times the baseline.

A new primary at 0.0005 would require a new untouched audit artifact. The
existing sensitivity audit cannot be reused as final audit evidence.

After the implementation and runners are committed, execute the complete
selection-audit pair with:

```bash
scripts/run_margin_floor_challenger.sh
```

The wrapper refuses a dirty measurement source, uses three fresh keys per
configuration trial and three new audit keys, and resumes safely by default.
Before executing the challenger, it reruns the floor-0.001 baseline selection
and locked audit as
`full_final_baseline_inputmodel_floor18_keys3` on the same immutable source
commit. Both arms use `--materialize-model-input`: the declared split rows are
treated as source feature data, the canonical score/decision artifact is
recomputed for both selection and locked audit, and each partition is admitted
only with verified source replay. The analysis emits
`primary_policy_adoption_allowed=false` and `paper_claim_allowed=false`.

After the wrapper completes, independently revalidate the comparison and
freeze the raw selection/audit results together with the protocol, comparison,
and baseline bindings:

```bash
python3 scripts/analyze_margin_floor_challenger.py --verify

python3 scripts/freeze_direct_locked_audit_evidence.py \
  --source-root \
    results/thesis_grade_protocol/direct_tabular_autotune_v1/full_inputmodel_margin0p0005_floor18_keys3/locked_audit/full_inputmodel_margin0p0005_floor18_keys3_locked_audit_keys3 \
  --output-root docs/evidence/margin_floor_challenger_v1 \
  --source-commit HEAD \
  --evidence-id margin_floor_challenger_v1 \
  --evidence-stage confirmatory \
  --selection-run-id full_inputmodel_margin0p0005_floor18_keys3 \
  --audit-run-id full_inputmodel_margin0p0005_floor18_keys3_locked_audit_keys3 \
  --split-seeds 0,1,2,3,4 \
  --key-repeats 3 \
  --expected-model-ids linear_poly3,mlp_square_linear_score \
  --require-max-budget-usage-below 1 \
  --require-source-replay \
  --execution-command scripts/run_margin_floor_challenger.sh \
  --source-protocol-manifest \
    results/thesis_grade_protocol/direct_tabular_autotune_v1/full_inputmodel_margin0p0005_floor18_keys3/summary/challenger_protocol.json \
  --extra-artifact \
    challenger_analysis=results/thesis_grade_protocol/direct_tabular_autotune_v1/full_inputmodel_margin0p0005_floor18_keys3/summary/challenger_analysis/summary.json \
  --extra-artifact \
    challenger_workloads=results/thesis_grade_protocol/direct_tabular_autotune_v1/full_inputmodel_margin0p0005_floor18_keys3/summary/challenger_analysis/workload_comparison.csv \
  --extra-artifact \
    baseline_summary=results/thesis_grade_protocol/direct_tabular_autotune_v1/full_final_baseline_inputmodel_floor18_keys3/summary/summary.json \
  --extra-artifact \
    baseline_workloads=results/thesis_grade_protocol/direct_tabular_autotune_v1/full_final_baseline_inputmodel_floor18_keys3/summary/workload_results.csv

python3 scripts/freeze_direct_locked_audit_evidence.py \
  --output-root docs/evidence/margin_floor_challenger_v1 \
  --verify
```

The freezer refuses an unexpected model set or any selected audit whose
sample-specific normalized error-budget usage is missing, non-finite, or at
least one.

## Interpretation

The margin floor is a coverage/assurance policy, not a conventional accuracy
hyperparameter. Increasing it removes difficult near-boundary samples from the
claim and can eventually make the claim vacuous. Decreasing it expands the
claim but may require greater precision or cause rejection. Paper tables must
therefore report coverage and `NO_SAFE` together with safety outcomes.
