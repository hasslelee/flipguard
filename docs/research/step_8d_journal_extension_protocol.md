# Step 8d: Journal Multiclass Extension Protocol

## Reviewer concern

FlipGuard RC2 is a complete controlled study, but its primary 5-dataset by
2-graph matrix is concentrated on scalar threshold decisions. It does not by
itself establish that direct synthesis and decision-integrity admission apply
to a standard ten-class architecture with many affine outputs or to a
convolutional graph. The journal extension must answer that question without
retuning Security Policy V2, Direct Policy V2, the primary margin-utilization
cap, or any frozen RC2 result.

## Literature precedent

HECATE and ELASM use an MNIST MLP with `784x100` and `100x10` affine layers
and a square activation. HECATE describes its LeNet benchmark as the LeCun
LeNet-5 graph with square activation and changes the second fully connected
layer width to 64. ELASM reuses the same benchmark family. Their compiler
evaluations use packed ciphertexts and a random MNIST input, so they establish
the model-family precedent but not FlipGuard's 1,000-image finite
decision-integrity protocol.

Primary sources:

- [HECATE author copy](https://www3.cs.stonybrook.edu/~dongyoon/papers/CGO-22-HECATE.pdf),
  CGO 2022, DOI `10.1109/CGO53902.2022.9741265`.
- [ELASM official proceedings](https://www.usenix.org/conference/usenixsecurity23/presentation/lee-yongwoo),
  USENIX Security 2023, pages 4697-4714.
- LeCun et al., *Gradient-Based Learning Applied to Document Recognition*,
  Proceedings of the IEEE 86(11), 1998.
- [FHE-Agent preprint record](https://arxiv.org/abs/2511.18653), preprint
  status as of this protocol freeze.

## Implementation requirement

### Immutable bindings

- Security policy: `security_guidelines_cic2025_table5_2_ternary_128_v2`,
  digest `sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055`.
- Direct policy constants: `flipguard_direct_synthesis_policy_v2`, digest
  `sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603`.
- Operational margin-utilization cap: `rho=0.5`.
- Gap floor: `0.001`.
- Maximum encrypted trials: `4`.
- Fresh-key repetitions: `3`.
- No model-specific literal lookup; no audit-driven model or configuration
  change.

The journal adapters reuse the frozen policy constants but are not added to
the V2 policy's historical supported-model list. Sample slots are an explicit
extension packing adapter, `feature_ciphertext_sample_slots_v1`; it does not
silently redefine the frozen `scalar_replicated_per_ciphertext_v1` scope.

### Decision-integrity contract v2

For plaintext logits `z=(z_1,...,z_K)`, let `c*=argmax_k z_k`, with the lowest
class index used only as a deterministic representation tie break. Let
`zhat_k=z_k+Delta_k` and `|Delta_k|<=B_k`. The proposition is:

`z_c* - z_j > B_c* + B_j` for every `j != c*` implies
`argmax_k zhat_k=c*`.

Proof: for every challenger `j`,

`zhat_c* - zhat_j = (z_c* - z_j) + Delta_c* - Delta_j`

`>= (z_c* - z_j) - |Delta_c*| - |Delta_j| > 0`.

Thus the encrypted top class is strictly above every challenger. Equality is
not admitted because it proves only a non-negative approximate gap; a tie can
change the deterministic class index. A plaintext tie has zero top-two gap and
belongs to `V_amb`. NaN and infinity in logits or bounds are rejected.

With a uniform per-logit bound `B`, the sufficient condition is `2B<g(x)`,
where `g=z_top1-z_top2`. The operational reserve policy requires the observed
top/challenger error sum to be strictly below `rho` times its plaintext gap.
The synthesis budget is therefore `rho*g_min/2` per logit over `V_cert`.

### Frozen models

`mnist_mlp_square_784_100_10_v1`:

- input: 784 pixels normalized to `[0,1]`;
- affine `784 -> 100`;
- square activation;
- affine `100 -> 10` logits;
- softmax cross-entropy is training-only and is not in the encrypted graph.

`mnist_lenet5_small_square_v1`:

- input: MNIST `28x28`, zero padded to `32x32`;
- C1: 6 valid `5x5` convolution channels, then square;
- S2: `2x2` average pooling with stride 2;
- C3: 16 valid `5x5` convolution channels, then square;
- S4: `2x2` average pooling with stride 2;
- affine `400 -> 120`, then square;
- affine `120 -> 64`, then square;
- affine `64 -> 10` logits.

The name denotes an FHE-compatible LeNet-5-small adapter. It does not denote
ReLU, max pooling, packed production inference, or the original partially
connected C3 map. Those differences are explicit.

### Frozen training

- source: byte-pinned OpenML MNIST ARFF gzip corresponding to official 60,000
  train and 10,000 test rows;
- test rows never affect weights, epoch count, learning rate, architecture, or
  preprocessing;
- official train rows are deterministically divided into 55,000 model-training
  and 5,000 plaintext model-validation rows by label-stratified SHA-256 rank;
- deterministic Adam, batch size 64, eight fixed epochs;
- MLP learning rate `0.001`, LeNet learning rate `0.0005`;
- Adam betas `0.9/0.999`, epsilon `1e-8`, L2 `1e-5`;
- deterministic SplitMix64 initialization and epoch shuffle;
- validation accuracy is descriptive; there is no early stopping or
  post-result hyperparameter selection;
- plaintext accuracy is reported once over all 10,000 official test images.

### Frozen encrypted input split

Within each test-set class, rows are ordered by SHA-256 over the policy ID,
label, and official row index. Ranks 0-49 form configuration validation and
ranks 50-99 form locked audit. Therefore each role contains 50 rows per class,
500 rows total, with zero overlap. The same 1,000-image manifest is shared by
both models. Gap-bin boundaries are derived from configuration validation only
and replayed byte-identically on locked audit.

### Static feasibility before encrypted execution

The preflight must bind the graph-operation counts, multiplicative depth,
required levels, synthesized Q/P/LogN, Security-V2 admission, required 500
slots, exact model/source/split digests, estimated runtime, available disk,
resumable ledger, and multiclass theorem tests. No encrypted command may run
before the protocol pack and its `SHA256SUMS` are committed and pushed.

Candidate arms are direct synthesis, the Security-V2-compliant bounded
catalog, graph-only fixed logit tolerance, one-shot direct, and latency-only
without certification. The formal comparator is a security-compliant bounded
catalog, never a global oracle.

## Falsification test

The extension records, rather than repairs away, `PLAN_UNSUPPORTED`,
`SECURITY_INADMISSIBLE`, `FAILED`, `REJECTED`, `NO_SAFE`, trial-budget
exhaustion, locked-audit argmax flip, and reserve-policy rejection. Any source
or split overlap, test-driven model choice, audit-driven retuning, policy
digest drift, inadmissible formal candidate, non-finite logit, missing
negative row, or candidate-identity mismatch is an integrity block. A valid
negative scientific result lowers the extension claim and does not modify RC2.
