# DP-03 첫 단계: 재계산 비용 구조 진단

2026-09-05. Protocol `DP03_COST_DIAG_V1`, run `dp03_cost_diag_v1_20260905`.

**현재 packing에서는 재계산 행 수가 줄어도 비어 있지 않은 고정밀도 배치의 암호화·동형연산 비용은 거의 줄지 않았다.**
842행을 한 배치로 처리한 두 단계 경로는 고정 고정밀도보다 느렸다. 128행 단위에서는
고정밀도 배치 생략으로 관측 비용이 감소했지만, 842행 고정 고정밀도의 총비용보다 훨씬 컸다.
클라이언트가 고정밀도 암호화 전에 요청을 모으는 작은 실험에는 근거가 있다.
현재 서로 다른 키로 생성된 암호문을 합치는 기능이나 실서비스 성능 개선은 입증하지 않았다.

## 범위와 사전 고정

기존 `CHATGPT_HANDOFF.md`, `THESIS_ROADMAP.md`, `INITIAL_RESULTS.md`, `RESEARCH_STATE.json`,
`THEORY_AND_SYSTEM.md`와 실행 소스를 확인했다. 기존 비용 모형은
`C_low + [1-(1-p)^b] C_high`였으며 batch 후보와 정식 비교 원칙은 있었다.
그러나 별도의 완료된 DP-03 protocol이나 수치 실행예산은 없었다. 로드맵의
“모형·실험 규격 작성”을 정식 사전등록 완료로 해석하지 않았다.

Spambase linear의 기존 세 모델 seed `20260905/20260906/20260907`, 각 842개 test 입력과
원래 순서, 분할, 전처리된 입력, 모델, radius, 판정 정책을 유지했다. 새 학습·보정은 없다.
기존 세 key 반복을 모두 사용하고, 원래 842행 배치와 로드맵 후보 하나인 128행을 비교했다.
128행 조건에는 마지막 74행을 남겼다. 결과를 보고 seed나 반복을 선택하지 않았다.

새 protocol을 측정 전에 고정했다. 72개 model/repeat/batch/chunk block의 순서를 seed
`2026090503`으로 섞고 6가지 arm 순열을 순환했다. 각 arm은 실행 위치 0/1/2에 각각 24회였다.
216개 arm 시행, 최대 288개 native 호출, 호출당 120초, 전체 900초, 측정 재시도 0회였다.
실제 216개 시행·247개 호출을 56.14초에 완료했다. 불리한 시간이나 시행을 삭제하지 않았다.
실제 호출은 새 독립 키를 생성한다. 반복 번호는 키를 공유한다는 뜻이 아니다.

이는 **탐색적 비용 진단**이다. 검정력 설계, 유의성 검정, 신뢰구간, p95/p99 서비스 주장,
새 위험 합격선은 없다. 세 모델과 반복 입력은 독립 모집단 표본이 아니다. 기존 600회 감사의
위험 상한을 이번 packed batch에 적용하지 않았다. 최종 유보가 없다는 관측도 위험 보장이 아니다.

## 실제 호출과 역할

| Path | File / function | Actual role and boundary |
|---|---|---|
| Historical cascade | `scripts/run_pilot_v1a.py::run_case`, `encrypted` | low CKKS → client interval gate → `z[test_idx[pending]]` → fresh high CKKS → gate |
| Diagnostic orchestration | `scripts/run_cost_diagnostic.py::main/invoke` | frozen client features/model/lock load; three-arm schedule; request JSON; local Go child process |
| Runtime decisions | `src/deciprotect/cost_diagnostic.py::execute_arm`; `decision.py::interval_gate` | only decrypted CKKS logits and frozen radius; no reference logits or labels |
| Client retry | `execute_arm`, `retry_inputs = x[pending]` | client gathers retained original model-space features; fresh high encoding and encryption |
| Parameters | `cmd/deciprotect-ckks/main.go::parametersForRequest` | unchanged parameter selection and declared QP envelope |
| Native local harness | `cost_diagnostic.go::runDiagnostic` | parameter/key setup, client encode/encrypt, server evaluator, client decrypt/decode |
| Server evaluator | `main.go::evaluateWithCost` | parameters, public model constants, input ciphertexts, evaluation keys; no original features, secret key, oracle or labels |
| Independent audit | `scripts/verify_cost_diagnostic.py::verify/binary_gate` | only after measurement loads frozen reference logits/labels and recomputes all events |

Python 실행기와 Go 자식 프로세스가 하나의 로컬 실험 장치에서 클라이언트·서버 역할을 대신한다.
Go 요청에 원래 특징이 들어가는 이유는 Go가 **클라이언트** 암호화도 수행하기 때문이다.
이를 원격 서버에 평문을 보내는 운영 API로 인정하지 않는다. 운영 설계에서 서버가 원래 특징을
받아 재포장해서는 안 된다. 네트워크 전송, 원격 클라이언트, 여러 소유자, 상주 키 서비스,
암호화 배치 병합, 운영 큐는 구현되어 있지 않다.

고정밀도 경로는 원래 클라이언트 특징에서 출발하여 새 고정밀도 파라미터와 키를 만들고
Encode/Encrypt를 다시 수행한다. 저정밀도 암호문의 scale을 바꾸는 방식이 아니다.
두 경로는 서로 다른 환·파라미터와 독립 키를 쓴다. 모델 상수는 평가자에게 평문으로 주어지며,
모델 기밀성과 악의적 서버의 계산 검증은 이 구현의 범위에 포함되지 않는다.

운영 스크립트는 출처 결속을 위해 `plaintext.json`의 해시만 계산하고 점수·레이블을 읽지 않는다.
무조건 반환 대조군의 `reference_decision` 인자는 복호화된 **고정밀도 CKKS** logit이다.
함수 이름이 oracle 사용을 뜻하지 않는다. 실제 평문 기준은 측정 이후 감사에서만 읽었다.

## Parameters, keys and packing

| Property | Low | High |
|---|---:|---:|
| log2 scale / logN | 18 / 12 | 30 / 13 |
| Nominal Q bits; P bits | [28,18]; [40] | [40,30]; [40] |
| Slots per ciphertext | 2,048 | 4,096 |
| Input / output ciphertexts per nonempty batch | 57 / 1 | 57 / 1 |
| Input ciphertext BinarySize sum, bytes | 7,490,142 | 14,961,246 |
| Output ciphertext BinarySize, bytes | 65,854 | 131,390 |
| Public / evaluation key BinarySize, bytes | 196,696 / 393,430 | 393,304 / 786,646 |

실제 Q/P 정수, 비밀키·오차 분포, 파라미터 식별자는 `native/*.json`에 기록하고 호출마다
동결된 부모 출력과 대조했다. 모든 대조군은 동일한 고정밀도 구성과 기존 보안 허용 범위를
사용한다. 새로운 독립 보안 추정은 수행하지 않았다. 고정밀도 파라미터 식별자는
`5044fc159777c9afdf7cb43dbd3efc9e618bb764ba4fbd734d3450ff9cfa49a4`;
저정밀도 식별자는 `7304c5323393c29650804c5165ba301219a9aefae7b184b9d476a2fddf0b3ed7`이다.
기록된 공개키 식별자 247개는 모두 다르다. 이는 생성한 공개키에 대한 관측용 해시이며
비밀키는 저장하지 않았다. 서로 다른 키 사이의 호환성을 추정하지 않는다.

특징별 packing으로 각 특징이 암호문 하나, 각 행이 slot 하나를 사용하고 나머지는 0으로 채운다.
유효 행 수가 k일 때 실제 특징 값은 `57k`개이지만 할당된 값의 수는 `57 × slots`로 유지된다.
비어 있지 않은 선형 호출은 가중치 평문 인코딩 57회, 암호문·평문 곱 57회, 암호문 덧셈 56회,
rescale 1회, bias 덧셈 1회를 수행한다. 회전이나 암호문·암호문 곱은 없다. 그럼에도 기존
실행기는 relinearization key를 생성한다. 이번에는 모든 대조군에 그 비용을 포함하여 유지했다.

k 감소에 따라 클라이언트의 행 수집·복사, 실제 입력 JSON 크기, 반환 행 복사가 줄어든다.
이 구현에서는 암호문 수, 전체 slot 인코딩·암호화, 가중치 인코딩, 동형연산 횟수,
전체 slot 출력 디코딩은 줄지 않는다. BinarySize는 크기 계산이며 실제 암호문 전송을 위한
직렬화나 네트워크 전송을 측정한 값이 아니다.

## Measured costs

아래 값에는 동일한 초기 파라미터·키·문맥 생성 비용을 포함한다. 기존 `run()`은 반복별
TotalMS 바깥에서 파라미터를 한 번 생성했다. 이번에는 단일 키 호출마다 새로 생성하고 모든
대조군에서 명시적으로 측정했다. 따라서 과거 시간 필드와 이번 총시간을 전후 성능 개선으로
비교해서는 안 된다.

각 표 셀에는 3모델 × 3반복 × 842행, 총 7,578개 행 관측이 있다. “842행당 평균”은 셀 총시간을
완전한 모델·반복 묶음 9개로 나눈 값이다. 128행 조건은 7개 조각의 시간을 모두 합산한다.
이는 128행 호출 하나의 시간이 아니며 IID 추정량으로 제시하지 않는다.

| Batch condition | Arm | Native total (ms) | Local total (ms) | Mean native / 842 (ms) | Mean local / 842 (ms) |
|---|---|---:|---:|---:|---:|
| 842 | Fixed high | 1,904.44 | 2,873.48 | 211.60 | 319.28 |
| 842 | Fixed high + gate | 1,892.94 | 2,869.91 | 210.33 | 318.88 |
| 842 | Two stage | 2,825.25 | 4,037.39 | 313.92 | 448.60 |
| 128 (+74 tail) | Fixed high | 13,258.12 | 15,966.53 | 1,473.12 | 1,774.06 |
| 128 (+74 tail) | Fixed high + gate | 13,248.50 | 16,310.26 | 1,472.06 | 1,812.25 |
| 128 (+74 tail) | Two stage | 11,189.12 | 13,016.26 | 1,243.24 | 1,446.25 |

Native는 Go 내부 계측 호출 시간이다. Local은 Python 제어, 실제 JSON 파일 입출력,
자식 프로세스 시작·종료 감지 및 관측 기록 처리를 포함한다. 동결 모델·전처리 입력의 최초
로딩, 빌드, 보고서 생성과 사후 감사는 시행 시간 밖에 있다.
**어느 총시간도 실서비스 종단 지연시간이 아니다.** 네트워크, 전송용 암호문 직렬화,
큐 대기는 미측정(`null`)이며 0으로 처리하지 않았다.

비용 분해 역시 9개 묶음으로 평균한 842행당 실제 밀리초이다.

| Component | 842 high | 842 high+gate | 842 two stage | 128 high | 128 high+gate | 128 two stage |
|---|---:|---:|---:|---:|---:|---:|
| Parameter/key/client-server context setup | 11.776 | 11.401 | 18.463 | 74.724 | 74.604 | 77.053 |
| Client packing / plaintext allocation | 1.434 | 1.408 | 2.145 | 8.757 | 8.676 | 9.812 |
| Client Encode | 29.301 | 29.450 | 42.337 | 203.503 | 202.955 | 163.770 |
| Client Encrypt | 136.544 | 136.766 | 204.087 | 964.513 | 965.102 | 804.216 |
| Server weight preparation / Encode | 20.618 | 20.074 | 29.357 | 141.962 | 140.690 | 114.898 |
| HE operators | 10.820 | 10.246 | 16.003 | 73.355 | 73.598 | 62.025 |
| Decrypt / Decode / output scatter / gate | 0.689 | 0.605 | 0.924 | 3.009 | 3.420 | 3.377 |
| Client retry selection / materialization | 0 | 0 | 0.036 | 0 | 0 | 0.156 |
| Observer parameter/key identity | 0.427 | 0.433 | 0.591 | 2.369 | 2.298 | 7.560 |
| Native unassigned remainder | 0.216 | 0.200 | 0.366 | 1.525 | 1.616 | 1.577 |
| Actual input/output JSON file I/O | 44.412 | 43.773 | 45.330 | 47.839 | 47.363 | 47.487 |
| Subprocess wall outside native call | 57.727 | 59.265 | 83.112 | 244.390 | 283.490 | 145.060 |
| Client/harness unassigned remainder | 5.311 | 5.259 | 5.847 | 8.112 | 8.441 | 9.262 |

두 미분해 잔여 비용을 그대로 남겼다. Native 바깥 자식 프로세스 시간은 Go CLI의 JSON
읽기·쓰기, 프로세스 시작·종료와 Python timeout 대기 polling을 포함하며 각각 분리 측정하지
않았다. 이 Python 3.12 호스트의 `subprocess.Popen._wait`는 최대 50ms 간격의 sleep을 쓴다.
따라서 이 차이를 모두 유효 계산, gate 또는 네트워크 지연으로 해석할 수 없다.
타이머·카운터 오버헤드를 보정하여 빼지 않았으며 큰 관측용 식별자 처리 시간을 포함한
모든 원시 시간을 보존했다.

호스트는 CPU 6개이며, 기록된 1분 load average는 0.763–1.082였다. 시행 전후 `/proc/stat`
차분의 호스트 busy 비율은 0.104–0.250이었다. 이는 프로세스 전용 CPU 시간이나 격리 실행의
증거가 아니다. `GOMAXPROCS=4`, `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`을 사용했다.
독립 장비 검증이나 CPU 주파수 통제 실험은 하지 않았다.

## Retry and final disposition

| Batch | Arm | Low returned | Retry requested / executed rows | High batches started / completed | High valid rows | High returned | Final abstain | Execution failure | Accepted CKKS disagreement | Accepted label error |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 842 | Fixed high | 0 | 0 / 0 | 9 / 9 | 7,578 | 7,578 | 0 | 0 | 0 | 510 |
| 842 | Fixed high + gate | 0 | 0 / 0 | 9 / 9 | 7,578 | 7,578 | 0 | 0 | 0 | 510 |
| 842 | Two stage | 7,548 | 30 / 30 | 9 / 9 | 30 | 30 | 0 | 0 | 0 | 510 |
| 128 | Fixed high | 0 | 0 / 0 | 63 / 63 | 7,578 | 7,578 | 0 | 0 | 0 | 510 |
| 128 | Fixed high + gate | 0 | 0 / 0 | 63 / 63 | 7,578 | 7,578 | 0 | 0 | 0 | 510 |
| 128 | Two stage | 7,548 | 30 / 30 | 22 / 22 | 30 | 30 | 0 | 0 | 0 | 510 |

6개 셀 모두 7,578/7,578개 관측을 반환했다. 두 단계 조건 각각의 입력 재계산율은
`30/7578 = 0.395883%`이고 최종 유보율은 0%이다. 두 값은 다른 양이다. 고정 고정밀도 호출은
최초 실행이며 재계산으로 세지 않는다. 반환 판정 불일치는 동결 평문 모델과 비교하고,
레이블 오류는 데이터 정답과 비교한다. 불일치 0회가 모델 정확성까지 뜻하지 않는다.
45,468개 행과 두 오류의 구분은 `requests.csv`에 있으며 독립 위험 시행 45,468개로 세지 않는다.
두 조건의 재계산 총행 수는 우연히 같지만 새 키와 packing이 다르므로 seed·반복별 수와
대상은 다르다. 입력별 이력을 모두 남겼다.

842행 조건의 고정밀도 재계산 유효 입력은 1/2/3/4/5행이 각각 1/1/2/4/1개 호출이었다.
128행 조건에서는 1행 호출 14개, 2행 호출 8개였다. 즉 재계산 입력 30행이 고정밀도 배치
22개를 유발했다. 각 배치는 여전히 암호문 57개와 암호문당 물리 slot 4,096개를 사용했다.
호출별 유효 행 수와 식별자는 `native_calls.csv`에 있다.

## Cost diagnosis and the queue decision

| Native call type | Calls | Mean native (ms) | Mean client Encode (ms) | Mean client Encrypt (ms) | Mean weight preparation (ms) | Mean HE (ms) |
|---|---:|---:|---:|---:|---:|---:|
| High, 842 valid rows, fixed arm | 9 | 211.60 | 29.30 | 136.54 | 20.62 | 10.82 |
| High fallback, 1–5 valid rows, 842 source | 9 | 207.93 | 27.92 | 137.40 | 19.56 | 10.45 |
| High, 74/128 valid rows, fixed arm | 63 | 210.45 | 29.07 | 137.79 | 20.28 | 10.48 |
| High fallback, 1–2 valid rows, 128 source | 22 | 208.32 | 27.53 | 137.74 | 19.68 | 10.34 |
| Low, 842 valid rows | 9 | 105.98 | 14.42 | 66.69 | 9.80 | 5.55 |
| Low, 74/128 valid rows | 63 | 104.86 | 13.78 | 66.79 | 9.54 | 5.25 |

반복 비용 중 클라이언트 암호화가 가장 크고 입력 인코딩과 서버 모델 준비가 그 뒤를 잇는다.
순수 동형연산은 더 작은 부분이다. 몇 행만 재계산해도 거의 한 번의 고정밀도 호출 비용을
지불한다. 842행 두 단계 방식은 저정밀도 105.98ms를 추가한 뒤 모든 시행에서 고정밀도
207.93ms를 다시 지불했다. 고정 고정밀도 대비 native 추가 비용은 842행당 102.31ms였다.
주요 원인은 저정밀도 선행 실행과 생략하지 못한 고정밀도 배치이다. 작은 행 수집 비용을
줄이는 것으로 이 차이를 해결하기 어렵다. `재계산 비율 × 고정밀도 시간`은 이 구조를 왜곡한다.

128행 조건에서는 63개 중 41개의 고정밀도 배치를 생략했다. 관측 native 평균은 842행당
1,473.12→1,243.24ms로 15.61%, 로컬 평균은 1,774.06→1,446.25ms로 18.48% 감소했다.
이는 동일 조건 안의 기술적 관측이며 확증된 성능 우월성이 아니다. 특히 로컬 gate 대조군과의
차이는 프로세스 잔여 시간 변동의 영향을 받는다. 또한 1,446.25ms는 842행 고정 고정밀도의
319.28ms보다 약 4.53배 크다. 작은 배치에서의 이득이 전체 처리량 최적성을 뜻하지 않는다.
큰 입력 배치를 허용할 수 있는지는 도착 시각과 지연 요구에 달려 있으며 이번에는 주어지지 않았다.

현재 고정밀도 재계산 22회는 서로 다른 고정밀도 키 22개를 사용하므로 **이미 호환되어 병합할
수 있는 배치 쌍은 0개**이다. 단일 클라이언트가 원래 입력을 보유하고 고정밀도 키 할당을
의도적으로 늦춘다면, 새 정책에서 동일 모델 window 안의 고정밀도 문맥을 공유하고 암호화 전에
packing할 수 있다. 묶음 기준에는 클라이언트·키 소유권, 실제 고정밀도 키, 모델, 파라미터,
출력 대응이 필요하다. 같은 파라미터나 반복 번호만으로 서로 다른 키가 호환되지 않는다.
여러 클라이언트의 키 병합이나 서버의 원래 평문 접근은 허용 가능한 대안으로 세지 않는다.

전체 842행을 같은 클라이언트 window로 모은다는 가정에서는 128행 조건의 재계산 대상이
모델·반복당 고정밀도 배치 하나에 들어간다. 고정밀도 배치 수는 조건부로 22→9가 된다.
이는 바뀐 키 수명 정책에 대한 **배치 수 하한**이며 측정된 절감량이 아니다. 대기·재포장
비용을 포함하지 않으므로 평균 고정밀도 시간을 곱하여 실현된 이득으로 주장하지 않는다.
`pooling_bounds.csv`는 더 없앨 배치가 없는 경우까지 포함하여 모든 묶음을 남긴다.

배치 하나를 없애면 고정밀도 입력 인코딩·암호화 57회, 모델 가중치 인코딩 57회와 해당
동형연산을 생략할 가능성이 있다. 상주 키를 공유하는 즉시 실행 대조군도 키를 한 번만
생성한다면, 생략한 배치마다 키 생성 비용까지 절감한다고 중복 계산해서는 안 된다.
새 비용은 클라이언트 버퍼, 수집·분배와 ID 대응, 스케줄링, window 대기 및 이후 구현할 실제
전송 비용이다. 현재의 작은 행 수집 시간으로 이 비용들을 대신할 수 없다.

동일 문맥 window에 재계산 배치가 하나 이하인 경우, 클라이언트·키 문맥을 공유할 수 없는
경우, 요청 마감이 대기를 허용하지 않는 경우에는 큐 이득이 확인되지 않았다. 이미 큰 배치가
가능한 조건에서도 이번 결과는 큐를 지지하지 않는다. 재계산이 잦으면 저정밀도 선행 실행이
추가 비용이 된다. 키 재사용이나 가중치 캐싱은 대조군을 맞춘 새 측정이 필요하다.

## Exactly one next minimal experiment — proposed, not executed

다음으로 **서로 인접한 원배치 2개를 묶는 클라이언트 큐 실험** 하나만 제안한다.
세 동결 모델·입력·radius를 유지하고 원래 입력 순서의 시작 offset (0,128), (256,384),
(512,640)을 짝지으며 마지막 74행은 단독으로 남긴다. 두 배치 모두 재계산을 요청한 경우만
골라서는 안 된다. 총 36개 모델·반복·window 중 이번 관측에서는 고정밀도 배치가 없는
window 22개, 하나인 window 6개, 둘인 window 8개였다. 이 고정 묶음의 조건부 배치 수
하한은 22→14이다. 불리한 단독·빈 window도 유지하면서 8회 호출을 없앨 여지가 있다.
이 역시 지연시간 추정은 아니다.

새 protocol에서 두 저정밀도 결과의 준비 시각과 판정을 먼저 기록한 뒤, 같은 도착 이력을
고정밀도 대안 두 개에 재생한다. 하나는 원배치별 즉시 재계산, 다른 하나는 두 번째 원배치가
준비될 때까지 기다린 뒤 함께 packing하는 방식이다. 두 대안 모두 클라이언트·모델·window당
실제 고정밀도 키 문맥 하나를 사용하고 그 준비 비용을 동일하게 포함한다. 원래 특징은
클라이언트에만 둔다. 입력 준비, Encode/Encrypt, HE, Decrypt/Decode/gate, 실제 고정밀도
배치 수, 입력별 추가 대기와 완료시간을 측정한다. 도착 이력과 준비 시각 측정 방식을 비교 전에
고정하며 대기를 무료로 가정하지 않는다. 저정밀도 작업은 공통 비용으로 기록한다.
이는 바뀐 키 수명 정책 아래의 배치 생략 효과를 분리하는 실험이다. 운영 큐 전체의 검증이나
위험 상한 이전을 뜻하지 않는다. 이 작은 protocol의 결과를 모두 남긴 뒤 종료한다.

## Evidence, changes and reproduction

시작 HEAD는 `9685958c0ac138bf6356fbcc63ef9cf3a7d94c57`이며 시작 작업 트리는 깨끗했다.
새 protocol SHA-256은 `ec6939713c03892d3f98e00878646b9c3bd8f48c392eff45ff4801c6ea0edb2b`,
원시 manifest SHA-256은 `0c183c7bb3ca9ba35b7dbccb605398de36fdd3323c89c2f6e35f4bde4becc379`이다.
`results/dp03_cost_diag_v1_20260905/run_binding.json`은 모델·부모 해시, protocol, 명령,
실행 바이너리, 소프트웨어·스레드 환경과 실행 당시 소스를 결속한다. 각 시행은 원배치,
클라이언트, 모델, 실제 저·고정밀도 키와 파라미터 문맥을 연결하고 요청·출력의 해시를 남긴다.
새 파일까지 포함한 `as_run_source`가 실행 소스의 기준이다. 시작 HEAD만으로는 새 계측 코드가
재현되지 않으며 `source_worktree.patch`만으로도 미추적 추가 파일을 포함하지 못한다.

독립 검증기는 원시 파일 1,219개와 직접 연결한 부모 파일 24개만 확인했다. 실제 출력으로
216개 시행 판정과 247개 호출을 재구성하고 원래 클라이언트 입력과 재계산 입력을 대조했으며,
횟수·시간 분해·파라미터 식별자를 확인했다. 운영 `execute_arm`을 호출하지 않고 별도의
이진 구간 계산으로 감사했다. `summary.json`은 검증기 해시를 결속한다.
`DERIVED_SHA256SUMS`는 생성한 수치 분석 파일 6개를 대상으로 하며 이 서술 보고서는 제외한다.
전체 archive 보존 해시는 반복하지 않았다.

변경 소스는 `cmd/deciprotect-ckks/main.go`의 공유 평가기 계측·동일 파라미터 생성 함수 추출,
새 `cost_diagnostic.go`, `src/deciprotect/cost_diagnostic.py`, 실행기·검증기와 관련 테스트이다.
새 protocol·원시 run·분석 폴더를 추가하고 README, 로드맵, CI, 변경 가능한 DeciProtect
동기화 패키지를 갱신했다. `.gitignore`는 임시 작업 폴더를 제외하고 `.gitattributes`는 새 분석
파일의 개행 변환으로 해시가 달라지지 않도록 설정했다. **기존 baseline, archive, 논문, 완료 protocol과 결과는 변경하지
않았다.** `/home/ckks2/flipguard`에서 코드·실험을 실행하지 않았고 archive를 Git에 추가하거나
전송하지 않았다. 기존 `INITIAL_RESULTS.md`와 과거 검증 보고서도 유지했다.

실행한 명령은 다음과 같다. 이 run ID는 이제 변경하지 않는다.

```bash
go build -o bin/deciprotect-ckks-dp03-v1 ./cmd/deciprotect-ckks
GOMAXPROCS=4 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python scripts/run_cost_diagnostic.py \
  --run-id dp03_cost_diag_v1_20260905 --binary bin/deciprotect-ckks-dp03-v1
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/verify_cost_diagnostic.py \
  --output docs/research/dp03_cost_diag_v1_20260905
```

현재 검증은 `--output` 없이 `.venv/bin/python scripts/verify_cost_diagnostic.py`로 수행한다.
읽기 전용이며 CKKS를 실행하지 않는다. 측정 재현에는 새 run ID가 필요하고 정책·예산이
바뀌면 새 protocol도 필요하다. 새 난수 키의 결과가 수치적으로 완전히 같을 필요는 없다.

Python 테스트 16개와 Go 테스트가 통과했다. 실제 affine CKKS의 유효 slot 수에 따른
연산량 확인과 재계산 요청·실행·유보·실패 구분을 포함한다. 이는 구현 검증이며 성능 향상이나
위험 보장이 아니다. 새 성공-run 검증기는 미완료·실패 run을 이번의 완전 비교로 인정하지
않는다. 그런 원시 실패는 보존하여 따로 분석해야 한다. 큐 실험이나 대규모 후속 실행은 시작하지 않았다.
