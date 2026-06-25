FlipGuard tabular suite summary

Workloads:
- datasets: wdbc, iris_binary, digits_binary, banknote
- models: linear_poly3, mlp_square_linear_score
- total workloads: 8

Safe candidate:
- profile: default
- path: rescale_aware
- safe pass workloads: 8/8
- total safe decision flips: 0
- total safe score error violations: 0

Unsafe raw-speed candidate:
- profile: short_chain_3
- path: baseline_non_rescale
- rejected workloads: 8/8
- total unsafe decision flips: 1153
- total unsafe score error violations: 2306
- unsafe total-latency speedup range versus safe candidate: 1.5236x to 2.2417x

Interpretation:
The default rescale-aware path preserved plaintext decisions and satisfied the output accuracy guard across all evaluated tabular workloads. The short-chain baseline non-rescale path was faster, but it caused decision flips and score error violations across all evaluated workloads, so it is rejected by the safety guard.
