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
| Direct synthesis | SUPPORTED | false | Final clean-source selection covers 50 primary instances; nine newly trained models across three declared training/data-split seeds select without catalog lookup; separate BSDS500 Sobel, Harris, and MNIST CNN-lite adapters also synthesize and select | Paper admission remains pending; scope is the declared models and adapters only |
| Adaptive repair | SUPPORTED | false | The predeclared seed-0 ablation returns one-shot NO_SAFE for four first-trial rejections, while frozen `+4` repair selects all four and their audits pass; primary confirmatory and Sobel evidence preserve the same bounded repair semantics | Support is empirical and scoped; repair is not guaranteed to succeed universally |
| Decision-contract candidate-synthesis effect | BLOCKED | false | Graph-only fixed tolerance and full FlipGuard have identical path+CKKS parameters, trials, repairs, and outcomes in 10/10 natural development workloads; candidate IDs differ only because they bind policy/contract identity | A strong natural-data claim that decision margins change the synthesized configuration is unsupported |
| Finite-domain decision-contract activation | SUPPORTED | false | A predeclared high-sensitivity control holds graph, interval calibration, and sensitivity fixed: narrow-margin full synthesis starts at S21 and selects S33, while graph-fixed starts at S20 and selects S32; wide-margin arms both start at S20 and select S28; all four no-retuning audits pass | This is an explanatory synthetic control and cannot promote the blocked natural-data effect |
| Decision-integrity certification | PARTIALLY_SUPPORTED | false | Final finite-set candidate certificates, negative controls, locked audits, and sample-level Sobel, Harris, and MNIST CNN-lite ledgers are verified | This remains observed finite-scope evidence, not a domain-wide analytical bound |
| Provider-neutral candidate admission | PARTIALLY_SUPPORTED | false | Manual, bounded-catalog, direct, and synthetic external-format arms share one verified gate; exact Orion public configurations fail closed before execution; one source-replayed AWS HIT literal imports losslessly and passes Security V2 but is decision-REJECTED on the declared development workload | No native third-party autotuner has yet produced a SAFE candidate that completed no-retuning locked audit; HIT is a formula-based parameter selector, not a search autotuner |
| Trial reduction | SUPPORTED | false | Final direct accounting uses 70/700 all instances and 56/560 confirmatory instances, both 90% fewer candidate trials than the Security V2 bounded catalog | Paper admission remains pending |
| Security-compliant bounded catalog comparison | SUPPORTED | false | V2 formal comparison uses only 700 admitted candidates; 400 excluded executions remain historical; paired arms are frozen | The result is bounded-catalog, never global-optimum evidence |
| Latency speedup | PARTIALLY_SUPPORTED | false | Final paired pack has 50/50 rows; clustered direct/catalog total-latency ratio is 3.14x with all frozen arms | Within-workload timing variability and manual paper admission remain |
| Security | PARTIALLY_SUPPORTED | false | Q and QP are separately checked against published Table 5.2; direct 50/50 PASS and four catalog profiles are excluded. Two exact-modulus lattice-estimator jobs cover 18 Q/QP objects each with complete primal-uSVP, primal-BDD, and dual-hybrid attack coverage; every static-admitted object passes both models, while the excluded N14/QP object is also sub-128 in both | The estimator matches ternary Xs and Gaussian sigma but not Lattigo's explicit Gaussian truncation bound; no exact-distribution or universal security claim |
| Locked audit on fixed held-out partitions | SUPPORTED | false | Primary final audits pass without retuning; nine independently trained model instances pass 9/9 on disjoint audit roles; deeper `mlp_square_poly3` preserves 24/25 PASS plus one disclosed REJECT; BSDS500 Sobel/Harris and MNIST CNN-lite pass on their disjoint locked-audit inputs | Support is limited to the declared repeated partitions, training seeds, and graph/input scopes |
| Training/model-seed generalization | PARTIALLY_SUPPORTED | false | Three datasets x three predeclared independent training/data-split seeds produce nine distinct trained models; direct selection and byte-identical audit replay pass 9/9 with no retuning | Three datasets and three seeds cannot establish universal training-seed or model generalization |
| Structural generalization | PARTIALLY_SUPPORTED | false | Full `mlp_square_poly3` selection is 25/25 with audit 24 PASS and 1 numerical REJECT; BSDS500 Sobel and depth-2 Harris pass selection/audit over 50+50 image clusters; scalar-replicated MNIST CNN-lite passes on 250+250 disjoint images | Arbitrary graphs, packed CNN/full-image operators, general LeNet, and universal graph support remain unevaluated |
| Conditional error-envelope propagation | SUPPORTED | false | Analytical V2 binds the exact operation graph, model scalar bits, per-node source digests, outward-rounded envelopes, probabilistic union bounds, replay validation, and 2,000 fixed-seed `linear_poly3` perturbation cases | This is an if-then arithmetic result only; it does not supply the CKKS primitive residual assumptions |
| Instantiated CKKS analytical certificate | BLOCKED | false | A static inventory covers all 50 primary selections: 25 have a supported `linear_poly3` graph contract, but 0/50 have complete primitive bounds, 0/50 are proof eligible, and no observed-versus-bound audit is run | Scoped absolute bounds for input encryption, plaintext encoding, multiplication, relinearization, rescale, and alignment are missing; the MLP operation graph is also missing |
| Planner baseline | PARTIALLY_SUPPORTED | false | Legacy catalog-pruning baseline has zero false NO_SAFE and low regret but low SAFE/optimum recall | It is not the primary contribution and cannot substitute for direct synthesis |
| Latency-only/no-certification comparator | SUPPORTED | false | The Security-V2-admitted fastest executable candidate is validation-REJECTED in 10/10 seed-0 workloads, with 794 flips and 1,610 violations; locked audit is explicitly NOT EVALUATED | This is development evidence and does not imply every latency-only candidate is unsafe |
| Artifact reproducibility | PARTIALLY_SUPPORTED | false | Final confirmatory, Sobel, Harris, MNIST CNN-lite, independent-training-seed, direct-ablation, and conditional-analytical-readiness packs have deterministic rebuild verifiers, raw ledgers or static inventories, policy/binary/input digests where applicable, and pushed source commits | Nine overwritten independent-seed pre-CKKS recovery logs are disclosed; release tag, external archive, and independent-machine replay remain |

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
- The separate training-seed extension contains nine newly trained models
  across three datasets and three predeclared seeds. It is reported as a
  scoped robustness extension, not as nine independent datasets or universal
  model-seed generalization.

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
