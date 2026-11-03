# Step 7C.3 MNIST CNN-Lite Non-Tabular Holdout Protocol

Status: `PREDECLARED_NOT_EVALUATED` on 2026-07-30. This document freezes the
input, training, graph, selection, and audit protocol before the locked-audit
artifact is inspected. It is a research protocol, not a manuscript result.

## Research question

This extension asks whether the frozen Direct Policy V2 constants and
Security Policy V2 admission gate can configure a small learned convolutional
decision graph without model-specific parameter lookup:

```text
28x28 image
-> fixed non-overlapping 7x7 mean pooling
-> 4x4 scalar inputs
-> four shared 2x2 valid convolution filters
-> elementwise square activation
-> learned linear binary head
-> score >= 0
```

The task is MNIST digit 0 versus digit 1. This scope is deliberately narrower
than LeNet: it has one convolution layer, no encrypted pooling, no packed
spatial layout, no multiclass argmax, and no bootstrapping.

Primary precedents and boundaries:

- LeCun et al.'s official MNIST distribution defines 60,000 training and
  10,000 test images and motivates preserving that boundary:
  `https://yann.lecun.com/exdb/mnist/`.
- CryptoNets demonstrates polynomial, including square, activations for
  encrypted neural inference:
  `https://www.microsoft.com/en-us/research/wp-content/uploads/2016/04/CryptonetsTechReport.pdf`.
- AutoFHE jointly adapts polynomial activations and bootstrapping placement
  for substantially broader CNNs under RNS-CKKS:
  `https://www.usenix.org/conference/usenixsecurity24/presentation/ao`.
- FHE-Agent evaluates automated CKKS configuration on MLP, LeNet, LoLa, and
  AlexNet. FlipGuard therefore does not claim the first direct CNN
  configurator or universal graph support:
  `https://arxiv.org/abs/2511.18653`.

## Frozen source and roles

Source:

```text
results/source_datasets/mnist/mnist_784.arff.gz
sha256:fe4410d8dbb50f6db6482b187557c5cb8bccfbcec74eeb6abc47c858f4ffab78
```

Only digits 0 and 1 enter this task. Rows are ranked within label by
domain-separated SHA-256. The roles are fixed before model training:

| Role | Official partition | Rows per class | Total | Use |
|---|---|---:|---:|---|
| Model development | train | 125 | 250 | plaintext diagnostic only |
| Configuration validation | train | 125 | 250 | encrypted selection |
| Model training | train | remainder | source-dependent | training/scaling only |
| Locked audit | test | 125 | 250 | no-retuning audit |

The validation and audit units are distinct source images. Key repeats are
cryptographic repeats of an image, not independent statistical samples. With
250 audit images, zero observed failures would correspond to a descriptive
rule-of-three upper rate near 1.2%; no independent-population inferential claim
is made from that heuristic.

## Frozen input transform

Every 28x28 image is normalized by `pixel/255`. Each non-overlapping 7x7 block
is averaged, producing sixteen values in `[0,1]`. Pooling is a fixed client-side
materialization step and is replayed from the digest-bound ARFF source. The
encrypted graph receives sixteen scalar-replicated ciphertexts and performs no
rotations.

Extraction and training policy:

```text
ID: mnist_binary01_cnn_lite_export_v1
digest: computed from canonical policy JSON by the exporter
```

## Frozen model training

The model uses four shared 2x2 filters, stride one, valid padding, square
activation, and one linear score. All weights are trained from the official
training partition after excluding the model-development and
configuration-validation rows.

Training is deterministic:

| Item | Frozen value |
|---|---:|
| Optimizer | Adam |
| Epochs | 24 |
| Batch size | 64 |
| Learning rate | 0.01 |
| Beta 1 / Beta 2 | 0.9 / 0.999 |
| Epsilon | 1e-8 |
| L2 penalty | 1e-4 |
| Shuffle | SplitMix64 Fisher-Yates |
| Seed | `0x464c495047554152` |

After training, the linear head alone is multiplied by a positive scalar so
the maximum absolute training score is one. Neither model-development,
configuration-validation, nor locked-audit scores affect this scaling.
Locked-audit accuracy, margins, and CKKS results cannot modify the model,
graph adapter, Direct Policy, or candidate.

## Frozen policy boundary

Direct Policy V2 remains byte-identical:

```text
sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603
```

Security Policy V2 remains byte-identical:

```text
sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055
```

`cnn_lite_square_binary01` is not added to the Direct Policy V2 supported-model
table. A separately versioned graph adapter may reuse the frozen alpha `0.5`,
margin floor `0.001`, numerical repair `+4` bits, level repair `+1` Q prime,
maximum two added levels, maximum four encrypted trials, first-SAFE rule, and
NO_SAFE rule. No constant may be changed from the validation or audit result.

## Planned evidence

Before encrypted execution:

1. Rebuild the dataset and model byte-for-byte from the source.
2. Verify role separation, source identity, graph equivalence, and model
   serialization.
3. Derive the graph scale trace and Security V2 static admission.
4. Commit and push the implementation and immutable input artifacts.

Configuration validation then evaluates all 250 validation images with three
fresh keys per candidate, records every image-by-key score, and applies at
most four frozen-policy trials. Locked audit replays the selected literal on
all 250 official-test images under three new keys without synthesis or repair.

Success can support only this learned, scalar-replicated MNIST binary
CNN-lite graph. It cannot support packed CNN efficiency, general LeNet
configuration, arbitrary CNNs, image classification accuracy improvements, or
universal autotuning. Any `REJECTED`, `NO_SAFE`, or audit violation remains a
scientific result and lowers the corresponding claim.
