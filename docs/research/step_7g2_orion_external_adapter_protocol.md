# Step 7G.2: Actual Orion Configuration Adapter Audit

## Question

Can an actual public CKKS configuration from Orion be passed through the
FlipGuard provider gate without changing the configuration's runtime or
security meaning?

This is a static interoperability audit. It does not execute CKKS and it does
not evaluate Orion's configuration quality.

## Pinned Primary Source

The audit pins Orion commit
`be8a827350a147d610fe3bb998b5bea8de814ff8` and its declared Lattigo fork:

- module `github.com/baahl-nyu/lattigo/v6`;
- version `v6.2.0`;
- tag commit `a9699d924dcc2628153b1ca3bf41d65b26299a86`.

The public MLP, LoLA, and ResNet YAML files are fetched from that exact commit.
The Orion parser, Lattigo scheme constructor, Go module, and license are also
bound by SHA-256. The comparison target is the official Lattigo v6.2.0 tag
commit `c1fd095f08602e2d4ef571db015fc553fdd2d845`.

The complete predeclared source list and expected classifications are in
`experiments/orion_external_adapter_v1/contract.json`.

## Exactness Gate

The adapter parses YAML with unknown-field and trailing-document rejection.
It separately evaluates:

1. ordered `LogN`, `LogQ`, `LogP`, and `LogScale` transfer;
2. standard versus conjugate-invariant ring semantics;
3. the concrete secret distribution;
4. the concrete error distribution;
5. backend module and commit provenance;
6. ciphertext-Q and evaluation-key-QP admission under Security Policy V2.

A source configuration is executable only if every semantic mapping is exact
and Security V2 admits it. Dropping a field or replacing it with a FlipGuard
default is a semantic change, not an adapter.

## Predeclared Falsification

The pinned Orion constructor passes `ring.Ternary{H: h}`. FlipGuard Security
Policy V2 is fixed to `ring.Ternary{P: 2/3}`. These are not identical
distributions. The public YAML also does not serialize `Xe`, and the MLP/LoLA
files request conjugate-invariant packing. Therefore those configurations
must be blocked before encrypted execution.

The MLP and LoLA modulus declarations sum to `LogQP=217`, which exceeds the
Policy V2 `LogN=13` cap of 214. The ResNet file uses `LogN=16`, outside the
current Policy V2 table. These checks are independent of the distribution
mismatches.

If the adapter emits or executes any of these configurations by silently
using target defaults, the audit fails.

## Claim Boundary

A passing static audit can support provenance-aware parsing and fail-closed
semantic mismatch detection. It cannot support:

- actual external-autotuner output integration;
- encrypted certification of an Orion candidate;
- Orion configuration quality;
- cross-backend equivalence;
- a broad provider-agnostic empirical claim.

Orion is a compiler framework. Its checked-in YAML files are not attributed
to an autotuning run, so `third_party_autotuner_integration` remains
`NOT_EVALUATED`.
