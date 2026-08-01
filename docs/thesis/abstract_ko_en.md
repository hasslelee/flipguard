# 국문 초록

## 결정 무결성 계약 기반 CKKS 실행 구성 직접 합성 및 검증 기법

CKKS 근사 동형암호는 암호화된 실수형 데이터에 대한 계산을 지원하지만, scale, modulus chain, polynomial degree와 실행 path의 선택에 따라 수치 오차와 지연이 크게 달라진다. 특히 score를 threshold와 비교하는 응용에서는 작은 근사 오차가 최종 decision을 바꿀 수 있으므로, 실행 가능성이나 평균 오차만으로 configuration을 승인하기 어렵다. 기존 compiler와 autotuner는 parameter, scale, bootstrapping, latency와 accuracy 최적화를 발전시켰으나, 서로 다른 candidate source에 공통으로 적용되는 threshold decision-integrity admission과 no-retuning audit은 별도 문제로 남는다.

<!-- P:ABSTRACT-KO-METHOD CLAIM:scoped_direct_synthesis,adaptive_repair,finite_scope_decision_integrity -->
본 논문은 지원 computation graph와 threshold decision-integrity contract에서 exact CKKS literal을 직접 합성하는 FlipGuard를 제안한다. FlipGuard는 graph fact로부터 scale과 Q/P chain 및 LogN을 계산하고, 최대 네 번의 encrypted trial에서 candidate를 검증한다. 실패 원인이 허용된 numerical 또는 level class일 때만 bounded repair를 수행하며 첫 SAFE에서 멈춘다. SAFE 후보를 확립하지 못하면 NO_SAFE로 기권하고, 선택 literal은 configuration-validation과 분리된 locked audit에서 retuning 없이 재생한다. Decision preservation의 충분조건 `e_c(x)<m(x)`과 운용 reserve policy `e_c(x)<0.5m(x)`를 구분하며, 후자의 0.5는 사전동결 margin-utilization cap이지 이론적 최적값이 아니다.

<!-- P:ABSTRACT-KO-PRIMARY CLAIM:formal_trial_reduction,primary_no_retuning_locked_audit,no_safe_behavior -->
Primary 평가는 5 dataset, 2 model graph, 5 deterministic repeated partition으로 구성한 50 workload-partition instance를 사용했다. Seed 0는 development/descriptive, seeds 1--4는 post-freeze confirmatory로 분리했다. Security-V2가 admit한 formal bounded catalog는 전체 700 candidate, confirmatory 560 candidate다. Direct synthesis는 전체 70회와 confirmatory 56회의 candidate trial을 사용해 두 경우 모두 90% 감소를 기록했다. No-retuning locked audit은 confirmatory 40/40과 development 10/10에서 PASS했고 retuning은 0이었다. Predeclared budget control은 16/40에서, finite-domain control은 50/50에서 NO_SAFE를 반환했다.

<!-- P:ABSTRACT-KO-EXT CLAIM:paired_latency,structural_extension,scoped_non_tabular_extension,training_model_seed_extension -->
동일 host의 paired protocol에서 Security-V2 bounded-catalog total latency를 direct total latency로 나눈 confirmatory dataset-model-cluster geometric mean은 3.140660이었고, cluster-bootstrap 95% confidence interval은 [2.342334, 4.215313]이었다. Deeper polynomial `mlp_square_poly3`는 25/25 selection 후 audit 24 PASS와 decision flip 없는 reserve-policy REJECT 1건을 기록했다. Sobel, Harris, scalar-replicated CNN-lite와 3 dataset x 3 independent training/data seed extension은 각 선언된 finite scope에서 selection과 audit evidence를 제공했다.

결과는 finite validation/audit artifact, 지원 adapter, frozen policy, 한 host의 latency 범위에 한정된다. 본 논문은 분포 전체의 decision safety, 임의 graph 지원, 구성 공간 전체의 최적성, production 성능, runtime distribution과 estimator의 완전한 동등성, 분석적 CKKS certificate를 주장하지 않는다. FlipGuard의 기여는 후보 생성 자체의 최초성보다 direct synthesis, empirical decision admission, bounded repair, abstention, immutable audit replay와 provenance를 하나의 재현 가능한 decision-integrity layer로 결합한 데 있다.

**주제어:** CKKS, 동형암호, 구성 합성, 결정 무결성, 암호화 검증, NO_SAFE, locked audit

# English Abstract

## FlipGuard: Decision-Integrity-Aware Direct Synthesis and Validation of CKKS Configurations

The CKKS approximate homomorphic-encryption scheme enables computation over encrypted real-valued data, but its numerical error and latency depend strongly on the scale, modulus chain, polynomial degree, and execution path. In applications that compare a score with a threshold, even a small approximation error can change the final decision. Execution success or an aggregate error metric alone is therefore insufficient for admitting a configuration. Existing compilers and autotuners have advanced parameter, scale, bootstrapping, latency, and accuracy optimization, while a common threshold decision-integrity admission rule and a no-retuning audit remain distinct concerns across candidate sources.

This thesis presents FlipGuard, which directly synthesizes exact CKKS literals from supported computation graphs and threshold decision-integrity contracts. FlipGuard derives the scale, Q/P chain, and LogN from graph facts and validates each candidate with at most four encrypted trials. It applies bounded repairs only to predeclared numerical or level failures and stops at the first SAFE candidate. When no SAFE candidate can be established, it abstains with NO_SAFE. The selected literal is then replayed without retuning on a locked audit disjoint from configuration validation. The sufficient decision-preservation condition, `e_c(x)<m(x)`, is explicitly separated from the operational reserve policy, `e_c(x)<0.5m(x)`; 0.5 is a predeclared margin-utilization cap rather than a theoretically optimal constant.

The primary evaluation uses 50 workload-partition instances formed from five datasets, two model graphs, and five deterministic repeated partitions. Seed 0 is development/descriptive, whereas seeds 1--4 are post-freeze confirmatory. The Security-V2-admitted formal bounded catalog contains 700 candidates overall and 560 confirmatory candidates. Direct synthesis used 70 and 56 candidate trials, respectively, yielding a 90% formal reduction in both populations. No-retuning locked audit passed for 40/40 confirmatory and 10/10 development instances with zero retuning. A predeclared budget control returned NO_SAFE in 16/40 instances, and a finite-domain control returned NO_SAFE in 50/50 instances.

Under a paired protocol on one host, the confirmatory dataset-model-cluster geometric mean of Security-V2 bounded-catalog total latency divided by direct total latency was 3.140660, with a cluster-bootstrap 95% confidence interval of [2.342334, 4.215313]. For the deeper polynomial `mlp_square_poly3` graph, all 25 instances were selected; locked audit produced 24 PASS outcomes and one reserve-policy REJECT without a decision flip. Sobel, Harris, scalar-replicated CNN-lite, and a three-dataset by three-independent-training/data-seed extension provide evidence only within their declared finite scopes.

<!-- P:ABSTRACT-EN-BOUNDARY CLAIM:security_attestation -->
These results are limited to finite validation/audit artifacts, supported adapters, frozen policies, and latency measurements on one host. This thesis does not claim distribution-wide decision safety, arbitrary graph support, whole-space optimality, production performance, exact runtime-estimator distribution equivalence, or a complete analytical CKKS certificate. FlipGuard's contribution is the reproducible integration of direct synthesis, empirical decision admission, bounded repair, abstention, immutable audit replay, and provenance into a decision-integrity layer.

**Keywords:** CKKS, homomorphic encryption, configuration synthesis, decision integrity, encrypted validation, NO_SAFE, locked audit
