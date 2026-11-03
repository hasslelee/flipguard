# 심사 질문과 대응 상태

| ID | Likely question | Required answer/evidence | Status |
|---|---|---|---|
| R01 | 경계 입력을 제외하면 실제로는 누구를 보호하나? | 전체 분모, 최저 coverage, 경계 flip | 기존 raw 재계산 완료; 새 유보 규칙 실행 |
| R02 | 68/68은 18,367개 전부 무반전인가? | 16,049 보호, 2,318 제외, 12쌍/21회 경계 반전 | 확인 완료 |
| R03 | 평문 추론 없이 운영 gate가 가능한가? | 입력에 oracle 없는 API와 실제 CKKS 재계산 | 구현·단위 테스트·파일럿 완료 |
| R04 | MSE를 줄이면 이미 해결되는 것 아닌가? | 최소오차 0/68 인정, matched budget 비용/coverage 비교 | 기존 근거 확인; 비교 확장 진행 중 |
| R05 | 83.43%는 단순히 전체 탐색과 비교해서 아닌가? | 고정 B와 실제 wall time, 총 setup/calibration 비용 | 기존 과장 없음; 본 비교 추가 필요 |
| R06 | 거의 같은 파라미터끼리 시간을 비교했나? | 65/68 literal 동일, 63/68 ID 동일 | 원시 직접 확인 |
| R07 | 왜 +4 bit, rho=.5, delta=.001인가? | 사전 정책·민감도 분석·개발/감사 구분 | 원본 유지; 새 정책 별도 ID |
| R08 | 민감도 합은 엄밀한 오차 상한인가? | 경험적 planner 신호임을 명시 | 논문과 source 일치 |
| R09 | 0회 오류가 새 키에서 재현되나? | 독립 키/입력 단위의 위험 상한 | 제한된 유한 모집단 600회 감사 |
| R10 | packed slot을 독립 표본으로 셌나? | 반복 의존 표시, 별도 IID 설계 | 파일럿 통계 claim 차단 |
| R11 | 유보하면 언제나 안전하지 않나? | selective risk와 coverage 동시 요구 | Wine 0% coverage를 실패로 공개 |
| R12 | 높은 정밀도면 언제나 해결되나? | 정확한 경계/tie에서 high-scale 반전 측정 | 스트레스에서 반전 확인 |
| R13 | 재계산은 정말 빠른가? | 요청 수가 아닌 ciphertext workload/queue cost | naive cascade 비용 실패 공개 |
| R14 | 현재 모델의 정답률이 낮은 것은 아닌가? | plaintext label metric과 CKKS 일치 분리 | 파일럿 accuracy 기록; MLP 수렴 제한 공개 |
| R15 | 다항식 근사 때문에 이미 결정이 바뀌지 않았나? | original→polynomial→CKKS 세 수준 | 새 파일럿은 직접 학습 기준; 변환 실험 후속 |
| R16 | 128-bit를 무엇으로 입증하나? | 실제 Q/QP, 분포, 정책/estimator 범위 | 기존 정책 유지; 보편적 보안 claim 없음 |
| R17 | 서버가 거짓 결과를 주면? | 위협 모델과 검증 가능 계산의 구분 | 정직한 서버 범위 명시 |
| R18 | retry bit가 정보를 노출하지 않나? | 관측 transcript·패딩/고정 스케줄 비용 | 위협 모델에 포함; 분산 평가 후속 |
| R19 | 외부 도구보다 낫다는 비교가 공정한가? | 같은 출력 의미/그래프/보안/packing | 기존은 보조 자료; 정식 비교 후속 |
| R20 | 새 clone에서 재현되는가? | fixture manifest, hashes, pinned environment | 새 GitHub clean runner의 테스트·2,646 payload 검증 통과; 과거 전체 fixture는 로컬 archive |
| R21 | 데이터셋·seed 수를 부풀렸나? | case-row와 unique source row, 조건부 모형 | 별도 명시; aggregate에 독립 CI 부여 안 함 |
| R22 | stress 결과로 유리하게 튜닝했나? | protocol chronology와 변경 이유 | 동결 유지; V1A는 암호화 전 소수 생성 실패만 수정 |
