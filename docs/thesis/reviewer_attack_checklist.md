# FlipGuard 외부 심사 공격 체크리스트

이 문서는 논문 주장을 더 강하게 만들기 위한 문서가 아니라, 현재 frozen evidence로 방어할 수 없는 주장을 본문에서 차단하기 위한 QA 기준이다. 판정은 `CLOSED_FOR_DRAFT`, `DISCLOSED_RESIDUAL_RISK`, `BLOCKED_CLAIM`만 사용한다.

| 우선순위 | 예상 공격 | 현재 방어와 evidence | 원고 위치 | 잔여 위험 | 판정 |
| --- | --- | --- | --- | --- | --- |
| 1 | Direct synthesis가 dataset별 handcrafted lookup에 불과한가? | Graph fact, canonical scale trace, required slot, Q/P materialization과 policy digest를 사용하며 dataset/model lookup 부재를 policy와 구현 경계로 검증한다. | 5.3--5.4, 6.2--6.3 | Adapter별 formula 지원 자체는 수작업이며 범용 compiler가 아니다. | DISCLOSED_RESIDUAL_RISK |
| 2 | Natural data에서 decision margin이 literal을 바꾸지 않았다면 novelty가 약한가? | Alpha grid에서 candidate state, oracle selection, initial literal 변화가 모두 0이라는 negative result를 공개한다. 기여는 margin-driven optimization의 우월성이 아니라 admission, abstention, lock, audit, provenance의 결합으로 한정한다. | 8.7, 9.1--9.2 | Literal 차별화에 관한 자연 데이터 claim은 BLOCKED다. | BLOCKED_CLAIM |
| 3 | 90% 감소가 1,100회 대비 계산된 과장인가? | Formal denominator는 Security-V2 admitted 700/560이고 direct trial은 70/56이다. 1,100은 pre-security historical execution ledger로만 사용한다. | 7.3, 8.2, 11 | Candidate trial 감소이며 key run, sample evaluation, wall-clock 감소로 바꾸지 않는다. | CLOSED_FOR_DRAFT |
| 4 | Bounded catalog가 global oracle 또는 최적해인가? | 7 profile과 2 path의 유한 집합에서 fastest-safe를 선택한다. Direct literal은 catalog 밖에 있을 수 있음을 명시한다. | 2.7, 5.9, 9.5 | 더 넓은 구성 공간의 더 빠른 SAFE 후보 존재 가능성을 배제하지 못한다. | DISCLOSED_RESIDUAL_RISK |
| 5 | Seed 0를 개발과 평가에 중복 사용했는가? | Seed 0는 development/descriptive로 분리하고 seeds 1--4만 confirmatory aggregate에 사용한다. | 7.2, 8.1, 8.4, 8.6 | 동일 fixed model artifact의 repeated partition이라는 한계는 남는다. | CLOSED_FOR_DRAFT |
| 6 | 50 rows 또는 1,800 latency pairs를 독립 표본으로 다뤘는가? | Primary inference unit은 10 dataset-model cluster이고 partition은 cluster 내부 반복이다. Raw pair-level p-value를 사용하지 않는다. | 7.7, 8.6, 9.8 | Cluster 수가 작아 confidence interval의 외적 일반화가 제한된다. | DISCLOSED_RESIDUAL_RISK |
| 7 | 3.14 latency ratio를 production speedup으로 일반화했는가? | 동일 host, frozen arm, balanced order의 paired ratio로 정의하고 cluster bootstrap CI를 보고한다. | 7.7, 8.6, 9.6 | 한 VMware host와 scalar-replicated packing 결과다. | DISCLOSED_RESIDUAL_RISK |
| 8 | Structural audit REJECT를 숨기거나 실패를 사후 보정했는가? | 25/25 selection 뒤 24 PASS와 1 reserve-policy REJECT를 그대로 보존하며 retuning과 policy modification은 0이다. | 8.8, 9.3 | Deeper polynomial transportability는 PARTIALLY_SUPPORTED다. | CLOSED_FOR_DRAFT |
| 9 | Flip이 없는데 REJECT를 실패라고 부르는 것이 모순인가? | Decision theorem `e<m`과 reserve policy `e<rho*m`을 분리하고 `POLICY_REJECTED_WITHOUT_FLIP`으로 분류한다. | 2.3, 8.8, 9.2--9.3 | Reserve cap의 응용별 calibration은 별도 연구가 필요하다. | CLOSED_FOR_DRAFT |
| 10 | `rho=0.5`와 margin floor 0.001이 사후 선택되었거나 이론 최적인가? | 두 값은 audit 전 동결된 operational policy이며 theorem constant나 optimum이 아니라고 반복 명시한다. Secondary sensitivity를 primary 선택에 사용하지 않는다. | 2.3--2.4, 7.1, 8.7, 9.2 | 다른 응용의 위험 비용에 대한 calibration 근거는 없다. | DISCLOSED_RESIDUAL_RISK |
| 11 | NO_SAFE가 전 구성의 infeasibility를 증명하는가? | One-candidate budget 및 finite two-candidate domain의 scoped abstention으로만 정의한다. | 4.4, 7.6, 8.5 | Global infeasibility claim은 BLOCKED다. | CLOSED_FOR_DRAFT |
| 12 | Security-V2 PASS가 보편적인 128-bit runtime security를 뜻하는가? | Exact Q와 QP, published cap, 두 estimator model을 기록하고 Lattigo Xe truncation 차이를 공개한다. | 2.6, 6.5, 8.11, 9.9 | Exact runtime-distribution equivalence와 임의 parameter 보장은 없다. | DISCLOSED_RESIDUAL_RISK |
| 13 | Sobel/Harris/CNN-lite로 범용 image/CNN generalization을 주장하는가? | 각 finite input count와 scalar-replicated scope를 보고하고 packed convolution, full-image throughput, multiclass argmax를 제외한다. | 7.9, 8.9, 9.7 | Operation-family breadth는 제한적이다. | DISCLOSED_RESIDUAL_RISK |
| 14 | Five partitions가 independent dataset/model generalization인가? | Fixed held-out artifact의 deterministic repeated partitions로 명명하며, 별도 3-dataset x 3-training-seed extension과 혼합하지 않는다. | 7.2, 7.10, 9.8 | Training-seed extension도 9 model에 한정된다. | CLOSED_FOR_DRAFT |
| 15 | Empirical certificate를 analytical CKKS proof로 과장하는가? | Per-sample encrypted observation certificate와 아직 없는 graph-wide residual bound를 분리한다. | 4.5--4.8, 9.4 | Instantiated analytical certificate claim은 BLOCKED다. | BLOCKED_CLAIM |
| 16 | External autotuner와 실제 end-to-end 비교 없이 autotuner-agnostic을 주장하는가? | Provider import/EVA는 appendix의 제한된 fail-closed 사례로만 두고 core comparator는 bounded catalog로 명시한다. | 3.2, 5.1, 9.10, 부록 | General external-autotuner integration은 NOT_EVALUATED다. | BLOCKED_CLAIM |
| 17 | Validation identity mismatch를 결과에서 삭제했는가? | Comparator v1의 fail-closed record와 v2 CLASS A resolution을 함께 보존하고 encrypted rerun 부재를 명시한다. | 4.3, 8.4, 10.3 | Future schema change에도 source/prepared/semantic layer 검증이 필요하다. | CLOSED_FOR_DRAFT |
| 18 | Artifact가 현재 논문 숫자와 실제로 결합되는가? | RC2 binding, V3 digest, claim registry, evidence-derived number registry, deterministic builder와 SHA256SUMS를 사용한다. | 6.9--6.10, 10 | 대학원 제출 template과 최종 bibliography style은 아직 적용되지 않았다. | DISCLOSED_RESIDUAL_RISK |

## Draft admission rules

1. `BLOCKED_CLAIM` 행은 한계 또는 future work로만 등장해야 한다.
2. `DISCLOSED_RESIDUAL_RISK` 행은 관련 정량 결과와 같은 장 또는 바로 다음 논의 장에서 명시해야 한다.
3. 표 13의 structural negative row, validation identity fail-closed row, NO_SAFE row를 삭제하면 draft는 실패다.
4. 700/560이 아닌 1,100을 formal trial denominator로 쓰거나 raw latency pair를 독립 표본으로 쓰면 draft는 실패다.
5. RC2, V3, claim-admission 또는 margin-interpretation digest가 바뀌면 새 binding 없이 draft를 재배포하지 않는다.
