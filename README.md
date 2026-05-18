# FlipGuard

FlipGuard is a research prototype for decision-stability-aware precision scheduling in CKKS-based encrypted inference.

The goal is to allocate node-wise precision budgets so that threshold-based decisions remain stable under CKKS approximation errors.

## Current status

- Project initialization
- Plain simulation first
- CKKS backend later

## Initial target

The first experiment focuses on a small logistic-style polynomial inference example:

```text
z = 0.8*x1 - 0.5*x2 + 1.2*x3 - 0.3
y = 0.5 + 0.197*z - 0.004*z^3
T = 0.5
```

FlipGuard will compare fixed precision, uniform quantization, accuracy-only scheduling, and decision-stability-aware scheduling.