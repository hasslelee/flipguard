# 제7장 평가 방법

## 7.1 평가 원칙

평가는 policy 개발과 post-freeze confirmatory evidence를 분리하고, candidate trial·key run·sample evaluation·wall-clock을 다른 단위로 보고하며, negative result를 삭제하지 않는 원칙을 따른다. Direct Policy V2, Security Policy V2, primary `rho={{N:primary_alpha}}`, margin floor `{{N:primary_margin_floor}}`, repair rule, maximum trial `{{N:max_encrypted_trials}}`, split assignment는 confirmatory execution 전에 동결되었다. Audit 결과를 이용한 candidate 변경은 허용하지 않았다.

표 2는 primary, structural, non-tabular, independent training-seed evidence의 선언 범위와 inference unit을 요약한다.

{{V3_TABLE_02}}

## 7.2 Primary workload

Primary evaluation은 `banknote`, `digits_binary`, `iris_binary`, `mnist_pool16`, `wdbc`의 {{N:primary_datasets}}개 dataset과 `linear_poly3`, `mlp_square_linear_score`의 {{N:primary_model_graphs}}개 model graph를 결합한 {{N:primary_dataset_model_clusters}} dataset-model workload로 구성한다. 각 workload의 fixed held-out artifact를 {{N:deterministic_partitions}}개 deterministic partition seed로 나누어 configuration-validation과 locked audit을 구성했다. 따라서 전체는 {{N:combined_descriptive_instances}} workload-partition instance다.

이 {{N:combined_descriptive_instances}}개 row를 독립적인 dataset, 독립적인 model, 독립적인 statistical sample로 해석하지 않는다. {{N:deterministic_partitions}}개 partition은 동일한 학습 model 및 held-out artifact를 반복 partition한 것이다. Seed 0는 direct policy와 ablation 개발에 사용되었으므로 development/descriptive population으로 분리한다. Seeds 1--4의 {{N:confirmatory_instances}}개 instance만 post-freeze confirmatory aggregate에 포함한다.

각 candidate trial은 fresh key {{N:fresh_key_repeats}}개로 configuration-validation을 실행한다. Selection candidate가 정해지면 audit artifact에서 다시 {{N:fresh_key_repeats}}개 fresh key로 exact literal을 재생한다. Selection과 audit의 input domain은 split manifest로 분리하며 candidate identity, model digest, source semantic digest를 비교한다.

## 7.3 Bounded catalog와 회계

역사적 catalog는 {{N:security_catalog_profiles_total}} profile, {{N:catalog_execution_paths}} path, {{N:combined_descriptive_instances}} instance로 {{N:raw_historical_catalog_executions|,}} candidate execution을 포함한다. Security-V2는 profile {{N:security_catalog_profiles_admitted}}개를 admit하고 {{N:security_catalog_profiles_excluded}}개를 exclude했다. Formal bounded catalog는 {{N:security_catalog_profiles_admitted}}개 profile과 {{N:catalog_execution_paths}} path이므로 전체 {{N:formal_catalog_all}}개, seed 0 development는 {{N:formal_catalog_development}}개, confirmatory seeds 1--4는 {{N:formal_catalog_confirmatory}}개 candidate다.

Trial reduction은 다음으로 계산한다.

\[
R_{all}=1-\frac{T_{direct,all}}{N_{catalog,all}}, \qquad
R_{conf}=1-\frac{T_{direct,conf}}{N_{catalog,conf}}.
\]

{{N:raw_historical_catalog_executions|,}}회는 실제로 지불한 pre-security historical cost를 설명할 때만 사용한다. Security-V2 excluded {{N:security_excluded_catalog_candidates}}개를 formal oracle이나 direct-trial denominator에 포함하지 않는다. Catalog fastest-safe는 admitted candidate 중 동일 validation에서 SAFE이며 latency가 최소인 후보다.

## 7.4 평가 지표

Direct selection 지표는 candidate trial, repair count와 cause, fresh-key run, encrypted sample evaluation, SELECTED/NO_SAFE, candidate literal, security admission이다. Decision-integrity 지표는 validation 및 audit의 flip, reserve-policy violation, `V_cert`, `V_amb`, coverage, maximum margin utilization이다. Audit 지표에는 candidate identity match와 retuning count를 추가한다.

Performance 지표는 setup/keygen, evaluation-only, total latency의 mean, median, p95, standard deviation, interquartile range와 within-workload coefficient of variation이다. Arm position effect도 따로 분석한다. Security 지표는 ciphertext `LogQ` headroom, evaluation-key `LogQP` headroom, final admission, estimator model별 결과다.

## 7.5 Direct-synthesis ablation

Ablation은 seed 0 development partition에서 수행했다. `graph_only_fixed_tolerance`는 decision margin contract 없이 graph depth와 fixed precision으로 합성한다. `one_shot_direct`는 initial candidate만 실행해 adaptive repair를 제거한다. `full_flipguard`는 graph와 decision contract, encrypted validation, repair, certify-or-reject, NO_SAFE, locked audit을 모두 포함한다. `latency_only_no_certification`은 실행 가능한 빠른 candidate를 선택하고 decision gate를 제거한다.

이 비교의 목적은 각 component의 causal contribution을 제한된 개발 workload에서 관찰하는 것이다. Full과 graph-only가 같은 결과를 보이면 숨기지 않으며, natural data에서 margin contract가 initial literal을 바꾸었다고 주장하지 않는다. One-shot과 full의 차이는 bounded repair의 경험적 효과를, latency-only의 flip은 decision gate를 제거한 결과를 보여준다.

## 7.6 NO_SAFE control

NO_SAFE는 두 control로 평가한다. Confirmatory one-candidate budget control은 seeds 1--4의 {{N:no_safe_budget_total}} instance에서 candidate budget을 사전 고정한다. Finite-domain control은 선언한 두 candidate domain의 {{N:no_safe_finite_domain_total}} instance를 사용한다. Validation과 audit domain은 분리하며 control parameter를 primary workload에 역적용하지 않는다.

Control이 예상대로 NO_SAFE를 만들지 못하더라도 사후에 budget이나 input을 바꾸지 않는 것이 protocol 원칙이다. NO_SAFE 결과는 global infeasibility가 아니라 해당 candidate budget/domain의 abstention behavior로만 해석한다.

## 7.7 Paired latency protocol

Paired latency는 모든 arm identity가 동결된 후 한 host에서 순차 수행했다. {{N:paired_arms}}개 arm은 direct-selected, Security-V2 bounded-catalog fastest-safe, fixed reference다. Warm-up은 {{N:paired_warmup_runs}}회, measurement run은 {{N:paired_measurement_runs}}회이며 balanced cyclic/reverse order를 사용했다. Outlier removal은 수행하지 않았다. 다른 CKKS process를 병렬로 실행하지 않았고 process restart와 arm position을 ledger에 기록했다.

Primary inference unit은 {{N:primary_dataset_model_clusters}} dataset-model cluster다. Seeds 1--4의 partition은 cluster 내부 repeated observation으로 취급한다. Catalog/direct ratio는 workload-partition별 paired latency ratio를 구성한 뒤 cluster 수준 geometric mean과 cluster bootstrap 95% confidence interval로 요약한다. Raw pair를 서로 독립인 표본으로 두는 p-value는 계산하지 않는다. Seed 0 ratio는 development/descriptive로만 보고 confirmatory aggregate에 합치지 않는다.

Formal latency claim은 confirmatory {{N:paired_confirmatory_complete}}/{{N:confirmatory_instances}} instance complete, direct/catalog arm SAFE, identity/source digest match, Security-V2 excluded candidate 부재, no concurrent CKKS process, no outlier removal, order protocol 검증, cluster-bootstrap lower bound `>1`을 요구한다. Reference가 REJECTED인 row는 diagnostic으로 남기되 reference safe-to-safe ratio에서 제외한다.

## 7.8 Structural polynomial holdout

Structural holdout은 `mlp_square_poly3`를 {{N:primary_datasets}} dataset과 {{N:deterministic_partitions}} partition에 적용한 {{N:structural_instances}} instance다. Direct Policy V2를 바꾸지 않았고 model-specific lookup, scale floor 변경, trial budget 변경을 금지했다. Selection은 graph signature, added depth/level, trial, repair, literal, security, validation outcome을 기록했다. Audit은 동일 literal을 no-retuning replay했다.

Structural 결과는 primary policy를 수정하는 feedback으로 사용하지 않는다. Audit REJECT가 나오면 그대로 보존하고 structural claim을 낮춘다. 이 설계는 deeper polynomial graph에서 policy transportability를 평가하되 한 graph family의 결과를 임의 graph generalization으로 확장하지 않는다.

## 7.9 Non-tabular scoped holdout

Sobel과 Harris는 BSDS500 natural image에서 사전동결 규칙으로 patch/window를 추출한다 [@martin2001bsds]. Sobel은 validation image {{N:sobel_validation_images}}개와 audit image {{N:sobel_audit_images}}개에서 각각 {{N:sobel_validation_samples}}/{{N:sobel_audit_samples}} sample을 사용한다. Harris는 역할별 image {{N:harris_validation_images}}개에서 각 {{N:harris_windows_per_image}}개 window, 즉 {{N:harris_validation_samples}}/{{N:harris_audit_samples}} sample을 사용한다. Image overlap은 0이며 threshold estimation용 image는 별도로 분리했다.

CNN-lite는 MNIST digit 0-vs-1의 학습된 scalar-replicated graph다 [@lecun1998gradient]. Validation {{N:cnn_lite_validation_samples}}개와 audit {{N:cnn_lite_audit_samples}}개 image를 사용했다. 이 평가에서 plaintext task accuracy와 decision-integrity outcome은 별도 지표다. Packed convolution, multiclass argmax, general LeNet performance는 평가하지 않는다.

## 7.10 Independent training/data-seed extension

Primary repeated partition은 동일 model artifact를 사용한다는 한계를 보완하기 위해 {{N:independent_training_datasets}} dataset에서 각각 {{N:independent_training_seeds_per_dataset}}개의 independent training/data-split seed를 사용해 {{N:independent_training_seed_total}} model instance를 별도로 생성했다. 이 extension은 `mlp_square_linear_score` graph에서 direct selection과 locked audit만 수행했고 full {{N:formal_catalog_all}}-candidate catalog를 반복하지 않았다. Statistical unit은 trained model instance이며 dataset별로 그룹화한다.

이 extension은 training randomness와 model artifact 변화에 대한 제한된 evidence를 제공한다. {{N:independent_training_datasets}} dataset과 {{N:independent_training_seeds_per_dataset}} seed만으로 model-seed 전반의 보편적 일반화를 추론하지 않는다. Primary의 deterministic partition 결과와 독립 학습 seed 결과를 같은 표본으로 합치지 않는다.

## 7.11 Security 및 artifact 검증

Security-V2 static re-attestation은 direct candidate, catalog profile, reference, paired arm의 exact Q/P를 검사한다. Two-estimator sensitivity는 exact prime을 입력으로 사용한다. Formal comparison은 admitted candidate만 포함한다. Evidence verifier는 security policy ID/digest, object별 Q/QP 판정, headroom, source commit을 확인한다.

모든 pack은 SHA256SUMS와 deterministic verifier를 갖는다. Final Paper Artifacts V3는 13개 table과 10개 figure를 frozen publication input으로 제공한다. 논문 본문 수치는 `number_registry.json`이 evidence에서 추출·검증하며, chapter source의 claim은 `claim_traceability.csv`와 paper claim admission registry에 연결한다.
