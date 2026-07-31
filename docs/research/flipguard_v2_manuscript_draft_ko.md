# FlipGuard V2 논문 초안

상태: `NON_AUTHORITATIVE_SCAFFOLD`. 2026-07-29 기준으로 방법과 검증
범위만 정리한다. Final evidence freeze와 `FINAL_ADMISSIBLE` artifact가
완성되기 전에는 결과 수치, 본문 주장, 초록, 결론을 확장하지 않는다.

## 제목

**FlipGuard: CKKS 암호화 추론을 위한 결정 보존 기반 자동 구성 합성 및
검증 프레임워크**

영문 후보:

**FlipGuard: Decision-Preservation-Aware Automatic Configuration Synthesis
and Validation for CKKS Inference**

## 초록

CKKS 기반 암호화 추론의 파라미터 선택은 보안성, 수치 정밀도, 연산 깊이,
실행 지연시간을 동시에 고려해야 한다. 기존 자동 튜닝 접근은 주로 정확도
또는 지연시간을 최적화하지만, 근사 오차가 최종 임계값 기반 판단을
뒤집지 않는지를 명시적으로 보존하지 않을 수 있다. 본 논문은 모델과
검증 데이터로부터 workload contract를 구성하고, 정확한 CKKS parameter
literal을 직접 합성한 뒤, 암호화 실행 증거를 통해 후보를
`SAFE`, `REJECTED`, 또는 `FAILED`로 판정하는 FlipGuard를 제안한다.
첫 후보가 안전하지 않을 때만 관측된 실패 신호에 따라 단조 수리를
수행하며, 주어진 실행 예산 안에 방어 가능한 후보가 없으면
`NO_SAFE`를 반환한다.

평가는 공개 tabular dataset의 다중 model graph와 disjoint multi-split
validation/locked-audit protocol, bounded catalog oracle, explicit abstention
control, 그리고 동일 프로세스 paired latency protocol로 구성한다.
수치 결과는 동일 source commit에 결합된 confirmatory evidence가 모두
통과하고 artifact manifest가 `FINAL_ADMISSIBLE`일 때만 제출 초록에
삽입한다. 본 프레임워크의 보장은 선언된 데이터, graph, margin policy 및
관측 검증 범위에 한정되며 전체 입력 공간에 대한 형식 보장을 의미하지
않는다.

<!-- BEGIN FINAL_RESULT_SENTENCE -->
<!-- NON_AUTHORITATIVE_SCAFFOLD: no final result sentence is admissible. -->
<!-- END FINAL_RESULT_SENTENCE -->

## 1. 서론

동형암호 기반 추론에서는 동일한 평문 모델이라도 polynomial modulus
chain, ring dimension, scale, rescale 경로에 따라 실행 가능성, 오차,
지연시간이 크게 달라진다. 단순히 가장 빠른 후보를 선택하면 출력
근사값의 작은 변화가 임계값 주변 표본의 최종 분류를 뒤집을 수 있다.
반대로 보수적인 기본 파라미터만 사용하면 안전할 수 있지만, workload에
불필요한 비용을 지불한다.

FlipGuard의 목표는 “가장 작은 오차” 또는 “가장 빠른 실행” 자체가
아니다. 목표는 선언된 결정 보존 조건을 만족하는 후보만 허용하고,
그 범위 안에서 방어 가능한 저비용 구성을 자동으로 생성하는 것이다.
후보 생성기는 내장 planner, 외부 autotuner 또는 수동 설정으로 교체할
수 있지만, 최종 결정은 동일한 decision-integrity gate와 locked protocol을
통과해야 한다.

### 1.1 연구 질문

- **RQ1:** 모델과 데이터만으로 고정 profile 이름에 투영하지 않고 정확한
  CKKS literal을 직접 생성할 수 있는가?
- **RQ2:** 직접 합성 및 실패 기반 수리가 고정 catalog 전수 실행보다
  encrypted configuration trial을 줄이는가?
- **RQ3:** validation에서 선택한 literal이 disjoint locked audit에서도
  재튜닝 없이 결정을 보존하는가?
- **RQ4:** 후보가 unsafe하거나 trial budget이 소진되었을 때 시스템이
  잘못 선택하지 않고 `NO_SAFE`를 반환하는가?
- **RQ5:** 직접 합성 literal의 추론 지연시간이 동일 프로세스 paired
  조건에서 bounded catalog 및 reference보다 낮은가?

### 1.2 기여

1. 모델 구조, 데이터 범위, 결정 임계값, margin policy, 보안 envelope 및
   실행 예산을 digest-bound workload contract로 정규화한다.
2. workload의 multiplicative depth와 정밀도 요구로부터
   `LogN`, `LogQ`, `LogP`, default scale을 직접 합성하고, 실패할 때만
   단조 repair를 생성한다.
3. sample-level margin과 관측 CKKS 오차를 결합한
   certify-or-reject decision-integrity gate를 제공한다.
4. validation selection과 disjoint locked audit을 분리하고, 선택 이후
   retuning을 금지하는 재현 가능한 검증 프로토콜을 제공한다.
5. complete bounded oracle, planner projection, paired latency,
   budgeted abstention 및 finite-domain `NO_SAFE` control을 분리하여
   각 주장에 필요한 근거와 금지된 과장을 명시한다.

## 2. 배경과 문제 정의

### 2.1 결정 보존

입력 \(x\)에 대한 평문 점수를 \(f_{\mathrm{plain}}(x)\), CKKS 근사 점수를
\(f_c(x)\), 결정 임계값을 \(\tau\)라 하자.

\[
d_{\mathrm{plain}}(x)=\mathbf{1}
\left[f_{\mathrm{plain}}(x)\ge\tau\right],
\qquad
d_c(x)=\mathbf{1}\left[f_c(x)\ge\tau\right].
\]

평문 margin과 관측 오차는 다음과 같다.

\[
m(x)=|f_{\mathrm{plain}}(x)-\tau|,
\qquad
e_c(x)=|f_c(x)-f_{\mathrm{plain}}(x)|.
\]

margin floor \(\delta\)에 대해

\[
V_{\mathrm{cert}}=\{x:m(x)>\delta\},\qquad
V_{\mathrm{amb}}=\{x:m(x)\le\delta\}.
\]

FlipGuard의 관측 검증 certificate는 \(V_{\mathrm{cert}}\)의 모든 표본과
모든 fresh-key run에서 먼저 다음의 충분조건을 구분한다.

\[
e_c(x)<m(x)\Longrightarrow d_c(x)=d_{\mathrm{plain}}(x).
\]

실제 admission은 더 엄격한 운용 reserve policy

\[
e_c(x)<\rho m(x)
\]

를 사용한다. 여기서 \(\rho\)는 margin utilization cap이고 \(1-\rho\)는
reserved margin fraction이다. Primary \(\rho=0.5\)는 사전 선언한
50%-utilization policy이며 CKKS 이론에서 도출된 상수나 최적값이 아니다.
내부 `SafetyFactor`/`alpha` 이름은 frozen evidence 호환성을 위한 alias다.
현재 주장은 \(V_{\mathrm{cert}}\)와 관측된 validation/audit artifact에
한정된다.

### 2.2 최적화 목표

후보 공간 \(C\)에서 관측 검증상 SAFE인 후보 집합을
\(C_{\mathrm{safe}}\)라 하자. 고정 catalog oracle은 선언된 유한
\(C\) 안에서 가장 낮은 측정 지연시간의 SAFE 후보를 선택한다.

\[
c^*_{\mathrm{catalog}}
=\arg\min_{c\in C_{\mathrm{safe}}} T(c).
\]

직접 합성 경로는 이 유한 catalog에 속할 필요가 없다. 따라서
FlipGuard V2는 직접 후보에 선언된 후보 공간 밖의 최적성 의미를 부여하지 않으며,
catalog와의 비교도 bounded comparison으로 한정한다.

직접 합성은 측정 지연시간 \(T(c)\)를 대상으로 여러 후보를 암호화
실행해 argmin을 구하지 않는다. 대신 workload contract에서

\[
s_0 \ge
\left\lceil-\log_2
\frac{\epsilon_{\mathrm{out}}}{S_{\mathrm{agg}}}\right\rceil
g_s,\qquad
L_Q \ge L_{\mathrm{graph}}+g_L
\]

를 만족하는 scale \(s_0\)와 Q-level 수 \(L_Q\)를 계산하고, 선언된
security envelope에서 \(\sum \log QP\)와 slot 요구를 수용하는 최소
`LogN`을 선택해 첫 literal \(c_0\)를 구성한다. 여기서
\(\epsilon_{\mathrm{out}}\)은 decision margin에서 유도한 출력 오차
예산, \(S_{\mathrm{agg}}\)는 관측 interval sensitivity, \(g_s,g_L\)은
고정된 guard다. 이는 정적 feasibility construction이지 SAFE 증명이나
latency optimum이 아니다.

암호화 실행은 \(c_0\)의 admission에 사용되고, 실패가 관측된 경우에만
미리 선언된 scale/level 방향으로 단조 repair한다. 따라서 본 논문에서
“탐색 효율”은 encrypted configuration trial 수로, “실행 성능”은 별도의
paired latency protocol로 평가한다. 두 주장을 혼합하지 않는다.

## 3. 관련 연구와 위치

[CHET](https://doi.org/10.1145/3314221.3314628)
[@dathathri2019chet]과
[EVA](https://doi.org/10.1145/3385412.3386023)
[@dathathri2020eva]는 tensor 또는
encrypted-vector 프로그램을 CKKS 실행으로 내리고 최적화했으며,
[HECO](https://www.usenix.org/conference/usenixsecurity23/presentation/viand)
[@viand2023heco]는
고수준 imperative program을 대상으로 end-to-end FHE compiler 구조를
제시했다. [HECATE](https://doi.org/10.1109/CGO53902.2022.9741265)
[@lee2022hecate]는
rescale 위치의 성능 효과를,
[ELASM](https://www.usenix.org/conference/usenixsecurity23/presentation/lee-yongwoo)
[@lee2023elasm]은
추정 output error와 latency의 trade-off를 최적화한다.
[DaCapo](https://www.usenix.org/conference/usenixsecurity24/presentation/cheon)
[@cheon2024dacapo]는
더 깊은 프로그램을 위한 bootstrapping 배치를 자동화한다. 따라서
FlipGuard는 최초의 FHE compiler, scale optimizer, 또는 error-aware
CKKS system을 주장하지 않는다.

[AutoPrivacy](https://papers.nips.cc/paper_files/paper/2020/hash/6244b2ba957c48bc64582cf2bcec3d04-Abstract.html)
[@lou2020autoprivacy]와
[AutoFHE](https://eprint.iacr.org/2023/162) [@ao2023autofhe]는
layer별 HE parameter
또는 polynomial activation, bootstrapping을 model accuracy와 latency에
맞춰 공동 탐색한다. Fuzzy logic와 linear programming을 결합한
parameter selector도 circuit와 사용자 우선순위에서 configuration을
자동화한다 [@cabrero2023fuzzy]. 2025년 preprint인
[FHE-Agent](https://arxiv.org/abs/2511.18653) [@xu2025fheagent]는
LLM controller와
deterministic tool을 결합해 static pruning, encrypted calibration,
layer-wise repair를 수행하며 MLP, LeNet, LoLa, AlexNet의 128-bit CKKS
configuration을 탐색한다. 이는 현재 FlipGuard보다 넓은 model coverage를
가지므로 FlipGuard는 최초의 자동 configuration 또는 failure-guided
repair도 주장하지 않는다.

[Application-Aware Approximate Homomorphic Encryption](https://eprint.iacr.org/2024/203)
[@alexandru2024applicationaware]은
회로뿐 아니라 허용 input domain까지 application specification에
포함하고 parameter generation, error estimation, validator를 그 범위에
결합해야 함을 형식화한다. FlipGuard workload contract는 이 방향과
맞닿지만, 현재 interval sensitivity는 planning signal일 뿐 sound error
bound가 아니다.

FlipGuard의 차별점은 후보 생성 방식이 아니라 최종 threshold decision을
기준으로 한 admission contract다. 외부 compiler, agent, 내장 synthesis,
수동 literal 중 어느 provider의 후보든 동일한 sample-level margin gate,
명시적 `V_amb`, `REJECTED`/`FAILED`/`NO_SAFE`, 그리고 선택 후
no-retuning locked audit을 통과해야 한다. 상세 출처와 금지된 novelty
표현은 `flipguard_v2_related_work.md`에 기록한다.

## 4. FlipGuard 방법

Figure 1(`figures/figure_01_framework.svg`)은 사용자 입력, digest-bound
contract, 직접 합성, 암호화 validation, 실패 기반 repair, 명시적
`NO_SAFE`, no-retuning locked audit으로 이어지는 주경로를 보인다. 고정
catalog는 이 경로에 포함되지 않으며 평가 절의 bounded oracle로만
등장한다.

### 4.1 Workload contract

최초 사용자 경로는 지원되는 model artifact와 held-out feature CSV를
입력받는다. 입력이 이미 model-input 공간이면
`row_id,label,x_0,...,x_{d-1}`를 사용한다. Raw 입력이면 model artifact에
동결된 selected feature name/index와 training-set mean/std를 사용하여
feature extraction 및 z-score standardization을 수행한다. `auto`, `model`,
`raw` 입력 공간을 구분하고 모호한 표현은 추측하지 않고 거절한다. 현재
preprocessing 범위는 이 selected-feature standardization으로 한정하며
임의의 변환 graph를 주장하지 않는다.

FlipGuard는 각 변환 행의 scaled logit, polynomial score, threshold
decision을 결정론적으로 materialize하고 canonical
configuration-validation CSV를 생성한다. 동결된 prepared CSV를 직접
받는 경로는 재현 및 evidence replay 용도로 유지한다. Contract builder는
다음을 기록한다.

- dataset/model/split identity와 model/source/prepared artifact의 SHA-256;
- source feature space, materialization schema, preprocessing method;
- 정확한 평문 계산 그래프 및 multiplicative depth;
- threshold, margin floor, margin-utilization cap
  (legacy `SafetyFactor` alias), \(V_{\mathrm{cert}}\),
  \(V_{\mathrm{amb}}\);
- validation 입력 범위와 empirical interval sensitivity;
- target security, required slots, packing strategy, allowed path;
- 최대 encrypted trial과 fresh-key 반복 수.

Empirical sensitivity는 첫 후보 생성 신호이며 analytical certificate가
아니다. materialized score와 decision은 동일 graph로 재계산하여
불일치 시 거절한다. Source preprocessing도 prepared feature와 행별로
재실행·대조하며 이 결과를 `source_replay_verified`로 기록한다. 이후
source/model/prepared bytes가 바뀌어도 실행 전에 거절한다. 최종 SAFE
판정은 반드시 실제 암호화 실행을 요구한다.

### 4.2 직접 CKKS configuration 합성

합성기는 graph depth와 Lattigo v6 rescale trace로 필요한 Q-prime 수를
구하고, output error budget 및 sensitivity로 정밀도 요구를 계산한다.
그다음 선언된 128-bit security envelope 안에서 backend가 수용하는
최소 `LogN`, Q/P prime bit sizes 및 scale을 구성한다. 생성 결과는
profile 별칭이 아니라 그대로 실행 가능한 parameter literal이다.

### 4.3 관측 기반 adaptive repair

첫 후보만 암호화 validation에서 실행한다.

- `SAFE`: 즉시 선택하고 탐색을 중단한다.
- numerical `REJECTED`: scale을 사전 고정된 step만큼 증가시킨다.
- level/rescale failure: Q level을 하나 증가시킨다.
- repair가 정의되지 않거나 trial/security budget이 끝남:
  `NO_SAFE`.

실패 전에는 이웃 후보를 미리 생성하거나 실행하지 않는다. 따라서
고정 profile ladder의 전수 sweep은 배포 알고리즘이 아니라 평가용
bounded oracle로만 사용된다.

### 4.4 Locked audit

선택된 literal, model digest, split manifest 및 policy를 고정한다.
Audit은 disjoint test partition에서 새 키로 literal을 정확히 한 번
평가하며 synthesis 또는 repair 함수를 호출하지 않는다. 결과가
SAFE가 아니면 selection claim은 실패한다.

## 5. 실험 설계

Seed 0는 development/ablation partition으로만 사용한다. Seeds 1-4는
policy freeze 이후 repeated-partition evaluation이며 각 audit은
no-retuning locked audit이다. 전체 범위는 고정 held-out artifact의
deterministic repeated partition 5개, 즉 10 dataset-model workloads x
5 partition seeds = 50 workload-partition instances다. 50개 행을 독립
표본으로 간주하지 않으며 dataset-model cluster 단위로 요약한다.
이 반복은 독립 training seed나 model generalization을 입증하지 않는다.

### 5.1 Workload matrix

- datasets: banknote, digits binary, iris binary, MNIST pool-16, WDBC;
- model graphs: linear model + cubic score, square-activation MLP + linear
  score;
- split seeds: 0–4;
- total workload instances: 50.

`linear_poly3`는 shallow-depth control이고,
`mlp_square_linear_score`가 현재 주요 비선형 graph다. 이 두 graph만으로
전체 신경망 또는 이미지 모델 일반성을 주장하지 않는다.

### 5.2 비교군

- direct synthesis + failure-driven repair;
- raw catalog: 11 built-in profiles × 2 paths = 22 executed
  candidates/workload;
- formal Security V2 catalog: 7 admitted profiles × 2 paths = 14
  candidates/workload;
- graph-aware planner projection;
- CKKS reference literal;
- latency-only minimum candidate;
- budgeted one-trial and finite all-unsafe `NO_SAFE` controls.

### 5.3 분할과 randomness

각 seed에서 configuration-validation과 locked-audit test를 분리한다.
Main selection은 후보당 3개의 fresh-key run을, locked audit은 선택
literal당 추가 3개의 fresh-key run을 사용한다. 암호화 randomness를
재현 가능한 seed로 고정하지 못하는 현재 backend 한계는 별도로
기록한다.

### 5.4 Paired latency

직접, bounded-catalog, reference arm을 workload별 한 프로세스에서
실행한다. 서로 다른 CKKS parameter는 같은 키를 공유할 수 없으므로
arm별 호환 키를 한 번 생성해 warm-up과 모든 측정에 고정한다. 최종
프로토콜은 6개의 고르게 선택한 행, 1 warm-up pass, 6 measured pass,
balanced cyclic-and-reverse order를 사용한다. 총 raw timing 수는
5,400개다. Primary inference unit은 raw timing이 아니라 50개 workload
instance이며, 10,000회 workload bootstrap interval을 보고한다.

## 6. 현재 결과

본 절의 수치와 논문용 Figure 1--6은
`results/thesis_grade_protocol/paper_artifacts_v2/current/`에서 생성한다.
현재 manifest 상태는 `NON_AUTHORITATIVE_SCAFFOLD`이며, 최종 evidence pack이
동일 source commit으로 모든 gate를 통과한 뒤에만
`FINAL_ADMISSIBLE`로 전환된다. Figure 1은 직접 합성을 주경로로,
Security V2에서 admissible한 고정 14-candidate catalog만 평가 전용
bounded oracle로 사용한다. 22-candidate 실행 ledger는 security-sensitivity
source records로만 보존한다.

제출 포맷 변환 시 사용하는 생성 artifact 매핑은 다음과 같다.

| Manuscript item | Generated artifact | Evidence role |
|---|---|---|
| Figure 1 | `figures/figure_01_framework.svg` | method workflow |
| Figure 2 | `figures/figure_02_search_effort.svg` | direct vs bounded search effort |
| Figure 3 | `figures/figure_03_locked_audit.svg` | disjoint locked audit |
| Figure 4 | `figures/figure_04_margin_floor_coverage.svg` | static policy sensitivity |
| Figure 5 | `figures/figure_05_no_safe_controls.svg` | abstention controls |
| Figure 6 | `figures/figure_06_paired_latency.svg` | pilot/final as manifest permits |
| Table 1 | `tables/01_direct_synthesis_locked_audit.md` | primary empirical evidence |
| Table 2 | `tables/02_search_effort_and_bounded_oracle.md` | bounded comparison |
| Table 3 | `tables/03_margin_floor_sensitivity.md` | policy sensitivity |
| Table 4 | `tables/04_no_safe_controls.md` | falsification controls |
| Table 5 | `tables/05_paired_latency.md` | pilot/final latency |

모든 경로는
`results/thesis_grade_protocol/paper_artifacts_v2/current/`를 기준으로
하며, hand-edited 표가 아니라 verified builder output을 사용한다.

### 6.1 직접 합성 및 locked audit

Table 1과 Figures 2--3은 직접 합성의 search effort와 선택 literal의
disjoint no-retuning audit 결과를 분리해 보고한다. 생성 Table 1의
`selection_source_replay_workloads`와
`audit_source_replay_workloads` 열은 최종 dual-replay protocol의 완전성을
별도로 보고한다. 현재 legacy preliminary pack의 이 값은 최종 결과로
해석하지 않는다.

| Metric | Result |
|---|---:|
| Workloads | 50 |
| Direct SELECTED | 50 |
| Configuration trials | 70 |
| Fresh-key validation runs | 210 |
| Initial REJECTED then repaired | 20 |
| Raw pre-security-filter executions | 1,100 |
| Formal Security V2 admitted candidate identities | 700 |
| Trial-count reduction vs bounded catalog | 93.64% |
| Locked audits passed without retuning | 50/50 |
| Fresh-key locked-audit runs | 150 |
| Audit flips / error violations | 0 / 0 |

이 결과는 직접 합성이 고정 catalog 전체를 실행하지 않고도 현재
workload matrix에서 방어 가능한 literal을 생성했음을 보인다. 하지만
선언된 후보 공간 밖의 최적성 또는 미관측 데이터 분포의 보장을 의미하지 않는다.

### 6.2 Planner projection

Table 2의 bounded-oracle 행과 planner projection evidence를 함께 사용해
candidate provider의 recall, pruning 및 regret을 해석한다.

| Metric | Result |
|---|---:|
| False NO_SAFE | 0/250 |
| Mean pruning | 68.18% |
| Overall optimum recall | 68% |
| Linear optimum recall | 100% |
| MLP optimum recall | 36% |
| Mean bounded latency regret | 0.7366% |
| Maximum regret | 8.6847% |

Planner는 유용한 candidate provider지만, 특히 MLP에서 fastest-safe
oracle의 대체물이라고 주장할 수 없다.

### 6.3 NO_SAFE controls

Table 4와 Figure 5는 budget-scoped abstention과 finite-domain
all-unsafe control을 서로 다른 행으로 유지한다.

Disjoint seed-0 one-trial pilot은 10개 중 4개 non-iris linear workload를
`NO_SAFE`로 반환하고 나머지 6개를 SAFE로 선택했다. unsafe selection은
0이었다. Seeds 1–4의 40-workload, 3-key confirmatory result는 아직
미실행이다.

`short_chain_3` 두 path로 제한한 retrospective finite domain에서는
100개 certificate가 `SAFE=0`, `REJECTED=75`, `FAILED=25`였고 50개
workload 모두 `NO_SAFE`였다. 같은 workload의 전체 catalog는 모두
SELECTED였다. Disjoint finite-domain runner의 banknote-linear smoke에서는
audit V_cert 207개 중 baseline path가 flip 96, error violation 207로
REJECTED였고 rescale path는 예상된 level exhaustion으로 FAILED였다.
따라서 해당 smoke domain은 독립적으로 `NO_SAFE`였지만, 50-workload,
300-attempt confirmatory 결과 전에는 retrospective 한계를 해소했다고
주장하지 않는다.

### 6.4 Paired latency pilot

Table 5와 Figure 6의 `paper_claim_allowed`가 false인 동안 아래 값은
protocol diagnostic으로만 유지한다.

Seed-0 pilot의 catalog/direct total-latency geometric-mean ratio는
1.9769였고 pilot workload-bootstrap interval은 [1.9225, 2.0379]였다.
세 arm의 decision flip은 모두 0이었다. 이 값은 반복 수와 순서 설계를
고정하기 위한 pilot이며 최종 논문 speedup으로 사용하지 않는다.

### 6.5 Policy sensitivity

Table 3과 Figure 4는 encrypted performance가 아니라 정적 coverage와
synthesis signature sensitivity를 보고한다.

5개 utilization cap, 9개 margin floor, 50개 workload,
validation/audit 두 partition에
대해 4,500개 정적 synthesis plan을 생성했다. 기존 1,100개 raw candidate
execution ledger의
certificate 상태와 50개 bounded-oracle 선택, direct initial literal은
\(\rho=0.1\)–0.9에서 모두 동일했다. 이는 minimum synthesis floor가
지배한 현재 grid의 empirical policy invariance이며 \(\rho=0.5\)의
이론적 최적성을 의미하지 않는다.

Margin floor 0.001의 validation coverage는 8,043/8,230(97.73%)이고,
0.0005에서는 8,142/8,230(98.93%)이다. 두 floor는 \(\rho=0.5\)에서 동일한
50개 정적 candidate signatures를 생성한다. 0.0005는
`SECONDARY_POLICY_SENSITIVITY`로만 유지하고 primary 0.001을 동결한다.
해당 audit은 policy 선택에 사용하지 않으며
`primary_policy_adoption_allowed=false`로 보고한다.

### 6.6 Structural extension

기존 primary graph보다 깊은 `mlp_square_poly3`에 대해 5개 dataset,
5개 seed, validation/audit 두 partition의 50개 정적 plan을 생성했다.
모든 plan이 depth 3, required Q-prime 10으로 분석됐고
`N14/Q10/scale22`를 제안했다. 정적 validation coverage는
3,992/4,115(97.01%), audit coverage는 4,033/4,150(97.18%)이다.

동결 정책으로 25/25 selection이 완료됐고, no-retuning locked audit은
24 PASS와 1 reserve-policy REJECT를 기록했다. REJECT instance의 최대
`error/margin`은 validation 0.470653, audit 0.561369였으며 decision flip은
0이었다. 따라서 이 결과는 `POLICY_REJECTED_WITHOUT_FLIP`이고
cryptographic correctness failure나 observed decision failure가 아니다.
Structural claim은 이 음성 결과를 포함해 `PARTIALLY_SUPPORTED`로 제한한다.

## 7. 위협과 한계

1. 현재 주요 실증은 5개 tabular dataset과 2개 graph에 한정된다.
2. SAFE는 관측 validation/audit 범위의 empirical certificate이며 전체
   입력 공간에 대한 형식 보장이 아니다.
3. 2024 security table은 parameter admission envelope이며 live security
   estimator가 아니다.
4. Catalog oracle은 22개 고정 후보에만 한정된다.
5. Planner의 MLP optimum recall은 36%로 낮다.
6. Margin-utilization cap 0.5와 margin floor 0.001의 보편적 최적성은 입증되지
   않았다.
7. Key generation과 encryption randomness의 재현 가능한 seed provenance가
   아직 부족하다.
8. Paired latency와 confirmatory `NO_SAFE` 실험은 clean committed source에서
   완료되어야 한다.

## 8. 논의

### 8.1 고정 configuration 실험의 역할

초기 fixed-profile 실험은 잘못된 실험이 아니라 후보 공간을 명시한
bounded oracle, 구현 regression, 그리고 negative control이다. 특히 기존
linear workload의 zero selected-speedup은 “linear model은 최적화할 수
없다”는 결과가 아니라 hand-authored ladder에 유용한 저비용 literal이
없을 수 있음을 보여준다. 따라서 본 방법의 주경로는 catalog를 전수
실행한 뒤 선택하는 것이 아니라 workload contract에서 literal을 직접
구성하고, 실패가 관측된 경우에만 수리하는 경로다.

이 역할 분리는 두 질문을 혼동하지 않게 한다. Configuration trial 수는
탐색 효율을 측정하고, 동일 프로세스 paired latency는 선택 literal의 실행
성능을 측정한다. Fixed catalog 결과는 전자의 비교 기준이자 제한된
oracle이며 선언된 범위 밖의 최적성 근거가 아니다.

### 8.2 연구 질문별 현재 상태

| RQ | Current evidence state | Submission gate |
|---|---|---|
| RQ1 direct literal synthesis | `PRELIMINARY_SUPPORTED` | final same-source selection/audit pack |
| RQ2 encrypted-trial reduction | `PRELIMINARY_SUPPORTED` | final manifest and bounded-count wording |
| RQ3 no-retuning locked audit | `PRELIMINARY_SUPPORTED` | final same-source locked audit |
| RQ4 safe abstention | `PARTIAL_CONTROL_EVIDENCE` | budgeted and disjoint finite-domain confirmatory packs |
| RQ5 paired latency | `PILOT_ONLY` | final paired pack with `paper_claim_allowed=true` |

이 표의 상태는 결과의 방향을 예고하는 표현이 아니라 claim registry의
사용 허용 범위다. 하나의 gate가 실패하면 해당 RQ를 약화하거나
미지원으로 보고하며, 성공한 다른 RQ로 대체하지 않는다.

### 8.3 입력 자동화와 범위

사용자 경로는 model artifact와 held-out raw 또는 model-input CSV를
받는다. Raw 경로는 artifact에 동결된 selected feature와 z-score
standardization을 적용하며 source transformation을 prepared row와 다시
대조한다. 이는 사용자가 score와 plaintext decision 열을 미리 계산해야
했던 초기 인터페이스를 제거한다.

현재 이 자동화는 지원되는 세 tabular graph form과 selected-feature
standardization에 한정된다. 임의의 sklearn/ONNX model import, categorical
encoding, image preprocessing, packing/layout synthesis는 후속 provider
또는 compiler integration 문제이며 현재 결과에 포함하지 않는다.

## 9. 재현성 및 artifact

최종 실험 진입점은 다음 명령이다.

```bash
scripts/run_thesis_final_confirmatory_suite.sh --resume
```

Runner는 `cmd/`, `internal/`, `scripts/`, `go.mod`, `go.sum`이 clean committed
state인지 먼저 검사한다. 이어서 regression, primary delta-0.001 selection,
no-retuning audit, budgeted 및 finite-domain abstention, structural extension,
paired latency를 실행하고 각 encrypted evidence pack에 동일 source commit을
기록한다. Source가 dirty하거나 pack commit이 다르면 fail-closed한다.

논문 표와 그림은 다음 명령으로 evidence pack의 native verifier를 먼저
통과시킨 뒤 생성한다.

```bash
python3 scripts/build_flipguard_v2_paper_artifacts.py --profile final --force
python3 scripts/build_flipguard_v2_paper_artifacts.py --profile final --verify
```

`appendix/evidence_manifest.json`은 입력 evidence tree, verifier, source
commit, 생성 output digest를 기록한다. 네 confirmatory pack, Security V2
static pack 및 semantic gate가 모두 통과하지 않으면 builder는
`FINAL_ADMISSIBLE`을 만들지 않는다. 현재
working draft의 `NON_AUTHORITATIVE_SCAFFOLD` artifact는 protocol review와 본문
초안에만 사용하며 제출 초록·결론의 수치 근거로 사용하지 않는다.

사용자 입력 재현성은 model, source CSV, canonical prepared CSV의 개별
SHA-256과 materialization schema, source feature space, preprocessing
method, `source_replay_verified`에 결합된다. 따라서 원시 데이터와
암호화 backend 사이의 평문 score/decision 준비 단계도 evidence chain의
일부다. Final primary 50개와 structural extension 25개 workload는
selection과 locked audit 모두
`--materialize-model-input` 경로를 사용해야 하며, 세 evidence pack은
model artifact, upstream source test CSV, 그리고 workload별 네
source/prepared partition CSV를 함께 snapshot한다. Model/source-test는
split seed 사이에서 중복 저장하지 않는다. 어느 partition의 replay
조건이라도 빠지면 paper builder는 `FINAL_ADMISSIBLE`을 거부한다.

## 10. 결론

FlipGuard는 CKKS configuration 생성과 최종 application decision의
admission을 분리한다. 내장 direct synthesis, 외부 autotuner, compiler,
수동 literal은 서로 다른 candidate provider가 될 수 있지만 동일한
margin-aware encrypted gate, explicit abstention, no-retuning locked audit을
통과해야 한다. 고정 catalog는 이 방법 자체가 아니라 제한된 비교
oracle로 유지된다.

현재 working draft의 결론은 이 방법론적 범위까지만 확정한다. 정량적
탐색 절감, locked-audit 결과, abstention control 및 latency 문장은
`FINAL_ADMISSIBLE` manifest에서 검증된 값으로만 최종 삽입한다.

<!-- BEGIN FINAL_CONCLUSION_SENTENCE -->
<!-- NON_AUTHORITATIVE_SCAFFOLD: no final conclusion is admissible. -->
<!-- END FINAL_CONCLUSION_SENTENCE -->

## 저자용 최종 결과 삽입 체크리스트 (본문 외)

- [ ] Step 7B.4 50-workload paired latency PASS 및 evidence freeze
- [ ] Step 7B.5 seeds 1–4 confirmatory budgeted abstention PASS
- [ ] disjoint finite-domain all-unsafe rerun
- [x] 정적 margin floor 및 margin-utilization-cap sensitivity
- [x] floor 0.0005는 secondary policy sensitivity로만 고정
- [ ] deeper graph / structural generalization
- [x] clean-commit final confirmatory one-command runner 및 evidence gates
- [ ] clean-environment replay와 release tag
- [x] related-work primary-source 검토 및 인용 경계 확정
- [x] verified evidence-only V2 표·그림·부록 빌더 및 결정성 검증
- [ ] 최종 표·그림·부록 manifest 생성

## 근거 위치

- `docs/evidence/direct_locked_audit_five_split_v1/`
- `docs/evidence/full_oracle_comparison_v1/`
- `docs/evidence/no_safe_controls_v1/`
- `docs/evidence/policy_sensitivity_v1/`
- `docs/evidence/paired_latency_pilot_v1/`
- `docs/research/flipguard_v2_claim_evidence_matrix.md`
- `docs/research/step_7b2a_direct_configuration_synthesis.md`
- `docs/research/step_7b4_paired_selected_latency_protocol.md`
- `docs/research/step_7b5_no_safe_budget_negative_control.md`
- `docs/research/step_7b6_policy_sensitivity.md`
- `docs/research/step_7b7_structural_extension.md`
- `docs/research/step_7b8_final_confirmatory_suite.md`
- `docs/research/step_7b9_paper_artifact_assembly.md`
- `docs/research/flipguard_v2_related_work.md`
- `docs/research/flipguard_v2_references.bib`

## 참고문헌

본문의 citation key 표기는
`docs/research/flipguard_v2_references.bib`의 검증된 1차 출처
메타데이터를 사용한다. 제출 포맷 변환 시 venue의 CSL/BibTeX 스타일로
자동 렌더링하며, preprint인 FHE-Agent는 최종 출판 여부를 다시 확인한다.
