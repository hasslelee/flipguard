# Step 7F.1 Primary-Source Novelty Audit

Status: completed on 2026-07-30 using primary publication, preprint, and
official project sources available on that date. This is a research-direction
control document, not manuscript prose. `paper_claim_allowed=false`.

## Audit Question

What part of FlipGuard remains defensible after accounting for automatic HE
compilers, scale/error optimizers, parameter selectors, repair systems,
application-aware approximate HE, and the project's own negative ablations?

## Reviewer-Risk Matrix

| Reviewer concern | Literature precedent | Practice adopted in FlipGuard | Residual gap and prohibited overclaim |
|---|---|---|---|
| Automatic CKKS configuration is established prior art | CHET, EVA, HECO, HEIR, HECATE, ELASM, and FHE-Agent already automate lowering, scale management, parameter selection, calibration, or repair | Position the direct synthesizer as one candidate provider behind a provider-agnostic decision-integrity gate | Do not claim the first CKKS autotuner, first direct selector, or first repair-based selector |
| Graph optimization is broader than the current adapters | DaCapo places bootstraps; Orbit jointly optimizes bootstrap/rescale placement; Rotom searches tensor layouts; Libra co-optimizes cross-scheme GPU code | Keep bootstrapping, tensor layout, packing, scheme choice, and backend scheduling outside the claimed contribution | Do not claim compiler replacement, arbitrary graph support, packed CNN generality, or hardware optimization |
| Error-aware optimization is not new | ELASM explicitly optimizes estimated output error and latency | Compare in decision space: certify observed threshold decisions, reject, abstain, and replay the selected literal on a locked audit | Do not state that prior work ignores approximation error |
| Application contracts already have a formal cryptographic treatment | Application-Aware Approximate HE binds a circuit and input domain to parameter generation, estimation, and runtime validation | Bind graph, model, threshold, split, candidate, policy, and source digests; keep empirical and analytical evidence types separate | Finite observed `SAFE` is not an application-domain proof or IND-CPAD result |
| LLM-guided configuration and repair already cover broader networks | FHE-Agent combines an LLM controller, deterministic tools, pruning, encrypted calibration, and layer-wise repair across MLP and CNN families | Retain deterministic bounded repair and fail-closed evidence; treat external autotuners as candidate providers | Do not claim broader neural coverage or novelty from failure-aware repair alone |
| Decision margins may be decorative if hard floors dominate | The predeclared seed-0 ablation observed identical initial and selected path-plus-CKKS literals for graph-only and full synthesis in 10/10 workloads | Preserve the decision gate, rejection, NO_SAFE, and locked audit; report that the natural-data parameter-synthesis effect was not observed | Do not claim that margins generally determine or improve the selected configuration |
| Validation success may not generalize | The structural holdout produced 24/25 audit PASS and one disclosed numerical REJECT with no retuning | Preserve negative rows, separate selection from locked audit, and lower the structural claim | Do not claim unseen decisions are always preserved |
| Empirical error is not an analytical bound | Application-aware AHE and CKKS analyses require explicit primitive assumptions and domain bounds | Maintain a typed error-envelope propagator that accepts separately justified primitive residual bounds | Do not infer a sound residual bound from observed maximum error, fresh-key variance, or quantiles |
| Security and numerical correctness are separate | HE parameter standards bound cryptographic security; decision correctness depends on computation error and margin | Apply Security Policy V2 independently to Q and QP objects, then apply the decision certificate | Do not use decision preservation as evidence of cryptographic security |
| A bounded catalog is not a global oracle | Compiler/search literature spans much larger program and parameter spaces | Use only “security-compliant bounded catalog oracle” for the fixed 700-candidate formal domain | Do not write global oracle, global optimum, or universal optimum |

## Adopted Research Boundary

The current defensible systems contribution is:

> Given a supported frozen graph and a threshold-decision contract, FlipGuard
> proposes a CKKS literal from a provider, executes a bounded number of
> encrypted validation trials, certifies or rejects the literal in the
> declared finite decision scope, abstains when no SAFE literal is
> established, and replays the selected literal without retuning on a
> disjoint locked audit.

The direct synthesizer is experimentally useful because it reaches the
validated literal with far fewer encrypted candidate trials than the frozen
security-compliant bounded catalog. The evidence also supports bounded repair
and shows that latency-only selection can choose decision-unsafe literals.
It does not currently show that natural decision margins alter the synthesized
CKKS literal.

## Sources Checked

- CHET, PLDI 2019, DOI `10.1145/3314221.3314628`.
- EVA, PLDI 2020, DOI `10.1145/3385412.3386023`.
- HECATE, CGO 2022, DOI `10.1109/CGO53902.2022.9741265`.
- ELASM, USENIX Security 2023.
- HECO, USENIX Security 2023.
- DaCapo, USENIX Security 2024.
- Application-Aware Approximate Homomorphic Encryption, ePrint 2024/203.
- HEIR, arXiv:2508.11095.
- FHE-Agent, arXiv:2511.18653.
- Rotom, ePrint 2025/1319 and USENIX Security 2026.
- Orbit, ePrint 2026/213 and USENIX Security 2026.
- Libra, USENIX Security 2026.

The bibliography is maintained in
`docs/research/flipguard_v2_references.bib`; the prose comparison is in
`docs/research/flipguard_v2_related_work.md`.
