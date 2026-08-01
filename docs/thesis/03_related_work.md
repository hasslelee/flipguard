# 제3장 관련 연구

## 3.1 CKKS compiler와 configuration 자동화

동형암호 프로그램의 성능과 정확성은 source-level 계산만으로 결정되지 않는다. 암호 parameter, data layout, rotation, rescale, relinearization, bootstrapping placement가 상호작용한다. 이에 따라 관련 연구는 고수준 graph를 FHE 실행으로 낮추는 compiler, scheme parameter를 고르는 selector, 정확도와 latency를 함께 다루는 application-aware optimizer로 발전해 왔다.

CHET는 동형암호 기반 신경망 추론을 위한 compiler와 runtime으로, symbolic analysis를 통해 ciphertext modulus와 polynomial degree를 선택하고 data layout 정책을 비용 모델로 비교한다 [@dathathri2019chet]. 이는 사용자가 저수준 FHE parameter를 수작업으로 조정해야 하는 부담을 줄였다. EVA는 encrypted vector arithmetic을 중간 표현과 언어로 제공하고, rescale·relinearization 삽입과 parameter selection 및 optimization을 compiler가 담당하도록 했다 [@dathathri2020eva]. 두 연구는 graph에서 실행 구성을 도출한다는 점에서 FlipGuard의 직접 합성 문제와 맞닿지만, FlipGuard의 주된 평가는 이들 compiler를 대체하는 code-generation 성능이 아니라 provider가 낸 literal을 최종 threshold-decision contract로 승인·거부하는 과정이다.

HECATE는 CKKS compiler에서 scale을 단순히 균일하게 두지 않고 성능 관점에서 최적화하는 문제를 다룬다 [@lee2022hecate]. ELASM은 output error와 latency의 trade-off를 명시하고, error estimation과 scale waterline을 이용해 scale management를 수행한다 [@lee2023elasm]. ELASM은 오차를 핵심 최적화 변수로 다룬다는 점에서 매우 가까운 선행연구다. 따라서 본 연구는 기존 연구가 error를 무시했다고 주장하지 않는다. 차이는 FlipGuard가 error를 최종 score의 threshold margin과 sample별로 결합하여 공통 admission contract를 구성하고, SAFE/REJECTED/FAILED/NO_SAFE와 locked audit을 protocol 결과로 남긴다는 데 있다.

HECO는 범용 FHE compiler를 지향하며 scheme-aware optimization과 lowering을 제공한다 [@viand2023heco]. DaCapo는 깊은 프로그램에서 bootstrapping 후보를 분석하고 scale-management 결과와 operation latency estimate를 결합하여 placement plan을 선택한다 [@cheon2024dacapo]. 이 연구들은 graph transformation과 cost-aware placement가 configuration automation에 필수임을 보여준다. FlipGuard는 bootstrapping placement나 일반 compiler IR 최적화를 새로 제안하지 않는다. 대신 지원 graph adapter가 제공한 사실을 직접 literal synthesis의 입력으로 사용하고, 선택 이후 decision-integrity gate와 no-retuning audit을 추가한다.

## 3.2 정확도·응용 인식형 자동화

AutoPrivacy는 hybrid private neural-network inference에서 layer별 HE parameter를 deep reinforcement learning으로 선택하여 latency와 model accuracy를 함께 고려한다 [@lou2020autoprivacy]. AutoFHE는 표준 CNN의 activation을 mixed-degree polynomial로 바꾸고 bootstrapping placement를 공동 최적화하여 accuracy-latency trade-off를 탐색한다 [@ao2024autofhe]. 이들 연구에서 응용 정확도는 configuration 또는 network transformation 선택의 중요한 기준이다. 다만 model-level accuracy가 유지되었다는 사실과 모든 평가 sample의 threshold decision이 동일하다는 사실은 같은 명제가 아니다. FlipGuard는 학습 정확도를 개선하거나 network architecture를 탐색하지 않고, 이미 주어진 score graph와 threshold에 대해 per-sample decision-integrity admission을 수행한다.

Application-Aware Approximate Homomorphic Encryption은 회로뿐 아니라 허용 input domain을 포함하는 application specification을 correctness와 security 정의에 반영한다 [@alexandru2024applicationaware]. 이는 최대 depth만으로 실제 응용 요구를 표현하기 어렵고 입력 범위가 approximation 및 security에 영향을 줄 수 있다는 점을 이론적으로 정리한다. FlipGuard가 workload contract에 graph와 input scope를 결합한 것은 이러한 문제의식과 양립한다. 그러나 본 연구의 empirical certificate가 해당 연구의 formal application-aware correctness 정의를 구현하거나 증명한 것은 아니다. FlipGuard는 선언된 finite artifact의 실제 encrypted observation을 승인 근거로 사용하며, 분석적 residual bound의 완전한 인스턴스화는 범위 밖이다.

FHE-Agent는 LLM-guided agent와 deterministic tool을 결합하여 CKKS configuration의 pruning, calibration, repair를 자동화하는 preprint다 [@xu2025fheagent]. 이 연구는 configuration automation이 fixed rule만이 아니라 tool-using agent와 결합될 수 있음을 보여준다. FlipGuard는 LLM planner의 성능이나 general external provider integration을 중심 기여로 삼지 않는다. 오히려 manual configuration, bounded catalog, external provider, direct synthesizer 중 어디에서 candidate가 왔든 동일한 decision-integrity gate에 넣을 수 있다는 계층 분리를 제안한다. 현재 external provider evidence는 appendix의 fail-closed import 사례로 제한하며 일반적인 상호운용 성공을 주장하지 않는다.

## 3.3 보안 parameter 지침

CKKS configuration은 수치적으로 실행 가능하더라도 목표 security category를 만족하지 않을 수 있다. HomomorphicEncryption.org 표준화 커뮤니티와 관련 연구자들이 갱신한 security guideline은 secret distribution, ring dimension, modulus 크기에 따른 보수적 한계를 제공한다 [@bossuat2025security]. 본 연구는 최신 출판본 Table 5.2의 Category-128 uniform-ternary cap을 Security Policy V2로 versioning하고, Q와 QP를 객체별로 검사한다. 이는 catalog의 모든 실행 이력을 자동으로 정식 비교 후보로 인정하지 않게 한다.

Security-V2는 guideline을 그대로 runtime 분포와 동일시하지 않는다. Lattigo `Xs`와 `Xe`의 concrete parameter, exact Q/P prime, estimator model을 기록하고 distribution caveat를 함께 공개한다. 이 접근은 논문의 security claim을 좁히지만, 어느 object가 어떤 근거로 admission을 통과했는지 재현할 수 있게 한다. Excluded profile의 과거 실행 결과는 삭제하지 않고 historical ledger로 보존하되 bounded comparison에서는 제외한다.

## 3.4 FlipGuard의 위치

그림 2는 기존 provider/autotuner와 FlipGuard Decision-Integrity Layer의 역할을 구분한다. 기존 시스템은 graph transformation, scale·modulus 선택, bootstrap 배치, latency·accuracy trade-off 탐색 등 서로 다른 목적의 candidate generation을 수행할 수 있다. FlipGuard는 이 결과를 candidate literal로 받아 source/model/input/policy identity와 security를 검사하고, encrypted validation을 거쳐 SAFE 또는 REJECTED로 판정한다. Direct path에서는 graph fact로부터 candidate를 생성하고 bounded repair를 적용하지만, candidate generation과 final admission의 논리적 경계는 유지된다.

{{V3_FIGURE_02}}

이 계층화는 두 가지 연구적 이점을 갖는다. 첫째, candidate generator가 다른 목적 함수를 사용하더라도 최종 threshold-decision 요구를 공통 형식으로 적용할 수 있다. 둘째, candidate를 생성한 알고리즘의 성공과 decision-integrity admission의 성공을 분리해 보고할 수 있다. 빠르게 실행되는 candidate라도 decision gate를 통과하지 못하면 정식 safe-to-safe latency 비교에 포함하지 않는다. 반대로 catalog 밖에서 직접 합성한 candidate도 security와 admission을 통과하면 선택될 수 있다.

관련 연구와의 비교를 요약하면 다음과 같다.

| 연구군 | 주된 optimization target | candidate 생성 또는 탐색 | correctness/error 처리 | FlipGuard가 채택한 관행 | 실제 차이와 claim 경계 |
| --- | --- | --- | --- | --- | --- |
| CHET/EVA [@dathathri2019chet; @dathathri2020eva] | parameter·layout·compiler optimization | graph analysis 및 compiler pass | 실행 가능성과 scheme 제약 | graph fact와 literal provenance | 최종 threshold admission을 공통 gate로 분리 |
| HECATE/ELASM [@lee2022hecate; @lee2023elasm] | scale 또는 error-latency | scale scheduling | output error estimation | error를 configuration 판단에 사용 | sample decision margin·NO_SAFE·locked audit이 중심 |
| HECO [@viand2023heco] | 범용 FHE lowering과 optimization | IR transformation | compiler correctness·scheme 제약 | 명시적 graph contract | 범용 compiler를 주장하지 않음 |
| DaCapo [@cheon2024dacapo] | bootstrapping count와 latency | placement candidate planning | scale capacity | stage별 fail-closed 실행 | bootstrap planner가 본 기여가 아님 |
| AutoPrivacy/AutoFHE [@lou2020autoprivacy; @ao2024autofhe] | model accuracy와 latency | RL 또는 multi-objective search | model-level accuracy | application outcome을 parameter 판단에 연결 | per-sample threshold integrity와는 다른 단위 |
| Application-Aware AHE [@alexandru2024applicationaware] | application-bound correctness/security | formal application specification | 회로와 domain 기반 정의 | input scope를 contract에 포함 | empirical finite-set certificate만 제공 |
| FHE-Agent [@xu2025fheagent] | practical CKKS configuration automation | agent·tool 기반 pruning/calibration/repair | tool validation과 repair | bounded repair와 명시적 실패 | agent contribution과 general integration을 주장하지 않음 |

이 비교는 최초성 주장을 만들기 위한 목록이 아니다. 오히려 FlipGuard가 기존 compiler와 autotuner의 목표를 대체하지 않고, 그 위 또는 옆에서 사용할 수 있는 admission protocol이라는 범위를 확정한다. 본 연구의 novelty boundary는 direct synthesis만에 있지 않다. Graph/decision contract, bounded encrypted validation, failure-aware repair, abstention, literal lock, disjoint audit, Security-V2 filtered comparison과 evidence provenance를 하나의 연구 protocol로 결합한 데 있다.

## 3.5 채택한 평가 관행과 채택하지 않은 주장

본 연구는 선행연구에서 graph-aware parameter selection, error-latency 분리 보고, compiler/runtime 역할 분리, bootstrapping 또는 scale plan의 비용 모델, application scope 명시라는 평가 관행을 채택했다. 동시에 각 논문이 직접 보고하지 않은 관행을 추정해 FlipGuard의 근거로 사용하지 않는다. 예컨대 ELASM이 output error를 다룬다는 사실에서 threshold decision locked audit을 수행했다고 추론하지 않으며, Application-Aware AHE의 formal 정의에서 FlipGuard의 empirical certificate가 자동으로 증명된다고 결론내리지 않는다.

또한 본 논문은 CKKS autotuning, application-aware parameter generation, direct synthesis 또는 repair selection의 선행 최초성을 주장하지 않는다. Bounded-catalog fastest-safe는 유한 비교 집합의 기준이며 가능한 configuration 전체에 대한 최적성을 뜻하지 않는다. Sobel, Harris, CNN-lite 결과는 각 finite scalar-replicated adapter 범위에 한정한다. 이러한 제한을 관련 연구 장에서 먼저 명시함으로써 결과 장의 정량 성능이 연구 범위보다 넓은 기여로 오해되는 것을 막는다.
