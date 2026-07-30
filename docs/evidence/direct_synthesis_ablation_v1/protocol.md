# Step 7E.1 Direct-Synthesis Ablation Protocol

Status: `PREDECLARED_NOT_EVALUATED` on 2026-07-30. This protocol is frozen
before graph-only plans, graph-only encrypted execution, or ablation summaries
are generated. It is a development ablation, not a manuscript result.

## Research Question

The primary experiment establishes that FlipGuard can directly synthesize,
validate, repair, and audit a CKKS literal with far fewer trials than the
Security V2 bounded catalog. It does not by itself isolate which observed
benefits come from:

- the threshold decision contract in candidate synthesis;
- bounded adaptive repair after an encrypted rejection;
- the decision-integrity certification gate rather than latency alone.

This ablation separates those factors without changing Direct Policy V2,
Security Policy V2, the primary result, or any locked-audit data.

## Frozen Population

Only partition seed 0 is used because its official role is
development/ablation. The population is:

```text
5 datasets x 2 supported primary model graphs
= 10 dataset-model development workloads
```

Datasets are `banknote`, `digits_binary`, `iris_binary`, `mnist_pool16`, and
`wdbc`. Models are `linear_poly3` and `mlp_square_linear_score`.

The exact model, source, prepared configuration-validation, split-manifest,
and locked-audit bytes are those frozen in:

```text
docs/evidence/direct_locked_audit_seed0_development_v1/
```

No seed 1-4 result is used to choose an arm, tolerance, or interpretation.
The ten rows are not treated as ten independent datasets or inferential
samples.

## Frozen Arms

### A. Graph-Only Fixed-Tolerance Synthesis

- policy ablation ID: `graph_only_fixed_tolerance`;
- candidate proposal uses graph structure and fixed output-error tolerance
  `0.001`;
- candidate proposal does not use the observed decision-margin budget;
- encrypted validation and the ordinary decision-integrity gate remain;
- frozen `+4` numerical and `+1 Q-prime` level repairs remain;
- maximum encrypted trials remains 4;
- first SAFE stops; exhausted repairs return NO_SAFE.

This arm changes only `SynthesisBudgetMode` to
`graph_fixed_tolerance` and `FixedOutputErrorBudget` to `0.001`, exactly as
predeclared inside Direct Policy V2. All other synthesis and certification
constants remain byte-identical.

Each selected literal is replayed on the frozen seed-0 locked audit without
synthesis, repair, or retuning.

### B. One-Shot Direct Synthesis

- policy ablation ID: `one_shot_direct`;
- candidate proposal and decision contract are the full FlipGuard proposal;
- only the first already executed encrypted trial is considered;
- adaptive repair is disabled;
- a SAFE first trial is SELECTED;
- a REJECTED or FAILED first trial becomes NO_SAFE for this arm.

This arm is derived from the first raw trial in the frozen full-FlipGuard
selection ledger. It does not execute a candidate again. When its first
candidate is also the full arm's selected literal, the existing byte-identical
locked audit is reused. NO_SAFE rows have no selected literal and therefore
record locked-audit metrics as `NOT_APPLICABLE`, never as zero.

### C. Full FlipGuard

- policy ablation ID: `full_flipguard`;
- graph plus threshold decision contract;
- encrypted validation;
- bounded failure-aware repair;
- decision-integrity gate;
- first-SAFE and NO_SAFE rules from Direct Policy V2.

The existing seed-0 clean-source selection and no-retuning locked-audit
ledgers are reused without encrypted rerun.

### D. Latency-Only / No-Certification

- policy ablation ID: `latency_only_no_certification`;
- candidate domain is the 14 Security-V2-admitted profile/path identities per
  workload;
- choose the fastest execution-OK candidate by the existing validation mean
  total latency;
- do not filter selection by SAFE/REJECTED status;
- preserve the chosen candidate's observed decision certificate as a
  diagnostic after selection.

The existing Security-V2 catalog ledger is reused. Inadmissible profiles are
excluded before selection. Because this arm intentionally has no certified
selected literal contract and no catalog locked-audit execution was
predeclared, locked-audit metrics are `NOT_EVALUATED`, not zero. It cannot
support a decision-preserving latency claim.

## Frozen Policy And Identity

Direct Policy V2:

```text
sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603
```

Security Policy V2:

```text
sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055
```

Primary alpha is `0.5`; primary margin floor is `0.001`; validation and audit
key repeats are `3`; maximum encrypted trials are `4`. The Security V2
admitted catalog contains `7 profiles x 2 paths x 10 seed-0 workloads = 140`
candidate executions.

Before any new encrypted execution, the ablation runner must bind:

- clean source commit and origin;
- execution-critical source closure and binary SHA-256;
- Direct/Security policy IDs and digests;
- all model, source, prepared validation, split, and audit digests;
- full-arm selection ledger digest;
- Security-V2 catalog certificate digest;
- exact arm definitions and an ablation-contract digest.

Any source, split, policy, security admission, or identity mismatch is an
`INTEGRITY_BLOCK`.

## Execution And Reuse Rules

Only Arm A may create new encrypted results. It runs the ten workloads
sequentially with no concurrent CKKS process. A scientific REJECTED, FAILED,
NO_SAFE, or audit violation is preserved and does not modify the arm.

Arms B-D are deterministic views over frozen evidence:

- B reads only the first raw full-arm trial;
- C reads the complete frozen full-arm selection and audit;
- D reads only Security-V2-admitted catalog candidates at alpha `0.5`.

No existing evidence pack is overwritten. The ablation uses a new run root
and a new evidence-pack path. A transient process failure may be retried up to
three times with identical binary, input, and policy; every attempt is logged.

## Frozen Metrics

For every arm and workload:

- candidate trials;
- repairs and repair cause;
- fresh key runs;
- encrypted sample evaluations;
- SELECTED / NO_SAFE;
- validation execution status;
- validation SAFE / REJECTED / FAILED;
- validation flips and violations;
- selected literal and Security V2 admission;
- locked-audit status;
- locked-audit flips and violations;
- locked-audit retuning count;
- mean validation latency when available.

Aggregate reporting includes:

- first-trial SAFE rate;
- rescue count: first trial non-SAFE but full arm SELECTED;
- graph-only versus full initial-literal identity;
- graph-only versus full selected-literal identity;
- graph-only versus full trials and repairs;
- latency-only selected SAFE / REJECTED / FAILED counts;
- decision-contract effect count;
- adaptive-repair effect count.

`NOT_APPLICABLE` and `NOT_EVALUATED` remain explicit and are never converted
to numeric zero.

## Frozen Interpretation

Adaptive repair is supported only when an already executed first candidate is
non-SAFE and the frozen monotone repair reaches SAFE. Decision-contract
candidate-synthesis effect is supported only when Arm A and Arm C propose
different literals or produce meaningfully different trial/outcome behavior.

If the natural seed-0 workloads show little or no decision-contract effect,
that negative result is reported. Existing predeclared finite-domain and
NO_SAFE controls may explain when a decision gate matters, but cannot be used
to alter this ablation.

Success does not establish a global optimum, arbitrary graph support,
universal autotuning, independent statistical replication, or an analytical
CKKS error bound. `paper_claim_allowed` remains false after the ablation.

