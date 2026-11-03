# 최종 논문 기존 증거 재현 보충자료 v1

문서 ID: FG_JOURNAL_EVIDENCE_V1_20260906. 기준 PDF와 원래 구성 선택 방법을 유지하는 **구현·동결 기록 확인 및 기존 평문 산술 재집계**다. 새 CKKS·소수 생성·학습·모델 refit·C/C′ 변경은 없다. 본 파일의 내부 식별자와 상세 산식은 본문에 자동 삽입하지 않는다. 로컬 제출 첨부용 v1이며 공개 저장소·외부 서비스에 게시하지 않았다.

## 1. 증거의 우선순위와 실행 소스 연결

최종 PDF의 SHA-256은 `0210899a12ff1025db358e1812159ca4af2b5c6095a79e2b7b19200d7e9f3b85`다. 작업 시작 HEAD는 `54671293e5f6532f2423f5bf473ea714555ee9f4`. 사용자 지시, 이 PDF, 당시 protocol·raw와 대응 소스, 검증된 재집계 순으로 사용했다. 이전 PAPER_ONLY의 심사 내용·해시는 보존했고 여기에 코드를 근거로 보충한 내용을 소급 주입하지 않았다.

`SOURCE_CLOSURE.csv`의 12개 파일과 `ADDITIONAL_SOURCE_CLOSURE.json`에 대해 실제 읽은 소스 바이트를 당시 source snapshot의 개별 SHA에 맞췄다. 원래 `source_snapshots/v17_final_vm1x6_20260811T050104Z/manifest.json`의 source tree digest는 `2095f4bf8bf3a30997bf1c526b8bea74f99e353d3ae43bf89df2104a80b187cd`, scientific execution digest는 `495ca799cd110c6180b5bf981bebf8339d31d895c71c20d6db02ea34acc88c57`이다. 실행 소스 closure commit은 `cefc44b0d7e351db2a34886dd758a2d31a3e4c12`; 후속 집계 commit `86b0403208abbc741a65934358a5dea4a66e4d88`과 구분한다. 당시 Git HEAD만으로 미커밋 실행 소스를 설명하지 않는다. 과거 전체 314파일 재해시를 반복하지 않았다.

읽기 경로의 `baseline/source`가 최근 복사본이라는 이유만으로 과거 증거가 되는 것은 아니다. 이번에 인용한 파일은 위 대응을 거쳤다. 학습 builder와 frozen raw는 원본 FlipGuard에서 **파일만 읽었고**, 원본 스크립트·Go 프로그램·인터프리터를 그 위치에서 실행하지 않았다. 원래 baseline/source 문맥에 있는 비활성 정책 함수가 원래 C에서 활성 실행됐다는 뜻도 아니다. 예시의 실제 plan은 `precision_slack_mode=none`이다.

원시 자료 참조는 절대 경로·SHA·필드 또는 JSON pointer로 연결했다. `READ_BINDINGS.json`, `DETAIL_READ_BINDINGS.json`, `ADDITIONAL_QUALITY_READ_BINDINGS.json`은 이번에 사용한 범위의 출처 목록이다. 두 다중 클래스 사례의 inventory/legacy split 명칭 차이는 `CASE_ID_ALIASES.csv`에 보존했다. 별개 모델이나 추가 사례로 세지 않고 같은 raw 경로와 실제 contract split을 확인했다.

## 2. 초기 합성과 한 단계 조정의 실제 사례

선정 규칙: 주요 68 중 조정된 21개를 case ID 사전순으로 정렬하고 원시 plan·trial·입력 추적이 갖춰진 첫 사례를 사용한다. 최대 개선 사례를 고르지 않았다.

- case: `primary|banknote|linear_poly3|outer_fold_0_training_seed_0`.
- 고정 모델 SHA: `e1fe81715d04bd32b62c60de8e3cc1edbf3c8940f1c5254206b9299265338de1`.
- 모델 경로: `/home/ckks2/flipguard/results/model_family_expansion_v17/plaintext/primary/banknote/linear_poly3/fold_0/training_seed_0/model.json`.
- raw 선택 경로: `/home/ckks2/flipguard/results/model_family_expansion_v17/runs/v17_final_vm1x6_20260811T050104Z/primary/banknote/linear_poly3/fold_0/training_seed_0/selection.json`; SHA `6a85ea8bfbb6c41e8ae8fde0153b276a7d625a247e39fc5661327d442a0abe87`.
- 학습/선택/별도 입력: 822/275/275. 선택 275개 모두 margin>0.001. 입력 특징 4, 출력 `0.5+0.197z−0.004z³`, threshold=0.5. 유효 요구 슬롯 1; 스칼라 복제 실행이다.

계산은 `BuildTabularWorkloadContract` → `AnalyzeBoundsAndSensitivity` → `aggregateOperationSensitivity` → `Synthesize` → `synthesizeBackendValidRescaleCandidate` / `synthesizeRescaleCandidate` → `Profile` → 실제 trial → `RepairCandidate`로 이어진다. 파일과 줄이 포함된 발췌는 `source_excerpts/`에 있다.

| Step | Actual value / calculation | Evidence |
| --- | --- | --- |
| 평문 관측 범위 | 정규화 입력 max abs 3.5423741437354272; z ∈ [−0.8936325467103716, 0.5915879201071373]; 출력 max abs 0.6157146533330677 | contract.calibration, WORKED_EXAMPLE_NODE_RANGES.csv |
| 판정 예산 | 최소 적용 마진 0.0027796012554593963 × ρ0.5 = 0.0013898006277296981 | contract.decision |
| 민감도 합 | 다항식 도함수 절댓값 최댓값 0.197; 상수배 4·합산 3·bias 합산 1개 노드의 각 민감도 0.197, 출력 노드 1 → 합 2.576 | 기존 IR과 순수 평문 구간 복원 |
| 단위 오차 예산 | 0.0013898006277296981 / 2.576 ≈ 0.000539519 | SYNTHESIS_WORKED_EXAMPLE.json의 정밀값 |
| 정밀도·분석 scale | ceil(−log₂(unit budget))=11; max(11+3,18)=18 | Table2와 frozen policy |
| 정적 백엔드 보정 | 기록된 attempts=3, lift=2 → 최초 실제 scale20 | initial_candidate.backend_* |
| 실제 연산 단계 | IR 곱셈 깊이2와 backend rescale 소요6은 다름; terminal scale exponent1 → Q 7개 | contract.graph / deployment |
| 첫 Q / P | message bits0; 첫 Q=S+0+1+2=23, 뒤 6개20; P=max(30,23)=30 | synthesis.go |
| 보안·환 차수 | Q143, QP173; N12 cap106은 부족, N13 cap214 통과 → N8192 | initial_candidate.security |
| 최초 암호화 trial | 275×3=825 관측; 판정 변화11, 오차 위반43 → REJECTED | trials[0].sample_ledger |
| 기존 조정 | scale20→24; Q=[27,24,24,24,24,24,24], P=[30]; Q171, QP201; N13 유지 | trials[1].candidate |
| 두 번째 trial | 825 관측; 판정 변화0, 오차 위반0 → SAFE; 후보2회/키 실행6회 | trials[1].sample_ledger |

정적 보정의 실패 시도별 소수/오류 문자열은 이 선택 기록에 저장되지 않았다. attempt3/lift2와 frozen retry 규칙으로 분석 단계와 실제 최초 구성을 구분했으며 소수 생성기를 재실행하지 않았다. 코드의 max scale50은 초과 시 실패시키는 상한이며 무조건 50으로 낮춰 통과시키는 규칙이 아니다. 분석 helper에 전달된 0.05 분위값은 원래 primary contract의 예산 출처가 아니다. primary는 δ보다 큰 마진의 최솟값을 별도로 계산한다.

입력226, key-repeat index1의 기존 기록은 `ACTUAL_DECISION_REPAIR_EXAMPLE.json`에 담았다. 평문0.5027796012554594; 최초0.4907081033856266, 오차0.012071497869832803; 선택0.5026977750559247, 오차0.00008182619953467363; 한계0.0013898006277296981. 최초의 flip/error는 모두 참, 선택은 둘 다 거짓이다. key index1의 대응이며 서로 다른 후보에서 같은 비밀키를 썼다는 주장은 하지 않는다. 입력을 재생성하거나 실패를 만들지 않았다.

이 민감도는 관측 입력 구간과 구현 DAG의 초기 추정이다. 실제 CKKS 전역 오차 보증, 모든 미래 입력의 충분조건 충족, 최소비용 최적성으로 확대하지 않는다.

## 3. 보안 검사의 시점과 적용 범위

`DefaultSecurityEnvelope`와 당시 plan은 secret `ring.Ternary(P=2/3)`, error `ring.DiscreteGaussian(sigma=3.2,bound=19.2)`를 기록한다. 원래 conservative 기준은 Security Guidelines Table5.2, classical Category128, logN12/13/14/15의 모듈러스 한도106/214/430/868이다. ciphertext Q와 evaluation-key QP가 각각 한도를 통과해야 한다. 표의 sigma3.19와 runtime3.2의 차이를 exact-distribution 동등성으로 쓰지 않는다.

| Check | Stage | Confirmed scope / limitation |
| --- | --- | --- |
| 선언 Q/QP 비트 검사 | 합성·조정, 실제 trial 앞 | 이번 예시 및 실행된 후보의 admission 필드; 표 기반 구성 수용 |
| backend literal 유효성 | Profile/parameter construction | NTT용 소수 및 backend 실행 가능성; lattice 보안 estimator 자체가 아님 |
| 실제 소수 사후 검사 | 기존 journal multiclass reconciliation | 기존4후보 중 주요 MLP-100·LeNet 선택2후보의 ID와 literal을 직접 일치시킴 |
| 후속 Bank의 별도 helper 호출 | 기존 정책 자료의 읽기 전용 확인 | 이번에 새 호출 실행으로 확인하지 않음; 함수 존재만으로 실행 판정하지 않음 |

`SECURITY_CHECK_SCOPE.json`에 일치한 두 주요 후보의 Q/QP 실제 로그값과 기존 사후 기록을 담았다. MLP-100 실제 QP193.99920762616645, LeNet856.0000005968122; 기존 두 classical estimator 모델의 최소치는 각각145.229851075969와132.046927836598비트다. 4후보 사후 검증 전부를 주요68 또는 후속 Bank의 검증으로 세지 않는다. runtime Gaussian truncation을 estimator가 정확히 모델링하지 않았고 quantum 비용은 평가하지 않았다는 기존 제한을 유지한다. Banknote 예시의 exact-prime 사후 검사 연결은 이번 한정 자료에서 확립하지 못했다. 이것은 선언 admission 실패나 보안 위반을 관측했다는 뜻이 아니다.

## 4. 89회와 537회의 실제 규격

원래 protocol의 `candidate_space.json` 사본과 당시 `BuildV17DepthCompleteFiniteSet`을 함께 확인했다. `B3` 등 내부 이름은 보충자료에서만 사용한다. B3는 C의 동일 contract와 기본 초기 합성을 호출해 첫 후보를 만든 후 numerical repair를 최대3번(+4비트씩) 진행하고 각 단계에 level guard0/1을 만든다. 허용 경로는 원래 contract의 rescale이다. legacy 7 profiles×2 paths14행은 별도 진단이며 537에 넣지 않는다.

생성 규칙은 암호화 실행 전 고정됐지만 사례 literal은 선택용 평문을 분석한 contract에서 생성된다. 주 caller는 C 선택 후 B3를 실행하되 원래 contract를 넘긴다. C의 최종 선택 결과를 보고 후보 하한을 바꾸지 않는다. 반면 contract의 마진 예산을 사용하므로 주석의 “graph facts alone”를 판정 정보로부터 독립한 생성기로 읽으면 안 된다. 이번 후속 A/B 독립 생성기와도 다르다.

| Accounting | Direct procedure | Frozen finite comparison |
| --- | --- | --- |
| 사례 수 | 68 | 68 |
| 실제 후보 평가 묶음 | 89 | 537 = 67×8+1 |
| 실제 키 실행 | 267 | 1,611 |
| SAFE / REJECTED | 68 / 21 | 477 / 60 |
| 실행된 묶음의 backend/security 실패 | 0 | 0 |
| 평가된 후보마다 키 반복 | 3 | 3 |

537행 모두 실제3키 출력 관측을 가진다. 생성 전 탈락을0으로 평가한 것이 아니다. LeNet은 초기 S44, Q18/P54, 선언 QP856/N15에서1개만 생성·평가됐다. 같은 S에 Q하나를 더하면900, S를48로 높인 기본 QP는932로, N15 한도868을 넘는다. 이는 저장 literal과 규칙의 산술 설명이며 생성되지 않은 각각의 branch가 별도 보안 실패 로그로 남았다고 하지 않는다. 생성 불가 branch별 상세목록은 미기록이다. 미생성·미실행을 암호화 실패나 별도 후보 평가로 합산하지 않는다.

생성기 `seen`은 candidate ID 중복을 제거한다. 전체 literal+path를 새로 비교한 결과도 사례 내부537쌍이 모두 다르지만, 서로 다른 사례의 동일 파라미터까지 전역 중복 제거한537종은 아니다. direct와 finite에 공통 literal이 있으면 실행 역할과 키가 다르므로 실제 평가 묶음은 각각 보존한다. 그 숫자를 독립 입력 수로 해석하지 않는다. 후보 원본 literal은 저장된 ParametersLiteral 규격 전체이며, 실제 Q/P 소수값을 이번에 새로 materialize한 값이 아니다.

`CANDIDATE_SPECIFICATIONS.csv`는 direct89+finite537=626행이고 case/model/split, raw SHA/pointer, literal JSON, N/Q/P/S, 경로, 생성이유, 보안, status, 실제 키·입력 관측, flip/error를 담는다. `CANDIDATE_COUNT_AND_COMPARATORS.csv`는 사례별 합계와 후보 수용/선택을 연결한다. 표형에서도 숫자 지표만으로 수용했다고 바꾸지 않는다.

최속 실행 후보의 판정 변화 사례18와 오차 위반 사례18의 교집합은18, 오차만 위반한 사례0이다. 후보와 C의 식별자 차이23 중 실제 literal/path 차이는21, 명칭만 다른 경우2다. 그21 중 기준 위반18, 기준을 통과하면서 실제 구성이 다른 경우3이다. 최속 수용 후보는 C와 ID가63/68, literal/path가65/68에서 같다. 나머지3은 Digits 1층 MLP fold4(S20 대24), Iris 다항식 fold3(S20 대24), 표형 MNIST 1층 MLP fold1(S20 대28)이다. 표기의 등식은 비밀키나 난수·시간 관측의 동일성을 뜻하지 않는다.

89/537의 83.43%는 후보 평가 횟수 감소다. 전체 선택시간 감소율, 후보별 균일비용, 전역 최속 선택 또는 독립 대조군 대비 개선으로 바꾸지 않는다.

## 5. 데이터·모델·분할과 평문 품질

| Dataset path meaning | Original task / features | Partition and treatment |
| --- | --- | --- |
| banknote | 원자료 0/1 label 유지, 4특징 | 각 5-fold에서 학습/선택/별도 분리; label값의 의미를 이름만으로 추정하지 않음 |
| wdbc | sklearn breast-cancer 0/1 target 유지, 30중16특징 | 학습 자료만 표준화·특징 순위 계산 |
| iris_binary | Iris target<2만 유지, 4특징 | 제3클래스 제외; 원래3클래스 문제의 정답률이 아님 |
| digits_binary | 짝수1/홀수0, 64중16특징 | 전체10종 숫자의 parity 과제; 표준화·특징 선택은 학습만 |
| mnist_pool16 | 짝수1/홀수0, 28×28→4×4 평균풀링16특징 | 전체70,000 원자료에서 class별1250행 hash표집; 공식train/test 분리 유지 아님 |
| mnist_10class | 원래10종 숫자, 784입력 | 공식train60,000과 test10,000 분리 유지; CKKS는 아래500/500 |
| mnist_binary01 | 숫자0/1, 4×4, threshold0 | 공식train에서 학습·개발·선택, 공식test에서 별도 입력 |

표형65는 5데이터×5fold의 다항식25, 1층MLP25와 Banknote/WDBC/MNIST16의 2층MLP15다. StratifiedKFold(5,shuffle=True,random_state=1701)의 외부20%를 별도 입력으로 고정하고 나머지의25%를 stratified split(seed2701+fold)으로 선택용에 둔다. 약60/20/20비율이며 선택용과 별도 행은 사례 내부에서 겹치지 않는다. 표준화 평균·표준편차, 최대16특징의 로지스틱 가중치 순위, 출력 정규화는 학습 역할에서만 계산한다. 학습seed0이며 후속 확대의 NearMiss 등 절차를 가져오지 않았다.

다항식의 선형 본체는 LogisticRegression(liblinear,C1,max_iter2000). 특징 순위 계산도 liblinear/max_iter2000이다. MLP는 4 또는8→4 제곱 은닉층, full-batch Adam1200epoch, 초기 가중치 N(0,0.08), bias0, lr0.003, beta0.9/0.999, epsilon1e−8, L2=1e−4, 전체 gradient norm cap5다. 고정 횟수 종료이며 수렴 판정/early stopping 결과는 아니다. 선형 모델의 실제 n_iter·ConvergenceWarning은 모델 artifact에 저장되지 않아 경고가 없었다고 단정하지 않는다. 정규화된 학습 logits 최대 절댓값의 역수를 출력 가중치/bias에 적용한다. 다항식은 `0.5+0.197z−0.004z³`, MLP의 선형 score는 `0.5+0.197z`; threshold0.5는 고정 출력 정의다.

MLP-100은784→100(square)→10, LeNet은28×28을32×32 zero-pad한 뒤 conv6(5×5)→square→avgpool2→conv16(5×5)→square→avgpool2→400→120(square)→64(square)→10이다. Table4의2FC는 두 은닉 affine층이며10출력 head는 따로 있다. 공통 모델seed5354592293955390513, Adam8epoch,batch64,beta0.9/0.999,epsilon1e−8,L2=1e−5,gradient cap5, lr는MLP0.001/LeNet0.0005, epoch마다×0.9, early_stopping=False다. 60,000 중 모델 학습55,000/검증5,000이고 공식test의 각클래스 hash순위0–49를 구성선택500,50–99를 별도500으로 둔다. 두 모델의 같은 영상 반복을 새 독립 영상으로 세지 않는다.

저장된 공식test10,000 평문 정확도는MLP97.76%,LeNet98.91%; balanced accuracy0.9774123089233575/0.9888295109137069,macroF1 0.9774991428126858/0.9889637861165234다. test의 클래스 수는[980,1135,1032,1010,982,892,958,1028,974,1009]이며 두 모델에 같다. 이10,000은 암호화 평가 수가 아니다. 각500 역할의 정답률은 실제 저장된 평문 logits와 해당 label을 이번에 다시 연결했다. epoch training_history의 온라인 정답률은 고정 최종모델의 training 재추론 정답률과 구분한다.

packed CNN-lite는 mean7×7 풀링, valid2×2 filter4, square,36개 출력의 선형 head다. 학습12,165,개발250,구성선택250,별도250. 모델seed5065504290027946322, Adam24epoch/batch64/lr0.01/beta0.9/0.999/epsilon1e−8/L2=0.0001,updates4584. 학습 정답12008/12165, 개발249/250, 선택245/250, 별도248/250이 기록돼 있다. 학습 score 최대값49.25859809230995의 역수0.020301024363828087로 정규화했다. 기존 모델 파일의 scalar adapter 범위 문구와 V17의 새 spatial packing adapter는 구분한다. 가중치는 같고 V17 실제 실행은 영상당16슬롯·11회전·8회전키다. 20개 영상의 시간 묶음을 유효 슬롯 수나 독립 키 수로 바꾸지 않는다.

주요68의 `MODEL_QUALITY_BY_ROLE.csv`는 136개 선택/별도 역할의 **저장 평문 출력 재집계**, 표형65 학습 역할의 **동결 모델·전처리만 사용한 평문 산술 복원**을 구분한다. 산술 구현은 같은 선택 입력의 원래 score와 최대 차이1e−10 미만인지65모델 전부 확인했다. 학습·평가 label의 일치, 분할 불중복, 클래스별 recall/혼동행렬과 balanced accuracy/macroF1도 포함한다. 정답률은 전체 입력, CKKS 수용 조건은 적용 입력으로 분모가 다르다. training manifest의 z>=0 품질 수치를 무조건 score>=0.5 결과로 대체하지 않았다.

### 주요68의 모델별 별도 입력 요약

| Dataset / model | Cases | Separate n / applicable / boundary | Accuracy % (min–max) | Coverage % (min–max) | Selected median ms (min–max) | Unit |
| --- | --- | --- | --- | --- | --- | --- |
| banknote / linear_poly3 | 5 | 1372 / 1372 / 0 | 97.45–98.91 | 100.00–100.00 | 63.387–63.624 | one input invocation |
| banknote / mlp_square2_linear_score | 5 | 1372 / 1372 / 0 | 100.00–100.00 | 100.00–100.00 | 306.046–306.533 | one input invocation |
| banknote / mlp_square_linear_score | 5 | 1372 / 1372 / 0 | 100.00–100.00 | 100.00–100.00 | 91.881–92.472 | one input invocation |
| digits_binary / linear_poly3 | 5 | 1797 / 1783 / 14 | 88.61–91.36 | 98.61–99.72 | 149.828–150.737 | one input invocation |
| digits_binary / mlp_square_linear_score | 5 | 1797 / 1765 / 32 | 92.48–95.56 | 96.11–99.44 | 179.060–179.642 | one input invocation |
| iris_binary / linear_poly3 | 5 | 100 / 100 / 0 | 100.00–100.00 | 100.00–100.00 | 62.732–63.108 | one input invocation |
| iris_binary / mlp_square_linear_score | 5 | 100 / 100 / 0 | 100.00–100.00 | 100.00–100.00 | 92.150–93.986 | one input invocation |
| mnist_10class / mnist_lenet5_small_square_v1 | 1 | 500 / 500 / 0 | 98.60–98.60 | 100.00–100.00 | 3626987.250–3626987.250 | one invocation over batch20 inputs |
| mnist_10class / mnist_mlp_square_784_100_10_v1 | 1 | 500 / 500 / 0 | 97.60–97.60 | 100.00–100.00 | 18094.536–18094.536 | one invocation over batch20 inputs |
| mnist_binary01 / packed_cnn_lite_binary01_v17 | 1 | 250 / 250 / 0 | 99.20–99.20 | 100.00–100.00 | 2321.761–2321.761 | one invocation over batch20 inputs |
| mnist_pool16 / linear_poly3 | 5 | 2500 / 2455 / 45 | 80.20–84.20 | 97.60–99.00 | 149.826–150.135 | one input invocation |
| mnist_pool16 / mlp_square2_linear_score | 5 | 2500 / 774 / 1726 | 85.80–88.80 | 25.60–41.20 | 454.792–455.856 | one input invocation |
| mnist_pool16 / mlp_square_linear_score | 5 | 2500 / 2425 / 75 | 84.40–89.00 | 95.80–97.80 | 179.001–179.639 | one input invocation |
| wdbc / linear_poly3 | 5 | 569 / 562 / 7 | 93.86–99.12 | 97.37–100.00 | 149.717–150.241 | one input invocation |
| wdbc / mlp_square2_linear_score | 5 | 569 / 159 / 410 | 92.98–99.12 | 20.35–42.11 | 453.749–455.540 | one input invocation |
| wdbc / mlp_square_linear_score | 5 | 569 / 560 / 9 | 90.35–99.12 | 97.37–100.00 | 178.987–179.419 | one input invocation |

각 행 시간 범위는 사례별 원시 시간 중앙값의 최솟값–최댓값이다. 서로 다른 데이터셋의 정확도 범위를 하나의 모델 일반화 정답률로 해석하지 않는다. 특히 2층 표형 MNIST 적용774/2500, WDBC159/569는 낮은 적용 범위를 드러낸다. 최저 WDBC 사례의 선택20/114,별도23/113도 `CASE_SCOPE_AND_QUALITY.csv`에 남겼다.

## 6. 분모, 추가63과 깊이5조건

| Role | Case–input pairs | Applicable | Boundary | Key-summed observations | Protected flips / error violations |
| --- | --- | --- | --- | --- | --- |
| Primary selection | 18,385 | 16,081 | 2,304 | 55,155 | 0 / 0 for final selections |
| Primary separate | 18,367 | 16,049 | 2,318 | 55,101 | 0 / 0 |

위 입력은 사례별 입력의 합이다. 같은 원자료 행이 서로 다른 모델/분할·역할에서 재등장한다. `INPUT_UNITS.csv`는 dataset/role 내부 고유 source ID 수를 별도로 제공하며 MNIST의 다른 export 간에도 무조건 독립으로 합하지 않는다. 키3반복과 슬롯 반복은 입력 수나 독립 표본 수를 늘리지 않는다. 경계 결과도 CSV에 보존하되 보호범위 실패와 합치지 않는다. 최종 PDF의 적용 범위를 전역 보장으로 넓히지 않는다.

`ADDITIONAL_63_CASES.csv`의30 body/head 조합+24표형seed+6다중클래스seed+3packedseed=63과 `DEPTH_5_CONDITIONS.csv`의5행은 별개다. run_status의204작업은 주요68+추가63+깊이5+시간68로 일치한다. `ADDITIONAL_63_QUALITY_BY_ROLE.csv`126행과 모델 metadata63행에 이 추가 사례의 저장 평문 정답률·클래스·선택/별도 범위를 별도로 채웠다. 주효과/주요68에 합하지 않았다. 깊이5는 별도 계산 그래프이며 학습된63모델 또는 independent-input audit5개로 바꾸지 않는다.

추가분석의 Banknote `mlp_square_poly3`, fold3/seed0에서는 별도274입력 중 입력1068의 key1만 오차 조건을 위반했다. 평문0.5196440056932156, CKKS0.508866189688053, threshold0.5; 오차0.010777816005162588 > 한계0.00982200284660778이나 둘 다 양성이다. `ADDITIONAL_ERROR_ONLY_CASE.json`이 원시 사건과 연결한다. 이는 충분조건 위반이며 충분조건 자체의 수학적 반례가 아니다. 이 결과를 보고 선택 구성을 변경하지 않았다.

## 7. 기존 비용 계측의 정확한 범위

동결 formal 측정:65표형은 입력별, MLP/LeNet/packed3은 고정20입력 batch invocation별이다. 각 방법 arm은 파라미터 호환 키 문맥을 새로 만들고 같은 블록 안에서 재사용한다. 3키×예비1회 제외×측정6회, 순서교대, 이상치 제거 없음. 실제 총23,454대응비는 입력당 비율23,400과 batch비54를 합한 관측 수이며 독립 표본 수는 아니다.

각 사례의 로그비 평균, 같은 데이터셋–모델 사례의 로그비 평균,16조합을 같은 비중으로 평균한 뒤 exp한 추정치1.000540931232697를 이번 raw에서 재확인했다. 95% CI [0.9999674747655278,1.0011217812090207]는 이미 검증된 기존16조합 bootstrap10,000회/seed20260824 결과를 재사용했다. 통계적 유의차 미검출은 동등성 또는 손해0의 증명이 아니다.

`COST_COMPONENTS_AND_SETUP.csv`136행은68×2arms의 실제 준비비, 인코딩/암호화, 동형연산, 복호화/디코딩, 기록된 adapter I/O, 총시간의 평균과 총시간 중앙값을 제공한다. 평균 분해를 사용해 중앙값끼리 더하는 오류를 피했고, 총시간에서 기록 성분을 뺀 차이는 특정 원인으로 임의 배정하지 않았다. network와 별도 gate 시간은 미측정이다. 로컬 adapter_io의0은 측정 기록의0이며 네트워크0이라는 뜻이 아니다.

예시 Banknote 선택 arm의 준비비는 키 문맥당 평균38.463877ms; 입력당 인코딩/암호화27.077922ms,동형연산25.255139ms,복호화/디코딩11.491638ms,총평균63.832042ms/중앙값63.564785ms다. 키 준비는 총 추론시간에 포함되지 않는다. LeNet은20입력 묶음 중앙값3,626,987.250ms로 실제 비용이 매우 크며, MLP-100은18,094.536ms, packed는2,321.761ms다. 원래 느린 구현의 절대 비용을 생략하거나20입력 batch를 단일 입력 시간으로 보고하지 않는다.

조정21의 최종/초기1.0045077568931444는 선택 단계 평균 추론시간의 사례별 비율 중앙값이다. formal paired CI와 다른 자료이며 후보 간 키·실행 시점이 다르다. 선택 전체 비용은 별도의 stage wall 기록을 사용한다. 공통66사례 direct13,754,260.638ms,finite167,825,454.593ms,합계비12.201706730010272; 사례별 비율 중앙값12.398599026421792,IQR[7.493242059725233,14.95910619899486]. 이 합계는 병렬화된 서비스 완료시간이 아니다.

65표형 direct 타이머는 합성부터 키/실행/조정/결과 쓰기까지 포함하고 입력 준비·contract 구성은 제외한다. packed direct는 plan 합성까지 타이머 밖이라는 차이가 있다. 두 frozen multiclass의 direct stage wall은 미기록이라 양쪽 공통66에서 제외했다. 합성 단독·훈련·전체 준비 비용을0으로 채우지 않았다. 역사적13.8441은 finite68/direct66의 분모 불일치 합계비이므로 주 비교로 쓰지 않는다. 해당 기존 주석 사본과 실제66집계가 함께 제공된다.

## 8. 후속 비교와 이번 원고 보강의 분리

`COMPARISON_EVIDENCE_SCOPE.csv`와 `CLAIM_STATUS_AND_GAPS_KO.md`는 원래 논문의 내부 제거/유한집합/외부 보조 결과와 이미 완료한 후속 비교를 분리한다. 후속 A/B/C와 HEDiff Bank를 다시 실행하지 않았다. A/B 무차이, Bank C 합성 스트레스 실패, 비용 증감의 혼재는 그대로 유지한다. 비용 감소로 판정 개선 미관측을 대체하지 않는다.

기존 원문 검토의 FHE-Agent2511.18653v1 §4.1/§4.3 활성화 고정 정정을 재사용했다. §5.3의 판본 내 불일치와 실제 구현 미확인은 유지한다. HECATE/FHE-Agent처럼 정확성을 선택 제약으로 쓰는 연구와 HEDiff처럼 판정 이탈을 검사하는 연구를 배제하지 않는다. 새 기능/미지원 여부를 추가로 단정하지 않아 이번 전수 문헌검색·설치·외부 호출은 필요하지 않았다.

C′ 정책과 C/C′/B30 계획은 이전 FOLLOWUP_SEPARATE에 확보 완료다. 이번에 다시 도입 경위를 탐색하거나 구현/활성화하지 않았다. logN 동일성이 실제 같은 비용이라는 보장은 없고, 미실행 Bank S33을 선택 결과로 쓰지 않는다. 예약684의 실제 행·label·score·margin은 읽지 않았다.

## 9. 재집계 명령과 파일 역할

이번 실제 실행 명령은 모두 `/home/ckks2/deciprotect`에서 수행한 아래 세 스크립트다. 각 파일은 Python 표준 라이브러리만 사용하고 CKKS/모델 학습 모듈을 import하지 않는다.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/analyze_journal_evidence_v1.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/collect_journal_evidence_details_v1.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/collect_journal_additional_quality_v1.py
```

기존 산출물에 같은 명령을 재실행하면 배타적 생성(`open x`)이 덮어쓰기를 거부한다. 재현 시에는 충돌하지 않는 새 폴더를 **먼저** 만들고 출력 경로를 지정한다. 예시 명령은 이번에 다시 실행하지 않았다.

```bash
cd /home/ckks2/deciprotect
export FG_EVIDENCE_DOC=/home/ckks2/deciprotect/docs/research/fg_journal_evidence_replay_run02
export FG_EVIDENCE_RUN=/home/ckks2/deciprotect/results/fg_journal_evidence_replay_run02
mkdir "$FG_EVIDENCE_DOC"
mkdir "$FG_EVIDENCE_RUN"
mkdir "$FG_EVIDENCE_DOC/evidence_tables" "$FG_EVIDENCE_DOC/source_excerpts"
PYTHONDONTWRITEBYTECODE=1 python3 scripts/analyze_journal_evidence_v1.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/collect_journal_evidence_details_v1.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/collect_journal_additional_quality_v1.py
```

생성 경로는 지정된 DeciProtect docs/research와 results 아래만 허용한다. 보충 ZIP은 보고서·전체626행 후보 명세·집계·필요 발췌와 검증 코드를 담고, 원래 대량 raw와 데이터셋 전체는 넣지 않는다. 따라서 ZIP만으로 CKKS 실험을 재실행할 수 있다고 하지 않는다. 위 집계 재현에는 manifest에 지정한 원래 로컬 raw/모델 파일이 필요하다. 상세 Q/P 소수 재생성이나 암호화 명령은 이번 실행 목록에 없다.

초기 분석은 다중 클래스 alias 조인 두 위치에서 중단됐으며 `ATTEMPT_01.json`과 `analysis_attempt_02/FAILURE.json`에 보존했다. 원시 파일이나 불리한 과학적 결과를 버린 것이 아니라 동일 frozen 사례 명칭을 연결한 집계 프로그램의 오류 수정이다. 최종 검증은 수정 후 전체 사례로 완료했다. 분석 후 출력 경로 환경변수만 추가했으며 산술·집계 규칙은 유지했다.
