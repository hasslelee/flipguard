# Initial Configuration Formula Trace

For the binary contract, `gamma_min` is the minimum strict margin `|f(x)-tau|` among configuration-selection inputs with margin greater than delta. The output budget is `B_out = rho * gamma_min`. For multiclass planning, the uniform per-logit budget is `B_out = rho * g_min / 2`, where `g_min` is the protected top-two gap; runtime certification still checks every competitor.

For the scalar IR path:

1. `S_G = sum_{v not input,const} s_v`.
2. `B_unit = B_out / S_G`.
3. `p = max(0, ceil(-log2(B_unit)))`.
4. `s = max(p + 3, 18, requested repair floor)`, with an upper policy clamp of 50 bits.
5. Output magnitude determines message bits. The first Q prime is `max(s + message_bits + 1 + 2, 18)`; later Q primes use scale-sized widths.
6. Required rescale levels plus any declared guard/repair levels determine Q-chain length. P contains one special prime of at least 30 bits and at least the first-prime width.
7. The smallest LogN in 12..15 that satisfies slot capacity and both Q and QP Security-V2 caps is admitted.
8. If the concrete backend literal is not NTT-feasible, the static rule raises scale one bit and repeats until valid or the 50-bit limit. This static retry occurs before encrypted B accounting.

The formula is implemented configuration generation, not an instantiated analytical error certificate.
