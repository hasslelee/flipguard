# Step 7B.5 Budgeted NO_SAFE Negative Control

Status: BUDGETED SEED-0 PILOT PASS and FINITE-DOMAIN LOCKED-AUDIT SMOKE PASS
on 2026-07-29. Both confirmatory protocols are frozen and pending a clean
source commit.

## Question and boundary

The main five-split study selected a SAFE configuration for every workload.
That evidence does not show whether FlipGuard abstains when its declared
encrypted-trial budget expires.

This negative control asks:

> If the one allowed candidate is empirically unsafe, does FlipGuard preserve
> the rejection and return `NO_SAFE` instead of selecting it?

`NO_SAFE` here is explicitly budget-scoped. It means no SAFE candidate was
admitted within one encrypted configuration trial. It does not mean no CKKS
configuration exists globally. The main study already shows that a monotone
scale repair can make these linear workloads SAFE.

## Independence from the main selection run

The control does not replay the configuration-validation records used to tune
the main results. It rebuilds each workload contract from the disjoint
`locked_audit_test.csv` partition and executes the newly synthesized initial
candidate there.

Frozen policy:

- initial synthesis floor: scale/Q-prime 18 bits;
- P special-prime floor: 30 bits;
- precision slack: none;
- maximum encrypted configuration trials: 1;
- margin floor: 0.001;
- safety factor: 0.5;
- pilot key repeats: 1;
- confirmatory key repeats: 3.

The pilot uses split seed 0. The confirmatory run uses only split seeds 1
through 4, for 40 workload instances.

## Pilot result

The seed-0 pilot completed all 10 disjoint workloads:

| Model/control group | SELECTED | NO_SAFE |
|---|---:|---:|
| `linear_poly3`, non-iris datasets | 0 | 4 |
| `linear_poly3`, iris | 1 | 0 |
| `mlp_square_linear_score` | 5 | 0 |
| Total | 6 | 4 |

All four `NO_SAFE` outcomes ended in `REJECTED` with
`NUMERICAL_REJECT`. Their observed flips and error violations remain in the
raw results. No `NO_SAFE` result contains a selected candidate, and all six
selected candidates have zero flips and zero error violations.

## Frozen confirmatory prediction

The seeds 1–4 result is predeclared as:

- 16 non-iris `linear_poly3` workloads: `NO_SAFE`;
- 4 iris `linear_poly3` workloads: `SELECTED`;
- 20 `mlp_square_linear_score` workloads: `SELECTED`;
- total: `NO_SAFE=16`, `SELECTED=24`.

The control fails if any workload command fails, an outcome differs from this
map, an unsafe trial is selected, a `NO_SAFE` payload contains a selected
candidate, or a non-linear workload returns `NO_SAFE`.

The exact count prediction is deliberately falsifiable. A mismatch is retained
and reported rather than relabeled after execution.

## Executable protocol

Pilot:

```bash
python3 scripts/run_no_safe_budget_negative_controls.py \
  --mode pilot \
  --output-root \
    results/thesis_grade_protocol/no_safe_budget_control_v1/pilot_seed0
```

Confirmatory seeds 1–4:

```bash
python3 scripts/run_no_safe_budget_negative_controls.py \
  --mode confirm \
  --output-root \
    results/thesis_grade_protocol/no_safe_budget_control_v1/confirm_seeds1_4
```

Confirm mode refuses to execute if any control source file is uncommitted.
Every workload has a source/input/result digest sidecar, and resume validates
those bindings before skipping completed work. The source digest closes over
the command, experiment script, module files, and every non-test Go source in
the runtime `certify`, `ckksbackend`, `ckksplanner`, and `tuner` packages.

After the confirmatory run, freeze it separately from the historical seed-0
pilot while retaining both the retrospective and disjoint finite-domain
controls:

```bash
python3 scripts/run_finite_domain_no_safe_locked_audit.py \
  --mode confirm \
  --output-root \
    results/thesis_grade_protocol/finite_domain_no_safe_locked_audit_v1/full

python3 scripts/freeze_no_safe_control_evidence.py \
  --budget-root \
    results/thesis_grade_protocol/no_safe_budget_control_v1/confirm_seeds1_4 \
  --finite-root \
    results/thesis_grade_protocol/finite_domain_no_safe_control_v1/full \
  --finite-audit-root \
    results/thesis_grade_protocol/finite_domain_no_safe_locked_audit_v1/full \
  --output-root docs/evidence/no_safe_controls_confirmatory_v1 \
  --evidence-id no_safe_controls_confirmatory_v1

python3 scripts/freeze_no_safe_control_evidence.py \
  --output-root docs/evidence/no_safe_controls_confirmatory_v1 \
  --verify
```

Confirmatory freezing requires the exact predeclared `NO_SAFE=16`,
`SELECTED=24` outcome map, 40 complete workloads, three completed fresh-key
runs per candidate, a clean source binding, and normalized error-budget usage
below one for every selected result.

The current pilot and retrospective finite-domain artifacts are frozen at:

```text
docs/evidence/no_safe_controls_v1/
```

The pack contains 36 checksum-bound internal files and binds 22 external
model, disjoint-split, and full-oracle inputs. Verify it with:

```bash
python3 scripts/freeze_no_safe_control_evidence.py \
  --output-root docs/evidence/no_safe_controls_v1 \
  --verify
```

## Finite-domain locked-audit protocol

This protocol validates budgeted abstention, not true global infeasibility.

A separate retrospective finite-domain control is now complete at:

```text
results/thesis_grade_protocol/finite_domain_no_safe_control_v1/full/
```

It declares exactly the two `short_chain_3` execution paths as the candidate
domain. Across 50 workloads its 100 independently executed certificates are
`SAFE=0`, `REJECTED=75`, and `FAILED=25`, so the restricted oracle returns
`NO_SAFE=50/50`. The complete 22-candidate catalog returns `SELECTED=50/50`
for the same workloads. This validates domain-scoped `NO_SAFE` semantics but is
retrospective because the restricted domain is derived from the completed
configuration-validation oracle.

Verify it with:

```bash
python3 scripts/build_finite_domain_no_safe_control.py --verify
```

The stronger disjoint rerun is now implemented. It executes the same two
candidates on every `locked_audit_test.csv` partition in a separate process
for each fresh-key repeat. The original validation status is used only to
report transitions; audit admission is recomputed from the audit plaintext
margin and raw CKKS score.

The one-workload smoke used split-seed 0 `banknote/linear_poly3`:

| Candidate | Validation | Audit | Audit evidence |
|---|---|---|---|
| `short_chain_3__baseline_non_rescale` | REJECTED | REJECTED | V_cert=207, flips=96, violations=207 |
| `short_chain_3__rescale_aware` | FAILED | FAILED | expected rescale level exhaustion |

The restricted audit outcome was `NO_SAFE`, and the deterministic verifier
reproduced all two attempt bindings and aggregate tables. This is a
dirty-source smoke, not final evidence.

The clean confirmatory protocol covers 50 workloads, 100 candidate rows, and
300 independent fresh-key attempts. Its falsification criteria require:

- no SAFE candidate in the declared domain;
- `NO_SAFE=50/50`;
- zero unexpected execution failures;
- exact model, audit CSV, split-manifest, source, log, and raw-output digests.

Any SAFE audit candidate makes the control result `FAIL` and remains recorded.
