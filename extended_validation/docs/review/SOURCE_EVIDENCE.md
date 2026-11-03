# 심사 판단의 코드 근거

아래 `baseline/source/`는 원본 소스의 수정하지 않은 독립 복사본이다.
행 번호는 이 checkpoint에서 확인했다. 최종 과학적 주장에는 코드만으로 충분하지
않으며, 원시 결과 재계산과 고정 정책도 함께 요구한다.

| Question | Source location | Verified behavior and implication |
|---|---|---|
| 보호 입력은 어떻게 정하는가? | `baseline/source/internal/certify/coverage.go:81` | `abs(score-threshold) <= marginFloor`이면 제외. 전체 입력의 결정 보존을 뜻하지 않음 |
| SAFE는 분석적 증명인가? | `baseline/source/internal/certify/engine.go:137` | proof의 존재와 strict bound, 관측 flip/violation을 별개 조건으로 계산. 관측 성공을 전역 bound로 승격할 수 없음 |
| 표본·키 관측은 어떻게 모으는가? | `baseline/source/internal/certify/observation.go:69` | 표본 ID 중복, threshold 불일치, 관측 길이 불일치와 비유한 값을 거부 |
| 다중 클래스도 같은 조건인가? | `baseline/source/internal/certify/multiclass_decision_contract.go:102` | 모든 경쟁 클래스의 오차와 gap을 검사하는 조건부 bound; 동점은 strict proof 불가 |
| 다중 클래스의 제외 영역은? | `baseline/source/internal/certify/multiclass_decision_contract.go:184` | 작은 top-two gap은 유한 SAFE 주장 밖이라는 주석과 구현 |
| V2의 고정값은? | `baseline/source/internal/ckksplanner/direct_policy.go:65` | alpha 0.5, margin floor 0.001, 최대 암호화 평가 4, scale repair +4, level repair +1. 후속 결과로 변경하지 않음 |
| 초기 정밀도는 어디서 나오는가? | `baseline/source/internal/ckksplanner/synthesis.go:654` | 출력 오차 예산을 aggregate sensitivity로 나누고, 음의 log2를 올림한 비트에 guard를 추가. 경험적 sensitivity를 분석적 보증으로 해석하지 않음 |
| repair는 exhaustive search인가? | `baseline/source/internal/ckksplanner/synthesis.go:407` | 실패 신호에 따라 단일 새 후보를 유도하며 level/scale을 단조 증가. 유한 전체 후보 평가와 다른 탐색 방식 |
| 보안 policy와 실제 QP는? | `baseline/source/internal/ckksplanner/security_policy.go:65`, `concrete_security.go:24` | 정책 admission과 실제 소수 곱의 평가 경로. 특정 분포의 exact security 증명과 구분 |
| 신규 gate가 평문 oracle를 쓰는가? | `src/deciprotect/decision.py:13` | 복호화 logit과 고정 radius만 받음; 평문 reference는 평가용 별도 함수 |
| 표본 부족을 어떻게 처리하는가? | `src/deciprotect/decision.py:32` | 요구 order statistic이 n을 넘으면 무한 구간. Wine의 전부 유보는 이 규칙의 결과 |
| 반환 오류율 검정의 단위는? | `src/deciprotect/risk.py:24`, `scripts/run_iid_audit.py:15` | 독립 단위가 명시되지 않으면 승인하지 않음; 별도 감사에서 입력+새 키 600회를 사용 |
| 새 서버 평가 함수에 비밀키가 있는가? | `cmd/deciprotect-ckks/main.go:105` | parameters/layers/ciphertexts/evaluation keys만 받음. 전체 harness의 역할은 아직 한 로컬 환경에 있음 |
| 새 CKKS 파라미터는 실제로 기록하는가? | `cmd/deciprotect-ckks/main.go:155` | 실제 Q/P, logQP, 키 분포와 크기, 암·복호화 및 평가 시간 기록. 독립적인 exact 보안 추정은 미완료 |
| 새 다중 클래스 가설의 구현은? | `src/deciprotect/difference.py:7` | 공통 logit 오차를 상쇄하는 residual range. 현재 진단에서 추가 반환 0건이므로 개선 주장 불가 |

원시 결과 검증은 `scripts/audit_legacy.py:35`,
`scripts/recompute_legacy_latency.py:16`, `scripts/verify_research.py:19`에 있다.
기존 정책을 새 자료로 재조정한 결과가 아니며, 새 정책과 실험은 별도 protocol ID를 가진다.
