# Step 8a: Evaluation Breadth Audit

## Reviewer concern

The controlled 5-dataset by 2-primary-graph design gives repeated,
source-bound evidence for FlipGuard's binary decision gate, but graph breadth
is narrower than compiler and neural-inference papers that include MLP,
LeNet, ResNet, or deeper programs. Merely adding dataset names would not answer
this objection; the extension needs a standard multiclass architecture and a
mathematically explicit argmax contract.

## Literature precedent

The table records only practices supported by a paper, official proceedings,
or an official conference program. `NR` means that the primary source does not
report a comparable count; it is not estimated.

| Work | Venue/year/status | Dataset | Model/graph | Input count | Correctness unit | Performance unit | Candidate/search space | Security setting | What FlipGuard already exceeds | What FlipGuard still lacks | Exact experimental practice adopted |
|---|---|---|---|---:|---|---|---|---|---|---|---|
| EVA | PLDI 2020 | synthetic vectors, image programs, ML examples | vector arithmetic programs including image and ML kernels | workload-dependent/NR | compiled-program output error | program latency | compiler-generated rescale/parameter plan | secure parameter generation; paper setting | source/split provenance, reject/abstain, locked audit | packed-vector compiler breadth | explicit IR facts and generated configuration provenance |
| HECATE | CGO 2022 | MNIST, synthetic regression, 64x64 image kernels | Sobel, Harris, MLP 784-100-10, LeNet-5, regression | one random MNIST input for DL; 4,096 image pixels; 16,384 regression inputs | maximum error bound and RMSE | actual program latency | 36 waterlines; scale-management exploration | 128-bit; SEAL 3.5.9 | finite decision rows and no-retuning audit | standard multiclass MLP/LeNet and packed scale | exact MLP shape, LeNet family, real execution, graph-operation accounting |
| ELASM | USENIX Security 2023 | MNIST, synthetic regression, image kernels | 10 ML/DL benchmarks including MLP and LeNet | one random MNIST input for DL; 4,096/16,384 for other groups | output error and inference accuracy case study | actual latency and Pareto curve | 12,000 scale plans, waterlines 2^15 to 2^50 | 128-bit; SEAL 3.5.9 | per-row margin admission, NO_SAFE, audit replay | error-latency baseline at standard graph scale | separate numerical error and latency, publish full candidate/search accounting |
| HECO | USENIX Security 2023 | microbenchmarks and application kernels | imperative FHE programs and compiler transformations | NR | semantic/compiler validation | end-to-end and kernel latency | rewrite/lowering alternatives | backend-dependent secure parameters | policy/evidence provenance and explicit decision gate | general compiler/program coverage | distinguish compiler transformations from admission-layer claims |
| DaCapo | USENIX Security 2024 | CIFAR-family deep inference graphs | ResNet-20/44, AlexNet, VGG16, SqueezeNet, MobileNet | model inference; exact image count NR in headline evaluation | approximation error constraint | actual latency and estimated-cost agreement | 52-662 placement candidates depending on model/activation | RNS-CKKS, declared secure settings | locked literal audit and finite decision outcomes | bootstrapping and deep graph support | operation counts, candidate counts, estimator-vs-runtime checks |
| AutoFHE | USENIX Security 2024 | CIFAR-10/CIFAR-100 | ResNet and VGG CNN families | encrypted evaluation scope NR in proceedings summary | model accuracy | encrypted inference latency | mixed-degree activation and bootstrap multi-objective search | RNS-CKKS | sample-level admission and explicit abstention | trained standard CNN breadth and bootstrap co-design | report accuracy-latency trade-off without claiming per-sample equivalence |
| FHE-Agent | 2025 arXiv preprint | MNIST and CIFAR-10 recipes | MLP, LeNet, LoLa, AlexNet | validation subset; exact count NR | accuracy, MAE, precision bits, feasibility | per-input FHE time excluding keygen | ten one-shot prompts plus gated multi-fidelity repair | estimated >=128-bit; Orion/Lattigo 5.0.2 | deterministic policy, exact digests, locked audit | comparable standard graphs and practical agent baseline | static pruning before encrypted trials, explicit failed configurations, fixed trial budget |
| Application-Aware Approximate HE | IACR Communications in Cryptology, published article | formal application domains | circuit plus input-domain specification | not empirical | application-bound correctness/security definitions | not a performance benchmark | application-specific parameter generation/validation | IND-CPAD-oriented formal model | executable finite evidence and provenance | instantiated analytical application-domain certificate | bind circuit, input scope, estimator, and runtime validation without claiming formal equivalence |
| Precise Max-Pooling on FHE | JKIISC 33(3), 2023 | synthetic max inputs | composite max approximation for 4+ values | NR | theoretical and measured approximation precision | sub-operation latency | focused polynomial construction | RNS-CKKS | end-to-end decision workflow and artifact pack | primitive-level theorem depth | present exact theorem, approximation boundary, and implementation timing concisely |
| CKKS MultiMax implementation | CISC-S 2025, official program; NSR director award (excellent paper) | Softmax/MultiMax comparison inputs | CKKS MultiMax and recent HE Softmax methods | proceedings paper count NR | approximation/comparison quality | CKKS implementation performance | focused function alternatives | CKKS | broader protocol and reproducibility evidence | focused primitive clarity and concise comparison | include one precise proposition, a standard benchmark, and a compact reviewer-facing comparison |

Primary-source anchors include the ACM DOI for EVA, IEEE DOI for HECATE,
USENIX proceedings pages for ELASM/HECO/DaCapo/AutoFHE, IACR ePrint
`2024/203`, KCI DOI `10.13089/JKIISC.2023.33.3.375`, and the official 2025
KIISC summer program. The MultiMax item is conference metadata, not a claim
about a journal publication or a best-paper grand prize.

## Implementation requirement

The existing primary matrix is retained as the controlled binary study. The
mandatory extension adds the exact HECATE/ELASM MLP family, an explicitly
adapted square/average-pool LeNet-5-small, a ten-class argmax proposition,
1,000 deterministic MNIST test rows, three fresh-key repetitions, and a
disjoint no-retuning locked audit. Evaluation must report graph operations,
candidate trials, security filtering, class and gap-bin results, and negative
outcomes. No claim may convert one finite standard benchmark into arbitrary
CNN or distribution-wide generalization.

## Falsification test

The breadth objection remains unresolved if either mandatory graph is only a
plaintext simulation, if the encrypted scope is not source-replayable and
class-balanced, if argmax is reduced to ten unrelated binary thresholds, if a
locked-audit result changes the model/configuration, or if the final text calls
the original 50 rows independent workloads. Missing primary-source counts are
reported as `NR`, never filled from snippets or secondary summaries.

