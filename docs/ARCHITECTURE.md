# FlipGuard Architecture

FlipGuard is a Decision-Integrity Layer for CKKS configuration providers. Its built-in direct synthesizer is the main candidate provider, while manual literals, bounded catalogs, and external provider formats can enter the same validation gate when their provenance is available.

## Design Contract

Every run binds four inputs before encrypted execution:

1. a supported computation-graph artifact;
2. a decision-integrity contract and finite input role;
3. the immutable Direct Policy V2;
4. the explicit Security Policy V2.

The binding prevents a candidate that was synthesized for one model, split, or policy from being reported under another. A run is not identified only by a friendly profile name: its literal parameters, graph, model, source, split, policy, and binary digests are part of the evidence identity.

## Main Path

![FlipGuard architecture](assets/figures/flipguard-overview.svg)

### 1. Graph and Decision Contract

Supported graph adapters expose facts needed for synthesis:

- operation and multiplicative-depth structure;
- scale and rescale trace;
- level and special-prime requirements;
- input width and required slots;
- output shape, threshold, or multiclass logits;
- finite validation and audit artifacts.

The graph adapter is explicit. FlipGuard does not infer arbitrary program semantics or claim universal graph support.

### 2. Direct Literal Synthesis

The built-in synthesizer maps graph facts and policy constraints to a literal CKKS configuration: `LogN`, exact `Q` and `P` chains, default scale, execution path, and packing scope. Candidate IDs bind the literal and source facts. The implementation stops at the first admitted `SAFE` candidate instead of enumerating every bounded-catalog profile.

Direct Policy V2 fixes the minimum scale and prime floors, scale and first-prime guards, numerical and level repairs, first-SAFE rule, and maximum of four encrypted trials. Results cannot retune these constants.

### 3. Security Admission

Security Policy V2 records the concrete Lattigo v6.2.0 secret and error distributions, exact modulus material, and published table caps. Ciphertext objects are checked with `Q`; relinearization and key-switching objects are checked with `QP`. A candidate is admitted only when every required object passes the declared policy.

Table-policy admission is reported separately from lattice-estimator model sensitivity. The latter cannot exactly reproduce every runtime distribution detail, so FlipGuard does not claim universal 128-bit security for arbitrary distributions.

### 4. Encrypted Validation

The executor evaluates the candidate on the declared configuration-validation artifact across fresh-key runs. For every observation, it records plaintext output, CKKS output, decision margin or top-two gap, absolute error, decision result, and reserve-policy status.

Outcomes are fail closed:

- `SAFE`: execution and the declared finite admission checks passed;
- `REJECTED`: execution completed but the decision-integrity reserve policy failed;
- `FAILED`: the candidate could not produce admissible execution evidence;
- `NO_SAFE`: no `SAFE` candidate was established within the bounded candidate policy.

`NO_SAFE` is not a proof that no CKKS configuration exists.

### 5. Bounded Repair

Predeclared repair classes respond to execution evidence without consulting the locked audit:

- numerical repair adds the frozen scale/prime allowance;
- level repair adds the frozen level allowance;
- static NTT-prime retry handles literal materialization constraints.

The repair process terminates at the first `SAFE` candidate or at the trial budget. Unsupported graphs and security-inadmissible literals fail before formal execution.

### 6. Literal Lock and Audit

After selection, FlipGuard locks the literal and replays it on a disjoint audit artifact. Synthesis and repair are unavailable in this stage. The audit records candidate, source, model, split, policy, and binary identities so that any mismatch fails closed.

An audit rejection is scientific evidence, not a request to retune. The structural polynomial holdout includes one such reserve-policy rejection without a decision flip, and the record is preserved.

## Evaluation-Only Catalog Path

The formal bounded catalog contains only profiles admitted by Security Policy V2 and paths supported by the workload. Its fastest-safe candidate is used to measure trial work and paired latency within that declared set. It is therefore called the **Security-V2-compliant bounded-catalog fastest-safe** candidate, not a global optimum.

For the controlled primary study, 7 admitted profiles, 2 paths, and 50 workload-partition instances yield 700 formal candidates. The 1,100-record pre-security ledger remains historical execution and security-sensitivity evidence; excluded profiles are not part of the formal oracle denominator.

## Identity Layers

FlipGuard separates three data identities:

- **source identity:** original ordered source rows and full-precision content;
- **prepared identity:** materialized rows, provenance columns, and execution representation;
- **semantic identity:** ordered model inputs and labels consumed by execution.

This distinction arose from a fail-closed comparator event in which semantically identical inputs had different prepared bytes. The original failure and the corrected identity audit are both retained.

## Module Responsibilities

| Area | Primary responsibility |
|---|---|
| `internal/analysis` and `internal/ir` | graph facts and intermediate representation |
| `internal/tuner` and `internal/ckksplanner` | direct synthesis and bounded planning |
| `internal/certify` | binary and multiclass decision contracts |
| `internal/ckksbackend` and `internal/runtime` | Lattigo execution and runtime accounting |
| `internal/report` | structured summaries and evidence records |
| `internal/providergate` and `internal/externaladapter` | fail-closed provider-format admission |
| `cmd/flipguard-*` | task-specific command-line entry points |
| `scripts/` | protocol orchestration, evidence freezing, and deterministic verification |

The command count reflects research protocols, not a promise that every entry point is a stable public API. Start with `flipguard-synthesize` and the artifact verifiers documented in [Reproducibility](REPRODUCIBILITY.md).

## Immutability Boundaries

Frozen evidence packs are append-only research records. New interpretations, security reconciliation, and claim admission are stored as overlays that cite predecessor digests. A public-documentation change must not alter Direct Policy V2, Security Policy V2, encrypted ledgers, model artifacts, or established claim values.
