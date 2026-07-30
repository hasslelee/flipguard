# Step 7G.5: Actual External-Provider Evidence Boundary

Status: static research-direction audit after the Orion and AWS HIT adapter
experiments. This document changes no policy, candidate, or frozen evidence.
`paper_claim_allowed=false`.

## Question

What can FlipGuard claim after replacing synthetic provider labels with
source-pinned public configuration artifacts?

## Evidence

### Provider-format interoperability

The provider-candidate gate executes manual, bounded-catalog, direct, and
synthetic external-format literals through the same Security V2,
certify-or-reject, and locked-replay path. All four development arms select
and audit successfully. This supports provider-class plumbing, but it is not
evidence that a third-party tool produced the external-format fixture.

Evidence:
`docs/evidence/provider_candidate_gate_interoperability_v1`.

### Orion public configurations

Three source-pinned Orion configurations were parsed with their checked-in
backend semantics. None could be imported losslessly into the frozen Lattigo
v6/Security V2 runtime:

- the MLP and LoLa configurations use incompatible ring, secret, error, and
  backend semantics and fail Security V2;
- the ResNet configuration also requests an unsupported `LogN=16`;
- no candidate request or encrypted execution was emitted.

This is a successful fail-closed interoperability audit, not a successful
external-candidate certification and not an assessment of Orion quality.

Evidence: `docs/evidence/orion_external_adapter_audit_v1`.

### AWS HIT source replay

The public AWS Homomorphic Implementor's Toolkit formula produced one
predeclared CKKS parameter literal from declared circuit depth, slots, scale,
and key-switch-prime count. Exact ordered Lattigo v2 Q/P primes were imported
into Lattigo v6 without regeneration or reordering. The literal passed the
frozen Security V2 Q/QP gate with 188 bits of table-cap headroom.

On seed 0 `iris_binary/linear_poly3`, the one permitted encrypted trial:

- completed 3/3 fresh-key executions;
- produced zero decision flips;
- exceeded the predeclared alpha-times-margin budget in 6/42 sample-key
  observations;
- was therefore `REJECTED`, and locked audit was correctly not run.

This supports lossless cross-version literal import and demonstrates that
cryptographic admission plus executable ciphertext arithmetic does not imply
decision-integrity admission. It does not support HIT quality, general
external-autotuner integration, or a SAFE external-candidate claim.

Evidence:

- `docs/evidence/hit_external_adapter_replay_v1`;
- `docs/evidence/hit_external_adapter_rejection_analysis_v1`.

## Novelty Consequence

Automatic program lowering, scale management, error-latency optimization,
parameter selection, bootstrapping placement, packing, and repair are prior
art. The current defensible FlipGuard contribution is the downstream,
provider-neutral finite decision gate:

1. preserve exact candidate lineage and literal identity;
2. reject security- or runtime-incompatible candidates before execution;
3. certify or reject executable candidates in threshold-decision space;
4. abstain when no candidate is SAFE;
5. replay only a selected literal on a disjoint locked audit without
   retuning.

Actual public-provider evidence currently spans one fail-closed static import
and one lossless but decision-REJECTED encrypted import. Therefore:

- `provider_class_interoperability=PARTIALLY_SUPPORTED`;
- `lossless_external_literal_import=SUPPORTED`;
- `encrypted_external_candidate_certification=BLOCKED`;
- `general_external_autotuner_integration=NOT_EVALUATED`;
- `external_autotuner_quality=NOT_EVALUATED`;
- `paper_claim_allowed=false`.

## Next Falsifiable Milestone

Before any new encrypted external-provider run, predeclare:

- the public tool, source commit, and whether it is a selector, compiler, or
  search autotuner;
- the exact graph/workload mapping and literal translation;
- Q/P, secret, error, ring, packing, and backend semantics;
- Security V2 admission;
- a one-candidate or otherwise fixed trial budget;
- a disjoint locked audit that runs only after SAFE validation.

Success requires a source-derived candidate to be SAFE and then pass
byte-identical locked replay. A blocked import, `REJECTED`, `FAILED`, or
`NO_SAFE` outcome remains valid evidence and must not trigger policy retuning.
