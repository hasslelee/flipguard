# Advisor Briefing - 2 Minutes

CKKS 실행 구성은 빠르더라도 근사 오차 때문에 최종 판단을 바꿀 수 있다. FlipGuard는 여러 구성 생성기가 만든 후보를 같은 판단 기준으로 검사하고, 통과한 후보 중 가장 빠른 구성을 선택한다.

The final evidence separates candidate generation from decision admission. The controlled primary uses 10 dataset-model clusters over five deterministic partitions, with seed 0 descriptive and seeds 1-4 confirmatory. Direct synthesis used 70 trials against 700 Security-V2-admitted bounded-catalog candidates, while 40/40 confirmatory literals passed locked audit without retuning. On one paired host, the bounded-catalog/direct total-latency ratio was 3.140660 with a cluster-bootstrap 95% CI of [2.342334, 4.215313].

External evidence is deliberately asymmetric. EVA exposes scale-dependent decision flips; HEIR supplies a stable external candidate in a common Lattigo executor; CoreLab EVA/ELASM remains NUMERICAL_ONLY; HECATE is paper-only; Orion is pilot-only. Only P3 catalog/HEIR latency is admitted. Direct-involving P1/P2 are blocked because eight repeated flips came from one unique ambiguous input.

Before manuscript editing, eight P0 items need approval: two legacy verifier robustness issues, incomplete editable BibTeX, three incorrect paper titles, journal table-language noncompliance, and one 22-profile/22-identity terminology error. No manuscript bytes have been changed.
