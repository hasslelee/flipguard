# Step 7F.2 Conditional Analytical V2 Protocol

Status: static research implementation protocol. No encrypted execution is
authorized or required by this step. Direct Policy V2 and Security Policy V2
remain byte-identical. `paper_claim_allowed=false`.

## Question

Can FlipGuard make its conditional arithmetic statement replayable and
fail-closed without misrepresenting empirical CKKS errors or standard
deviations as absolute end-to-end bounds?

## Claims Kept Separate

1. **Conditional propagation lemma.** If every input, encoding, and CKKS
   operation residual is covered by an explicit deterministic or
   probabilistic absolute bound, outward-rounded interval arithmetic produces
   an end-to-end score-error upper bound for the bound operation graph.
2. **Instantiated CKKS analytical certificate.** The current selected
   candidates have all required Lattigo v6.2.0 primitive residual bounds and
   may therefore use the conditional result as a certificate.

The first claim can be supported by implementation and property tests. The
second remains blocked until the primitive bounds are derived and replayed.
Supporting the first never implies the second.

## V2 Requirements

- Preserve the frozen V1 analytical files byte-identically because they are
  part of prior encrypted-execution source closures.
- Place new research-only code outside those closures.
- Bind the exact ordered `AnalyticalOperationGraph`.
- Bind model scalar values by canonical IEEE-754 binary64 bits.
- Require one ordered `NodeAssumption` for every graph node.
- Require a SHA-256 source digest for every primitive assumption, including
  assumptions whose numerical bound is zero.
- Distinguish:
  - `DETERMINISTIC_ABSOLUTE_BOUND`;
  - `PROBABILISTIC_ABSOLUTE_BOUND`;
  - `EMPIRICAL_DIAGNOSTIC`;
  - `STANDARD_DEVIATION_DIAGNOSTIC`.
- Combine probabilistic assumptions with an outward-rounded union bound.
- Refuse proof promotion if any source is diagnostic or if the combined
  failure probability is not below one.
- Round every positive upper-bound addition and multiplication toward
  positive infinity.
- Reject NaN, infinity, negative bounds, source mismatch, graph mismatch,
  unused model scalars, missing model scalars, node reorder, and result
  mutation.
- Recompute all node envelopes during artifact validation.

## Static Primary Inventory

The readiness audit consumes, without modifying:

- 10 seed-0 development selections from
  `direct_locked_audit_seed0_development_v1`;
- 40 seeds-1-4 confirmatory selections from
  `direct_locked_audit_final_source_v1`.

For each of the 50 selected candidates it records:

- workload and model type;
- candidate ID, path, and literal signature;
- graph-contract support;
- primitive-bound completeness;
- proof eligibility;
- observed-versus-bound audit status;
- exact block reasons.

## Falsification

- A property-test perturbation exceeding the V2 envelope blocks the
  conditional propagation claim.
- A diagnostic source that can produce `AnalyticalBoundProof` blocks the
  implementation.
- A stored node-envelope mutation that passes replay blocks the artifact.
- A primary candidate marked proof-eligible without complete primitive
  derivations blocks the instantiated analytical claim.
- Empirical maxima, quantiles, fresh-key variance, or Lattigo noise standard
  deviation must never fill a required absolute-bound field.

## Claim State Rule

- Conditional propagation lemma: `SUPPORTED` only after full tests and
  deterministic readiness artifact verification pass.
- Instantiated CKKS analytical certificate: `BLOCKED` until every required
  primitive category has a scoped absolute derivation and an
  observed-versus-bound audit is complete.
