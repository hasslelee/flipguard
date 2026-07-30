# Step 7G.1 Provider-Agnostic Candidate Gate Protocol

Status: predeclared implementation protocol on 2026-07-30. No encrypted
candidate has been executed under this extension. This is a research and
development control document, not manuscript prose.
`paper_claim_allowed=false`.

## Motivation

HECATE, ELASM, DaCapo, HEIR, and FHE-Agent establish that CKKS scale
management, graph lowering, parameter selection, encrypted calibration, and
failure-aware repair are prior art. FlipGuard's defensible systems boundary is
therefore not ownership of every candidate-generation method. It is the
downstream decision-integrity gate applied to an exact candidate literal.

The current Go engine exposes `ExecuteTabularCandidate`, but an external or
manual literal has no dedicated artifact contract that recomputes Security V2
admission and binds provider provenance to the workload. This protocol closes
that implementation gap without changing Direct Policy V2, Security Policy
V2, CKKS execution semantics, or any frozen evidence.

## Provider Contract

The importer accepts exactly four provider kinds:

- `manual`;
- `bounded_catalog`;
- `external_autotuner`;
- `direct_synthesizer`.

An input artifact contains:

- schema version;
- provider kind and stable provider ID;
- execution path;
- literal `LogN`, `LogQ`, `LogP`, and default scale.

Binding recomputes and records:

- input-artifact SHA-256;
- workload-contract SHA-256;
- Security Policy V2 SHA-256;
- ciphertext-Q and evaluation-key-QP admission;
- required slots and required Q-prime count;
- backend literal validity;
- a canonical candidate ID derived from provider identity, input digest,
  contract digest, path, and exact literal.

No security assessment supplied by a provider is trusted.

## Fail-Closed Rules

Binding fails before CKKS execution when:

- JSON contains unknown or trailing fields;
- the provider kind or ID is invalid;
- the execution path is outside the workload contract;
- the literal is malformed or unsupported by Lattigo;
- the ring does not provide the required slots;
- the Q chain is shorter than the graph contract requires;
- Security V2 rejects ciphertext Q or evaluation-key QP;
- the source artifact, contract, candidate ID, or policy digest changes after
  binding.

The gate executes one exact bound literal. It does not enumerate neighboring
configurations and does not call Direct Policy V2 repair. A `SAFE` result
produces `SELECTED`; `REJECTED` or `FAILED` produces `NO_SAFE` for that
single-provider request. The underlying status is always retained.

## Static Verification

Required tests before any encrypted evaluation:

- all four provider kinds bind successfully for an admissible fixture;
- the same bytes and contract reproduce the same candidate ID;
- a provider ID, source byte, literal, or contract change changes or invalidates
  the binding;
- unknown JSON fields fail;
- inadmissible QP fails before CKKS;
- insufficient slots and insufficient levels fail;
- a post-binding source mutation fails before CKKS;
- Direct and Security policy digests remain byte-identical.

## Future Evaluation

Any empirical provider-agnostic claim requires a separately committed,
predeclared matrix using frozen candidate literals. At minimum it must include
one manual literal, one Security-V2 bounded-catalog literal, one
direct-synthesized literal, and one externally formatted literal. Reusing an
existing encrypted ledger is allowed only when contract, literal, source, and
execution semantics are identical and the provenance mapping is verified.

Until that matrix is frozen and verified:

- provider-agnostic binding implementation: `NOT_EVALUATED`;
- provider-agnostic encrypted certification: `NOT_EVALUATED`;
- external-autotuner interoperability: `NOT_EVALUATED`;
- `paper_claim_allowed=false`.

## Predeclared Development Matrix

The first matrix is now fixed in
`experiments/provider_candidate_gate_v1/contract.json`. It uses only the
development partition:

- workload: seed 0, `iris_binary/linear_poly3`;
- configuration validation: 14 rows;
- disjoint locked audit: 16 rows;
- fresh-key repeats: three for validation and three for audit;
- one exact encrypted candidate trial per provider arm;
- provider order: manual, Security-V2 bounded catalog, external-format
  fixture, and direct synthesizer.

The manual, external-format, and direct arms intentionally carry the same
frozen direct literal. This isolates provider-label and source-binding behavior
from parameter quality. The catalog arm carries the frozen Security-V2
bounded-catalog fastest-SAFE literal for this development workload at
`alpha=0.5`. A SAFE validation result is replayed without synthesis or repair
on the locked audit split. A scientific `REJECTED`, `FAILED`, or `NO_SAFE`
result is retained and does not change any literal or policy.

The external arm is a hand-authored schema-compatibility fixture. Success
cannot be reported as an evaluation of FHE-Agent or any other third-party
autotuner. Actual external-tool integration remains `NOT_EVALUATED`.

## Prohibited Interpretation

This adapter does not make FlipGuard a compiler, prove arbitrary autotuner
compatibility, or turn finite observed validation into an application-domain
correctness proof or IND-CPA-D result. Application-Aware Approximate
Homomorphic Encryption requires the circuit and allowed input domain to remain
consistent across parameter generation, estimation, and runtime use; the
provider binding is an artifact-assurance mechanism aligned with that
principle, not a replacement for its security definition.
