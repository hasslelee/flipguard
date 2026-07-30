# EVA External Adapter Replay V1

This immutable pack preserves an actual Microsoft EVA v1.0.1 compiler output
and exact Microsoft SEAL v3.6.4 modulus materialization for the predeclared
seed-0 Iris `linear_poly3` program.

The compiler replay succeeded and the exact concrete candidate passed
Security Policy V2. It was not encrypted because EVA produced only three
ciphertext Q primes while the frozen FlipGuard Lattigo lowering requires
seven. The result is `BLOCKED_GRAPH_COMPATIBILITY`; no prime was padded and no
compiler option, scale, frozen policy, or graph lowering was retuned.

The three preceding implementation failures are retained in
`recovery_log.json`. They occurred before compiler output evaluation and did
not modify the predeclared contract or upstream cryptographic source bytes.
