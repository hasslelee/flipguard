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
| Automatic candidate generation | Direct digest-bound synthesis of LogN/LogQ/LogP/scale; seed-0 three-key matrix selected 10/10 workloads and all frozen literals passed the disjoint three-key locked audit without retuning | PARTIALLY_SUPPORTED | Current scope is three tabular forms, scalar-replicated packing, rescale-aware Lattigo v6, and one data split | Predeclared multi-split direct-synthesis study, frozen-oracle comparison, and external providers | “Fully general automatic tuner” |
| Candidate feasibility pre-check | Lattigo-aware symbolic scale trace, 2024 HE security envelope, and literal construction check | PARTIALLY_SUPPORTED | Symbolic trace may miss future backend/model operations; security table is an admission envelope rather than a live estimator | Operation mutation tests, all declared models, and observed under/over-provision audit | “All generated candidates execute” |
| Adaptive encrypted-trial reduction | Seed-0 selection used 14 configuration trials/42 key runs, including four REJECTED-to-SAFE repairs, versus 220/660 for an equally repeated fixed catalog; its ten frozen selections then passed 10 one-trial/30-key locked audits without retuning | PARTIALLY_SUPPORTED | One split, and the 93.64% selection reduction is a bounded-protocol count comparison rather than a global-oracle result | Multi-split trial distribution, false NO_SAFE analysis, and bounded-oracle regret | “One encrypted trial always suffices” |
| Generality across computation graphs | Direct synthesis supports linear-poly3, MLP-square-linear, and MLP-square-poly3; legacy Sobel/Harris probes remain | PARTIALLY_SUPPORTED | Primary evidence remains shallow and tabular | Deeper MLP, CNN-lite, modernized image protocols | “All models and datasets” |
| Robustness across dataset splits | Seed-0 selected literals passed a disjoint locked audit, but no second split seed has been selected or audited | UNSUPPORTED | A held-out partition within one split does not establish split robustness | Predeclared multi-split selection and locked-audit protocol | “Split-independent result” |
| Robustness across cryptographic randomness | Contract schema 2 aggregates sample scores across fresh keypairs; seed-0 selection completed 42 key runs and the no-retuning locked audit completed 30 additional fresh-key runs with all final certificates at zero flips/violations | PARTIALLY_SUPPORTED | Three keys per partition on one split are too few for a key-independence claim; encryption randomness is not separately seeded | More key repeats across multiple splits with explicit randomness recording | “Key-independent safety” |
| Safety-factor choice | alpha=0.5 current default | UNSUPPORTED | Arbitrary policy constant | Predeclared sensitivity study and policy interpretation | “0.5 is theoretically optimal” |
| Margin-floor choice | margin_floor=0.001 current default | UNSUPPORTED | Arbitrary ambiguity cutoff | Coverage/latency/NO_SAFE sensitivity study | “0.001 is universally correct” |
| Final latency claims | Mean/std fields in preliminary summaries | PARTIALLY_SUPPORTED | Warm-up, p95, process variance incomplete | Frozen latency protocol with raw records | “Stable production latency” |
| Artifact reproducibility | Frozen observed evidence v1 plus frozen direct locked-audit seed-0 evidence with 35 checksummed files and verifier | PARTIALLY_SUPPORTED | Direct evidence remains preliminary and single-split; final V2 pack is incomplete | One-command multi-split V2 runner, final evidence freeze, and verifier | “Complete reproducibility achieved” |

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
