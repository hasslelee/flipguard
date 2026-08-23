# V18 Comparison Extension Final Report

Status: `V18 COMPARISON EXTENSION COMPLETE — OFFLINE REPLAY SUFFICIENT`

## Binding

- Scientific execution source: `cefc44b0d7e351db2a34886dd758a2d31a3e4c12`
- Aggregation/tooling source: `86b0403208abbc741a65934358a5dea4a66e4d88`
- V17 matrix: 204/204 terminal
- V17 primary cases: 68/68
- V17 formal latency: 68/68
- V18 protocol SHA-256: `4adf230d43d6120cd805f51e970d1dfcd452c229ae7d8a03ea85c1adc971db44`
- New encrypted candidate evaluations: 0

## RQ-A: Does the decision-stability gate matter?

Yes at the configuration-selection stage. Gate removal selected 68/68 first
candidates. Twenty cases had at least one selection-input decision flip and 21
had a reserve-policy violation. The full method changed 21 literals and selected
a SAFE configuration in all 68 cases. Separate-input data exist for 47 gate-off
literals and show no failures; the other 21 are explicitly `NOT_EVALUATED`.

## RQ-B: What does stability cost?

The full method spent 21 additional encrypted candidate evaluations. Across the
21 changed literals, median deltas were LogN +0, Q-chain +28 bits, P-chain +0
bits, and scale +4 bits. The median candidate-stage total-latency delta for the
changed literals was 0.616136 ms. That value is diagnostic: no formal paired
gate-off inference arm exists, so V18 does not claim a formal inference-latency
cost for the gate.

## RQ-C: Is bounded adjustment necessary?

The first candidate was acceptable in 47/68 cases. The other 21 required one
recorded adjustment; all 21 then selected successfully and all 68 full-method
configurations passed separate-input evaluation. There were no primary repair
failures. This is bounded empirical success, not a theorem that adjustment
always succeeds.

## RQ-D: How close is selection to the finite reference?

The direct path used 89 encrypted candidate evaluations; the finite reference
used 537. The avoided offline reference burden is 83.426443%. Across 66 cases
with both selection timing boundaries, sum(finite wall-clock)/sum(direct
wall-clock) was 12.201707; the case-level ratio median was 12.398599 with IQR
7.465864. These are reference-validation burdens, not practical tuner speedups.

False `NO_SAFE` was 0. SAFE-rank median, IQR, p90, and maximum were 1, 0, 1,
and 3. Formal latency regret `(direct-fastest acceptable)/fastest acceptable`
had median -0.000153236, IQR 0.001825805, p90 0.001426190, and maximum
0.002309669. The 16-cluster finite/direct total-latency ratio was 1.000540931,
95% CI [0.999967475, 1.001121781], so the data support near-reference quality,
not superiority.

## Traditional-objective diagnostics

The fastest execution-valid candidate was unstable in 18/68 cases. The minimum
maximum-absolute-error candidate was stable in all 68, but minimum RMS was not
uniformly available under one definition. Across case-wise Pareto frontiers, 28
candidates were unstable. This directly motivates checking the decision output,
without pretending that the diagnostic is a named external system.

## External scope

Eligibility is 1 exact, 1 output-comparable, 2 numerical-only, and 7
related-work-only systems/guides. HEIR is exact only on the frozen shared
polynomial; its common-executor latency remains blocked due to eight flips in
the paired direct arm. EVA is decision-output comparable but native-runtime
latency stays separate. HECATE/ELASM are numerical-only. No external system was
reimplemented or selectively sampled.

## Negative and incomplete evidence

- Gate-off candidate-specific separate-input outcome: 47 observed, 21 not evaluated.
- Formal gate-off inference-latency arm: not measured.
- All-scope controlled-ablation separate-input rejection: one preserved V17 case.
- External all-system speed ranking: blocked.
- Global optimum and future-input safety: not claimed.

## Final claim change

V18 strengthens the causal internal comparison: decision stability changes the
selected configuration and has a measurable encrypted-evaluation/configuration
cost. It narrows external claims to compatibility-qualified subsets. V17 remains
the scientific source; V18 is a read-only comparison overlay.
