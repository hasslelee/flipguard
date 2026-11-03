# 두 번째 확대의 질문과 사전 결정

이번 질문은 기존 수치 정확성 기준과 비교하여 **입력별 판정 일치와 마진에 연결된 오차 조건을 구성 선택에 반영하면 구성·별도 입력 판정·비용이 어떻게 달라지는가**이다. 더 많은 입력의 성공률만으로 기여를 입증하지 않는다. 동일·악화·미선택도 결과다.

기준 PDF SHA-256은 `0210899a12ff1025db358e1812159ca4af2b5c6095a79e2b7b19200d7e9f3b85`로 기존 출처 기록 및 checkpoint `b64fa9c100f4f13789e3012a8e2258a48034f5d0`와 일치했다. 4쪽 §2.3·식(4), §2.4, §3.1의 실제 PDF 렌더와 본문을 확인했고, 5–9쪽 선택·별도 평가·유한 비교·시간 정의, 10쪽 §5.7 외부 비교를 기존 방법 대응 문서와 대조했다. PDF와 완료 문서는 수정하지 않았다.

| 제안 | 결정과 이유 |
|---|---|
| Fashion-MNIST | 공식 네 IDX gzip의 제공 MD5 및 취득 SHA-256 확인. 새로운 영상 분포 한 개의 확대이며 침입 탐지 적용 증거는 아님. |
| 784→100→10 제곱 MLP | 원래 Go 학습·Adam·평문·CKKS 연산 그대로 재사용. 데이터 및 모델 식별과 입력 출처 연결만 확장. |
| seed 0/1/2 | 모두 실행. 같은 train 역할 분할, 같은 선택·test 입력. 세 데이터셋·세 구조가 아니라 한 구조의 세 학습 사례. |
| 학습·개발·선택 | 공식 train에서 54,500/5,000/500으로 분리. 클래스별 SHA-256 순위로 개발500·선택50, 나머지 학습. 픽셀/255 외 전처리·출력 정규화 없음. |
| 별도 1,000 제안 | 10,000 전체로 수정. 기존500-slot 배치20개. 개발 CKKS 약18.2초/배치, 기존 동형 구조18.6초/배치를 근거로 예상2–4시간·상한6시간. test 판정 결과를 보기 전에 결정. |
| 배치 키 | 후보·배치마다 새 키3개. 배치 사이 키 재사용 없음. 한 후보20배치에는60문맥이며 각 입력3관측. 세 전역 키로 모든10,000을 재실행한 실험이 아님. |
| 비교 집합 | 원래 V17 다중 클래스 exhaustive가 호출하는 `BuildV17DepthCompleteFiniteSet`. 생성 후 실제 수를 기록. 단순히 표형의8개를 강제하지 않음. |
| 시간 | 최종 V17의 `RunV17PrimaryPairedLatencyKeyset`: 고정20입력 배치, 예열1·측정6·키3. 더 오래된 별도 단일 이미지 MLP 시간 경로와 혼합하지 않음. |
| 최소 오차 | 기존 유한 최소 최대오차 진단 재사용. 선택 결과와 제안 수용 여부를 기록하며 그 역할만을 위한 별도10,000 감사는 추가하지 않음. |
| 외부 | EVA 공식 기존 빌드와 공통 다항식으로 실제 실행. Fashion 그래프의 새 EVA lowering 개발은 이번 필수 과제로 만들지 않음. |

개발 정답률은 seed별 88.82%, 88.50%, 88.24%이고 모든 출력은 유한했다. 원래 8epoch를 채운 사실은 수렴 보증이 아니다. 개발 클래스별 recall·혼동행렬·마진, epoch별 손실은 원시에 있다. Python 행렬 계산과 원래 Go 평문 출력도 개발5,000개에서 대조했다. 최종 시험 입력을 학습 중단·모델 교체·정밀도 조정에 사용하지 않았다.

## 비교군이 답하는 서로 다른 질문

초기 구성은 판정 검사와 입력별 오차 검사를 함께 제외한 해석이다. **초기 합성에는 마진이 남아 있다.** 공통 유한 후보 역시 그 초기 합성과 조정에서 파생하므로 아래 수치 비교군도 완전히 판정 정보를 쓰지 않는 전체 선택법은 아니다. 이 통제 비교는 같은 후보 범위 안의 **수용 기준 차이**를 측정한다.

유한 최속 실행은 수치/판정 조건을 무시할 수 있다. 유한 최속 수용은 이미 제안 조건을 통과한 후보 중 최속이므로 선택 효율의 기준이다. 전역 최적성이나 외부 연구 대비 성능의 증거는 아니다.

새 수치 대조군은 개발 출력의 FP16 반올림 오차를 정밀도 예산으로 삼는다. 이는 특정 논문의 완전한 재현이나 검증된 응용 허용 오차가 아닌 **명시적 대표 수치 기준**이다. 개발 원래 logits를 binary16으로 반올림한 뒤 float64로 되돌린 차이에서 (a) 전체 출력 RMSE, (b) 최대 절대오차를 각각 고정한다. 후보는 선택500입력의 세 키 각각에서 해당 조건을 통과해야 한다. 허용값 산출에는 정답 레이블·마진·CKKS 출력·test 출력이 들어가지 않는다. 모델 출력 자체를 FP16으로 바꾸지 않는다.

HECATE의 `2^-8`을 단위가 다른 Fashion logits에 복사하거나, 판정 변화가 생기도록 허용값을 조정하지 않았다. FP16은 계산 정밀도와 비교하기 위한 개발 자료 기반 공학적 기준이며, 다른 정밀도 예산에서도 결론이 같다는 주장은 남아 있다. 이번에는 결과에 맞춰 예산을 추가·변경하지 않는다.

| seed | 고정 RMSE 한도 | 고정 최대 절대오차 한도 |
|---|---:|---:|
| 0 | 0.0028724034277539836 | 0.027530070390810124 |
| 1 | 0.0026124242411956584 | 0.029613854530992967 |
| 2 | 0.0026951232116630055 | 0.026194294078862868 |

수치 비교군의 후보 선택은 **전체 유한 후보 평가 후** 해당 기준을 통과한 최소 관측 시간 후보를 고르는 사후 유한 분석이다. 제안 절차의 최대4회 온라인 선택과 같은 예산으로 실행했다고 하지 않는다. 실제 원래 조건 통과, 제안 조건 통과, 적용/경계 입력 판정은 각각 보고한다.

## 실제 함수와 호출 경로

경로 접두사는 `research/fashion_extension/`이다. `SOURCE_COPY_BINDING.json`은 기존 복사본의 274개 internal 파일과 Go module을 결속하고 `MAIN_SOURCE_LOCK.json` 및 명시적 수정 기록은 실행 바이트를 결속한다.

- `cmd/fashion-train/main.go`는 공식 train IDX만 읽어 `internal/journalmnist/mlp.go::TrainMLP`와 `optimizer.go`를 호출한다. 원래8epoch·batch64·학습률.001×.9^(epoch−1)·Adam·norm cap5·L2=1e-5를 바꾸지 않는다. `MLPModel.Logits`는 제곱 활성화 후10 logits를 반환한다.
- `cmd/fashion-case/main.go --mode plan` → `multiclass_contract.go::BuildJournalMNISTMulticlassContract` → 원래 `Synthesize` 및 `BuildV17DepthCompleteFiniteSet`. 데이터/모델의 Fashion 식별과 출처 명칭을 추가했고 식(4)·보안·합성·조정 함수를 바꾸지 않았다.
- `--mode direct`는 원래 `RunAdaptiveJournalMNISTMulticlassAutotune`의 최초 SAFE/최대4회/FailureSignal별 `RepairCandidate` 루프를 명령층에서 그대로 따르며 `ExecuteJournalMNISTMulticlassCandidateWithOptions`의 키별 callback으로 원시 점수를 저장한다. 실행된 후보와 수정 이력으로 루프를 재검증한다.
- 실제 HE: `multiclass_executor.go` → `ckksbackend.NewContextFromProfile` → `RunCKKSJournalMNISTMulticlassInference` → `encryptMNISTFeatureVectors` → `evaluateMNISTMLP` → `weightedCipherSum`/`squareAndRescale` → `decryptRealSlots`.
- `certify/multiclass_decision_contract.go::AggregateObservedMulticlassCandidate`는 최상위 평문 클래스와 **모든 경쟁 클래스** 사이의 오차합/점수차를 검사한다. 동일 점수는 가장 낮은 클래스 index를 선택하며, top-two gap≤.001 또는 동점은 적용 영역 밖이다. 판정이 같아도 rho=.5 여유 조건을 위반할 수 있다.
- 감사는 선택 저장 후 모델·후보 바이트를 고정하고, 배치마다 기존 계약을 만들되 계획용 calibration은 선택 계약 값을 유지한다. 감사에서 합성·조정을 호출하지 않는다. batch500의 원래 CSV 검증 규칙도 유지한다.
- 시간은 `ckksbackend/v17_primary_paired_latency.go::RunV17PrimaryPairedLatencyKeyset` → `runV17JournalMNISTBatch`다. 키 준비는 별도, 인코딩·암호화/동형 연산/복호화·디코딩을 기록한다. 배치 시간과20입력당 환산 시간은 별개다. 로컬 프로세스가 client/server 역할을 함께 수행하며 네트워크·큐 비용은 미측정이다.

모든 구성·모델·원시 점수는 protocol별로 분리한다. 68개 주요 결과, 추가63개, 첫 확대4개, 이번3seed의 분모와 시간을 무조건 합치지 않는다. 검증기 통과는 성능 향상이나 미래 입력의 판정 보장이 아니다.

### 시간 필드의 실제 경계

원래 정확성 실행의 `RunCKKSJournalMNISTMulticlassInference`는 모델·CSV를 읽은 뒤 `totalStart`를 시작한다. `total_ms`에는 키 준비와 인코딩·암호화, 동형 계산, 복호화·디코딩뿐 아니라 GC와 원시 점수 기록을 위한 평문 참조 계산도 들어 있다. 모델/CSV 로딩, 바깥쪽 인증 집계와 JSON 저장은 명령 wall time에서만 포함된다. 따라서 `total_ms`를 순수 서버 동형 연산 시간이나 실제 서비스 전체 지연시간으로 쓰지 않는다.

최종 V17 paired 실행은 `RunV17PrimaryPairedLatencyKeyset`가 각 arm의 파라미터·키 준비를 `setup_keygen_ms`에 별도 기록한다. 그 뒤 `runV17JournalMNISTBatch`의 `total_ms`는 두 arm 모두 키 준비를 제외하며, 인코딩/암호화·동형 연산·복호화/디코딩 외 평문 참조와 GC 등 원래 harness 잔여 시간도 포함한다. 분해 항목 합과 total의 차이는 '미분리 harness 잔여'로 보고하고 gate나 통신으로 임의 귀속하지 않는다. `evaluation_only_ms`가 동형 계산 구간이다. 로컬 전체 명령 시간·준비 시간·배치 추론 시간의 분모를 섞지 않는다.
