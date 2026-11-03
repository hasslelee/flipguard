# Step 7E.1 Direct-Synthesis Ablation Results

Status: `SUPPORTED` for the predeclared seed-0 development ablation on
2026-07-30. Adaptive repair is `SUPPORTED` in this scope. A distinct
decision-contract effect on candidate synthesis is `BLOCKED` because it was
not observed. `paper_claim_allowed=false`.

The immutable protocol is
`docs/research/step_7e1_direct_synthesis_ablation_protocol.md`. It was
committed before graph-only planning or encrypted execution. This result
document changes neither Direct Policy V2 nor Security Policy V2.

## Frozen Scope

The ablation uses the ten development workloads:

```text
5 datasets x {linear_poly3, mlp_square_linear_score}
x partition seed 0
```

The one-shot and full arms reuse the existing clean-source direct ledger. The
latency-only arm reuses the 140 Security-V2-admitted seed-0 catalog
executions. Only graph-only selection and its locked audit create new
encrypted results.

| Frozen identity | Value |
|---|---|
| Protocol commit | `1767c54` |
| Execution commit | `062e1a9e0305b57ae75d681eb35a4655c5f00c43` |
| Execution-source digest | `sha256:5e7e0be1e69918b14445c97d3c05b4afe6aef874c6c928ed1d15c15e7ef38fb2` |
| Ablation contract | `sha256:8521da562e477d2a2f5dc60e3524affe85a22067225764a5910fe78e3ac0d6bf` |
| Direct Policy V2 | `sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603` |
| Security Policy V2 | `sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055` |

## Arm Results

| Arm | Selected | NO_SAFE | Trials | Repairs | Key runs | Encrypted evaluations | Validation SAFE / REJECTED | Audit PASS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Graph-only fixed tolerance | 10 | 0 | 14 | 4 | 42 | 7,365 | 10 / 0 | 10 |
| One-shot direct | 6 | 4 | 10 | 0 | 30 | 4,938 | 6 / 4 | 6; 4 N/A |
| Full FlipGuard | 10 | 0 | 14 | 4 | 42 | 7,365 | 10 / 0 | 10 |
| Latency-only, no certification | 10 | 0 | 140 | 0 | 140 | 23,044 | 0 / 10 | NOT EVALUATED |

All evaluated graph-only and full-arm audits had zero flips, zero violations,
and zero retuning. The one-shot SAFE subset reuses six existing byte-identical
audits, which also pass. A NO_SAFE one-shot row has no selected literal, so
its audit is `NOT_APPLICABLE`, not zero.

The latency-only arm chooses the fastest execution-OK candidate before looking
at its decision certificate. It selected a REJECTED candidate in 10/10
workloads, with 794 certifiable-row decision flips and 1,610 certifiable-row
error violations in the reused catalog ledger. It has no locked-audit claim.

## Adaptive Repair Effect

Four `linear_poly3` first candidates were REJECTED:

- `banknote`;
- `digits_binary`;
- `mnist_pool16`;
- `wdbc`.

Consequently, the one-shot arm returned NO_SAFE for 4/10 workloads. The
frozen `+4`-bit numerical repair reached SAFE on the second trial in all four,
and every repaired literal passed locked audit without retuning.

This supports the bounded repair mechanism in the declared development scope.
It does not prove that every repair succeeds or that four workloads are
independent statistical replications.

## Decision-Contract Effect

Graph-only synthesis uses fixed output tolerance `0.001`; full FlipGuard uses
the threshold decision contract. Their candidate ID strings differed in
10/10 workloads because IDs bind policy and contract identity.

After comparing literal identity as execution path plus CKKS parameters:

| Comparison | Differences |
|---|---:|
| Initial literal parameters | 0/10 |
| Selected literal parameters | 0/10 |
| Trials, repairs, or outcome | 0/10 |

Therefore, a decision-contract effect on candidate synthesis was not observed
on these natural development workloads. The minimum precision/scale guards
dominated both proposal modes. This negative result blocks a strong claim
that natural decision margins generally cause FlipGuard to choose different
CKKS parameters.

The decision-integrity gate remains operational: it rejected four one-shot
initial candidates and all ten latency-only choices. Existing finite-domain
and NO_SAFE controls show conditions in which certification matters, but they
do not convert this natural-data synthesis ablation into a positive
decision-margin result.

## Recovery Disclosure

The first graph-only audit attempt set failed at the path identity check:
the frozen split manifest named the original results path while the new
selection bound byte-identical evidence-pack paths. The runner made three
pre-CKKS attempts for each of ten workloads, preserving 30 failure logs.

A run-local compatibility view changed only the two represented paths.
Ordered row membership and CSV digests remained identical. Selection reruns,
semantic split changes, and pre-recovery audit CKKS executions were all zero.
The ten recovered audits then passed.

## Evidence And Claim Boundary

Frozen evidence:

```text
docs/evidence/direct_synthesis_ablation_v1/
manifest sha256:0f40f6041bf2a8999e125fad3d517c68bc47a80ba7bcb12900493ab629dc2e46
```

The deterministic verifier checks execution-source closure, binaries,
policies, all referenced frozen ledgers, literal identity, trial and key-run
accounting, the 30 failure logs, compatibility manifests, recovered audits,
and a byte-for-byte pack rebuild.

This ablation supports bounded adaptive repair and the need to certify rather
than choose latency alone. It does not support a distinct natural-data
decision-margin synthesis effect, a global optimum, universal model support,
or confirmatory inference from seed 0.

