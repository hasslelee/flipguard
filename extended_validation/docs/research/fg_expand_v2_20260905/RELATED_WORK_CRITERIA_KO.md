# 정확성 보고와 구성 수용 조건의 구분

최종 PDF §2.4·§5.7의 인용 및 기존 V18·V8 자산을 출발점으로 제한적으로 확인했다. 지난 원문 취득본과 hash는 `LITERATURE_REUSE.json`, 공식 EVA 복사본 및 기존 외부 기록은 `EXTERNAL_SOURCE_BINDINGS.json`에 연결했다. 원문에 기술되지 않은 것과 구현에 없는 것은 다르다. 아래 ‘미확인’은 없다는 단정이 아니다.

| 대상·확인 판본 | 수치 오차 / 정답률 평가 | 평문–암호화 입력별 판정 일치 | 선택·수용 조건 | 입력별 판정 마진 조건 | 공식 구현 확인 범위 |
|---|---|---|---|---|---|
| CHET PLDI2019, 이전 arXiv2018 구분 | 공식2019 초록은 보안·수치 정확성을 위한 파라미터 선택 자동화 명시. DOI 전문 접근403 | 2019 전문 미확인 | 이전 판본의 사용자 정밀도 기반 설정을2019 정량 결과로 대체하지 않음 | 미확인 | 독립 실행 artifact 미확인 |
| EVA arXiv1912.11951v2, §4·§8 | MSE 및 DNN 정답률 평가 | 전체 정확도 같음을 입력별 일치로 해석하지 않음; 해당 절에서 독립 일치 수용 규칙 미확인 | 사용자가 input scale/output range 제공, compiler가 scale·rescale·파라미터 계획. DNN 실험에서 정답률을 보고 scale을 정하는 절차 있음 | 확인한 compiler 경로에 입력별 분류 마진 인자가 없음 | 실제 공식 compile/nativeSEAL 실행. README 및 tests/common.py, ckks compiler 경로 확인 |
| HECATE CGO2022, §VI–VII | RMSE·지연, DNN 포함 | 해당 평가의 일치율 조건 미확인 | 36 waterline 중 허용 오차2^-8 아래 최소 지연을 고르는 **오차 제약** 있음 | 해당 설명에서 미확인 | 기존 CoreLab native/HEVM 수치 실행과 README 확인. 현재 큰 repository를2022판과 동일시하지 않음; 전체 선택 구현 감사 미완료 |
| ELASM Security2023, §5–7 | 오차·지연 추정, §7.4 LeNet 정확도 | task accuracy와 입력별 일치 구분 | SNR·오차·지연을 고려한 scale 관리; 정확도 결과만으로 입력별 판정 수용이 있다고 추정하지 않음 | 확인한 절에서 미확인 | 기존70완료/72계획의 수치 자료, official README/출처. 전체 margin 검사 존재 여부는 미확인 |
| FHE-Agent arXiv2511.18653v1, §3–5 | 정확도·MAE·effective bits, 실제 암호화 평가 | plaintext task accuracy 대비 gap은 개별 일치율과 다름 | **사용자 정확도 허용차, 수치 정밀도·보안 gate를 수용에 사용**. 단순 결과 보고만 하는 방법이 아님 | 해당 수식·설계에서 우리 입력별 점수차 조건은 확인하지 못함 | 저자 확인된 실행 가능한 공식 artifact 미확보. 활성화 설명 정정은 별도 기록 참조 |
| HEIR arXiv2508.11095v1 | compiler pass/backend 중심. 모든 모델의 공통 정확도 실험 표로 볼 수 없음 | 기존 우리 V8의 공통 다항식 결과는 존재 | 해당 pipeline이 범용 inputwise decision gate라고 확인하지 않음 | 미확인 | 기존 MLIR 산출/공통 Lattigo 이식의 범위. 공식 모든 NN native 실행으로 표현하지 않음 |
| Orion arXiv2311.03470v3, §7 | PyTorch 대비 암호화 출력 정밀도·정답률. MNIST10,000 등 규모 구분 | 정답률의 동일성은 모든 입력 판정 동일성 아님 | packing·scale·bootstrap 계획; 해당 표는 입력별 일치 수용 조건의 증거가 아님 | 미확인 | 기존 build/preflight와 모델·packing 불일치 기록. 이번 native모델 비교 없음 |
| El Bouabidi 등 SciRep2026 | computational accuracy·지연 평가 | 정의를 개별 분류 일치로 동일시하기 어려움 | 정확도 제약을 둔 설정 선택으로 문제 교집합 존재 | 미확인 | 공식 실행·동일 보안 조건 미확인, 정량 비교 보류 |

EVA 공식 `tests/common.py::assert_compiles_and_matches_reference`에는 평문 변환 MSE<1e-10와 HE MSE<.01 검사가 존재한다. 이는 **테스트의 허용오차**이며 실제 compiler의 모든 응용에 자동 적용되는 후보 선택 gate가 아니다. 이번 공통 다항식의 scale30/range20 설정에 임의로 이 테스트 한도를 수용 정책으로 붙이거나, 단위가 다른 Fashion logits에 복사하지 않았다. 공식 compiler가 요구하는 입력 scale·출력 범위·security128과 실측 오차/우리 사후 조건을 각각 기록한다. [공식 EVA 저장소](https://github.com/microsoft/EVA)

HECATE와 FHE-Agent처럼 정확성을 선택 제약으로 쓰는 연구를 숨기지 않는다. 비교의 초점은 정확성을 처음 고려했는지가 아니라 **무엇을 수용 조건으로 삼는지**, 특히 입력별 판정 마진과 연결하는지다. FHE-Agent의 활성화 고정 설명을 인정한 [정정 기록](FHE_AGENT_CORRECTION_KO.md)을 기존 문단보다 우선한다. [FHE-Agent v1](https://arxiv.org/html/2511.18653v1), [HECATE 원문](http://www.corelab.or.kr/Pubs/cgo22_hecate.pdf), [ELASM 공식 원문](https://www.usenix.org/system/files/usenixsecurity23-lee-yongwoo.pdf)

## 기존 외부 자산의 구현 수준과 이번 결정

| 자산 | 정확한 분류 | 보존해야 할 제한 / 이번 결정 |
|---|---|---|
| EVA V8 공통 다항식, S20/30/40 | 공식 EVA/SEAL 실제 암호화 실행 | S20의133/1,500·114/500 변화는 과거 선택용 입력의 특정 설정 결과. 그것을 EVA 원래 절차가 항상 선택하는 설정으로 쓰지 않음. 이번 대표 대상은 기존 사전 scale30 유지. |
| HEIR V8 공통 다항식 | 외부 산출·설정을 공통 Lattigo로 연결한 이식 비교 | 500입력·3키의 HEIR 결과0위반 존재. 같은 이름의 native NN 실행이 아님. 대응 direct 시간 arm의 한 입력8반복 변화 때문에 기존 시간 주장 차단을 유지. |
| CoreLab EVA-mode/ELASM36+36계획 | 실제 공식 연결 실행의 수치 자료, 일부 계획 실패 | 70계획×200입력=14,000관측과2실패 존재. 동일 분류 출력 계약이 없어 판정 보존 사례로 세지 않음. |
| Orion 기존 설치·preflight | build/연결 또는 지원 범위 확인 | 구조·가중치·활성화·출력·packing의 동일성이 확보되지 않음. 이번 새 모델로 축소해 원래 재현이라고 부르지 않음. |
| Fashion FP16 기준 선택 | 개발 자료 기반 별도 대표 대조군 | 선행 논문 native 재현이 아님. 공통 후보의 수용 조건 차이만 해석. |
| FHE-Agent·CHET 등 미실행 | 문헌 설명 / 제한된 연결 확인 | 미실행은0실패가 아님. controller/새compiler 재개발은 보류. |

대표 대상으로 EVA를 고른 근거는 최종 PDF의 관련성, 공개 공식 구현, 이미 동작한 build, 정확히 같은 공통 다항식·입력의 존재다. 예상 실패율을 기준으로 고르지 않았다. 복사한 모듈의 첫 연결 검사가 통과했고 기존 docker image에서 실행했으며 원본 FlipGuard는 mount하지 않았다. 같은128bit 목표라도 SEAL와 Lattigo의 키 분포·assessment·실행 일정·packing이 완전히 같다고 하지 않는다. 이번 외부 결과는 출력 의미가 같은 범위의 실제 암호화 비교이고, 선택 조건만의 인과적 속도 비교는 보류한다.

Fashion 전체784→100→10 그래프를 EVA에 새로 옮기는 작업은 원래 backend schedule과 정확한 공정 조건의 별도 검증이 필요하다. 이번에는 공통 구현의 수치/판정 기준 비교를 Fashion에서 수행하고, 실제 EVA는 기존 지원 공통 다항식으로 수행한다. 외부 비교를 문헌 소개로만 미루지 않았으며 외부 연결을 이유로 영상 확대를 멈추지도 않았다.

## 최종 PDF에 맞춘 최소 보강 문장 — 미적용

§2.4의 기존 설명 뒤: “선행 연구는 수치 오차 또는 응용 정확도를 평가하며, 일부는 이를 구성 선택의 제약으로 사용한다. 본 연구는 같은 후보 범위에서 수치 오차 기준에 따른 선택과 입력별 판정 마진을 반영한 수용 조건의 차이를 비교한다.”

§5.7의 외부 결과 설명 뒤: “외부 도구의 공식 암호화 실행과 공통 backend 이식 결과는 구현 수준을 구분하였다. 동일한 평문 출력에서도 실행 일정과 보안 평가 가정이 다르면 지연 차이를 선택 기준만의 효과로 해석하지 않았다.”

삭제된 수식·의사코드·내부 시스템 이름을 복구하거나 이 문장을 PDF에 자동 삽입하지 않았다. 실측 결과 문장은 이번 결과 완료 후 검증 가능한 범위에서만 별도 제시한다.

CHET의 공식 PLDI2019 소개를 추가 확인했지만 연결된 DOI 전문은 HTTP403으로 확보하지 못했다. 2018 판본을2019 본문으로 대체하지 않았고, 본문/구현의 개별 판정 조건 부재를 단정하지 않는다. 접근 결과는 `CHET_2019_ACCESS_CHECK.json`에 남겼다. [Microsoft Research의2019 소개](https://www.microsoft.com/en-us/research/publication/chet-an-optimizing-compiler-for-fully-homomorphic-neural-network-inferencing/)
