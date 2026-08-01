# 제2장 배경

## 2.1 CKKS 근사 동형암호

CKKS는 실수 또는 복소수 값에 대응하는 벡터를 다항식 ring의 plaintext로 인코딩하고, 암호문 상태에서 덧셈과 곱셈을 수행할 수 있게 하는 근사 동형암호 방식이다 [@cheon2017ckks]. 복호화 결과는 평문 계산값과 비트 단위로 동일할 필요가 없으며, 인코딩과 연산 과정의 근사 오차를 포함한다. 이러한 성질은 선형대수와 기계학습 추론처럼 일정한 수치 오차를 수용할 수 있는 계산에 적합하다. 동시에 응용이 허용할 수 있는 오차를 명확히 정의하지 않으면, 암호 연산이 성공했다는 사실만으로 응용 결과의 적합성을 판단할 수 없다는 문제를 낳는다.

CKKS 구현은 cyclotomic ring dimension `N`, ciphertext modulus chain `Q`, special modulus `P`, scale과 level을 주요 구성 요소로 사용한다. 보통 `LogN`은 `log2(N)`을 뜻하며, `Q`는 ciphertext가 연산 중 사용하는 modulus prime들의 곱, `P`는 relinearization과 key switching에 쓰이는 auxiliary modulus를 나타낸다. `LogQ`, `LogP`, `LogQP`는 해당 modulus product의 bit 크기를 요약한다. 동일한 graph에서도 더 큰 scale은 표현 정밀도를 높일 수 있지만 prime budget을 더 요구하며, 더 긴 chain은 곱셈 깊이를 수용하지만 계산과 키 비용 및 보안 제약을 키운다.

곱셈 후 ciphertext의 scale은 대략 피연산자 scale의 곱으로 증가한다. Rescale은 modulus prime 하나를 소비하면서 scale을 낮추어 다음 연산의 수치 범위를 관리한다. Relinearization은 곱셈으로 증가한 ciphertext 차수를 다시 다루기 쉬운 형태로 낮춘다. 따라서 graph의 multiplicative depth와 rescale trace는 필요한 Q chain 길이 및 각 prime 크기와 직접 연결된다. 부트스트래핑은 소모된 계산 능력을 갱신할 수 있지만 비용이 크며, 본 연구의 primary graph는 부트스트래핑을 포함하지 않는 leveled CKKS 범위다.

## 2.2 실행 단위와 비용 회계

본 연구는 서로 다른 비용 단위를 혼합하지 않는다. **Candidate trial**은 하나의 CKKS literal을 configuration-validation artifact에 대해 시험한 횟수다. 하나의 trial은 여러 fresh-key run을 포함할 수 있다. **Fresh-key run**은 새 secret/evaluation key material을 생성하고 동일 후보를 실행하는 한 번의 반복이다. **Encrypted sample evaluation**은 하나의 sample이 하나의 fresh-key run에서 암호화 평가된 횟수다. **Wall-clock latency**는 setup/key generation, evaluation-only, total 구간을 구분해 측정한다.

이 구분은 연구 주장의 해석에 중요하다. 예를 들어 후보 1개를 세 fresh-key로 평가하면 candidate trial은 1이지만 key run은 3이다. 200개 sample을 세 key로 평가하면 encrypted sample evaluation은 600이다. Catalog 후보 수, direct trial 수, key run 수를 서로 바꾸어 사용하면 tuning-work 감소를 과장하거나 실제 실행비용을 축소할 수 있다. FlipGuard의 trial-reduction 주장은 candidate trial 단위로만 정의하며, key run과 sample evaluation은 별도 회계로 보고한다.

## 2.3 Threshold decision과 margin

입력 `x`에 대한 평문 score를 `f_plain(x)`, CKKS candidate `c`의 score를 `f_c(x)`, decision threshold를 `tau`라 하자. 평문 decision과 CKKS decision은 각각 score가 threshold 이상인지 여부로 정의한다. 평문 score가 threshold에서 떨어진 거리는 다음 decision margin으로 나타낸다.

\[
m(x)=\left|f_{plain}(x)-\tau\right|.
\]

CKKS 절대오차는 다음과 같다.

\[
e_c(x)=\left|f_c(x)-f_{plain}(x)\right|.
\]

`m(x)>0`인 sample에서 다음 조건은 decision 보존의 충분조건이다.

\[
e_c(x)<m(x) \quad\Longrightarrow\quad d_c(x)=d_{plain}(x).
\]

이는 삼각부등식에 따른 단순하지만 중요한 결과다. CKKS score가 평문 score에서 threshold까지의 거리보다 적게 이동하면 threshold를 건널 수 없다. 이 명제는 `rho=0.5`에서만 성립하는 정리가 아니며, 특정 CKKS parameter가 해당 조건을 항상 만족한다고 증명하는 분석적 certificate도 아니다. 개별 관측에서 `e_c(x)<m(x)`이면 그 관측의 decision이 보존된다는 수학적 관계다.

FlipGuard는 이 충분조건과 별도로 다음 운용 reserve policy를 사용한다.

\[
e_c(x)<\rho m(x), \qquad \rho=0.5.
\]

여기서 `rho`는 **margin utilization cap**, `1-rho`는 **reserved margin fraction**, `rho*m(x)`는 **operational acceptance budget**이다. Primary `rho=0.5`는 오차가 margin의 절반 미만일 때만 승인하는 사전동결 50% margin-utilization 정책이다. 이 값은 CKKS 이론에서 도출된 보편 상수도 아니고 경험적 최적값도 아니다. 정책은 관측된 decision이 유지되었더라도 reserve를 초과한 후보를 거부할 수 있다. 따라서 `POLICY_REJECTED_WITHOUT_FLIP`은 암호학적 복호화 실패나 실제 decision flip과 구별해야 한다.

그림 3은 수학적 충분조건과 운용 reserve policy의 포함 관계를 시각화한다. 먼저 `e<m`이 decision 보존 경계를 정의하고, 그 내부의 더 엄격한 `e<0.5m`이 본 연구의 승인 영역을 정의한다.

{{V3_FIGURE_03}}

## 2.4 Ambiguous region과 certificate 집합

Margin floor `delta`를 사용해 `m(x)<=delta`인 입력을 ambiguous region `V_amb`로 분류한다. 임계값에 지나치게 가까운 sample은 아주 작은 수치 차이에도 decision이 달라질 수 있으므로, 동일한 reserve budget을 안정적으로 적용하기 어렵다. `m(x)>delta`인 집합을 certifiable region `V_cert`라 하며, FlipGuard는 이 영역에서 flip과 오차 budget 위반을 검사한다. Primary margin floor는 사전동결된 `delta=0.001`이다.

Candidate `c`의 empirical certificate는 실행 성공, `V_cert`에서 flip 부재, `e_c(x)<rho*m(x)` 위반 부재를 함께 요구한다. `V_amb`의 sample은 coverage 분모와 함께 별도로 보고하며 숨기지 않는다. Coverage는 `|V_cert|/(|V_cert|+|V_amb|)`로 해석할 수 있다. Candidate가 실행되었더라도 flip이나 policy violation이 있으면 `REJECTED`, 실행 자체가 끝나지 않았거나 materialization/runtime error가 있으면 `FAILED`다. 모든 허용 candidate가 SAFE가 아니면 선택기는 `NO_SAFE`를 반환한다.

## 2.5 Validation과 locked audit

Configuration-validation은 후보 생성 후 encrypted trial과 bounded repair에 사용되는 유한 artifact다. Locked audit은 선택된 candidate literal을 새로 조정하지 않고 재생하는 분리된 artifact다. 두 집합은 digest와 split manifest로 결합되며 overlap 검사가 수행된다. Selection이 끝나면 LogN, exact Q/P primes, scale, path, graph/model/input identity를 포함하는 literal을 잠근다. Audit은 synthesis, repair, catalog search를 호출하지 않는다.

Locked audit의 목적은 분포 전체의 안전성을 증명하는 것이 아니다. Validation에서 선택된 literal이 분리된 관측에서 동일 정책을 통과하는지, 그리고 audit 결과를 본 뒤 retuning하지 않았는지를 검증하는 절차다. Audit에서 REJECT가 발생하면 그 결과는 삭제되거나 다음 후보 선택에 사용되지 않는다. 이는 보장 실패를 숨기지 않는 claim-level fail-closed 원칙의 핵심이다.

## 2.6 Security-V2 admission

CKKS parameter의 기능적 실행 가능성과 암호학적 security admission은 별도 조건이다. Security Policy V2는 *Security Guidelines for Implementing Homomorphic Encryption*의 출판 Table 5.2에 제시된 uniform-ternary Category-128 modulus cap을 보수적 admission reference로 사용한다 [@bossuat2025security]. LogN 12, 13, 14, 15에 대해 정책이 사용하는 cap은 각각 106, 214, 430, 868 bit다. Ciphertext 객체는 Q를, relinearization·key-switching과 관련된 evaluation-key 객체는 QP를 검사하며, 필요한 모든 객체가 통과해야 candidate를 허용한다.

실제 runtime은 Lattigo v6.2.0이며 secret distribution `Xs`는 `ring.Ternary`의 `P=2/3`, error distribution `Xe`는 `ring.DiscreteGaussian`의 `Sigma=3.2`, `Bound=19.2`다. 출판 표가 전제하는 Gaussian parameter와 Lattigo의 명시적 truncation은 정확히 동일한 분포가 아니다. 그러므로 본 연구는 표 cap을 보수적 admission 기준으로 사용하고 exact Q/P를 두 estimator model에서 재검사하지만, runtime distribution의 완전한 동등성은 주장하지 않는다.

## 2.7 Bounded catalog

Bounded catalog는 사전 선언한 {{N:security_catalog_profiles_total}}개 CKKS profile과 native/rescale-aware {{N:catalog_execution_paths}}개 path로 구성된 유한 후보 집합이다. 역사적으로는 {{N:combined_descriptive_instances}}개 workload-partition instance에 대해 {{N:raw_historical_catalog_executions|,}}회가 실행되었다. Security-V2 재감사에서는 profile {{N:security_catalog_profiles_admitted}}개가 admitted, {{N:security_catalog_profiles_excluded}}개가 excluded되었다. 따라서 정식 비교 집합은 전체 {{N:formal_catalog_all}}개이며, confirmatory seeds 1--4에서는 {{N:formal_catalog_confirmatory}}개다.

이 catalog의 fastest-safe candidate는 **Security-V2-compliant bounded-catalog fastest-safe** 또는 간단히 bounded-catalog oracle로 부른다. 이는 선언된 {{N:security_catalog_profiles_admitted}} profile x {{N:catalog_execution_paths}} path의 candidate identity 안에서 가장 빠른 SAFE 후보일 뿐, 가능한 CKKS configuration 전체의 최적해가 아니다. {{N:raw_historical_catalog_executions|,}}회는 pre-security-filter historical execution ledger와 security sensitivity 분석의 원자료로만 남긴다.
