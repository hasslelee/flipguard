# FlipGuard V2 Claim-Evidence Matrix

Status vocabulary is limited to `SUPPORTED`, `PARTIALLY_SUPPORTED`, `BLOCKED`,
`NOT_EVALUATED`, `SUPERSEDED`, and `PILOT_ONLY`. `paper_claim_allowed` is a
separate boolean; `BLOCKED` never means that a gate is merely closed.

Core contribution:

> FlipGuard directly synthesizes a CKKS configuration from a supported
> computation graph and a threshold decision-integrity contract, validates it
> with a small number of encrypted trials, applies bounded failure-aware
> repairs, abstains when no SAFE candidate can be established, and replays the
> selected literal without retuning on a locked audit set.

| Claim | State | paper_claim_allowed | Current evidence | Block reason / required evidence |
|---|---|---:|---|---|
| Direct synthesis | SUPPORTED | false | Final clean-source selection covers 50 primary instances; the separate BSDS500 Sobel extension also synthesized and selected without catalog lookup | Paper admission remains pending; scope is the declared adapters only |
| Adaptive repair | PARTIALLY_SUPPORTED | false | Primary confirmatory results and the Sobel holdout preserve bounded REJECTED-to-SAFE repairs; Sobel required exactly the frozen `+4` numerical repair | Predeclared graph-only/one-shot/full ablation is incomplete |
| Decision-integrity certification | PARTIALLY_SUPPORTED | false | Final finite-set candidate certificates, negative controls, locked audits, and sample-level Sobel ledgers are verified | This remains observed finite-scope evidence, not a domain-wide analytical bound |
| Trial reduction | SUPPORTED | false | Final direct accounting uses 70/700 all instances and 56/560 confirmatory instances, both 90% fewer candidate trials than the Security V2 bounded catalog | Paper admission remains pending |
| Security-compliant bounded catalog comparison | SUPPORTED | false | V2 formal comparison uses only 700 admitted candidates; 400 excluded executions remain historical; paired arms are frozen | The result is bounded-catalog, never global-optimum evidence |
| Latency speedup | PARTIALLY_SUPPORTED | false | Final paired pack has 50/50 rows; clustered direct/catalog total-latency ratio is 3.14x with all frozen arms | Within-workload timing variability and manual paper admission remain |
| Security | PARTIALLY_SUPPORTED | false | Q and QP are separately checked against published Table 5.2; direct 50/50 PASS, four catalog profiles excluded | Exact estimator inputs are exported but exact estimation is NOT RUN; no universal security claim |
| Locked audit on fixed held-out partitions | SUPPORTED | false | Primary final audits pass without retuning; deeper `mlp_square_poly3` preserves 24/25 PASS plus one disclosed REJECT; BSDS500 Sobel passes with 399/1 certifiable/ambiguous samples | Support is limited to the declared repeated partitions and Sobel image scope |
| Structural generalization | PARTIALLY_SUPPORTED | false | Full `mlp_square_poly3` selection is 25/25 with audit 24 PASS and 1 numerical REJECT; BSDS500 Sobel selection/audit passes over 50+50 disjoint image clusters | Arbitrary graphs, packed full-image operators, Harris, and CNN/LeNet remain unevaluated |
| Conditional analytical claim | BLOCKED | false | Scope metadata and primitive placeholders exist | No sound primitive CKKS residual derivation or observed-versus-bound audit |
| Planner baseline | PARTIALLY_SUPPORTED | false | Legacy catalog-pruning baseline has zero false NO_SAFE and low regret but low SAFE/optimum recall | It is not the primary contribution and cannot substitute for direct synthesis |
| Artifact reproducibility | PARTIALLY_SUPPORTED | false | Final confirmatory and Sobel packs have deterministic rebuild verifiers, raw ledgers, policy/binary/input digests, and pushed source commits | Release tag, external archive, and independent-machine replay remain |

## Evaluation Units

- Seed 0 is the development/ablation partition.
- Seeds 1-4 are post-freeze repeated-partition evaluation.
- The experiment comprises five deterministic repeated partitions of a fixed
  held-out artifact.
- Report the scope as 10 dataset-model workloads x 5 partition seeds, or 50
  workload-partition instances.
- Do not call these 50 independent workloads, models, or dataset splits.
- Inferential summaries must cluster by dataset-model; repeated partitions do
  not establish training-seed or model generalization.

## Policy Freeze

- Primary alpha: `0.5`.
- Alpha sensitivity: `{0.1, 0.25, 0.5, 0.75, 0.9}`.
- Primary margin floor: `0.001`.
- Margin floor `0.0005`: `SECONDARY_POLICY_SENSITIVITY` only.
- No audit result may select alpha or margin floor.
- Direct maximum encrypted trials: `4`.

## Forbidden Claims

- first application-aware CKKS configuration;
- first direct CKKS autotuner;
- first repair-based CKKS parameter selection;
- optimization claims outside the declared bounded candidate domain;
- universal model support;
- independent evidence from the 50 repeated-partition rows;
- latency speedup from unpaired or pilot evidence.
