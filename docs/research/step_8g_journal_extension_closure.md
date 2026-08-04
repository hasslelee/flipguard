# Step 8g: Journal Extension Closure and Experiment Hierarchy

## Reviewer concern

The controlled 5-by-2 primary study is intentionally narrow, while the
multiclass extension introduces different units, a deeper graph, and a
candidate-specific security analysis. Mixing these results into one flat count
would obscure both the strength and the boundary of the evidence.

## Literature precedent

Compiler and configuration-selection work commonly combines controlled
workloads with recognizable application graphs, but correctness and performance
units must remain explicit. FlipGuard therefore retains its repeated-partition
primary study as the controlled causal comparison, uses MNIST MLP-100 and
LeNet-5-small as a standard multiclass generalization tier, and keeps the
polynomial, image-operator, CNN-lite, training-seed, and NO_SAFE studies as
additional robustness evidence. No tier is treated as a collection of
independent samples merely because it contains multiple encrypted records.

## Implementation requirement

The final evidence and journal manuscript use three fixed tiers:

1. **Controlled Primary:** five real tabular datasets, two binary graph
   families, five deterministic repeated partitions, 50 workload-partition
   instances, 700 formal Security-V2 catalog candidates, 70 direct trials,
   no-retuning audit, and paired latency. Seed 0 remains descriptive and seeds
   1-4 remain confirmatory.
2. **Standard Multiclass Generalization:** one frozen MNIST test artifact,
   MLP-100 and FHE-compatible square-activation LeNet-5-small, 500 validation
   plus 500 locked-audit images per model, three fresh keys, the argmax
   decision contract, natural top-two-gap activation, and the focused MLP
   paired amendment.
3. **Additional Robustness:** 25 `mlp_square_poly3` instances; Sobel 400+400,
   Harris 200+200, and CNN-lite 250+250 observations; nine independently
   trained model instances; and the predeclared NO_SAFE controls.

The standard-model security statement is qualified: exact Q/P literals pass
Security Policy V2 and two declared classical estimator adapters, but exact
equivalence to Lattigo's truncated error distribution and quantum security are
not claimed. The MLP paired amendment establishes catalog/S29 latency evidence,
but the S32/S29 interval contains one and therefore supports a literal effect,
not a latency-superiority effect. LeNet's seven frozen profiles are
`PLAN_UNSUPPORTED_WITHIN_FROZEN_CATALOG`; no LeNet catalog latency claim is
made.

## Falsification test

The hierarchy verifier fails if any tier count changes, if 50 repeated
partitions are described as independent workloads, if the 14 multiclass
catalog profiles are confused with six encrypted executable candidates, if a
LeNet catalog latency claim is admitted, if the S29/S32 interval is described
as a speedup, or if the estimator caveats are omitted. Existing RC2, V3, V10,
thesis, and journal-extension predecessor packs must retain their byte digests.
