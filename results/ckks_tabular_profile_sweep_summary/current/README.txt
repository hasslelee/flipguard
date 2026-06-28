FlipGuard repeated tabular profile sweep summary

Experiment scale:
- total requested runs: 660
- successful runs: 630
- failed runs: 30
- profile candidates: 220
- strict safe candidates: 150
- workloads with selected fastest safe profile: 10/10

Interpretation:
This experiment evaluates multiple CKKS profiles and two evaluation paths across all tabular dataset-model combinations. A candidate is treated as strictly safe only when every repeated run completes successfully and preserves plaintext accuracy with zero decision flips and zero score error violations. The selected profile for each workload is the fastest strict safe candidate by mean total latency.
