# 제8장 결과

## 8.1 결과 보고 원칙

이 장의 모든 수치는 frozen evidence와 Paper Artifacts V3에서 가져온다. Seed 0는 development/descriptive로, seeds 1--4는 confirmatory로 분리한다. Trial 감소는 Security-V2가 admit한 700/560 candidate를 분모로 사용한다. Latency ratio는 `catalog latency / direct latency`로 정의한다. Structural audit의 한 REJECT와 provenance fail-closed 사건을 성공 결과에서 제거하지 않는다.

## 8.2 Primary direct selection과 trial 감소

표 3은 primary direct selection 및 locked audit의 seed 역할별 결과다. Development seed 0의 10 instance는 14 candidate trial과 42 selection key run을 사용했다. Confirmatory seeds 1--4의 40 instance는 56 candidate trial과 168 selection key run을 사용했다. 모든 instance에서 selection candidate가 확립되었고 selection execution failure는 없었다. Audit key run은 development 30회, confirmatory 120회였다.

{{V3_TABLE_03}}

<!-- P:RESULT-TRIAL CLAIM:formal_trial_reduction -->
FlipGuard는 Security-V2 bounded catalog의 700개 후보 대비 전체 70회, confirmatory 560개 후보 대비 56회의 encrypted candidate trial을 사용해 두 경우 모두 90% 감소를 기록했다. 표 4와 그림 4는 이 formal candidate-trial 회계를 나타낸다. Historical 1,100 execution은 pre-security-filter cost로 존재하지만 4개 excluded profile의 400 candidate를 포함하므로 정식 감소율 분모가 아니다.

{{V3_TABLE_04}}

{{V3_FIGURE_04}}

전체 기준으로 direct trial 비율은 `70/700=0.1`, confirmatory 기준은 `56/560=0.1`이다. 이 결과는 선언된 7-profile, 2-path bounded catalog 대비 encrypted candidate 실행 수를 줄였다는 뜻이다. 가능한 configuration 공간 전체의 search complexity를 90% 줄였다는 뜻은 아니다. Direct path가 catalog 밖 exact literal을 생성한다는 점 때문에 두 분자는 같은 후보 목록의 부분집합도 아니다.

## 8.3 Direct synthesis ablation

표 6은 development seed 0에서 수행한 ablation을 보여준다. Full FlipGuard와 graph-only/fixed-tolerance는 각각 14 trial, 4 repair, 10 SELECTED, 10 audit PASS로 동일했다. One-shot direct는 10 trial에서 6개만 선택되고 4개가 NO_SAFE였으며 validation flip 194개를 기록했다. Full policy는 사전동결 repair를 통해 이 네 one-shot 실패를 SAFE selection으로 전환했다. Latency-only/no-certification은 140 trial을 실행해 10개 후보를 선택했지만 validation flip 794개가 발생했고 audit PASS는 0이었다.

{{V3_TABLE_06}}

<!-- P:RESULT-REPAIR CLAIM:adaptive_repair -->
FlipGuard의 동결된 bounded repair는 선언된 개발 ablation에서 one-shot 실패 네 건을 SAFE 선택으로 전환했으며, 이는 보편적 repair 성공을 뜻하지 않는다. 이 ablation은 repair의 필요성과 decision gate 제거의 위험을 보여주지만, natural primary range에서 decision contract가 initial literal을 바꾸었다는 근거는 제공하지 않는다. Full과 graph-only 결과가 동일한 것은 minimum synthesis floor가 이 범위의 initial literal을 지배했음을 나타낸다.

## 8.4 Primary locked audit

Confirmatory seeds 1--4의 선택 literal 40개는 모두 disjoint locked audit을 통과했다. Flip 0, reserve-policy violation 0, execution FAILED 0, retuning 0이었다. Development seed 0도 10/10 PASS, flip 0, violation 0, retuning 0이었다. 두 population은 표 3에서 분리되어 있으며 그림 6은 전체 descriptive audit outcome을 시각화한다.

{{V3_FIGURE_06}}

<!-- P:RESULT-AUDIT CLAIM:primary_no_retuning_locked_audit -->
동결 literal의 no-retuning locked audit은 confirmatory seeds 1--4에서 40/40, development seed 0에서 10/10 통과했다. 이 결과의 단위는 10 dataset-model workload와 그 내부의 repeated partition이며 서로 독립인 50개 workload가 아니다. 또한 fixed held-out artifact에 대한 결과이므로 미래 입력 분포에 대한 무조건적 audit 통과를 의미하지 않는다.

Source replay는 50/50에서 검증되었고 preprocessing method는 `identity_model_input_v1`이었다. Comparator v1의 validation identity mismatch는 prepared representation의 provenance/full-precision 차이를 source 차이로 해석해 fail-closed한 사건이었다. V2 audit은 source raw, prepared raw, semantic, ordered row, model digest를 분리했고 50/50을 semantic CLASS A로 판정했다. 이 해결은 encrypted rerun이나 candidate 변경 없이 이루어졌다.

## 8.5 NO_SAFE control

표 7과 그림 7은 두 NO_SAFE control을 제시한다. Confirmatory one-candidate budget control 40 instance 중 24개는 SELECTED, 16개는 NO_SAFE였다. Declared finite two-candidate domain에서는 50/50이 NO_SAFE였고 SELECTED는 0이었다. 실패 row를 삭제하거나 candidate budget을 사후 확장하지 않았다.

{{V3_TABLE_07}}

{{V3_FIGURE_07}}

<!-- P:RESULT-NOSAFE CLAIM:no_safe_behavior -->
사전동결 budget control은 40건 중 16건에서 NO_SAFE를, 선언된 finite-domain control은 50/50에서 NO_SAFE를 반환했다. 이 결과는 FlipGuard가 안전성을 확립할 수 없는 조건에서 기권 상태를 표현한다는 근거다. 그러나 해당 candidate domain 밖에 SAFE literal이 존재하지 않는다는 결론은 아니다.

## 8.6 Paired latency

표 5와 그림 5는 동일 host에서 수행한 paired latency 결과를 보여준다. Confirmatory seeds 1--4의 40/40 workload-partition instance가 완결되었고 measurement failure는 0이었다. Direct와 catalog arm은 모두 decision SAFE였고 reference도 40/40 SAFE였다. No outlier removal, warm-up 1회, measurement pass 6회, balanced cyclic/reverse order가 검증되었다.

{{V3_TABLE_05}}

{{V3_FIGURE_05}}

<!-- P:RESULT-LATENCY CLAIM:paired_latency -->
Security-V2 bounded-catalog total latency divided by direct total latency의 dataset-model-cluster geometric mean은 confirmatory population에서 `3.14065956642714`였다. 10 dataset-model cluster를 resampling unit으로 한 bootstrap 95% confidence interval은 `[2.3423342246526992, 4.21531336367743]`이었다. Evaluation-only ratio의 geometric mean은 `2.624674483419857`이었다. Lower confidence bound가 1보다 크므로 선언된 post-freeze workload와 host에서 direct arm의 paired total latency 감소 claim이 admission 조건을 통과했다.

Confirmatory arm별 total latency는 catalog mean 478.948 ms, median 416.171 ms, p95 1000.148 ms였고 direct는 mean 145.892 ms, median 134.727 ms, p95 247.771 ms였다. Evaluation-only latency는 catalog mean 149.180 ms와 direct mean 61.317 ms였다. Workload-partition catalog/direct total ratio의 min/median/max는 1.8506/3.3972/5.4107, cluster ratio는 1.8854/3.4278/5.3583이었다. 모든 cluster에서 ratio가 1보다 컸지만, 이는 현재 workload와 host에 대한 관측이다.

Within-workload total-latency CV의 median은 catalog 0.1362, direct 0.1567이었고 max는 각각 0.3812, 0.3275였다. Arm-position normalized effect는 position 1, 2, 3에서 각각 0.9988, 1.0029, 0.9983으로 1에 가까웠다. 이러한 보조 결과는 order imbalance가 headline ratio를 지배한다는 징후가 없음을 보여주지만, 다른 host에서 같은 ratio를 보증하지 않는다.

Seed 0는 descriptive only다. Total ratio는 `3.1461387110645793`이며 rounded display는 3.146139다. 이 값은 confirmatory geometric mean에 포함하지 않았다. Seed 0의 total latency는 catalog mean 474.753 ms, direct mean 144.503 ms였으며 failure는 0이었다.

## 8.7 Margin-utilization sensitivity

표 8은 theorem과 operational policy를 분리하고 `rho` sensitivity를 보고한다. Tested grid는 0.1, 0.25, 0.5, 0.75, 0.9다. Natural primary workload에서 candidate-state change, bounded-oracle selection change, direct initial literal change는 모두 0이었다. 그림 3에서 보인 `e<m`은 decision preservation 충분조건이고 `e<0.5m`은 primary reserve policy다.

{{V3_TABLE_08}}

이 불변성은 `rho=0.5`가 최적이라는 증거가 아니다. 오히려 tested natural range에서 minimum synthesis floor가 candidate generation을 지배했고 decision contract의 margin 변화가 initial literal까지 활성화되지 않았음을 보여준다. Decision contract는 validation admission에는 사용되었으나, natural primary data에서 literal을 직접 차별화했다는 claim은 열리지 않는다.

## 8.8 Structural polynomial extension

`mlp_square_poly3` structural holdout 25 instance는 43 candidate trial, 18 repair, 129 selection key run을 사용해 25/25가 SELECTED였다. Selection FAILED와 NO_SAFE는 0이었다. Locked audit은 75 key run을 사용했고 24 PASS, 1 REJECT, 0 FAILED, 0 retuning이었다. Flip은 0, reserve-policy violation은 1이었다. 표 9는 negative result를 포함한 outcome을 제시한다.

{{V3_TABLE_09}}

<!-- P:RESULT-STRUCT CLAIM:structural_extension -->
`mlp_square_poly3`는 25/25 선택됐고 no-retuning audit에서 24건 PASS와 decision flip 없는 reserve-policy REJECT 1건을 기록했다. 실패 instance는 seed 4, banknote, `mlp_square_poly3`였고 candidate는 `synth_analysis_minimum_rescale_N14_Q10_S22_01ae407b2f60`이었다. Validation의 margin utilization은 0.470653으로 cap 0.5 아래였지만 audit은 0.5613685로 cap을 넘었다.

이 row의 classification은 `OBSERVED_DECISION_PRESERVED`, `RESERVE_POLICY_REJECTED`, `POLICY_REJECTED_WITHOUT_FLIP`이다. Plaintext와 CKKS decision은 같았고 cryptographic execution도 성공했다. REJECT 이유는 사전동결 reserve가 audit에서 소진되었기 때문이다. Audit 결과를 보고 scale이나 Q를 늘리지 않았고 policy modification count는 0이다.

그림 9는 validation과 audit margin utilization 및 cap 관계를 보여준다. 이 negative result는 selection SAFE가 unseen audit의 reserve-policy PASS를 보장하지 않음을 실증하며, locked audit을 별도 단계로 둔 설계의 필요성을 보여준다.

{{V3_FIGURE_09}}

## 8.9 Scoped non-tabular extension

표 10과 그림 8은 Sobel, Harris, CNN-lite adapter 결과를 structural matrix 안에서 제시한다. Sobel은 BSDS500 validation 400 sample과 audit 400 sample을 사용했다. Initial candidate는 violation 4건으로 REJECTED였고 한 번의 repair 후 SELECTED되었다. Locked audit은 flip 0, violation 0, retuning 0으로 PASS했다. Validation과 audit image는 각각 50개이고 overlap은 0이었다.

Harris는 validation 200 sample과 audit 200 sample을 사용했다. Initial candidate가 repair 없이 SELECTED되었고 locked audit은 flip 0, violation 0, retuning 0이었다. 역할별 image는 50개, image당 window는 4개였다. Sobel과 Harris의 결과는 single-patch gradient-energy 및 single-window response threshold에 관한 것이다.

CNN-lite는 MNIST digit 0-vs-1 scalar-replicated graph의 validation 250 image와 audit 250 image를 사용했다. Selection과 audit은 각 750 encrypted sample-key evaluation을 기록했고 모두 flip 0, violation 0이었다. Candidate는 Security-V2 PASS였고 audit에서 byte-identical literal을 재생했다. Plaintext accuracy는 validation 0.98, audit 0.992였지만 이 task accuracy를 decision-integrity certificate와 혼합하지 않는다.

{{V3_TABLE_10}}

{{V3_FIGURE_08}}

<!-- P:RESULT-NONTAB CLAIM:scoped_non_tabular_extension -->
Sobel, Harris, CNN-lite adapter는 각 선언된 finite input과 scalar-replicated execution 범위에서 selection과 no-retuning audit evidence를 제공한다. 이 결과로 packed CNN, full-image operator accuracy, arbitrary image graph 지원을 주장하지 않는다.

## 8.10 Independent training/data-seed extension

표 11은 3 dataset과 dataset별 3 independent training/data seed로 생성한 9 model instance의 결과다. Selection은 9 trial, 27 key run에서 9/9 SELECTED, repair 0, flip 0, violation 0이었다. Audit은 27 key run에서 9/9 PASS, flip 0, violation 0, retuning 0이었다. Selection과 audit encrypted sample evaluation은 각각 1,854였다.

{{V3_TABLE_11}}

<!-- P:RESULT-SEED CLAIM:training_model_seed_extension -->
세 dataset과 세 independent training/data seed로 생성한 9개 model instance가 9/9 selection과 no-retuning audit PASS를 기록했다. Candidate ID는 prepared-contract path를 결합하므로 9건 모두 representation상 달랐지만 exact CKKS literal parameter와 Security-V2 facts는 일치했다. 이 extension은 fixed-model repeated partition의 한계를 일부 보완하지만 9개 model만으로 보편적인 training-seed robustness를 확립하지 않는다.

## 8.11 Security re-attestation

표 12는 Security-V2 및 exact-Q/P 재감사 결과다. Direct-selected candidate row 50개는 모두 static re-attestation PASS였고 minimum headroom은 13 bit였다. Catalog profile 11개 중 7개가 admitted, 4개가 excluded되었다. Exact estimator model object는 두 model에서 17 PASS, 1 excluded였고 excluded object는 128-bit 목표 아래로 남았다.

{{V3_TABLE_12}}

<!-- P:RESULT-SEC CLAIM:security_attestation -->
선택 후보의 exact Q/P를 Security Policy V2와 두 estimator model에서 재감사했으며, 실제 Lattigo Xe truncation과 estimator 분포의 exact equivalence는 주장하지 않는다. Q와 QP를 별도로 검사했고 formal catalog와 paired arm은 admitted candidate만 사용했다. 이 결과는 선언된 object와 policy의 admission 근거이지 임의 runtime distribution의 보편적 128-bit 보증이 아니다.

Security filter는 comparison 결과에도 영향을 주었다. Pre-security oracle과 V2 fastest-safe selection은 alpha 전체 250 workload-alpha cell 중 125개에서 달랐고, primary alpha 0.5에서는 50개 중 25개에서 달랐다. 따라서 catalog execution이 성공했다는 이유만으로 security-compliant comparator에 포함할 수 없으며, 1,100 historical ledger를 그대로 oracle로 사용하는 것은 부적절하다.

## 8.12 Failure 및 negative-result taxonomy

표 13은 연구 중 보존한 failure class와 claim effect를 정리한다. One-shot numerical reject는 bounded repair ablation의 입력이 되었고, budget 및 finite-domain NO_SAFE는 scoped abstention을 지지했다. Structural `VALIDATION_NEAR_BUDGET_LIMIT_AUDIT_OVERRUN`은 structural claim을 partial로 낮췄다. Validation identity v1 mismatch는 v2 semantic audit으로 원인을 분리했지만 원래 fail-closed record를 삭제하지 않았다. Provider import와 rejection은 appendix evidence로만 남겼다.

{{V3_TABLE_13}}

Negative result를 포함한 전체 claim scope는 그림 10에 제시한다. Core paper는 11개 admitted claim을 사용하며 9개 BLOCKED 또는 NOT_EVALUATED claim은 limitation과 future work로 남긴다.

{{V3_FIGURE_10}}

## 8.13 연구 질문에 대한 답

**RQ1:** 선언된 Security-V2 bounded catalog와 비교할 때 direct synthesis는 전체 70/700, confirmatory 56/560 candidate trial을 사용해 두 population 모두 90% 감소했다. 이 답은 candidate trial 단위와 유한 catalog 범위에 한정된다.

**RQ2:** Confirmatory 40/40과 development 10/10 primary literal이 no-retuning locked audit을 통과했다. Bounded repair는 development ablation의 four one-shot failure를 SAFE로 전환했고, control은 16/40 및 50/50 NO_SAFE를 반환했다. 이는 finite artifact의 empirical admission과 기권 behavior를 지지한다.

**RQ3:** Confirmatory catalog/direct total-latency ratio의 cluster geometric mean은 3.140660, 95% CI는 [2.342334, 4.215313]이었다. 한 host와 선언 workload 범위에서 direct arm의 paired latency가 낮았으며 production 성능 결론은 내리지 않는다.

**RQ4:** Deeper polynomial graph는 25/25 selection 후 audit 24 PASS와 1 reserve-policy REJECT를 보였다. Sobel/Harris/CNN-lite와 independent training/data seed는 각 finite scope에서 admission을 통과했다. 따라서 structural/scoped extension은 부분적으로 지지되지만 arbitrary packed graph나 분포 전체 일반화는 남아 있다.

