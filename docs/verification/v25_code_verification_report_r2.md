# FlipGuard V25 코드·원시 결과 2차 감사

감사 일자: 2026-08-30 (Asia/Seoul)

감사 대상 run: `v17_final_vm1x6_20260811T050104Z`

감사 원고: `/home/ckks2/flipguard/CKKS_결정안정성_실행구성선택_정보보호학회논문지_v25.txt`

## 1. 최종 판정: PASS WITH CHANGES

지정 원고는 실제로 존재하며 SHA-256은 다음과 같다.

```text
9db961268890b1ae1cbf724a6eaa1b5172d0e4d6151311df09aa989d9e061703
```

따라서 1차 감사의 `BLOCKING: 지정 원고 파일 없음`은 해소됐다. 식 (1)–(5), Table 1–6, 본문 실험 수치와 주장 범위는 코드·원시 기록·고정 집계값과 일치한다. 원고 수치의 `BLOCKING`, `MAJOR` 또는 `MINOR` 불일치는 없다.

다만 원고 TXT에는 `[Fig. n 삽입]` 자리표시자와 caption만 있고, V25에 삽입할 정확한 figure 파일이나 digest가 결속되어 있지 않다. 저장소의 최신 편집 가능 source로 확인되는 V22.1 deck의 slide 1–6은 수식과 수치에 일치하지만, release package에서 이 deck 또는 최종 export를 SHA-256으로 명시해야 한다. 이를 `MINOR` 1건으로 분류한다.

최종 issue 수는 다음과 같다.

| Severity | Count |
|---|---:|
| BLOCKING | 0 |
| MAJOR | 0 |
| MINOR | 1 |

새 암호화 실행은 수행하지 않았다. 이번 감사가 수정한 것은 새 R2 보고 파일 네 개뿐이며, source·raw result·frozen evidence는 변경하지 않았다.

## 2. 별도 입력 수 1차 문제 재검증

수정 원고 192행과 205행의 표현은 실제 자료와 일치한다.

### 2.1 전체 별도 입력은 사례별 20–500개

68개 주요 사례의 전체 별도 입력 수를 각 role artifact에서 다시 셌다.

| Inputs per case | Cases |
|---:|---:|
| 20 | 10 |
| 113 | 3 |
| 114 | 12 |
| 250 | 1 |
| 274 | 9 |
| 275 | 6 |
| 359 | 6 |
| 360 | 4 |
| 500 | 17 |
| **Total** | **68** |

최솟값은 20, 최댓값은 500이다. 표 형식 65개 사례는 각 run directory의 `independent_evaluation.prepared.csv`를 직접 셌다. MLP-100과 LeNet-5-small은 locked-audit aggregation의 `V_cert + V_amb = 500`, packed CNN-lite는 `250`이다.

판정: **PASS**.

### 2.2 공식 지연 시간 측정 하위집합은 사례별 20개

`docs/protocols/model_family_expansion_v17/latency_subsets.json`은 20개 row ID를 사전 고정한다. `cmd/flipguard-v17-primary-paired-latency/main.go:219-229`는 subset identity, data digest와 `len(row_ids)==20`을 검사한다. 68개 `paired_latency.json`을 직접 읽은 결과 모든 artifact가 20개 입력을 사용했다.

판정: **PASS**.

### 2.3 Table 4의 68은 입력 수가 아닌 aggregate 결과 수

원고 185행은 사례, 후보 평가, 별도 입력 재평가와 지연 시간 기록을 서로 교환해 해석하지 말라고 명시한다. Table 4의 192행은 `One aggregate result for each primary selected configuration; 20-500 inputs per case`라고 정확히 적었다.

- 주요 선택 구성: 68개
- 구성별 별도 입력 aggregate outcome: 68개
- 전체 별도 입력 크기: 사례별 20–500개

판정: **PASS**.

### 2.4 후보 평가와 별도 입력 재평가의 키 집합

원고 159행은 후보 평가 한 회를 `후보 하나 × 선택용 입력 전체 × 서로 다르게 생성한 세 키 집합`으로 정의한다. `internal/ckksplanner/executor.go:166-260`은 key repeat마다 새 context를 만든다. 별도 입력은 `internal/ckksplanner/audit.go:377-450`의 별도 stage에서 선택된 한 구성을 다시 실행하고 `RetuningPerformed=false`를 기록한다. `internal/ckksbackend/context.go:31-40`에서 context 생성은 runtime key-generation path로 이어진다.

따라서 source-level 실행 의미는 수정 원고와 일치한다. 다만 raw JSON에는 key fingerprint나 RNG seed가 없으므로 두 stage의 key material이 byte 단위로 다름을 결과 파일만으로 독립 증명할 수는 없다.

판정: **PASS WITH NOTE**.

## 3. 식 (1)–(5) 검증

| 식 | 원고 위치 | 구현 근거 | 판정 |
|---|---:|---|---|
| (1) 이진 판정과 절대 오차 | 64–65 | `internal/certify/observation.go:272-315,323-327` | PASS |
| (2) `E < gamma` 결정 보존 충분조건 | 67–71 | 같은 파일 272–315 | PASS WITH NOTE |
| (3) `V_delta`, coverage | 73–77 | `internal/certify/coverage.go:41-105` | PASS |
| (4) 모든 경쟁 class의 pairwise argmax 조건 | 81–87 | `internal/certify/multiclass_decision_contract.go:96-163,230-375` | PASS |
| (5) 이진 operational admission | 104–110 | `observation.go:272-315` | PASS |

식 (2)는 `E < gamma`가 판정 보존의 충분조건임을 말한다. 실제 후보 승인은 더 엄격한 `E < rho*gamma`, `rho=0.5`를 사용한다. 원고가 이론 조건과 운용 조건을 구분하므로 모순이 없다.

다중 클래스 구현은 두 번째 클래스 하나만 검사하지 않는다. 모든 `j != k*`에 대해 class-wise observed errors의 합을 gap과 비교하며, 모든 key repeat를 순회한다. tie, NaN, Inf와 등호는 fail-closed 처리한다.

## 4. Table 1–6 검증

### Table 1: notation

`f`, `f_hat`, `tau`, `gamma`, `D`, `E`의 정의가 식 (1)–(5)와 일치한다. 판정: **PASS**.

### Table 2: fixed policy

다음 값이 `internal/ckksplanner/direct_policy.go:64-106`과 일치한다.

- `rho=0.5`
- `delta=0.001`
- 최초 후보 포함 최대 `B=4 candidate evaluations`
- numerical rejection 후 scale `+4 bits`
- level 부족 후 Q prime `+1`
- initial scale floor `18 bits`, guard `3 bits`
- key repeats `3`
- security target `128 bits`

`internal/ckksplanner/security_policy.go:63-120`은 ciphertext Q와 evaluation-key QP를 따로 검사하고 둘 다 통과해야 최종 PASS로 둔다. 판정: **PASS**.

### Table 3: as-run environment

원고 169–179행은 environment manifest와 일치한다.

- AMD Ryzen 5 3600
- VMware Workstation
- Ubuntu 24.04.4 LTS
- as-run kernel `7.0.0-28-generic`
- 1 socket × 6 cores, CPUs 0–5, `GOMAXPROCS=6`
- RAM 15.568 GiB, swap 4.000 GiB
- Go 1.25.9, Python 3.12.3, Lattigo 6.2.0, NumPy 2.2.6, scikit-learn 1.6.1

현재 audit kernel은 `7.0.0-30-generic`이지만 원고는 결과 생성 당시 값을 사용하므로 정확하다. 판정: **PASS**.

### Table 4: evaluation units

| Item | Manuscript | Recomputed | Result |
|---|---:|---:|---|
| Primary cases | 68 | 68 | PASS |
| Proposed candidate evaluations | 89 | 89 | PASS |
| Comparison candidate evaluations | 537 | 537 | PASS |
| Separate-input aggregate outcomes | 68 | 68 | PASS |
| Formal paired aggregate rows | 68 | 68 | PASS |
| Protocol records | 204 | 204 DONE | PASS |
| All selected case identities | 131 | 131 | PASS |
| Exact parameter literals | 16 / 7 | 16 overall / 7 primary | PASS |

68개 formal timing row의 하위 raw pair 합계는 `23,454`다. 원고의 68은 case-level paired aggregate record 수이므로 raw pair 수와 충돌하지 않는다. 판정: **PASS WITH NOTE**.

### Table 5: decision-stability criterion effect

독립 cross-tab 결과는 다음과 같다.

- flip 없음 / violation 없음: 47
- flip만: 0
- violation만: 1
- 둘 다: 20
- 합집합: 21
- gate-off evaluations: 68
- full method evaluations: 89
- 추가 후보가 필요한 사례: 21
- 정확히 한 번 추가 평가: 21
- 두 번 이상 추가 평가: 0
- scale +4 bits: 21
- Q prime 수, Q-chain 길이, LogN 변화: 각각 0
- gate-off separate: 47 SAFE, 21 NOT_EVALUATED, failure 0
- full method separate: 68 SAFE

판정: **PASS**.

### Table 6: selection quality and latency

독립 재계산값은 다음과 같다.

- `89 vs 537`, candidate evaluation reduction `83.42644320297952%`
- missed acceptable configuration `0/68`
- finite-reference/proposed total-latency ratio `1.000540931232697`
- 95% CI `[0.9999674747655278, 1.0011217812090207]`
- fastest executable unstable `18/68`
- minimum-error unstable `0/68`, proposed와 다른 구성 `68/68`
- all-scope negative `1/131`

원고 반올림값은 모두 정확하다. 판정: **PASS**.

## 5. Fig. 1–6 검증

V25 TXT에는 실제 drawing이 없으므로 최신 repository figure source로 명시된 다음 deck의 slide XML을 읽었다.

```text
/home/ckks2/flipguard/docs/final_manuscript_v22_1/CKKS_논문그림01_06_영문한글_편집가능_v22_1.pptx
SHA-256: 3dd16a8df79982bf34256c7abdc0a470966698fa16a4c1ae293b8634755a731a
```

| Figure | 확인 내용 | 판정 |
|---|---|---|
| Fig. 1 | support, initial configuration, security check, encrypted evaluation, adjustment, selection/failure, no-feedback separate re-evaluation | PASS WITH NOTE |
| Fig. 2 | binary `E<gamma`, operational `E<rho*gamma`, multiclass all-competitor strict condition | PASS WITH NOTE |
| Fig. 3 | 68/89/537/68/68/204/131/16/7의 서로 다른 단위 | PASS WITH NOTE |
| Fig. 4 | 47/0/1/20, 68→89, 21 one-additional, +4 scale, Q/LogN/Q-length 0 | PASS WITH NOTE |
| Fig. 5 | fastest unstable18, differs23, min-error stable68/differs68, 89/537, ratio/CI, external evidence boundaries | PASS WITH NOTE |
| Fig. 6 | ratio/CI, depth adaptation, negative case rounded values | PASS WITH NOTE |

내용 불일치는 없다. 그러나 V25-specific asset binding이 없으므로 최종 HWP/PDF 또는 publication manifest에서 정확한 source/export digest를 결속해야 한다. 이것이 유일한 `MINOR` issue다.

## 6. 핵심 수치 재연결

| Value | Manuscript location | Raw/aggregate source | Result |
|---|---:|---|---|
| 68 primary cases | 8,13,183,189 | `case_level_ledger.csv` | PASS |
| 89 proposed evaluations | 8,13,190,232,248,259,287 | `sum(c1_candidate_evaluations)` | PASS |
| 537 comparison evaluations | same | `sum(c6_finite_evaluations)` | PASS |
| 83.426443%, shown 83.43% | 8,13,248,259,287 | `(537-89)/537` | PASS |
| 68/68 separate SAFE | 8,13,240,246,285 | `c1_separate_status` | PASS |
| ratio 1.000540931 | 250 | 68 raw-summary rows, 16 clusters | PASS |
| CI [.999967475,1.001121781] | 250 | seed 20260824, 10,000 bootstrap | PASS |
| 23,454 raw pairs | not printed as headline | sum of `pairs` in 68 latency rows | PASS WITH NOTE |

`23,454`는 `65 × 360 + 3 × 18`이다. 표 형식 65개 사례는 20 inputs × 6 passes × 3 keysets의 paired rows를 갖고, 세 fixed batched path는 6 passes × 3 keysets의 batch pairs를 갖는다. 원고 Table 4의 `68`은 이 raw pairs를 사례별로 집계한 row 수다.

## 7. 지연 시간 경계

원고 207행의 정의는 구현과 일치한다.

포함:

- input encoding and encryption
- homomorphic evaluation
- decryption and decoding
- multiclass/packed path의 adapter I/O/end-to-end boundary

제외:

- direct synthesis
- candidate materialization
- key generation/setup
- repair
- sequential whole-selection wall-clock

Tabular code는 `internal/ckksbackend/paired_tabular_latency.go:213-309`, multiclass/packed code는 `internal/ckksbackend/v17_primary_paired_latency.go:141-203,330-380`에 대응한다. 따라서 `83.43%`를 operating-time reduction으로 표현하지 않은 원고가 정확하다.

## 8. 부정 사례

전체 131개 selected case identity 중 별도 입력 REJECTED는 1건이다.

| Field | Value |
|---|---|
| Case | `banknote/mlp_square_poly3/fold_3/training_seed_0` |
| Sample | `1068` |
| Key repeat | `1` |
| Plain score | `0.5196440056932156` |
| CKKS score | `0.508866189688053` |
| Threshold | `0.5` |
| Margin | `0.01964400569321556` |
| Allowed limit | `0.00982200284660778` |
| Observed error | `0.010777816005162588` |
| Plain / CKKS decision | `true / true` |
| Flip / violation | `0 / 1` |

원고의 `0.0107778`과 `0.00982200`은 올바른 반올림이다. 판정이 유지됐으므로 decision flip failure가 아니라 reserve-policy violation이다. 결과 후 재선택이나 사례 제거는 없었다.

## 9. 데이터 분리와 사후 피드백

- 65개 tabular primary case의 selection/separate row-ID overlap: 0
- 전처리와 threshold/calibration: train indices만 사용
- MLP-100/LeNet: configuration selection 500과 locked separate 500이 사전 분리
- packed CNN-lite: selection 250과 separate 250이 사전 분리
- separate result에 따른 candidate regeneration/repair: 0
- `RetuningPerformed`: false

원고 29, 143, 203, 246행과 일치한다.

## 10. Claim-strength scan

| Prohibited overclaim | Manuscript result |
|---|---|
| Global optimum | 133,279행에서 finite prepared comparison 범위로 제한: PASS |
| Latency superiority | 250,287행에서 CI가 1을 포함하며 우월성 미주장: PASS |
| 83.43% operating-time reduction | 207,248,259,287행에서 명시적으로 부정: PASS |
| Universal graph/backend generalization | 270,279,289행에서 지원 범위로 제한: PASS |
| 68/68 as distribution-wide guarantee | 246,279행에서 finite inputs와 empirical scope로 제한: PASS |

## 11. 외부 비교 수치

- HEIR: LogN 14, scale 45, 500 inputs × 3 contexts, flip 0, violation 0, max error `5.079101816907183e-08`.
- EVA S20: 500 unique inputs × 3 contexts = 1,500 observations, flip events 133, affected inputs 114.
- HECATE/ELASM: matching final-decision output이 없어 numerical-only comparison으로 제한.

원고 272행은 모두 정확하며 cross-runtime speed superiority를 주장하지 않는다.

## 12. 검증 실행

다음은 PASS했다.

- `python3 docs/evidence/comparison_extension_v18/verify_comparison_extension_v18.py`
- `python3 docs/reports/comparison_extension_v18/verify_primary_68_inventory.py`
- `python3 docs/reports/comparison_extension_v18/verify_paper_facts_v18.py`
- `go test ./internal/certify ./internal/ckksplanner ./internal/ckksbackend`
- V17 final `SHA256SUMS`
- V17 release R3 `SHA256SUMS`
- 독립 CSV/JSON 재집계
- 원고 equation/table/figure/caption/overclaim scan

독립 재집계 스크립트 작성 중 CSV `pairs`가 `18.0`으로 직렬화된 특수 경로와 batched latency artifact의 schema 차이 때문에 두 번의 read-only parser 오류가 있었다. 이를 numeric conversion과 schema branch로 고친 뒤 전체 68행을 재검증했다. 오류는 감사용 임시 코드에만 있었으며 source, raw result, evidence에는 영향을 주지 않았다. 자세한 기록은 command log에 남겼다.

## 13. 불일치 및 변경 요구

### 수치·문장 불일치

없음.

### MINOR-1: V25 figure asset binding

V25 TXT는 Fig. 1–6 자리와 caption만 포함한다. 현재 deck 내용은 모두 일치하지만, 최종 publication package는 실제 삽입한 figure source/export path와 SHA-256을 명시해야 한다.

이 변경은 연구 코드, frozen evidence, 실험값 또는 원고 과학 주장을 바꾸지 않는다.

## 14. 생성 파일

- `/home/ckks2/flipguard/v25_code_verification_report_r2.md`
- `/home/ckks2/flipguard/v25_code_verification_evidence_r2.tsv`
- `/home/ckks2/flipguard/v25_code_verification_summary_r2.json`
- `/home/ckks2/flipguard/v25_code_verification_commands_r2.log`
