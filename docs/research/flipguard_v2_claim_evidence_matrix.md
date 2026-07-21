# FlipGuard V2 claim-evidence matrix

Status values:

- FROZEN_PRELIMINARY
- IMPLEMENTED_NOT_EVALUATED
- PARTIALLY_SUPPORTED
- UNSUPPORTED
- REQUIRED_FINAL
- NEGATIVE_CONTROL
- REGRESSION_ONLY

| Claim or component | Current evidence | Current status | Reviewer objection | Evidence required before final claim | Forbidden overclaim |
|---|---|---|---|---|---|
| Certify-or-reject state machine works | Unit tests and observed tabular importer | IMPLEMENTED_NOT_EVALUATED | Software correctness is not empirical safety | Mutation tests, malformed artifact tests, end-to-end failure cases | “The framework is universally safe” |
| Existing tabular selection preserves decisions | Frozen 10-workload observed snapshot, V_cert=2645, V_amb=61 | FROZEN_PRELIMINARY | One fixed split and preliminary policy constants | Independent validation/audit sets, multiple seeds, independent keys | “General decision preservation” |
| Latency-only tuning can be unsafe | Latency-only candidate rejected in all 10 current workloads | PARTIALLY_SUPPORTED | Candidate space and workload family may be constructed favorably | Generated candidate spaces and modernized graph suite | “All latency tuners are unsafe” |
| FlipGuard improves latency | MLP-square preliminary speedups; Linear has zero improvement | PARTIALLY_SUPPORTED | Half the workload matrix has no improvement | Primary-model table separated from negative controls; final multi-seed audit | “Ten workloads all improve” |
| Linear model evidence | Five datasets with zero selected speedup | NEGATIVE_CONTROL | Workload count inflation | Use only as shallow-depth/no-headroom control | “Five successful optimized workloads” |
| Core workload evidence | Six legacy probes | REGRESSION_ONLY | Too few or synthetic inputs | Rebuild with complete predeclared datasets if used in main evaluation | “Core suite proves generality” |
| Analytical proof contract | Scoped proof metadata and strict validation | IMPLEMENTED_NOT_EVALUATED | Metadata does not make the numeric bound sound | Sound primitive derivation and underestimation audit | “Analytical guarantee implemented” |
| Conditional linear_poly3 envelope | Arithmetic propagation tests | IMPLEMENTED_NOT_EVALUATED | Primitive residuals are still assumed | CKKS primitive derivation tied to profile and path | “End-to-end CKKS bound” |
| CKKS profile facts | Eleven profile digests, certificate_eligible=false | IMPLEMENTED_NOT_EVALUATED | Facts alone are not a guarantee | Derivation using exact parameter semantics | “NoiseBound is output error” |
| Analytical execution scope | Finite set, declared box, empirical range contract | IMPLEMENTED_NOT_EVALUATED | No real workload scope builder yet | Exact artifact/input/graph/profile/path builder | “Current test range is a domain guarantee” |
| HYBRID certification | Policy and proof plumbing exist | UNSUPPORTED | No sound bound producer | Bound calculator, proof export, observed<=predicted audit | “HYBRID results available” |
| Planner reduces evaluation work | Existing exploratory planner subset summaries | PARTIALLY_SUPPORTED | No general oracle recall/regret study | Exhaustive oracle, safe recall, optimum recall, regret, overhead | “Planner finds global optimum” |
| Automatic candidate generation | Current fixed profile catalog and resolver | UNSUPPORTED | Fixed catalog is not general autotuning | Graph-derived chain/scale/logN/path generation | “Fully automatic tuner” |
| Candidate feasibility pre-check | Partial planner/resolver behavior | PARTIALLY_SUPPORTED | May miss backend-specific failure modes | Exact level/security/operation feasibility model | “All generated candidates execute” |
| Generality across computation graphs | Linear, MLP-square, Sobel, Harris development paths | PARTIALLY_SUPPORTED | Legacy probes and shallow graph concentration | Deeper MLP, CNN-lite, modernized image protocols | “All models and datasets” |
| Robustness across dataset splits | random_state=42 artifacts | UNSUPPORTED | Single split may drive selection | Predeclared multi-split protocol | “Split-independent result” |
| Robustness across cryptographic randomness | Repeated current runs | UNSUPPORTED | Repetition dimensions are not separated | Independent keys and encryption randomness | “Key-independent safety” |
| Safety-factor choice | alpha=0.5 current default | UNSUPPORTED | Arbitrary policy constant | Predeclared sensitivity study and policy interpretation | “0.5 is theoretically optimal” |
| Margin-floor choice | margin_floor=0.001 current default | UNSUPPORTED | Arbitrary ambiguity cutoff | Coverage/latency/NO_SAFE sensitivity study | “0.001 is universally correct” |
| Final latency claims | Mean/std fields in preliminary summaries | PARTIALLY_SUPPORTED | Warm-up, p95, process variance incomplete | Frozen latency protocol with raw records | “Stable production latency” |
| Artifact reproducibility | Frozen observed evidence v1 and verifier | PARTIALLY_SUPPORTED | Does not cover final V2 claims | One-command full V2 runner and verifier | “Complete reproducibility achieved” |

## Immediate development dependency

Before implementing the finite-set analytical scope builder:

1. freeze this reviewer protocol;
2. bind every new implementation to a matrix row;
3. state the reviewer concern addressed;
4. state the falsification condition;
5. preserve preliminary and final evidence separately.

## Immediate analytical sequence

1. exact finite-set digest builder;
2. exact operation-graph specification and digest;
3. primitive derivation scope;
4. probabilistic or deterministic primitive error model;
5. linear_poly3 bound calculator;
6. observed-error versus predicted-bound audit;
7. proof export;
8. HYBRID integration;
9. MLP-square propagation.

No HYBRID certificate may be issued before steps 1–7 pass.
