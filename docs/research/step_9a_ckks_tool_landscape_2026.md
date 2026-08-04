# Step 9a: CKKS Tool Landscape and Fair-Baseline Audit (2026)

## Reviewer concern

Comparing FlipGuard only with EVA, HECATE, and ELASM would not represent the
current CKKS compiler and configuration landscape. The landscape now includes
general compilers, scale managers, bootstrap-placement systems, neural-network
adapters, application-aware security models, and agentic configuration tools.
These systems optimize different objects and often use different graphs,
packing layouts, runtimes, and security conventions. A long list of native
latencies would therefore look comprehensive while remaining scientifically
unfair.

This audit separates three questions: whether an official paper exists,
whether an executable artifact can be pinned and reproduced, and whether the
artifact can execute a byte- and semantics-bound FlipGuard workload. Only the
last category can enter a common-executor headline. Native reproduction is
reported as tool-specific evidence and is never used for raw cross-runtime
speed ranking.

## Literature precedent

The census below binds every work to a primary publication page or paper and,
when one exists, an official repository. `NR` means that the official source
does not report or expose the requested fact. Two naming collisions are kept
explicit: this audit uses Google HEIR (2025), not the unrelated NDSS 2024
cross-scheme compiler with the same acronym, and uses the loop-aware
bootstrapping HALO (ASPLOS 2025), not the heterogeneous-circuit HISA named
HALO.

| System | Full title | Venue / status | Scheme and primary objective | Official artifact at audit time | Experimental class |
|---|---|---|---|---|---|
| CHET | CHET: An Optimizing Compiler for Fully-Homomorphic Neural-Network Inferencing | PLDI 2019, peer reviewed | CKKS tensor compilation, layouts, and parameter selection | no separate official repository verified; EVA contains the later CHET-on-EVA path | RELATED_WORK_ONLY |
| EVA | EVA: An Encrypted Vector Arithmetic Language and Compiler for Efficient Homomorphic Computation | PLDI 2020, peer reviewed | CKKS vector IR, rescale insertion, parameter generation | `microsoft/EVA`, tag `v1.0.1` | REQUIRED_REPRODUCTION |
| HECO | HECO: Fully Homomorphic Encryption Compiler | USENIX Security 2023, peer reviewed | BFV/BGV/CKKS imperative compilation and SIMD rewrites | `MarbleHE/HECO`, artifact tag | CONDITIONAL_REPRODUCTION |
| HEIR | HEIR: A Universal Compiler for Homomorphic Encryption | arXiv 2025, preprint | MLIR toolchain across schemes/backends, including CKKS | `google/heir`, release `v2026.08.01` | REQUIRED_REPRODUCTION |
| ANT-ACE | ANT-ACE: An FHE Compiler Framework for Automating Neural Network Inference | CGO 2025, peer reviewed | RNS-CKKS ONNX-to-C/C++ inference compiler | `ant-research/ace-compiler`, tag `cgo2025-artifacts` | REQUIRED_REPRODUCTION |
| HEaaN.MLIR | HEaaN.MLIR: An Optimizing Compiler for Fast Ring-Based Homomorphic Encryption | PLDI 2023, peer reviewed | low-level polynomial/modular-operation optimization | no public source repository verified | RELATED_WORK_ONLY |
| HECATE | HECATE: Performance-Aware Scale Optimization for Homomorphic Encryption Compiler | CGO 2022, peer reviewed | RNS-CKKS performance-aware scale placement | `corelab-src/hecate-compiler`, post-publication snapshot pinned by commit | REQUIRED_REPRODUCTION |
| ELASM | ELASM: Error-Latency-Aware Scale Management for Fully Homomorphic Encryption | USENIX Security 2023, peer reviewed | RNS-CKKS error/latency scale-plan search | `corelab-src/elasm`, pinned commit | REQUIRED_REPRODUCTION |
| HEILP | HEILP: An ILP-Based Scale Management Method for Homomorphic Encryption Compiler | DATE 2025, peer reviewed | ILP-based CKKS level and scale management | no official executable artifact verified | CONDITIONAL_REPRODUCTION |
| DaCapo | DaCapo: Automatic Bootstrapping Management for Efficient Fully Homomorphic Encryption | USENIX Security 2024, peer reviewed | joint scale-aware bootstrap placement | publication points to `corelab-src/elasm`; current code lives in `corelab-src/hecate-compiler` | REQUIRED_REPRODUCTION |
| HALO | HALO: Loop-aware Bootstrapping Management for Fully Homomorphic Encryption | ASPLOS 2025, peer reviewed | bootstrap placement for flat and nested loops | implementation is present in the post-publication HECATE repository; no paper-tagged release verified | CONDITIONAL_REPRODUCTION |
| ReSBM | ReSBM: Region-based Scale and Minimal-Level Bootstrapping Management for FHE via Min-Cut | ASPLOS 2025, peer reviewed | min-cut scale and minimum-level bootstrap management | open-sourced in `ant-research/ace-compiler` after the CGO artifact tag | CONDITIONAL_REPRODUCTION |
| Orbit | Orbit: Optimizing Rescale and Bootstrap Placement with Integer Linear Programming Techniques for Secure Inference | USENIX Security 2026, peer reviewed | joint ILP rescale/bootstrap placement | paper and official proceedings verified; no public executable artifact verified | CONDITIONAL_REPRODUCTION |
| AutoFHE | AutoFHE: Automated Adaption of CNNs for Efficient Evaluation over FHE | USENIX Security 2024, peer reviewed | layer-wise activation degree and bootstrap architecture search | `human-analysis/AutoFHE`, pinned commit | CONDITIONAL_REPRODUCTION |
| Orion | Orion: A Fully Homomorphic Encryption Framework for Deep Learning | ASPLOS 2025, peer reviewed | PyTorch-to-CKKS packing, scale, and bootstrap compilation | `baahl-nyu/orion`, pinned commit | REQUIRED_REPRODUCTION |
| LOHEN | LOHEN: Layer-wise Optimizations for Neural Network Inferences over Encrypted Data with High Performance or Accuracy | USENIX Security 2025, peer reviewed | layer-wise ciphertext configuration and switching | no official source artifact verified | REQUIRED_REPRODUCTION |
| SLOTHE | SLOTHE: Lazy Approximation of Non-Arithmetic Neural Network Functions over Encrypted Data | USENIX Security 2025, peer reviewed | lazy polynomial approximation of non-arithmetic functions | `SNUSOR-PECT/SLOTHE` and Zenodo artifact | CONDITIONAL_REPRODUCTION |
| Application-Aware Approximate HE | Application-Aware Approximate Homomorphic Encryption: Configuring FHE for Practical Use | IACR Communications in Cryptology 2026, peer reviewed | application-aware security definition and ASL, not latency tuning | proof-of-concept OpenFHE integration described; not a performance provider | NOT_COMPARABLE |
| FHE-Agent | FHE-Agent: Automating CKKS Configuration for Practical Encrypted Inference via an LLM-Guided Agentic Framework | arXiv 2025, preprint | LLM-guided global parameter selection and bounded repair over Orion | paper verified; no official executable repository verified | CONDITIONAL_REPRODUCTION |
| FHECrafter | FHECrafter: A Multi-Agent Framework for Automated Fully Homomorphic Encrypted Tensor Program Generation | ICS Workshops 2026, peer reviewed workshop paper | agentic tensor-program generation | DOI metadata verified; no official paper bytes or executable repository verified | REPRODUCTION_BLOCKED |

Detailed authors, URLs, revisions, licenses, workloads, security handling, and
exclusion reasons are machine-readable in
`docs/evidence/external_autotuner_comparison_v2/landscape.csv` and
`official_sources.json`. Publication presence is not treated as artifact
availability, and an artifact build is not treated as exact workload
equivalence.

## Implementation requirement

1. Freeze Sobel, Harris, MLP-100, and LeNet-5-small contracts before any
   external build result is observed. Each contract binds the graph formula,
   coefficients or model weights, operation order, preprocessing, output
   decision, validation/audit split, and source digests.
2. Attempt the eight required artifacts with at most three independent
   build-only recoveries. Missing artifacts, licenses, hardware, or proprietary
   dependencies produce explicit reason codes; algorithm semantics are never
   patched.
3. Keep native and common-executor results separate. Native time describes an
   official runtime under its own objective. Headline latency requires
   `PORTABLE_EXACT`, including graph, operation order, scale schedule,
   rescale/modswitch/relinearization, LogN, Q/P, packing, and output semantics.
4. Apply the same FlipGuard decision gate to provider candidates only when the
   provider output exposes enough information for security admission and exact
   execution. An unparseable or semantically incomplete plan fails closed.
5. DaCapo, HALO, ReSBM, and Orbit are `NOT_APPLICABLE_NO_BOOTSTRAP` on the four
   frozen workloads unless those workloads naturally require bootstrapping.
   No depth is added to manufacture applicability.
6. Native absolute latencies are never ranked across runtimes. Missing values
   remain `NR` or `NOT_EVALUATED`, rather than being copied from a paper onto
   this host's result table.

## Falsification test

The broad comparison claim is blocked if any headline arm changes model
weights, activation, pooling, packing, decision output, or input set; if a
native cross-runtime latency is presented as a common-host win; if an
inadmissible Security-V2 candidate is executed as a formal result; if a
bootstrap workload is manufactured post hoc; if a build patch changes an
algorithm; or if a system without an official artifact is counted as
reproduced. Fewer fair baselines is a valid outcome. A larger count obtained by
relaxing equivalence is not.
