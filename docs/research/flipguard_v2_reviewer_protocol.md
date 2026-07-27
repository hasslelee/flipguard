# FlipGuard V2 strict reviewer and evaluation protocol

## 1. Purpose

This document defines how FlipGuard V2 must be evaluated before its results
may be used as thesis-grade evidence.

The protocol preserves the current certify-or-reject research direction.
It does not discard the existing Core and tabular results. It prevents those
preliminary results from being presented more strongly than their evidence
allows.

Every experiment must answer:

1. What exact paper claim does this experiment support?
2. Why were these datasets, models, inputs, seeds, thresholds, and candidates
   selected?
3. Was the setting fixed before inspecting the final audit result?
4. What result would falsify or materially weaken the claim?
5. Can an external evaluator reproduce the result from the artifact?

## 2. Reviewer stance

All work must be assessed as if it were an unrelated submission.

The default questions are:

- Is the dataset too small?
- Is the input set merely a convenient example?
- Is one split or one seed being generalized?
- Is the comparison favorable to FlipGuard by construction?
- Is a policy constant arbitrary?
- Is a workload count inflated by no-improvement cases?
- Is an observed result being described as a guarantee?
- Is the planner being credited for safety that is actually checked by the
  certifier?
- Are failed, rejected, ambiguous, or NO_SAFE results omitted?
- Can the raw artifact regenerate every reported table?

Passing software tests alone does not resolve these questions.

## 3. Evidence tiers

### Tier A: development and regression probes

Purpose:

- backend functionality
- arithmetic-path execution
- state-transition regression
- planner/resolver integration
- fast continuous testing

Current six Core workloads belong here unless they are rebuilt with a
thesis-grade data protocol.

Tier A results must not be used as evidence of model, dataset, or input-space
generality.

### Tier B: automation evaluation

Purpose:

- candidate generation
- feasibility filtering
- exhaustive-oracle comparison
- planner pruning quality
- selection overhead

Required metrics:

- full candidate count
- generated candidate count
- executable candidate count
- SAFE candidate recall
- global fastest-safe recall
- pruning ratio
- latency regret
- planner overhead
- FAILED and NO_SAFE counts

Planner safety claims are prohibited. Safety is determined by the certifier.

### Tier C: final thesis audit

Purpose:

- final evidence for the paper claims

Required separation:

1. training set
2. configuration-validation set
3. final audit/test set

The final audit/test set must not influence:

- model selection
- planner coefficients
- candidate-generation rules
- safety factor
- margin floor
- threshold choice
- comparison selection
- stopping rules

Any change made after inspecting final audit results invalidates the final
status and requires a newly frozen audit set.

## 4. Current evidence classification

### Core workloads

Classification:

- legacy functional/regression probes

Current limitations:

- few probe inputs
- some polynomial experiments repeat one effective input
- input diversity and cryptographic randomness are not separated
- old experiment paths were reused during development

### Existing tabular certification

Classification:

- preliminary observed-validation study
- exploratory fixed-split evidence

Current strengths:

- ten dataset/model workloads
- complete 220-candidate matrix
- frozen manifest and checksums
- explicit V_cert and V_amb
- latency-only candidates rejected in all ten workloads

Current limitations:

- effectively one dataset split seed: 42
- no independent configuration-validation and final audit split
- no final multi-seed study
- no explicit independent-key protocol
- alpha and margin floor are not yet justified by sensitivity evidence

### Linear workloads

Classification:

- negative control
- shallow-graph ablation
- no-optimization-headroom case

The five Linear results must not be counted as five successful performance
improvements when their selected speedup is zero.

### MLP-square workloads

Classification:

- preliminary performance evidence

They may motivate the final evaluation but do not replace it.

## 5. Decision-stability policy

For plaintext score f(x), CKKS score f_hat(x;c), threshold tau, and margin

gamma(x) = |f(x) - tau|,

the current configured budget is

epsilon(x) = alpha * gamma(x).

A V_cert violation occurs when

|f_hat(x;c) - f(x)| >= epsilon(x).

Equality is unsafe.

The following are policy parameters, not universal constants:

- alpha
- margin_floor

The current alpha=0.5 and margin_floor=0.001 must be described as preliminary
defaults until sensitivity analysis and a predeclared selection policy are
complete.

Required sensitivity outputs:

- V_cert
- V_amb
- coverage
- SAFE candidate count
- REJECTED candidate count
- selected configuration
- selected latency
- decision flips
- error violations
- NO_SAFE frequency
- analytical eligibility

The sensitivity grid must be frozen before the final audit results are viewed.

## 6. Repetition dimensions

The final protocol must distinguish:

- dataset split seed
- model initialization/training seed
- key-generation seed
- encryption randomness
- latency repetition
- process restart
- machine or VM instance

Repeating encryption of the same input is not evidence of input generality.

The exact counts must be fixed after a variance/runtime pilot and before the
final audit. The selected counts and stopping rule must be recorded in the
frozen protocol.

## 7. Latency protocol

Required reporting:

- hardware and VM configuration
- CPU governor and relevant runtime settings
- software versions
- commit hash
- profile and execution path
- warm-up count
- measured repetition count
- evaluation-only latency
- end-to-end latency
- median
- p95
- mean
- standard deviation or IQR
- planner/certifier overhead
- raw timing records

Outlier removal must not be performed silently. If used, both the rule and raw
distribution must be preserved.

## 8. Planner protocol

The exhaustive candidate evaluation is the oracle within the declared candidate
space.

The executable Step 7B.2 contract is frozen in
[`step_7b2_planner_oracle_protocol.md`](step_7b2_planner_oracle_protocol.md).
It projects planner candidate IDs onto the same exhaustive execution records;
it does not rerun the planner subset. `mean_total_ms` is frozen as the
selection metric before the full validation run.

Required definitions:

safe_candidate_recall =
    planner-retained SAFE candidates / all SAFE candidates

global_optimum_recall =
    fraction of workloads where the exhaustive fastest-safe candidate is
    retained by the planner

latency_regret =
    (planner-selected latency - exhaustive fastest-safe latency)
    / exhaustive fastest-safe latency

A planner with high pruning but low safe recall or high latency regret is not
successful.

When the exhaustive oracle has no SAFE candidate, safe recall, global optimum
recall, and latency regret are undefined rather than zero. False `NO_SAFE`
requires an oracle SAFE candidate and an empty planner SAFE subset.

Heuristic coefficients must be tuned on workloads separate from the final
evaluation workloads, or evaluated through a nested protocol that prevents
test leakage.

### 8.1 Direct-synthesis protocol

The first-party deployment path must not project its proposal onto the fixed
profile catalog. It must emit an exact CKKS parameter literal and preserve:

- model and validation artifact digests;
- plaintext graph and score-consistency checks;
- decision margin and ambiguity partition;
- scale/level derivation method;
- backend NTT-prime generation attempts and any feasibility scale lift;
- statically considered same-tier literals and precision gain;
- declared LogN, LogQ, LogP, and default scale;
- security-envelope identity, source, and remaining headroom;
- every encrypted trial and repair trigger;
- the final SAFE certificate or NO_SAFE reason.

Parameter construction success is only a backend-validity check. Security
admission and decision certification remain separate checks.

Adaptive search cost is the number of fully encrypted candidate trials, not
the number of statically considered expressions. The planner must report its
trial distribution and compare it with:

- the fixed-catalog exhaustive oracle;
- the CKKS reference configuration;
- any external candidate provider used in the final study.

Stopping at the first SAFE candidate is an efficiency policy, not proof of
global latency optimality. Oracle latency regret must quantify the tradeoff.

## 9. Workload modernization

Final primary workloads must represent distinct computation structures, not
only different dataset names.

Target structures:

- MLP-square
- deeper polynomial MLP
- polynomial-activation CNN or CNN-lite
- Sobel
- Harris
- threshold and sign decisions
- different threshold positions
- class-imbalance variants

Linear/Poly3 remains useful as a negative control and shallow-depth ablation.

No claim of support for every model or dataset is allowed.

## 10. Analytical evidence discipline

Observed validation and analytical guarantees are separate evidence types.

Forbidden substitutions:

- empirical maximum error as analytical error bound
- test-set feature minima/maxima as a declared input domain
- Lattigo precision statistics as a proof
- fresh-noise standard deviation as an absolute end-to-end bound
- arbitrary scalar plus `AnalyticalBoundProvided=true`

Supported input-scope types:

- ENUMERATED_FINITE_SET
- DECLARED_BOX_DOMAIN
- EMPIRICAL_RANGE_ONLY

EMPIRICAL_RANGE_ONLY is not certificate eligible.

A HYBRID certificate requires both:

- valid observed evidence
- valid scoped analytical proof

The proof must bind:

- model artifact
- operation graph
- input scope
- profile facts
- execution path
- source code
- library version
- threshold and formula
- derivation method
- failure probability when probabilistic

## 11. Baselines and comparisons

Required comparisons where applicable:

- CKKS default configuration
- latency-only selection
- error-only selection
- fixed catalog
- exhaustive fastest-safe oracle
- planner-guided FlipGuard
- generated candidate space
- existing autotuner-generated candidates followed by FlipGuard certification

Comparison conditions must use the same:

- hardware
- cryptographic security target
- dataset split
- model artifact
- timing boundary
- repetition protocol

## 12. Failure disclosure

The final artifact must retain and report:

- FAILED candidates
- REJECTED candidates
- AMBIGUOUS samples
- NO_SAFE workloads
- planner misses
- analytical-bound underestimation
- configurations with no speedup
- low-coverage settings
- workloads where bounds are too conservative

These results must not be deleted because they weaken the headline result.

## 13. Literature precedents

These precedents motivate evaluation requirements but do not mechanically
determine FlipGuard's exact sample or repetition counts.

### HECO — USENIX Security 2023

Relevant practices:

- explicit hardware and FHE library
- common security parameters
- explicit timing boundary
- ten timing iterations
- stated outlier treatment
- several benchmarks and instance sizes

### PILLAR — USENIX Security 2024

Relevant practices:

- multiple datasets and architectures
- repeated random seeds
- 95 percent confidence intervals
- comparison against related-work baselines
- parameter and design ablations
- aligned LAN/WAN assumptions

### USENIX Security artifact evaluation

Relevant requirements:

- consistency with the paper
- completeness
- documentation
- ease of reuse and reproduction

### IEEE Symposium on Security and Privacy artifact evaluation

Relevant requirements:

- scripts and data sufficient to exercise paper experiments
- successful execution by evaluators
- reproducible artifact packaging

## 14. Reproducibility target

The final evidence package must contain:

- immutable source commit
- environment manifest
- workload manifest
- split and seed manifest
- candidate-space manifest
- raw records
- summary-generation scripts
- checksums
- one-command runner
- one-command verifier
- claim-to-artifact map

Every paper table must be regenerable from frozen raw evidence.
