# V18 Paper Facts Locked

Status: `V18 PAPER FACTS LOCKED — READY FOR MANUSCRIPT INTEGRATION`

## Immutable binding

- V18 package payload SHA-256: `884d979087b62a1f4e2ca066902f4deb603589dbff6fd5349c57bead5539aded`
- V18 manifest SHA-256: `a86427207d5525a83036f0a99e3bf6888f9e21b0219a489af3d1ac8fb1fa7e50`
- New encrypted candidate evaluations: `0`

## 1. Gate-off cross table

| Gate-off state | Cases |
|---|---:|
| No flip, no violation | 47 |
| Flip only | 0 |
| Violation only | 1 |
| Flip and violation | 20 |
| Union: flip or violation | 21 |

The exact case IDs are recorded in `PAPER_FACTS_V18_LOCKED.json` and
`V18_GATE_EFFECT_TABLE.csv`. The violation-only case is
`primary|mnist_binary01|packed_cnn_lite_binary01_v17|v17_p6_packed_cnn_lite`.

## 2. Gate-off versus full cost

Gate-off used 68 candidate evaluations; the full method used 89. Forty-seven
cases needed no additional evaluation, 21 recovered with exactly one additional
evaluation, and none required two or more. An exact paired gate-off/full
selection wall-clock cannot be reconstructed because V17 did not record a
stage-complete wall-clock boundary after the rejected first trial. It is locked
as `NOT_RECONSTRUCTABLE_FROM_V17_STAGE_BOUNDARIES`, not estimated.

For context, the separately measured finite-reference/full selection wall-clock
ratio over 66 cases had median `12.398599026`, IQR
`7.465864139`, and p90 `16.756551324`. Its direction is
finite-reference divided by full method; it is not a gate-off/full statistic.

For the 21 changed cases, the observed selected-candidate mean-total-latency
ratio full/gate-off had median `1.004507757`, IQR
`0.004738687`, p90 `1.011218199`, and maximum
`1.011741766`. These are selection-stage observations, not formal
paired inference latency.

## 3. Configuration change

All 21 changes increased scale by 4 bits. Q-prime count increased in 0 cases,
so scale +4 and Q-prime +1 co-occurred in 0 cases. LogN and Q-chain length
changed in 0 cases. The Q-chain retained its prime count while total declared Q
bits increased by 28 in 20 `linear_poly3` cases and 24 in the packed-CNN case.
Every before/after literal is in `V18_STABILITY_COST_TABLE.csv` and the JSON.

## 4. Gate-off separate-input outcome

Candidate-specific separate-input results are observed for 47 cases: 47 PASS,
0 REJECTED, and 0 FAILED. The remaining 21 are `NOT_EVALUATED` because their
initial literals failed the selection gate and V17 advanced only selected
literals to that stage. `NOT_EVALUATED` is not counted as failure.

## 5. Traditional objectives

The fastest executable candidate had flips and violations in 18/68 cases; no
flip-only or violation-only fastest case occurred. It differed from the proposed
selection in 23 cases. The minimum-error candidate had no flip or violation in
68/68 cases but differed from the proposed selection in all 68. The 279
case-level error-latency Pareto candidates included 28 unstable candidates in 20
cases. The finite fastest acceptable candidate differed from the proposed
candidate in 5 cases.

Representative small-error violation: in
`primary|digits_binary|linear_poly3|outer_fold_2_training_seed_0`, candidate `synth_repair_scale_2_rescale_N14_Q7_S28_bbf9e9983d20` had
maximum absolute error `0.0010583344403514161` and zero
flips but 18 reserve violations. For sample 239/key repeat 3, absolute error
`0.0010361468174261423` exceeded rho x margin budget
`0.00071487406552511734` (usage
`1.449411676`).

## 6. External comparison

HEIR's exact shared-polynomial Lattigo arm uses LogN 14, Q
`[36028797017456641, 35184372744193, 35184371138561, 35184372121601]`, P `[1152921504607338497, 1152921504608747521]`, scale 45,
and Security-V2 state PASS. Its locked audit has 500 inputs x 3 contexts, zero
flips, zero violations, and maximum absolute error
`5.0791018169071833e-08`. Common-Lattigo
diagnostic mean/median/p95 total latency is
`49.056611172` /
`47.303517500` /
`59.866485000` ms. The paired
speed claim remains blocked because the paired direct arm was unstable.

EVA S20 validation produced 133 flip events over 1,500 observations, affecting
114/500 unique inputs, and maximum absolute error 1.2114988677117884. S30 and
S40 each had zero flips and violations on the 500-input x 3-context locked
audit; audit maximum errors were 0.0020735645861611196 and
3.0338053744749516e-06. EVA latency remains native-SEAL-only. HECATE lacks an
exact V17 decision output, while ELASM's 34/36 completed CoreLab plans expose
numerical error and native latency but no matching threshold/argmax contract.

The seven related-work-only entries are CHET (no verified exact executable
mapping), DaCapo (bootstrapping objective not applicable), Orion (model/packing
identity mismatch), FHE-Agent (no verified official runnable artifact), Lattigo
(backend library), Microsoft SEAL (manual example), and OpenFHE (context API
guide).

## 7. Finite reference

- Direct / finite evaluations: 89 / 537
- Offline finite-reference burden avoided: 83.426443%
- False NO_SAFE: 0
- Formal latency regret median/IQR/p90/max:
  `-0.000153236247` / `0.001825804968` /
  `0.001426189816` / `0.002309669255`
- Formal direct-minus-finite median-total difference in ms, median/IQR/p90/max:
  `-0.027911000` / `0.392658250` /
  `0.323917150` / `3.775770000`
- Dataset-model cluster finite/direct total-latency ratio:
  `1.000540931233`, 95% CI
  `[0.999967474766, 1.001121781209]`

The confidence interval includes 1. The admitted conclusion is near-reference
selection quality, not latency superiority, practical exhaustive-search
speedup, or global optimality.
