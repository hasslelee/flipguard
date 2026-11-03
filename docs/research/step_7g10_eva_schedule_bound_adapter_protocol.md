# Step 7g10: EVA Schedule-Bound External Adapter Protocol

Status: PREDECLARED BEFORE ENCRYPTED EXECUTION

This development control follows the parameter-only EVA replay. That replay
was Security V2 admitted but correctly stopped because the three-prime EVA
chain did not satisfy FlipGuard's seven-prime default lowering contract.

The compiled EVA program is a different lowering of the same plaintext graph.
It uses 60-bit plaintext scales and exactly two `Rescale(60)` operations. This
protocol therefore binds both the concrete parameter literal and the compiled
program digest to candidate identity. It does not relax the Direct Policy V2
or Security Policy V2.

## Frozen Inputs

- EVA v1.0.1 commit: `4cd3254c9c51340ae30c451495ce5378135758c0`
- SEAL v3.6.4 commit: `0b058d99b7f18a00e5ebb2b80caee593804b0500`
- Compiled DOT SHA-256:
  `3c5ec469e692ea17dd413180c6c37c5042ef7bb5bfedd968d19447242fd72bca`
- Compiler output SHA-256:
  `605cc94bb1df230f9d58b1cbbeb66a26d11b6ae44ed4ad46dfca0925cd711dea`
- Workload: seed-0 Iris binary `linear_poly3`
- Validation rows: 14
- Locked audit rows: 16
- Exact candidate: LogN 14, Q3 x 60-bit, P1 x 60-bit, scale 20

## Bound Schedule

1. Encrypt four scalar-replicated inputs at scale 20 and highest level.
2. Encode weights at scale 20 and form the linear score at scale 40.
3. Encode the model bias at scale 40.
4. Square the linear score, consume one exact Q prime, then relinearize.
5. Mod-switch the original linear score to the same level.
6. Form the cubic branch at scale 80.
7. Form the affine branch at scale 60 and lift it to scale 80.
8. Subtract the cubic branch, consume one exact Q prime, then relinearize.
9. Require terminal level 0, degree 1, and scale approximately 20.

The adapter accepts no arbitrary schedule. The schedule ID, DOT digest,
compiler-output digest, model digest, formula, exact Q/P order, scale values,
packing scope, and workload identity must all match the pinned contract.

## Execution And Falsification

- Run one diagnostic row only after a clean source commit is pushed.
- If the diagnostic passes, run exactly one validation candidate trial over
  all 14 rows and three fresh keys.
- Run the 16-row locked audit only when validation is SAFE.
- The locked audit reuses the same schedule ID and candidate literal.
- No synthesis, repair, prime padding, scale change, or retuning is allowed.
- REJECTED, FAILED, or audit-negative outcomes are preserved.
- Native EVA/SEAL runtime equivalence is not claimed because encrypted replay
  uses the frozen Lattigo v6.2.0 Xs/Xe runtime.

This is development evidence for schedule-bound interoperability. It is not a
confirmatory population result, and `paper_claim_allowed` remains false.
