# V18 Literature and Artifact Baseline Audit

## Audit rule

Only official papers, proceedings pages, repositories, and already frozen
execution artifacts are used. A system name is not promoted to an experimental
baseline unless model, graph, weights, inputs, decision rule, security target,
and measurement boundary are defensible. Native runtimes remain separate from
the common Lattigo executor. This prevents a broad but misleading speed chart.

## Baseline practice

| System | Native objective | Actual paper baseline and ablation practice | Exact locator | V18 consequence |
|---|---|---|---|---|
| CHET | tensor lowering, packing, and parameter selection | compares generated tensor programs with hand-optimized implementations; the later EVA paper retargets CHET to EVA | PLDI 2019, DOI `10.1145/3314221.3314628` | no separate exact V17 artifact; related work only |
| EVA | vector IR optimization, rescale insertion, parameter generation | evaluates EVA optimizations and CHET-on-EVA; reports program latency and numerical error | PLDI 2020, DOI `10.1145/3385412.3386023` | existing V8 shared-polynomial result is output-comparable; native SEAL latency remains separate |
| HECATE | joint scale/level management for latency under an error bound | one external compiler (EVA) and internal `PARS`/`SMSE` ablations across 36 waterlines | Sec. VII-A/B, PDF pp. 8-9, Table II, Figs. 7-8 | existing record is numerical-only; no invented decision baseline |
| ELASM | error-latency-aware scale-plan search | EVA and HECATE in the same SEAL setting across ten variants; explores 12,000 sampled plans | Sec. 7.1-7.2, PDF pp. 11-14, Figs. 11-15 | existing 70/72 CoreLab plan grid is numerical-only |
| DaCapo | automatic bootstrapping placement | manual placement plus `Liveness` and `Bypass` mechanism ablations over twelve DNN variants | Sec. 8.1-8.3, PDF pp. 10-12, Table 3, Figs. 4-5 | current leveled V17 graphs do not require bootstrapping; related work only |
| HEIR | MLIR FHE compiler and multi-backend lowering | compiler passes and backend/code-generation comparisons; current project exposes CKKS and Lattigo/OpenFHE dialects | arXiv `2508.11095` and `heir.dev` | existing V8 shared-polynomial Lattigo translation is portable-exact; no new run |
| Orion | DNN compilation, packing, scale, and bootstrapping | baseline changes by sub-question: Fhelipe, Lee et al., DaCapo, EVA, or HeLayers | Secs. 7-8, PDF pp. 10-13, Tables 2-5 | build success alone does not establish exact V17 model/packing identity |
| FHE-Agent | LLM-guided CKKS configuration and multi-fidelity repair | ten independent one-shot LLM proposals form the naive baseline; one three-phase agent run is compared under the same Orion/Lattigo backend and security target; the paper example reaches a feasible configuration after four fully encrypted trials | arXiv `2511.18653`, Secs. 4-5 and Table 1 | no official executable repository was verified; do not reimplement it |

The paper practice does not support a universal all-system panel. The common
pattern is one or two task-aligned external baselines plus causal internal
ablations. HECATE, ELASM, and DaCapo each choose controls that match their own
optimization target. V18 therefore treats decision-gate removal and repair
removal as the primary causal comparisons, and uses external systems only at
the exact compatibility level already established by frozen artifacts.

## Library guides

Microsoft SEAL's official CKKS example demonstrates manual scale and modulus
chain selection for a fixed cubic polynomial. OpenFHE's official examples expose
the multiplicative depth, scaling-modulus size, ring dimension, batch size, and
security-level context inputs. Lattigo exposes explicit `LogN`, ordered `LogQ`,
ordered `LogP`, and default scale literals. These are implementation guides,
not workload-matched configuration selectors, so they remain
`RELATED_WORK_ONLY`.

## Existing external evidence admitted to V18

1. **HEIR exact subset:** `focused_external_comparison_v8` contains a
   portable-exact shared-polynomial translation in the common Lattigo executor.
   The HEIR arm itself had no flips, but the paired FlipGuard-direct comparison
   arm exhibited eight repeated flips for one input. The existing paired-latency
   ratios therefore remain blocked diagnostics rather than speed claims.
2. **EVA output-comparable subset:** the same frozen pack contains 1,000 unique
   shared-polynomial inputs split 500/500 for configuration validation and
   locked audit. It is decision-bearing, but native SEAL latency is not compared
   directly with Lattigo latency and its security distribution assumptions are
   qualified.
3. **CoreLab numerical subset:** 70 of 72 predeclared EVA/ELASM plans completed
   for 200 inputs each. They support an error-latency Pareto diagnostic only;
   they do not provide the exact V17 decision output contract.

## Official source index

- CHET: https://doi.org/10.1145/3314221.3314628
- EVA: https://www.microsoft.com/en-us/research/publication/eva-an-encrypted-vector-arithmetic-language-and-compiler-for-efficient-homomorphic-computation/
- HECATE: https://doi.org/10.1109/CGO53902.2022.9741265
- ELASM: https://www.usenix.org/conference/usenixsecurity23/presentation/lee-yongwoo
- DaCapo: https://www.usenix.org/conference/usenixsecurity24/presentation/cheon
- HEIR: https://heir.dev/ and https://arxiv.org/abs/2508.11095
- Orion: https://doi.org/10.1145/3676641.3716008
- FHE-Agent: https://arxiv.org/abs/2511.18653
- Lattigo: https://github.com/tuneinsight/lattigo
- Microsoft SEAL CKKS example: https://github.com/microsoft/SEAL/blob/main/native/examples/5_ckks_basics.cpp
- OpenFHE examples: https://github.com/openfheorg/openfhe-development/blob/main/src/pke/examples/README.md

## Falsification boundary

This audit fails if native-runtime latency is merged into a common-executor
speed ranking, if CoreLab numerical rows are called decision-stability rows, if
the unsafe HEIR common-executor arm is presented as an admitted latency claim,
or if a missing artifact is replaced by a home-grown imitation.
