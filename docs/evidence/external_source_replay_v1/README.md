# External Source Replay Evidence V1

This pack preserves one failed clean-runner recovery and one successful
replay from byte-pinned official MNIST and BSDS500 sources. The successful
run reproduces the CNN-lite, Sobel, and Harris deterministic exporters and
three static graph contracts from a clean GitHub runner.

The recovery is retained: MNIST export succeeded but the replay driver
matched the wrong success token, while the verified BSDS500 archive had not
been extracted before the Sobel and Harris exporters ran.

This evidence does not replay ignored encrypted execution ledgers and does
not perform CKKS trials, key runs, sample evaluations, or policy retuning.
`paper_claim_allowed=false`.
