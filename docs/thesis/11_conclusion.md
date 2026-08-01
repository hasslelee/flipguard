# 제11장 결론

본 연구는 CKKS configuration 선택을 단순한 실행 가능성이나 latency 최적화만으로 보지 않고, 최종 threshold decision을 보존하기 위한 finite-scope admission 문제로 정식화했다. FlipGuard는 지원 computation graph와 decision-integrity contract에서 exact CKKS literal을 직접 합성하고, 제한된 encrypted trial과 bounded failure-aware repair를 수행하며, SAFE 후보가 없을 때 NO_SAFE로 기권한다. 선택된 literal은 disjoint locked audit에서 retuning 없이 재생된다.

<!-- P:CONCLUSION-DIRECT CLAIM:scoped_direct_synthesis,formal_trial_reduction -->
선언된 adapter와 동결 policy에서 direct synthesis는 전체 {{N:direct_trials_all}}/{{N:formal_catalog_all}}, confirmatory {{N:direct_trials_confirmatory}}/{{N:formal_catalog_confirmatory}} candidate trial을 사용해 Security-V2 bounded catalog 대비 {{N:formal_trial_reduction_all|.0%}}의 formal trial 감소를 기록했다. 이 수치는 candidate trial 단위와 유한 admitted catalog 범위에 한정된다. Historical {{N:raw_historical_catalog_executions|,}} execution이나 가능한 CKKS parameter 공간 전체를 분모로 사용하지 않는다.

<!-- P:CONCLUSION-AUDIT CLAIM:primary_no_retuning_locked_audit,no_safe_behavior -->
Primary no-retuning locked audit은 confirmatory seeds 1--4에서 {{N:confirmatory_locked_audit_pass}}/{{N:confirmatory_instances}}, development seed 0에서 {{N:development_locked_audit_pass}}/{{N:development_instances}} 통과했고 retuning은 {{N:primary_locked_audit_retuning}}이었다. 사전동결 budget control은 {{N:no_safe_budget}}/{{N:no_safe_budget_total}}, finite-domain control은 {{N:no_safe_finite_domain}}/{{N:no_safe_finite_domain_total}}에서 NO_SAFE를 반환했다. 이 결과는 선언된 finite artifact와 candidate budget에서 admission과 abstention behavior를 지지하며 분포 전체의 안전성 또는 전 구성의 infeasibility를 의미하지 않는다.

<!-- P:CONCLUSION-LATENCY CLAIM:paired_latency -->
한 host의 confirmatory paired protocol에서 Security-V2 bounded-catalog total latency를 direct total latency로 나눈 dataset-model-cluster geometric mean은 {{N:paired_total_ratio_confirmatory|.6f}}이었고 cluster-bootstrap 95% confidence interval은 [{{N:paired_total_ci_low|.6f}}, {{N:paired_total_ci_high|.6f}}]이었다. 이 결과는 frozen direct/catalog arm과 선언 workload에 대한 paired comparison이다. Production system이나 다른 hardware에서 같은 비율을 보증하지 않는다.

<!-- P:CONCLUSION-SCOPE CLAIM:structural_extension,scoped_non_tabular_extension,training_model_seed_extension -->
Deeper polynomial `mlp_square_poly3`는 {{N:structural_selected}}/{{N:structural_instances}} selection 후 locked audit {{N:structural_audit_pass}} PASS와 decision flip 없는 reserve-policy REJECT {{N:structural_reserve_reject}}건을 기록했다. Sobel, Harris, CNN-lite는 각 finite scalar-replicated input 범위에서 selection과 no-retuning audit evidence를 제공했고, {{N:independent_training_datasets}} dataset x {{N:independent_training_seeds_per_dataset}} independent training/data seed의 {{N:independent_training_seed_total}} model은 {{N:independent_training_seed_pass}}/{{N:independent_training_seed_total}} selection 및 audit PASS였다. 이 extension은 범위를 넓혔지만 arbitrary packed graph와 보편적인 model-seed generalization을 확립하지 않는다.

본 연구의 중요한 결론은 negative result를 제거하지 않는 protocol 자체에 있다. Structural audit rejection은 validation SAFE가 unseen audit의 reserve를 항상 보존하지 않음을 보여주었고, latency-only ablation의 flip은 실행 속도가 decision integrity를 대신하지 못함을 보여주었다. Validation identity v1 mismatch와 Security-V2 catalog exclusion은 representation 및 security layer를 구분해야 함을 드러냈다.

향후 연구는 typed graph IR를 통한 adapter 자동화, packed CNN과 bootstrapping graph, 여러 host/runtime의 paired study, 외부 autotuner candidate의 systematic admission, 그리고 exact CKKS residual bound를 decision margin과 결합한 분석적 certificate를 다루어야 한다. 이러한 확장은 현재의 frozen evidence가 지지하는 범위를 바꾸지 않고 별도 policy와 protocol로 수행해야 한다.

결론적으로 FlipGuard는 지원된 계산 범위에서 direct synthesis, bounded validation/repair, NO_SAFE, no-retuning audit, Security-V2 comparison과 evidence provenance를 결합한 decision-integrity layer를 구현했다. 그 성과는 모든 CKKS workload를 자동으로 해결했다는 데 있지 않다. 어떤 후보를 왜 승인했는지, 언제 기권했는지, audit에서 무엇이 반증되었는지를 재현 가능한 형태로 남겼다는 데 있다.
