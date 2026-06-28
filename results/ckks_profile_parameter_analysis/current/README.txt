FlipGuard CKKS profile parameter and safety analysis

This analysis summarizes CKKS profile metadata and observed safety outcomes across the repeated tabular profile sweep.

Key observations:
- profile with the largest number of strict safe candidates: deep_chain_8_scale45 (16)
- profile with the lowest mean latency among completed candidates: short_chain_3 (101.5965241038 ms)
- short-chain profiles can reduce latency but may increase decision flips, output error violations, or level-exhaustion failures.
- deep-chain profiles provide more capacity, but they are not automatically fastest.

Scope:
- Security level is not independently estimated in this script.
- The table reports parameter-shape metadata used by FlipGuard experiments.
- A formal security estimate should be added separately with an LWE/RLWE estimator or library-provided security metadata.
