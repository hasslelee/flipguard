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
| Direct synthesis | PARTIALLY_SUPPORTED | false | Three supported scalar-tabular formulas; 50 PRE_SECURITY_V2 selected rows; all 50 literals statically pass Security V2 | Clean-source post-freeze selection is not executed |
| Adaptive repair | PARTIALLY_SUPPORTED | false | 20 REJECTED-to-SAFE repairs in 70 PRE_SECURITY_V2 trials; monotone `+4` scale and `+1` level rules are bounded | One-shot/graph-only/full ablation is not executed |
| Decision-integrity certification | PARTIALLY_SUPPORTED | false | Finite `V_cert` certify-or-reject logic and mutation tests; zero preliminary selected flips/violations | This is finite observed evidence, not a domain-wide bound |
| Trial reduction | PARTIALLY_SUPPORTED | false | 70 direct trials/210 key runs versus 1,100 catalog candidate executions | Comparison is bounded and PRE_SECURITY_V2; final clean-source accounting is absent |
| Security-compliant bounded catalog comparison | PARTIALLY_SUPPORTED | false | V2 filtering retains 7/11 profiles and 14/22 identities; existing records are re-summarized without rerun | Final direct rows and paired arms are not yet clean-source confirmatory evidence |
| Latency speedup | BLOCKED | false | Existing unpaired comparison is SUPERSEDED for latency; seed-0 paired pack is PILOT_ONLY | Final paired 50-instance run over frozen V2 arms is absent |
| Security | PARTIALLY_SUPPORTED | false | Q and QP are separately checked against published Table 5.2; direct 50/50 PASS, four catalog profiles excluded | Exact estimator inputs are exported but exact estimation is NOT RUN; no universal security claim |
| Locked audit on fixed held-out partitions | PARTIALLY_SUPPORTED | false | 50 PRE_SECURITY_V2 no-retuning audits passed with zero retuning/flips/violations | Seed 0 is development; seeds 1-4 need clean-source post-freeze replay |
| Structural generalization | PILOT_ONLY | false | One `mlp_square_poly3` selection/audit pilot and static plans | Full structural holdout and non-tabular CNN/image graph are absent |
| Conditional analytical claim | BLOCKED | false | Scope metadata and primitive placeholders exist | No sound primitive CKKS residual derivation or observed-versus-bound audit |
| Planner baseline | PARTIALLY_SUPPORTED | false | Legacy catalog-pruning baseline has zero false NO_SAFE and low regret but low SAFE/optimum recall | It is not the primary contribution and cannot substitute for direct synthesis |
| Artifact reproducibility | PARTIALLY_SUPPORTED | false | SHA-256 pre-change checkpoint, deterministic pack verifiers, policy digests, and source bindings exist | Final evidence freeze, clean replay, release tag, and archive are absent |

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
