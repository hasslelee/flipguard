# Step 7G.7: HIT-Direct Matched-Workload Diagnostic

## Purpose

Use only frozen records to compare the FlipGuard direct literal and the
source-replayed AWS HIT literal evaluated on seed 0
`iris_binary/linear_poly3`.

This is an explanatory post-hoc analysis. It adds no encrypted execution,
does not alter either candidate, and does not modify Direct Policy V2 or
Security Policy V2.

## Identity Gate

The analysis proceeds only when both records bind:

- the same workload, dataset, model, and partition IDs;
- byte-identical raw validation source and model digests;
- the same graph facts;
- the same threshold, alpha, margin floor, sample count, and ambiguity count;
- protected margin and output-error budget within an absolute `1e-12`
  representation tolerance;
- the same frozen Direct and Security V2 policy digests.

The direct run binds a prepared full-precision artifact plus its raw source.
The HIT run binds the same raw source directly. The analysis therefore claims
raw-source and execution-semantic identity, not prepared-file byte identity.

## Outputs

For each arm:

- candidate identity and provider class;
- LogN, LogQ, LogP, LogQP, scale, and rescale levels;
- Security V2 admission and headroom;
- trials and fresh-key runs;
- SAFE/REJECTED, flips, violations, maximum error, and maximum budget usage;
- mean, median, and p95 total latency;
- locked-audit disposition and retuning count.

Derived HIT/direct ratios are descriptive only.

## Prohibited Inference

The runs occurred in separate processes at different times, without a paired
randomized execution order or shared fresh-key draws. Therefore the analysis
does not support:

- a paired latency speedup;
- a causal claim that one parameter field caused the error difference;
- general HIT quality;
- general external-autotuner performance;
- promotion of the rejected HIT candidate.

The allowed observation is narrower: on the same frozen raw workload, both
candidates pass Security V2 and execute successfully, but the direct literal
is decision-SAFE while the source-replayed HIT literal is decision-REJECTED.
Only the direct literal proceeds to and passes locked audit.

`paper_claim_allowed=false`.
