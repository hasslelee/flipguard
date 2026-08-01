# 제1장 서론

## 1.1 연구 배경

동형암호는 암호문을 복호화하지 않은 상태에서 연산을 수행하고, 그 결과를 복호화했을 때 대응하는 평문 연산 결과를 얻도록 하는 암호 기술이다. 이 성질은 의료, 금융, 공공 데이터처럼 원자료를 외부 계산 주체에 공개하기 어려운 환경에서 계산과 데이터 보호를 동시에 달성할 가능성을 제공한다. 특히 CKKS(Cheon-Kim-Kim-Song) 근사 동형암호 체계는 실수 또는 복소수 벡터에 대한 근사 산술을 지원하므로 통계 처리와 기계학습 추론에 널리 사용된다 [@cheon2017ckks]. 그러나 CKKS의 편의성은 정확한 정수 산술이 아니라 근사 산술이라는 조건과 함께 주어진다. 인코딩, 암호화 잡음, 곱셈, 재선형화, 재스케일 과정에서 발생하는 오차는 설정한 스케일(scale), 모듈러스 체인(modulus chain), 다항식 차수(polynomial degree), 연산 깊이에 따라 달라진다.

CKKS 실행 구성(configuration)을 정하는 일은 단순히 큰 파라미터를 선택하는 문제가 아니다. 큰 환 차원(ring dimension)과 긴 modulus chain은 계산 가능 깊이와 정밀도에 여유를 줄 수 있지만, 키 생성·메모리·연산 지연을 증가시키며 보안 한계에도 제약을 받는다. 반대로 작은 구성은 빠르지만 scale exhaustion, level 부족, 수치 오차 또는 실행 실패를 일으킬 수 있다. 따라서 사용자는 계산 그래프, 입력 범위, 필요한 출력 정확도, 보안 수준을 함께 고려해야 한다. CHET, EVA, HECATE, ELASM, HECO, DaCapo와 같은 컴파일러 및 최적화 연구는 파라미터 선택, scale 관리, 부트스트래핑 배치, 데이터 배치와 코드 생성의 자동화를 발전시켰다 [@dathathri2019chet; @dathathri2020eva; @lee2022hecate; @lee2023elasm; @viand2023heco; @cheon2024dacapo].

본 연구가 다루는 간극은 이들 연구의 가치와 별개로 남는 최종 의사결정 문제다. 분류 또는 위험 판정처럼 출력 점수(score)를 임계값(threshold)과 비교하는 시스템에서는 작은 근사 오차도 score의 수치적 차이보다 더 직접적인 결과를 낳을 수 있다. 평문 score와 CKKS score의 차이가 작더라도, 그 차이가 임계값 반대편으로 score를 이동시키면 최종 결정(decision)이 바뀐다. 반대로 절대오차가 상대적으로 커 보여도 평문 score가 임계값에서 충분히 멀다면 decision은 보존될 수 있다. 그러므로 정밀도(precision), 평균제곱오차(mean squared error), 지연시간(latency)만을 독립적으로 최적화하는 것과 최종 threshold decision을 보존하는 것은 같은 목적이 아니다.

기존 연구가 decision 또는 application accuracy를 전혀 고려하지 않는다고 단정할 수는 없다. AutoPrivacy와 AutoFHE는 정확도와 성능의 절충을 다루며, Application-Aware Approximate Homomorphic Encryption은 회로와 입력 domain에 결합된 correctness 및 security 정의의 필요성을 이론적으로 정리한다 [@lou2020autoprivacy; @ao2024autofhe; @alexandru2024applicationaware]. 본 연구의 중심은 이 흐름을 부정하는 데 있지 않다. 핵심은 서로 다른 구성 제공자(configuration provider)의 출력에 공통으로 적용할 수 있는 임계값 결정 무결성 계약(threshold decision-integrity contract), 후보 단위의 승인·거부, SAFE 후보 부재 시 명시적 기권, 그리고 선택 리터럴(literal)을 재조정 없이 분리된 잠금 감사(locked audit)에서 재생하는 절차를 하나의 검증 계층으로 구성하는 데 있다.

## 1.2 문제 인식

초기 실험 방식은 미리 정한 {{N:security_catalog_profiles_total}}개 CKKS profile과 {{N:catalog_execution_paths}}개 실행 path의 조합을 모든 작업부하-분할 인스턴스(workload-partition instance)에 실행하는 유한 후보 목록(bounded catalog)에 가까웠다. 이 방식은 비교 가능한 유한 후보 집합을 만들고, 실행 가능한 후보와 decision-integrity를 만족하는 후보를 관찰하는 데 유용하다. 또한 가장 빠른 SAFE 후보를 유한 범위에서 식별할 수 있으므로 평가용 기준선으로서 의미가 있다. 그러나 사용자가 새 모델과 데이터셋을 입력할 때마다 같은 catalog를 반복 실행한다면, 계산 그래프에서 이미 알 수 있는 깊이와 scale 요구를 후보 생성에 충분히 활용하지 못한다. 후보 수가 커질수록 실행 비용이 선형으로 증가하고, catalog 밖의 유효한 literal은 처음부터 고려되지 않는다.

이 문제의 해결 방향은 catalog를 더 크게 만드는 것만이 아니다. FlipGuard는 지원되는 계산 그래프에서 연산 깊이, rescale 수, 곱셈 구조, 요구 slot과 같은 사실을 추출하고, threshold decision contract와 동결된 수치·보안 정책을 결합하여 첫 CKKS literal을 직접 합성한다. 그 후보를 실제 암호화 validation에 통과시키고, 실패 원인이 수치 정밀도 또는 level 부족으로 분류될 때만 제한된 repair를 적용한다. 첫 SAFE에서 멈추며, 사전 선언한 trial budget 안에서 SAFE를 확립하지 못하면 NO_SAFE를 반환한다. 이 방식에서 encrypted execution은 configuration search 전체를 대신하는 전수 탐색이 아니라, 정적으로 합성한 후보를 경험적으로 승인하거나 반증하는 단계다.

<!-- P:INTRO-CORE CLAIM:scoped_direct_synthesis,finite_scope_decision_integrity -->
FlipGuard는 선언된 graph adapter와 동결 정책 범위에서 computation graph와 threshold decision-integrity contract로부터 CKKS literal을 직접 합성했다. 또한 선언된 finite validation에서 관측 error와 decision margin을 결합해 후보를 certify-or-reject하고, disjoint audit에서 동결 literal을 재생한다. 여기서 SAFE는 선언된 유한 validation artifact와 관측 fresh-key run에서 정책을 통과했다는 뜻이며, 입력 분포 전체에 대한 수학적 보증을 뜻하지 않는다.

## 1.3 연구 목적과 연구 질문

본 연구의 목적은 지원 그래프와 decision-integrity contract에서 CKKS 실행 literal을 직접 합성하고, 제한된 encrypted trial, bounded repair, NO_SAFE, locked audit을 포함하는 재현 가능한 승인 체계를 구현·평가하는 것이다. 이를 위해 다음 네 연구 질문을 설정한다.

**RQ1.** 지원되는 계산 그래프와 decision-integrity contract에서 CKKS literal을 직접 합성하여 Security-V2 bounded catalog 대비 encrypted candidate trial을 줄일 수 있는가?

**RQ2.** 직접 합성 후보와 bounded repair가 finite validation scope에서 decision-integrity admission을 통과하고, 선택 literal이 disjoint locked audit에서 retuning 없이 유지되는가? 또한 안전한 후보를 확립할 수 없을 때 NO_SAFE를 반환하는가?

**RQ3.** 동일 host의 paired protocol에서 direct configuration은 Security-V2 bounded-catalog fastest-safe configuration보다 어떤 latency 차이를 보이는가?

**RQ4.** 이 결과는 deeper polynomial graph, scoped Sobel/Harris/CNN-lite, 독립 training/data seed에서 어느 범위까지 유지되며, 어떤 negative result와 한계를 보이는가?

이 질문들은 서로 다른 보장 수준을 갖는다. RQ1은 후보 실행 회계, RQ2는 finite-set 경험적 admission과 audit, RQ3은 한 host에서의 paired 측정, RQ4는 선언된 adapter 범위의 확장을 다룬다. 어느 질문도 임의의 CKKS 프로그램, 모든 데이터 분포, 모든 하드웨어에 대한 결론을 요구하지 않는다. 이러한 범위 분리는 약한 결과를 숨기기 위한 장치가 아니라, 관측된 근거가 실제로 지지하는 명제만 남기기 위한 연구 설계다.

## 1.4 연구 기여

본 논문의 기여는 네 가지로 정리한다.

<!-- P:INTRO-CONTRIB1 CLAIM:finite_scope_decision_integrity -->
첫째, 계산 그래프, model/input digest, threshold, decision margin 정책, 보안 정책을 결합한 **decision-integrity workload contract와 finite-scope admission**을 제안한다. 평문 score와 CKKS score의 오차를 decision margin과 비교하고, flip과 정책 위반을 분리해 기록한다. 이 certificate는 empirical finite-set certificate이며 분석적 CKKS error bound를 대신하지 않는다.

<!-- P:INTRO-CONTRIB2 CLAIM:scoped_direct_synthesis,adaptive_repair -->
둘째, **direct literal synthesis와 bounded failure-aware repair**를 구현한다. graph fact로부터 LogN, Q/P chain, initial scale을 계산하고, 실행 실패를 분류해 수치 repair와 level repair를 사전동결된 한도 안에서 적용한다. 후보는 최대 {{N:max_encrypted_trials}}번의 encrypted trial만 허용되며 첫 SAFE에서 멈춘다.

<!-- P:INTRO-REPAIR CLAIM:adaptive_repair -->
FlipGuard의 동결된 bounded repair는 선언된 개발 ablation에서 one-shot 실패 네 건을 SAFE 선택으로 전환했으며, 이는 보편적 repair 성공을 뜻하지 않는다. 이 결과는 repair의 경험적 가치를 보여주지만, 모든 그래프와 입력에서 repair가 성공한다고 해석하지 않는다.

<!-- P:INTRO-CONTRIB3 CLAIM:no_safe_behavior,primary_no_retuning_locked_audit -->
셋째, **NO_SAFE와 no-retuning locked audit protocol**을 제시한다. 제한된 후보 budget 안에서 SAFE를 확립하지 못하면 임의의 차선 후보를 선택하지 않고 기권한다. 후보가 선택되면 candidate literal과 관련 digest를 잠그고, configuration-validation과 분리된 audit input에서 synthesis와 repair를 호출하지 않은 채 그대로 재생한다. Audit의 negative result는 후보 재조정의 근거가 아니라 해당 claim을 낮추는 과학적 결과로 보존한다.

<!-- P:INTRO-CONTRIB4 CLAIM:formal_trial_reduction,paired_latency,structural_extension,scoped_non_tabular_extension,training_model_seed_extension,security_attestation -->
넷째, **Security-V2 bounded comparison, paired latency, negative result, structural/scoped generalization을 포함한 재현 가능한 evidence system**을 구축한다. Security-V2에 허용된 {{N:security_catalog_profiles_admitted}}개 profile과 {{N:catalog_execution_paths}}개 path만 정식 bounded catalog에 포함하고, Q와 QP를 객체별로 재감사한다. 모든 주요 결과는 source commit, policy digest, input/model/split digest, raw ledger, summary, SHA256SUMS, verifier와 연결한다. 이 체계는 성공 사례뿐 아니라 NO_SAFE, audit policy rejection, provenance mismatch의 fail-closed 기록을 유지한다.

## 1.5 논문 범위와 구성

본 연구는 선언된 tabular graph, 더 깊은 polynomial graph, scalar-replicated Sobel/Harris/CNN-lite adapter를 대상으로 한다. 보장 범위는 동결된 policy와 finite validation/audit artifact에 한정된다. Bounded catalog는 Security-V2를 통과한 유한 비교 집합이며 전역 탐색을 뜻하지 않는다. Paired latency는 동일 연구 host에서 측정한 결과이고 실제 서비스 환경의 성능을 대변하지 않는다. Security 결과 역시 명시한 runtime object, Q/P literal, estimator model과 보수적 표 한계에 대한 재감사이며, 임의 runtime 분포와의 정확한 동등성을 뜻하지 않는다.

제2장은 CKKS 근사 산술, 파라미터, decision margin과 보안 정책을 설명한다. 제3장은 compiler, autotuning, application-aware correctness 연구와 FlipGuard의 관계를 분석한다. 제4장은 문제와 assurance model을 형식화하고, 제5장과 제6장은 설계 및 구현을 제시한다. 제7장은 평가 프로토콜과 통계 단위를 정의하며, 제8장은 direct synthesis, audit, NO_SAFE, latency, 구조 확장, security 결과를 보고한다. 제9장은 negative result와 한계를 논의하고, 제10장은 재현성·보안 artifact를 정리한다. 제11장은 admitted claim의 범위 안에서 결론을 제시한다.
