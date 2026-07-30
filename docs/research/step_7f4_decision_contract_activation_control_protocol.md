# Step 7F.4 Decision-Contract Activation Control Protocol

Status: `PREDECLARED_NOT_EXECUTED`. This protocol is frozen before any control
CKKS execution. It does not alter Direct Policy V2, Security Policy V2, the
primary results, or the natural-data ablation.

## Motivation

The seed-0 natural-data ablation found identical literal parameters for
graph-only fixed-tolerance and full FlipGuard synthesis in 10/10 workloads.
That negative result remains `BLOCKED` as a natural-data claim.

Static source inspection gives a falsifiable explanation. Candidate scale is:

```text
max(
  min_scale_bits,
  ceil(-log2(output_error_budget / aggregate_sensitivity))
    + scale_guard_bits
)
```

Primary `margin_floor=0.001` and `alpha=0.5` lower-bound the observed decision
budget near `0.0005`. Natural aggregate sensitivities were too small for this
budget to cross the frozen 18-bit synthesis floor and backend feasibility
lift. This control tests whether decision margins activate synthesis once the
same graph has a larger, predeclared sensitivity.

## Frozen Finite Domain

One scalar-replicated `linear_poly3` graph is used:

```text
z = 512 * x
score = 0.5 + 0.197*z - 0.004*z^3
threshold = 0.5
```

Two 32-row configuration-validation regimes use identical:

- model bytes and graph;
- input dimension and scalar-replicated packing;
- minimum and maximum input interval;
- maximum plaintext-output magnitude;
- graph-derived aggregate sensitivity;
- Direct Policy V2 and Security Policy V2;
- alpha `0.5`, margin floor `0.001`, three fresh keys, and four-trial cap.

They differ only in the interior validation points that determine the minimum
certifiable decision margin:

- `narrow_margin`: minimum `|z|=0.0061`;
- `wide_margin`: minimum `|z|=0.06`.

Both retain extrema `z=-100` and `z=100`, so the interval calibration and
aggregate sensitivity must remain byte-for-byte equal after normalization.
The wide interval deliberately activates the cubic node's local error
amplification; increasing the affine weight alone would not change the
planner's operation-error sensitivity definition.
Each regime has a separate 32-row locked audit with disjoint row IDs.
All row IDs are disjoint decimal integers because the encrypted tabular
backend parses the canonical row identity as an integer.
Each generated row contains the complete backend schema:
`row_id,label,scaled_logit,polynomial_score,plaintext_decision,x_0`.

Synthetic split seeds `9101` and `9102` identify this development control and
must never be combined with primary seeds 0-4.

## Frozen Arms

For each regime:

1. `graph_fixed_tolerance`: fixed synthesis budget `0.001`;
2. `decision_contract`: the frozen `alpha * protected_margin` budget.

Encrypted validation, bounded repair, first-SAFE stopping, NO_SAFE, and locked
audit rules remain unchanged. Each selected literal is replayed without
retuning on its disjoint audit.

## Predeclared Predictions

Before encryption:

- graph-fixed literal parameters must be identical across regimes;
- narrow-margin full synthesis must request higher scale than graph-fixed;
- wide-margin full synthesis must remain at the same backend-feasibility floor
  as graph-fixed;
- narrow and wide full literals must differ;
- all literals must pass Security V2 static admission.

If any prediction fails, the static activation claim is `BLOCKED` and no
encrypted control is needed.

After encryption, all scientific outcomes are preserved. A REJECTED, FAILED,
NO_SAFE, or locked-audit violation lowers the corresponding empirical control
claim but does not change a policy or candidate. The natural-data claim
remains `BLOCKED` even if this finite-domain control succeeds.

## Claim Boundary

This control can support only:

> Under the predeclared finite domain, the observed decision-margin contract
> changes the directly synthesized CKKS literal while graph structure,
> interval calibration, and frozen policy constants are held fixed.

It cannot establish that decision margins change configurations on natural
data, improve latency universally, provide a domain-wide proof, or make
FlipGuard a universal CKKS autotuner. `paper_claim_allowed=false`.
