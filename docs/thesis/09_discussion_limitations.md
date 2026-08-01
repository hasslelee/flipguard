# 제9장 논의와 한계

## 9.1 결과의 핵심 해석

FlipGuard의 가장 강한 결과는 catalog를 모두 실행한 뒤 선택하는 흐름에서 벗어나 graph에서 exact literal을 직접 합성하고, encrypted validation을 후보 승인에 집중시켰다는 점이다. Formal candidate trial이 전체 {{N:formal_catalog_all}} 대비 {{N:direct_trials_all}}, confirmatory {{N:formal_catalog_confirmatory}} 대비 {{N:direct_trials_confirmatory}}으로 감소했고 primary locked audit이 retuning 없이 통과했다. 동시에 latency-only candidate가 많은 flip을 만들고 one-shot direct가 NO_SAFE를 낳은 ablation은 candidate 실행 성공이나 속도가 decision-integrity를 대신할 수 없음을 보여준다.

그러나 이 결과를 “margin이 항상 더 좋은 literal을 만든다”로 해석하면 안 된다. Natural primary range에서 `rho` grid 변화는 candidate state, bounded-oracle selection, direct initial literal을 바꾸지 않았다. Graph-derived minimum synthesis floor가 초기 구성을 지배했다. Decision contract는 admission predicate와 failure reporting에서 작동했지만, primary natural data의 literal generation을 직접 차별화했다는 claim은 근거가 부족하다. 이는 framework의 한계를 드러내는 동시에 synthesis와 admission을 구분해야 하는 이유다.

## 9.2 `rho={{N:primary_alpha}}`의 의미

Decision preservation의 수학적 충분조건은 `e_c(x)<m(x)`다. Primary `e_c(x)<{{N:primary_alpha}}m(x)`는 더 엄격한 운용 reserve policy다. `rho={{N:primary_alpha}}`는 margin의 절반을 approximation error에 허용하고 나머지 절반을 관측되지 않은 variation에 남기는 해석 가능한 사전 정책이지만, CKKS noise theorem에서 유도된 값은 아니다. Sensitivity 결과도 이 값의 최적성을 보여주지 않는다.

정책 상수의 정당성은 두 층으로 평가해야 한다. 첫째, 연구 protocol 관점에서는 confirmatory 이전에 동결되어 audit 결과로 바뀌지 않았다는 점이 중요하다. 둘째, scientific optimality 관점에서는 여러 domain과 risk preference에서 calibration이 더 필요하다. 실제 배포에서는 application owner가 false acceptance/false rejection 비용, threshold calibration, acceptable abstention을 고려해 `rho`와 `delta`를 사전 선언해야 한다. 본 논문의 {{N:primary_alpha}}는 reproducible primary setting이지 보편 권고값이 아니다.

## 9.3 Structural audit negative result

Structural seed4/banknote instance는 validation utilization {{N:structural_validation_margin_utilization|.6f}}으로 SAFE였지만 audit utilization {{N:structural_audit_margin_utilization|.7f}}로 reserve cap을 초과했다. Decision flip은 없었다. 이 결과를 “audit 실패지만 실제 문제는 없었다”고 축소하면 사전 정책의 의미가 무너진다. 반대로 암호학적 correctness failure나 observed decision failure라고 부르면 실제 관측을 왜곡한다. 정확한 해석은 decision은 보존되었으나 reserve policy가 unseen audit에서 거부되었다는 것이다.

따라서 이 관측의 정식 분류는 `OBSERVED_DECISION_PRESERVED`,
`RESERVE_POLICY_REJECTED`, `POLICY_REJECTED_WITHOUT_FLIP`이다. 세 상태를 함께
기록해야 암호 연산 성공, 관측 결정 보존, 운용 여유 정책 거부를 서로 바꾸어
해석하지 않는다.

이 negative result는 두 가지를 보여준다. 첫째, finite validation admission이 disjoint audit PASS를 논리적으로 보장하지 않는다. 둘째, audit은 결과를 본 뒤 candidate를 강화하는 tuning set이 아니라 claim을 반증할 수 있는 장치여야 한다. 본 연구는 해당 row를 제거하거나 재선택하지 않았고 structural claim을 PARTIALLY_SUPPORTED로 유지했다. 운영 시스템에서는 이 audit 결과가 배포 전 발견되었다면 candidate를 사용하지 않고 human review 또는 새로운 사전 등록 protocol로 돌아가야 한다.

## 9.4 Finite candidate와 empirical certificate의 한계

FlipGuard의 SAFE는 선언된 finite validation과 관측 key repetition의 empirical certificate다. 입력 분포의 tail, adversarial input, 데이터 drift는 직접 포함하지 않는다. Audit이 disjoint여도 동일한 dataset/model family의 유한 artifact이므로 distribution-wide guarantee로 확대할 수 없다. Ambiguous region을 분리하는 것도 threshold 근처 위험을 사라지게 하지 않으며 certificate coverage를 명시하는 방식일 뿐이다.

분석적 certificate를 완성하려면 graph별 CKKS residual bound `B_c(x)`를 exact parameter와 input bound에서 인스턴스화하고, `B_c(x)<m(x)`를 domain 전체 또는 명시한 subset에서 증명해야 한다. 현재 implementation은 primitive bound를 결과 score까지 합성한 proof artifact를 제공하지 않는다. 따라서 empirical admission과 analytical proof를 구분한다.

## 9.5 Catalog 비교의 한계

Security-V2 bounded catalog는 {{N:security_catalog_profiles_admitted}} profile과 {{N:catalog_execution_paths}} path의 유한 비교 집합이다. Fastest-safe라는 명칭은 이 {{N:security_admitted_catalog_identities}} candidate identity 안에서만 성립한다. Direct candidate는 catalog 밖에 있을 수 있고, 더 넓은 configuration space에 더 빠르거나 더 안정적인 candidate가 존재할 수 있다. 그러므로 latency ratio는 global search baseline 대비 결과가 아니다.

그럼에도 bounded catalog는 유용한 평가 기준이다. 사전 선언되고 exhaustive하게 실행되었으며 동일 decision gate와 Security-V2 filter를 적용할 수 있기 때문이다. Historical {{N:raw_historical_catalog_executions|,}} execution을 보존하면서 formal denominator를 {{N:formal_catalog_all}}으로 수정한 과정은 security admission이 tuning-space 정의의 일부여야 함을 보여준다. 후속 연구는 여러 compiler/autotuner가 생성한 candidate set을 같은 gate에 투입해 provider별 recall과 regret을 비교할 수 있다.

## 9.6 Latency 일반화의 한계

Paired latency는 동일 host, 동일 process policy, frozen arms, balanced order에서 강한 내부 비교를 제공한다. Cluster bootstrap은 repeated partition을 독립 표본으로 부풀리는 문제를 피한다. Confidence interval lower bound가 1보다 높았으므로 현재 cluster 범위에서 direct arm의 total latency 감소는 안정적으로 관측되었다.

하지만 host는 하나이고 VMware virtual platform이다. CPU microarchitecture, memory hierarchy, OS scheduling, Lattigo version, Go runtime, cloud noisy neighbor가 달라지면 absolute latency와 ratio가 바뀔 수 있다. Scalar-replicated packing은 batch throughput을 최적화한 production configuration이 아니다. 따라서 결과는 연구 host에서의 paired comparison이며 production capacity planning 자료가 아니다.

## 9.7 Graph 및 packing scope

Primary graph adapter는 두 tabular formula를 지원하고 structural extension은 한 deeper polynomial family다. Sobel과 Harris는 finite patch/window score이며 CNN-lite는 scalar-replicated binary graph다. 이 breadth는 linear-only 초기 실험보다 넓지만 arbitrary graph compiler를 구성하지 않는다. Rotation-heavy packed layout, ciphertext convolution, bootstrapped deep network, encrypted argmax는 별도 adapter와 policy scope가 필요하다.

Graph adapter에는 formula와 scale trace가 명시적으로 구현되어 있어 hardcoding 요소가 남아 있다. Dataset별 lookup table은 사용하지 않지만 operation family별 adapter는 존재한다. 향후에는 typed graph IR에서 multiplicative depth, rescale constraint, slot flow를 자동 추출하고 unsupported operator를 정형적으로 보고하는 방향이 필요하다. 다만 그러한 compiler 확장은 현재 admission layer의 finite-set semantics와 독립적으로 개발할 수 있다.

## 9.8 Partition과 training-seed 일반화

Primary 다섯 partition은 fixed held-out artifact를 deterministic하게 반복 분할한 것이다. 동일 training run과 model artifact를 공유하므로 다섯 독립 dataset split이나 다섯 independent model이 아니다. Seed 0는 policy development에 사용되어 confirmatory aggregate에서 제외했다. Seeds 1--4도 cluster 내부 반복으로 처리했다.

Independent training/data-seed extension은 {{N:independent_training_datasets}} dataset x {{N:independent_training_seeds_per_dataset}} seed의 {{N:independent_training_seed_total}} model을 새로 생성해 이 한계를 일부 보완했다. {{N:independent_training_seed_pass}}/{{N:independent_training_seed_total}} selection/audit PASS는 model artifact 변화에 대한 scoped evidence지만 dataset 수와 seed 수가 작다. 더 강한 일반화를 위해서는 architecture, preprocessing, class balance가 다른 독립 cohort와 계층적 통계가 필요하다.

## 9.9 Security 해석의 한계

Security-V2는 published Table 5.2 cap, exact Q/P object, two-estimator sensitivity를 결합한다. Q와 QP를 분리한 점은 ciphertext와 evaluation key의 modulus semantics를 명확히 한다. Direct {{N:security_direct_pass}} row가 모두 통과하고 catalog {{N:security_catalog_profiles_excluded}} profile이 제외된 결과는 security filter가 실제 comparison population을 바꾸었음을 보여준다.

그러나 guideline의 uniform-ternary 및 Gaussian 가정과 Lattigo의 concrete `Xs/Xe`, 특히 finite-bound truncation은 정확히 동일하지 않다. Estimator model도 공격 비용 모델과 구현 세부에 의존한다. 따라서 “임의 runtime에서 정확히 {{N:security_target_bits}}-bit”라는 문장을 사용할 수 없다. 본 논문은 명시된 policy와 object가 보수적 admission reference 및 sensitivity를 통과했다고만 주장한다.

## 9.10 External provider와 EVA가 appendix인 이유

Provider-format interoperability, Orion fail-closed import, AWS HIT rejection, EVA native scale sensitivity와 exact Q/P materialization은 candidate admission interface를 점검하는 데 유용했다. 그러나 matched Lattigo-SEAL numerical execution과 runtime-specific equivalent security는 수행하지 않았다. 한 provider의 성공과 몇 개 rejection 사례는 general external-autotuner integration을 뒷받침하지 않는다.

따라서 provider/EVA evidence는 core contribution을 지지하는 본문 결과가 아니라 appendix의 auxiliary evidence로 둔다. 이는 음성 결과를 숨기는 것이 아니라, execution runtime과 candidate semantics가 일치하지 않는 상태에서 cross-runtime 성능 또는 correctness를 과장하지 않기 위한 경계다.

## 9.11 Negative result와 fail-closed 연구 방식

그림 10과 표 13이 보여주듯 본 연구의 claim registry에는 admitted claim과 blocked claim이 함께 남아 있다. Structural REJECT, one-shot NO_SAFE, latency-only flip, validation identity v1 fail-closed, security-excluded catalog profile은 모두 연구 artifact의 일부다. 성공률만 남기는 대신 failure cause와 claim effect를 기록하면 시스템이 실제로 어디에서 보수적으로 멈추는지 설명할 수 있다.

이 접근의 비용은 claim이 좁아진다는 점이다. 그러나 석사논문의 완성도는 모든 항목이 성공했다는 선언보다, 질문·protocol·negative result·한계가 일치하는지에 달려 있다. FlipGuard의 의미 있는 결과는 audit rejection이 전혀 없다는 데 있지 않고, rejection이 발생했을 때 retune하지 않고 보존하며 해당 claim을 낮출 수 있는 구조를 구현했다는 데 있다.

## 9.12 타당도 위협

**내적 타당도**에는 개발 seed 0에서 policy와 ablation을 관찰한 영향, VM host의 runtime variation, finite key repetition이 포함된다. 이를 줄이기 위해 seed 역할을 분리하고 paired order 및 no-outlier protocol을 사용했으며 frozen policy digest를 검증했다.

**구성 타당도**에는 reserve-policy violation이 실제 application harm과 동일하지 않다는 문제가 있다. 본 연구는 flip과 policy rejection을 분리하고 margin utilization을 공개했다. `rho={{N:primary_alpha}}`를 theorem constant로 부르지 않는다.

**외적 타당도**는 dataset, graph, packing, host 범위가 제한된다는 점이다. Structural/non-tabular/training-seed extension을 추가했지만 범용 compiler 또는 production deployment를 대표하지 않는다.

**결론 타당도**에는 {{N:combined_descriptive_instances}} partition row를 독립 표본으로 처리할 위험이 있다. Latency는 {{N:primary_dataset_model_clusters}} cluster를 inference unit으로 사용하고 seed 0를 분리했다. Decision audit 결과는 inferential population claim보다 finite outcome count로 보고한다.
