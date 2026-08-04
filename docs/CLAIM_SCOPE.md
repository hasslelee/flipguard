# FlipGuard Claim Scope

FlipGuard's public claims are governed by machine-readable core and multiclass claim registries. This page is a concise human-facing map; the registries remain authoritative.

## What FlipGuard Supports

Within declared finite inputs, supported adapters, frozen policies, and recorded fresh-key runs, the evidence supports the following scoped statements:

- FlipGuard directly synthesizes CKKS literals from supported graph facts and a decision-integrity contract.
- Bounded numerical and level repairs can recover candidates within the predeclared four-trial limit.
- A candidate is admitted, rejected, failed, or followed by `NO_SAFE` under explicit fail-closed semantics.
- Selected literals are replayed without retuning on disjoint locked-audit artifacts.
- The controlled primary study used 70 direct trials instead of 700 Security-V2-admitted bounded-catalog candidates, a 90% formal reduction.
- Confirmatory seeds 1–4 produced 40 of 40 no-retuning locked-audit passes.
- One-host paired evidence reports a 3.140660 bounded-catalog/direct total-latency ratio with clustered 95% CI [2.342334, 4.215313].
- The multiclass argmax proposition and uniform top-two-gap corollary hold under their stated strict error bounds.
- MLP-100 and LeNet-5-small each had zero argmax flips on declared 500-image validation and 500-image audit sets.
- The natural top-two-gap contract changed the MLP-100 literal from S32 to S29.
- Security claims are qualified by explicit Policy V2 and estimator models.

## What FlipGuard Does Not Claim

The project does not claim:

- to be the first CKKS autotuner, application-aware configuration tool, direct synthesizer, or repair-based selector;
- universal or arbitrary computation-graph support;
- arbitrary packed-CNN or full LeNet compilation;
- global configuration optimality or a global oracle;
- distribution-wide decision preservation;
- a complete instantiated analytical CKKS certificate;
- production readiness or universal hardware speedup;
- universal 128-bit security for arbitrary runtime distributions;
- exact cross-runtime numerical or security equivalence;
- general external-autotuner integration.

## Empirical and Analytical Assurance

The inequalities in [Decision-Integrity Contracts](DECISION_CONTRACTS.md) are mathematical sufficient conditions. FlipGuard's measured error budgets, however, come from finite encrypted execution evidence. Consequently:

- a `SAFE` candidate passed the declared empirical gate;
- a locked-audit PASS reports the same literal on a disjoint finite artifact;
- neither result proves future or distribution-wide behavior;
- the reserve policy can reject an observation even when no decision flip is observed.

The primary `rho=0.5` margin-utilization cap is predeclared policy, not an optimal theorem constant. Natural primary alpha sensitivity did not change the initial literal in the tested range because minimum synthesis floors dominated.

## Security Qualification

Security-V2 admission checks exact `Q` and `QP` material under the policy's declared published-table interpretation. Lattice-estimator evidence is a separate sensitivity layer. Runtime error distributions, truncation details, and estimator mappings are documented rather than treated as exact universal equivalents.

Public wording should prefer:

> admitted under Security Policy V2 and qualified by the declared estimator model

It should not use:

> universally 128-bit secure

## Packing and Runtime Scope

The controlled primary and several extensions use scalar-replicated packing and explicit graph adapters. The multiclass extension exercises wider affine layers, multiple logits, convolution, average pooling, and square activations within its declared FHE-compatible adapters. It does not establish a general packed tensor compiler.

Recorded paired latency applies to one measured host and frozen arm identities. It is evidence about those paired runs, not a deployment benchmark across CPUs, clouds, libraries, or runtimes.

## Important Negative Results

- The structural polynomial audit had 24 PASS outcomes and one reserve-policy rejection without a decision flip.
- MLP-100 S29 and S32 did not show admitted S29-over-S32 latency superiority.
- All seven frozen catalog profiles were `PLAN_UNSUPPORTED` for LeNet-5-small depth; this is not `NO_SAFE` or global infeasibility.
- Cross-runtime numerical equivalence remains not evaluated.
- The analytical-certificate claim remains blocked.

## Authoritative Registries

- [Core paper claim admission](evidence/paper_claim_admission_v1/claims.json)
- [Multiclass claim admission](evidence/journal_multiclass_claim_admission_v2/claims.json)
- [Core allowed sentences](evidence/paper_claim_admission_v1/allowed_sentences.md)
- [Multiclass allowed sentences](evidence/journal_multiclass_claim_admission_v2/allowed_sentences.md)

When this summary and a registry differ, fail closed and use the registry only after verifying its manifest and dependency digests.
