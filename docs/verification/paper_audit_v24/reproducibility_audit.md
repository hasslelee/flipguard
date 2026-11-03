# FlipGuard 논문 V24 재현성 감사

## 1. 전체 판정: PASS WITH NOTES

22개 고정 수치는 모두 동결된 V17/V18 자료와 일치했다. 다만 원고에는 (1) 별도 입력 전체 재평가와 20개 지연시간 부분집합의 구분, (2) `V_delta`에서 제외되는 경계 입력의 규모, (3) 키 생성의 소스 수준 fresh-context 근거와 저수준 난수 provenance의 한계를 명시해야 한다.

## 2. 논문 고정 수치별 PASS/FAIL 표

| 번호 | 논문 주장 | 주장값 | 독립 검산값 | 판정 | 근거 |
|---:|---|---|---|---|---|
| 1 | 주요 평가 사례 | `68` | `68` | PASS | `docs/reports/comparison_extension_v18/PRIMARY_68_CASE_INVENTORY.csv` |
| 2 | gate-off 초기 후보 평가 | `68` | `68` | PASS | `docs/reports/comparison_extension_v18/PRIMARY_68_CASE_INVENTORY.csv` |
| 3 | 전체 기법 후보 평가 | `89` | `89` | PASS | `results/model_family_expansion_v17/final_vm1x6/table_04_direct_vs_exhaustive.csv` |
| 4 | 유한 비교 후보 평가 | `537` | `537` | PASS | `results/model_family_expansion_v17/final_vm1x6/table_04_direct_vs_exhaustive.csv` |
| 5 | 별도 입력 재평가 기록 | `68` | `68` | PASS | `results/model_family_expansion_v17/final_vm1x6/table_04_direct_vs_exhaustive.csv` |
| 6 | 공식 짝지은 지연시간 기록 | `68` | `68` | PASS | `results/model_family_expansion_v17/final_vm1x6/table_05_formal_paired_latency.csv` |
| 7 | 초기 후보 교차표 (47/0/1/20; union 21) | `[47, 0, 1, 20, 21]` | `[47, 0, 1, 20, 21]` | PASS | `docs/reports/comparison_extension_v18/PRIMARY_68_CASE_INVENTORY.csv` |
| 8 | 문제 사례의 추가 평가 1회 | `21` | `21` | PASS | `docs/reports/comparison_extension_v18/PRIMARY_68_CASE_INVENTORY.csv` |
| 9 | 문제 사례 scale +4 bit | `21` | `21` | PASS | `docs/reports/comparison_extension_v18/PRIMARY_68_CASE_INVENTORY.csv` |
| 10 | Q-chain/LogN 변경 사례 | `[0, 0]` | `[0, 0]` | PASS | `docs/reports/comparison_extension_v18/PRIMARY_68_CASE_INVENTORY.csv` |
| 11 | 최종 별도 입력 SAFE | `68` | `68` | PASS | `results/model_family_expansion_v17/final_vm1x6/table_04_direct_vs_exhaustive.csv` |
| 12 | 적합 후보 누락 | `0` | `0` | PASS | `results/model_family_expansion_v17/final_vm1x6/table_04_direct_vs_exhaustive.csv` |
| 13 | 후보 평가 감소율 | `0.8342644320297952` | `0.8342644320297952` | PASS | `results/model_family_expansion_v17/final_vm1x6/table_04_direct_vs_exhaustive.csv` |
| 14 | finite/proposed 총 지연시간 비율과 CI | `[1.000540931232697, 0.9999674747655278, 1.0011217812090207]` | `[1.000540931232697, 0.9999674747655278, 1.0011217812090207]` | PASS | `raw paired_latency.json files listed by table_05_formal_paired_latency.csv` |
| 15 | 변경 21건 관측 지연시간 비율 median/p90 | `[1.0045077568931444, 1.0112181988336308]` | `[1.0045077568931444, 1.0112181988336308]` | PASS | `docs/reports/comparison_extension_v18/PAPER_FACTS_V18_LOCKED.json` |
| 16 | formal latency regret median/p90/max | `[-0.00015323624671320646, 0.0014261898161542356, 0.002309669255065927]` | `[-0.00015323624671320646, 0.0014261898161542356, 0.002309669255065927]` | PASS | `results/model_family_expansion_v17/final_vm1x6/table_06_latency_regret.csv` |
| 17 | 전체 선택 사례 | `131` | `131` | PASS | `results/model_family_expansion_v17/final_vm1x6/table_03_decision_stability.csv` |
| 18 | 공개 음성 사례와 상세값 | `[1, 0, 1, '1068', 0.010777816005162588, 0.00982200284660778]` | `[1, 0, 1, '1068', 0.010777816005162588, 0.00982200284660778]` | PASS | `results/model_family_expansion_v17/runs/v17_final_vm1x6_20260811T050104Z/ablation/banknote/mlp_square_poly3/fold_3/training_seed_0/direct_independent_evaluation.json` |
| 19 | D1-D8 Q-chain 길이 | `[2, 3, 5, 8, 11]` | `[2, 3, 5, 8, 11]` | PASS | `results/model_family_expansion_v17/final_vm1x6/table_10_depth_ladder.csv` |
| 20 | D1-D8 LogN | `[12, 12, 13, 14, 14]` | `[12, 12, 13, 14, 14]` | PASS | `results/model_family_expansion_v17/final_vm1x6/table_10_depth_ladder.csv` |
| 21 | 전체 파라미터 조합 | `16` | `16` | PASS | `results/model_family_expansion_v17/final_vm1x6/table_07_selected_configurations.csv` |
| 22 | 주요 평가 파라미터 조합 | `7` | `7` | PASS | `results/model_family_expansion_v17/final_vm1x6/table_07_selected_configurations.csv` |

## 3. 발견한 불일치

- **수치 불일치:** 없음.
- **방법 설명 보정 필요:** 별도 입력 재평가는 사례마다 20개가 아니다. 20개는 formal paired latency에 사용한 고정 부분집합이다. 65개 tabular 사례의 전체 별도 입력은 outer test fold이며 크기가 데이터셋별로 다르고, MLP-100/LeNet-5-small은 각각 500개, packed CNN-lite는 250개다.
- **추론 범위 보정 필요:** SAFE/REJECTED의 flip·오차 위반 집계는 `V_delta`(`margin > 0.001`)에 한정된다. 경계 입력은 실패로 세지 않고 `V_amb`로 별도 집계한다.
- **재현성 한계:** 코드는 각 반복에서 fresh CKKS context/key set을 생성하지만 key fingerprint 또는 RNG seed를 결과에 기록하지 않는다. 따라서 소스 수준의 fresh-key 생성은 확인되나 난수 스트림 독립성을 결과 JSON만으로 재검증할 수는 없다.
- **선택 wall-clock 범위:** finite/full 사례별 wall-clock 비율은 68개가 아니라 wall-clock 경계가 모두 존재한 66개 사례의 기술통계다. 68개 formal inference latency 결과와 혼동하면 안 된다.

## 4. 경계 입력 통계

- 구성 선택: 총 **18,385**개 중 경계 입력 **2,304**개(12.531955%), `V_delta` **16,081**개, 최소 마진 `5.3016457479682089e-07`.
- 별도 입력: 총 **18,367**개 중 경계 입력 **2,318**개(12.620461%), `V_delta` **16,049**개, 최소 마진 `2.0095735286940197e-07`.
- `V_delta`가 빈 사례: selection `0`개, separate `0`개.
- 이진 코드는 `abs(score-threshold) <= margin_floor`를 `V_amb`로 분류한다(`internal/certify/coverage.go:80-89`). 다중 클래스 코드는 top-1/top-2 gap이 strict하게 `margin_floor`보다 큰 경우만 certifiable로 분류한다(`internal/certify/multiclass_decision_contract.go:261-269`). 따라서 두 경로 모두 `<= 0.001`을 경계로 취급한다.
- 경계 입력에서는 관측값을 보존하지만 decision flip과 reserve-policy violation을 SAFE 판정 집계에 넣지 않는다(`internal/certify/observation.go:274-313`, `internal/certify/multiclass_decision_contract.go:306-321`).

## 5. 후보 평가 단위 검증

- 후보 평가 1회는 입력 한 건이 아니라 한 후보를 구성 선택 입력 전체에서 **3개 fresh-key context**로 수행한 묶음이다.
- 89개 주요 후보 평가 묶음은 tabular/packed `87`개와 고정 다중 클래스 `2`개다. 모든 묶음의 key run이 3개인지: `True`.
- 운용 정책은 `rho=0.5`, `delta=0.001`이며 `B=4`는 초기 후보를 포함한 최대 후보 평가 묶음 수다. 초기 scale은 `s0=max(18,p+3)`이고, 수치 거부 시 scale `+4 bit`, 허용된 level shortage 시 Q prime `+1`의 단조 보정을 적용한다(`internal/ckksplanner/direct_policy.go:87-105`, `internal/ckksplanner/executor.go:429-489`). 주요 68건에서 Q-chain/LogN level-adjustment 사용은 0건이었다.
- 보안 admission은 128-bit 목표에서 ternary secret(nonzero probability `2/3`)과 discrete Gaussian error(`sigma=3.2`, bound `19.2`)를 기록하고 Q 및 evaluation-key QP를 모두 검사한다(`internal/ckksplanner/security_policy.go:63-120`). 이는 사전 고정 policy admission이지 exact-distribution 증명은 아니다.
- evaluator는 첫 SAFE에서 즉시 반환한다. 따라서 89/537은 실행시간 비율이 아니라 candidate-evaluation bundle 수의 감소다. finite/full selection wall-clock은 경계가 함께 남은 66건에서 median `12.398599`, IQR `7.465864`, p90 `16.756551`이나 formal inference latency와 별도인 기술통계다.
- 별도 입력은 선택 literal을 그대로 복사해 fresh keys로 실행하며 `Synthesize`나 `RepairCandidate`를 호출하지 않는다(`internal/ckksplanner/audit.go:85-87`).
- encrypted sample-evaluation 수, key-run 수, candidate-evaluation bundle 수는 서로 다른 단위다. 예를 들어 tabular trial의 `encrypted_sample_evaluations`는 `입력 수 x 3`이다.

## 6. 데이터 분리 및 키 독립성 검증

- 65개 tabular 사례에서 학습/구성 선택/별도 입력 row overlap 사례: **0**.
- 65개 tabular 사례는 각 outer fold에 별도 `model.json`을 가지며, 각 dataset-model 조합에서 5개의 fold-specific model digest가 확인됐다.
- 학습/선택 분리는 `StratifiedKFold(random_state=1701)`와 outer-train 내부 selection split(`random_state=2701+fold`)로 구현된다(`scripts/build_v17_plaintext_suite.py:380-397`). 표준화, feature 선택, 모델 학습과 threshold/head 정의는 model-training role에서 먼저 산출된다.
- MLP-100/LeNet-5-small split manifest의 validation/audit overlap은 `0`이며, packed CNN-lite audit noninterference flag 중 true 값은 `False`이다.
- 별도 입력 결과는 후보 선택 루프로 되돌아가지 않는다. 단, 저수준 RNG algorithm/seed provenance는 별도 기록이 없어 `NOT_VERIFIABLE`이다.

## 7. 부트스트랩 구현 설명

- 사례 68개를 `(dataset, model)` 기준 **16개** 묶음으로 구성했다.
- 각 사례값은 동일 input/keyset/pass의 `finite/direct` raw pair 비율 기하평균이다. 묶음 안에서는 사례 기하평균, 전체에서는 16개 묶음 기하평균을 사용한다.
- 각 bootstrap 반복은 16개 묶음값을 복원추출하고 동일한 기하평균을 계산한다. 묶음은 동일 가중치이며, 묶음 내부 사례도 동일 가중치다.
- seed `20260824`, 반복 `10,000`회, 2.5/97.5 percentile linear-interpolation CI이며 BCa가 아니다.
- 독립 재계산: `1.000540931232697`, 95% CI `[0.999967474765528, 1.001121781209021]`; 9자리 일치 `True`.
- warm-up 1회는 공식 records에서 제외되고 측정 6회만 남는다. 68개 사례에서 raw pair `23,454`개를 input/keyset/pass별로 재결합했고, balanced cyclic/reverse 순서 위반 사례는 `0`개다. 모든 raw pair가 보존되며 outlier 제거는 없다. raw ratio mismatch 사례 수는 `0`이다.
- `total_ms`는 encode/encrypt, homomorphic evaluation, decrypt/decode를 감싸는 end-to-end 측정 구간이다. 다중 클래스 adapter에서는 이 구간 안의 adapter I/O와 작은 실행 오버헤드도 포함한다. setup/key generation, direct synthesis, parameter materialization, repair와 전체 selection wall-clock은 제외된다(`internal/ckksbackend/v17_primary_paired_latency.go:141-162, 178-202, 363-380`; `internal/ckksbackend/paired_tabular_latency.go:300-309`).

## 8. 실험 환경 증거

- Host: `AMD Ryzen 5 3600 6-Core Processor`, physical cores `6`, logical processors `12`.
- Hypervisor/guest: `VMware Workstation`(정확한 VMware 버전은 `NOT_VERIFIABLE`), `Ubuntu 24.04.4 LTS`, kernel `7.0.0-28-generic`, architecture `x86_64`, 1 socket x 6 cores, affinity `0-5`, `GOMAXPROCS=6`.
- Memory/swap: `16324060` KiB / `4194300` KiB. Go `go version go1.25.9 linux/amd64`, Python `Python 3.12.3`, Lattigo `v6.2.0`.
- NumPy `2.2.6`와 scikit-learn `1.6.1`은 frozen scientific protocol에 기록됐다. x86_64도 protocol의 machine 필드에서 확인했다.
- 한 번에 한 CKKS case worker를 사용했다. Windows host 부하는 guest에서 완전히 관찰할 수 없었고 사후 outlier 규칙은 추가하지 않았다.

## 9. 재현성 위험요인

- 원시 실험은 1x6 VM 환경으로 결속됐지만 host의 순간 부하는 완전 관찰되지 않았다.
- 별도 입력의 전체 decision-stability population과 formal latency의 20-input subset은 다르다.
- 16-cluster bootstrap은 cluster equal weighting이다. 1개 고정 사례 cluster도 5-fold cluster와 동일한 cluster 가중치를 받는다.
- Security-V2는 Q와 QP를 각각 Table 5.2 cap에 대조하는 사전 고정 admission policy이지 exact-distribution security proof가 아니다(`internal/ckksplanner/security_policy.go:63-120`).
- HEIR는 exact common-workload decision 결과가 있으나 unsafe paired direct arm 때문에 latency claim은 diagnostic이다. EVA/CoreLab native latency는 runtime이 달라 직접 speedup으로 사용할 수 없다.
- HEIR raw audit: 500 inputs x 3 contexts, flips/violations `0/0`, max error `5.0791018169071833e-08`.
- EVA S20 raw audit: 1500 observations, flips `133`, affected inputs `114/500`.
- 공개 음성 사례 `banknote/mlp_square_poly3/fold_3`는 별도 입력 1068의 key repeat 1에서 판정 변화 없이 오차 `0.0107778160051625882`이 예산 `0.00982200284660778022`을 `0.000955813158554807973` 초과한 reserve-policy rejection이다. 별도 입력을 본 뒤 재선택하지 않았다.

## 10. 논문에 추가하거나 수정해야 할 문장

1. 본문: 구성 선택 및 별도 입력 전체에서 경계 입력과 `V_delta`의 규모를 명시하고, SAFE 판정이 `V_delta`에 한정됨을 적는다.
2. 본문: “별도 입력 20개”를 “별도 입력 중 사전 고정한 20개 latency subset”으로 고친다.
3. 통계 절: 68 case -> 16 dataset-model cluster, within-cluster case geometric mean -> equal-cluster bootstrap, seed 20260824, 10,000 percentile replicates라고 명시한다.
4. 재현성 부록: candidate evaluation/key run/encrypted input execution을 서로 다른 단위로 정의한다.
5. 한계: fresh context 생성은 소스로 확인되지만 key fingerprint/RNG seed provenance는 기록되지 않았다고 명시한다.
