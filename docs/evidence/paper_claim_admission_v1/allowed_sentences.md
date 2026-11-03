# Allowed Paper Sentences

Only the exact scoped sentences below are admitted. Numerical tables may
substitute verified values without broadening the sentence.

## scoped_direct_synthesis

- KO: FlipGuard는 선언된 graph adapter와 동결 정책 범위에서 computation graph와 threshold decision-integrity contract로부터 CKKS literal을 직접 합성했다.
- EN: Within the declared graph adapters and frozen policies, FlipGuard directly synthesized CKKS literals from computation graphs and threshold decision-integrity contracts.

## adaptive_repair

- KO: FlipGuard의 동결된 bounded repair는 선언된 개발 ablation에서 one-shot 실패 네 건을 SAFE 선택으로 전환했으며, 이는 보편적 repair 성공을 뜻하지 않는다.
- EN: In the declared development ablation, FlipGuard's frozen bounded repair converted four one-shot failures into SAFE selections; this does not imply universal repair success.

## formal_trial_reduction

- KO: FlipGuard는 Security-V2 bounded catalog의 700개 후보 대비 전체 70회, confirmatory 560개 후보 대비 56회의 encrypted candidate trial을 사용해 두 경우 모두 90% 감소를 기록했다.
- EN: FlipGuard used 70 encrypted candidate trials versus 700 Security-V2 bounded-catalog candidates overall and 56 versus 560 in the confirmatory partitions, a 90% reduction in both cases.

## primary_no_retuning_locked_audit

- KO: 동결 literal의 no-retuning locked audit은 confirmatory seeds 1-4에서 40/40, development seed 0에서 10/10 통과했다.
- EN: Byte-identical frozen literals passed no-retuning locked audit in 40/40 confirmatory seed-1-4 instances and 10/10 development seed-0 instances.

## no_safe_behavior

- KO: 사전동결 budget control은 40건 중 16건에서 NO_SAFE를, 선언된 finite-domain control은 50/50에서 NO_SAFE를 반환했다.
- EN: The predeclared budget control returned NO_SAFE in 16/40 instances, and the declared finite-domain control returned NO_SAFE in 50/50 instances.

## paired_latency

- KO: 선언된 post-freeze workload partition에서 direct configuration은 Security-V2 bounded-catalog fastest-safe configuration보다 paired total inference latency를 줄였으며, 정확한 clustered geometric-mean ratio와 confidence interval을 함께 보고한다.
- EN: Across the declared post-freeze workload partitions, FlipGuard's directly synthesized configurations reduced paired total inference latency relative to the Security-V2-compliant bounded-catalog fastest-safe configurations; the exact clustered geometric-mean ratio and confidence interval are reported.

## structural_extension

- KO: mlp_square_poly3는 25/25 선택됐고 no-retuning audit에서 24건 PASS와 decision flip 없는 reserve-policy REJECT 1건을 기록했다.
- EN: For mlp_square_poly3, 25/25 instances were selected and no-retuning audit produced 24 PASS results and one reserve-policy REJECT without a decision flip.

## scoped_non_tabular_extension

- KO: Sobel, Harris, CNN-lite adapter는 각 선언된 finite input과 scalar-replicated execution 범위에서 selection과 no-retuning audit evidence를 제공한다.
- EN: The Sobel, Harris, and CNN-lite adapters provide selection and no-retuning audit evidence only for their declared finite inputs and scalar-replicated execution scopes.

## training_model_seed_extension

- KO: 세 dataset과 세 independent training/data seed로 생성한 9개 model instance가 9/9 selection과 no-retuning audit PASS를 기록했다.
- EN: Nine model instances from three datasets and three independent training/data seeds achieved 9/9 selection and no-retuning audit PASS.

## security_attestation

- KO: 선택 후보의 exact Q/P를 Security Policy V2와 두 estimator model에서 재감사했으며, 실제 Lattigo Xe truncation과 estimator 분포의 exact equivalence는 주장하지 않는다.
- EN: Selected exact Q/P literals were re-attested under Security Policy V2 and two estimator models; exact equivalence to Lattigo's truncated Xe distribution is not claimed.

## finite_scope_decision_integrity

- KO: FlipGuard는 선언된 finite validation에서 관측 error와 decision margin을 결합해 후보를 certify-or-reject하고, disjoint audit에서 동결 literal을 재생한다.
- EN: FlipGuard combines observed error and decision margin to certify or reject candidates on declared finite validation artifacts and replays the frozen literal on disjoint audits.

