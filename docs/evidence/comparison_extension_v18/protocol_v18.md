# V18 Comparison Protocol

**State: `PROTOCOL_FROZEN`**

This protocol was fixed before candidate outcome columns were used for the V18
replay. V17 remains immutable. The primary causal population is the 68 V17
primary cases; the 131-case all-scope population is secondary context. Key
repeats, candidate rows, and latency passes are not independent samples.

## Comparators

1. **C1 PROPOSED_FULL.** Replay the frozen V17 direct method: synthesized
   initial configuration, Security-V2 admission, encrypted decision agreement,
   the predeclared reserve policy, bounded monotone adjustment, and first
   acceptable selection or abstention. `B=4` is four candidate evaluations,
   with bounded adjustments between evaluations, not four repairs.
2. **C2 DECISION_GATE_OFF.** Traverse the same recorded direct sequence and
   select the first materialized, security-admitted, execution-successful,
   finite-output candidate. Ignore decision agreement and reserve-policy tests.
   No new numerical threshold is introduced.
3. **C3 INITIAL_ONLY.** Apply the complete C1 gate only to the first direct
   candidate. Stop if it is not acceptable; do not consider a repair candidate.
4. **C4 PREEXISTING_DEFAULT_OR_LATENCY_ONLY.** Use a fixed default or aggressive
   latency-only arm only where the V17 protocol contains its prior identity,
   hash, rule, exact workload binding, and security result. Otherwise report
   `NO_PREEXISTING_BASELINE_AVAILABLE`.
5. **C5 TRADITIONAL_OBJECTIVE_DIAGNOSTICS.** Among finite-reference candidates
   that pass security and execution, identify the fastest observed candidate,
   the minimum maximum-absolute-error candidate, and the error-latency Pareto
   frontier. RMS is admitted only if a consistent value exists for every
   eligible candidate and case. This is a diagnostic, not a simulated external
   system.
6. **C6 FINITE_REFERENCE.** The predeclared V17 depth-complete finite candidate
   set is an offline selection-quality reference. It identifies the fastest
   acceptable finite candidate, false `NO_SAFE`, selected rank, and latency
   regret. It is neither a practical user baseline nor a global optimum.
7. **C7 EXTERNAL_NATIVE_BASELINES.** Reuse frozen EVA, HEIR, and CoreLab
   evidence with explicit exact/output/numerical compatibility classes. Raw
   latency is compared only for a portable-exact common-executor arm whose
   decision-stability admission is valid.

## Measures

- Candidate-evaluation reduction uses aggregate C1 and C6 counts.
- The finite/direct selection-wall-clock ratio uses aggregate elapsed time over
  the intersection where both timing boundaries are present.
- Formal inference latency and regret use only the 68 existing exact candidate
  bindings under the V17 paired protocol.
- Selection-stage latency may order diagnostic candidates but is never called
  formal paired latency.
- Separate-input failure includes a flip, reserve-policy violation, or explicit
  `REJECTED`/`FAILED` state on the independent input set.

## Targeted execution gate

The default is zero new encrypted evaluations. A targeted run is allowed only
when an official artifact has an exact-compatible, core-claim cell missing from
all immutable evidence. At most 12 cases and 36 candidate evaluations may be
frozen. Exceeding either limit blocks expansion rather than shrinking the exact
case set after seeing outcomes.

## Claim boundary

The 83.426443% candidate-evaluation reduction, if reproduced, describes the
offline finite-reference burden avoided. It is not a speedup over existing CKKS
systems, an empirical reduction in every user's search, or a fraction of the
global CKKS configuration space.
