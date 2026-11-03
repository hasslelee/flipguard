# 기존 판정 일치 기반 구성 선택 연구 인계

최신 사용자 결정은 최종 검수한 논문지 PDF의 방법을 확대 검증하는 것이다.
DeciProtect는 작업 폴더·저장소 이름이다. 재계산 queue·유보 정책·새 위험 보장을
현재 연구의 핵심이나 선행 과제로 삼지 않는다. 완료한 과거 결과는 보존한다.

- 작업: `/home/ckks2/deciprotect`; 원본 FlipGuard 코드/인터프리터 실행 금지.
- GitHub: https://github.com/hasslelee/deciprotect (private).
- 기준: `baseline/journal_final_20260905.pdf`, SHA-256
  `0210899a12ff1025db358e1812159ca4af2b5c6095a79e2b7b19200d7e9f3b85`.
  사용자 Downloads 지정·기존 복사 기록·동결 manifest와 연결하여 확인했다.
- 상태: **FIRST_EXPANSION_COMPLETED_EXPLORATORY**. Protocol `FG_EXPAND_V1_20260905`, run `fg_expand_v1_20260905_run01`.
- 자동 후속 실행은 꺼져 있다. 종료 후 새 대규모 실험을 시작하지 않는다.

방법은 입력별 판정·오차 조건을 이용한 오프라인 구성 선택이다.
rho=.5, delta=.001, 최대4후보, 기존 조정·128bit Q/QP 보안 정책을 유지한다.
선택자는 평문 기준 점수를 읽는다. 운영 중 oracle gate로 혼동하지 않는다.
구성 선택·유한 탐색·키 준비와 PDF 정의의 추론 비용을 분리한다.

첫 묶음: Spambase/HTRU2 × 기존 다항식/MLP4 네 사례, 사례마다 선택32·별도256입력·
3개 새 키. 같은 데이터의 두 모델은 같은 입력이므로 별도1,024 사례–입력 쌍과
고유512입력을 구분한다. Spambase는 노출된 자료이며 확증 실험으로 표현하지 않는다.

기존 자산: 주요68 + 추가모델63 + 별도 깊이5조건. 다중 클래스·CNN·학습 seed 반복은
이미 있다. PDF7쪽 §5.1의 63개 표현과 원시 분류 차이는 별도 보고했으며 PDF나 동결
표를 수정하지 않았다. 기존 68개 결과를 덮어쓰지 않는다.

먼저 읽을 자료:

- `docs/research/fg_expand_v1_20260905/PDF_METHOD_MAP_KO.md`
- `docs/research/fg_expand_v1_20260905/LEGACY_ASSETS_KO.md`, `LEGACY_CASES.csv`
- `docs/research/fg_expand_v1_20260905/RELATED_WORK_KO.md`
- `docs/research/fg_expand_v1_20260905/DECISIONS_AND_MATRIX_KO.md`
- `docs/research/fg_expand_v1_20260905/REPORT_KO.md` (완료 시 최종 결과)
- `docs/research/THESIS_ROADMAP.md`

과거 DP 파일럿·IID600회·gap·stress·DP-03는 해당 protocol의 역사적 결과다.
위험 상한이나 비용 정의를 이전하지 않는다. 당시 모의심사 점수는 과거 기록이며
현재 점수를 올리거나 졸업논문 완성을 선언하지 않았다.

보존: baseline·archive·원본·완료 evidence 불변, archive 업로드/전수 재해시 금지.
새 protocol/run ID 사용. 불리한 결과·실행 실패·제외 입력 유지. 제출 PDF 수정이나
삭제된 수식/의사코드/용어 자동 복원 없음. 기존 archive 복구 경위는
`docs/review/SOURCE_STATE_RESOLUTION.json`에 보존되어 있으며 이번에 반복하지 않았다.

## 첫 묶음의 실제 결과

- spambase__linear_poly3__split0_seed0: 선택 2 / 유한 8, 별도 적용 235/256, 판정 변화 0, 오차 위반 0, 경계 판정 변화 1; 선택 비용 28.133s.
- htru2__linear_poly3__split0_seed0: 선택 2 / 유한 8, 별도 적용 256/256, 판정 변화 0, 오차 위반 0, 경계 판정 변화 0; 선택 비용 17.992s.
- spambase__mlp_square_linear_score__split0_seed0: 선택 1 / 유한 8, 별도 적용 75/256, 판정 변화 0, 오차 위반 0, 경계 판정 변화 0; 선택 비용 17.347s.
- htru2__mlp_square_linear_score__split0_seed0: 선택 1 / 유한 8, 별도 적용 254/256, 판정 변화 0, 오차 위반 0, 경계 판정 변화 0; 선택 비용 11.633s.

원시 점수로 재계산: `.venv/bin/python scripts/analyze_fg_expand_v1.py --check`.
