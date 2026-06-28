FlipGuard tabular operation analysis

This file summarizes logical encrypted inference operation counts for each exported tabular workload.

Important scope:
- The counts are logical operation counts, not measured hardware memory usage.
- Rotations are zero because the current evaluator encrypts one replicated scalar per ciphertext instead of using SIMD-packed vector slots.
- The analysis is useful for explaining model complexity and ciphertext operation structure.
- Actual memory and communication measurement should be added separately if needed.
