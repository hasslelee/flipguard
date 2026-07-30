# Direct-Synthesis Ablation Evidence V1

This pack freezes the predeclared seed-0 development ablation. Graph-only
fixed-tolerance synthesis and full FlipGuard produced the same literal
parameters, trials, repairs, and outcomes on all ten natural workloads.
Candidate IDs differ because they bind policy/contract identity. Therefore,
the decision-contract candidate-synthesis effect was not observed in this
scope.

The one-shot view selected 6/10 and returned NO_SAFE for four first-trial
rejections. Frozen adaptive repair selected all four without validation or
audit violations. The Security-V2 latency-only arm selected a REJECTED
candidate in 10/10 workloads and has no locked-audit claim.

Thirty original audit attempts failed before CKKS execution because equivalent
frozen paths were represented differently. The recovery bound the evidence
pack paths while preserving row membership and CSV digests; all ten recovered
audits passed without selection rerun or retuning.

This is development evidence. It does not make the paper claim admissible.
