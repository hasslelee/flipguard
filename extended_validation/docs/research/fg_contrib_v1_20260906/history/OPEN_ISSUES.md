# Current open issues

1. Numerical FP16-reference tolerances are representative engineering choices, not proof of application adequacy or reproduction of a named paper.
2. Shared finite candidates inherit margin-based synthesis; they isolate acceptance conditions, not an entirely decision-agnostic selector.
3. Three initializations form one dataset/architecture group and one VM; no risk/equivalence guarantee.
4. Full10,000 batching uses3fresh keys per batch, not3global keys across all batches. Report missing work and boundary outcomes separately.
5. Official EVA native and Lattigo share real polynomial semantics and128bit targets; identical distributions/schedules/packing and causal latency attribution are not established.
6. FHE-Agent v1 design says fixed activations while its case-study language differs; actual official implementation remains unverified.
7. Frozen PDF p7 wording about63additional models versus5depth conditions remains a proposed correction only.
8. Preserve all incidents, negative results and historical protocols. No automatic new model/dataset/queue experiment.
9. First-expansion Spambase linear numerical selection S32/Q8/N14 differs from direct S24/Q7/N13, but its held-out/paired comparison is not yet evaluated. One bounded fixed-configuration comparison is a possible next review item, not an automatically scheduled run; old inputs are already exposed.
