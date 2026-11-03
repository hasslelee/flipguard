# 외부 검증의 근거와 범위

이 문서는 실제 실행 결과표를 대신하지 않는다. 실행 결과는 `EXTERNAL_RESULTS.json` 및 최종 보고서에 별도로 연결한다. 확인한 코드의 범위를 넘어 구현 전체에 특정 기능이 없다고 단정하지 않는다.

| 대상 | 수치 오차·분류 정확도 | 평문/암호화 판정 | 구성 선택 조건 | 입력별 마진 조건 | 이번 구현 수준 |
|---|---|---|---|---|---|
| HEDiff, ICSE 2025 | 모델 정확도와 암호화 후 변화 평가 | 핵심 검사 대상. Eq.(2)는 평문이 정답인 입력에서의 이탈 | 구성 선택 경쟁 알고리즘이 아님 | 작은 평문 마진을 이용한 불일치 탐색과 선택 수용 조건을 구분해야 함 | 공식 Bank 모델/훈련/CKKS forward를 고정 commit에서 재사용; 원래 가중치가 없어 공개 절차 단일 재학습 |
| ELASM, USENIX Security 2023 | 수치 오차–지연 목적과 분류 정확도 평가 | 점검 범위에서 입력별 판정 일치를 선택 제약으로 사용하는지 확인되지 않음 | 확인한 explorer는 추정 지연·오차를 목적함수에 사용 | 점검한 explorer/estimator에서 입력별 마진 수용 조건은 확인되지 않음 | 기존 CoreLab 실행 자산 보존, 이번 원문·공식 코드의 제한된 정적 검토; 새 컴파일러 연결 실행이라고 하지 않음 |
| 기존 EVA 비교 | 수치 오차 평가·선택과 실제 CKKS 실행 | 기존 별도 입력에서 사후 판정·경계 관측 존재 | 원래 EVA 설정과 독립 C 선택을 구분 | 기존 실행에 없는 마진 수용 절차를 추가로 주장하지 않음 | 이전 공식 native 비교 결과 보존, 이번 신규 Bank 실행과 혼합하지 않음 |

[HEDiff 논문](https://daoyuan14.github.io/papers/ICSE25_HEDiff.pdf)의 Eq.(2)와 공개 코드의 반올림·argmax를 따로 확인했다. 주 지표는 전체 평문/CKKS 판정 불일치이고, 평문 예측이 정답인 부분집합의 이탈도 함께 보고한다. 원래 코드의 float32 모델과 CKKS 출력의 float32 변환 후 판정을 재현하는 지표, 공통 float64 다항식과 원래 복호화값을 비교하는 지표를 분리한다. 합성 스트레스 입력은 정답이 미확정이므로 Eq.(2)의 정답 조건을 충족했다고 계산하지 않는다.

대표 사례는 [공식 HEDiff 코드](https://github.com/Yiteng-Peng/HEDiff/tree/ffeed7f131d4b55698a08798927777b44f508099)의 Bank MLP이다. `plain_models.py:MLP_Bank`와 `base_ts.py:BankMLP_TS`는 모두 20→256→2 구조와 `t*t+t` 활성화를 사용한다. 연산 지원, 작은 공개 훈련 절차, 동일 다항식 출력이라는 이유로 선택했다. 불일치가 많이 날 것이라는 예측으로 모델을 고르지 않았다. 저장소의 pretrained/corpus 폴더에는 `.dummy`만 있으므로 논문 원래 가중치나 원래 발견 입력의 재현은 아니다.

[UCI Bank Marketing 자료](https://archive.ics.uci.edu/dataset/222/bank+marketing)의 `bank-additional-full.csv`를 사용한다. 공식 코드의 결측 대용값 `unknown` 제거, 범주 인코딩, 전체 자료 min-max 정규화, NearMiss, shuffle42, 마지막 20% 시험 분할을 유지한다. 훈련은 고정 seed 20260906, Adam 기본값, batch64, shuffleFalse, 100epoch이며 좋은 epoch/seed를 고르지 않는다. 전체 자료 전처리와 레이블 기반 재표집이 분할보다 앞서므로 이 정답률을 누출 없는 일반화 평가라고 부르지 않는다. 원시 자료 URL·SHA와 공식 코드 commit은 새 결과의 source binding에 있다.

외부 시험 순서 중 0–15는 선택, 16–47은 일반 감사, 48–175는 수치 허용값을 정하는 개발 자료이다. 개발 FP16 roundtrip 오차는 정규화하지 않은 두 원래 logit 전체에서 계산한다. 감사 정답률·CKKS 오차를 보고 허용값이나 모델을 바꾸지 않는다. 원래 native 설정도 선택 입력에서 먼저 실행한 뒤 모든 공통 선택을 고정하고 감사한다.

원래 native는 `diff_tenseal.py`의 Bank branch에 따라 N=8192, scale=2^26, 소수 비트 `[31,26,26,26,26,26,26,31]`, Galois key를 사용한다. 출력은 원래 두 logit이다. 이 SEAL 기본 admission과 우리 frozen V2의 보안 envelope는 동일하지 않다. 원래 설정의 QP 합 218은 우리 N13 한도 214를 초과한다. 원래 설정을 임의로 약화하거나 변경하지 않고 그 차이를 보고한다.

[TenSEAL v0.3.14의 빌드 설정](https://raw.githubusercontent.com/OpenMined/TenSEAL/v0.3.14/cmake/seal.cmake)은 SEAL v4.1.1을 지정하고, [SEAL 생성자](https://raw.githubusercontent.com/microsoft/SEAL/v4.1.1/native/src/seal/context.h)의 기본 보안 수준은 tc128이다. 이는 설치 wheel의 모든 빌드 내용을 검증했다는 뜻은 아니다. `SOURCE_AMENDMENT_08.json`은 외부 실행 전에 공개 context 계측을 추가한 기록이다. 실제 API가 제공하면 key/data modulus와 admission qualifier를 읽고, 제공하지 않으면 `API_UNAVAILABLE`로 남긴다. 비밀키는 직렬화하지 않는다. 계측 시간은 setup·추론 타이머 밖에서 별도 기록하고 전체 명령 시간에는 포함한다.

공통 연결은 원래 두 출력의 항등식 `t²+t=(t+.5)²−.25`를 사용해 기존 Lattigo 제곱 MLP의 낮은 수준 연산을 재사용한다. 각 출력 행의 bias를 독립적으로 보정하므로 가중치 차이로 하나의 점수를 만들거나 출력을 정규화하지 않는다. 원래 float32, 공통 원래 float64 다항식, 항등식으로 연결한 float64, CKKS 출력을 구분한다. 항등식은 실수 연산에서 같지만 부동소수점 연산 순서 차이는 별도로 측정한다. 내부 일곱 모델이나 C 정책을 바꾸지 않으며 새로운 compiler/bootstrap을 개발하지 않는다.

공통 C는 기존 layerwise primitive-count/역방향 L-infinity 민감도 계산 규칙을 이 20→256→2의 정확한 제곱 그래프에 적용한다. 규칙 변경 없이 차원·shifted hidden 관측 범위만 바뀐다. 그 후 기존 `Synthesize`, `DefaultPrimarySynthesisPolicy`, `RepairCandidate`, Q/QP admission, 다중 클래스 수용 함수를 호출한다. A/B는 별도 `BankIndependentFacts`가 산출한 그래프·출력 범위만 받는다. 원래 TenSEAL의 packing·scale 일정까지 같은 것으로 간주하지 않고 두 backend의 시간 차이를 선택 조건의 인과 효과로 해석하지 않는다.

비용 경계는 `research/hediff_bank_validation/cmd/contribution-case/main.go`의 `select` 분기에서 확인한다. C는 `freshContract`와 `Synthesize`를 실제 선택 타이머 안에서 다시 호출하며 `analysis_ms`와 전체 선택 wall에 포함한다. A/B는 그 대신 `BankIndependentFacts`를 계산한다. 앞선 `new-plan`은 연결 검사용 계약 컨테이너 준비이며 별도 명령 비용으로 남긴다. 그 산출 후보를 A/B 생성기에 전달하거나, 그 최초 준비 비용을 각 방법의 선택 시간에 임의로 합산하지 않는다. 모든 기록된 명령의 전체 비용에는 이 준비도 포함하고, 선택·준비·훈련·연결 비용을 구분한다.

기존 스칼라 projection 검토안은 외부 훈련/CKKS 시작 전에 폐기했다. 원래 spec과 소스는 보존하고 `SOURCE_AMENDMENT_05/06` 및 `EXTERNAL_PROTOCOL_EXACT_LOGITS.json`에 정정 이유와 해시를 남겼다. 내부 실행 바이너리는 변경하지 않았다. 외부 소스·바이너리는 `EXACT_ADAPTER_SOURCE_LOCK.json`에 별도로 고정했다.

외부 스트레스의 원시 나이·기간·횟수 열에는 정수 제약이 있다. 외부 훈련과 CKKS 실행 전에 이를 확인하여, 같은 16개 부모·20단계·0.05 정규화 반경 안에서 마지막 결과를 원래 정수 격자에 투영하도록 보완했다. 범주형 값은 그대로 고정한다. `SOURCE_AMENDMENT_07.json`과 `STRESS_INTEGER_PREEXEC_AMENDMENT.json`이 이 변경을 기록한다. 모델·일반 입력·선택 기준·보안·실행예산은 바뀌지 않았다. 좌표별 제약을 만족해도 실제 고객 특성의 공동 타당성과 합성 정답은 미확정이며, 독립 집계에서 그 제한을 유지한다.

[ELASM 논문](https://www.usenix.org/system/files/usenixsecurity23-lee-yongwoo.pdf)은 오차·지연과 분류 정확도의 관계, LeNet의 응용 정확도를 평가한다. 따라서 기존 CKKS 연구가 판정을 전혀 고려하지 않았다고 전제할 수 없다. [공식 구현](https://github.com/corelab-src/elasm/tree/3c37c11b29ca480525bb6681e0254bdf90029425)의 검토한 `ELASMExplorer.cpp`는 추정 latency/error로 비용함수를 계산하며, 검토한 MLP 예제는 784→100→10 제곱 모델과 자체 packing을 사용한다. 기존 70/72 계획·14,000 수치 관측 자산은 보존하되 가중치·입력·출력 일치를 확인한 이번 판정 비교로 재명명하지 않는다. 이 제한된 확인으로 전체 구현의 모든 분기에 판정 조건이 없다고 단정하지 않는다.

FHE-Agent v1 §4.1/§4.3의 활성화 고정 서술과 기존 설명의 정정은 `../fg_expand_v2_20260905/FHE_AGENT_CORRECTION_KO.md`에 보존돼 있다. 이번 작업은 최종 제출 PDF를 수정하지 않는다.
