# Step 7D.1 Independent Training-Seed Extension Protocol

Status: `PREDECLARED_NOT_EVALUATED` on 2026-07-30. This protocol is frozen
before extension artifacts, trained models, encrypted selections, or locked
audits are generated. It is a research protocol, not a manuscript result.

## Research Question

The primary 50-instance experiment repeats deterministic partitions of fixed
held-out artifacts. It does not establish robustness to independently trained
models or fresh train/validation/audit assignments.

This extension asks whether byte-identical Direct Policy V2 can synthesize and
validate configurations for newly trained square-activation MLPs across three
declared datasets and three independent training/data-split seeds. It runs
direct selection and no-retuning locked audit only; the bounded catalog is not
repeated.

## Frozen Population

Datasets:

- `iris_binary`: Iris setosa versus versicolor;
- `wdbc`: Wisconsin Diagnostic Breast Cancer;
- `digits_binary`: scikit-learn digits, even versus odd.

Exact source payloads are the dataset files distributed with scikit-learn
`1.9.0`. The exporter records their paths, SHA-256 digests, scikit-learn
version, NumPy version, row counts, feature names, and label mapping before
training. Source arrays are also serialized into the frozen extension input
pack so verification does not depend only on library API behavior.

Training/data-split seeds:

```text
1729, 2718, 3141
```

The evaluated matrix contains:

```text
3 datasets x 3 independently trained models = 9 training-seed instances
```

These nine rows are not described as nine independent datasets. Fresh-key
repeats are cryptographic repeats and are never treated as statistical
samples.

## Frozen Role Assignment

Rows are ranked independently within each label by:

```text
SHA256(
  "flipguard_independent_training_seed_v1" || NUL ||
  seed || NUL || dataset_id || NUL || label || NUL || source_row_id
)
```

For a label containing `n` rows:

```text
evaluation_rows_per_role = min(floor(0.20 * n), 48)
```

The first ranked block is configuration validation, the second block is
locked audit, and all remaining rows are model training. Every role contains
both labels. Role assignment occurs before standardization, feature
selection, model initialization, or training.

Rows may receive different roles under different declared seeds. Within one
training-seed instance, training, configuration validation, and locked audit
are disjoint. Results are summarized by dataset and training seed rather than
treating all rows as independent inferential samples.

## Frozen Model Pipeline

Each instance trains only `mlp_square_linear_score`:

```text
selected standardized inputs
-> affine layer with four hidden units
-> elementwise square
-> affine output z
-> score = 0.5 + 0.197*z
-> decision = score >= 0.5
```

All preprocessing is fitted on the training role only:

- zero-variance-safe standardization;
- at most eight features;
- feature ranking by absolute train-only Pearson correlation with the binary
  label, with source feature index as the deterministic tie-breaker;
- selected feature indices sorted into source order before serialization.

The square MLP uses full-batch Adam:

| Item | Frozen value |
|---|---:|
| Hidden units | 4 |
| Epochs | 3000 |
| Learning rate | 0.01 |
| Beta 1 / Beta 2 | 0.9 / 0.999 |
| Epsilon | 1e-8 |
| L2 penalty | 1e-4 |
| Initialization | NumPy PCG64 with the declared seed |

After training, only the output layer and output bias are multiplied by a
positive factor so the largest absolute training logit is one. Validation and
audit scores do not affect this scaling. The locked audit cannot affect the
model, feature selection, preprocessing, candidate, or policy.

## Frozen Input And Replay Contract

For every dataset/seed, the artifact builder emits:

- source snapshot and source digest;
- model artifact and model digest;
- raw selected-feature configuration-validation CSV;
- raw selected-feature locked-audit CSV;
- split manifest with ordered row IDs and role digests;
- training metrics and margin summaries;
- canonical policy manifest and SHA-256 sums.

A deterministic verifier reloads the declared source payloads, reconstructs
all role assignments, preprocessing, training, models, and CSVs, and compares
the rebuilt tree byte-for-byte. It rejects overlap, missing labels, source
drift, audit-derived model state, score mismatch, or digest mismatch.

## Frozen CKKS Protocol

Direct Policy V2 remains byte-identical:

```text
sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603
```

Security Policy V2 remains byte-identical:

```text
sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055
```

For each of the nine instances:

1. Materialize configuration validation from the raw selected-feature CSV and
   the seed-specific model.
2. Synthesize from the supported `mlp_square_linear_score` graph and decision
   contract without model-specific lookup.
3. Use primary alpha `0.5`, margin floor `0.001`, frozen `+4` numerical repair,
   frozen `+1` level repair, maximum two added levels, and maximum four
   encrypted trials.
4. Evaluate every validation row under three fresh keys.
5. Stop at the first SAFE literal or return NO_SAFE.
6. If selected, replay the byte-identical literal over the disjoint locked
   audit under three new keys without synthesis or repair.
7. Preserve SELECTED, REJECTED, FAILED, NO_SAFE, flip, and violation outcomes.

Security V2 admission is required before encrypted execution. An inadmissible
literal is an integrity block and cannot enter the formal extension result.

## Frozen Accounting

The extension records separately:

- trained models;
- candidate trials;
- repairs and repair causes;
- key runs;
- encrypted sample evaluations;
- SELECTED and NO_SAFE outcomes;
- validation flips and violations;
- locked-audit PASS, REJECTED, FAILED, flips, and violations;
- retuning count;
- candidate identity and Q/QP admission.

No trial-reduction denominator is claimed because this extension does not
execute a seed-specific bounded catalog.

## Claim Boundary

Success on all nine instances supports robustness across the declared
training/data-split seeds for three `mlp_square_linear_score` pipelines. A
negative result remains valid evidence and lowers the claim without triggering
policy changes.

This extension does not establish:

- universal training-seed robustness;
- independent-dataset inference from nine rows;
- arbitrary model or graph support;
- packed inference;
- CNN generalization;
- a global optimum;
- model accuracy improvements from FlipGuard.

`paper_claim_allowed` remains false until the combined research artifact and
claim gate are reviewed separately.
