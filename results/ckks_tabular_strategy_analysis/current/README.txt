FlipGuard strategy and ablation analysis

This analysis compares profile-selection strategies using the repeated tabular profile sweep result.

Main result:
- proposed safe selections: 8/8
- proposed unsafe selections: 0
- proposed total decision flips: 0
- proposed total score error violations: 0
- proposed mean speedup versus fixed default safe path: 1.1120x

Fastest-only baseline:
- fastest-only safe selections: 0/8
- fastest-only unsafe selections: 8
- fastest-only total decision flips: 1153
- fastest-only total score error violations: 2306

Interpretation:
The proposed strategy chooses the fastest candidate satisfying both output error and decision stability guards. The fastest-only baseline can reduce latency but may select unsafe candidates. The guard-only variants show whether each individual condition is sufficient or whether both conditions are needed.
