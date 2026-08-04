# FlipGuard Results

This document reports frozen observations with their formal denominators and claim scope. It distinguishes development partitions, post-freeze confirmatory partitions, historical execution accounting, and later multiclass extensions.

## Controlled Primary Study

The primary study contains 5 real tabular datasets, 2 graph families, and 5 deterministic repeated partitions: 50 workload-partition instances across 10 dataset-model clusters. Seed 0 is development/descriptive. Seeds 1–4 are post-freeze confirmatory repeated partitions. The 50 rows are not 50 independent workloads or models.

### Candidate Accounting

| Population | Direct trials | Security-V2 catalog candidates | Reduction |
|---|---:|---:|---:|
| All 50 instances | 70 | 700 | 90% |
| Confirmatory seeds 1–4 | 56 | 560 | 90% |

The formal catalog consists of 7 Security-V2-admitted profiles and 2 supported paths. The historical ledger contains 1,100 pre-security executions, including 400 records from 4 later-excluded profiles. That ledger documents work actually performed and security sensitivity; it is not the formal Security-V2 tuning-work denominator.

Evidence: [Security-V2 bounded oracle](evidence/security_v2_bounded_oracle_v1/) and [paper claim admission](evidence/paper_claim_admission_v1/).

### Locked Audit

| Role | Instances | PASS | Retuning |
|---|---:|---:|---:|
| Development seed 0 | 10 | 10 | 0 |
| Confirmatory seeds 1–4 | 40 | 40 | 0 |

The selected validation literal was replayed on disjoint audit data. The confirmatory statement is based on seeds 1–4; seed 0 is not silently added to its aggregate.

### Paired Latency

The primary inference unit is the dataset-model cluster, with repeated partitions inside each cluster. Across 40 complete confirmatory workload-partition instances, the geometric mean of

```text
Security-V2 bounded-catalog total latency / direct total latency
```

was **3.140660**, with cluster-bootstrap 95% CI **[2.342334, 4.215313]**. The eval-only ratio was 2.624674. There were no failed paired workloads, no outlier removal, and all 40 fixed-reference rows were decision `SAFE`.

This is a one-host paired measurement against a declared bounded catalog, not a production or universal speedup. Evidence: [confirmatory paired-latency admission](../results/thesis_grade_protocol/paired_latency_claim_admission_v1/).

## Abstention Controls

- In confirmatory budget controls, 16 of 40 cases returned `NO_SAFE`; 24 were selected.
- In the finite-domain control, 50 of 50 cases returned `NO_SAFE`.

These controls demonstrate bounded abstention behavior under their predeclared candidate budgets. They do not prove global infeasibility. Evidence: [confirmatory NO_SAFE controls](evidence/no_safe_controls_confirmatory_v1/) and the dependencies listed in the [claim registry](evidence/paper_claim_admission_v1/).

## Structural and Robustness Evidence

The deeper `mlp_square_poly3` holdout selected 25 of 25 candidates. Locked audit produced 24 PASS outcomes and one reserve-policy rejection, with zero decision flips and zero retuning.

The rejected banknote seed-4 observation had an audit margin-utilization ratio above the predeclared 0.5 cap. The plaintext and CKKS decisions still agreed. Its classification is:

```text
OBSERVED_DECISION_PRESERVED
RESERVE_POLICY_REJECTED
POLICY_REJECTED_WITHOUT_FLIP
```

The negative result remains visible and limits the structural-generalization claim. Evidence: [structural extension](evidence/structural_extension_v1/) and [failure analysis](evidence/structural_audit_failure_analysis_v1/).

Additional scoped evidence includes finite Sobel, Harris, CNN-lite, and 9 independently trained data/model seed cases. These are adapter-scoped robustness results, not arbitrary packed-CNN support.

## Standard Multiclass Extension

Two MNIST models use the multiclass argmax contract and the same disjoint split manifest: 500 configuration-validation images and 500 locked-audit images per model, balanced by class, with three fresh-key runs.

| Model | Plaintext test accuracy | Validation | Locked audit | Argmax flips | Direct status |
|---|---:|---:|---:|---:|---|
| MLP-100, square activation | 97.76% on 10,000 images | 500 | 500 | 0 | selected in 1 trial, 0 repairs |
| LeNet-5-small, square activation | 98.91% on 10,000 images | 500 | 500 | 0 | selected in 1 trial, 0 repairs |

Both results are finite-scope validation/audit observations. Evidence: [final multiclass extension](evidence/journal_multiclass_extension_final_v1/).

### Natural Top-Two-Gap Activation

For MLP-100, the decision-aware contract selected S29 while graph-only fixed tolerance produced S32. This is an observed literal effect attributable to the top-two-gap contract within the declared protocol.

The literal difference did not produce admitted S29-over-S32 latency superiority. On the frozen 100-image latency subset:

| Ratio | Geometric mean | 95% CI | Interpretation |
|---|---:|---:|---|
| S32 graph-only / S29 gap-aware total latency | 0.999780 | [0.998648, 1.000920] | no admitted superiority |
| S40 frozen catalog / S29 gap-aware total latency | 1.981795 | [1.979758, 1.983842] | admitted within the frozen MLP catalog comparison |

The graph-only S32 comparator has no separate full 500-image locked-audit replay; its decision checks in this amendment are limited to the 100-image latency subset. Evidence: [MLP paired latency](evidence/journal_mlp_paired_latency_v1/).

### LeNet Catalog Coverage

All 7 frozen Security-V2 catalog profiles were `PLAN_UNSUPPORTED` for the LeNet-5-small required depth. FlipGuard direct synthesis generated a literal that passed the declared security gate and finite validation/audit. The catalog result must not be restated as `NO_SAFE`, absence of a candidate in all CKKS catalogs, a global optimum, or a direct-vs-catalog latency win.

## Security Qualification

Security Policy V2 checks exact `Q` material for ciphertext objects and `QP` material for evaluation-key objects against its declared published-table policy. Four of the original 11 profiles were excluded; 7 remained in the formal bounded catalog.

The exact-estimator reconciliation identified a result-scope and aggregation mismatch in the initial multiclass estimator adapter. Corrected static materialization reported minimum classical estimates of 145.229851 bits for MLP-100 and 132.046928 bits for LeNet-5-small under the matched declared model. The runtime error distribution is not modeled exactly, and a quantum cost model was not evaluated. The admitted wording is therefore qualified rather than universal.

Evidence: [formal Security-V2 attestation](evidence/security_v2_static_attestation_formal_v2/), [exact estimator](evidence/exact_security_estimator_v1/), and [multiclass security reconciliation](evidence/journal_multiclass_security_reconciliation_v1/).

## Negative and Unsupported Results

FlipGuard preserves results that narrow a claim:

- one structural reserve-policy rejection without a decision flip;
- no MLP S29-over-S32 latency superiority;
- LeNet frozen catalog `PLAN_UNSUPPORTED` for 7 of 7 profiles;
- natural primary alpha sensitivity did not change the initial literal in the tested range;
- empirical admission does not instantiate an analytical CKKS certificate;
- provider-format and cross-runtime evidence remains auxiliary and scoped.

These outcomes are not removed or relabeled to improve an aggregate. See [Claim Scope](CLAIM_SCOPE.md) before quoting a result.
