# Step 10a: Final Research Message and Comparison Objective

## Reviewer concern

FlipGuard's existing evidence establishes direct synthesis, finite-scope
decision admission, locked audit, and a Security-V2 bounded-catalog comparison.
The external-system audit, however, must not confuse artifact availability or a
compiler build with an equivalent experiment. It must also state the selection
objective more directly: the useful outcome is not a configuration generated
by a particular provider, but the fastest measured configuration among the
candidates that satisfy the same security, execution, and decision-stability
requirements for a declared workload.

## Literature precedent

CKKS systems generate candidates for different purposes. General compilers
lower programs and choose layouts; scale managers place scales and rescaling;
bootstrapping planners place refresh operations; DNN systems alter packing,
layers, or polynomial approximations; and agent-based systems automate parts of
configuration construction. Their original objectives remain valid within
their reported scopes. A fair comparison therefore separates capability,
paper-reported results, native execution, and common-executor evidence instead
of placing heterogeneous native latencies in one ranking.

## Implementation requirement

For a frozen workload `W`, define the declared candidate set as

```text
C(W) = C_manual(W) union C_catalog(W) union C_external(W) union C_direct(W).
```

The decision-stable subset is

```text
C_stable(W) = {c in C(W) |
  c passes the declared security/runtime admission and
  c preserves the plaintext decision on the frozen validation inputs}.
```

Under one common timing protocol, the selector returns

```text
c* = argmin_{c in C_stable(W)} T_W(c).
```

This is a minimum only within the declared, comparable candidate set. It is not
an optimum over the global CKKS configuration space. When `C_stable(W)` is
empty, the result is `NO_SAFE` for that candidate set.

FlipGuard has two roles. The provider-independent decision-stability gate
admits or rejects candidates from manual, catalog, external, or direct sources.
The built-in direct-synthesis provider analyzes a supported graph and decision
contract, executes at most the frozen trial budget, applies only the frozen
bounded repairs, and stops at the first `SAFE` literal. The paper-facing
introduction is consequently limited to three propositions:

1. Existing CKKS compilers and autotuners generate or optimize execution
   configurations under their own objectives.
2. FlipGuard applies the same declared decision-stability requirements to a
   candidate independently of its source.
3. Among comparable passing candidates, FlipGuard selects the lowest measured
   latency and returns `NO_SAFE` when no passing candidate is established.

Comparison evidence is divided into four non-interchangeable tiers:

- `TIER_1_LANDSCAPE_AND_CAPABILITY`: publication, objective, feature, artifact,
  security, and assurance metadata for all 20 external systems plus FlipGuard.
- `TIER_2_ORIGINAL_PAPER_REPORTED_RESULTS`: within-paper normalized results,
  with table/figure/page provenance and no cross-paper absolute ranking.
- `TIER_3_NATIVE_END_TO_END_AND_PROVIDER_GATE`: official-runtime outputs and
  gate outcomes, with native latency treated as diagnostic across runtimes.
- `TIER_4_COMMON_EXECUTOR_COMPARISON`: exact or explicitly graph-equivalent
  candidates under a shared security and paired timing protocol. Only this
  tier permits a head-to-head latency statement.

The frozen predecessor
`external_autotuner_comparison_v2` remains a 20-system landscape, artifact
availability, documented build/runtime-smoke, applicability, and limited
EVA/Orion gate record. Its correct result is: eight public artifacts passed a
documented build or runtime smoke gate; external exact mapping and
`PORTABLE_EXACT` counts were zero. V3 never describes those eight smoke passes
as eight benchmark reproductions.

## Falsification test

The comparative claim fails closed if a missing value becomes zero; a build
smoke is promoted to native execution; a configuration parse is promoted to an
end-to-end result; a paper-reported speedup is presented as locally measured;
native absolute latency is ranked across runtimes; graph, weights,
preprocessing, packing, output semantics, security assumptions, or timing
boundaries are hidden; or the existing Direct/Security policy is modified to
admit an external candidate. Fewer experimental arms is acceptable after the
feasible official set is exhausted. Relaxing equivalence to reach a target
count is not acceptable.
