# One-Page Defense Cheatsheet

## Opening

CKKS 실행 구성은 빠르더라도 근사 오차 때문에 최종 판단을 바꿀 수 있다. FlipGuard는 여러 구성 생성기가 만든 후보를 같은 판단 기준으로 검사하고, 통과한 후보 중 가장 빠른 구성을 선택한다.

## Core contribution

FlipGuard is a provider-independent decision-integrity layer with a built-in direct-synthesis provider. It applies explicit Security-V2 admission, finite encrypted validation, bounded repair, `NO_SAFE` abstention, and byte-identical no-retuning locked audit.

## Equations

- Binary: `m=|f_plain-tau|`, `e=|f_CKKS-f_plain|`, and `e<m` is sufficient.
- Policy: `e<rho*m`, with predeclared `rho=0.5`; this is not a theorem constant.
- Multiclass: `z_c*-z_j > B_c*+B_j` for every competitor; uniform form `2B<g`.

## Numbers to say precisely

- Formal trial accounting: 70/700 overall and 56/560 confirmatory, both 90% reductions.
- Primary audit: 40/40 confirmatory and 10/10 development, retuning 0.
- Primary latency: catalog/direct total-latency ratio 3.140660, cluster-bootstrap CI [2.342334, 4.215313], one host.
- P3 external: catalog/HEIR 6.393517 [6.361222, 6.427118] in the common Lattigo executor.
- P1/P2 stay blocked: 8 raw direct flips came from one unique V_amb input.
- Structural: 24 PASS + 1 reserve-policy rejection, 0 observed flips.

## Never claim

Global optimum; distribution-wide safety; complete analytical CKKS certificate; production speedup; universal 128-bit security; arbitrary packed CNN; measured HECATE; formal Orion baseline; or eight unique failed inputs.
