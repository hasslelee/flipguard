# 제5장 FlipGuard 설계

## 5.1 설계 원칙

FlipGuard의 설계 원칙은 decision preservation, fail-closed admission, bounded work, literal immutability, evidence provenance의 다섯 가지다. 시스템은 속도만 빠른 candidate를 선택하지 않으며, empirical admission을 통과한 후보 중에서 latency를 비교한다. 실행 가능한 후보가 없거나 SAFE를 확립하지 못하면 임의 선택 대신 NO_SAFE를 반환한다. Selection 이후에는 candidate를 변경하지 않고 audit negative result도 그대로 보존한다.

그림 1은 전체 구조를 보여준다. Main path는 graph와 decision contract에서 시작해 direct synthesis, bounded encrypted validation, failure-aware repair, certify/reject/NO_SAFE, literal lock, disjoint audit으로 이어진다. Security-V2 bounded catalog는 evaluation-only side path이며 direct policy의 후보 생성 규칙에 관여하지 않는다. External provider는 동일 gate에 candidate를 공급할 수 있지만, 본 논문의 일반 상호운용 주장은 appendix 범위로 제한된다.

{{V3_FIGURE_01}}

## 5.2 Workload normalization과 scope binding

첫 단계는 입력을 canonical workload contract로 정규화하는 것이다. Model JSON, source CSV, split manifest, graph adapter, threshold, policy를 읽어 각각 digest를 계산한다. Candidate ID는 profile name만이 아니라 source digest와 materialization identity를 포함한다. Required slot이 ring capacity를 넘거나 adapter가 지원하지 않는 operation을 포함하면 synthesis 전에 실패한다.

Source/prepared/semantic identity를 분리하는 이유는 재현성과 실행 편의를 함께 보존하기 위해서다. Prepared CSV에 provenance column을 추가하거나 숫자 serialization이 바뀌면 raw byte는 달라질 수 있다. 이 차이를 source mismatch로 간주하면 의미상 동일한 encrypted evidence를 재사용하지 못한다. 반대로 semantic digest만 비교하면 source row ordering이나 model 변경을 놓칠 수 있다. FlipGuard는 source raw digest, prepared raw digest, ordered-row digest, semantic digest, model digest를 모두 기록하고 각 layer의 기대 관계를 검증한다.

## 5.3 Graph fact extraction

Graph adapter는 모델 formula를 분석하여 direct synthesis에 필요한 정적 사실을 제공한다. 주요 사실은 ciphertext-ciphertext multiplication 수, plaintext multiplication 수, multiplicative depth, rescale count, expected output scale, first-prime requirement, required slot 수다. Linear polynomial과 square-activation MLP는 서로 다른 multiplication trace를 가지며, `mlp_square_poly3`는 primary graph보다 깊은 구조 holdout으로 사용한다.

Direct synthesizer는 model name에 따른 lookup table로 literal을 선택하지 않는다. 동일 graph formula와 fact는 dataset 이름과 무관하게 같은 계산 규칙을 통과한다. Dataset별 score distribution과 threshold margin은 validation admission에서 반영된다. Natural primary range에서는 minimum synthesis floor가 initial literal을 지배해 `rho` 변화가 initial literal을 바꾸지 않았으며, 이 사실은 결과와 limitation에 공개한다.

## 5.4 Direct literal synthesis

Direct Policy V2는 `flipguard_direct_synthesis_policy_v2`라는 immutable contract다. Policy는 graph contract schema, 지원 formula, scale trace version, primary `rho={{N:primary_alpha}}`, margin floor `{{N:primary_margin_floor}}`, minimum scale/prime floor, scale guard, first-prime guard, numerical repair `+{{N:numerical_repair_scale_bits}}` bits, level repair `+{{N:level_repair_q_primes}}` Q prime, maximum additional level {{N:max_additional_levels}}, static NTT-prime retry, maximum encrypted trials `{{N:max_encrypted_trials}}`, error classifier, Security-V2 policy ID, scalar-replicated packing, required-slot rule, first-SAFE stopping과 NO_SAFE rule을 포함한다.

Initial scale은 graph의 multiplication과 rescale trace가 요구하는 최소 정밀도, output scale floor, first-prime guard를 충족하도록 계산한다. Q chain은 예상 rescale마다 소비될 prime과 input/output guard prime을 배치한다. P는 relinearization과 key-switching object가 필요로 하는 special prime을 포함한다. Required slot으로 최소 LogN을 정한 뒤 Q와 QP가 Security-V2 cap 안에 있는지 검사한다. 정적 literal이 admission을 통과하지 못하면 formal candidate로 실행하지 않는다.

<!-- P:DESIGN-DIRECT CLAIM:scoped_direct_synthesis -->
FlipGuard는 선언된 graph adapter와 동결 정책 범위에서 computation graph와 threshold decision-integrity contract로부터 CKKS literal을 직접 합성했다. 직접 합성이라는 표현은 catalog profile을 이름으로 고르는 대신 exact Q/P와 scale을 계산한다는 뜻이며, 임의 graph 지원을 뜻하지 않는다.

## 5.5 Bounded encrypted validation

Static analysis만으로 runtime의 실제 근사오차와 implementation behavior를 완전히 알 수 없으므로, 합성 literal을 configuration-validation artifact에서 실행한다. 각 candidate trial은 새 키 {{N:fresh_key_repeats}}개를 사용한다. 실행 ledger는 key마다 plaintext score, CKKS score, absolute error, decision margin, budget, utilization ratio, decision, flip을 기록한다. Aggregate 판정은 한 key에서라도 violation이 있으면 REJECTED가 되도록 보수적으로 결합한다.

Validation gate는 두 층으로 구성된다. Execution gate는 materialization, key generation, evaluation, decryption이 성공했는지 확인한다. Decision gate는 `V_cert`의 flip과 reserve-policy violation이 0인지 확인한다. 이 둘을 분리하면 level 부족으로 실행되지 않은 candidate를 수치 REJECT와 구별하고, repair classifier가 적절한 bounded action을 선택할 수 있다.

## 5.6 Failure-aware bounded repair

Initial candidate가 SAFE이면 즉시 선택한다. 실패하면 error classifier가 원인을 numerical precision, level exhaustion, static NTT-prime incompatibility, non-repairable provenance/security failure로 구분한다. Numerical repair는 scale 관련 prime budget을 `+4` bits 조정한다. Level repair는 Q prime 하나를 추가하되 maximum additional level을 넘지 않는다. Static NTT-prime retry는 같은 bit target에서 실제 사용 가능한 prime을 결정론적으로 다시 materialize한다.

Repair는 audit 결과를 보아 수행하지 않으며, validation에서도 최대 encrypted trial 네 번과 사전 선언된 변화만 허용한다. Security admission을 매 trial 다시 확인하고 first SAFE에서 멈춘다. Repair budget 종료까지 SAFE가 없으면 NO_SAFE다. Provenance mismatch나 inadmissible security는 repair 대상이 아니라 integrity block이다.

<!-- P:DESIGN-REPAIR CLAIM:adaptive_repair -->
FlipGuard의 동결된 bounded repair는 선언된 개발 ablation에서 one-shot 실패 네 건을 SAFE 선택으로 전환했으며, 이는 보편적 repair 성공을 뜻하지 않는다. Repair의 의미는 실패를 무조건 성공으로 바꾸는 것이 아니라, 원인이 허용 class에 속할 때만 제한된 다음 literal을 생성하고 종료를 보장하는 데 있다.

## 5.7 First-SAFE selection과 NO_SAFE

Candidate가 SAFE가 되면 더 큰 또는 더 빠른 candidate를 탐색하지 않고 즉시 literal을 잠근다. 이 first-SAFE rule은 direct path를 fastest configuration search와 구분한다. 합성 순서는 policy가 정한 보수 수준과 repair progression을 반영하므로, 선택 결과는 “검증된 후보 중 최소 latency”가 아니라 “동결 순서에서 처음으로 SAFE가 된 후보”다. Latency 우월성은 selection 목적이 아니라 후속 paired evaluation에서 측정한다.

<!-- P:DESIGN-NOSAFE CLAIM:no_safe_behavior -->
사전동결 budget control은 {{N:no_safe_budget_total}}건 중 {{N:no_safe_budget}}건에서 NO_SAFE를, 선언된 finite-domain control은 {{N:no_safe_finite_domain}}/{{N:no_safe_finite_domain_total}}에서 NO_SAFE를 반환했다. NO_SAFE는 해당 budget 또는 finite candidate domain에서 SAFE를 확립하지 못했다는 뜻이며 가능한 CKKS literal 전체의 부재를 뜻하지 않는다.

## 5.8 Literal lock과 no-retuning audit

Selection 결과에는 candidate literal의 canonical JSON, SHA-256, graph/model/input/policy digest, binary digest, selection ledger를 결합한다. Locked audit runner는 이 selection artifact를 input으로 받고 synthesizer와 repair module을 호출할 수 없다. Audit source와 model digest를 확인한 뒤 exact Q/P와 scale을 byte-identical하게 materialize하고 새 key로 실행한다.

Audit 결과가 REJECTED여도 같은 audit에 다른 candidate를 넣지 않는다. Primary에서는 confirmatory seeds 1--4의 {{N:confirmatory_instances}}건이 {{N:confirmatory_locked_audit_pass}}/{{N:confirmatory_instances}} PASS였고, development seed 0의 {{N:development_instances}}건도 descriptive 결과에서 {{N:development_locked_audit_pass}}/{{N:development_instances}} PASS였다. Structural `mlp_square_poly3`에서는 {{N:structural_reserve_reject}}건의 reserve-policy REJECT가 관측되었다. 이 결과는 policy 변경을 유발하지 않았으며 structural claim을 PARTIALLY_SUPPORTED로 낮췄다. 이 설계는 negative result를 시스템 오류와 동일시하지 않고, certificate scope를 좁히는 정당한 결과로 다룬다.

## 5.9 Evaluation-only bounded catalog

Bounded catalog side path는 {{N:security_catalog_profiles_total}} profile과 {{N:catalog_execution_paths}} path의 역사적 ledger를 Security-V2로 다시 필터링한다. Excluded profile의 encrypted record를 삭제하지 않지만 formal fastest-safe selection에는 포함하지 않는다. 동일 workload-partition에서 admitted candidate 중 SAFE이며 latency가 가장 작은 것을 bounded-catalog arm으로 선택한다. Direct arm과 catalog arm은 source/model/split identity v2 검사를 통과해야 paired comparison에 들어간다.

Catalog의 목적은 direct synthesis가 유한 비교 집합 대비 candidate trial을 얼마나 줄였는지, 선택 literal의 latency가 bounded fastest-safe와 어떻게 다른지를 평가하는 것이다. Catalog가 direct algorithm의 repair policy를 학습시키거나 audit 결과를 통해 바뀌지는 않는다.

## 5.10 Evidence provenance

각 stage는 raw ledger, summary, failures, manifest, SHA256SUMS, deterministic verifier를 별도 pack으로 freeze한다. Manifest는 execution commit과 evidence-builder commit을 구분하고 binary digest, policy IDs, input/model/split digest를 기록한다. Frozen pack은 덮어쓰지 않으며 후속 해석은 overlay evidence로 추가한다. 예를 들어 margin theorem과 `rho={{N:primary_alpha}}`의 의미는 기존 encrypted pack을 수정하지 않고 `margin_utilization_interpretation_v1`이 참조한다.

Pipeline은 claim-level fail-closed와 pipeline-level continuation을 따른다. 과학적 negative result는 해당 claim의 상태를 낮추지만 독립적인 downstream evidence 생성을 중단하지 않는다. 잘못된 source, policy, security admission, 복구 불가능한 provenance 문제는 integrity block으로 처리한다. 이 구분이 장시간 실행의 완결성과 연구 무결성을 동시에 지탱한다.
