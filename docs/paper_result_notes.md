# FlipGuard Paper Result Notes

## Research Claim

FlipGuard is an accuracy-constrained CKKS inference profile selection method.
It does not select the fastest encrypted inference profile directly. Instead, it
filters candidate profiles using decision stability and output accuracy guards,
and then selects the lowest-latency profile among the safe candidates.

## Controlled Boundary Stress Test

Result tag:

- `boundary_1001x10`

Configuration:

- target z range: [-0.05, 0.05]
- points: 1,001
- repetitions: 10
- total CKKS runs: 10,010

Results:

- stable runs: 9,900
- ambiguous runs: 110
- total decision flips: 4
- stable decision flips: 0
- ambiguous decision flips: 4
- stable margin-safety violations: 0
- output accuracy violations: 0
- max y error: 0.0000000002

Interpretation:

Stable-region decision flips were not observed. All observed flips occurred only
inside the explicitly ambiguous boundary region.

## Repeated Speed Benchmark

Result tag:

- `speed_repetition_summary`

Configuration:

- 5 independent repetitions
- 30 measurement runs per repetition

Baseline path:

- profile: `default`
- evaluation path: `baseline_non_rescale`
- mean eval-only latency: 52.7847 ms ± 3.4348
- mean total latency: 147.0721 ms ± 8.3772

Selected safe path:

- profile: `default`
- evaluation path: `rescale_aware`
- selected in: 5 / 5 repetitions
- mean eval-only latency: 47.3964 ms ± 4.0001
- mean total latency: 117.7348 ms ± 9.4823
- mean eval-only speedup: 1.1159x ± 0.0515
- mean total speedup: 1.2515x ± 0.0485
- best observed eval-only speedup: 1.1999x
- best observed total speedup: 1.3327x

Unsafe raw-speed reference:

- profile: `short_chain_3`
- evaluation path: `baseline_non_rescale`
- mean eval-only speedup: 2.3403x
- mean total speedup: 1.9040x
- max decision flips: 30
- max y error: 5.0197e-01
- decision: rejected

## WDBC Public Dataset Experiment

Dataset:

- WDBC Breast Cancer
- test samples: 171
- selected features:
  - worst texture
  - worst area
  - worst concave points

Plaintext model:

- model: 3-feature logistic regression
- raw logistic accuracy: 0.947368
- raw logistic F1: 0.958525
- raw logistic AUC: 0.987296
- polynomial decision match rate: 1.000000

CKKS encrypted inference:

- result tag: `wdbc_default_rescale_aware`
- profile: `default`
- evaluation path: `rescale_aware`
- evaluated rows: 171
- plain accuracy: 0.9473684211
- CKKS accuracy: 0.9473684211
- decision match rate: 1.0000000000
- decision flips: 0
- score error violations: 0
- max y error: 0.0000002078
- mean eval-only latency: 42.9856001520 ms
- mean total latency: 111.3772588772 ms

## WDBC Profile Sweep

Result tag:

- `wdbc_profile_sweep`

Selected fastest safe profile:

- profile: `default`
- evaluation path: `rescale_aware`
- CKKS accuracy: 0.9473684211
- decision flips: 0
- score error violations: 0
- mean eval-only latency: 42.9856001520 ms
- mean total latency: 111.3772588772 ms
- eval-only speedup vs baseline: 1.1668859751x
- total speedup vs baseline: 1.3057241508x

Unsafe raw-speed reference:

- profile: `short_chain_3`
- evaluation path: `baseline_non_rescale`
- CKKS accuracy: 0.3742690058
- decision flips: 110 / 171
- score error violations: 171 / 171
- max y error: 0.5961896640
- eval-only raw speedup: 2.4676391495x
- total raw speedup: 1.9083288944x
- decision: rejected

## Paper Tables

Generated result snippets:

- `results/final_research_summary/current/paper_results.tex`

Recommended paper tables:

1. Boundary stress test and WDBC correctness summary
2. Repeated speed benchmark
3. WDBC profile sweep
4. Unsafe profile rejection analysis

## Main Paper Message

The fastest raw CKKS profile is not necessarily safe. Reduced-chain profiles can
produce attractive latency improvements but may cause severe decision instability
and output error. FlipGuard uses decision stability and output accuracy guards to
reject unsafe profiles and selects the fastest remaining safe profile. In both a
controlled boundary stress test and the WDBC public dataset experiment, the
selected rescale-aware default profile preserved decisions and output accuracy
while reducing end-to-end latency.
