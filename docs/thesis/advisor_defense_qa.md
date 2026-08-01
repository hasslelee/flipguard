# 지도교수 및 심사위원 예상 질의응답

## Q1. 왜 error budget을 margin의 0.5로 두었는가?

`rho=0.5`는 오차가 decision margin의 절반을 넘지 않도록 하고 나머지 절반을 reserve로 두는 사전동결 운용 정책이다. 이 값은 CKKS 이론에서 도출된 최적 상수가 아니다. Primary confirmatory 이전에 고정했고 audit 결과로 변경하지 않았다는 protocol 성질이 중요하다. Sensitivity grid에서 결과가 불변이었던 것은 최적성보다 minimum synthesis floor dominance를 보여준다. **Claim ID:** `finite_scope_decision_integrity`. **Evidence:** `docs/evidence/margin_utilization_interpretation_v1/`. **금지 과장:** 0.5가 이론적 최적값이라는 표현. **짧은 구두 답변:** “0.5는 증명된 상수가 아니라 사전동결한 50% margin-utilization reserve 정책입니다.”

## Q2. 결정 보존 수학 조건은 정확히 무엇인가?

평문 score와 threshold 사이 거리를 `m(x)=|f_plain(x)-tau|`, CKKS 절대오차를 `e_c(x)=|f_c(x)-f_plain(x)|`라 한다. `e_c(x)<m(x)`이면 CKKS score가 threshold를 건널 수 없으므로 decision이 보존된다. FlipGuard의 `e_c(x)<0.5m(x)`은 이 충분조건 내부의 더 엄격한 admission policy다. **Claim ID:** `finite_scope_decision_integrity`. **Evidence:** `docs/evidence/margin_utilization_interpretation_v1/policy_interpretation.json`. **금지 과장:** empirical observation이 domain 전체 proof라는 표현. **짧은 구두 답변:** “정리는 `e<m`이고, 0.5는 그 안쪽에 둔 운용 reserve입니다.”

## Q3. 0.5가 이론적 최적값이 아니라면 왜 primary인가?

Primary policy에는 해석 가능하고 audit 전에 고정할 수 있는 reserve가 필요했다. 0.5는 허용 오차와 남는 margin을 같은 비율로 나누는 명확한 기준이며 개발 단계에서 사전 선언되었다. 본 연구는 사후 audit 성능으로 0.5를 선택하지 않았다. 다른 응용에서는 위험 비용에 따라 별도 calibration이 필요하다. **Claim ID:** `finite_scope_decision_integrity`. **Evidence:** `docs/research/step_7h2_margin_utilization_policy.md`. **금지 과장:** 0.5의 보편 권고. **짧은 구두 답변:** “해석 가능하고 사전동결 가능한 primary reserve였으며, 최적성 주장은 하지 않습니다.”

## Q4. Margin floor 0.001은 왜 사용했는가?

Threshold에 지나치게 가까운 sample은 작은 approximation 변화에도 decision이 불안정하므로 certifiable과 ambiguous 영역을 분리할 필요가 있다. `delta=0.001`은 primary protocol에서 audit 전에 동결된 값이다. 본 연구는 `delta=0.0005` audit 결과를 primary 선택에 사용하지 않고 secondary sensitivity로만 남겼다. **Claim ID:** `finite_scope_decision_integrity`. **Evidence:** `config/policies/direct_synthesis_policy_v2.json` 및 `docs/evidence/policy_sensitivity_v1/`. **금지 과장:** 0.001이 모든 score scale에 적합하다는 표현. **짧은 구두 답변:** “임계값 근처를 ambiguous로 분리하기 위한 사전동결 floor이며 보편 상수는 아닙니다.”

## Q5. 700과 1,100의 차이는 무엇인가?

1,100은 11 profile, 2 path, 50 instance를 실제 실행한 historical pre-security ledger다. Security-V2 재감사에서 4 profile이 제외되어 formal 비교에는 7 profile만 남았다. 따라서 formal candidate는 `7*2*50=700`이고 confirmatory는 `7*2*40=560`이다. **Claim ID:** `formal_trial_reduction`. **Evidence:** `docs/evidence/security_v2_bounded_oracle_v1/` 및 V3 표 4. **금지 과장:** 1,100을 formal trial-reduction 분모로 사용. **짧은 구두 답변:** “1,100은 실행 이력, 700은 Security-V2를 통과한 정식 비교 집합입니다.”

## Q6. 왜 bounded catalog이지 global oracle이 아닌가?

Catalog는 사전 선언한 7 admitted profile과 2 path만 포함한다. 이 집합 안에서는 exhaustive fastest-safe를 찾았지만 가능한 exact Q/P와 scale 전체를 탐색하지 않았다. Direct literal은 catalog 밖에 있을 수도 있다. **Claim ID:** `formal_trial_reduction`. **Evidence:** `results/thesis_grade_protocol/paper_artifacts_v3/final/tables/04_formal_trial_reduction.md`. **금지 과장:** 전 구성 공간 최적성. **짧은 구두 답변:** “유한 14개 identity 안의 fastest-safe이므로 bounded catalog라고 부릅니다.”

## Q7. 90% trial reduction의 정확한 단위는 무엇인가?

단위는 encrypted candidate trial이다. 전체는 direct 70회 대 formal catalog 700개, confirmatory는 56회 대 560개로 계산한다. Key run, encrypted sample evaluation, wall-clock과는 다른 단위다. **Claim ID:** `formal_trial_reduction`. **Evidence:** V3 표 3과 표 4. **금지 과장:** key run 또는 총 계산량이 정확히 90% 줄었다는 표현. **짧은 구두 답변:** “Candidate trial 수가 70/700과 56/560으로 90% 감소했습니다.”

## Q8. Direct synthesis가 단순 handcrafted heuristic 아닌가?

현재 synthesis는 graph fact와 versioned policy에서 literal을 계산하는 결정론적 rule system이며 learned optimizer는 아니다. Scale trace, rescale count, required slot, security cap, bounded repair가 canonical policy에 명시되어 있다. Operation-family adapter가 존재하므로 heuristic 요소와 scope limitation을 인정한다. 기여는 이를 universal optimizer로 포장하는 것이 아니라 encrypted admission과 provenance까지 결합한 데 있다. **Claim ID:** `scoped_direct_synthesis`. **Evidence:** `config/policies/direct_synthesis_policy_v2.json`. **금지 과장:** 임의 graph 최적 구성 자동 도출. **짧은 구두 답변:** “결정론적 graph-aware synthesizer이며, adapter 범위와 heuristic policy를 명시적으로 versioning했습니다.”

## Q9. HECATE, ELASM, FHE-Agent와 무엇이 다른가?

HECATE는 performance-aware scale optimization, ELASM은 error-latency-aware scale management, FHE-Agent는 agent와 deterministic tool을 이용한 CKKS configuration automation을 다룬다. FlipGuard는 이들을 부정하거나 최초성을 주장하지 않는다. 차별점은 candidate source와 독립적인 threshold decision gate, NO_SAFE, literal lock, disjoint no-retuning audit, evidence provenance의 결합이다. **Claim ID:** `scoped_direct_synthesis`, `finite_scope_decision_integrity`. **Evidence:** `docs/thesis/citation_audit.csv`, V3 그림 2. **금지 과장:** 기존 연구가 correctness를 전혀 다루지 않았다는 표현. **짧은 구두 답변:** “최적화기 자체보다 그 출력의 decision-integrity admission과 audit 계층이 중심입니다.”

## Q10. Natural data에서 decision contract가 literal을 바꿨는가?

Primary natural range에서는 바꾸지 않았다. `rho` grid 전체에서 candidate state, bounded-oracle selection, direct initial literal change가 모두 0이었다. Minimum synthesis floor가 initial literal을 지배했다. **Claim ID:** `natural_data_margin_literal_effect`는 BLOCKED. **Evidence:** V3 표 8. **금지 과장:** margin이 primary literal을 직접 차별화했다는 표현. **짧은 구두 답변:** “아니요. Primary 범위에서는 floor가 지배했고, contract 효과는 admission에서 관측됐습니다.”

## Q11. Seed 0를 왜 confirmatory에서 제외했는가?

Seed 0는 policy development와 ablation에 사용되었으므로 post-freeze population이 아니다. 이를 confirmatory aggregate에 포함하면 개발 관측과 평가 관측이 섞인다. Seed 0 결과는 descriptive로 별도 보고했다. **Claim ID:** `primary_no_retuning_locked_audit`, `paired_latency`. **Evidence:** V3 표 3과 표 5. **금지 과장:** 50개 모두 confirmatory라는 표현. **짧은 구두 답변:** “Seed 0는 개발에 사용했기 때문에 정식 confirmatory는 seeds 1--4의 40건입니다.”

## Q12. 다섯 partition은 독립 split인가?

아니다. Fixed held-out artifact를 다섯 deterministic 방식으로 반복 partition한 것이다. 동일 model artifact를 공유하므로 independent model 또는 independent dataset split으로 해석하지 않는다. Latency 통계에서는 partition을 dataset-model cluster 내부 반복으로 취급했다. **Claim ID:** `primary_no_retuning_locked_audit`. **Evidence:** direct locked-audit manifests. **금지 과장:** five independent dataset splits. **짧은 구두 답변:** “같은 held-out artifact의 deterministic repeated partitions이며 독립 split이 아닙니다.”

## Q13. 3.14 ratio의 통계 단위는 무엇인가?

Ratio는 Security-V2 bounded-catalog total latency를 direct total latency로 나눈 값이다. Primary inference unit은 10 dataset-model cluster이고 seeds 1--4는 cluster 내부 반복이다. Cluster bootstrap 10,000회로 95% CI를 계산했다. **Claim ID:** `paired_latency`. **Evidence:** `results/thesis_grade_protocol/paired_latency_claim_admission_v1/seeds1_4_confirmatory_summary.json`. **금지 과장:** raw pair를 독립 표본으로 한 유의성 주장. **짧은 구두 답변:** “10개 dataset-model cluster의 geometric mean ratio가 3.140660입니다.”

## Q14. One-host latency를 일반화할 수 있는가?

같은 host에서 arm을 paired한 내부 비교는 가능하지만 다른 CPU, OS, runtime, packing으로 직접 일반화할 수 없다. VM scheduling과 memory hierarchy도 ratio에 영향을 줄 수 있다. 따라서 claim state는 PARTIALLY_SUPPORTED다. **Claim ID:** `paired_latency`; `production_latency`는 NOT_EVALUATED. **Evidence:** paired latency manifest. **금지 과장:** production speedup. **짧은 구두 답변:** “현재 host의 paired comparison이며 production 일반화는 하지 않습니다.”

## Q15. Structural audit 한 건 REJECT는 연구 실패 아닌가?

그 instance에서는 reserve policy generalization이 실패했으므로 해당 claim에 대한 정당한 negative result다. 이를 숨기지 않고 structural claim을 PARTIALLY_SUPPORTED로 낮췄다. 동시에 decision flip이나 execution failure는 아니었고 audit이 위험을 발견했다는 설계 증거이기도 하다. **Claim ID:** `structural_extension`. **Evidence:** `docs/evidence/structural_audit_failure_analysis_v1/`. **금지 과장:** structural audit 전부 PASS. **짧은 구두 답변:** “한 건의 policy rejection이며, 바로 그 때문에 structural claim을 partial로 보고합니다.”

## Q16. 왜 decision flip은 없는데 REJECT인가?

Decision preservation 충분조건보다 더 엄격한 `rho=0.5` reserve policy를 사용했기 때문이다. Audit utilization 0.5613685는 0.5 cap을 넘었지만 1보다 작아 observed decision은 유지될 수 있었다. Classification은 `POLICY_REJECTED_WITHOUT_FLIP`이다. **Claim ID:** `structural_extension`. **Evidence:** V3 그림 9. **금지 과장:** cryptographic failure 또는 observed decision failure. **짧은 구두 답변:** “결정은 같았지만 사전동결한 50% reserve를 넘어서 정책상 REJECT입니다.”

## Q17. NO_SAFE가 global infeasibility를 뜻하는가?

아니다. NO_SAFE는 해당 policy, candidate budget, finite domain에서 SAFE를 확립하지 못했다는 뜻이다. 더 넓은 configuration space에 SAFE 후보가 있을 수 있다. **Claim ID:** `no_safe_behavior`. **Evidence:** V3 표 7. **금지 과장:** 가능한 CKKS configuration이 없다는 표현. **짧은 구두 답변:** “현재 탐색 budget 안에서 승인할 후보가 없다는 기권입니다.”

## Q18. Analytical certificate는 왜 BLOCKED인가?

현재 certificate는 encrypted observation과 margin을 비교하는 empirical finite-set certificate다. Primitive CKKS residual error bound를 exact graph와 input domain에 합성해 `B_c(x)<m(x)`를 증명하지 않았다. 그런 proof가 있어야 analytical certificate라 부를 수 있다. **Claim ID:** `instantiated_analytical_ckks_certificate`는 BLOCKED. **Evidence:** paper claim registry. **금지 과장:** complete analytical proof. **짧은 구두 답변:** “관측 기반 certificate이며 graph-wide residual bound 증명은 아직 없습니다.”

## Q19. 128-bit security를 정확히 보장하는가?

Security-V2는 published Category-128 cap을 보수적 admission reference로 사용하고 exact Q/P를 검사한다. 두 estimator model도 sensitivity를 제공한다. 다만 runtime distribution과 estimator 가정이 정확히 같지 않으므로 임의 runtime에 대한 절대적 보증은 하지 않는다. **Claim ID:** `security_attestation`. **Evidence:** V3 표 12 및 Security-V2 policy. **금지 과장:** universal runtime 128-bit security. **짧은 구두 답변:** “선언 object가 보수적 Category-128 policy와 estimator sensitivity를 통과했다는 범위입니다.”

## Q20. Lattigo Xe와 estimator distribution 차이는 무엇인가?

실제 Lattigo `Xe`는 `Sigma=3.2`, `Bound=19.2`의 truncated discrete Gaussian이다. Published table은 sigma 3.19 가정을 사용하고 estimator export도 truncation을 완전히 동일하게 모델링하지 않는다. 이 차이를 manifest와 논문 caveat에 공개했다. **Claim ID:** `security_attestation`. **Evidence:** `config/security/security_guidelines_cic2025_table5_2_ternary_128_v2.json`. **금지 과장:** exact distribution equivalence. **짧은 구두 답변:** “Sigma와 truncation 모델이 정확히 같지 않아 conservative admission으로만 해석합니다.”

## Q21. Sobel/Harris/CNN-lite 결과의 한계는?

Sobel은 400/400 patch, Harris는 200/200 window, CNN-lite는 250/250 image의 finite scope다. 모두 scalar-replicated execution이며 full-image throughput 또는 general CNN accuracy를 평가하지 않았다. **Claim ID:** `scoped_non_tabular_extension`. **Evidence:** 각 `docs/evidence/non_tabular_*_holdout_v1/summary.json`. **금지 과장:** image-processing 또는 CNN 전반의 일반화. **짧은 구두 답변:** “세 adapter의 선언된 finite scalar-replicated 입력에서만 통과했습니다.”

## Q22. Packed CNN을 지원하는가?

현재 evidence는 scalar-replicated CNN-lite에 한정된다. Packed convolution, rotation schedule, slot layout optimization, multiclass encrypted argmax는 구현·평가하지 않았다. **Claim ID:** `arbitrary_graph_support`는 NOT_EVALUATED. **Evidence:** CNN-lite manifest. **금지 과장:** arbitrary CNN support. **짧은 구두 답변:** “아니요. 현재는 scalar-replicated binary CNN-lite scope입니다.”

## Q23. External autotuner와 실제 비교했는가?

Core paired comparator는 Security-V2 bounded catalog다. Provider-format import와 EVA auxiliary evidence는 있으나 general external autotuner와 matched end-to-end comparison은 하지 않았다. **Claim ID:** `general_external_autotuner_integration`은 NOT_EVALUATED. **Evidence:** V3 appendix provider boundary. **금지 과장:** general provider integration. **짧은 구두 답변:** “Core 비교는 bounded catalog이며 external provider는 appendix의 제한된 admission 사례입니다.”

## Q24. 왜 EVA/provider 결과는 appendix인가?

Runtime과 exact operation semantics를 맞춘 Lattigo--SEAL comparison이 없기 때문이다. 한 native candidate의 성공과 import rejection으로 일반 상호운용을 말할 수 없다. Core contribution의 admission·audit protocol을 흐리지 않도록 auxiliary evidence로 분리했다. **Claim ID:** `general_external_autotuner_integration`. **Evidence:** V3 `appendix/auxiliary_provider_boundary.md`. **금지 과장:** cross-runtime equivalence. **짧은 구두 답변:** “Matched runtime study가 없어 core claim이 아니라 boundary evidence로 둡니다.”

## Q25. 연구의 가장 강한 기여와 가장 약한 부분은 무엇인가?

가장 강한 부분은 direct synthesis, bounded encrypted admission, NO_SAFE, immutable audit replay, Security-V2와 provenance를 end-to-end로 결합하고 negative result까지 freeze한 것이다. 가장 약한 부분은 graph/packing 범위와 empirical certificate의 유한성이다. Natural primary data에서 margin이 initial literal을 바꾸지 않았다는 점도 novelty를 좁힌다. **Claim ID:** 여러 core admitted claim 및 blocked margin claim. **Evidence:** Paper Artifacts V3 전체. **금지 과장:** 모든 component가 동일 강도로 지지된다는 표현. **짧은 구두 답변:** “강점은 재현 가능한 admission protocol, 약점은 finite adapter와 empirical 범위입니다.”

## Q26. 논문을 떨어뜨릴 수 있는 가장 큰 이유는 무엇인가?

Direct synthesis가 adapter-specific heuristic으로 보이고, primary natural range에서 decision margin이 literal을 바꾸지 않은 점이 가장 큰 novelty risk다. 또한 one-host latency와 fixed-model repeated partitions는 외적 타당도를 제한한다. 논문은 이를 숨기지 않고 admission layer, negative result, provenance의 결합으로 기여를 정확히 한정해야 한다. **Claim ID:** `scoped_direct_synthesis`; blocked margin claim. **Evidence:** V3 표 8 및 discussion. **금지 과장:** heuristic 한계를 감춘 범용성. **짧은 구두 답변:** “Margin-driven literal 차별화가 약하고 adapter 범위가 좁다는 점이 가장 큰 심사 위험입니다.”

## Q27. 재현 가능한가?

RC2 tag/source/archive digest, frozen evidence manifest, SHA256SUMS와 verifier, V3 deterministic builder가 제공된다. 258 soak cycle과 21 clean-clone rebuild가 완료되었다. External dataset은 license를 지키며 fetch URL, expected digest, extraction rule을 제공한다. **Claim ID:** artifact reproducibility는 core evidence system의 일부. **Evidence:** `docs/evidence/research_release_binding_rc2_v1/` 및 V10. **금지 과장:** 모든 미래 dependency 환경에서 bit-identical 실행 보장. **짧은 구두 답변:** “RC2와 verifier로 publication artifact를 clean clone에서 재구축할 수 있습니다.”

## Q28. 실제 배포 시 사용자가 제공해야 하는 policy는?

사용자는 graph adapter 또는 지원 formula, threshold, acceptable margin floor, margin-utilization cap, validation/audit governance와 target security category를 정해야 한다. False acceptance와 abstention 비용도 application owner가 결정해야 한다. Default 0.5와 0.001을 무비판적으로 모든 응용에 적용하면 안 된다. **Claim ID:** `finite_scope_decision_integrity`. **Evidence:** thesis contract 및 Direct Policy V2. **금지 과장:** FlipGuard가 application risk policy를 자동 결정. **짧은 구두 답변:** “Threshold와 risk reserve, audit domain은 응용 책임자가 사전 선언해야 합니다.”

## Q29. Audit에서 실패하면 운영 시스템은 무엇을 하는가?

같은 audit 결과를 이용해 candidate를 retune하지 않는다. 배포를 보류하고 failure record를 보존하며, 필요하면 완전히 새로운 development/validation/audit protocol을 사전 등록해야 한다. Current claim은 해당 scope에서 낮아진다. **Claim ID:** `structural_extension`. **Evidence:** structural failure analysis. **금지 과장:** audit-driven automatic repair. **짧은 구두 답변:** “그 배포는 멈추고 결과를 보존하며, 새 protocol 없이는 재튜닝하지 않습니다.”

## Q30. 향후 어떤 연구가 analytical guarantee를 완성하는가?

Exact Q/P, scale, graph operation, input bound에 대해 CKKS residual error envelope `B_c(x)`를 계산해야 한다. 그 bound가 domain의 decision margin보다 작음을 정형적으로 검증하고 implementation parameter와 proof object를 연결해야 한다. Empirical audit은 이 분석적 bound의 validation 수단으로 남을 수 있다. **Claim ID:** `instantiated_analytical_ckks_certificate`는 BLOCKED. **Evidence:** claim registry reviewer rationale. **금지 과장:** 현재 artifact가 proof를 이미 포함. **짧은 구두 답변:** “Graph-wide residual bound를 exact literal과 domain margin에 인스턴스화하는 작업이 필요합니다.”

