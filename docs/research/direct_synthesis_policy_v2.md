# Direct Synthesis Policy V2

Policy ID: `flipguard_direct_synthesis_policy_v2`.
Algorithm ID: `flipguard_direct_synthesis_v2`.

The canonical artifact is `direct_synthesis_policy_v2.json`; its
`policy_sha256` binds the immutable semantic policy. The artifact separately
binds the source commit that generated it.

## Primary Contract

- graph contract schema: 2;
- supported formulas: `linear_poly3`, `mlp_square_linear_score`,
  `mlp_square_poly3`;
- scale trace: `lattigo_v6_rescale_scale_trace_v1`;
- primary alpha: 0.5;
- primary margin floor: 0.001;
- scale/Q-prime floor: 18 bits;
- scale guard: 3 bits;
- first-prime guard: 2 bits;
- P-prime floor: 30 bits;
- numerical repair: add 4 scale bits;
- level repair: append one Q prime;
- maximum additional levels: 2;
- static NTT retry: increment scale one bit only for prime-generation
  exhaustion;
- maximum encrypted trials: 4;
- security policy:
  `security_guidelines_cic2025_table5_2_ternary_128_v2`;
- packing: scalar-replicated per feature ciphertext;
- required slots: must not exceed N/2;
- stop at first SAFE;
- return NO_SAFE when trials or monotone repairs are exhausted.

The error classifier maps level/rescale failures to level repair, successful
encrypted trials with flips or error-budget violations to numerical repair,
and other execution failures to FAILED.

## Predeclared Ablations

| ID | Candidate synthesis | Repair | Decision gate |
|---|---|---:|---:|
| `graph_only_fixed_tolerance` | graph plus fixed output tolerance 0.001 | yes | yes |
| `one_shot_direct` | graph plus decision contract | no; maximum trial 1 | yes |
| `full_flipguard` | graph plus decision contract | bounded | yes |
| `latency_only_no_certification` | fastest executable admitted catalog candidate | no | no |

Every ablation reports candidate trials, key runs, encrypted sample
evaluations, SELECTED/NO_SAFE, validation and audit flips/violations, selected
inference latency, repair count, and repair cause. The primary natural-data
study must not overstate a decision-contract effect when the minimum floor
dominates synthesis. Near-boundary or finite-domain controls are reported
separately.

## Freeze Rule

The policy must be committed and pushed before structural holdout execution.
Results from `mlp_square_poly3`, image operators, or CNN holdouts may not
change this policy. A changed semantic field creates a new policy ID and
digest; it cannot silently mutate V2.
