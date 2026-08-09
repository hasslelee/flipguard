# Formal Definition Audit

Status: **PARTIAL - corrections proposed, manuscripts unchanged**

## Authoritative notation

| Symbol | Meaning | Boundary/tie rule | Evidence |
|---|---|---|---|
| `f_plain(x)` | plaintext scalar score | finite real value required | `docs/research/flipguard_v3_equation_list.md` |
| `f_c(x)` | CKKS scalar score for candidate `c` | NaN/Inf is execution failure | same |
| `tau` | binary decision threshold | repository decision uses deterministic threshold comparison; `m=0` is ambiguous | same and certification implementation |
| `m(x)=abs(f_plain(x)-tau)` | binary decision margin | zero at a plaintext tie | same |
| `e_c(x)=abs(f_c(x)-f_plain(x))` | observed candidate error | empirical observation, not an analytical upper bound | same |
| `rho` | margin-utilization cap | primary `rho=0.5`; policy constant, not theorem constant | `docs/evidence/margin_utilization_interpretation_v1/` |
| `V_cert={x:m(x)>delta}` | certified-region input set | strict floor comparison | equation list |
| `V_amb={x:m(x)<=delta}` | ambiguous-region input set | includes equality | equation list |
| `z_k`, `zhat_k` | plaintext and CKKS logits | finite logits required | multiclass contract implementation |
| `c*` | deterministic plaintext argmax | smallest class index breaks a plaintext tie in implementation; theorem assumes a unique top class | multiclass contract implementation |
| `g=z_top1-z_top2` | top-two plaintext gap | `g=0` is ambiguous for the proposition | multiclass contract implementation |

## Binary decision preservation

For a finite scalar observation, the sufficient condition is

`e_c(x) < m(x)  =>  d_c(x)=d_plain(x)`.

The operational reserve policy is the strictly stronger admission rule
`e_c(x) < rho*m(x)`, with predeclared `rho=0.5`. The theorem does not derive
`rho`; `1-rho` is reserved margin. Equality does not pass either strict test.

Proof dependency: the error ball of radius `e_c(x)` cannot cross the threshold
when it is strictly smaller than the plaintext distance to that threshold.
The proof is pointwise and does not establish a distribution-wide error bound.

## Multiclass argmax preservation

Let `c*=argmax_k z_k`, and suppose finite class-wise bounds satisfy
`|Delta_k|<=B_k`. If every competitor `j!=c*` satisfies

`z_c* - z_j > B_c* + B_j`,

then `zhat_z_c* > zhat_z_j` for all competitors, so the CKKS argmax is `c*`.
Under a uniform bound `B`, the sufficient condition becomes `2B<g`.
Equality is not certified. NaN/Inf is rejected. A plaintext tie is resolved
deterministically by index for execution, but it is outside the strict theorem.

## Candidate eligibility and selection

A candidate is eligible only when execution succeeds, all required Security-V2
object checks pass, the declared finite validation observations pass the reserve
policy, and the candidate state is SAFE. Selection chooses the measured
fastest SAFE candidate within the declared candidate set. The bounded catalog
is an evaluation-only comparator, not a global oracle.

The direct path consumes the supported graph, decision contract, packing scope,
and frozen policies and emits literal candidate configurations. It stops at the
first SAFE candidate. Numerical repair adds four scale bits; level repair adds
one Q prime; the frozen maximum encrypted candidate-trial budget is four.
Bounded repair terminates at the first SAFE candidate or the trial limit. When
no SAFE candidate has been established inside that declared budget, the result
is `NO_SAFE`; this is not global CKKS infeasibility.

The selected literal, model/source/split identities, and policy digests are
locked before audit. Audit replays that byte-identical literal with no synthesis,
repair, or retuning. A locked-audit rejection is retained as a negative result.

## Inconsistencies and missing preconditions

1. The manuscripts alternate between *decision integrity* and *decision
   stability*. Define integrity as the contract/layer and stability as the
   observed preservation property.
2. Some compressed tables write `delta/rho` together. Keep margin floor
   `delta=0.001` separate from utilization cap `rho=0.5`.
3. Any argmax proposition statement must explicitly require finite logits,
   finite bounds, strict inequality, and a unique plaintext top class.
4. Observed encrypted error must not be called an analytical CKKS error bound.
5. `C_stable` should explicitly include successful execution and all required
   security-object admissions, rather than decision error alone.
6. The locked audit is empirical finite-artifact replay, not a second tuning set.

## Recommended correction text

> 본 연구의 충분조건 `e<m`은 각 관측 입력에 대한 결정 보존 조건이다.
> 실제 승인에는 사전 동결한 운용 정책 `e<rho*m` (`rho=0.5`)을 적용한다.
> `rho`는 이론에서 도출된 최적 상수가 아니며, SAFE는 선언된 유한 입력과
> 정책 범위에서의 경험적 승인만을 뜻한다.

> 다중 클래스 명제는 유한한 logit과 오차 상한, 유일한 평문 top class,
> 그리고 모든 경쟁 클래스에 대한 엄격 부등식을 전제로 한다. 동률이나
> NaN/Inf 관측은 명제의 인증 범위에 포함하지 않는다.
