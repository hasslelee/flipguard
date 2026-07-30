# Step 7g11: EVA Native Runtime Control

Status: `PREDECLARED_BEFORE_NATIVE_ENCRYPTED_EXECUTION`

## Question

Does the exact pinned EVA v1.0.1 compiler output satisfy FlipGuard's finite
decision-integrity contract when executed on EVA's own Microsoft SEAL v3.6.4
backend, and does a SAFE validation result survive a no-retuning locked
audit?

## Fixed Artifact

- EVA commit: `4cd3254c9c51340ae30c451495ce5378135758c0`.
- SEAL commit: `0b058d99b7f18a00e5ebb2b80caee593804b0500`.
- Compiled DOT:
  `sha256:3c5ec469e692ea17dd413180c6c37c5042ef7bb5bfedd968d19447242fd72bca`.
- Exact literal: `LogN=14`, three 60-bit Q primes, one 60-bit P prime,
  input scale 20.
- Workload: seed-0 development Iris binary `linear_poly3`.
- Validation: 14 fixed rows.
- Locked audit: 16 disjoint fixed rows.

The compiler configuration, model, formula, input scale, concrete prime
literal, and row assignments are unchanged from the frozen compiler replay.
The two ignored historical `results/` files are copied byte-for-byte into the
versioned experiment directory for clean-runner replay; both SHA-256 digests
remain unchanged.

## Decision Protocol

- Threshold: `0.5`.
- Primary alpha: `0.5`.
- Margin floor: `0.001`.
- Fresh native SEAL key contexts: 3 for validation.
- Candidate trials: 1.
- SAFE requires zero execution failures, decision flips, and strict
  alpha-times-margin budget violations.
- Locked audit runs only after SAFE validation and uses three new native SEAL
  key contexts.
- Each row is encrypted and evaluated independently in the scalar EVA vector.
- No synthesis, repair, parameter adjustment, row removal, or retuning is
  allowed.

An individual runtime failure is recorded and remaining rows continue.
REJECTED or FAILED validation is preserved and prevents locked audit. A
negative audit is preserved without candidate changes.

## Security Boundary

The exact Q/P literal passes the frozen Security V2 static cap with 190 bits
of table headroom. Native SEAL uses its pinned uniform-ternary secret and
centered-binomial error distribution, not Lattigo's exact Xs/Xe objects. The
pinned EVA backend also constructs the SEAL context with
`sec_level_type::none`; the external runtime does not independently enforce
the cap. Therefore this control records FlipGuard's static cap result but does
not claim exact runtime-distribution identity or promote a new formal
Security V2 runtime claim.

## Claim Boundary

This single development workload can support native execution and, only if
both gates pass, a scoped native EVA/SEAL decision certificate. It cannot
support cross-runtime numerical equivalence, broad compiler generalization,
external search-autotuner integration, or a paper claim.

`paper_claim_allowed=false`.

## Pre-Execution Recovery

GitHub Actions run `30561535356` stopped at static preflight because the
contract initially referenced ignored local `results/` paths. It performed
zero encrypted executions and zero candidate trials. The recovery packages
byte-identical input snapshots and changes no row, split, candidate, policy,
or execution semantics.

Run `30562143758` then stopped after compilation and before key generation
because a repeated EVA compilation produced a different raw DOT digest. It
also performed zero encrypted executions and zero candidate trials. The
recovery preserves expected and observed raw DOT digests separately and adds
an ID/order-independent canonical DAG digest. Native execution is allowed
only when the canonical node labels, attributes, operand edges, and topology
match the frozen graph; a semantic mismatch remains an integrity block.
