# FlipGuard V2 Related-Work Positioning

Status: primary-source audit completed on 2026-07-29. This document records
the conservative novelty boundary used by the manuscript.

## Scope

FlipGuard must not claim to be the first automatic CKKS configurator, the
first error-aware CKKS optimizer, or a general FHE compiler. Prior work already
automates program lowering, parameter selection, scale management,
bootstrapping placement, model adaptation, or agent-guided configuration.

The defensible research question is narrower:

> Given a frozen threshold-based model and declared validation scope, can a
> system synthesize a CKKS literal, admit it only when the observed encrypted
> output preserves every certifiable plaintext decision, abstain otherwise,
> and retain that decision under a disjoint no-retuning audit?

The system position is an autotuner-agnostic Decision-Integrity Layer.
Manual configuration, bounded catalog search, external autotuners, and the
direct synthesizer are candidate providers evaluated by the same gate.

## Compiler and Scale-Management Systems

- [CHET (PLDI 2019)](https://doi.org/10.1145/3314221.3314628) compiles tensor
  programs for homomorphic neural-network inference and optimizes their
  encrypted execution.
- [EVA (PLDI 2020)](https://doi.org/10.1145/3385412.3386023) provides an
  encrypted-vector IR and compiler that generates correct, secure, and
  optimized CKKS programs.
- [HECATE (CGO 2022)](https://doi.org/10.1109/CGO53902.2022.9741265)
  explores performance-aware scale-management plans and rescaling points.
- [ELASM (USENIX Security 2023)](https://www.usenix.org/conference/usenixsecurity23/presentation/lee-yongwoo)
  explicitly optimizes the output-error/latency trade-off using estimated
  error, scale-to-noise ratio, and operation-specific waterlines.
- [HECO (USENIX Security 2023)](https://www.usenix.org/conference/usenixsecurity23/presentation/viand)
  lowers high-level imperative programs through an end-to-end FHE compiler
  stack and includes basic depth-guided parameter selection.
- [DaCapo (USENIX Security 2024)](https://www.usenix.org/conference/usenixsecurity24/presentation/cheon)
  automatically places bootstrapping operations using liveness and latency
  analysis.

These systems establish that graph lowering, scale placement, output-error
optimization, and automatic cryptographic configuration are prior art.
FlipGuard treats such systems as possible candidate providers. Its claimed
contribution is the downstream decision-integrity admission and audit
contract, not replacement of their compiler optimizations.

## Automated Search and Model Adaptation

- [AutoPrivacy (NeurIPS 2020)](https://papers.nips.cc/paper_files/paper/2020/hash/6244b2ba957c48bc64582cf2bcec3d04-Abstract.html)
  uses reinforcement learning to select layer-wise HE parameters for hybrid
  private neural inference while trading latency against model accuracy.
- [Automated HE Parameter Selection with Fuzzy Logic and Linear Programming
  (2023 preprint)](https://arxiv.org/abs/2302.08930) maps circuit properties
  and user priorities to security-, precision-, and performance-aware
  parameters.
- [AutoFHE (2023 ePrint)](https://eprint.iacr.org/2023/162) jointly searches
  polynomial activations, coefficients, and bootstrapping placement for
  encrypted CNN inference.
- [FHE-Agent (2025 preprint)](https://arxiv.org/abs/2511.18653) is the closest
  automation precedent. It combines an LLM controller with deterministic
  tools, static pruning, encrypted calibration, and layer-wise repair to find
  feasible 128-bit CKKS configurations for MLP, LeNet, LoLa, and AlexNet.

FHE-Agent has substantially broader neural-network coverage than the current
FlipGuard prototype. FlipGuard therefore cannot claim automation breadth or
first use of failure-guided CKKS repair. Its different target is a
deterministic, provider-agnostic gate whose acceptance rule is expressed in
the final application's decision space. Model architecture, packing, and
activation search remain outside the present contribution.

## Application-Aware Approximate FHE

[Application-Aware Approximate Homomorphic Encryption (ePrint
2024/203)](https://eprint.iacr.org/2024/203) formalizes an application using
both a circuit and an allowed input domain, and argues that parameter
generation, error estimation, and runtime validators should be tied to that
application specification. This is the closest conceptual foundation for
FlipGuard's workload contract.

The distinction must remain explicit:

- application-aware FHE provides cryptographic definitions and may use a
  provable or heuristic error estimator;
- FlipGuard's current interval sensitivity is only a planning signal;
- current `SAFE` evidence is empirical and finite-scope, not a sound
  application-domain error bound or an IND-CPAD result;
- FlipGuard additionally maps numeric error to a threshold-decision margin,
  separates `V_cert` from `V_amb`, exposes `REJECTED`/`FAILED`/`NO_SAFE`, and
  performs a disjoint locked audit after selection.

## Conservative Comparison

| System family | Primary optimization target | Relation to FlipGuard |
|---|---|---|
| CHET, EVA, HECO | Program lowering and encrypted execution | Candidate provider or backend |
| HECATE | Scale placement and runtime | Candidate provider |
| ELASM | Output error versus latency | Strong error-aware baseline; not decision-margin admission |
| DaCapo | Bootstrapping placement | Orthogonal provider for deeper programs |
| AutoPrivacy, AutoFHE | Model/HE co-design and accuracy-latency | Broader model adaptation; frozen-model assumption differs |
| Fuzzy/LP selector | User-priority-guided HE parameters | Parameter-selection baseline |
| FHE-Agent | Agent-guided feasible CKKS configuration and repair | Closest automation baseline; broader graph coverage |
| Application-aware FHE | Circuit/domain-aware correctness and security | Formal foundation and future analytical target |
| FlipGuard | Threshold-decision admission, abstention, and locked audit | Current claimed contribution |

## Required Citation Language

Allowed:

> Prior systems automate FHE compilation, scale management, parameter
> selection, model adaptation, and repair. FlipGuard complements these systems
> with a provider-agnostic decision-preservation gate and a locked,
> no-retuning audit protocol for threshold-based inference.

Forbidden:

- “FlipGuard is the first automatic CKKS tuner.”
- “Prior work ignores approximation error.”
- “FlipGuard provides a formal application-domain correctness guarantee.”
- “FlipGuard supports arbitrary neural networks.”
- “Decision preservation makes the underlying CKKS parameters secure.”
