# Step 7G.13: Cross-Runtime Evidence Boundary

Status: static post-execution audit. This document adds no encrypted
execution, changes no policy or candidate, and does not authorize paper work.
`paper_claim_allowed=false`.

## Question

Do the source-replayed Lattigo and native EVA/SEAL results establish numerical
equivalence across runtimes?

## Existing Bindings

The studies bind the same seed-0 Iris `linear_poly3` model, threshold `0.5`,
primary alpha `0.5`, margin floor `0.001`, and semantic polynomial:

```text
z = bias + sum_i(weight_i * x_i)
score = 0.5 + 0.197*z - 0.004*z^3
```

The original and repeated native scale-20 compiler graphs have semantic digest
`sha256:403b0d9e5ee96ff9484c0ad598ac73355c03e907d23996b8a882e2d28fd12513`
and the same `N=16384`, Q bits `[60,60,60]`, and P bits `[60]`. Both native
fresh-key validations are `REJECTED`. The schedule-bound Lattigo scale-20
smoke is also `REJECTED`.

That outcome direction does not establish equivalence.

## Why Equivalence Is Not Evaluated

- The corrected Lattigo schedule replay covers one development smoke row.
- Each native validation arm covers 14 rows under three fresh key contexts.
- The native scale-30 locked audit covers 16 different rows under three more
  key contexts.
- The Lattigo and SEAL runs use different secret and error distributions.
- No row-wise paired error ledger exists for the same scale-20 rows and keys.
- No Lattigo schedule-bound execution exists for the selected native scale-30
  literal.
- Runtime-specific security is not transferable: the native SEAL experiment
  uses `sec_level_type::none`, while Security V2 is bound to the declared
  Lattigo distributions.

The scale-20 rejection agreement is descriptive outcome concordance only. A
single shared rejection label cannot show equality of ciphertext error,
normalized budget usage, failure probability, or decision behavior.

## Current Claim States

- `native_eva_seal_runtime_execution=SUPPORTED`
- `native_eva_seal_decision_certification=PARTIALLY_SUPPORTED`
- `native_eva_seal_locked_audit=PARTIALLY_SUPPORTED`
- `external_precision_sensitivity=PARTIALLY_SUPPORTED`
- `cross_runtime_numerical_equivalence=NOT_EVALUATED`
- `runtime_specific_native_security=NOT_EVALUATED`
- `general_external_autotuner_integration=NOT_EVALUATED`
- `paper_claim_allowed=false`

The positive native claim is limited to one post-rejection seed-0 development
sensitivity with three fixed scale arms. The scale-30 first-SAFE literal
passes 42 validation and 48 untouched locked-audit observations with zero
flips, violations, repair, or retuning.

## Required Future Paired Protocol

A future cross-runtime study must be predeclared before execution and bind:

1. one literal Q/P modulus sequence and one semantic operation schedule;
2. identical model, plaintext rows, row order, threshold, alpha, and margin;
3. matched validation and locked-audit roles;
4. a fixed key-repeat count and runtime-specific key provenance;
5. per-row plaintext score, CKKS score, absolute error, normalized usage,
   decision, flip, violation, and failure status;
6. a pairing key independent of runtime serialization;
7. an equivalence or non-inferiority tolerance chosen before outcomes;
8. separate security analyses for the concrete Lattigo and SEAL secret/error
   distributions.

The study must report paired differences and failures, not merely compare
aggregate labels. A mismatch lowers the equivalence claim and must not trigger
policy retuning.

## Bound Evidence

- `docs/evidence/eva_schedule_bound_adapter_replay_v1`
- `docs/evidence/eva_native_runtime_replay_v1`
- `docs/evidence/eva_native_scale_sensitivity_v1`

These immutable packs remain the source of execution facts. This note only
states what those facts can and cannot support.
