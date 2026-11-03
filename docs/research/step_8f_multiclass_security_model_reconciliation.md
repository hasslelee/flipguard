# Step 8F. Multiclass Security-Model Reconciliation

## Reviewer concern

JOURNAL_EXTENSION_V1의 MLP-100과 LeNet-5-small literal은 Security Policy V2에서
PASS였지만, 기존 exact-estimator pack의 최상위 상태는
`FALSIFIED_UNDER_ESTIMATOR_MODEL`이었다. 이 두 상태를 candidate 단위로 결합하지
않으면 표준 모델 extension을 128-bit security evidence로 서술할 수 없다. 특히
전역 run 상태를 개별 candidate에 귀속하거나, Security-V2 table admission을 actual
runtime distribution에 대한 완전한 security proof로 표현하면 안 된다.

감사 결과 기존 exact-estimator input은 journal extension 이전의 14개 core row와
9개 modulus identity만 포함했다. 실패 객체는 Security-V2에서 이미 제외된
`LogN=14`, exact `log2(QP)=441.0000000356197` catalog identity였고, journal MLP와
LeNet candidate는 해당 input에 없었다. 따라서 이전의 journal candidate 실패
해석은 estimator 수치 실패가 아니라 **result-scope attribution 오류**였다.

## Literature precedent

Security admission 기준은 Bossuat et al., *Security Guidelines for Implementing
Homomorphic Encryption*, IACR Communications in Cryptology 1(4), 2025,
DOI `10.62056/anxra69p1`, Table 5.2를 따른다. 공식 문서와 ePrint는 각각
`https://doi.org/10.62056/anxra69p1` 및 `https://eprint.iacr.org/2024/463`이다.
Table cap은 보수적 admission reference이며 candidate의 exact Q와 evaluation-key
QP를 별도 객체로 검사한다.

Runtime parameter semantics는 Lattigo v6.2.0의 공식 source에 결합한다.
`core/rlwe/security.go`의 default는 `ring.Ternary{P: 2/3}`와
`ring.DiscreteGaussian{Sigma: 3.2, Bound: 19.2}`이다. Candidate-specific estimate는
`malb/lattice-estimator`의 guidelines-pinned commit
`8f1ff7e20a4d3391e3badff1d76825314db225bc`와 current sensitivity commit
`3e48ef421ec256afddb3e7d2249a77eab6e9ba12`에서 primal-uSVP, primal-BDD,
dual-hybrid를 `m=oo`, classical `RC.BDGL16`로 실행한다. Quantum cost model은
실행하지 않았으므로 `NOT_EVALUATED`이다.

## Implementation requirement

Lattigo v6.2.0에서 frozen candidate literal을 다시 materialize하고 실제 ordered
Q/P primes를 export했다. Concrete Q와 QP product를 Security Policy V2와 두 pinned
estimator model에 동일하게 입력했다. Direct/security policy, rho, margin floor,
scale, Q/P chain, LogN 및 candidate identity는 변경하지 않았다.

| Model/arm | LogN | default scale | depth | actual log2(Q) | actual log2(P) | actual log2(QP) | V2 cap | ceil headroom | minimum classical bits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MLP-100 gap-aware direct | 13 | 29 | 1 | 154.9992070672 | 39.0000005589 | 193.9992076262 | 214 | 20 | 145.2298510760 |
| MLP-100 graph-only | 13 | 32 | 1 | 170.0000989257 | 42.0000001774 | 212.0000991030 | 214 | 1 | 131.7868627080 |
| MLP-100 frozen catalog | 14 | 40 | 1 | 235.0000000108 | 110.0000000000 | 345.0000000108 | 430 | 84 | 166.3898582581 |
| LeNet-5-small direct | 15 | 44 | 4 | 802.0000005967 | 54.0000000002 | 856.0000005968 | 868 | 11 | 132.0469278366 |

MLP direct Q primes는
`[549755731969, 536903681, 536952833, 536690689, 536641537]`, P prime은
`[549756026881]`이다. LeNet direct Q primes 18개와 P prime
`[18014398511382529]`의 전체 ordered list는
`journal_multiclass_security_reconciliation_v1/materialized_candidates.json`에
기록한다. 두 graph 모두 square multiplication 때문에 relinearization-key QP
객체를 필요로 하며 rotation key는 사용하지 않는다.

분류는 `CLASS_S1_ESTIMATOR_ADAPTER_MISMATCH`, 세부 원인은
`RESULT_SCOPE_AND_AGGREGATION_MISMATCH`로 고정한다. Candidate-specific replay에서
네 arm 모두 두 estimator commit의 Q/ QP 검사를 통과했으므로 MLP와 LeNet의 최종
상태는 `SECURITY_CORRECTED_AND_REPLAYED`이다. Security amendment와 encrypted
replay는 필요하지 않다.

허용 문구는 다음과 같다.

> Journal candidate는 exact materialized Q와 QP를 사용한 Security Policy V2 및
> 두 개의 선언된 classical estimator model을 통과했다. 단, Lattigo error의
> truncation bound는 estimator에서 정확히 모델링되지 않았다.

`universal 128-bit security`, `exact runtime-distribution equivalence`, `quantum
128-bit security` 표현은 금지한다.

## Falsification test

다음 중 하나라도 발생하면 S1 closure를 거부한다.

1. Original 14-row estimator input에서 journal candidate identity가 발견된다.
2. Materialized Q/P가 frozen execution candidate의 ordered literal과 다르다.
3. Q 또는 QP 객체의 세 공격 중 하나가 실행 실패한다.
4. 두 estimator model 중 하나에서 candidate minimum `log2(rop) < 128`이다.
5. Candidate identity, graph/decision policy, scale, Q/P chain 또는 LogN이 변경된다.
6. Lattigo truncation과 estimator Gaussian을 exact-identical distribution이라고 쓴다.

현재 결과는 여섯 falsification condition을 모두 통과한다. 이 결론은 선언한 두
classical estimator model과 frozen candidates에 한정되며 arbitrary runtime
distribution 또는 quantum cost model로 일반화하지 않는다.
