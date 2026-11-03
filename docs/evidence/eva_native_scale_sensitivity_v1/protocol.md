# Step 7g12: EVA Native Scale Sensitivity

Status: `PREDECLARED_DEVELOPMENT_SENSITIVITY_BEFORE_NEW_ENCRYPTED_EXECUTION`

## Question

The frozen EVA scale-20 candidate executed successfully but failed FlipGuard's
decision-integrity gate. This development-only study asks whether the
caller-declared input precision is associated with a different native
EVA/SEAL validation outcome when graph, model, rows, compiler configuration,
decision contract, and key-repeat protocol are fixed.

The original candidate remains frozen and `REJECTED`. This study neither
repairs it nor reuses a locked-audit result.

## Literature Basis

The EVA PLDI 2020 paper and pinned public implementation require the caller to
provide the CKKS input scale and output range before compilation. EVA then
inserts rescale, relinearization, and modulus-switch operations and returns a
compiled program, encryption parameters, and an encoding signature.

HECATE (CGO 2022) identifies scale management as a distinct compiler design
dimension. Accordingly, this protocol varies only caller-declared input scale
at the experiment boundary and records every compiler-generated schedule and
parameter object rather than assuming graph depth alone determines accuracy.

Primary sources:

- https://www.microsoft.com/en-us/research/publication/eva-an-encrypted-vector-arithmetic-language-and-compiler-for-efficient-homomorphic-computation/
- https://github.com/microsoft/EVA
- https://www3.cs.stonybrook.edu/~dongyoon/papers/CGO-22-HECATE.pdf

## Fixed Arms

All three validation arms run in the declared order:

1. input scale 20;
2. input scale 30;
3. input scale 40.

The output range remains one bit. EVA v1.0.1, SEAL v3.6.4, compiler flags,
Iris `linear_poly3` graph, seed-0 development rows, threshold `0.5`, alpha
`0.5`, and margin floor `0.001` remain fixed.

Each arm uses three fresh native SEAL key contexts and evaluates all 14
validation rows independently. Individual arm rejection or failure does not
stop the remaining predeclared arms.

## Selection And Audit

The selected literal is the smallest scale whose static Security V2 reference
gate passes and whose three-key validation is `SAFE`. Only that byte-identical
compiled program and parameter object may enter the disjoint 16-row locked
audit with three new key contexts.

If no validation arm is SAFE, the outcome is `NO_SAFE` and no audit runs. If
the selected audit is negative, the result is preserved without repair,
reselection, or another audit.

## Security Boundary

For each compiler output, Q and P bit sizes are recorded separately and both Q
and QP are checked against the frozen Security V2 cap before key generation.
Native SEAL uses a different error distribution from Lattigo and the EVA
backend constructs its context with `sec_level_type::none`. The check is
therefore a conservative admission reference, not a claim of exact runtime
distribution identity or independent SEAL security enforcement.

## Causal And Claim Boundary

This fixed matrix can establish an association between caller scale and the
joint compiler/runtime outcome. It cannot isolate scale from the schedule,
degree, and modulus chain that EVA may generate in response.

The study is post-rejection seed-0 development evidence. It cannot establish
confirmatory generalization, public-autotuner quality, cross-runtime numerical
equivalence, or a paper claim.

`paper_claim_allowed=false`.
