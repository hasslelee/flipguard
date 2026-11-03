# Five-Minute Artifact Demonstration

## 0:00-0:40 - Problem

CKKS 실행 구성은 빠르더라도 근사 오차 때문에 최종 판단을 바꿀 수 있다. FlipGuard는 여러 구성 생성기가 만든 후보를 같은 판단 기준으로 검사하고, 통과한 후보 중 가장 빠른 구성을 선택한다.

## 0:40-1:40 - Contracts

Show `docs/DECISION_CONTRACTS.md`. Explain `e<m`, then separate the operational `e<0.5m` reserve policy. Show the multiclass pairwise gap condition and state that ties/NaN/Inf are not certified.

## 1:40-2:40 - Read-only quick demo

Run `scripts/reproduce_quick_demo.sh`. It reads frozen summaries only and prints one SAFE result, one REJECTED result, and declared NO_SAFE controls. State explicitly: “This is artifact replay, not a new encrypted evaluation.”

## 2:40-3:40 - Main numbers

Open `authoritative_number_registry.json`: 70/700, 40/40, and the scoped 3.140660 ratio. Then show P3 6.393517 and point out why P1/P2 are blocked.

## 3:40-4:30 - Negative evidence

Show the structural 24+1 result and direct repeated-flip forensics: one V_amb input, eight repeated flips. Emphasize that results are not deleted or retuned.

## 4:30-5:00 - Reproducibility

Run the final audit verifier and show dependency digests. Close by naming the finite-input, one-host, adapter, and security-model limits.
