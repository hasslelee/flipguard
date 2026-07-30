# MNIST CNN-Lite Holdout Evidence V1

This pack freezes one predeclared scalar-replicated MNIST digit-0-vs-1
CNN-lite execution. The first synthesized candidate was SAFE on 250
configuration-validation images under three fresh keys and remained SAFE on
250 official-test locked-audit images under three new keys. No repair or
retuning occurred.

The result supports only the declared one-convolution, square-activation,
linear-head graph. It does not support packed CNN performance, general LeNet
configuration, arbitrary CNNs, multiclass encrypted argmax, or universal
autotuning. `paper_claim_allowed` remains false.
