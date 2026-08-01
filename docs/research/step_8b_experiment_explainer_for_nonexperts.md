# Step 8b: FlipGuard Experiment Explainer for Non-Experts

## Reviewer concern

The evidence contains several different units: dataset-model workloads,
deterministic partitions, encrypted candidate trials, fresh-key runs, sample
evaluations, and latency passes. Combining them into one large number makes
the study look larger but less trustworthy. A non-expert explanation must say
what each unit means and must not call 50 repeated-partition instances 50
independent workloads.

## Literature precedent

Systems papers such as HECATE, ELASM, and DaCapo separately report benchmark
programs, explored plans, actual executions, and latency measurements.
Application-Aware Approximate HE also motivates explicit application and input
scope. FlipGuard adopts that separation and adds validation/audit roles and
candidate identity provenance.

## Implementation requirement

### 200-character summary

FlipGuard는 5개 데이터셋과 2개 그래프의 50개 반복 파티션에서 CKKS 후보를
직접 만들고, 암호화 검증 뒤 안전한 후보만 잠근다. 700개 제한 catalog 대비
70회 trial을 사용했으며, 잠금 감사·NO_SAFE·보안·지연·영상 확장을 별도 증거로
검증했다.

### One-page explanation

FlipGuard의 질문은 “암호문 계산이 성공했는가?”에서 끝나지 않는다. 예측
점수가 임계값의 어느 쪽에 있는지가 평문 계산과 같고, 오차가 미리 남겨 둔
margin reserve 안에 있는지를 확인한다. 사용자는 모델, 입력 범위, decision
contract를 제공한다. FlipGuard는 graph depth와 scale 수요를 읽어 CKKS
literal을 직접 만들고, 최대 네 번의 암호화 trial 안에서 실행한다. 수치 오차나
level 부족은 미리 정한 단조 repair만 허용한다. SAFE 후보를 만들지 못하면
더 큰 후보를 무한히 찾지 않고 `NO_SAFE`를 반환한다.

핵심 연구는 5개 실제 tabular dataset과 linear/poly 및 square-MLP의 두 graph
family를 조합한 10개 dataset-model workload다. 각 workload는 동일한 고정
artifact를 다섯 deterministic partition으로 반복하므로 50
workload-partition instance가 되지만, 이들은 50개의 독립 dataset이나 독립
model이 아니다. seed 0의 10개는 개발·기술 결과이고 seeds 1-4의 40개가
post-freeze confirmatory 결과다.

Security-V2에서 허용된 bounded catalog는 7 profile과 2 path를 갖는다. 전체
formal denominator는 `7x2x50=700`, confirmatory denominator는
`7x2x40=560`이다. Direct synthesis는 각각 70회와 56회 candidate trial을
사용해 formal tuning work를 90% 줄였다. 보안 필터 이전에 실제로 실행한
1,100개 record는 역사적 비용과 security sensitivity 분석용이며 formal
denominator가 아니다.

선택한 literal은 configuration-validation 결과를 본 뒤 더 이상 바꾸지 않고
분리된 locked audit에서 재생했다. confirmatory 40개와 development 10개가
감사를 통과했고 retuning은 0이었다. 실패 가능한 설계도 별도로 검증했다.
사전 고정 budget control 40개 중 16개와 finite-domain control 50개 모두가
`NO_SAFE`를 냈다. 이는 전역적으로 안전한 구성이 없다는 증명이 아니라, 선언된
후보와 trial budget에서 SAFE를 확립하지 못했을 때 기권하는 동작의 증거다.

지연시간 실험은 세 arm, 50 instance, 여섯 측정 pass와 균형 순서를 사용해
총 5,400 record를 남겼다. 통계 단위는 raw record가 아니라 10개
dataset-model cluster다. 추가로 deeper polynomial graph 25개, Sobel/Harris와
CNN-lite의 1,700 encrypted observation, 그리고 3개 dataset에서 3개 독립
training/data seed로 만든 9개 model을 평가했다. Security-V2는 11개 profile
중 7개를 허용하고 4개를 formal catalog에서 제외했다.

Journal extension은 이 통제된 연구를 지우지 않는다. 대신 표준 MNIST
10-class MLP와 square/average-pool LeNet을 추가하고, binary threshold 조건을
top-two argmax gap 조건으로 확장한다. 따라서 “dataset 이름을 많이 늘렸다”가
아니라 “결정 계약과 graph scale을 표준 multiclass architecture에서 반증
가능하게 시험했다”가 목표다.

### Three-minute oral explanation

1. CKKS는 근사 계산이라 정답 숫자와 아주 조금 다를 수 있습니다. 분류
   임계값이나 argmax 근처에서는 작은 오차도 최종 class를 바꿀 수 있습니다.
2. FlipGuard는 가장 빠른 파라미터만 찾지 않습니다. graph와 decision margin을
   계약으로 받아 후보를 직접 합성하고, 실제 암호화 실행에서 decision과 reserve
   조건을 통과한 후보만 SAFE로 승인합니다.
3. 기존 핵심 실험은 5 dataset, 2 graph, 5 deterministic partition입니다.
   따라서 50개 instance지만 독립 workload는 10개입니다. seed 0는 개발,
   seeds 1-4는 confirmatory입니다.
4. Security-V2 bounded catalog의 formal 크기는 700이고 direct trial은 70이라
   trial reduction은 90%입니다. 보안 필터 전 1,100번 실행도 숨기지 않지만
   formal 비교 분모로 쓰지 않습니다.
5. 선택 후보는 40개 confirmatory와 10개 development audit에서 retuning 없이
   재생됐습니다. NO_SAFE control 90개는 안전한 후보를 확립하지 못할 때 시스템이
   억지 선택하지 않는지 확인합니다.
6. 5,400개 latency record는 10개 cluster를 통계 단위로 분석했습니다. 더 깊은
   polynomial, 영상 연산, CNN-lite, 독립 training seed도 별도 scope로 시험했습니다.
7. 남은 약점은 표준 multiclass graph입니다. Journal extension은 MNIST
   MLP-100과 LeNet-5-small에서 argmax gap 정리, encrypted validation, locked
   audit을 그대로 적용합니다. 결과가 REJECT나 NO_SAFE여도 숨기지 않습니다.

### Detailed experiment-scale table

| Evidence unit | Exact scale | Correct interpretation |
|---|---:|---|
| Controlled primary datasets | 5 | five real tabular datasets |
| Primary graph families | 2 | linear/poly and square-MLP families |
| Dataset-model workloads | 10 | primary cluster unit |
| Deterministic partitions | 5 per workload | repeated partitions of fixed artifacts |
| Workload-partition instances | 50 | not 50 independent workloads |
| Formal Security-V2 catalog | 700 | 7 admitted profiles x 2 paths x 50 |
| Direct candidate trials | 70 | formal all-instance tuning work |
| Confirmatory trial comparison | 56 / 560 | seeds 1-4 only; 90% reduction |
| Locked audit | 40 + 10 | confirmatory plus development; retuning 0 |
| Paired latency records | 5,400 | three arms x 50 x six passes x repetitions/order design |
| NO_SAFE controls | 90 | budget controls 40 plus finite-domain 50 |
| Structural polynomial instances | 25 | 25 selected; audit 24 pass and 1 reserve reject |
| Sobel/Harris/CNN-lite observations | 1,700 | scoped non-tabular encrypted observations |
| Independent training models | 9 | 3 datasets x 3 independent training/data seeds |
| Security profiles | 7 / 4 | admitted / excluded from 11 profiles |

## Falsification test

The explainer fails if it calls the 50 primary rows independent, uses 1,100 as
the Security-V2 denominator, merges seed 0 into confirmatory claims, presents
NO_SAFE as global infeasibility, treats 5,400 latency records as independent
samples, or hides the structural reserve-policy rejection.

