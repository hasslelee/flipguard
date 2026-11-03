# FlipGuard V34 Required Code Audit

## 1. 최종 판정

**PASS WITH CHANGES**

- Severity: `BLOCKING=0`, `MAJOR=0`, `MINOR=4`
- 감사 대상: primary run `v17_final_vm1x6_20260811T050104Z`, scientific execution source `cefc44b0d7e351db2a34886dd758a2d31a3e4c12`
- 방법: production source, final binding, immutable sample/key ledgers와 paired-latency 원시 record를 read-only로 검사하고 별도 Python 구현으로 재집계하였다.
- 새 CKKS 암호화 실행: `0`
- source/frozen evidence 수정: `0`
- commit/push: `0`

네 가지 MINOR는 (1) `68/68 SAFE`의 `V_delta` 범위 명시, (2) 16개 클러스터 동일 가중 지연 시간 추정량의 정확한 표기, (3) EVA S20의 `133/1,500 observations`와 `114/500 inputs` 분리, (4) as-run 기준 HEAD와 source-closure/aggregation commit의 역할 분리다. 핵심 수치나 알고리즘의 CODE MISMATCH는 발견되지 않았다.

V33 PDF는 참고물로만 해시를 확인했다: `/home/ckks2/Downloads/CKKS_정보보호학회논문지_전체적용_2단예시_v33.pdf`, `sha256:6b5ec1ac06e859c5530d9827ab243165f64c16f31b7d7c3fbfe9b71a4e3cde42`. 지시대로 원고 문체 감사나 원고 부재 판정은 수행하지 않았다.

## 2. coverage 정확한 수치

`V_delta={x: margin(x)>delta}`, `delta=0.001`이다. 입력 수는 `case_id x row_id`로 세고 세 key repeat는 중복하지 않았다.

| stage / task | cases | |V| | |V_delta| | boundary | pooled coverage | case min / median / max | 100% / <100% / empty |
|---|---|---|---|---|---|---|---|
| selection / all | 68 | 18385 | 16081 | 2304 | 0.874680446015774 | 0.175438596491228 / 0.991228070175439 / 1.000000000000000 | 28 / 40 / 0 |
| selection / binary | 66 | 17385 | 15081 | 2304 | 0.867471958584987 | 0.175438596491228 / 0.991228070175439 / 1.000000000000000 | 26 / 40 / 0 |
| selection / multiclass | 2 | 1000 | 1000 | 0 | 1.000000000000000 | 1.000000000000000 / 1.000000000000000 / 1.000000000000000 | 2 / 0 / 0 |
| separate / all | 68 | 18367 | 16049 | 2318 | 0.873795393912996 | 0.203539823008850 / 0.994436706901888 / 1.000000000000000 | 31 / 37 / 0 |
| separate / binary | 66 | 17367 | 15049 | 2318 | 0.866528473541775 | 0.203539823008850 / 0.994428969359331 / 1.000000000000000 | 29 / 37 / 0 |
| separate / multiclass | 2 | 1000 | 1000 | 0 | 1.000000000000000 | 1.000000000000000 / 1.000000000000000 / 1.000000000000000 | 2 / 0 / 0 |

- 최저 사례는 `primary|wdbc|mlp_square2_linear_score|outer_fold_4_training_seed_0`이다. selection은 `20/114=0.17543859649122806`, separate는 `23/113=0.20353982300884957`이다.
- 기존 separate 크기 분포 `20x10, 113x3, 114x12, 250x1, 274x9, 275x6, 359x6, 360x4, 500x17`을 원시 ledger에서 그대로 재현했으며 합은 `18,367`이다.
- 이진 selection은 `15,081/17,385=0.867471958584987`, separate는 `15,049/17,367=0.8665284735417746`이다. 다중 클래스 두 사례는 두 stage 모두 `1,000/1,000=1.0`이다.
- 다중 클래스 margin은 평문 top-1 logit과 가장 큰 경쟁 logit 사이의 top-two gap이다. 이는 모든 competitor 중 top-1과의 최소 gap과 같다. 다만 각 class의 관측 오차가 다르므로 적합 판정은 모든 `j != c*`에 대해 `z_c*-z_j > |Delta_c*|+|Delta_j|`를 검사한다.
- 평문 tie는 가장 낮은 class index로 결정적으로 반환되지만 `V_amb`로 분류한다. `NaN`/`Inf` plaintext 또는 CKKS logit은 입력 검증 오류로 fail closed하며 coverage 값으로 흡수하지 않는다.
- boundary(`margin<=delta`)는 `|V|`와 coverage 분모에는 포함하지만 판단 반전/운용 예산 위반 및 SAFE claim의 분자에는 포함하지 않는다.
- `68/68 separate SAFE`는 모든 사례에서 `V_delta`가 비어 있지 않고, 그 안의 모든 입력과 세 key repeat가 판단 반전 및 운용 예산 위반 없이 통과했다는 뜻이다.

상세 136행은 `v34_primary_coverage_by_case.tsv`에 있다.

## 3. 초기 구성 알고리즘

### Production 경로

1. model registry로 linear/1-hidden-square/2-hidden-square body와 affine/cubic head를 exact scalar IR로 만든다 (`cefc44b0d7e351db2a34886dd758a2d31a3e4c12:internal/ckksplanner/tabular_contract.go:546-637`).
2. selection 입력을 key 생성 전에 평문으로 실행하고, 각 노드의 실제 관측 min/max와 출력 margin을 계산한다 (`internal/analysis/bounds.go:44-105`). 이는 interval propagation이 아니다.
3. `margin>delta`인 입력 중 최소 margin을 구한다. 없으면 contract 생성 오류로 종료한다 (`tabular_contract.go:208-233`).
4. 출력에서 민감도 1로 시작해 DAG를 역순으로 전파한다. 동일 노드가 여러 경로에서 재사용되면 `+=`로 영향을 합산한다 (`bounds.go:127-218`).
5. 이진 `S_G`는 input/const를 제외한 모든 연산 노드의 역방향 민감도 합이다 (`tabular_contract.go:1131-1145`). 다중 클래스 MLP/LeNet은 별도 layerwise L-infinity norm x primitive-count 합을 사용하며 generic multi-output sum/max/matrix norm은 아니다 (`internal/journalmnist/calibration.go:24-167`).
6. 이진은 `B_out=rho*gamma_min`, 다중 클래스는 logit별 `B_out=rho*g_min/2`를 만든다.
7. `B_unit=B_out/S_G`, `p=0` if `B_unit>=1`, otherwise `p=ceil(-log2 B_unit)`로 두고 `s=max(p+3,18,s_requested)`를 선택한다. `s>50`이면 clamp하지 않고 실패한다.
8. Q/P chain을 만들고 slot 및 declared `log2(QP)`를 만족하는 최소 `log2 N`을 Security-V2 envelope에서 고른 뒤 Q와 QP를 재검사하고 backend profile을 materialize한다.
9. retryable prime-generation failure일 때만 scale을 1 bit씩 올려 재materialize하며 최대 50 bit를 넘으면 실패한다. 이 static retry는 encrypted candidate evaluation이 아니다.

V17 primary `selection.json` 66개의 policy는 모두 `precision_slack_mode=none`이었다. 따라서 초기 후보는 같은 보안 tier 안에서 더 큰 scale을 탐색하지 않고, 분석식과 backend materialization이 요구하는 최소 scale을 사용했다. 해당 plan에 기록된 Direct Policy V2 digest는 `sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603`, Security Policy V2 digest는 `sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055`다.

### 계산 그래프에서 수집하는 정보

- exact DAG에서 `Input`, `Const`, `Add`, `Sub`, `MulConst`, `Mul`, `Pow2`, `Pow3`, `Poly`를 식별하고 연산 수와 최장 multiplicative depth를 계산한다 (`tabular_contract.go:1069-1128`). 다만 production rescale tracer는 standalone `Pow3`를 실행 가능하다고 인정하지 않고, `Poly`는 degree 3에만 한정한다 (`1160-1308`). 즉 graph summary에서 인식하는 operation과 backend에서 materialize 가능한 operation을 구분한다.
- rescale 요구량은 단순히 graph depth와 동일시하지 않고, Lattigo v6 scale exponent trace에서 `LevelsConsumed`c640 terminal exponent를 계산해 `RequiredQPrimes=LevelsConsumed+ScaleExponent`로 만든다 (`1160-1166`, `1303-1308`).
- 요구 slot, packing strategy와 rotation은 각 adapter contract에서 받는다. scalar tabular graph의 sensitivity IR에는 rotation이 없으며, packed CNN-lite의 rotation 수와 key는 adapter/backend graph facts에 별도 고정된다.
- 가중치와 다항식 계수는 `model.json`에서 exact coefficient로 IR에 들어간다. planner가 별도의 전역 “weight range” 통계를 만드는 것은 아니며, `MulConst`는 실제 계수의 절대값을 민감도에 사용한다. plaintext magnitude는 selection 평문 실행에서 관측한 노드별 min/max와 최대 output 절대값으로 기록한다 (`internal/analysis/bounds.go:44-105`).
- 알 수 없는 op, 비위상 DAG, plaintext-only 연산, 비지원 다항식 차수는 fallback으로 교체하지 않고 오류로 fail closed한다 (`tabular_contract.go:1111-1115`, `1213-1217`, `1260-1290`).

초기 분석 scale의 핵심 식은 다음과 같다.

```text
B_out  = rho * gamma_min                       (binary)
B_out  = rho * g_min / 2                       (multiclass, per logit)
B_unit = B_out / S_G
p      = 0, if B_unit >= 1; otherwise ceil(-log2(B_unit))
s_0    = max(18, p + 3)
```

Q/P 규칙은 `message_bits=ceil(log2(max(1,max_abs_plain_output)))`, `q_0=max(18,s+message_bits+1+2)`, 나머지 Q 소수는 `s` bit, Q 개수는 `required_Q_primes+level_guard+extra_levels`, P는 `max(30,q_0)` bit 소수 하나다. 별도 last-Q 규칙은 없다.

Security-V2 envelope의 지원 `log2 N`과 최대 `log2(QP)`는 각각 `(12,106)`, `(13,214)`, `(14,430)`, `(15,868)` bit이다. planner는 요구 slot과 QP cap을 동시에 만족하는 최소 N을 고르며, 지원 범위에 없으면 fail closed한다.

### 역방향 민감도 규칙

| op | input sensitivity increment |
|---|---|
| add/sub | 양쪽에 `S_out`을 더함 |
| multiply by constant `a` | `|a| S_out` |
| multiply `u*v` | `u`에 `max|v| S_out`, `v`에 `max|u| S_out` |
| square `u^2` | `2 max|u| S_out` |
| cube `u^3` | `3 (max|u|)^2 S_out` |
| polynomial | 관측 구간에서 계산한 `max|p'(u)| S_out`; cubic은 endpoints와 derivative critical point 사용 |
| affine/weighted sum | `MulConst`와 `Add`의 조합으로 위 규칙 적용 |
| square activation | `Pow2` 규칙 적용 |
| rotation/slot | scalar sensitivity IR에 없고 adapter graph facts/packing 요구로 별도 반영 |

IR sensitivity 함수는 `Pow3`도 정의하지만 production tabular cubic head는 `Poly`로 materialize한다. 현재 rescale scale tracer는 standalone `Pow3`, degree!=3 polynomial, unknown op를 지원하지 않으며 fallback 없이 오류로 종료한다 (`tabular_contract.go:1260-1290`). 따라서 이 계산은 **분석적 오차 보증이 아니라 초기 후보 생성을 위한 경험적 추정**이다. 실제 encrypted admission이 최종 판정을 담당한다.

### Algorithm 1 (원고용)

```text
Input: graph G, selection set V, rho, delta, Direct Policy V2, Security-V2
1: Materialize exact plaintext DAG and reject unsupported operations.
2: Evaluate V in plaintext; collect observed node ranges and eligible margins.
3: If V_delta is empty, stop fail closed.
4: Back-propagate local sensitivities and compute aggregate signal S_G.
5: Compute B_out, B_unit, precision p, and initial scale s.
6: Derive Q/P from scale and rescale demand.
7: Select the minimum admitted log2 N satisfying slots and QP security.
8: Materialize the backend profile; fail closed if no profile is admitted.
9: Return the single initial candidate for bounded encrypted validation.
```

## 4. Q 확장 후 log2 N 전이

판정은 **A**다. `RepairLevelFailure`는 `extraLevels`를 1 늘리고 전체 candidate construction/materialization 함수를 다시 호출한다 (`synthesis.go:407-488`). 이 함수는 늘어난 Q chain으로 declared `log2(QP)`를 다시 계산하고, 요구 slot과 함께 최소 admitted `log2 N`을 다시 탐색한 뒤 `AssessSecurity`로 ciphertext Q와 evaluation-key QP를 모두 검사한다 (`654-769`, `946-977`). 현재 N이 더 이상 맞지 않으면 더 큰 지원 N이 선택되며, 지원 범위 안에 적합한 N이 없으면 repair exhaustion이 되어 executor가 `NO_SAFE`를 반환한다.

실패한 기존 encrypted candidate는 이미 최대 후보 평가 수 `B=4`에 포함된다. repair materialization 자체는 encrypted 평가가 아니며, 다음 후보가 실제 실행될 때 새 평가 1회로 센다 (`executor.go:432-486`). 따라서 Fig. 3의 “Stage 2 전체로 복귀”는 Stage 2를 candidate construction/materialization/security admission으로 정의할 때만 정확하다. 평문 graph range와 sensitivity calibration까지 다시 계산하지는 않는다.

Pure targeted test `TestSynthesizeRaisesLogNWhenModulusRequiresIt`와 `TestRepairCandidateIsMonotoneAndFeedbackDriven`이 PASS했다. 전자는 더 긴 QP가 필요할 때 `log2 N=14`로 상승함을, 후자는 level repair가 scale을 유지하며 Q 소수 하나만 추가함을 검사한다. 주 평가 68개 원시 trial에서는 `analysis_minimum=68`, `repair_scale_1=21`, `repair_level=0`이었다.

## 5. 지연시간 통계량과 16개 cluster

원시 짝 `r_ij=T_finite/T_direct`에서 사례별 `R_i=exp(n_i^-1 sum_j log r_ij)`를 먼저 계산한다. 클러스터 `C_k`마다 `G_k=exp(|C_k|^-1 sum_{i in C_k} log R_i)`를 만들고 최종 점추정량은

```text
R_hat = exp((1/16) * sum_{k=1}^{16} log G_k)
```

이다. 즉 전체 latency 합의 비율도, 68개 비율의 산술평균도, 68개 비율을 동일 가중한 기하평균도 아니다. 마지막 값은 별도로 `1.0005872532925908`이며 보고 추정량과 다르다.

원시 결합은 tabular 65사례의 `20 inputs x 3 keysets x 6 passes = 360 pairs/case`와 MLP-100/LeNet/Packed CNN-lite의 `3 keysets x 6 whole-20-input-batch passes = 18 pairs/case`로, `65x360+3x18=23,454`다. input, key, pass는 사례 내부 반복이며 독립 통계 표본으로 승격하지 않는다.

| dataset | model | cases | raw pairs | cluster GM |
|---|---|---|---|---|
| banknote | linear_poly3 | 5 | 1800 | 1.001565108123881 |
| banknote | mlp_square2_linear_score | 5 | 1800 | 1.000517920759221 |
| banknote | mlp_square_linear_score | 5 | 1800 | 0.999257682949791 |
| digits_binary | linear_poly3 | 5 | 1800 | 1.000706716980340 |
| digits_binary | mlp_square_linear_score | 5 | 1800 | 1.000991841793039 |
| iris_binary | linear_poly3 | 5 | 1800 | 1.002735626557923 |
| iris_binary | mlp_square_linear_score | 5 | 1800 | 0.999510693277765 |
| mnist_pool16 | linear_poly3 | 5 | 1800 | 1.000140387012544 |
| mnist_pool16 | mlp_square2_linear_score | 5 | 1800 | 1.000198201716239 |
| mnist_pool16 | mlp_square_linear_score | 5 | 1800 | 1.001520399048053 |
| multiclass | mnist_lenet5_small_square_v1 | 1 | 18 | 0.999921124002637 |
| multiclass | mnist_mlp_square_784_100_10_v1 | 1 | 18 | 1.002794167833737 |
| packed_cnn_lite_binary01_v17 | packed_cnn_lite_binary01_v17 | 1 | 18 | 0.998125690307491 |
| wdbc | linear_poly3 | 5 | 1800 | 1.000736025814053 |
| wdbc | mlp_square2_linear_score | 5 | 1800 | 1.000410151160136 |
| wdbc | mlp_square_linear_score | 5 | 1800 | 0.999534357188899 |

Bootstrap은 위 16개 `G_k`를 replacement로 16개 다시 뽑는다. 원래 클러스터의 모든 사례는 `G_k` 계산에 포함되어 있고, 같은 클러스터가 여러 번 뽑히면 그 scalar `G_k`가 뽑힌 횟수만큼 가중된다. 각 반복에서 16개 sampled cluster 값의 기하평균을 다시 계산한다. seed `20260824`, 10,000회이며 정렬된 bootstrap 값에서 `(n-1)q` 위치를 선형 보간한 percentile 2.5%/97.5% 구간이다.

독립 raw 재계산 결과는 `R_hat=1.000540931232697`, 95% CI `[0.9999674747655278, 1.0011217812090207]`로 frozen 값과 정확히 일치했다. 비율이 1보다 크면 동일 paired boundary에서 finite-reference total latency가 direct보다 크다는 뜻이지만 CI가 1을 포함하므로 우월성은 주장하지 않는다.

## 6. 모델 계열별 68개 구성

| family | cases | datasets | architecture / activation / head | selection inputs | separate inputs | model status |
|---|---|---|---|---|---|---|
| Polynomial model | 25 | banknote, digits_binary, iris_binary, mnist_pool16, wdbc | input 4-16; scalar score; cubic output polynomial 0.5+0.197z-0.004z^3; cubic scalar score | 6345 total (20-500/case) | 6338 total (20-500/case) | retrained independently in each outer fold |
| 1-layer MLP | 25 | banknote, digits_binary, iris_binary, mnist_pool16, wdbc | input 4-16 -> hidden 4 -> scalar score; square; affine score 0.5+0.197z | 6345 total (20-500/case) | 6338 total (20-500/case) | retrained independently in each outer fold |
| 2-layer MLP | 15 | banknote, mnist_pool16, wdbc | input 4-16 -> hidden 8 -> hidden 4 -> scalar score; square after each hidden affine; affine score 0.5+0.197z | 4445 total (114-500/case) | 4441 total (113-500/case) | retrained independently in each outer fold |
| MLP-100 | 1 | mnist_10class | 784 -> 100 -> 10 logits; square; 10 affine logits | 500 total (500-500/case) | 500 total (500-500/case) | one frozen pretrained artifact |
| LeNet-5-small | 1 | mnist_10class | 1x28x28 (zero-padded 32x32) -> 10 logits; square after both convolutions and FC120/FC64; 10 affine logits | 500 total (500-500/case) | 500 total (500-500/case) | one frozen pretrained artifact |
| Packed CNN-lite | 1 | mnist_binary01 | one image in 16 spatial slots; four 3x3 activation maps -> scalar; square; affine scalar score | 250 total (250-250/case) | 250 total (250-250/case) | one frozen pretrained artifact |

잠정 집계 `25+25+15+1+1+1=68`은 final case binding과 정확히 일치했다. P1-P3는 각 outer fold에서 재학습되었고, P4/P5/P6는 한 frozen pretrained artifact를 사용했다.

Packed CNN-lite는 4x4 영상 하나를 16개 연속 spatial slot에 저장한다. 실행은 convolution offset `1,4,5`의 3회 rotation과 spatial reduction offset `1,2,4,5,6,8,9,10`의 8회 rotation, 합계 11회다. 필요한 unique rotation key 목록은 `[1,4,5,2,6,8,9,10]` 8개다. LeNet-5-small은 feature ciphertext/sample-slot batching이며 spatial rotation graph는 아니다.

## 7. EVA S20 정의

`S20`은 `EvaProgram.set_input_scales(20)`으로 지정한 **EVA 초기 입력 scale 20 bit**를 뜻한다. 보안 bit나 generic modulus profile 이름이 아니다. 같은 compiler가 output range 20도 설정하지만 arm 명명과 candidate ID의 S20은 input scale parameter에서 온다 (`scripts/external_v8/run_eva_shared_polynomial_v8.py:47-70,179-191`). materialized candidate는 `eva_v8_scale20_N13_QP140_3fc14b392a39`다.

S20은 configuration-validation 고유 입력 500개를 독립 context 3개에서 한 batch씩 실행해 `1,500` input-context observations를 만들었다. 판단 반전은 `133/1,500 observations`이고, 적어도 한 context에서 반전된 고유 입력은 `114/500 inputs`다. 96개 입력은 1 context, 17개는 2 contexts, 1개는 3 contexts에서 반전되었다. reserve-policy violation은 794/1,500이었다.

S20은 validation에서 REJECTED되어 locked audit을 수행하지 않았다. frozen audit arm은 사전 선택 S30과 comparator S40이었다. 이 결과는 native EVA/SEAL, shared-polynomial workload, EVA 고유 compiler/materialization과 runtime security 해석을 사용하므로 V17 direct 주 평가와 동일 조건의 latency baseline이 아니다.

원고 최초 등장 문장: **“EVA S20은 보안 수준이 아니라 EVA 프로그램의 초기 입력 scale을 20 bit로 둔 native EVA/SEAL 구성으로, 500개 구성-선택 입력을 세 독립 context에서 실행한 1,500개 관측 중 133회 판단 반전이 발생했다.”**

## 8. 환경·commit

| item | exact value |
|---|---|
| run ID | `v17_final_vm1x6_20260811T050104Z` |
| guest | Ubuntu 24.04.4 LTS; kernel 7.0.0-28-generic |
| CPU | VMware 1 socket x 6 cores, 6 vCPU; affinity 0-5; GOMAXPROCS 6 |
| memory | 16324060 KiB (15.568 GiB) |
| Go | 1.25.9 |
| Python | 3.12.3 |
| Lattigo | 6.2.0 |
| NumPy | 2.2.6 (frozen scientific protocol) |
| scikit-learn | 1.6.1 (frozen scientific protocol) |
| as-run manifest Git HEAD | `c550185c753220b8b5c0a5d9d2e922496d543414` |
| exact as-run source closure commit | `cefc44b0d7e351db2a34886dd758a2d31a3e4c12` |
| post-run aggregation tooling commit | `86b0403208abbc741a65934358a5dea4a66e4d88` |
| current editorial HEAD | `67251c57ca7be5aa8aeffd746a6a6671685e98c5` |

Run manifest의 `Git_HEAD=c550185...`는 실행 당시 기준 commit이고, 당시 작업 트리의 exact as-run source는 후속 역할 분리 commit `cefc44b...`에서 추적되었다. paired-latency 결합의 variable-shadowing 수정과 regression test는 `86b0403...`에 별도 기록되었다. 결과를 후속 source에 소급 결속하지 않는다.

V18 protocol/evidence/paper-facts verifier는 모두 PASS했다. V17 release-R3 verifier는 payload mismatch가 아니라 현재 editorial branch HEAD가 verifier에 고정된 `86b0403...`이 아니어서 `repository HEAD moved`에서 중단했다. 이는 현재 evidence 수치 불일치가 아니라 branch-position-sensitive release verifier의 추적성 제약이다.

## 9. V34 원고에 그대로 붙일 한국어 문장

### Coverage

구성-선택 단계의 68개 사례는 사례-입력 쌍 18,385개 중 마진이 경계 하한을 초과한 16,081개를 적합 판정 대상으로 사용하여 pooled coverage 0.874680을 보였다. 별도 입력 재평가에서는 18,367개 중 16,049개가 적합 판정 대상이었고 pooled coverage는 0.873795였다. 68/68 SAFE는 각 사례의 이 적합 판정 대상에서 세 키 반복 모두 판단 반전과 운용 예산 위반이 없었다는 유한 범위의 결과이며, 경계 입력이나 전체 입력 분포에 대한 보장을 뜻하지 않는다.

### 초기 구성

FlipGuard는 구성-선택 입력의 최소 적격 결정 마진에 rho를 곱해 출력 오차 허용량을 만들고, 이를 계산 그래프의 경험적 민감도 S_G로 나눈 단위 오차 예산에서 필요한 정밀도 p를 산출한다. 초기 scale bit는 s=max(18, ceil(-log2(B_out/S_G))+3)으로 정하되 단위 오차 예산이 1 이상이면 p=0으로 둔다. 이 값은 암호화 검증 전 첫 후보를 만드는 경험적 계획 신호이며 분석적 CKKS 오차 증명은 아니다.

### Q 소수 추가 보정

level 또는 rescale 부족이 관측되면 정책은 Q 소수 하나를 추가한 후보를 다시 구성하고, 늘어난 QP 크기와 slot 요구를 함께 사용해 목표 보안 정책을 만족하는 최소 log2 N을 다시 선택한다. 이어 ciphertext Q와 evaluation-key QP를 모두 재검사하며, 적합한 N이 없으면 보정을 중단하고 NO_SAFE를 반환한다. 주 평가 68개 사례에서는 이 level 보정이 발생하지 않았고, 관측된 21개 추가 평가는 모두 scale을 4 bit 늘린 수치 보정이었다.

### 지연 시간

각 사례에서는 짝지은 원시 지연 시간의 유한 기준 구성/제안 구성 비율을 기하평균한 뒤, 동일 데이터셋-모델 조합 16개 클러스터마다 사례 비율을 다시 기하평균하였다. 최종 점추정량은 16개 클러스터 요약값의 동일 가중 기하평균으로 1.000540931이었고, 클러스터를 복원 추출한 10,000회 percentile bootstrap의 95% 신뢰구간은 [0.999967475, 1.001121781]이었다. 비율이 1보다 크면 기준 구성의 total latency가 더 크다는 뜻이지만, 이 구간은 1을 포함하므로 지연 시간 우월성을 주장하지 않는다.

### 모델 구성

주 평가 68개 사례는 다항식 모델 25개, 1층 square-activation MLP 25개, 2층 square-activation MLP 15개와 MNIST MLP-100, LeNet-5-small, packed CNN-lite 각 1개로 구성하였다. 앞의 세 tabular 계열은 outer fold마다 재학습했고, 뒤의 세 계열은 frozen pretrained artifact를 사용하였다.

### EVA S20

EVA S20은 보안 bit가 아니라 EVA 프로그램의 초기 입력 scale을 20 bit로 설정한 native EVA/SEAL 구성이다. 구성-선택 입력 500개를 세 독립 context에서 실행한 1,500개 관측 중 133회 판단 반전이 발생했으며, 적어도 한 번 반전된 고유 입력은 114개였다.

### 범위

민감도와 초기 scale 계산은 첫 후보 생성을 위한 경험적 계획 신호이며 분석적 CKKS 오차 certificate가 아니다. SAFE 결과는 선언된 `V_delta`, 세 키 반복, 지원 adapter와 Security-V2 정책 범위에 한정되고 미래 입력 분포나 전역 최적성을 보장하지 않는다.

## 10. 기존 예상값과 다른 항목

핵심 기대값과 독립 재계산 결과의 수치 불일치는 없다. 다만 원고 작성 시 다음 차이를 정확히 반영해야 한다.

1. 보고 지연 시간 점추정량은 68개 사례비의 단순 기하평균 `1.0005872532925908`이 아니라 16개 클러스터 동일 가중 기하평균 `1.000540931232697`이다.
2. EVA S20의 133은 `133/1,500 observations`이며, 고유 입력 기준은 별도 `114/500 inputs`다.
3. 이진 `S_G`의 operation-node DAG 합산과 다중 클래스의 adapter-specific layerwise L-infinity 합산은 같은 집계식이 아니다.
4. Q 추가 repair는 코드에 존재하고 log2 N/security를 재선택하지만, 주 평가 68개에서 관측된 Q 추가는 0회다.
5. `68/68 SAFE`의 분모는 사례 수이며, 각 사례 내부 claim은 `V_delta`에만 적용된다. boundary input은 coverage 분모에는 남지만 실패 판정에서는 제외된다.
6. 실행 당시 manifest HEAD `c550185...`, exact source closure `cefc44b...`, post-run aggregation fix `86b0403...`은 서로 다른 역할이다.
