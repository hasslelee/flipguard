# Step 7B.7 Deeper-Graph Structural Extension

Status: STATIC 5-SPLIT PLAN GRID COMPLETE on 2026-07-29. Encrypted
selection and locked audit are pending a clean source commit.

## Purpose and claim boundary

The primary 50-workload experiment covers `linear_poly3` and
`mlp_square_linear_score`. Those model names differ, but their evaluated CKKS
graphs remain shallow. This extension adds the already exported
`mlp_square_poly3` graph on all five datasets and five split seeds.

This is a structural extension within the existing scalar-replicated tabular
backend. It is not evidence for CNNs, packed SIMD inference, arbitrary ONNX
graphs, or universal model support.

## Frozen inputs

- datasets: banknote, digits-binary, iris-binary, MNIST pool-16, WDBC;
- model: square-activation MLP followed by a cubic score polynomial;
- split seeds: 0–4;
- validation ratio: 0.5;
- margin floor: 0.001;
- safety factor: 0.5;
- synthesis floor: scale/Q-prime 18 bits and P-prime 30 bits;
- encrypted configuration trials: at most four;
- fresh keys: three per selection trial and three new keys per audit.

The dedicated split root is:

```text
results/thesis_grade_protocol/structural_extension_splits_v1/
```

It contains 25 disjoint validation/audit pairs. Its summary digest is:

```text
sha256:8e1ac4e74e086a86944510023c0312f5ee77b0dedeaaa4dc3d1b5332607fa609
```

## Static plan result

All 50 partition-specific plans are feasible:

| Property | Result |
|---|---:|
| Static plans | 50/50 `PLAN_OK` |
| Graph shape | depth 3 / rescale 3 / required Q primes 10 |
| Initial signature | `N14 / Q10 / scale22` on 50/50 |
| Declared `logQP` | 253 bits |
| Security-envelope headroom | 185 bits |
| Validation `Vcert / Vamb` | 3,992 / 123 |
| Validation coverage | 97.01% |
| Audit `Vcert / Vamb` | 4,033 / 117 |
| Audit coverage | 97.18% |

The static outputs are:

```text
results/thesis_grade_protocol/structural_extension_v1/static_plans/
  plans.csv
  summary.json
```

Verify them with:

```bash
python3 scripts/analyze_structural_extension_plans.py --verify
```

Static feasibility is not encrypted safety evidence.

## Exploratory encrypted pilot

Before freezing the confirmatory run, one dirty-source, one-key implementation
pilot was executed on split-seed 0 `iris_binary/mlp_square_poly3`.

| Partition | Outcome | Trials | Vcert / Vamb | Max raw error | Max error-budget usage |
|---|---|---:|---:|---:|---:|
| Configuration validation | `SELECTED` | 1 | 14 / 0 | 0.05645 | 0.78285 |
| Locked audit | `LOCKED_AUDIT_PASS` | 1 | 16 / 0 | 0.05241 | 0.79005 |

The frozen literal was `N14 / Q10 / scale22`; the audit performed no retuning.
The raw maximum error can exceed the minimum-margin contract budget because it
may occur on a different sample with a larger decision margin. The normalized
usage is the auditable quantity:

```text
error / (safety_factor * sample_margin)
```

Both observed maxima are below 1. This pilot validates the execution path and
the new diagnostic field; it is not confirmatory paper evidence.

## Confirmatory encrypted protocol

Run the complete experiment only from a clean committed measurement source:

```bash
scripts/run_structural_extension.sh
```

The wrapper deterministically rebuilds and verifies the split set, executes
25 direct-synthesis selections, then evaluates every frozen selected literal
once on its disjoint audit partition with three new keys. Selection and audit
both materialize their canonical artifact from model-input source rows and
record `source_replay_verified=true`.

A structural-generalization claim requires:

1. 25/25 `SELECTED` results, each with zero flips and error violations;
2. 25/25 locked-audit passes without retuning;
3. aggregate validation `Vcert/Vamb = 3992/123`;
4. aggregate audit `Vcert/Vamb = 4033/117`;
5. maximum sample-specific `error / (alpha * margin)` below 1 in every
   selection and audit;
6. exact model type `mlp_square_poly3` and graph depth 3 in every contract.

An explicit `NO_SAFE` remains correct framework behavior, but it does not
satisfy this extension's audited-support claim and must be reported.

After a complete run, freeze the raw selections and audits with the exact
structural protocol, split, and static-plan checkpoints:

```bash
python3 scripts/analyze_structural_extension_plans.py --verify

python3 scripts/freeze_direct_locked_audit_evidence.py \
  --source-root \
    results/thesis_grade_protocol/direct_tabular_autotune_v1/full_structural_poly3_inputmodel_floor18_keys3/locked_audit/full_structural_poly3_inputmodel_floor18_keys3_locked_audit_keys3 \
  --output-root docs/evidence/structural_extension_v1 \
  --source-commit HEAD \
  --evidence-id structural_extension_v1 \
  --evidence-stage confirmatory \
  --selection-run-id full_structural_poly3_inputmodel_floor18_keys3 \
  --audit-run-id full_structural_poly3_inputmodel_floor18_keys3_locked_audit_keys3 \
  --split-seeds 0,1,2,3,4 \
  --key-repeats 3 \
  --expected-model-ids mlp_square_poly3 \
  --require-max-budget-usage-below 1 \
  --require-source-replay \
  --execution-command scripts/run_structural_extension.sh \
  --source-protocol-manifest \
    results/thesis_grade_protocol/direct_tabular_autotune_v1/full_structural_poly3_inputmodel_floor18_keys3/summary/structural_protocol.json \
  --extra-artifact \
    split_summary=results/thesis_grade_protocol/structural_extension_splits_v1/summary.json \
  --extra-artifact \
    static_plan_summary=results/thesis_grade_protocol/structural_extension_v1/static_plans/summary.json \
  --extra-artifact \
    static_plans=results/thesis_grade_protocol/structural_extension_v1/static_plans/plans.csv

python3 scripts/freeze_direct_locked_audit_evidence.py \
  --output-root docs/evidence/structural_extension_v1 \
  --verify
```

The freezer verifies the exact model set and every audit's normalized
sample-specific error budget before writing the checksum manifest.

## Interpretation

The extension tests whether direct synthesis scales from the primary N13
graphs to a deeper N14 graph with ten Q primes. It addresses the immediate
reviewer objection that the primary evaluation only varies datasets around
two shallow graph families. CNN-lite and alternative packing remain separate
future extensions.
