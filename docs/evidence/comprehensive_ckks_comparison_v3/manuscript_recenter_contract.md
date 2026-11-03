# Manuscript Recenter Contract

## Core message

FlipGuard receives a model, data artifact, decision rule, and candidates from
one or more configuration providers. It admits only candidates that meet the
declared security, runtime, and finite-input decision-stability checks, then
selects the minimum measured latency under a common timing boundary. If no
candidate passes, it returns `NO_SAFE`. The direct synthesizer is one built-in
provider, not the definition of the entire framework.

## Korean paper-facing wording

> FlipGuard는 모델·데이터·결정 규칙과 여러 구성 생성기가 제안한 CKKS
> 실행 구성을 입력받아, 최종 판단을 유지하는 후보만 선별하고 그중 실제
> 실행시간이 가장 짧은 구성을 선택한다. 적합한 후보를 확인하지 못하면
> 선택을 중단한다.

The direct-provider sentence is:

> FlipGuard는 외부 구성 생성기와 별도로, 계산 그래프와 결정 여유로부터
> 유망한 실행 구성을 직접 계산하는 내장 구성 생성기를 제공한다.

## Evidence placement

- Main text may use the 21-system capability map and 13-system source-located
  original-paper normalized comparison.
- The exact public-artifact statement is: "Ten external public artifacts
  passed a documented build or runtime smoke gate." It must not say that ten
  systems were benchmark-reproduced.
- The scoped EVA native rejection and Orion static `PLAN_UNSUPPORTED` result
  may illustrate fail-closed provider admission.
- External common-executor latency and an external fastest-stable winner remain
  blocked because no plan met E1 or defensible E2 portability.
- FlipGuard's 50-workload paired result remains an internal common-executor
  comparison among manual/reference, Security-V2 bounded catalog, and direct
  arms. It is not evidence of superiority over external compilers.

## Prohibited synthesis

Do not combine native milliseconds from different runtimes, call reported
paper speedups locally measured, infer exact graph identity from a shared model
name, or imply global optimality. An external provider that later supplies a
faster admitted exact candidate must be selectable over FlipGuard direct; that
outcome would support provider independence rather than falsify FlipGuard.
