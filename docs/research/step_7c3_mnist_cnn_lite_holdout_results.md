# Step 7C.3 MNIST CNN-Lite Holdout Results

Status: `SUPPORTED` within the predeclared scalar-replicated MNIST
digit-0-vs-1 CNN-lite scope on 2026-07-30. Structural generalization remains
`PARTIALLY_SUPPORTED`, and `paper_claim_allowed=false`.

The immutable protocol is
`docs/research/step_7c3_mnist_cnn_lite_holdout_protocol.md`. It was committed
before input materialization, graph-adapter implementation, or encrypted
execution. This result document does not alter that protocol.

## Frozen Task

The official MNIST train/test boundary is retained. Digit 0 and digit 1 images
are transformed from 28x28 pixels to sixteen client-side 7x7 block means. The
encrypted graph evaluates four shared 2x2 valid convolutions, square
activations, and a learned linear binary head. Each of the sixteen inputs is
scalar-replicated in a separate ciphertext; the graph uses no rotations.

The deterministic plaintext model was trained only on the official training
partition after excluding the predeclared development and
configuration-validation rows. The official test rows used by the locked
audit were not used for training, scaling, synthesis, repair, or selection.

| Plaintext result | Value |
|---|---:|
| Training accuracy | 12008/12165 (0.987094) |
| Development accuracy | 249/250 (0.996) |
| Configuration-validation accuracy | 245/250 (0.980) |
| Locked-audit accuracy | 248/250 (0.992) |

Classification accuracy is descriptive task context, not CKKS
decision-integrity evidence.

## Frozen Inputs And Policy

| Artifact | Identity |
|---|---|
| Official source archive | `sha256:fe4410d8dbb50f6db6482b187557c5cb8bccfbcec74eeb6abc47c858f4ffab78` |
| Extraction/training policy | `sha256:06c795514837759cfb8a75a0390964f1e3cf252ceda233ee42b2de3023a8bab5` |
| Model | `sha256:28f673795c1982eb20d9cf156e527a5d61d74c2d674fc75f70dcca7b4876cf4e` |
| Direct Policy V2 | `sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603` |
| Security Policy V2 | `sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055` |

Source replay rebuilds the model and both evaluated CSVs byte-for-byte. The
adapter ID is `mnist_cnn_lite_scalar_replicated_graph_adapter_v1`; it is an
explicit graph extension outside the Direct Policy V2 supported-model table
and changes none of the frozen policy constants.

Static graph facts are multiplicative depth 1, three consumed rescale levels,
terminal scale exponent 2, five required Q primes, and zero rotations.

## Execution Provenance

| Property | Value |
|---|---|
| Predeclared protocol commit | `a85acca1aad301927246492b83a5b57122f8698c` |
| Frozen input commit | `c7b5b3f317d427107740d4be30098c12aa6d1cac` |
| Execution commit | `515d5dd680b09dfb454b5d4b900ab7f52c84373e` |
| Execution-source digest | `sha256:3d3b1c8bc2e3c140ebad0673861e9f3593642393b751d3ccbba76190ab2032fe` |
| Autotune binary | `sha256:963eef36588913024ba378f34bce0a1fedee14ed1876e5ee591f5730f5c0dffc` |
| Audit binary | `sha256:25d6df614eaac06350b0678c9ae75f14472be490a421fb668bae850ff7502d34` |
| Run manifest | `sha256:2a7b77721714cdc8944d09b106d6d967f42c9be0e49854ec0e602533d73b21ec` |

Before encrypted execution, a short-hash expansion error in the initial
manifest was classified as `RECOVERABLE_IMPLEMENTATION_FAILURE`. No encrypted
execution had begun. The invalid manifest is preserved in the evidence pack,
the full commits were resolved with Git, and the corrected manifest passed the
pre-execution provenance gate.

## Configuration Validation

| Property | Result |
|---|---:|
| Images | 250 |
| Outcome | `SELECTED` |
| Trials / repairs | 1 / 0 |
| Selected candidate | `synth_analysis_minimum_rescale_N13_Q5_S20_e0e2cacc6372` |
| Parameters | `N13 / Q5 / scale20` |
| LogQ / LogP / LogQP | 103 / 30 / 133 |
| Security V2 cap / headroom | 214 / 81 bits |
| Fresh key runs | 3 |
| Encrypted sample evaluations | 750 |
| Certifiable / ambiguous images | 250 / 0 |
| Flips / violations | 0 / 0 |
| Maximum absolute error | 0.00687752 |
| Maximum normalized budget usage | 0.221977 |
| Mean / median / p95 total per image | 803.70 / 744.50 / 1186.12 ms |

The first synthesized literal passed both the ciphertext-Q and
evaluation-key-QP Security V2 checks and was SAFE, so the frozen first-SAFE
rule stopped after one trial.

## Locked Audit

| Property | Result |
|---|---:|
| Official-test images | 250 |
| Candidate identity | byte-identical |
| Outcome | `LOCKED_AUDIT_PASS` |
| Fresh key runs | 3 |
| Encrypted sample evaluations | 750 |
| Certifiable / ambiguous images | 250 / 0 |
| Flips / violations | 0 / 0 |
| Maximum absolute error | 0.00711927 |
| Maximum normalized budget usage | 0.364669 |
| Mean / median / p95 total per image | 753.87 / 711.23 / 1137.06 ms |
| Retuning | 0 |
| Policy modifications after audit | 0 |

## Evidence And Claim Boundary

Frozen evidence:

```text
docs/evidence/non_tabular_mnist_cnn_lite_holdout_v1/
manifest sha256:de43a2e784d05f6901f87e9f5e7d4e499528dc65a14ed959e4d2665f088482d1
```

The deterministic verifier reconstructs the pack and recomputes all 1,500
image-by-key observations from the bound input CSVs. It also checks source
closure, binaries, policies, candidate identity, Q/QP admission, partition
separation, and every aggregate.

This result supports direct synthesis and no-retuning audit replay for one
learned scalar-replicated CNN-lite binary graph. It does not support packed
CNN performance, general LeNet configuration, arbitrary CNN graphs,
multiclass encrypted argmax, improved classification accuracy, or universal
autotuning. The earlier `mlp_square_poly3` audit rejection also remains part
of the structural evidence; this successful extension does not erase it.
