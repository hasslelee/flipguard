# Step 8a: Evaluation Breadth Audit

## Reviewer concern

The controlled 5-dataset by 2-primary-graph design gives repeated,
source-bound evidence for FlipGuard's binary decision gate, but graph breadth
is narrower than compiler and neural-inference papers that include MLP,
LeNet, ResNet, or deeper programs. Merely adding dataset names would not answer
this objection; the extension needs a standard multiclass architecture and a
mathematically explicit argmax contract.

Final audit verdict for the existing primary is
`VALID_CONTROLLED_PRIMARY__INSUFFICIENT_ALONE_FOR_MULTICLASS_BREADTH`. It is
valid evidence for the frozen binary threshold contract, direct synthesis,
abstention, and no-retuning protocol. It is not, by itself, evidence for a
ten-class argmax contract, convolutional graph scale, or arbitrary model
generalization. The journal extension fills that specific gap without
relabeling or discarding the primary study.

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
| DaCapo | USENIX Security 2024 | CIFAR-10 | ResNet-20/44, AlexNet, VGG16, SqueezeNet, MobileNet; ReLU/max-pool and SiLU/average-pool variants | 1,000 images for accuracy validation; latency per image | plaintext-vs-CKKS classification accuracy and approximation error | actual per-image latency and estimated-cost agreement | 52-662 placement candidates depending on model/activation | GPU RNS-CKKS/HEaaN, declared secure settings | locked literal audit and finite decision outcomes | bootstrapping and deep packed graph support | operation counts, candidate counts, 1,000-image accuracy check, estimator-vs-runtime checks |
| AutoFHE | USENIX Security 2024 | CIFAR-10/CIFAR-100 | ResNet-20/32/44 and VGG11 families | 10,000 encrypted validation images per reported dataset evaluation; 96-image latency batches | ciphertext top-1 accuracy | amortized per-image encrypted latency | mixed-degree activation/bootstrap multi-objective search; 10 generations, population 10-40, offspring 6x population | RNS-CKKS, 128-bit target | sample-level decision admission, explicit abstention and source replay | trained standard CNN breadth, packing and bootstrap co-design | report full encrypted accuracy scope separately from latency batches and avoid per-sample equivalence claims |
| FHE-Agent | 2025 arXiv preprint | MNIST and CIFAR-10 recipes | MLP, LeNet, LoLa, AlexNet | validation subset; exact count NR | accuracy, MAE, precision bits, feasibility | per-input FHE time excluding keygen | ten one-shot prompts plus gated multi-fidelity repair | estimated >=128-bit; Orion/Lattigo 5.0.2 | deterministic policy, exact digests, locked audit | comparable standard graphs and practical agent baseline | static pruning before encrypted trials, explicit failed configurations, fixed trial budget |
| Application-Aware Approximate HE | IACR Communications in Cryptology, published article | formal application domains | circuit plus input-domain specification | not empirical | application-bound correctness/security definitions | not a performance benchmark | application-specific parameter generation/validation | IND-CPAD-oriented formal model | executable finite evidence and provenance | instantiated analytical application-domain certificate | bind circuit, input scope, estimator, and runtime validation without claiming formal equivalence |
| Precise Max-Pooling on FHE | JKIISC 33(3), 2023 | synthetic max inputs | composite max approximation for 4+ values | NR | theoretical and measured approximation precision | sub-operation latency | focused polynomial construction | RNS-CKKS | end-to-end decision workflow and artifact pack | primitive-level theorem depth | present exact theorem, approximation boundary, and implementation timing concisely |
| Privacy-Preserving Federated Learning in Non-IID Environments | JKIISC 36(1), 2026 | non-IID federated-learning partitions | CKKS-protected local model aggregation | paper-specific/NR for a comparable encrypted inference count | federated model utility and privacy-preserving aggregation | application-level experiment | one declared federated framework, not a configuration search | CKKS application setting | parameter-selection provenance and sample-level decision admission | distributed/application deployment study | keep application scope, correctness unit, and performance unit explicit |
| CKKS MultiMax implementation | CISC-S 2025, official program; NSR director award (excellent paper) | Softmax/MultiMax comparison inputs | CKKS MultiMax and recent HE Softmax methods | proceedings paper count NR | approximation/comparison quality | CKKS implementation performance | focused function alternatives | CKKS | broader protocol and reproducibility evidence | focused primitive clarity and concise comparison | include one precise proposition, a standard benchmark, and a compact reviewer-facing comparison |

Primary-source registry:

| Work | Primary source | Point checked directly |
|---|---|---|
| EVA | [Microsoft Research publication page](https://www.microsoft.com/en-us/research/publication/eva-an-encrypted-vector-arithmetic-language-and-compiler-for-efficient-homomorphic-computation/) and its ACM DOI link | PLDI 2020 status, compiler scope, image-processing examples, CHET comparison |
| HECATE | [author-hosted CGO paper](https://www3.cs.stonybrook.edu/~dongyoon/papers/CGO-22-HECATE.pdf), DOI `10.1109/CGO53902.2022.9741265` | `784x100x10` square MLP, LeNet family, 36 waterlines, explored-plan counts |
| ELASM | [USENIX Security 2023 proceedings](https://www.usenix.org/conference/usenixsecurity23/presentation/lee-yongwoo) | ten benchmarks, error-latency objective, scale-plan search and publication metadata |
| HECO | [USENIX Security 2023 proceedings](https://www.usenix.org/conference/usenixsecurity23/presentation/viand) | imperative-program compiler scope and end-to-end transformation claim |
| DaCapo | [USENIX Security 2024 proceedings](https://www.usenix.org/conference/usenixsecurity24/presentation/cheon) | bootstrapping-placement objective; Table 3's 1,000-image accuracy validation; Table 5's 52-662 candidate counts |
| AutoFHE | [USENIX Security 2024 proceedings](https://www.usenix.org/conference/usenixsecurity24/presentation/ao) | Section 4 search settings, Table 4's 10,000 encrypted-image accuracy scope and 96-image latency protocol |
| FHE-Agent | [arXiv preprint record](https://arxiv.org/abs/2511.18653) | preprint status, MLP/LeNet/LoLa/AlexNet scope, multi-fidelity repair framing |
| Application-Aware Approximate HE | [IACR ePrint 2024/203](https://eprint.iacr.org/2024/203) | application-domain formalization, ASL, CIC 2026 publication metadata |
| Security Guidelines | [IACR Communications in Cryptology article](https://cic.iacr.org/p/1/4/26) | published security-reference status; FlipGuard's exact table binding remains in Security Policy V2 |
| Precise Max-Pooling | [KCI record](https://www.kci.go.kr/kciportal/landing/article.kci?arti_id=ART002968399), DOI `10.13089/JKIISC.2023.33.3.375` | JKIISC venue, focused primitive scope and publication metadata |
| Non-IID federated learning with HE | [KCI record](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003304308), DOI `10.13089/JKIISC.2026.36.1.191` | JKIISC venue, CKKS-protected federated application scope and publication metadata |
| CKKS MultiMax | [official KIISC CISC-S 2025 program book](https://kiisc.or.kr/bbs/downloadBoardImage?uploadedFileId=12693) | title and `우수`/국가보안기술연구소 소장상 metadata only |

The MultiMax row is conference-program metadata. It is not treated as a
journal publication, a full experimental report, or a best-paper grand prize.
Counts not recoverable from the primary paper remain `NR` rather than being
filled from a search snippet.

Count-critical PDF replay metadata (retrieved 2026-08-02) is recorded below.
The hashes bind the exact primary-source bytes used to check the table; the
PDFs are not vendored into the repository.

| Work | Primary PDF SHA-256 | Exact location checked | Replayed fact |
|---|---|---|---|
| HECATE | `0ae9ad193c58cddd0da4fca37a5033a379256fea0962c9de7a34fb1d4f46b6cb` | Section VII-A and benchmark description | MLP `784x100`/`100x10`; 4,096 image pixels; 16,384 regression inputs; one random MNIST input for DL; 36 waterlines |
| ELASM | `8c1ad29a2b8e7f43ed265a55576dc73c0569bf7d354dfd202746579f338b605f` | Sections 7.1-7.2 | 4,096/16,384 non-DL inputs; one random MNIST input for DL; 12,000 scale-plan samples; `N=2^15` setting |
| DaCapo | `20c7e84518987441d6b08ad1943f8cf3953423b70db7d64b5382859e764d0803` | Table 3 and Table 5 | 1,000 CIFAR-10 images for accuracy validation; 52-662 candidates across the reported networks |
| AutoFHE | `f340cc685e8559a86bcd7f2769f7550271dcac957fcd777aca9665293d95e8f7` | Section 6 parameters and Tables 4-5 | 10 generations; populations 10/20/30/40; offspring `6x`; 10,000 encrypted validation images; 96-image latency unit |
| FHE-Agent | `347360507b510bfd66fa16abbd1d409f132593af282da1c5022721e830d82511` | Sections 4-5 and Table 1 | Orion/Lattigo v5.0.2 prototype; MLP/LeNet/LoLa/AlexNet; ten one-shot prompts; multi-fidelity static/light/full evaluation; preprint status |

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
