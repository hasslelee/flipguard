# FlipGuard 논문 V25 코드·원시 결과 독립 감사

감사 일자: 2026-08-30 (Asia/Seoul)  
감사 대상 run: `v17_final_vm1x6_20260811T050104Z`  
검증 기준으로 요청된 원고: `CKKS_결정안정성_실행구성선택_정보보호학회논문지_v25.txt`

## 1. 최종 판정: FAIL

**판정은 `FAIL`이다.** 이유는 암호화 결과나 핵심 집계가 틀렸기 때문이 아니라, 지정된 V25 원고 파일이 `/home/ckks2` 아래에 존재하지 않아 원고 자체의 문장, Table 2–6, Fig. 3–6과 주장 강도를 제출 수준으로 검증할 수 없기 때문이다. 이는 `BLOCKING` 1건이다.

원시·고정 결과 측면의 독립 재계산은 통과했다. 68개 주 평가 사례, gate-off 68회, 전체 기법 89회, 유한 비교 537회, 68/68 별도 입력 SAFE, 83.426443% 후보 평가 감소, 68개 공식 지연시간 기록, 비율 1.000540931232697 및 16-cluster bootstrap 신뢰구간을 모두 재현했다. 새로운 암호화 실행은 0회이며 code/raw/evidence를 수정하지 않았다.

다만 요청문에 포함된 “각 주요 사례의 별도 입력이 정확히 20개”라는 명제는 실제 artifact와 다르다. 20개는 공식 짝지은 지연시간 측정 하위집합의 크기이며 전체 별도 입력 재평가의 크기가 아니다. 이 항목을 `MAJOR` 1건으로 분류한다.

상태 집계는 `PASS 65`, `PASS WITH NOTE 9`, `MINOR 1`, `MAJOR 1`, `BLOCKING 1`, `NOT VERIFIABLE 15`이다. 세부 항목은 `v25_code_verification_evidence.tsv`에 있다.

## 2. 제출을 막는 문제

### BLOCKING-1: V25 원고 source 부재

- 예상 파일: `/home/ckks2/flipguard/CKKS_결정안정성_실행구성선택_정보보호학회논문지_v25.txt` 또는 사용자 지정 위치의 동일 파일명
- 관측: `/home/ckks2` 전체 검색 결과 0개
- 영향: 원고 수식 표기, 실제 Table 2–6 셀·단위·caption, Fig. 3–6의 표시, ratio 방향, 정확한 문장 인용, 과장 표현 부재를 확인할 수 없다.
- 성격: 원시 자료 손상이 아니라 **감사 입력 누락**이다.
- 해결: 해당 V25 `.txt`를 작업 공간에 제공한 뒤, 이 감사의 수치 재계산은 재사용하고 원고 text/table/figure scan만 추가 수행한다. 암호화 실험 재실행은 필요 없다.

## 3. 주요 불일치

### MAJOR-1: “별도 입력 20개”의 통계 단위가 잘못됨

독립 manifest scan 결과, 65개 표 형식 주 평가 사례의 전체 별도 입력 크기는 사례에 따라 20, 113–114, 274–275, 359–360 또는 500개다. 고정 MLP-100과 LeNet-5-small은 각각 500개, packed CNN-lite는 250개를 별도 입력으로 사용한다. 반면 `docs/protocols/model_family_expansion_v17/latency_subsets.json`의 20개는 **공식 지연시간 측정용 하위집합**이다.

이 오류는 code/raw result 오류가 아니라 원고의 방법·통계 단위 설명 오류다. 이전 원고 v22.1에는 실제로 “각 주 평가 사례의 별도 입력은 20개”라는 문장이 남아 있으나, V25 source가 없으므로 V25에도 같은 문장이 있는지는 확인하지 못했다.

## 4. 경미한 불일치

### MINOR-1: legacy manifest의 configuration count 명칭

`docs/evidence/model_family_expansion_v17/final_vm1x6/manifest.json`의 `distinct_selected_configurations=131`은 실제로 131개 selected case identity를 센 값이다. exact `(LogN,Q,P,scale,path)` parameter literal은 전체 16개, primary 7개다. 이 의미 오류는 immutable R3 overlay의 `CONFIGURATION_COUNT_SEMANTICS.md`와 `PAPER_VALUES_V17_LOCKED.json`에서 교정되었다. 논문은 legacy key를 직접 인용하지 말고 R3 교정값을 사용해야 한다.

그 밖의 주의점은 경미한 수치 불일치가 아니라 scope note다. VMware Workstation의 정확한 version과 암호학적 key fingerprint/RNG seed는 기록되지 않았다. 현재 audit host의 kernel은 `7.0.0-30-generic`이지만 결과 생성 당시 as-run manifest는 `7.0.0-28-generic`이므로 논문 환경은 as-run 값을 유지해야 한다.

## 5. 저장소·commit·환경

### 저장소 및 source binding

| 항목 | 관측값 | 판정 |
|---|---|---|
| Repository | `/home/ckks2/flipguard` | PASS |
| Current branch | `paper/v22-1-editorial-sync` | PASS |
| Current HEAD | `67251c57ca7be5aa8aeffd746a6a6671685e98c5` | PASS |
| Scientific execution source | `cefc44b0d7e351db2a34886dd758a2d31a3e4c12` | PASS |
| Post-run aggregation fix | `86b0403208abbc741a65934358a5dea4a66e4d88` | PASS WITH NOTE |
| Run ID | `v17_final_vm1x6_20260811T050104Z` | PASS |
| Worktree | 기존 `AGENTS.md` 수정과 다수 선행 untracked artifact가 존재; 이번 감사가 만든 것은 네 파일뿐 | NOTE |

`cefc44b0`과 현재 HEAD 사이에서 V17 scientific path에 생긴 추적 변경은 `cmd/flipguard-v17-primary-paired-latency/main.go`와 해당 test의 post-run aggregation shadowing fix뿐이다. 따라서 encrypted execution은 Commit A에 결속하고, recovery/aggregation은 Commit B에 결속해야 한다.

### 결과 생성 당시 환경

| 항목 | 원고 예상 | as-run manifest | 판정 |
|---|---|---|---|
| Host CPU | AMD Ryzen 5 3600 | AMD Ryzen 5 3600 6-Core Processor | PASS |
| Host topology | 6 physical / 12 logical | 6 / 12 | PASS |
| Hypervisor | VMware Workstation | VMware Workstation | PASS; exact version 미기록 |
| Guest OS | Ubuntu 24.04.4 LTS | Ubuntu 24.04.4 LTS | PASS |
| Kernel | 7.0.0-28-generic | 7.0.0-28-generic | PASS |
| Architecture | x86_64 | x86_64 | PASS |
| Guest CPU | 1 socket × 6 cores, 6 vCPU | 1 × 6, 6 | PASS |
| Affinity/GOMAXPROCS | 0–5 / 6 | 0–5 / 6 | PASS |
| RAM/swap | 15.568 / 4.000 GiB | 16324060 / 4194300 KiB | PASS |
| Go/Python | 1.25.9 / 3.12.3 | 1.25.9 / 3.12.3 | PASS |
| Lattigo/NumPy/sklearn | 6.2.0 / 2.2.6 / 1.6.1 | exact match | PASS |

현재 guest도 6 vCPU와 affinity 0–5를 보지만 kernel이 `7.0.0-30-generic`이다. 현재 환경을 과거 지연시간의 생성 환경으로 소급 기술하면 안 된다.

### 실행 및 집계 계보

1. 전체 scheduler: `scripts/run_model_family_expansion_v17_vm1x6.py`
2. 표 형식 candidate 실행: `cmd/flipguard-v17-tabular-case` 및 `internal/ckksplanner/executor.go`
3. candidate 생성/repair: `internal/ckksplanner/synthesis.go`, frozen constants: `direct_policy.go`
4. security admission: `internal/ckksplanner/security_policy.go`
5. 별도 입력 replay: `internal/ckksplanner/audit.go`, multiclass/CNN executor
6. 공식 latency raw: `internal/ckksbackend/paired_tabular_latency.go`, `v17_primary_paired_latency.go`
7. V17 table/figure build: `scripts/build_model_family_expansion_v17_reports.py` → `scripts/finalize_model_family_expansion_v17_vm1x6.py`
8. V18 decision-gate overlay: `docs/evidence/comparison_extension_v18/build_offline_replay_v18.py` → `results/comparison_extension_v18/*.csv`
9. manuscript facts: `docs/reports/comparison_extension_v18/build_paper_facts_v18.py`

주요 raw root는 `/home/ckks2/flipguard/results/model_family_expansion_v17/runs/v17_final_vm1x6_20260811T050104Z`이고, 권위 V17 aggregate는 `/home/ckks2/flipguard/results/model_family_expansion_v17/final_vm1x6`, V18 aggregate는 `/home/ckks2/flipguard/results/comparison_extension_v18`이다.

## 6. 수식별 코드 대응표

| 수식 | 원고 조건 | 대응 코드 파일·함수·줄 | 실제 구현 | 일치 여부 | 비고 |
|---|---|---|---|---|---|
| (1) | 이진 `f(x)>=tau`, CKKS도 같은 tie rule, `abs(f_hat-f)` | `internal/certify/observation.go`, `classifyObservedScore`, 272–315, 323–327 | 두 판정 모두 `>=`; 오차는 `math.Abs` | PASS | sample ledger도 동일 |
| (2) | `e<gamma`이면 decision preservation | `observation.go` 306–313 | 실제 admission은 `e<rho*gamma`; 등호는 violation | PASS WITH NOTE | `rho=.5`라 theorem sufficient condition보다 엄격함. 필요조건·전체 보장 아님 |
| (3) | `gamma>delta`만 `V_delta`; `<=`는 `V_amb`; empty set은 SAFE 금지 | `coverage.go`, `AnalyzeValidationCoverage`, 72–105; `engine.go` 214–218 | 경계 포함 `<=`를 ambiguous; `VCert==0`은 AMBIGUOUS | PASS | raw selection/separate 모두 empty 사례 0 |
| (4) | 모든 competing class, 모든 key run, `E_top+E_j<rho gap_j` | `multiclass_decision_contract.go`, 96–163, 230–375 | 모든 class loop와 모든 key run; `MinimumCap<rho` | PASS | tie는 non-certifiable; NaN/Inf는 error; deterministic lowest-index tie break |
| (5) | 모든 `x in V_delta`, 모든 key에서 동일 판정 및 strict budget | binary `observation.go` 272–315; multiclass 253–372 | flip과 violation 별도 count, 둘 중 하나면 REJECTED | PASS | `rho=.5`, `delta=.001`은 Direct Policy V2 frozen values |

식 (2)는 구현이 theorem을 “필요조건”으로 사용한 것이 아니다. 구현의 운용 admission은 `rho=0.5` reserve를 둔 더 강한 경험적 조건이다. 이 구분을 원고에서 유지해야 한다.

### 후보 생성과 repair 확인

- 최대 candidate evaluation: initial 포함 4회 (`executor.go:429-494`, `direct_policy.go:100`).
- 초기 scale: `max(18, p+3)` 의미의 최소 18 bit와 guard 3 bit.
- numerical reject: scale +4 bit (`synthesis.go:458-463`).
- level/rescale failure: Q level +1 (`synthesis.go:443-456`).
- 다른 failure에는 repair signal을 만들지 않으며, unsupported repair는 error/NO_SAFE다.
- repaired candidate는 materialization 뒤 Security-V2에 다시 admission된다.
- `security_policy.go:63-120`에서 ciphertext Q와 evaluation-key QP를 별도로 검사하고 둘 다 PASS해야 최종 PASS다.
- target 128 bit, `ring.Ternary(p=2/3)`, `ring.DiscreteGaussian(sigma=3.2,bound=19.2)`가 as-run code에 있다.
- candidate evaluation 1회는 “구성 하나 × selection 입력 전체 × 세 fresh-key context”의 묶음이다.
- locked replay는 `Synthesize`/`RepairCandidate`를 호출하지 않고 `RetuningPerformed=false`를 기록한다.

## 7. 데이터 분리·키 독립성 점검

### 데이터 분리

- 표 형식 primary manifest 65개를 직접 읽어 `model_training`, `configuration_selection`, `independent_evaluation` row ID의 모든 pairwise intersection을 계산했다. overlap 사례는 0개다.
- `scripts/build_v17_plaintext_suite.py:314-354`는 mean/std, feature selection, model fit과 logit scale을 `train_idx`에서만 계산한다.
- 각 tabular dataset-model group은 fold-specific model digest 5개를 갖는다.
- MNIST multiclass는 training 55,000, model validation 5,000, configuration selection 500, locked separate evaluation 500이며 selection/audit source identity overlap은 0이다.
- packed CNN-lite는 selection 250, locked separate evaluation 250이고 sample identity overlap은 0이다. manifest의 audit noninterference flag도 모두 false다.

### 20개 단위의 정확한 역할

공식 지연시간 측정은 각 case의 별도 입력 집합에서 사전 고정한 20개 subset을 사용한다. 그러나 decision-stability separate-input result는 full role artifact를 사용한다. 따라서 “별도 입력 20개”는 formal timing에는 맞고 full separate reevaluation에는 틀리다.

### 키 독립성

selection executor는 key repeat마다 `NewContextFromProfile`을 호출하고, context의 runtime key generation path가 새 keypair를 만든다. locked replay도 별도 stage에서 같은 방식으로 fresh contexts를 만든다. 모든 completed candidate bundle은 3 key runs를 갖는다.

다만 raw JSON에는 key fingerprint나 RNG seed가 없다. 따라서 source-level fresh generation과 repeat count는 확인했지만, 두 stage의 key material byte-level 비재사용은 결과 파일만으로 독립 증명할 수 없다. 이를 `PASS WITH NOTE`와 별도 `NOT VERIFIABLE` subclaim으로 기록했다.

## 8. 핵심 수치 재집계표

| 항목 | 원고 예상값 | 독립 재집계값 | 판정 | 주 근거 |
|---|---:|---:|---|---|
| Primary cases | 68 | 68 | PASS | `case_level_ledger.csv` |
| Gate-off evaluations | 68 | 68 | PASS | `c2_candidate_evaluations` sum |
| Neither / flip-only / violation-only / both | 47/0/1/20 | 47/0/1/20 | PASS | `c2_selection_*` cross-tab |
| Union / flip / violation cases | 21/20/21 | 21/20/21 | PASS | same |
| Cases with one added evaluation | 21 | 21 | PASS | `c1-c2 evaluations` |
| Cases with >=2 added evaluations | 0 | 0 | PASS | same |
| Scale +4 / Q-prime change / chain change / LogN change | 21/0/0/0 | 21/0/0/0 | PASS | before/after literal |
| Full-method evaluations | 89 | 89 | PASS | `direct_trials` sum |
| Finite-reference evaluations | 537 | 537 | PASS | `exhaustive_denominator` sum |
| Missed acceptable | 0/68 | 0/68 | PASS | `false_no_safe`, safe rank |
| Full separate SAFE | 68/68 | 68/68 | PASS | `c1_separate_status` |
| Gate-off separate | 47 pass, 21 N/E | 47 SAFE, 21 NOT_EVALUATED, 0 failed | PASS | `c2_separate_status` |
| Fastest executable unstable | 18/68 | 18/68 | PASS | numerical diagnostics |
| Minimum-error unstable | 0/68 | 0/68 | PASS | numerical diagnostics |
| Minimum-error differs | 68/68 | 68/68 | PASS | candidate identity |
| Protocol records | 204 | 204 DONE | PASS | `final_run_status.csv` |
| All selection cases / non-primary | 131/63 | 131/63 | PASS | `table_03` |
| Unique literals all/primary | 16/7 | 16/7 | PASS | exact tuple set |
| Candidate reduction | 83.43% | 83.42644320297952% | PASS | `(537-89)/537` |

`83.43%`는 candidate-evaluation bundle 수의 finite-denominator 감소다. 전체 wall-clock 감소, key run 감소, ciphertext operation 감소 또는 전체 CKKS 공간 축소가 아니다.

### Selection wall-clock의 올바른 통계

66개 matched case에서 `finite-reference whole selection wall-clock / full-method whole selection wall-clock` 비율은 median `12.3985990264`, Q1 `7.49324205973`, Q3 `14.95910619899`, IQR `7.46586413927`, P90 `16.75655132438`이다. MLP-100과 LeNet의 direct selection wall-clock 2개는 predecessor-frozen이라 paired distribution에서 제외된다.

legacy final manifest의 `13.8440787224`는 finite 68행 numerator와 direct 66행 denominator를 나눈 asymmetric aggregate이므로 manuscript headline에 사용하면 안 된다. gate-off와 full-method의 “전체 선택시간”은 stage boundary상 직접 재구성되지 않으므로, 21개 changed case의 candidate-stage observed latency와도 혼동하면 안 된다.

## 9. 지연 시간 독립 재계산

### Raw pairing audit

68개 `paired_latency.json`을 직접 읽어 기존 final report builder를 호출하지 않고 재조합했다.

- Tabular 65 cases: pair key `(keyset, measurement_run, row_id)`, case당 360 pairs.
- MLP-100, LeNet-5-small, packed CNN-lite: batch pair key `(keyset, measurement_run)`, case당 18 pairs.
- 총 raw pairs: `23,454`.
- pair duplicate/missing: 0.
- raw geometric mean과 table row mismatch: 0.
- warm-up 1, measurements 6, no outlier removal: 68/68 확인.
- direct/reference order-position balance error: 0.

Tabular total latency는 encode/encrypt, homomorphic model/polynomial evaluation, decrypt/decode를 포함한다. Multiclass total에는 이 경계와 adapter I/O/end-to-end overhead도 들어간다. Parameter synthesis/materialization, key generation/setup, repair와 whole selection wall-clock은 제외되며 setup/keygen은 별도 metadata다.

### Ratio 및 CI

- 정의: `finite-reference total latency / proposed total latency`.
- case 내부: 동일 input/keyset/pass raw ratios의 geometric mean.
- cluster: `(dataset, model_id)` 16개, cluster 내부 case geometric mean.
- point estimate: 16 cluster values의 equal-weight geometric mean.
- CI: seed `20260824`, 10,000회 cluster resampling, percentile 2.5/97.5%, linear interpolation, BCa 아님.

독립 결과는 `1.000540931232697`, 95% CI `[0.9999674747655278, 1.0011217812090207]`이다. 신뢰구간이 1을 포함하므로 finite reference 또는 proposed 어느 쪽의 speed superiority도 주장할 수 없다.

21개 changed case의 `final candidate / initial candidate` selection-stage observed latency ratio는 median `1.0045077568931444`, P90 `1.0112181988336308`이다. 이는 formal paired inference latency가 아니다.

Formal regret는 `(proposed-reference)/reference = 1/(reference/proposed)-1`로 계산했다.

| 통계 | 비율 | 백분율 |
|---|---:|---:|
| Median | -0.000153236246713 | -0.0153236% |
| Q1 | -0.001322856383080 | -0.132286% |
| Q3 | 0.000502948584564 | 0.0502949% |
| IQR width | 0.001825804967644 | 0.182580%p |
| P90 | 0.001426189816154 | 0.142619% |
| Maximum | 0.002309669255066 | 0.230967% |

## 10. 부정 사례 추적

전체 131개 selection cases 중 separate-input REJECTED는 정확히 1건이다.

| 항목 | 값 |
|---|---|
| Case | `banknote/mlp_square_poly3/fold_3/training_seed_0` |
| Role | separate / independent evaluation |
| Candidate | `synth_analysis_minimum_rescale_N14_Q10_S22_188825b7cf8c` |
| Sample / key repeat | `1068` / `1` |
| Plain score | `0.5196440056932156` |
| CKKS score | `0.508866189688053` |
| Threshold | `0.5` |
| Margin | `0.01964400569321556` |
| rho × margin | `0.00982200284660778` |
| Absolute error | `0.010777816005162588` |
| Excess | `0.000955813158554808` |
| Plain / CKKS decision | `true / true` |
| Flip / violation | `0 / 1` |
| Literal | `LogN=14`, `Q=[25,22,22,22,22,22,22,22,22,22]`, `P=[30]`, `scale=22`, `rescale` |

이 사례는 decision failure가 아니라 `POLICY_REJECTED_WITHOUT_FLIP` 성격의 reserve-policy violation이다. candidate selection은 이미 끝났고 separate input에서 발견되었으며, 해당 row는 `table_03_decision_stability.csv`와 R3 negative report에 남아 있다. case 삭제나 post-result retuning 근거는 없다.

Depth ladder도 독립 확인했다. D1/D2/D4/D6/D8의 Q-chain length는 `2/3/5/8/11`, LogN은 `12/12/13/14/14`다.

## 11. 외부 도구 비교 근거

### HEIR

`heir_shared_polynomial_records.csv`의 `Lattigo-v6.2.0-translation`, `locked_audit` rows를 직접 집계했다. LogN 14, scale 45, 500 unique inputs × 3 contexts = 1,500 observations, flips 0, reserve violations 0, maximum absolute error `5.079101816907183e-08`이다.

이 결과는 shared polynomial의 common-Lattigo diagnostic이다. paired direct arm이 unsafe였으므로 HEIR 대비 formal speed claim은 blocked다.

### EVA S20

`eva_population_records.csv`의 `configuration_validation`, scale 20 rows는 unique inputs 500, contexts 3, observations 1,500, flip events 133, at least-one-flip inputs 114다. 따라서 133의 정확한 분모는 **1,500 encrypted observations**이며 500 unique inputs에 대한 event 비율로 쓰면 안 된다.

### HECATE / ELASM

HECATE에 대해 V17 decision-bearing exact output은 저장소에서 확인되지 않아 direct decision baseline은 `NOT VERIFIABLE`이다. ELASM은 36 plans 중 34 PASS, 2 execution failure를 가진 numerical-only panel이며 matching threshold/argmax contract가 없다. 두 결과는 error/latency 또는 related-work scope로만 설명해야 한다.

EVA/CoreLab의 native cross-runtime timing과 V17 same-host common-executor formal paired timing은 boundary가 다르다. raw cross-runtime latency superiority를 주장하지 않는 제한은 타당하다.

## 12. 재현성 및 누락 자료

### 통과

- `go test ./internal/certify ./internal/ckksplanner ./internal/ckksbackend`: PASS.
- V18 protocol/comparison verifier: PASS.
- Primary 68 inventory verifier: PASS.
- V18 locked paper facts verifier: PASS.
- V17 final result `SHA256SUMS`: 모두 PASS.
- R3 package `SHA256SUMS`: 모두 PASS.
- Focused external comparison V8 `SHA256SUMS`: 모두 PASS.
- Candidate ledger의 693 source-path hashes: mismatch 0.

### 의도된 verifier 제한

`verify_release_r3.py`는 repository HEAD가 정확히 Commit B인지 검사하므로 descendant인 현재 HEAD에서 `repository HEAD moved`로 중단한다. R3 payload checksums와 Commit A/B lineage는 별도로 통과했다. `verify_model_family_expansion_v17_vm1x6.py`도 current source가 as-run snapshot과 byte-identical해야 하므로 post-run aggregation fix 파일에서 fail-closed한다. 이 둘은 raw evidence corruption이 아니라 verifier의 exact-HEAD/current-source binding 특성이다.

### 누락·검증 불가

1. V25 원고 `.txt` 자체.
2. V25 Table 2–6 및 Fig. 3–6 actual content.
3. V25 exact sentence-level overclaim scan.
4. Key fingerprint/RNG seed.
5. VMware Workstation exact version.
6. Exact decision-bearing HECATE output.

전체 matrix나 latency를 다시 실행할 필요는 없다. V25 원고를 받은 뒤 필요한 것은 text/table/figure read-only audit뿐이며 예상 시간·추가 용량은 10분 미만·수 MB 미만이다.

## 13. 원고에서 수정해야 할 문장

V25 source가 없어 실제 문장을 인용할 수 없으므로 다음은 **증거에 맞춘 exact replacement sentences**다.

### 별도 입력과 timing subset

> 표 형식 모델의 별도 입력 재평가는 각 외부 분할의 전체 독립 평가 집합을 사용했으며 사례별 크기는 데이터셋에 따라 달랐다. MLP-100과 LeNet-5-small은 각각 500개, packed CNN-lite는 250개의 별도 입력을 사용했다. 공식 짝지은 지연시간 측정은 이 별도 입력 집합에서 사전에 고정한 사례별 20개 하위집합만 사용했다.

### candidate evaluation unit

> 후보 평가 1회는 하나의 실행 구성을 구성 선택용 입력 전체에 대해 서로 독립적으로 생성한 세 키 context에서 실행한 묶음이다. 입력 수, 키 반복 수와 후보 평가 횟수는 서로 다른 통계 단위다.

### candidate reduction

> 제안 절차는 68개 주 평가 사례에서 89개의 암호화 후보를 평가했으며, 사전에 고정한 유한 비교 후보군은 537개를 평가했다. 따라서 후보 평가 횟수의 감소율은 `(537-89)/537=83.426443%`이며, 이는 전체 구성 공간이나 전체 실행시간의 감소를 의미하지 않는다.

### formal latency

> 동일 입력·키 인덱스·측정 반복을 유지한 공식 짝지은 측정에서 유한 비교 기준 구성의 총 지연시간을 제안 구성의 총 지연시간으로 나눈 16개 데이터셋-모델 묶음 기하평균은 1.000540931이었다. 10,000회 묶음 bootstrap 95% 신뢰구간은 [0.999967475, 1.001121781]로 1을 포함했으므로 지연시간 우월성을 주장하지 않는다.

### changed candidate observational latency

> 초기 구성이 제외된 21개 사례에서 최종 후보와 초기 후보의 후보 평가 단계 관측 지연시간 비율은 중앙값 1.004508, 90번째 백분위수 1.011218이었다. 이 값은 공식 짝지은 추론 지연시간이나 두 절차의 전체 구성 선택시간이 아니다.

### negative result

> 전체 131개 선택 사례 중 Banknote의 세제곱 출력부 제곱 MLP 세 번째 외부 분할 1건은 별도 입력에서 판정 변화 없이 운용 오차 예산을 한 번 초과했다. 해당 사례를 제거하거나 결과 확인 뒤 구성을 다시 선택하지 않았다.

### external scope

> HEIR shared-polynomial 결과와 EVA/ELASM 자료는 실행 runtime, 출력 계약과 측정 경계가 주 평가의 공식 짝지은 측정과 다르므로 수치·판정 가능 범위만 보고하며 cross-runtime 속도 우월성의 근거로 사용하지 않는다.

### claim boundary

> 결과는 사전에 고정한 유한 비교 후보군, 지원 계산 그래프, 선언한 입력 집합, 단일 가상머신과 명시한 보안 admission model의 범위에 한정된다. 전역 최적 구성, 미래 입력 분포의 결정 안정성 또는 모든 CKKS backend에 대한 일반화를 주장하지 않는다.

## 14. 실제 실행한 명령과 생성 파일 목록

전체 명령은 `/home/ckks2/flipguard/v25_code_verification_commands.log`에 기록했다. 주요 명령은 다음과 같다.

```bash
git branch --show-current
git rev-parse HEAD
git status --short
find /home/ckks2 -type f -name 'CKKS_결정안정성_실행구성선택_정보보호학회논문지_v25.txt'
go version
python3 --version
lscpu
python3 <independent read-only CSV/JSON recomputation heredoc>
python3 docs/evidence/comparison_extension_v18/verify_comparison_extension_v18.py
python3 docs/reports/comparison_extension_v18/verify_primary_68_inventory.py
python3 docs/reports/comparison_extension_v18/verify_paper_facts_v18.py
sha256sum -c SHA256SUMS
go test ./internal/certify ./internal/ckksplanner ./internal/ckksbackend
```

생성 파일:

1. `/home/ckks2/flipguard/v25_code_verification_report.md`
2. `/home/ckks2/flipguard/v25_code_verification_evidence.tsv`
3. `/home/ckks2/flipguard/v25_code_verification_summary.json`
4. `/home/ckks2/flipguard/v25_code_verification_commands.log`

원고, code, raw log, frozen evidence 및 기존 result는 수정하지 않았다. Commit/push와 encrypted rerun은 수행하지 않았다.
