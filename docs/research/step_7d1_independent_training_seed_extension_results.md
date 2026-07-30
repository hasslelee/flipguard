# Step 7D.1 Independent Training-Seed Extension Results

Status: `SUPPORTED` within the predeclared three-dataset, three-training-seed
`mlp_square_linear_score` scope on 2026-07-30. Training/model-seed
generalization remains `PARTIALLY_SUPPORTED`, and
`paper_claim_allowed=false`.

The immutable protocol is
`docs/research/step_7d1_independent_training_seed_extension_protocol.md`.
It was committed before source extraction, training, input materialization,
encrypted selection, or locked audit. This result document does not modify
the protocol or either frozen policy.

## Frozen Population

The extension independently assigns train, configuration-validation, and
locked-audit roles and trains a new square-activation MLP for each of:

```text
iris_binary, wdbc, digits_binary
x training/data-split seeds 1729, 2718, 3141
= 9 trained-model instances
```

All nine model SHA-256 digests are distinct. Within each instance, the three
roles are disjoint and preprocessing, feature selection, model training, and
output scaling use training rows only. Deterministic source replay reconstructs
the nine models, split manifests, and evaluation CSVs byte-for-byte.

| Dataset | Train rows | Validation rows | Audit rows |
|---|---:|---:|---:|
| `iris_binary` | 60 | 20 | 20 |
| `wdbc` | 389 | 90 | 90 |
| `digits_binary` | 1605 | 96 | 96 |

## Frozen Identity

| Artifact | Identity |
|---|---|
| Protocol commit | `dc0c57e` |
| Input builder commit | `eb6e53fc6638a0e84e07261112967a22d9bd7615` |
| Frozen input commit | `d87ea9e5d1c1e865713b5ff16fddca03404dfc5d` |
| Execution commit | `f3cfd7f4527cc9ceb66c1b36d9926512102e7435` |
| Execution-source digest | `sha256:5e7e0be1e69918b14445c97d3c05b4afe6aef874c6c928ed1d15c15e7ef38fb2` |
| Input policy | `sha256:e9353654e5ec899fc91ce70e8dd501905b95973bcb8493cc1d27f3ffc77af1cb` |
| Input summary | `sha256:04947a11ce1ab319860d6bd8e247d6d803169e8c6e3f3312b6cf259394247f5d` |
| Direct Policy V2 | `sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603` |
| Security Policy V2 | `sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055` |
| Run manifest | `sha256:c00e4cc65089fd3c0944e58fb98e65aa4bf3025ef302125f1863428b743d7408` |

Static preflight and execution used identical CKKS literal parameters and
Security V2 facts in all nine instances. Their candidate-ID strings differ
because the ID binds the prepared-contract path. This is a representation
difference, not a selected-literal or selection/audit identity change.

## Configuration Validation

| Property | Result |
|---|---:|
| Trained-model instances | 9 |
| `SELECTED` / `NO_SAFE` | 9 / 0 |
| Candidate trials / repairs | 9 / 0 |
| Fresh key runs | 27 |
| Encrypted sample evaluations | 1,854 |
| Certifiable / ambiguous rows | 575 / 43 |
| Flips / violations | 0 / 0 |
| Maximum absolute error | 0.000390695 |
| Maximum normalized budget usage | 0.196783 |
| Security V2 admitted / inadmissible | 9 / 0 |
| Minimum security headroom | 61 bits |

Every instance selected the first synthesized candidate. No model-specific
lookup, policy change, catalog execution, or repair was used.

## Locked Audit

| Property | Result |
|---|---:|
| `LOCKED_AUDIT_PASS` / `REJECTED` / `FAILED` | 9 / 0 / 0 |
| Fresh key runs | 27 |
| Encrypted sample evaluations | 1,854 |
| Certifiable / ambiguous rows | 587 / 31 |
| Flips / violations | 0 / 0 |
| Maximum absolute error | 0.000676062 |
| Maximum normalized budget usage | 0.338680 |
| Retuning | 0 |

Each audit replays its selected candidate byte-identically on the disjoint
audit rows under three fresh keys. The audit never calls synthesis or repair.

## Recovery Disclosure

Four recoverable implementation issues did not alter encrypted semantics:

1. The runner initially expected a nonexistent top-level evaluation-count
   field after the first completed selection. The result was preserved and
   resumed without rerunning selection.
2. A default run-root name changed after an orchestration-only commit. Resume
   used the explicit immutable `run_f3cfd7f` root before further execution.
3. Frozen split manifests encoded row IDs as JSON numbers while the Go audit
   schema expected strings. Run-local compatibility views changed only the
   representation; ordered values, paths, CSV digests, and memberships were
   verified identical. Failed parser attempts did not reach CKKS execution.
4. Nine first-attempt parser logs were overwritten when successful resume
   reused their paths. Eighteen parser-failure logs remain. No encrypted
   result or frozen evidence pack was overwritten. This weakens raw recovery
   log completeness and is retained as an artifact-assurance limitation.

Encrypted selection reruns and semantic split changes are both zero.

## Evidence And Claim Boundary

Frozen evidence:

```text
docs/evidence/independent_training_seed_extension_v1/
manifest sha256:adf0c9d9a265bcc8e5f695ba68df06675ffd7f67034a0aa59fc5e901ad04ac40
```

The verifier checks execution-source closure, binaries, input source replay,
all model and split digests, Q/QP admission, selection/audit literal identity,
accounting, recovery views, and a deterministic byte-for-byte pack rebuild.

The result supports direct synthesis and no-retuning replay for nine newly
trained models in the declared scope. It does not establish universal
training-seed robustness, nine independent datasets, arbitrary model support,
packed inference, a bounded-catalog optimum, or model-accuracy improvement.

