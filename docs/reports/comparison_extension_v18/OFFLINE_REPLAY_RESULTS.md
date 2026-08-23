# Offline Replay Results

## Frozen populations

The replay reconciled `131/131` selected case identities, including `68/68`
primary cases. The primary candidate ledger contains `89` direct
candidate evaluations and `537` finite-reference evaluations. It
reuses the `68/68` formal latency rows; no encrypted execution was started.

## Decision-stability gate effect

Removing only the decision gate selected `68/68`
primary cases. The selected first candidates contained
`20` case(s) with observed selection-input flips and
`21` case(s) with reserve-policy violations.
FlipGuard changed the literal in `21` cases and
spent `21` additional encrypted candidate
evaluations. Separate-input outcomes are available for
`47/68` gate-off selections; missing
candidate-specific held-out evaluations are reported as `NOT_EVALUATED`, not
imputed. A formal gate-off inference-latency arm was not measured.
Among changed literals, median LogN, Q-chain, P-chain, and scale deltas were
`0.0`,
`28.0` bits,
`0.0` bits, and
`4.0` bits, respectively.
The changed-literal candidate-stage median total-latency delta was
`0.616136` ms; it is
diagnostic and is not substituted for the unmeasured formal gate-off arm.

## Bounded adjustment

The initial candidate passed in `47` cases.
The remaining `21` required a recorded bounded adjustment;
`21` were selected by the full method and
`0` remained unresolved. This cost exactly
`21` additional candidate evaluations.

## Numerical objectives

Across `68` primary cases, the fastest execution-valid finite
candidate violated the decision gate in `18` cases. The candidate
with minimum maximum-absolute error violated it in `0` cases.
There were `28` unstable candidates on case-wise numerical
error/latency Pareto frontiers. These rows are diagnostics, not stand-ins for a
named external system.

## Finite reference

The direct method avoided `83.426443%` of
the encrypted candidate evaluations required by the declared finite reference.
Over the `66` cases with both timing boundaries, the ratio
of aggregate finite-reference selection wall-clock to aggregate direct selection
wall-clock was `12.201707`. This is an offline reference burden and not a
speedup over an existing tuner. The separate case-level ratio had median
`12.398599`
and IQR
`7.465864`;
the aggregate and case-level summaries are intentionally not conflated. False
`NO_SAFE` was `0`.

Formal latency regret is `(direct - fastest acceptable) / fastest acceptable`.
Its median was `-0.000153236`,
IQR `0.001825805`, p90
`0.001426190`, and maximum
`0.002309669` over 68
case-level paired rows.

The dataset-model-cluster geometric mean of finite/direct total latency was
`1.000540931` with deterministic cluster-bootstrap
95% CI `[0.999967475,
1.001121781]` across
`16` clusters. The interval includes 1;
the result supports near-reference selection quality, not latency superiority.

## Preexisting baselines

The frozen fixed default was not a runnable common comparator: 65 cases were
security-inadmissible, two multiclass cases were not reevaluated, and one packed
case was plan-unsupported. The preexisting latency-only candidate was SAFE in
51 cases, REJECTED in 15, and not evaluated in two. These are preserved as
preexisting V17 rows rather than synthesized after observing V18 outcomes.

## External boundary

One frozen HEIR shared-polynomial workload is portable-exact, one EVA workload
is output-comparable, and HECATE/ELASM contribute two numerical-only system
classes. Seven remaining systems or library guides are related-work-only. No
external runtime is folded into the V17 primary latency aggregate.
