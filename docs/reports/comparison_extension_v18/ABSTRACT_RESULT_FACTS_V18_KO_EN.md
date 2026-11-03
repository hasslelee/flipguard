# V18 Abstract Result Facts

## Korean

선언된 68개 주 평가 사례에서 결정 안정성 검사를 제거하면 첫 후보가
모두 선택되었지만, 20개 사례에서 구성-선택 입력의 판단 반전이, 21개
사례에서 운용 오차 예산 위반이 관찰되었다. FlipGuard는 21회의 추가
암호화 후보 평가로 이 21개 구성을 변경했으며, 최종 68개 구성은 모두
분리된 입력 평가를 통과했다. 직접 경로는 오프라인 유한 참조의 537회
대신 89회의 후보 평가를 사용했고 false NO_SAFE는 없었다. 가장 빠른
적합 유한 참조 대비 latency regret의 중앙값은 -0.000153이었으며,
dataset-model cluster 기준 finite/direct total-latency ratio는 1.000541
(95% CI [0.999967, 1.001122])이었다. 이 결과는 선언된 유한 후보군과
측정 환경에 한정되며 전역 최적성이나 모든 외부 tuner에 대한 우월성을
뜻하지 않는다.

## English

Across 68 declared primary cases, removing the decision-stability gate selected
every initial candidate, although 20 cases exhibited selection-input decision
flips and 21 violated the operational error budget. FlipGuard changed those 21
configurations using 21 additional encrypted candidate evaluations, and all 68
final configurations passed separate-input evaluation. The direct path used 89
candidate evaluations instead of 537 for the offline finite reference, with no
false NO_SAFE. Median latency regret to the fastest acceptable finite-reference
configuration was -0.000153; the dataset-model-cluster finite/direct total-
latency ratio was 1.000541 (95% CI [0.999967, 1.001122]). These results are
limited to the declared finite candidates and measurement environment and do
not establish global optimality or superiority over all external tuners.
