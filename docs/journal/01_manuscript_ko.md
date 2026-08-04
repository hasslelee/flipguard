# 결정 무결성 계약 기반 CKKS 실행 구성 직접 합성 및 검증

# FlipGuard: Direct Synthesis and Validation of CKKS Configurations under Decision-Integrity Contracts

{{ABSTRACTS}}

# I. 서론

근사 동형암호(approximate homomorphic encryption)는 복호화하지 않은 수치에 대해 산술 회로를 평가할 수 있게 한다. CKKS는 실수·복소수 근사 연산을 지원하여 암호화 추론에 널리 사용되지만, `LogN`, ciphertext modulus chain `Q`, key-switching modulus `P`, scale과 rescale 위치가 수치 오차와 실행비용을 함께 결정한다 [1]. 실행 가능한 구성이 곧 응용 결정에 안전한 구성이라는 뜻은 아니다. 분류 score가 threshold 또는 다른 class의 logit에 가까우면 작은 근사 오차도 최종 label을 바꿀 수 있다.

CHET와 EVA는 graph 분석과 compiler pass로 FHE parameter 및 실행 계획을 자동화했고 [2], [3], HECATE와 ELASM은 scale과 error-latency 관계를 정교하게 다뤘다 [4], [5]. HECO와 DaCapo 역시 lowering 및 bootstrapping management를 확장했다 [6], [7]. 이 연구들은 오차나 응용 정확도를 무시하지 않는다. 다만 서로 다른 provider가 생성한 후보를 동일한 최종 결정 계약으로 승인·거부하고, 후보가 없을 때 명시적으로 기권하며, 선택 literal을 분리된 audit에서 변경 없이 재생하는 문제는 별도의 assurance layer로 정리할 필요가 있다.

본 논문은 이를 위해 FlipGuard를 제안한다. FlipGuard는 지원되는 계산 그래프와 threshold 또는 multiclass argmax 결정 무결성 계약으로부터 CKKS literal을 직접 합성한다. 후보는 Security-V2 admission 이후 제한된 encrypted trial로 검증되며, 사전동결된 numerical·level repair만 적용된다. 어떤 후보도 SAFE임을 확립하지 못하면 `NO_SAFE`를 반환한다. 선택 literal은 byte-identical하게 잠긴 뒤 disjoint locked audit에서 synthesis와 repair 없이 재생된다.

기여는 다음과 같다. 첫째, binary threshold와 multiclass argmax를 공통의 finite-scope decision-integrity admission으로 정의한다. 둘째, graph fact와 decision budget에서 literal을 직접 합성하고 bounded failure-aware repair로 종료하는 경로를 구현한다. 셋째, `SAFE`, `REJECTED`, `FAILED`, `NO_SAFE` 및 no-retuning locked audit을 하나의 fail-closed protocol로 결합한다. 넷째, Security-V2 bounded catalog, paired latency, standard multiclass architecture, negative result와 재현 artifact를 포함하는 3-tier 평가를 제공한다.

주장 범위는 의도적으로 제한된다. FlipGuard는 최초 CKKS autotuner, arbitrary graph compiler, global optimum, distribution-wide decision safety, 완전한 analytical CKKS certificate 또는 production hardware 성능을 주장하지 않는다. 핵심은 구성 생성의 최초성이 아니라 provider와 최종 결정 승인 사이의 책임 경계를 명시하는 데 있다.

# II. 배경 및 관련 연구

## 2.1 CKKS 구성과 실행 객체

CKKS ciphertext는 근사값과 scale을 가지며 곱셈 후 rescale을 통해 modulus level을 소모한다 [1]. `Q`는 ciphertext 연산에 사용되고, `P`는 relinearization과 key switching을 포함한 evaluation-key 객체의 modulus에 참여한다. 따라서 본 연구는 ciphertext-Q와 evaluation-key-QP를 따로 검사한 뒤 필요한 모든 객체가 통과할 때만 후보를 security-admitted로 판정한다. Fresh-key run은 동일 literal과 입력을 새 key material로 다시 실행하는 단위이며, candidate trial이나 sample evaluation과 구분해 회계한다.

## 2.2 구성 자동화와 FlipGuard의 위치

CHET와 EVA는 high-level tensor 또는 vector program을 parameterized FHE 실행으로 낮춘다 [2], [3]. HECATE는 performance-aware scale optimization을, ELASM은 output error와 latency를 함께 고려한 scale management를 제안했다 [4], [5]. HECO는 scheme-aware compiler optimization을 제공하고 [6], DaCapo는 깊은 graph의 bootstrapping 위치를 자동 관리한다 [7]. AutoFHE는 CNN activation polynomial과 bootstrapping을 함께 탐색한다 [8]. Application-Aware Approximate HE는 회로뿐 아니라 input domain을 correctness·security 명세에 포함해야 함을 형식화한다 [9]. FHE-Agent는 LLM-guided tool orchestration으로 CKKS 후보를 pruning·calibration·repair하는 preprint다 [10].

Fig. 1은 이들 provider/autotuner와 FlipGuard의 역할을 구분한다. 기존 계층은 configuration 생성 또는 최적화를 담당할 수 있고, FlipGuard는 manual, bounded catalog, external provider, direct synthesizer의 출력을 동일한 decision-integrity gate로 평가한다. 본 연구의 main path는 direct synthesis이며 bounded catalog는 evaluation-only side path다.

{{FIGURE_01}}

**Fig. 1. Separation between configuration providers and the FlipGuard decision-integrity layer.**

**Table 1. Comparison of optimization and assurance roles.**

| Work | Main target | Candidate mechanism | Error/correctness role | Difference from FlipGuard |
|---|---|---|---|---|
| CHET/EVA [2], [3] | Compiler and parameter optimization | Graph analysis and compiler passes | Executability and numerical planning | FlipGuard adds a common final decision gate and locked replay |
| HECATE/ELASM [4], [5] | Scale or error-latency optimization | Scale scheduling/search | Output-error estimation | FlipGuard binds observed error to sample decision margins |
| HECO/DaCapo [6], [7] | General lowering or bootstrapping | IR optimization/planning | Scheme constraints and depth | FlipGuard does not replace compiler or bootstrap planning |
| AutoFHE [8] | Accuracy-latency trade-off | Network/polynomial search | Model-level accuracy | FlipGuard freezes the model and certifies finite decisions |
| Application-Aware AHE [9] | Application-bound correctness | Formal domain specification | Formal correctness/security | FlipGuard provides empirical finite-artifact admission only |
| FHE-Agent [10] | Practical CKKS automation | Agent-guided calibration/repair | Tool-based validation | FlipGuard's provider-independent gate is the primary object |

# III. 결정 무결성 계약

## 3.1 이진 threshold 결정

평문 score를 `f_plain(x)`, CKKS score를 `f_c(x)`, threshold를 `tau`라 하자. Decision margin과 절대 CKKS error는 각각

`m(x)=|f_plain(x)-tau|`, `e_c(x)=|f_c(x)-f_plain(x)|`

이다. `e_c(x)<m(x)`이면 CKKS score가 threshold를 건널 수 없으므로 평문 결정이 보존된다. 이는 충분조건이다. FlipGuard의 운용 정책은 더 보수적인

`e_c(x)<rho*m(x)`, `rho=0.5`

를 사용한다. `rho`는 margin-utilization cap이며 `1-rho`는 reserved margin fraction이다. 0.5는 CKKS 이론에서 도출된 상수나 최적값이 아니라 실험 전에 선언된 운용 정책이다.

## 3.2 다중 클래스 argmax 결정

평문 logits를 `z=(z_1,...,z_K)`, 유일한 평문 예측을 `c*=argmax_k z_k`라 하자. CKKS logits가 `zhat_k=z_k+Delta_k`이고 class별 error bound가 `|Delta_k|<=B_k`일 때, 모든 `j != c*`에 대해

`z_c* - z_j > B_c* + B_j`

이면 `argmax_k zhat_k=c*`이다. 실제로 `zhat_c* >= z_c*-B_c*`이고 `zhat_j <= z_j+B_j`이므로 위의 엄격한 부등식은 `zhat_c*>zhat_j`를 보장한다. Uniform bound `B`에는 top-two gap `g=z_top1-z_top2`에 대해 `2B<g`라는 corollary가 성립한다.

Fig. 2는 theorem 조건과 50% utilization policy를 분리한다. Equality는 approximate tie를 배제하지 못하므로 REJECTED이며, 평문 tie는 `V_amb`에 속한다. Lowest-index tie break는 deterministic representation일 뿐 certificate가 아니다. NaN과 Inf는 즉시 FAILED다.

{{FIGURE_02}}

**Fig. 2. Binary threshold and multiclass argmax decision contracts.**

## 3.3 상태와 보장 범위

`V_cert`는 margin floor보다 큰 결정 margin을 가진 certifiable input 집합이고, `V_amb`는 그 이하의 ambiguous input 집합이다. Candidate 실행이 실패하면 FAILED, `V_cert`에서 flip 또는 reserve-policy violation이 있으면 REJECTED, 모든 검사를 통과하면 SAFE다. Bounded trial 안에 SAFE 후보가 없으면 workload 결과는 NO_SAFE다. Coverage는 `|V_cert|/(|V_cert|+|V_amb|)`로 보고한다.

**Table 2. FlipGuard outcome semantics and assurance boundary.**

| State | Meaning | Permitted action | Not implied |
|---|---|---|---|
| SAFE | Predeclared finite validation passes decision and reserve checks | Literal may be locked | Distribution-wide safety |
| REJECTED | Execution succeeds but decision or reserve policy fails | Exclude candidate | Cryptographic execution failure |
| FAILED | Execution, identity, or non-finite check fails | Exclude and record reason | Numerical unsafety alone |
| NO_SAFE | No SAFE candidate is established within the frozen budget | Abstain | Global CKKS infeasibility |

# IV. FlipGuard 설계

## 4.1 Workload contract와 identity

Workload contract는 model artifact, supported input scope, graph signature, threshold 또는 argmax contract, margin floor, `rho`, split digest와 policy digest를 결합한다. Source artifact, prepared representation, semantic rows와 ordered rows의 digest를 분리한다. 이는 같은 source semantics가 full-precision provenance 표현 때문에 다른 prepared raw bytes를 가질 수 있기 때문이다. Identity가 복구되지 않으면 실행 결과를 재사용하지 않는다.

## 4.2 Direct literal 합성

Graph adapter는 multiplicative depth, rescale count, multiplication/addition count, required slots와 scale trace를 추출한다. Direct synthesizer는 minimum scale/prime floor, scale guard, first-prime guard와 required Q level을 적용하고 Security-V2가 허용하는 최소 `LogN`을 찾는다. 모델별 literal lookup table은 사용하지 않는다. Candidate ID는 literal과 graph/source binding을 포함하며, 첫 SAFE에서 멈춘다.

## 4.3 Encrypted validation과 bounded repair

후보는 세 fresh key에서 실행되어 per-sample score 또는 logits, error, margin/gap, flip과 reserve-policy status를 남긴다. Numerical failure에는 scale을 4 bit 올리는 repair, level failure에는 Q prime 하나를 추가하는 repair를 적용하되 최대 trial은 4로 동결되어 있다. Repair는 validation 결과에만 반응하고 audit 입력은 보지 않는다. 이 구조는 heuristic을 제거하지 않지만, heuristic의 입력·상수·종료·실패 결과를 versioned policy로 만든다.

## 4.4 NO_SAFE와 literal lock

모든 후보가 REJECTED 또는 FAILED이면 `NO_SAFE`를 반환한다. SAFE 후보는 literal과 source/model/policy digest를 잠근다. Locked audit은 이 literal을 byte-identical하게 재생하며 synthesis, repair, candidate 교체를 호출할 수 없다. Audit rejection은 policy를 낮추는 입력이 아니라 claim을 낮추는 과학적 결과다.

## 4.5 Security admission

Security Policy V2는 최신 Security Guidelines Table 5.2의 Category-128 uniform-ternary cap을 보수적 admission reference로 사용한다 [11]. Ciphertext 객체는 Q, evaluation-key 객체는 QP를 검사한다. Journal extension은 exact Q/P prime을 두 classical estimator adapter에 재생했다. Runtime `Xs` ternary mapping은 일치하지만, Lattigo의 bounded discrete-Gaussian `Xe`는 estimator의 untruncated Gaussian proxy와 정확히 동일하지 않다. Quantum cost model도 평가하지 않았으므로 security claim은 이 caveat를 포함한다.

# V. 구현 및 평가 방법

## 5.1 구현과 protocol freeze

FlipGuard는 Go, Lattigo v6.2.0과 Python artifact tool로 구현되었다. Go backend는 graph fact, literal materialization, encrypted execution과 certification을 담당하고 Python tool은 split, aggregation, bootstrap, evidence freeze와 verifier를 담당한다. 실행 binary, model/input/policy digest, keyset, process/order metadata를 ledger에 기록한다. RC2, Paper Artifacts V3, Completion V10과 기존 석사논문 evidence는 이번 extension에서 변경하지 않았다.

## 5.2 3-tier 실험 계층

Fig. 3과 Table 3은 평가 단위를 세 tier로 고정한다. Controlled Primary의 50 rows는 10 dataset-model workload에 대한 다섯 deterministic repeated partition이지, 50 independent workload가 아니다. Seed 0는 development/descriptive이고 seeds 1-4만 confirmatory aggregate다. Standard Multiclass는 MNIST 공식 test 10,000 images에서 SHA-256 class-stratified rank로 고정한 1,000 images를 500 validation과 500 locked audit으로 분리하며 overlap은 0이다 [12]. 모델별 각 역할은 세 fresh key로 실행한다.

{{FIGURE_03}}

**Fig. 3. Three-tier evaluation hierarchy and statistical units.**

**Table 3. Evaluation hierarchy and declared units.**

| Tier | Workloads/models | Validation and audit unit | Main purpose |
|---|---|---|---|
| Controlled Primary | 5 real tabular datasets x 2 binary graphs | 10 clusters x 5 repeated partitions | Trial reduction, locked audit, paired latency |
| Standard Multiclass | MNIST MLP-100 and LeNet-5-small | 500 validation + 500 audit images/model, 3 keys | Argmax contract and standard-model breadth |
| Additional Robustness | poly3, Sobel, Harris, CNN-lite, 9 trained models | Adapter-specific frozen finite sets | Negative result, image operators, training seeds |

MNIST MLP는 `784 -> 100 -> square -> 10 logits`이며 plaintext test accuracy는 0.9776이다. LeNet-5-small은 `conv5x5(6) -> square -> average pool -> conv5x5(16) -> square -> average pool -> FC120 -> square -> FC64 -> square -> 10 logits`이고 accuracy는 0.9891이다. 이는 ReLU와 max pooling을 암묵적으로 바꾼 표준 LeNet claim이 아니라 FHE-compatible square-activation adapter다.

## 5.3 Bounded catalog와 비용 단위

Primary catalog 11 profiles 중 Security-V2 admitted profile은 7개이고 두 path와 50 instance를 결합한 formal denominator는 700이다. Confirmatory denominator는 560이다. Historical 1,100 encrypted executions은 pre-security ledger로만 남으며 formal trial-reduction 분모가 아니다. Multiclass에서는 동일한 7개 frozen profile을 모델별로 static plan한 14 profile-model pair를 denominator로 기록하되, 실제 encrypted 실행 가능한 MLP 후보는 6개이고 LeNet 후보는 0개다. Static screening과 encrypted candidate execution을 같은 비용으로 취급하지 않는다.

Candidate trial, repair, fresh-key run, encrypted sample evaluation과 wall-clock을 별도 기록한다. Fastest-safe는 Security-V2-admitted bounded set 안에서만 정의되며 global oracle 또는 global optimum을 뜻하지 않는다.

## 5.4 Paired latency protocol

Primary latency는 한 host에서 warm-up 1, measurement 6, balanced cyclic/reverse order, no outlier removal로 수행했다. 통계 단위는 10 dataset-model cluster이고 partition은 cluster 내부 반복이다. MLP amendment는 locked-audit 500 images 중 실행 전에 SHA-256 class-stratified rank로 class당 10개, 총 100개를 고정했다. S29 gap-aware, S32 graph-only, catalog S40 `short_chain_5`를 3 keyset, 6 pass로 실행하여 5,400 records를 얻었다. Image-level paired ratio를 class-stratified image-cluster bootstrap 10,000회로 요약했다. 동시 CKKS process는 없고 outlier는 제거하지 않았다.

# VI. 평가 결과

## 6.1 Controlled Primary

Table 4와 Fig. 4는 primary 결과를 요약한다. Direct trial은 전체 70/700, confirmatory 56/560으로 각각 90% 감소했다. Confirmatory selected literal은 40/40 locked audit을 통과했고 seed 0 development는 10/10이었다. Retuning은 0이다. 이 감소율은 Security-V2 bounded candidate trial 단위이며 1,100 historical execution 또는 가능한 CKKS 공간 전체와의 비교가 아니다.

**Table 4. Controlled Primary selection, audit, and latency results.**

| Population | Direct/catalog trials | Trial reduction | Locked-audit PASS | Catalog/direct total ratio | 95% cluster CI |
|---|---:|---:|---:|---:|---:|
| Development seed 0 | 14/140 | 90.0% | 10/10 | 3.146139 | [2.364689, 4.183993] |
| Confirmatory seeds 1-4 | 56/560 | 90.0% | 40/40 | 3.140660 | [2.342334, 4.215313] |
| Combined descriptive | 70/700 | 90.0% | 50/50 | not an inferential aggregate | - |

{{FIGURE_04}}

**Fig. 4. Direct candidate trials versus the Security-V2 bounded catalog.**

Security-V2 bounded-catalog total latency divided by direct total latency의 confirmatory dataset-model-cluster geometric mean은 3.140660이고, 95% cluster-bootstrap interval은 [2.342334, 4.215313]이다. Fig. 5는 이 ratio 정의와 cluster 단위를 함께 표시한다. 40/40 instance가 완결되었고 failure는 0이었다. 한 host에서의 비교이므로 production 또는 모든 workload의 speedup으로 일반화하지 않는다.

{{FIGURE_05}}

**Fig. 5. Confirmatory paired total-latency ratio for the Controlled Primary.**

## 6.2 Standard Multiclass validation과 catalog coverage

Table 5는 direct, catalog, security와 audit 결과를 모델별로 분리한다. MLP S29와 LeNet S44는 각각 1 trial, 0 repair로 선택되었다. 모델별 500 validation과 500 audit images를 세 fresh key로 평가한 결과 두 모델 모두 SAFE, argmax flip 0, reserve-policy rejection 0, retuning 0이었다. 이는 한 frozen model과 finite input artifact의 결과다.

MLP에서는 7개 frozen profile 중 6개가 executable SAFE이고 `short_chain_3` 한 개가 required Q level 부족으로 PLAN_UNSUPPORTED였다. LeNet에서는 7개 모두 required depth를 지원하지 못했다. 정확한 결론은 `PLAN_UNSUPPORTED_WITHIN_FROZEN_CATALOG`이다. FlipGuard direct synthesis가 security gate를 통과하는 S44 literal을 만든 것은 frozen catalog coverage보다 넓은 direct construction을 보여주지만, 모든 CKKS catalog에 SAFE 후보가 없거나 direct가 LeNet catalog보다 빠르다는 뜻은 아니다.

**Table 5. Standard multiclass selection, audit, catalog, and security results.**

| Model | Accuracy | Direct literal | Val/Audit images | Audit outcome | Frozen catalog | Estimator status |
|---|---:|---|---:|---|---|---|
| MLP-100 | 0.9776 | N13, Q5, S29 | 500/500 | SAFE, 0 flips | 6 SAFE, 1 PLAN_UNSUPPORTED | min 145.229851 classical bits |
| LeNet-5-small | 0.9891 | N15, Q18, S44 | 500/500 | SAFE, 0 flips | 7/7 PLAN_UNSUPPORTED | min 132.046928 classical bits |

## 6.3 Natural top-two-gap activation과 focused latency

MLP의 frozen natural gap은 per-logit synthesis budget 0.0106245를 허용하여 gap-aware direct path가 S29 literal을 만들었다. Graph-only fixed tolerance 0.001은 같은 graph에서 S32를 만들었다. 두 literal은 모두 Security-V2와 두 estimator adapter를 통과했다. 따라서 natural-data decision contract가 실제 literal을 바꾸는 `A_LITERAL_EFFECT_SUPPORTED` 사례가 관측되었다.

그러나 literal 차이가 자동으로 latency 차이를 만들지는 않았다. Table 6과 Fig. 6에서 graph-only S32 total latency / gap-aware S29 total latency의 geometric mean은 0.999780이고 95% interval은 [0.998648, 1.000920]으로 1을 포함한다. 결론은 `LITERAL_EFFECT_ONLY`이며 S29의 S32 대비 latency superiority는 인정하지 않는다. 반면 catalog S40/S29 ratio는 1.981795, interval [1.979758, 1.983842]였다. Graph-only S32에는 별도의 full 500-image locked audit이 없고 이 amendment의 decision check는 frozen 100-image latency subset에 한정된다.

**Table 6. Focused MLP-100 paired-latency amendment.**

| Pair (numerator/denominator) | Total ratio | 95% image-cluster CI | Eval-only ratio | Decision observations | Claim |
|---|---:|---:|---:|---:|---|
| Graph-only S32 / gap-aware S29 | 0.999780 | [0.998648, 1.000920] | 0.999932 | 1,800/arm | Literal effect only |
| Catalog S40 / gap-aware S29 | 1.981795 | [1.979758, 1.983842] | 1.938752 | 1,800/arm | Scoped paired latency admitted |

{{FIGURE_06}}

**Fig. 6. Focused MLP-100 paired total-latency ratios and 95% intervals.**

## 6.4 NO_SAFE, structural negative result와 additional robustness

Predeclared one-candidate budget control은 40건 중 16건에서 NO_SAFE를, declared finite two-candidate domain은 50/50에서 NO_SAFE를 반환했다. 이는 bounded scope에서 기권이 작동함을 보일 뿐 global infeasibility를 증명하지 않는다. `mlp_square_poly3`는 25/25 selection 이후 locked audit에서 24 PASS와 1 reserve-policy REJECT를 보였다. 해당 row는 decision flip 0인 `OBSERVED_DECISION_PRESERVED`, `RESERVE_POLICY_REJECTED`, `POLICY_REJECTED_WITHOUT_FLIP`이며 삭제하거나 retuning하지 않았다.

Sobel은 400 validation+400 audit, Harris는 200+200, CNN-lite는 250+250 finite observations에서 locked-audit PASS였다. 세 dataset과 세 independent training/data seed로 만든 9 model instance도 9/9 selection 및 audit PASS였다. Table 7은 이 결과를 하나의 독립 표본 수로 합산하지 않고 adapter별 범위로 제시한다.

**Table 7. Abstention, negative results, and additional robustness.**

| Study | Declared unit | Result | Claim boundary |
|---|---|---|---|
| Budget NO_SAFE | 40 confirmatory controls | 16 NO_SAFE, 24 SELECTED | Frozen one-candidate budget only |
| Finite-domain NO_SAFE | 50 controls | 50 NO_SAFE | Declared two-candidate domain only |
| Polynomial structural | 25 instances | 24 audit PASS, 1 policy REJECT, 0 flips | One deeper polynomial graph |
| Sobel/Harris/CNN-lite | 800/400/500 observations | Locked-audit PASS | Finite scalar-replicated adapters |
| Independent training seeds | 3 datasets x 3 models | 9/9 selection and audit PASS | Nine trained models only |

## 6.5 Security reconciliation과 재현성

초기 exact-estimator global status는 `FALSIFIED_UNDER_ESTIMATOR_MODEL`이었으나 journal candidate attribution이 성립하지 않았다. Root-cause audit 결과 기존 estimator input은 journal 후보를 포함하지 않은 14개 pre-journal row였고, global failure는 이미 Security-V2에서 excluded된 N14/QP441 catalog identity에서 발생했다. 이를 MLP와 LeNet에 귀속한 것이 `RESULT_SCOPE_AND_AGGREGATION_MISMATCH`, 즉 CLASS S1이었다.

Candidate-specific exact Q/P replay에서 MLP S29, graph-only S32, catalog S40, LeNet S44의 Q와 QP 객체는 두 classical estimator adapter에서 모두 128 bit를 넘었다. 최소값은 각각 145.229851, 131.786863, 166.389858, 132.046928 bit였다. Policy, literal 또는 encrypted evidence를 변경하지 않았고 security amendment와 encrypted replay는 0이었다. 다만 Xe truncation exact equivalence와 quantum model은 평가하지 않았으므로 “universal 128-bit security”라고 쓰지 않는다.

모든 결과 pack은 source commit, binary/model/input/policy digest, raw ledger, failure와 SHA256SUMS를 가진다. Pre-reconciliation checkpoint와 원래 fail-closed estimator record도 보존한다. 최종 journal extension은 predecessor digest를 참조하는 overlay이므로 RC2, V3, V10과 authoritative thesis를 수정하지 않는다.

# VII. 논의 및 한계

첫째, direct synthesis는 수학적으로 유일한 configuration을 도출하는 solver가 아니라 versioned graph facts와 보수적 floor를 사용하는 bounded policy다. Controlled Primary의 natural alpha grid에서는 minimum floor가 literal을 지배하여 decision-aware와 graph-only initial literal이 같았다. 반면 MLP-100 top-two gap에서는 S29와 S32가 갈라져 decision contract의 natural activation을 관측했다. 이 한 사례를 모든 natural data에 일반화하지 않는다.

둘째, finite validation SAFE는 미래 audit 통과 정리가 아니다. Polynomial extension의 한 reserve-policy REJECT는 flip 없이도 predeclared reserve가 unseen audit에서 소진될 수 있음을 보여준다. 이는 framework 실패를 숨겨야 할 이유가 아니라 selection과 locked audit을 분리해야 할 근거다. 운영에서는 REJECT를 보고하고 해당 literal을 decision-preserving arm으로 사용하지 않는다.

셋째, multiclass breadth는 MLP-100과 FHE-compatible LeNet-5-small 두 architecture, 하나의 MNIST model seed, scalar-replicated feature-ciphertext adapter에 한정된다. Arbitrary packed CNN, 일반 rotation/layout 최적화, CIFAR 계열 또는 modern deep network는 평가하지 않았다. 기존 independent training-seed evidence는 tabular 범위의 별도 보완이며 MNIST model-seed 일반화를 대신하지 않는다.

넷째, bounded catalog는 frozen profile의 상대 기준이다. LeNet의 7/7 PLAN_UNSUPPORTED는 catalog breadth의 negative result이지 CKKS 전체 공간의 infeasibility가 아니다. 사후에 LeNet용 catalog를 추가하지 않은 것은 비교 무결성을 위한 선택이다. 따라서 LeNet latency superiority와 global optimum은 BLOCKED다.

다섯째, latency는 한 host와 고정 process protocol에서 측정했다. Primary ratio는 dataset-model cluster, MLP amendment는 image cluster가 통계 단위다. 5,400 raw records나 1,800 pairs를 독립 표본으로 취급하지 않는다. 다른 CPU, library 또는 packing에서 같은 ratio를 기대해서는 안 된다.

여섯째, Security-V2 table과 estimator replay는 명시적 모델 아래의 admission이다. Actual runtime Xe truncation을 estimator가 정확히 표현하지 않으며 quantum cost도 평가하지 않았다. 본 논문은 이러한 model sensitivity를 숨기지 않고 policy admission, estimator outcome, distribution caveat를 별도 열로 보고한다.

# VIII. 결론

FlipGuard는 지원 graph와 decision-integrity contract에서 CKKS literal을 직접 합성하고, bounded encrypted validation과 failure-aware repair로 후보를 승인·거부하며, SAFE 후보를 확립하지 못하면 NO_SAFE로 기권하고, 선택 literal을 disjoint audit에서 retuning 없이 재생한다. Controlled Primary에서 formal candidate trial은 90% 감소했고 confirmatory 40/40 locked audit을 통과했다. 한 host의 catalog/direct total-latency cluster ratio는 3.140660이었다.

Standard Multiclass에서 MLP-100과 LeNet-5-small direct literal은 finite 500-image validation과 500-image audit에서 argmax flip 없이 SAFE였다. MLP natural top-two-gap은 S32와 다른 S29 literal을 만들었지만 S29/S32 latency superiority는 관측되지 않았다. Catalog/S29 paired 차이, LeNet frozen-catalog 미지원, structural reserve-policy rejection과 NO_SAFE를 함께 공개함으로써 성공과 claim boundary를 같은 artifact에 남겼다.

이 결과는 universal autotuning이나 complete analytical certificate가 아니다. 본 논문의 기여는 구성 생성, decision admission, abstention, literal lock, security-filtered comparison과 reproducible evidence를 하나의 제한되고 감사 가능한 CKKS workflow로 결합한 데 있다.

# References

[1] J. H. Cheon, A. Kim, M. Kim, and Y. Song, “Homomorphic encryption for arithmetic of approximate numbers,” in Advances in Cryptology - ASIACRYPT 2017, pp. 409-437, 2017.

[2] R. Dathathri et al., “CHET: An optimizing compiler for fully-homomorphic neural-network inferencing,” in Proc. ACM SIGPLAN PLDI, pp. 142-156, 2019.

[3] R. Dathathri et al., “EVA: An encrypted vector arithmetic language and compiler for efficient homomorphic computation,” in Proc. ACM SIGPLAN PLDI, pp. 546-561, 2020.

[4] Y. Lee et al., “HECATE: Performance-aware scale optimization for homomorphic encryption compiler,” in Proc. IEEE/ACM CGO, pp. 193-204, 2022.

[5] Y. Lee et al., “ELASM: Error-latency-aware scale management for fully homomorphic encryption,” in Proc. 32nd USENIX Security Symposium, pp. 4697-4714, 2023.

[6] A. Viand, P. Jattke, M. Haller, and A. Hithnawi, “HECO: Fully homomorphic encryption compiler,” in Proc. 32nd USENIX Security Symposium, pp. 4715-4732, 2023.

[7] S. Cheon et al., “DaCapo: Automatic bootstrapping management for efficient fully homomorphic encryption,” in Proc. 33rd USENIX Security Symposium, pp. 6993-7010, 2024.

[8] W. Ao and V. N. Boddeti, “AutoFHE: Automated adaption of CNNs for efficient evaluation over FHE,” in Proc. 33rd USENIX Security Symposium, pp. 2173-2190, 2024.

[9] A. Alexandru, A. Al Badawi, D. Micciancio, and Y. Polyakov, “Application-aware approximate homomorphic encryption: Configuring FHE for practical use,” IACR Communications in Cryptology, vol. 2, no. 4, 2026.

[10] N. Xu et al., “FHE-Agent: Automating CKKS configuration for practical encrypted inference via an LLM-guided agentic framework,” arXiv:2511.18653, preprint, 2025.

[11] J.-P. Bossuat et al., “Security guidelines for implementing homomorphic encryption,” IACR Communications in Cryptology, vol. 1, no. 4, 2025.

[12] Y. LeCun, L. Bottou, Y. Bengio, and P. Haffner, “Gradient-based learning applied to document recognition,” Proceedings of the IEEE, vol. 86, no. 11, pp. 2278-2324, Nov. 1998.
