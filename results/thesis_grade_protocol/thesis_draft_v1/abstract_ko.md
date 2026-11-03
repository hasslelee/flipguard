# 국문 초록

## 결정 무결성 계약 기반 CKKS 실행 구성 직접 합성 및 검증 기법

CKKS 근사 동형암호는 암호화된 실수형 데이터에 대한 계산을 지원하지만, 스케일(scale), 모듈러스 체인(modulus chain), 다항식 차수(polynomial degree), 실행 경로의 선택에 따라 수치 오차와 지연시간이 크게 달라진다. 특히 점수를 임계값과 비교하는 응용에서는 작은 근사 오차가 최종 결정을 바꿀 수 있으므로 실행 가능성이나 평균 오차만으로 구성을 승인하기 어렵다. 기존 컴파일러와 자동 조정기(autotuner)는 파라미터, 스케일, 부트스트래핑, 지연시간과 정확도 최적화를 발전시켰으나, 서로 다른 후보 출처에 공통으로 적용되는 임계값 결정 무결성 승인과 무재조정 잠금 감사는 별도 문제로 남는다.

<!-- P:ABSTRACT-KO-METHOD CLAIM:scoped_direct_synthesis,adaptive_repair,finite_scope_decision_integrity -->
본 논문은 지원 계산 그래프와 임계값 결정 무결성 계약에서 구체적인 CKKS 리터럴을 직접 합성하는 FlipGuard를 제안한다. FlipGuard는 그래프 특성으로부터 스케일, Q/P 체인, LogN을 계산하고 작업부하마다 최대 4회의 암호화 후보 시험으로 합성 경로를 검증한다. 실패 원인이 허용된 수치 정밀도 또는 레벨 부족 유형일 때만 제한적 복구를 수행하며 첫 SAFE에서 멈춘다. SAFE 후보를 확립하지 못하면 NO_SAFE로 기권하고, 선택 리터럴은 구성 검증과 분리된 잠금 감사에서 재조정 없이 재생한다. 결정 보존 충분조건 `e_c(x)<m(x)`과 운용 여유 정책 `e_c(x)<0.5m(x)`를 구분하며, 후자의 0.5는 사전동결 margin-utilization cap이지 이론적 최적값이 아니다.

<!-- P:ABSTRACT-KO-PRIMARY CLAIM:formal_trial_reduction,primary_no_retuning_locked_audit,no_safe_behavior -->
주요 평가는 5개 데이터셋, 2개 모델 그래프, 5개 결정론적 반복 분할로 구성한 50개 작업부하-분할 인스턴스를 사용했다. Seed 0는 개발·기술 결과, seeds 1--4는 동결 이후 확인 평가로 분리했다. Security-V2가 허용한 정식 bounded catalog는 전체 700개 후보, 확인 평가 560개 후보다. 직접 합성은 전체 70회와 확인 평가 56회의 후보 시험을 사용해 두 경우 모두 90% 감소를 기록했다. 무재조정 잠금 감사는 확인 평가 40/40과 개발 평가 10/10에서 PASS했고 재조정은 0회였다. 사전 선언한 후보 예산 대조군은 16/40에서, 유한 후보 영역 대조군은 50/50에서 NO_SAFE를 반환했다.

<!-- P:ABSTRACT-KO-EXT CLAIM:paired_latency,structural_extension,scoped_non_tabular_extension,training_model_seed_extension -->
동일 호스트의 쌍체 측정 프로토콜에서 Security-V2 bounded-catalog 전체 지연시간을 직접 합성 전체 지연시간으로 나눈 확인 평가 데이터셋-모델 군집 기하평균은 3.140660이었고, 군집 부트스트랩 95% 신뢰구간은 [2.342334, 4.215313]이었다. 더 깊은 다항식 그래프 `mlp_square_poly3`는 25/25 선택 후 잠금 감사 24건 PASS와 결정 뒤집힘이 없는 reserve-policy REJECT 1건을 기록했다. Sobel, Harris, scalar-replicated CNN-lite 및 3개 데이터셋 x 3개 독립 학습·데이터 seed 확장은 각각 선언된 유한 범위에서 선택과 감사 근거를 제공했다.

결과는 유한한 검증·감사 artifact, 지원 adapter, 동결 정책, 한 호스트의 지연시간 범위에 한정된다. 본 논문은 분포 전체의 결정 안전성, 임의 그래프 지원, 구성 공간 전체의 최적성, 운영 환경 성능, 실행 분포와 estimator의 완전한 동등성, 분석적 CKKS certificate를 주장하지 않는다. FlipGuard의 기여는 후보 생성 자체의 최초성보다 직접 합성, 경험적 결정 승인, 제한적 복구, 기권, 변경 불가능한 감사 재생과 provenance를 하나의 재현 가능한 결정 무결성 계층으로 결합한 데 있다.

**주제어:** CKKS, 동형암호, 구성 합성, 결정 무결성, 암호화 검증, NO_SAFE, locked audit
