FlipGuard final research result summary

Validation:
- status: pass

Boundary stress test:
- total runs: 10010
- stable runs: 9900
- stable decision flips: 0
- output accuracy violations: 0

Repeated speed benchmark:
- selected safe path: default+rescale_aware
- selected total speedup: 1.2515x
- selected evaluation-only speedup: 1.1159x

WDBC public dataset:
- test samples: 171
- plaintext accuracy: 0.9473684211
- encrypted accuracy: 0.9473684211
- decision flips: 0
- score error violations: 0

Tabular multi-dataset suite:
- workloads: 8
- datasets: 4
- model families: 2
- safe pass workloads: 8
- safe decision flips: 0
- safe score error violations: 0
- rejected unsafe workloads: 8
- unsafe decision flips: 1153
- unsafe score error violations: 2306
- unsafe total-latency speedup range: 1.5236x to 2.2417x

Interpretation:
The safe path preserved plaintext decisions and satisfied the output accuracy guard across all evaluated workloads. The faster unsafe path reduced latency, but it caused decision flips and output accuracy violations, so it was rejected by the safety guard.
