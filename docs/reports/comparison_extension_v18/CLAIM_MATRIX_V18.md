# V18 Claim Matrix

| Claim | State | Exact admitted wording | Limitation |
|---|---|---|---|
| Decision gate changes selection | SUPPORTED | Removing only the decision-stability gate selected all 68 initial candidates, including 20 cases with observed selection-input flips and 21 with reserve-policy violations; the full method changed 21 literals. | Candidate-specific separate-input outcomes are observed for 47 gate-off literals; 21 are not evaluated. |
| Bounded adjustment is useful | SUPPORTED | Forty-seven initial candidates were acceptable; all 21 initially rejected primary cases were recovered by one recorded bounded adjustment and the selected literals passed separate-input evaluation. | Empirical result for the declared V17 primary cases, not universal repair success. |
| Cost of decision stability | PARTIALLY_SUPPORTED | Stability cost 21 additional encrypted candidate evaluations; changed literals had median +28 Q bits and +4 scale bits, with no LogN or P increase. | Formal gate-off inference latency was not measured; candidate-stage latency is diagnostic only. |
| Numerical objectives imply stability | FALSIFIED_FOR_DECLARED_DIAGNOSTIC | The fastest executable finite candidate violated the gate in 18/68 cases, and 28 unstable candidates lay on case-wise error-latency Pareto frontiers. | This is a diagnostic over the declared finite set, not a reconstruction of a named external tuner. |
| Finite-reference selection quality | SUPPORTED | Direct selection used 89 evaluations versus 537 for the offline finite reference, with false NO_SAFE 0, median SAFE rank 1, and median formal latency regret -0.000153. | The 83.426443% reduction is finite-reference burden avoided, not an existing-system speedup or global search result. |
| Final latency near finite fastest acceptable | PARTIALLY_SUPPORTED | The cluster-geometric finite/direct total-latency ratio was 1.000541 with 95% cluster-bootstrap CI [0.999967, 1.001122]. | CI includes 1; no latency superiority is claimed. |
| Preexisting latency-only policy | PARTIALLY_SUPPORTED | The frozen latency-only candidate was SAFE in 51 cases, REJECTED in 15, and not evaluated in two. | Not a universal user baseline; the fixed default was not a runnable common comparator. |
| Exact external comparison | PARTIALLY_SUPPORTED | A frozen HEIR shared-polynomial arm is portable-exact and decision-stable on its locked audit. | Paired latency remains blocked because the paired direct comparison arm was unstable on one timing input. |
| EVA external decision output | PARTIALLY_SUPPORTED | Frozen EVA scale-30 and scale-40 arms preserve the decision on the declared locked audit. | Native SEAL latency and security assumptions are reported separately. |
| All external tuners outperformed | BLOCKED | Not admitted. | Artifact, workload, runtime, and objective equivalence are not available across all systems. |
| Global optimum or future-input guarantee | BLOCKED | Not admitted. | V18 is finite empirical evidence only. |
