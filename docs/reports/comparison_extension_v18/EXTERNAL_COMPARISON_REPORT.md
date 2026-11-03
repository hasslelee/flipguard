# External Comparison Report

## Eligibility census

| Class | Systems | Count | Admitted use |
|---|---|---:|---|
| EXACT_COMPARABLE | HEIR | 1 | Shared-polynomial decision outcome; same-Lattigo diagnostic only |
| OUTPUT_COMPARABLE | EVA | 1 | Decision outcome and native-runtime configuration behavior |
| NUMERICAL_ONLY | HECATE, ELASM | 2 | Error-latency evidence without a matching decision contract |
| RELATED_WORK_ONLY | CHET, DaCapo, Orion, FHE-Agent, Lattigo, SEAL, OpenFHE | 7 | Positioning and evaluation-practice context |

## HEIR

The frozen V8 shared-polynomial workload is portable-exact in Lattigo. The
HEIR arm has 500 locked-audit inputs, three fresh keys, zero decision flips, and
zero reserve-policy violations. The common-executor timing file has 5,400 raw
records, but the paired FlipGuard-direct comparison arm produced eight repeated
flips on one timing input. Therefore the reported HEIR/direct and catalog/HEIR
ratios remain `BLOCKED_DIAGNOSTIC_UNSAFE_ARM`; no speed claim is admitted.

## EVA

The V8 EVA workload uses the same shared polynomial, weights, 500 validation
inputs, 500 disjoint locked-audit inputs, and threshold output. Scale-30 and
scale-40 arms have zero locked-audit flips and violations. Because native EVA
uses SEAL and its runtime security assumptions are not identical to the Lattigo
Security-V2 model, its native latency stays in a separate panel. It is
`OUTPUT_COMPARABLE`, not a common-runtime speed baseline.

## HECATE and ELASM

The frozen CoreLab grid contains 36 EVA-mode and 36 ELASM-mode plans. Seventy
plans completed on 200 inputs each, producing 14,000 numerical output rows; two
ELASM plans aborted before rows were produced. The workload has no frozen V17
decision output contract. These rows support an error-latency Pareto diagnostic
only and are never counted as decision-stability cases.

## Remaining systems

CHET lacks a separately verified executable artifact for the exact V17
contracts. DaCapo targets bootstrapping placement while V17 is leveled. Orion's
official model and packing identities do not match V17. No official runnable
FHE-Agent artifact was verified. Lattigo, SEAL, and OpenFHE examples are library
guides rather than workload-matched selectors. V18 does not replace any of
these systems with a home-grown imitation.

## Fairness conclusion

External evidence supports one exact decision-bearing subset and one
output-comparable subset. It does not support a raw cross-runtime speed ranking,
a claim over all CKKS tuners, or a universal superiority statement.
