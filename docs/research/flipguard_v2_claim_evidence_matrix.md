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
| Planner reduces evaluation work | Step 7B.2 projection implementation and four-candidate smoke: SAFE recall 1, optimum recall 1, regret 0, pruning 0.5 for five alpha rows | IMPLEMENTED_NOT_EVALUATED | Smoke has one split/workload and cannot establish general planner quality | Full 1,100-candidate oracle comparison with safe recall, optimum recall, regret, false NO_SAFE, and overhead | “Planner finds global optimum” |
| Automatic candidate generation | Direct digest-bound synthesis of LogN/LogQ/LogP/scale; two split checkpoints selected 20/20 workloads and all frozen literals passed disjoint three-key locked audits without retuning | PARTIALLY_SUPPORTED | Current scope is three tabular forms, scalar-replicated packing, rescale-aware Lattigo v6, and two of five split seeds | Complete the five-split study, frozen-oracle comparison, and external providers | “Fully general automatic tuner” |
| Candidate feasibility pre-check | Lattigo-aware symbolic scale trace, 2024 HE security envelope, and literal construction check | PARTIALLY_SUPPORTED | Symbolic trace may miss future backend/model operations; security table is an admission envelope rather than a live estimator | Operation mutation tests, all declared models, and observed under/over-provision audit | “All generated candidates execute” |
| Adaptive encrypted-trial reduction | Two completed split checkpoints used 28 configuration trials/84 key runs, including eight REJECTED-to-SAFE repairs, versus 440/1,320 for an equally repeated fixed catalog; 20 frozen selections then passed 20 one-trial/60-key locked audits without retuning | PARTIALLY_SUPPORTED | Two of five splits are complete, and the 93.64% selection reduction is a bounded-protocol count comparison rather than a global-oracle result | Complete multi-split trial distribution, false NO_SAFE analysis, and bounded-oracle regret | “One encrypted trial always suffices” |
| Generality across computation graphs | Direct synthesis supports linear-poly3, MLP-square-linear, and MLP-square-poly3; legacy Sobel/Harris probes remain | PARTIALLY_SUPPORTED | Primary evidence remains shallow and tabular | Deeper MLP, CNN-lite, modernized image protocols | “All models and datasets” |
| Robustness across dataset splits | Split seeds 0 and 1 each selected 10/10 workloads and passed 10/10 disjoint no-retuning audits with the same predeclared policy | PARTIALLY_SUPPORTED | Only two of five predeclared seeds are complete, and two splits cannot establish split independence | Complete split seeds 2--4 and freeze the combined selection/audit distribution | “Split-independent result” |
| Robustness across cryptographic randomness | Across two split checkpoints, selection completed 84 fresh-key runs and locked audit completed 60 more; all 20 final validation certificates and 20 audits had zero flips/violations | PARTIALLY_SUPPORTED | Three keys per partition and two split seeds are too few for a key-independence claim; encryption randomness is not separately seeded | More key repeats across all predeclared splits with explicit randomness recording | “Key-independent safety” |
| Safety-factor choice | alpha=0.5 current default | UNSUPPORTED | Arbitrary policy constant | Predeclared sensitivity study and policy interpretation | “0.5 is theoretically optimal” |
| Margin-floor choice | margin_floor=0.001 current default | UNSUPPORTED | Arbitrary ambiguity cutoff | Coverage/latency/NO_SAFE sensitivity study | “0.001 is universally correct” |
| Final latency claims | Mean/std fields in preliminary summaries | PARTIALLY_SUPPORTED | Warm-up, p95, process variance incomplete | Frozen latency protocol with raw records | “Stable production latency” |
| Artifact reproducibility | Frozen observed evidence v1 plus separately checksummed seed-0 and seed-1 direct locked-audit packs with a shared verifier | PARTIALLY_SUPPORTED | Direct evidence remains preliminary and the five-split V2 pack is incomplete | Complete the one-ledger multi-split run, final evidence freeze, and verifier | “Complete reproducibility achieved” |

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
