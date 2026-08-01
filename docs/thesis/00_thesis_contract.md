# FlipGuard Thesis Narrative Contract V1

Status: `FROZEN_NARRATIVE_CONTRACT_V1`

## Document Identity

- Korean title: **결정 무결성 계약 기반 CKKS 실행 구성 직접 합성 및 검증 기법**
- English title: **FlipGuard: Decision-Integrity-Aware Direct Synthesis and Validation of CKKS Configurations**
- Release baseline: `flipguard-thesis-v1.0.0-rc2`
- RC2 source: `6c5f8b234f9f9da91a189fa0f2dc180bb996abf5`
- RC2 archive SHA-256: `05ef70306a11ab577243b0c708489864f19ccd104e6036e28fc6bd1dab45c0be`
- Paper Artifacts V3 manifest SHA-256: `32d378b371b75d31b8e39ef2acce4c3c7353581ccfbd5e6c7d22b30ffaf4743b`
- Claim-admission manifest SHA-256: `d982f0f81915b760c537244fc71aa992bf521eaf65d57a67c2d96dbae0607b8d`
- Margin-interpretation manifest SHA-256: `12626638b1abb5d57155345ee84e7e145dc13bfc947767f4484b1e18475cdce0`

The title may later receive surface-level edits required by the university,
but those edits must not change the research contribution or claim scope.

## Central Statement

FlipGuard는 지원되는 계산 그래프와 threshold decision-integrity
contract로부터 CKKS literal을 직접 합성하고, 제한된 encrypted trial과
failure-aware bounded repair를 통해 후보를 승인 또는 거부하며, SAFE
후보가 없으면 NO_SAFE로 abstain하고, 선택한 literal을 disjoint locked
audit에서 retuning 없이 재생한다.

## Research Questions

### RQ1: Direct synthesis and tuning work

지원되는 계산 그래프와 decision-integrity contract에서 CKKS literal을
직접 합성하여 Security-V2 bounded catalog 대비 encrypted candidate
trial을 줄일 수 있는가?

### RQ2: Admission, repair, abstention, and locked replay

직접 합성 후보와 bounded repair가 finite validation scope에서
decision-integrity admission을 통과하고, 선택 literal이 disjoint locked
audit에서 retuning 없이 유지되는가? 또한 안전한 후보를 확립할 수 없을
때 NO_SAFE를 반환하는가?

### RQ3: Paired latency

동일 host의 paired protocol에서 direct configuration은 Security-V2
bounded-catalog fastest-safe configuration보다 어떤 latency 차이를
보이는가?

### RQ4: Scope and negative results

이 결과는 deeper polynomial graph, scoped Sobel/Harris/CNN-lite, 독립
training/data seed에서 어느 범위까지 유지되며, 어떤 negative result와
한계를 보이는가?

## Contributions

1. Threshold inference를 위한 decision-integrity workload contract와
   finite-scope admission을 정의하고 구현한다.
2. 계산 그래프에서 CKKS literal을 직접 합성하고, 관측된 실패 유형에
   대응하는 bounded failure-aware repair를 수행한다.
3. 방어 가능한 후보가 없을 때의 NO_SAFE와 선택 literal을 변경하지 않는
   no-retuning locked-audit protocol을 제공한다.
4. Security-V2 bounded comparison, paired latency, negative result,
   structural/scoped generalization을 claim과 provenance에 연결하는
   재현 가능한 evidence system을 제공한다.

## Claim Boundary

The authoritative claim vocabulary and allowed wording are defined only by
`docs/evidence/paper_claim_admission_v1/claims.json`. A blocked or unevaluated
claim may appear solely as a limitation, prohibited overclaim, or future-work
statement.

The following claims are prohibited as contributions or conclusions:

- first CKKS autotuner;
- first application-aware CKKS parameter generation;
- first direct CKKS configuration synthesis;
- first repair-based selection;
- universal graph or arbitrary packed-CNN support;
- global optimum or global oracle;
- an instantiated analytical CKKS certificate;
- distribution-wide safety;
- production or universal speedup; and
- universal {{N:security_target_bits}}-bit runtime security.

## Evidence and Statistical Contract

- Seed 0 is development/descriptive only.
- Seeds 1-4 are post-freeze confirmatory repeated partitions.
- Five deterministic partitions are not five independent dataset splits.
- The paired-latency inference unit is {{N:primary_dataset_model_clusters}} dataset-model clusters; raw timing
  pairs are not independent statistical samples.
- Formal catalog denominators are {{N:formal_catalog_all}} overall and {{N:formal_catalog_confirmatory}} confirmatory. The {{N:raw_historical_catalog_executions|,}}
  executions are historical pre-security-filter accounting only.
- The mathematical decision-preservation condition is `e_c(x) < m(x)`.
- The stricter `e_c(x) < rho*m(x)` with `rho={{N:primary_alpha}}` is a predeclared operational
  reserve policy, not a theorem constant or an optimized value.
- The structural result must retain {{N:structural_audit_pass}} audit PASS outcomes and {{N:structural_reserve_reject}}
  reserve-policy REJECT without a decision flip.

## Manuscript Authority

`docs/research/flipguard_v2_manuscript_draft_ko.md` remains an immutable
`NON_AUTHORITATIVE_SCAFFOLD`. The assembled V1 manuscript under
`docs/thesis/` is authoritative only after the thesis linter, deterministic
builder, RC2 overlay verifier, V3 verifier, and claim-admission verifier pass.
