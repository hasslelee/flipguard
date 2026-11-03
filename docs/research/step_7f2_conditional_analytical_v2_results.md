# Step 7F.2 Conditional Analytical V2 Results

Status: conditional propagation implementation `SUPPORTED`; instantiated CKKS
analytical certificate `BLOCKED`. Static audit only, with zero encrypted
executions and zero policy modifications. `paper_claim_allowed=false`.

## Implementation

`research/analyticalv2` adds a replayable derivation over the existing exact
CKKS operation-graph contract. It:

- binds model scalars by canonical binary64 bits;
- requires one digest-bound assumption per ordered operation node;
- distinguishes absolute derivations from empirical and standard-deviation
  diagnostics;
- propagates input, coefficient, multiplication, addition, relinearization,
  rescale, and alignment uncertainty;
- rounds every positive upper-bound operation toward positive infinity;
- composes probabilistic primitive events with an outward-rounded union bound;
- recomputes node envelopes during validation;
- refuses proof promotion for diagnostic sources, invalid probabilities,
  graph/source mismatch, overflow, or mutation.

A fixed-seed property test covers 2,000 random `linear_poly3` input and
coefficient perturbations. No sampled arithmetic error exceeded the derived
conditional bound. Unit tests also cover deterministic and probabilistic
proof promotion, diagnostic blocking, assumption reorder, stored-result
mutation, missing model values, and overflow.

## Primary Readiness Audit

The static inventory binds all current primary direct selections:

| Population | Candidates | Graph contract implemented | Complete primitive bounds | Proof eligible |
|---|---:|---:|---:|---:|
| Seed 0 development | 10 | 5 | 0 | 0 |
| Seeds 1-4 confirmatory | 40 | 20 | 0 | 0 |
| Combined descriptive | 50 | 25 | 0 | 0 |

The 25 implemented graph contracts are `linear_poly3`. The other 25
`mlp_square_linear_score` rows require a separate exact analytical operation
graph.

Even for `linear_poly3`, the current Lattigo facts do not provide scoped
absolute end-to-end primitive residuals for:

- input encoding and public-key encryption;
- coefficient/plaintext encoding at the concrete scale and level;
- ciphertext multiplication;
- relinearization and key switching;
- rescaling and RNS rounding;
- level alignment.

Lattigo fresh-noise helpers are standard deviations and therefore remain
diagnostic. Observed maximum error, quantiles, and fresh-key variation are
also prohibited substitutions.

## Claim Boundary

Supported:

> Given complete digest-bound deterministic or probabilistic absolute
> primitive bounds for the bound operation graph, the V2 engine computes a
> replayable outward-rounded upper bound on output error and composes stated
> primitive failure probabilities by a union bound.

Blocked:

> Current FlipGuard CKKS candidates have a sound instantiated analytical
> decision-preservation certificate.

No observed-versus-bound audit was run because no selected candidate has a
complete primitive derivation. Reporting `0/50` is the intended fail-closed
result, not missing data to be filled with an empirical estimate.

## Artifacts

Raw readiness output:

```text
results/thesis_grade_protocol/conditional_analytical_readiness_v2/
```

The frozen evidence pack is generated separately at:

```text
docs/evidence/conditional_analytical_readiness_v2/
```
