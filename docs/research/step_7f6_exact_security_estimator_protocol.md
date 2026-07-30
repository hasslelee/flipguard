# Step 7F.6 Exact-Modulus Security Estimator Protocol

Status: predeclared security sensitivity. This protocol does not modify
Security Policy V2, candidate admission, candidate identity, or CKKS execution
semantics.

## Purpose

Security Policy V2 currently admits candidates with the published
HomomorphicEncryption.org Table 5.2 caps and exports exact Lattigo Q/P primes.
This stage executes the lattice estimator on those exact modulus products.
It is a sensitivity and reproducibility check, not a retrospective policy
selection procedure.

## Fixed Inputs

- source: `lattice_estimator_inputs_v2.json` from the frozen formal Security
  V2 attestation pack;
- source rows: 14;
- unique `(LogN, Q primes, P primes, Xs, Xe)` identities: 9;
- objects per identity: ciphertext Q and evaluation-key QP;
- total estimator objects per model: 18;
- target: 128 classical bits;
- sample model: `m=oo`;
- cost model: `RC.BDGL16`;
- attacks: primal uSVP, primal BDD, and dual hybrid.

The exact integer modulus is the product of the exported Lattigo primes. No
rounded `2^logQ` or `2^logQP` substitute is used.

## Estimator Models

Two immutable jobs are executed:

1. `GUIDELINE_PINNED_REPLAY` at lattice-estimator commit
   `8f1ff7e20a4d3391e3badff1d76825314db225bc`, which is the submodule commit in
   the published guideline toolkit;
2. `CURRENT_ESTIMATOR_SENSITIVITY` at commit
   `3e48ef421ec256afddb3e7d2249a77eab6e9ba12`.

The second job is sensitivity only and cannot change Security Policy V2.
Both jobs use SageMath 10.6 in the pinned amd64 container image
`sha256:60dfb09e8d1399e127a0d7b62b45eef1044574bae397df51bb6ba38df5498879`.

## Distribution Binding

- Lattigo `ring.Ternary{P:2/3}` is represented as
  `ND.Uniform(-1, 1)`, an exact per-coefficient ternary distribution.
- Lattigo `ring.DiscreteGaussian{Sigma:3.2, Bound:19.2}` is represented as
  `ND.DiscreteGaussian(3.2)`.

The error sigma matches, but the estimator does not model Lattigo's explicit
truncation bound. Therefore this stage must not claim an exactly identical
error distribution or a formal proof of implementation security.

## Fail-Closed Interpretation

Each object is classified as:

- `PASS_ESTIMATOR_MODEL`: all three attacks ran and the minimum estimated cost
  is at least 128 bits;
- `FAIL_ESTIMATOR_MODEL`: a completed attack estimates less than 128 bits;
- `INCOMPLETE_ATTACK_COVERAGE`: one or more attacks failed without a
  sub-128 result.

Any sub-128 result is preserved as falsification evidence. An incomplete
attack does not become a PASS. Neither result changes the frozen Security V2
candidate set during this stage.

The workflow preserves the exact source commit, estimator commit, container
identity, raw per-attack results, and SHA-256 index. A separate local verifier
recomputes all 18 exact modulus identities without requiring Sage.

`paper_claim_allowed=false`.
