FlipGuard repeated tabular profile sweep summary

Experiment scale:
- total requested runs: 528
- successful runs: 504
- failed runs: 24
- profile candidates: 176
- strict safe candidates: 120
- workloads with selected fastest safe profile: 8/8

Interpretation:
This experiment evaluates multiple CKKS profiles and two evaluation paths across all tabular dataset-model combinations. A candidate is treated as strictly safe only when every repeated run completes successfully and preserves plaintext accuracy with zero decision flips and zero score error violations. The selected profile for each workload is the fastest strict safe candidate by mean total latency.
