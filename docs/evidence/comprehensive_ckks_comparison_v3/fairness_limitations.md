# Fairness Limitations

- Build/runtime smoke demonstrates artifact reachability, not benchmark reproduction.
- Native absolute latencies use different runtimes, graphs, packing, security assumptions, and hosts; they are never ranked across providers.
- Original-paper normalized values use each paper's own baseline and are not pooled.
- Model names such as LeNet, MLP, Sobel, and Harris do not establish graph identity.
- `PORTABLE_EXACT` requires graph, operation order, weights, preprocessing, packing, parameters, schedules, and output semantics to match.
- No external candidate met the E1/E2 common-executor gate. Missing measurements remain explicit states, never zero.
- The native feasible set was exhausted under official artifact, license, hardware, output, and workload constraints; this is not evidence of inferior algorithms.
- Security assumptions remain runtime-specific unless explicitly aligned.
- FlipGuard's fastest-stable result is bounded to declared candidates, finite inputs, and a measured host, not the global CKKS configuration space.
