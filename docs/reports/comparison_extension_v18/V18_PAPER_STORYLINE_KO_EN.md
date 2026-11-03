# V18 Paper Storyline (KO/EN)

## Korean

V18의 중심 비교는 외부 시스템 수를 늘리는 것이 아니라 결정 안정성
검사의 인과적 역할을 분리하는 것이다. 동일한 직접 합성 순서에서 이
검사를 제거하면 68개 첫 후보가 모두 실행 가능했지만, 20개 사례에서는
판단 반전이, 21개 사례에서는 운용 오차 예산 위반이 관찰되었다.
FlipGuard는 21회의 추가 암호화 후보 평가로 21개 구성을 변경했고, 최종
68개 구성은 모두 분리 입력 평가를 통과했다.

이 비용은 제한적이었다. 변경된 구성은 모두 scale이 4 bit 증가했지만
Q prime 수, Q-chain 길이, LogN은 증가하지 않았다. 관측된 후보 latency
ratio는 selection-stage 진단이며 formal paired latency가 아니다. 유한
참조는 운영 baseline이 아니라 false NO_SAFE와 선택 품질을 확인하는
오프라인 기준이다. Direct는 89회, 유한 참조는 537회를 사용했고, 최종
latency는 참조의 가장 빠른 적합 구성과 통계적으로 구별되는 우월성을
보이지 않았다.

외부 비교는 적격성에 따라 분리한다. HEIR는 하나의 exact workload,
EVA는 output-comparable workload, HECATE/ELASM은 numerical-only evidence,
나머지 7개는 관련 연구로만 사용한다. 이 구조는 비교 폭보다 공정한
동일성 조건을 우선한다.

## English

V18 does not maximize the number of named external systems. It isolates the
causal role of the decision-stability gate under the same direct-synthesis
sequence. Removing the gate made all 68 initial candidates execution-valid,
but 20 cases exhibited decision flips and 21 violated the operational error
budget. FlipGuard spent 21 additional encrypted candidate evaluations, changed
21 configurations, and all 68 final configurations passed separate-input
evaluation.

The adaptation was bounded: every changed configuration added four scale bits,
while Q-prime count, Q-chain length, and LogN remained unchanged. Candidate
latency ratios are selection-stage observations, not formal paired gate-off
latency. The finite reference is an offline test of missed feasibility and
selection quality, not an operating baseline. Direct selection used 89
evaluations versus 537, while final latency showed near-reference quality but no
statistically admitted superiority.

External results are stratified by eligibility: one exact HEIR workload, one
output-comparable EVA workload, two numerical-only HECATE/ELASM entries, and
seven related-work-only systems or guides. Fair identity takes precedence over
baseline count.
