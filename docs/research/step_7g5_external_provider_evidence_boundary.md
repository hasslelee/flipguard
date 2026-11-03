# Step 7G.5: Actual External-Provider Evidence Boundary

Status: static research-direction audit after the Orion, AWS HIT, and
Microsoft EVA adapter experiments. This document changes no policy,
candidate, or frozen evidence.
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

### Microsoft EVA compiler replay

Pinned EVA v1.0.1 source and SEAL v3.6.4 were replayed to compile the
predeclared seed-0 Iris `linear_poly3` program. The compiler emitted the exact
ordered three-prime Q chain and one-prime P chain, its compiled DOT graph, and
a Security-V2-admitted `LogN=14`, `LogQP=240` literal. The default FlipGuard
lowering could not consume the compiler's three-prime schedule because it
required seven Q primes, so the first parameter-only adapter stopped before
encrypted execution.

A second immutable contract bound the same exact literal to the compiler's
actual scale/level schedule rather than regenerating parameters. The first
one-row development smoke exposed and preserved a cubic-sign implementation
bug. After the minimum semantic correction, a clean-source replay completed
under frozen Lattigo v6.2.0 Xs/Xe but was decision-REJECTED:

- Security V2 admission: PASS;
- decision flips: 0;
- budget violations: 1;
- maximum normalized budget usage: `9.410894423253259`;
- repair, synthesis, and retuning calls: 0.

The predeclared smoke gate therefore prevented the 14-row formal validation
and locked audit. This supports source-replayed compiler output and
schedule-bound fail-closed import. It does not support an encrypted SAFE EVA
candidate, native EVA/SEAL runtime equivalence, or general external-compiler
interoperability.

Evidence:

- `docs/evidence/eva_external_adapter_replay_v1`;
- `docs/evidence/eva_schedule_bound_adapter_replay_v1`.

The same scale-20 compiler output was then executed on pinned EVA's native
SEAL v3.6.4 backend over the 14-row development validation artifact and three
fresh key contexts. All 42 encrypted observations executed, but the candidate
was decision-REJECTED:

- decision flips: 11;
- alpha-times-margin violations: 36;
- maximum absolute error: `1.784804773973152`;
- maximum normalized budget usage: `58.5611405658713`;
- locked audit: not run;
- synthesis, repair, and retuning: 0.

The three key repeats had 14, 13, and 9 violations, respectively, so the
result is not localized to one failed execution. Native EVA plaintext replay
matched the bound CSV scores within `4.21e-13`, separating graph/input
identity from encrypted numerical error. This supports native EVA/SEAL
execution of the bound compiler output, but not native decision
certification. SEAL's pinned secret/error semantics differ from Lattigo's
Xs/Xe, and the experiment is not a paired cross-runtime equivalence test.

Evidence: `docs/evidence/eva_native_runtime_replay_v1`.

After preserving that rejection, a separate predeclared seed-0 development
sensitivity compiled and executed three fixed EVA input-scale arms in the
order 20, 30, and 40. The output range, graph, model, validation rows, audit
rows, compiler flags, threshold, alpha, and margin floor remained fixed.
Every arm ran three fresh-key validation contexts:

- scale 20: `REJECTED`, with 21 flips and 42 violations in 42 observations;
- scale 30: `SAFE`, with zero flips and violations in 42 observations;
- scale 40: `SAFE`, with zero flips and violations in 42 observations.

The predeclared first-SAFE rule selected scale 30. Its byte-identical compiled
literal then passed 48/48 untouched locked-audit observations across three new
key contexts with zero flips, zero violations, and zero retuning. The study
used three candidate trials, nine validation key runs, and three audit key
runs; it invoked neither FlipGuard synthesis nor repair.

This is a successful, scoped native external-compiler candidate
certification. It is post-rejection development evidence on one model and one
runtime, not an EVA autotuner evaluation or a confirmatory generalization
study. Because EVA can change both the schedule and modulus chain in response
to input scale, the arm comparison is an association between the declared
compiler input and the observed decision outcome, not an isolated causal
effect of scale. Native SEAL used `sec_level_type::none`, and its secret/error
distribution differs from frozen Lattigo Security V2; runtime-specific
security remains not evaluated.

Evidence: `docs/evidence/eva_native_scale_sensitivity_v1`.

The Lattigo schedule-bound replay and the native SEAL studies are not a
matched cross-runtime experiment. The Lattigo replay covers one smoke row,
whereas native validation covers 14 rows and three fresh keys. The shared
scale-20 rejection direction is therefore not numerical-equivalence evidence,
and no scale-30 Lattigo replay exists. The exact boundary and a future paired
test contract are recorded in
`docs/research/step_7g13_cross_runtime_evidence_boundary.md`.

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

Actual public-provider evidence currently spans Orion fail-closed imports,
one lossless but decision-REJECTED HIT literal, a scale-20 source-compiled EVA
literal rejected in both scoped native studies, and a scale-30 EVA literal
that passed native validation and untouched locked audit in one post-rejection
development sensitivity. Therefore:

- `provider_class_interoperability=PARTIALLY_SUPPORTED`;
- `lossless_external_literal_import=SUPPORTED`;
- `actual_eva_compiler_parameter_output=SUPPORTED`;
- `schedule_bound_external_candidate_import=SUPPORTED`;
- `general_external_compiler_interoperability=PARTIALLY_SUPPORTED`;
- `encrypted_external_candidate_certification=PARTIALLY_SUPPORTED`;
- `locked_audit_external_schedule_replay=PARTIALLY_SUPPORTED`;
- `native_eva_seal_runtime_execution=SUPPORTED`;
- `native_eva_seal_decision_certification=PARTIALLY_SUPPORTED`;
- `native_eva_seal_locked_audit=PARTIALLY_SUPPORTED`;
- `external_precision_sensitivity=PARTIALLY_SUPPORTED`;
- `cross_runtime_numerical_equivalence=NOT_EVALUATED`;
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
