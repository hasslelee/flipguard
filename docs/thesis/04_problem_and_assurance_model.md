# 제4장 문제 정의와 Assurance Model

## 4.1 시스템 주체와 입력

FlipGuard가 받는 기본 입력은 학습이 끝난 model artifact, 그 모델을 CKKS 연산으로 표현한 지원 computation graph, score를 이진 decision으로 바꾸는 threshold `tau`, configuration-validation input, locked-audit input, 그리고 동결된 direct/security policy다. Model artifact는 weight, bias, graph structure, threshold를 포함하며 digest로 식별된다. Input artifact는 source representation과 실행용 prepared representation을 각각 보존한다. Candidate provider는 direct synthesizer, manual literal, bounded catalog, 외부 provider 중 하나일 수 있다.

사용자는 모델과 데이터셋을 제공하지만, FlipGuard가 임의 모델을 자동으로 CKKS graph로 번역하는 것은 아니다. 각 graph adapter는 지원 operation, polynomial formula, multiplicative depth, rescale trace, required slot을 명시해야 한다. 이 계약을 만족하지 못하는 graph는 fail-closed로 처리한다. 따라서 문제의 입력 domain은 adapter가 선언한 graph family와 materialization rule로 제한된다.

## 4.2 Decision-integrity workload contract

Workload contract `W`를 다음 요소의 묶음으로 정의한다.

\[
W=(G,M,X_v,X_a,\tau,\delta,\rho,P_d,P_s),
\]

여기서 `G`는 graph contract, `M`은 model artifact, `X_v`와 `X_a`는 각각 configuration-validation 및 locked-audit artifact, `tau`는 threshold, `delta`는 margin floor, `rho`는 margin-utilization cap, `P_d`는 Direct Policy V2, `P_s`는 Security Policy V2다. Contract에는 각 요소의 canonical digest와 source commit이 결합된다. 실행 결과는 이 identity를 재현하지 못하면 formal evidence로 승격할 수 없다.

Graph contract는 operation sequence만 나열하지 않는다. Model formula, multiplication count, ciphertext-ciphertext multiplication 여부, rescale count, expected scale trace, output slot 요구, packing scope를 포함한다. Primary tabular adapter는 scalar-replicated packing을 사용하며, 같은 scalar input을 slot에 복제해 graph를 실행한다. Sobel, Harris, CNN-lite 확장 역시 해당 evidence에서 선언한 scalar-replicated 범위로 제한된다.

## 4.3 Candidate와 literal identity

Candidate literal `c`는 최소한 `(LogN, Q primes, P primes, default scale, execution path)`를 포함한다. Profile 이름이나 candidate ID가 같다는 사실만으로 literal identity가 성립하지 않는다. FlipGuard는 exact prime list와 scale을 canonical serialization한 literal digest를 사용한다. 또한 model digest, input digest, graph digest, policy digest를 별도로 기록해 동일 parameter가 다른 workload에 적용된 경우를 구분한다.

Source data와 prepared data도 구분한다. Source artifact는 원래 row와 full-precision value를 보존하고, prepared artifact는 실행에 필요한 provenance column 또는 materialized representation을 포함할 수 있다. 두 파일의 raw byte가 다르더라도 ordered semantic row가 같을 수 있다. Validation identity audit v1은 이 representation layer를 혼동해 fail-closed했고, v2는 source raw, prepared raw, semantic, ordered-row, model digest를 분리했다. 50/50 primary instance는 source artifact가 byte-identical했고, prepared raw byte는 provenance 표현 때문에 달랐으나 execution semantics는 동일한 CLASS A로 판정되었다. 이 사건은 삭제하지 않고 artifact assurance 사례로 유지한다.

## 4.4 상태 정의

Candidate execution 결과는 다음 네 상태로 구분한다.

**SAFE**는 실행이 성공하고, `V_cert`의 모든 관측에서 decision flip이 없으며, `e_c(x)<rho*m(x)` 운용 policy 위반이 없고, Security-V2가 필요한 object를 모두 admit한 상태다. SAFE는 선언된 finite artifact와 key repetition의 관측 결과다.

**REJECTED**는 실행은 완료되었지만 적어도 하나의 decision flip 또는 operational reserve violation이 관측된 상태다. Flip이 없더라도 `rho*m(x)`를 초과하면 REJECTED가 될 수 있다. 이 구분은 observed decision preservation과 사전동결 reserve policy를 혼합하지 않기 위해 필요하다.

**FAILED**는 parameter materialization, key generation, CKKS evaluation, decrypt/parse 또는 필수 provenance 검증이 정상 완료되지 않은 상태다. FAILED를 REJECTED와 분리하면 수치적으로 부적절한 후보와 실행할 수 없는 후보를 다른 failure cause로 repair하거나 보고할 수 있다.

**NO_SAFE**는 허용된 candidate budget을 소진했지만 SAFE를 확립하지 못한 selection outcome이다. 이는 가능한 모든 CKKS configuration이 부적합하다는 결론이 아니다. 주어진 policy, candidate generator, repair budget, finite validation domain 안에서 승인 가능한 후보가 없었다는 기권 상태다.

## 4.5 Certifiable 및 ambiguous 집합

`V_cert={x | m(x)>delta}`이고 `V_amb={x | m(x)<=delta}`로 둔다. `delta=0.001`은 primary protocol에서 사전동결된 margin floor다. Candidate `c`에 대해 다음 empirical admission predicate를 정의한다.

\[
Cert(c,V_{cert}) = RunOK(c)\land SecurityV2(c)
\land \sum_{x\in V_{cert}}Flip_c(x)=0
\land \sum_{x\in V_{cert}}\mathbf{1}[e_c(x)\geq \rho m(x)]=0.
\]

여러 fresh-key run을 사용하는 경우 위 합은 sample-key observation에 적용된다. `V_amb`는 certificate 위반으로 세지 않지만 크기와 coverage를 공개한다. 이 방식은 threshold 바로 근처의 불안정한 sample을 조용히 삭제하는 것이 아니라, certificate가 주장하는 finite scope에서 분리해 회계하는 것이다.

Candidate가 SAFE인지와 model 자체가 정확한지는 다른 문제다. Plaintext model의 task accuracy, calibration, fairness는 별도의 모델 품질 속성이다. FlipGuard는 주어진 plaintext model decision을 CKKS 실행이 보존하는지를 검사하며, 잘못 학습된 평문 모델의 decision을 올바른 것으로 바꾸지 않는다.

## 4.6 Threat 및 assurance boundary

본 연구가 직접 다루는 위험은 잘못된 CKKS parameter 선택으로 인해 실행 실패, 수치 budget 위반, threshold decision flip이 생기거나, selection과 audit 사이에 candidate 또는 input identity가 달라지는 경우다. Evidence system은 source commit과 binary digest가 다른 결과의 혼합, Security-V2 excluded 후보의 정식 비교 포함, audit 후 retuning, frozen evidence overwrite를 무결성 위반으로 취급한다.

반면 malicious evaluator가 임의의 ciphertext를 변조하는 active attack, side channel, secret-key compromise, network protocol attack은 본 연구의 threat model이 아니다. CKKS scheme의 IND-CPA security를 새로 증명하지 않으며, implementation constant-time 특성을 평가하지 않는다. Security-V2 admission은 parameter object가 선언된 보수적 한계와 estimator sensitivity를 통과했는지를 검증한다.

표 1은 paper claim registry의 상태와 scope를 제시한다. `paper_admitted=true`인 문장만 본문의 긍정적 주장으로 사용할 수 있고, BLOCKED 또는 NOT_EVALUATED 항목은 limitation이나 future work로만 기술한다.

{{V3_TABLE_01}}

## 4.7 보장하는 것

FlipGuard가 제공하는 첫 번째 assurance는 선언된 finite validation artifact에서의 empirical decision-integrity admission이다. 각 certifiable sample과 fresh-key observation에 대해 error, margin, flip, reserve-policy pass를 기록한다. 두 번째는 selected literal을 byte-identical하게 잠그고 disjoint locked audit에서 synthesis나 repair 없이 재생했다는 no-retuning provenance다. 세 번째는 literal의 Q와 필요한 evaluation-key QP가 Security-V2 admission을 통과했다는 정적 재감사다. 네 번째는 모든 결과를 source/policy/input/model/split digest와 연결한 재현성이다.

<!-- P:ASSURANCE-FINITE CLAIM:finite_scope_decision_integrity -->
FlipGuard는 선언된 finite validation에서 관측 error와 decision margin을 결합해 후보를 certify-or-reject하고, disjoint audit에서 동결 literal을 재생한다. 이 문장은 finite artifact에 대한 관측과 replay protocol을 말하며 확률분포 전체의 안전성을 말하지 않는다.

## 4.8 보장하지 않는 것

첫째, validation과 audit 결과는 미래 입력 분포 전체의 decision preservation을 증명하지 않는다. 둘째, graph adapter 밖의 임의 연산과 packed CNN을 지원한다고 결론내리지 않는다. 셋째, bounded catalog 비교는 유한 후보 집합에 대한 것이며 구성 공간 전체의 최적성을 제시하지 않는다. 넷째, two-estimator security sensitivity가 Lattigo runtime distribution과 정확히 동일한 security estimate를 준다고 주장하지 않는다. 다섯째, primitive CKKS residual bound를 graph 전체에 인스턴스화한 분석적 certificate는 제공하지 않는다. 여섯째, 한 host에서 측정한 latency는 production deployment의 성능 보증이 아니다.

이 negative boundary는 별도의 부록이 아니라 assurance model의 일부다. 어떤 결과가 PASS였는지와 함께 무엇이 평가되지 않았는지를 명시해야 reviewer가 certificate의 실제 강도를 판단할 수 있다. 그림 10과 표 13은 결과 장 이후 이 경계를 다시 종합한다.

