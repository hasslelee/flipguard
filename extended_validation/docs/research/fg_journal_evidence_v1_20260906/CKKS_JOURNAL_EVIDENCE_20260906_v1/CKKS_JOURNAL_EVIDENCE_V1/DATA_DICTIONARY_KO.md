# 집계표와 계산 규칙

CSV의 수치·식별자 원본은 각 행의 source/raw_source/label_source/model_source 및 SHA/JSON pointer에 연결된다. SHA가 행에 없으면 provenance의 READ_BINDINGS 세 파일에서 그 정확한 경로를 찾는다. 새 숫자를 산출한 함수는 reproduction_scripts에 실제 포함했다. source_excerpts의 복사·발췌 내역은 evidence_tables/SOURCE_COPY_MANIFEST.json과 최상위 MANIFEST.json에 있다.

| Table group | Fields and calculation |
| --- | --- |
| CANDIDATE_SPECIFICATIONS | 전체 저장 parameters와 path를 canonical JSON으로 묶어 SHA. 실제 trial별 전체 입력 ledger, key index별 관측. 이진 margin>0.001, abs error>=0.5margin이면 위반. 다중 클래스는 모든 경쟁자의 두 실제 절대오차 합/(0.5×평문 점수차)의 최댓값>=1이면 위반. 실제 argmax 변화와 구분. |
| CANDIDATE_COUNT / ID_LITERAL_RECONCILIATION | 실제 실행 가능한 모든 finite 후보 중 mean_total_ms 최솟값과 SAFE 중 최솟값. 동률은 원래 trial_index 순. ID와 전체 parameters/path의 일치를 각각 계산. |
| CASE_SCOPE_AND_QUALITY | 선택된 후보의 입력 ID 중복 제거, 모든 키에서 같은 평문인지 검증. 전체/적용/경계 입력 및 키 관측, 전체 출력 범위, 전체 최대오차, 적용 영역 최대 예산 사용률. 경계 판정 변화는 따로 집계. |
| MODEL_QUALITY_BY_ROLE | 정답–예측 confusion의 대각합/n. balanced accuracy는 실제 클래스별 recall 평균, macroF1은 클래스별 F1 평균. 키 관측을 중복하지 않음. training65는 동결 모델 평문 산술, 나머지는 저장 출력. |
| MODEL_TASK_AND_TRAINING / MODEL_METADATA | 저장 모델 구조·학습·전처리 metadata와 SHA. 없는 종료·수렴 판단을 만들어 넣지 않음. MC의 online epoch metric은 최종 모델 train 정확도로 대체하지 않음. |
| ADDITIONAL_63_* | 원래 추가 그룹 30+24+6+3, 선택/별도126행. 주요68과 분리. 원래 출력/레이블 및 모델 SHA 연결. |
| MODEL_SUMMARY | 동일 dataset/model의 별도 역할을 합계. 정답률·적용비율·사례별 시간 중앙값의 범위. 서로 다른 분할의 정답률을 단일 독립 실험으로 합하지 않음. |
| INPUT_UNITS | dataset/role 내부 고유 source ID 수. 모델/분할/키/슬롯 반복과 구분하며 다른 MNIST export 사이의 전역 독립성은 주장하지 않음. |
| TIMING_BY_CASE | keyset/measurement_run/row(또는batch)를 대응시킨 finite/direct 기하평균. 절대시간은 전체 해당 arm 기록의 중앙값. 조정 전후는 별도 선택 단계 mean_total_ms 비율. |
| COST_COMPONENTS_AND_SETUP | 실제 기록된 성분별 평균, 총시간 평균/중앙값, 키 문맥당 준비비 평균. 총시간에서 성분 합을 뺀 잔여는 특정 원인으로 배정하지 않음. setup은 추론 total 밖. network·별도gate는 미측정. |
| SYNTHESIS / WORKED_EXAMPLE | 원래 contract·policy·literal·trial 재사용. 고정모델/선택 입력으로 노드 구간을 복원하고 민감도·ceil 정밀도만 평문 산술로 확인. actual primes 생성 없음. |
| SECURITY_CHECK_SCOPE | 기존 reconciliation의 후보 ID+literal을 주요 선택2후보와 직접 연결. 기존 실제Q/QP·estimator 결과만 재사용. |
| EXISTING_FULL_TEST_PLAINTEXT_QUALITY | 저장된10,000평문 결과. source_sha256은 이번 집계에서 읽은 quality.json의 파일 SHA이며 원래 데이터셋 SHA와 다름. 원래 필드를 보존한 두 사본도 source_excerpts/EXISTING_FULL_TEST_*.json에 제공. |
| PATCH_ANCHORS | 최종 PDF 기존 page text의 공백 제거 문자열과 앞/대상/뒤 발췌 대조. 조판용 쪽 번호이며 새 PDF를 생성하지 않음. |
| COMPARISON_EVIDENCE_SCOPE | 원래PDF/완료후속/문헌 확인을 구분한 기존 기록 전사. 이번 새 비교나 성능 실험이 아님. |

생성되지 않은 후보와 누락된 timing은 0행으로 위장하지 않는다. 원래 run_manifest의 시작 상태와 최종 run_status의 완료 목록은 시점이 다른 기록이다. 통계 신뢰구간은 기존 검증치를 재사용했고 이번에는 대응 추정치와 총계를 검증했다.
