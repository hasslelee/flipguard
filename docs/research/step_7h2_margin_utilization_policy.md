# Step 7H2: Decision Margin and Utilization Policy

Status: paper-facing interpretation overlay; frozen encrypted evidence and
policy identities are unchanged.

## Mathematical separation

Let the plaintext score, CKKS score, and threshold be

```text
f_plain(x)
f_c(x)
tau
```

Define the decision margin and absolute CKKS error as

```text
m(x)   = |f_plain(x) - tau|
e_c(x) = |f_c(x) - f_plain(x)|
```

For the same strict threshold convention, the following is a sufficient
decision-preservation condition:

```text
e_c(x) < m(x)  =>  d_c(x) = d_plain(x)
```

FlipGuard's operational reserve policy is deliberately stricter:

```text
e_c(x) < rho * m(x)
```

The primary predeclared policy uses `rho = 0.5`.

## Operational interpretation

- `rho` is the margin utilization cap.
- `1 - rho` is the reserved margin fraction.
- `rho * m(x)` is the operational acceptance budget.
- `rho = 0.5` is the predeclared 50%-margin-utilization policy.
- `rho = 0.5` is neither derived from CKKS theory nor claimed to be optimal.

The internal `SafetyFactor` field remains as a backward-compatible alias so
that frozen policies, candidate identities, and evidence schemas retain their
original digests. New report adapters expose `margin_utilization_cap` and
`reserved_margin_fraction`; they do not alter execution semantics.

## Structural negative result

For `seed4/banknote/mlp_square_poly3`, the selected literal was SAFE on
validation and was replayed without retuning on the locked audit.

| Partition | Maximum `e_c(x)/m(x)` | Reserve-policy result | Flip |
|---|---:|---|---:|
| validation | 0.4706530094839232 | PASS | 0 |
| locked audit | 0.5613686443055665 | REJECT | 0 |

The locked-audit result is classified as:

- `OBSERVED_DECISION_PRESERVED`;
- `RESERVE_POLICY_REJECTED`; and
- `POLICY_REJECTED_WITHOUT_FLIP`.

It is not a cryptographic-correctness failure and not an observed decision
failure. The execution artifact retained population maxima and violation
counts but not the exact per-sample CKKS ledger; the interpretation therefore
does not bind the maximum absolute error and maximum utilization to the same
sample.

## Alpha-grid interpretation

The tested primary grid is `rho in {0.1, 0.25, 0.5, 0.75, 0.9}`. Across the
natural primary workloads:

- candidate-state changes: `0`;
- Security-V2 bounded-oracle selection changes: `0`; and
- direct initial path-and-parameter literal changes: `0`.

The observed invariance is explained by minimum synthesis-floor dominance in
the tested primary range. It is not evidence that `rho = 0.5` is optimal.

## Claim boundary

The theorem supports decision preservation when the observed error is strictly
smaller than the full margin. The 50%-utilization rule is a predeclared
operational reserve policy used by the finite-set admission gate. Neither
statement supplies an instantiated distribution-wide CKKS error certificate.
The derived evidence pack
`docs/evidence/margin_utilization_interpretation_v1` references frozen records
without modifying them.
