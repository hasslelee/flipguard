# FlipGuard Research Completion Checkpoint V4

This non-overwriting checkpoint binds the 19 packs in checkpoint V3 and the
external source replay pack. It performs no CKKS execution, changes no frozen
policy, and promotes no paper claim.

Byte-pinned official MNIST and BSDS500 inputs, three deterministic exporters,
and three static graph contracts replay successfully on a clean GitHub runner.
Ignored encrypted execution ledgers were not replayed, so external source and
artifact reproducibility claims remain scope-limited.

`paper_claim_allowed=false`.
