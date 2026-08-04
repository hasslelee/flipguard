# Decision-Integrity Contracts

FlipGuard evaluates CKKS configuration candidates against an explicit decision contract. The contract defines a finite empirical admission test; it does not establish a distribution-wide theorem about unseen inputs.

## Binary Threshold Contract

Let the plaintext score be `f_plain(x)`, the CKKS score be `f_c(x)`, and the decision threshold be `tau`. Define

```text
m(x) = |f_plain(x) - tau|
e_c(x) = |f_c(x) - f_plain(x)|.
```

### Sufficient Condition

If `e_c(x) < m(x)`, then the CKKS and plaintext threshold decisions agree.

Proof: when `f_plain(x) > tau`, the strict error bound gives

```text
f_c(x) > f_plain(x) - m(x) = tau.
```

The case `f_plain(x) < tau` is symmetric. Equality is intentionally excluded: at the boundary the result depends on the decision convention and is not certified by this inequality.

### Operational Reserve Policy

FlipGuard applies the stricter empirical policy

```text
e_c(x) < rho * m(x),  with primary rho = 0.5.
```

`rho` is the margin-utilization cap and `1-rho` is the reserved fraction. The primary value is a predeclared operating policy. It is neither derived from CKKS theory nor shown to be optimal.

The structural polynomial holdout demonstrates the distinction: one audit observation retained its plaintext decision but used more than the 50% margin budget. FlipGuard therefore classified the candidate as reserve-policy rejected without calling it an observed decision failure.

## Multiclass Argmax Contract

Let plaintext logits be `z(x) = (z_1, ..., z_K)` and define the deterministic plaintext class

```text
c* = argmax_k z_k,
```

with the smallest class index used to break exact plaintext ties. Let CKKS logits satisfy

```text
z_hat_k = z_k + Delta_k,  with |Delta_k| <= B_k.
```

### Pairwise Preservation Proposition

If for every `j != c*`,

```text
z_c*(x) - z_j(x) > B_c*(x) + B_j(x),
```

then `argmax_k z_hat_k(x) = c*`.

Proof: for every competitor `j`,

```text
z_hat_c* - z_hat_j
  = (z_c* - z_j) + (Delta_c* - Delta_j)
  >= (z_c* - z_j) - |Delta_c*| - |Delta_j|
  > 0.
```

Thus the encrypted top logit remains strictly larger than every competitor. Strict inequality avoids depending on a runtime tie rule.

### Uniform-Bound Corollary

If every logit error is bounded by the same `B`, it is sufficient that

```text
2B < g(x),
g(x) = z_top1(x) - z_top2(x).
```

The top-two gap is computed from plaintext configuration-validation logits. Audit bucketing and policy boundaries are frozen before the audit is evaluated.

## Boundary and Failure Semantics

- Exact equality at a sufficient-condition boundary is not admitted.
- Plaintext ties use a deterministic class-index tie break but are ambiguous for certification.
- `NaN` or infinite plaintext/CKKS values are rejected.
- An observed matching decision does not override a reserve-policy rejection.
- An observed flip is always reported, even when another aggregate metric would pass.
- Audit evidence cannot trigger synthesis, repair, or new bucket boundaries.

## Certification Sets

For an input set `V`, define a certified region and an ambiguous region:

```text
V_cert = {x in V : decision margin exceeds the declared floor}
V_amb  = V \ V_cert.
```

For binary outputs the margin is the threshold distance. For multiclass outputs it is the top-two gap, together with pairwise logit-error budgets. Coverage reports the fraction of declared observations eligible for certification; it is not a population probability.

## Candidate Outcomes

| State | Meaning |
|---|---|
| `SAFE` | candidate executed and passed every required finite admission check |
| `REJECTED` | execution evidence exists, but a decision or reserve-policy check failed |
| `FAILED` | execution, parsing, identity, or required evidence did not complete admissibly |
| `NO_SAFE` | the bounded candidate process ended without establishing a `SAFE` candidate |
| `PLAN_UNSUPPORTED` | the graph cannot be instantiated by that declared profile or path |

`PLAN_UNSUPPORTED` is evaluated before a candidate can become `SAFE`, `REJECTED`, or `FAILED`. It must not be relabeled as `NO_SAFE` for a larger or hypothetical search space.

## What the Contract Establishes

The empirical contract supports statements about declared finite validation and disjoint locked-audit artifacts under frozen identities, policies, and fresh-key repetitions. It does not by itself establish:

- distribution-wide decision preservation;
- arbitrary graph support;
- a closed-form CKKS analytical certificate;
- global configuration feasibility or optimality;
- exact equivalence between every security estimator model and runtime noise distribution.

Canonical allowed wording is maintained in the [core](evidence/paper_claim_admission_v1/) and [multiclass](evidence/journal_multiclass_claim_admission_v2/) claim registries.
