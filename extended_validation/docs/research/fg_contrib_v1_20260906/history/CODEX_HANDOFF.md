# 최종 논문 방법의 두 번째 확대 인계

상태: **COMPLETED_EXPLORATORY**. 작업은 `/home/ckks2/deciprotect`에서만 수행한다.
원본 FlipGuard·baseline·archive·완료 결과/PDF는 보존한다. archive 업로드/전수 재해시 금지.
최종 PDF는 `baseline/journal_final_20260905.pdf`, SHA-256
`0210899a12ff1025db358e1812159ca4af2b5c6095a79e2b7b19200d7e9f3b85`.
시작 checkpoint는 `b64fa9c100f4f13789e3012a8e2258a48034f5d0`이고 당시 clean이었다.

질문은 수치 정확성 조건과 비교해 입력별 판정·마진 오차 조건이 선택 구성·별도 입력·비용에
주는 차이다. 외부 방법의 실패나 제안 방법의 승리를 예정하지 않는다. 오프라인 선택의 평문
참조는 원래 방법이다. DP-03 queue/유보/새 위험 보장으로 바꾸지 않는다.

Protocol: `FG_EXPAND_V2_PREP_20260905`, `FG_EXPAND_V2_MAIN_20260905`,
`FG_EXPAND_V2_EVA_NATIVE_20260905`. Run: `fg_expand_v2_20260905_run01`.
Fashion-MNIST 공식 train 60,000/test 10,000, 기존 784→100→10 제곱 MLP, 학습 seed 0/1/2.
공식 train의 학습 54,500·개발 5,000·선택 500은 분리했고 기존 8epoch 학습을 완료했다.
개발 정답률 88.82/88.50/88.24%; 수렴 보증은 아니다. 공식 test를 학습/선택에 쓰지 않는다.
별도 10,000은 기존 500slot×20배치다. 후보·배치마다 새 키 3개(후보당 60문맥), 키/slot을
독립 데이터셋으로 세지 않는다. 시간은 최종 V17의 20입력 배치·예열 1·측정 6·키 3이다.
사전 본 실행 예상은 2–4시간, 명령 실행 시간 합산 상한은 6시간이다. 미완료를 0실패로 채우지 않는다.

추가 수치 기준은 개발 출력 FP16 반올림 RMSE/최대오차. 특정 논문 재현이 아닌 대표 정밀도
기준이다. 같은 유한 후보 전체의 사후 분석이며 최대 4후보 온라인 선택처럼 쓰지 않는다.
초기 합성과 유한 후보에는 마진 정보가 남아 있다. 완전히 판정 정보를 쓰지 않는 기법은 아니다.
모델·후보를 고정한 뒤 감사하며, 같은 후보 역할 alias는 관측으로 중복 집계하지 않는다.

EVA 공식 native 실행은 복사본에서 기존 scale30/range20·공통 다항식 500/500으로 완료했다.
제안 방법도 독립 선택했다. 두 방법 모두 별도 적용 498입력·1,494키 관측에 판정/오차 위반 0회다.
경계 변화는 EVA 1회·제안 2회(각각 고유 1입력)다. SEAL/Lattigo 보안 가정·packing·일정이
같다고 하지 않으며 속도 우월성을 주장하지 않는다. 과거 S20의 133회와 이번 A를 혼동하지 않는다.

첫 확대는 읽기 전용 재분석만 완료했다. 적용 820사례–입력=2,460키 관측이다.
초기 70입력/201변화, 228입력/675오차이며 선택 후 적용 영역 0·경계 1회다.
실제 최소 최대오차 후보는 4사례 모두 SAFE였다. 최소 오차 방법이 실패한다는 주장은 지지되지 않는다.
Spambase MLP는 선택 11/32·별도 75/256이 적용 영역이다. 학습 자료로 정한 출력 scale과 마진 분포를 분석했다.

FHE-Agent에 관한 이전 활성화 변경 일반화는 정정했다. v1 §4.1/4.3은 고정을 명시한다.
§5.3 차수 변경 문구와 불일치하며, 공식 실행 구현은 미확인이다. 최종 PDF는 수정하지 않았다.

먼저 읽기:
- `docs/research/fg_expand_v2_20260905/RESEARCH_QUESTION_AND_METHOD_KO.md`
- `docs/research/fg_expand_v2_20260905/FIRST_EXPANSION_ADDENDUM_KO.md`
- `docs/research/fg_expand_v2_20260905/RELATED_WORK_CRITERIA_KO.md`
- `docs/research/fg_expand_v2_20260905/FHE_AGENT_CORRECTION_KO.md`
- `docs/research/fg_expand_v2_20260905/EXTERNAL_COMPARISON_KO.md`
- `docs/research/fg_expand_v2_20260905/REPORT_KO.md`

실행/검증:
- `.venv/bin/python scripts/run_fg_expand_v2.py` 는 실제 실행에 사용한 명령이며 새 키 암호화를 포함한다.
  완료된 실행을 다시 시작하지 않는다. 미완료 상태라면 `main_resume02.log` 및 native 프로세스를 먼저 확인하고 중복 시작하지 않는다.
- `.venv/bin/python scripts/analyze_fg_expand_v2.py --check` 는 최종 결과의 읽기 전용 검증이다.
- `.venv/bin/python scripts/analyze_external_fg_expand_v2.py --check`
- `.venv/bin/python scripts/analyze_fg_expand_v1.py --check`

실행 주의: 외부 실행 중첩으로 중단한 Fashion 첫 시도를 `ORCHESTRATION_INCIDENT_01.json`에 보존했다.
완료된 키 증거는 0개다. MAIN_SOURCE_AMENDMENT_01은 직렬 실행 검사, 02는 원시 JSON 필드 읽기를 수정했다.
완료 후보 재실행은 없다. seed 1 source-commit CLI 오타는 원래 model 필드를 보존하고
SOURCE_ID_CORRECTION.json과 실제 trainer hash로 정정했다. 학습 가중치는 수정하지 않았다.

기존 68개·추가 63개·첫 확대 4개·이번 3seed는 프로토콜별로 분리한다. 테스트 통과는 성능/위험 보장이 아니다.
이번 묶음 후 대규모 자동 후속은 없다. GitHub private `hasslelee/deciprotect`에만 기록한다.

## 새 묶음의 확인 결과

- seed 0: 선택 1, 유한 8; 별도 10000/10,000, 적용 9999, 판정 변화 0, 오차 위반 0, 경계 변화 0.
  평문 test 정답률 87.66%, class 6 재현율 72.7%. 이 분류 약점을 CKKS 판정 일치로 해결했다고 하지 않는다.
- seed 1: 선택 1, 유한 8; 별도 10000/10,000, 적용 9999, 판정 변화 0, 오차 위반 0, 경계 변화 0.
  평문 test 정답률 87.62%, class 6 재현율 57.2%. 이 분류 약점을 CKKS 판정 일치로 해결했다고 하지 않는다.
- seed 2: 선택 1, 유한 8; 별도 10000/10,000, 적용 10000, 판정 변화 0, 오차 위반 0, 경계 변화 0.
  평문 test 정답률 87.88%, class 6 재현율 59.0%. 이 분류 약점을 CKKS 판정 일치로 해결했다고 하지 않는다.

평가한 유한 후보에서 수치 기준과 제안 기준의 수용 집합은 같았다. 수용 조건 차이에 따른 개선은 관측되지 않았다. 같은 구성의 시간 차이를 선택 효과나 성능 우월성으로 해석하지 않는다.
