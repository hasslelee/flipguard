# Multiclass Decision-Preservation Proposition

Let the plaintext logits be `z=(z_1,...,z_K)`, and let `c*` be the unique
plaintext argmax. Let `zhat_k=z_k+Delta_k`, with finite class-wise bounds
`|Delta_k|<=B_k`. If, for every `j != c*`,

`z_c* - z_j > B_c* + B_j`,

then `argmax_k zhat_k=c*`.

For every competitor `j`, `zhat_c* >= z_c*-B_c*` and
`zhat_j <= z_j+B_j`. The strict premise therefore gives
`zhat_c* > zhat_j` for every competitor, so `c*` remains the unique encrypted
argmax. Under a uniform bound `B_k=B`, the top-two gap `g` yields the corollary
`2B<g`.

Equality is not admitted because it may produce an approximate tie. A
plaintext tie has zero top-two gap and belongs to the ambiguous region; a
lowest-index tie break is only a deterministic representation rule. Any NaN or
infinite logit or bound is `FAILED`. This proposition is sufficient but does
not itself instantiate an analytical CKKS error bound.
