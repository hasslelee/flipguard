# Thesis Defense Q&A

Questions: 62. Every answer states its evidence and its forbidden extrapolation.

## Q1. Security-V2 admission을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** The paper may claim Security-V2 policy admission, not universal exact 128-bit security.
- **직관적 설명:** The policy checks the exact Q/P material against a published conservative cap, while the runtime error distribution is not claimed identical to the table model.
- **기술적 설명:** Ciphertext Q and evaluation-key QP are checked separately; the exact-estimator overlay reports model sensitivity and the Lattigo Xe truncation caveat.
- **정확한 수치/증거:** 7 of 11 catalog profiles admitted; 4 excluded; target category 128. Evidence: `docs/evidence/security_v2_static_attestation_formal_v2/`
- **반드시 피할 주장:** universally 128-bit secure

## Q2. Security-V2 admission에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** The paper may claim Security-V2 policy admission, not universal exact 128-bit security.
- **직관적 설명:** The policy checks the exact Q/P material against a published conservative cap, while the runtime error distribution is not claimed identical to the table model.
- **기술적 설명:** Ciphertext Q and evaluation-key QP are checked separately; the exact-estimator overlay reports model sensitivity and the Lattigo Xe truncation caveat.
- **정확한 수치/증거:** 7 of 11 catalog profiles admitted; 4 excluded; target category 128. Evidence: `docs/evidence/security_v2_static_attestation_formal_v2/`
- **반드시 피할 주장:** universally 128-bit secure

## Q3. Q versus QP을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** Final admission requires every required object to pass its applicable Q or QP check.
- **직관적 설명:** A safe ciphertext modulus alone does not cover the larger modulus material used by relinearization or key switching.
- **기술적 설명:** The policy records logQ, logP, logQP, per-object admission, headroom, and a final conjunction.
- **정확한 수치/증거:** 11 profiles audited; 7 admitted and 4 excluded. Evidence: `docs/evidence/security_v2_static_attestation_formal_v2/`
- **반드시 피할 주장:** Q-only candidate security

## Q4. Q versus QP에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** Final admission requires every required object to pass its applicable Q or QP check.
- **직관적 설명:** A safe ciphertext modulus alone does not cover the larger modulus material used by relinearization or key switching.
- **기술적 설명:** The policy records logQ, logP, logQP, per-object admission, headroom, and a final conjunction.
- **정확한 수치/증거:** 11 profiles audited; 7 admitted and 4 excluded. Evidence: `docs/evidence/security_v2_static_attestation_formal_v2/`
- **반드시 피할 주장:** Q-only candidate security

## Q5. Binary sufficient condition을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** `e<m` is a pointwise sufficient decision condition; the evidence supplies observed encrypted errors on finite artifacts.
- **직관적 설명:** If the approximation error is smaller than the distance to the threshold, the score cannot cross the threshold.
- **기술적 설명:** The implication assumes finite values and strict inequality; it does not bound error on unseen inputs.
- **정확한 수치/증거:** rho=0.5 is applied after the theorem as an operational cap. Evidence: `docs/research/flipguard_v3_equation_list.md`
- **반드시 피할 주장:** complete analytical certificate

## Q6. Binary sufficient condition에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** `e<m` is a pointwise sufficient decision condition; the evidence supplies observed encrypted errors on finite artifacts.
- **직관적 설명:** If the approximation error is smaller than the distance to the threshold, the score cannot cross the threshold.
- **기술적 설명:** The implication assumes finite values and strict inequality; it does not bound error on unseen inputs.
- **정확한 수치/증거:** rho=0.5 is applied after the theorem as an operational cap. Evidence: `docs/research/flipguard_v3_equation_list.md`
- **반드시 피할 주장:** complete analytical certificate

## Q7. Multiclass proposition을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** Argmax preservation follows only when every plaintext pairwise gap strictly exceeds the sum of the two class-wise error bounds.
- **직관적 설명:** Even if the top score moves down and a competitor moves up, their error intervals must not touch.
- **기술적 설명:** For uniform B, `2B<g`; equality, NaN/Inf, and plaintext ties are not certified.
- **정확한 수치/증거:** 10 logits in the MLP-100 and LeNet-5-small adapters. Evidence: `internal/certify/multiclass_decision_contract.go`
- **반드시 피할 주장:** non-strict or distribution-wide argmax guarantee

## Q8. Multiclass proposition에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** Argmax preservation follows only when every plaintext pairwise gap strictly exceeds the sum of the two class-wise error bounds.
- **직관적 설명:** Even if the top score moves down and a competitor moves up, their error intervals must not touch.
- **기술적 설명:** For uniform B, `2B<g`; equality, NaN/Inf, and plaintext ties are not certified.
- **정확한 수치/증거:** 10 logits in the MLP-100 and LeNet-5-small adapters. Evidence: `internal/certify/multiclass_decision_contract.go`
- **반드시 피할 주장:** non-strict or distribution-wide argmax guarantee

## Q9. Operational reserve policy을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** rho=0.5 is a predeclared conservative utilization policy, not an optimal or theorem-derived constant.
- **직관적 설명:** Half the observed margin is used as the acceptance budget and half is reserved against finite-sample uncertainty.
- **기술적 설명:** The alpha sensitivity grid did not change primary candidate states or initial literals because the minimum synthesis floor dominated.
- **정확한 수치/증거:** rho=0.5; tested grid 0.1, 0.25, 0.5, 0.75, 0.9. Evidence: `docs/evidence/margin_utilization_interpretation_v1/`
- **반드시 피할 주장:** theoretically optimal 0.5

## Q10. Operational reserve policy에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** rho=0.5 is a predeclared conservative utilization policy, not an optimal or theorem-derived constant.
- **직관적 설명:** Half the observed margin is used as the acceptance budget and half is reserved against finite-sample uncertainty.
- **기술적 설명:** The alpha sensitivity grid did not change primary candidate states or initial literals because the minimum synthesis floor dominated.
- **정확한 수치/증거:** rho=0.5; tested grid 0.1, 0.25, 0.5, 0.75, 0.9. Evidence: `docs/evidence/margin_utilization_interpretation_v1/`
- **반드시 피할 주장:** theoretically optimal 0.5

## Q11. No-retuning audit을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** The audit replays the selected literal byte-identically; synthesis, repair, and retuning are prohibited.
- **직관적 설명:** Configuration selection ends before the audit data are opened.
- **기술적 설명:** Candidate, model, source, split, policy, and binary digests are recorded, with retuning count required to be zero.
- **정확한 수치/증거:** 40/40 confirmatory and 10/10 development primary audits passed; retuning 0. Evidence: `docs/evidence/direct_locked_audit_final_source_v1/`
- **반드시 피할 주장:** audit-guided selection

## Q12. No-retuning audit에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** The audit replays the selected literal byte-identically; synthesis, repair, and retuning are prohibited.
- **직관적 설명:** Configuration selection ends before the audit data are opened.
- **기술적 설명:** Candidate, model, source, split, policy, and binary digests are recorded, with retuning count required to be zero.
- **정확한 수치/증거:** 40/40 confirmatory and 10/10 development primary audits passed; retuning 0. Evidence: `docs/evidence/direct_locked_audit_final_source_v1/`
- **반드시 피할 주장:** audit-guided selection

## Q13. Meaning of SAFE을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** SAFE means that one candidate passed execution, security admission, and the finite declared decision-reserve checks.
- **직관적 설명:** It is a checked claim about named inputs and keys, not every future input.
- **기술적 설명:** The state binds the input/model/split/policy digests and observed fresh-key repetitions.
- **정확한 수치/증거:** 50 workload-partition instances in the controlled primary. Evidence: `docs/evidence/paper_claim_admission_v1/claims.json`
- **반드시 피할 주장:** distribution-wide safety

## Q14. Meaning of SAFE에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** SAFE means that one candidate passed execution, security admission, and the finite declared decision-reserve checks.
- **직관적 설명:** It is a checked claim about named inputs and keys, not every future input.
- **기술적 설명:** The state binds the input/model/split/policy digests and observed fresh-key repetitions.
- **정확한 수치/증거:** 50 workload-partition instances in the controlled primary. Evidence: `docs/evidence/paper_claim_admission_v1/claims.json`
- **반드시 피할 주장:** distribution-wide safety

## Q15. Provider-independent positioning을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** FlipGuard is a decision-integrity layer with a built-in direct-synthesis provider.
- **직관적 설명:** Candidate generators propose configurations; the same gate decides whether any proposal is acceptable.
- **기술적 설명:** Manual, catalog, external-provider, and direct literals share security, encrypted-validation, state, and audit semantics.
- **정확한 수치/증거:** External measured providers include EVA and HEIR; HECATE remains paper-only. Evidence: `docs/evidence/final_realistic_baseline_closure_v9/final_baseline_matrix.csv`
- **반드시 피할 주장:** first or universal CKKS autotuner

## Q16. Provider-independent positioning에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** FlipGuard is a decision-integrity layer with a built-in direct-synthesis provider.
- **직관적 설명:** Candidate generators propose configurations; the same gate decides whether any proposal is acceptable.
- **기술적 설명:** Manual, catalog, external-provider, and direct literals share security, encrypted-validation, state, and audit semantics.
- **정확한 수치/증거:** External measured providers include EVA and HEIR; HECATE remains paper-only. Evidence: `docs/evidence/final_realistic_baseline_closure_v9/final_baseline_matrix.csv`
- **반드시 피할 주장:** first or universal CKKS autotuner

## Q17. Heuristic nature을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** It is a frozen graph-fact-to-literal policy with bounded empirical repairs, and its supported adapter scope is explicit.
- **직관적 설명:** The graph supplies depth and scale requirements; the policy maps them to an admissible literal and tests it.
- **기술적 설명:** There is no model-specific lookup table in the policy; structural and multiclass adapters are evaluated without retuning policy constants.
- **정확한 수치/증거:** 70 trials for 50 primary instances; observed maximum 2 under a policy maximum of 4. Evidence: `docs/evidence/direct_synthesis_policy_v2.json`
- **반드시 피할 주장:** universal synthesis optimality

## Q18. Heuristic nature에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** It is a frozen graph-fact-to-literal policy with bounded empirical repairs, and its supported adapter scope is explicit.
- **직관적 설명:** The graph supplies depth and scale requirements; the policy maps them to an admissible literal and tests it.
- **기술적 설명:** There is no model-specific lookup table in the policy; structural and multiclass adapters are evaluated without retuning policy constants.
- **정확한 수치/증거:** 70 trials for 50 primary instances; observed maximum 2 under a policy maximum of 4. Evidence: `docs/evidence/direct_synthesis_policy_v2.json`
- **반드시 피할 주장:** universal synthesis optimality

## Q19. Repair causality을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** Only classified numerical and level failures trigger fixed, bounded changes.
- **직관적 설명:** The system applies a small predeclared correction and stops once a candidate passes or the budget ends.
- **기술적 설명:** Numerical repair adds four scale bits; level repair adds one Q prime; no audit-triggered repair is allowed.
- **정확한 수치/증거:** 20 primary repair events; policy trial limit 4. Evidence: `docs/evidence/direct_synthesis_policy_v2.json`
- **반드시 피할 주장:** unlimited adaptive search

## Q20. Repair causality에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** Only classified numerical and level failures trigger fixed, bounded changes.
- **직관적 설명:** The system applies a small predeclared correction and stops once a candidate passes or the budget ends.
- **기술적 설명:** Numerical repair adds four scale bits; level repair adds one Q prime; no audit-triggered repair is allowed.
- **정확한 수치/증거:** 20 primary repair events; policy trial limit 4. Evidence: `docs/evidence/direct_synthesis_policy_v2.json`
- **반드시 피할 주장:** unlimited adaptive search

## Q21. Formal denominator을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** The formal denominator is 700 Security-V2-admitted candidates, not the historical 1,100 executions.
- **직관적 설명:** Four of eleven profiles are retained as history but removed before formal selection accounting.
- **기술적 설명:** 7 admitted profiles x 2 paths x 50 instances = 700; confirmatory is 7 x 2 x 40 = 560.
- **정확한 수치/증거:** 70/700 and 56/560, both 90% reductions. Evidence: `docs/thesis/number_registry.json`
- **반드시 피할 주장:** 90% versus 1,100 or global search

## Q22. Formal denominator에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** The formal denominator is 700 Security-V2-admitted candidates, not the historical 1,100 executions.
- **직관적 설명:** Four of eleven profiles are retained as history but removed before formal selection accounting.
- **기술적 설명:** 7 admitted profiles x 2 paths x 50 instances = 700; confirmatory is 7 x 2 x 40 = 560.
- **정확한 수치/증거:** 70/700 and 56/560, both 90% reductions. Evidence: `docs/thesis/number_registry.json`
- **반드시 피할 주장:** 90% versus 1,100 or global search

## Q23. Oracle terminology을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** It is the fastest SAFE candidate only within the frozen Security-V2 bounded catalog.
- **직관적 설명:** The comparator exhausts a declared small shelf, not all possible CKKS parameters.
- **기술적 설명:** Inadmissible profiles and unsupported plans are excluded under declared rules.
- **정확한 수치/증거:** 11 raw profiles, 7 admitted, two paths. Evidence: `docs/evidence/security_v2_bounded_oracle_v1/`
- **반드시 피할 주장:** global oracle or global optimum

## Q24. Oracle terminology에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** It is the fastest SAFE candidate only within the frozen Security-V2 bounded catalog.
- **직관적 설명:** The comparator exhausts a declared small shelf, not all possible CKKS parameters.
- **기술적 설명:** Inadmissible profiles and unsupported plans are excluded under declared rules.
- **정확한 수치/증거:** 11 raw profiles, 7 admitted, two paths. Evidence: `docs/evidence/security_v2_bounded_oracle_v1/`
- **반드시 피할 주장:** global oracle or global optimum

## Q25. HEIR role을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** HEIR is reported as an external compiler/configuration provider.
- **직관적 설명:** It emits a configuration for the shared polynomial; FlipGuard then applies the common gate.
- **기술적 설명:** Only exact shared-graph common-Lattigo comparisons support the P3 latency claim.
- **정확한 수치/증거:** HEIR validation/audit flips 0/0 across 500/500 inputs and three contexts. Evidence: `docs/evidence/final_realistic_baseline_closure_v9/tables/table_04_heir_common_executor_candidates.csv`
- **반드시 피할 주장:** HEIR autotuner unless exact context supports it

## Q26. HEIR role에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** HEIR is reported as an external compiler/configuration provider.
- **직관적 설명:** It emits a configuration for the shared polynomial; FlipGuard then applies the common gate.
- **기술적 설명:** Only exact shared-graph common-Lattigo comparisons support the P3 latency claim.
- **정확한 수치/증거:** HEIR validation/audit flips 0/0 across 500/500 inputs and three contexts. Evidence: `docs/evidence/final_realistic_baseline_closure_v9/tables/table_04_heir_common_executor_candidates.csv`
- **반드시 피할 주장:** HEIR autotuner unless exact context supports it

## Q27. P1/P2 instability을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** P1 HEIR/direct and P2 catalog/direct are blocked because the repeated direct arm flipped on one V_amb input.
- **직관적 설명:** A fast arm is not an admissible stable baseline when repeated execution changes the decision.
- **기술적 설명:** Eight raw flips came from one unique near-boundary input; the arm remains diagnostic but not a stable-speed denominator.
- **정확한 수치/증거:** 8 raw repeats, 1 unique V_amb input. Evidence: `docs/evidence/final_realistic_baseline_closure_v9/direct_repeat_flip_forensics/`
- **반드시 피할 주장:** eight failed inputs or admitted direct speedup

## Q28. P1/P2 instability에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** P1 HEIR/direct and P2 catalog/direct are blocked because the repeated direct arm flipped on one V_amb input.
- **직관적 설명:** A fast arm is not an admissible stable baseline when repeated execution changes the decision.
- **기술적 설명:** Eight raw flips came from one unique near-boundary input; the arm remains diagnostic but not a stable-speed denominator.
- **정확한 수치/증거:** 8 raw repeats, 1 unique V_amb input. Evidence: `docs/evidence/final_realistic_baseline_closure_v9/direct_repeat_flip_forensics/`
- **반드시 피할 주장:** eight failed inputs or admitted direct speedup

## Q29. CoreLab scope을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** CoreLab EVA/ELASM is NUMERICAL_ONLY error-latency plan evidence.
- **직관적 설명:** Those rows measure numerical behavior but do not carry the threshold decision contract used by the main evaluation.
- **기술적 설명:** Seventy plans executed successfully and two failed; 14,000 rows are plan-input observations, not independent decision samples.
- **정확한 수치/증거:** 36 EVA + 36 ELASM plans; 70 PASS, 2 failures. Evidence: `docs/evidence/final_realistic_baseline_closure_v9/tables/table_06_corelab_eva_hecate_elasm_grid.csv`
- **반드시 피할 주장:** decision-bearing CoreLab baseline

## Q30. CoreLab scope에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** CoreLab EVA/ELASM is NUMERICAL_ONLY error-latency plan evidence.
- **직관적 설명:** Those rows measure numerical behavior but do not carry the threshold decision contract used by the main evaluation.
- **기술적 설명:** Seventy plans executed successfully and two failed; 14,000 rows are plan-input observations, not independent decision samples.
- **정확한 수치/증거:** 36 EVA + 36 ELASM plans; 70 PASS, 2 failures. Evidence: `docs/evidence/final_realistic_baseline_closure_v9/tables/table_06_corelab_eva_hecate_elasm_grid.csv`
- **반드시 피할 주장:** decision-bearing CoreLab baseline

## Q31. HECATE and Orion depth을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** HECATE is a paper baseline only; Orion is a 10-input official self-test pilot.
- **직관적 설명:** Neither is counted as a formal measured decision baseline.
- **기술적 설명:** Their states are NOT_EVALUATED and PILOT_ONLY in V9 claim admission.
- **정확한 수치/증거:** HECATE plans attempted 0; Orion preflight inputs 10. Evidence: `docs/evidence/final_realistic_baseline_closure_v9/manifest.json`
- **반드시 피할 주장:** measured HECATE or formal Orion validation

## Q32. HECATE and Orion depth에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** HECATE is a paper baseline only; Orion is a 10-input official self-test pilot.
- **직관적 설명:** Neither is counted as a formal measured decision baseline.
- **기술적 설명:** Their states are NOT_EVALUATED and PILOT_ONLY in V9 claim admission.
- **정확한 수치/증거:** HECATE plans attempted 0; Orion preflight inputs 10. Evidence: `docs/evidence/final_realistic_baseline_closure_v9/manifest.json`
- **반드시 피할 주장:** measured HECATE or formal Orion validation

## Q33. Primary latency inference을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** The primary inference unit is the 10 dataset-model clusters; partitions are within-cluster repetitions.
- **직관적 설명:** Repeated measurements of the same workload do not create new workloads.
- **기술적 설명:** The ratio uses a dataset-model-cluster geometric mean and a cluster bootstrap, with no raw record-level p-value.
- **정확한 수치/증거:** ratio 3.140660; 95% CI [2.342334, 4.215313]. Evidence: `results/thesis_grade_protocol/paired_latency_claim_admission_v1/seeds1_4_confirmatory_summary.json`
- **반드시 피할 주장:** 50 or 5,400 independent samples

## Q34. Primary latency inference에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** The primary inference unit is the 10 dataset-model clusters; partitions are within-cluster repetitions.
- **직관적 설명:** Repeated measurements of the same workload do not create new workloads.
- **기술적 설명:** The ratio uses a dataset-model-cluster geometric mean and a cluster bootstrap, with no raw record-level p-value.
- **정확한 수치/증거:** ratio 3.140660; 95% CI [2.342334, 4.215313]. Evidence: `results/thesis_grade_protocol/paired_latency_claim_admission_v1/seeds1_4_confirmatory_summary.json`
- **반드시 피할 주장:** 50 or 5,400 independent samples

## Q35. P3 latency inference을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** P3 reports input-cluster inference; keysets and passes are repeated measurements.
- **직관적 설명:** The same 100 inputs are timed repeatedly, so there are 100 input clusters, not 1,800 independent inputs.
- **기술적 설명:** Three keysets and six passes produce 1,800 raw pairs; the bootstrap clusters by input.
- **정확한 수치/증거:** 6.393517, 95% CI [6.361222, 6.427118]. Evidence: `docs/evidence/final_realistic_baseline_closure_v9/tables/table_05_pairwise_latency_claims.csv`
- **반드시 피할 주장:** raw-pair independence

## Q36. P3 latency inference에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** P3 reports input-cluster inference; keysets and passes are repeated measurements.
- **직관적 설명:** The same 100 inputs are timed repeatedly, so there are 100 input clusters, not 1,800 independent inputs.
- **기술적 설명:** Three keysets and six passes produce 1,800 raw pairs; the bootstrap clusters by input.
- **정확한 수치/증거:** 6.393517, 95% CI [6.361222, 6.427118]. Evidence: `docs/evidence/final_realistic_baseline_closure_v9/tables/table_05_pairwise_latency_claims.csv`
- **반드시 피할 주장:** raw-pair independence

## Q37. Structural negative result을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** The one rejection is preserved and demonstrates that validation SAFE does not guarantee unseen reserve-policy acceptance.
- **직관적 설명:** The decision did not flip, but the encrypted error used more than the reserved half-margin on one audit observation.
- **기술적 설명:** It is OBSERVED_DECISION_PRESERVED and RESERVE_POLICY_REJECTED, with retuning zero.
- **정확한 수치/증거:** 24 PASS, 1 reserve-policy rejection, 0 flips. Evidence: `docs/evidence/structural_audit_failure_analysis_v1/`
- **반드시 피할 주장:** all structural audits passed or cryptographic correctness failure

## Q38. Structural negative result에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** The one rejection is preserved and demonstrates that validation SAFE does not guarantee unseen reserve-policy acceptance.
- **직관적 설명:** The decision did not flip, but the encrypted error used more than the reserved half-margin on one audit observation.
- **기술적 설명:** It is OBSERVED_DECISION_PRESERVED and RESERVE_POLICY_REJECTED, with retuning zero.
- **정확한 수치/증거:** 24 PASS, 1 reserve-policy rejection, 0 flips. Evidence: `docs/evidence/structural_audit_failure_analysis_v1/`
- **반드시 피할 주장:** all structural audits passed or cryptographic correctness failure

## Q39. Non-tabular scope을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** They are scoped scalar-replicated adapter observations only.
- **직관적 설명:** They broaden operation shapes but do not implement general packed neural inference.
- **기술적 설명:** Each adapter has frozen finite inputs and a separate source replay manifest.
- **정확한 수치/증거:** Sobel 400/400, Harris 200/200, CNN-lite 250/250. Evidence: `docs/evidence/non_tabular_sobel_holdout_v1/; docs/evidence/non_tabular_harris_holdout_v1/; docs/evidence/non_tabular_mnist_cnn_lite_holdout_v1/`
- **반드시 피할 주장:** arbitrary packed CNN support

## Q40. Non-tabular scope에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** They are scoped scalar-replicated adapter observations only.
- **직관적 설명:** They broaden operation shapes but do not implement general packed neural inference.
- **기술적 설명:** Each adapter has frozen finite inputs and a separate source replay manifest.
- **정확한 수치/증거:** Sobel 400/400, Harris 200/200, CNN-lite 250/250. Evidence: `docs/evidence/non_tabular_sobel_holdout_v1/; docs/evidence/non_tabular_harris_holdout_v1/; docs/evidence/non_tabular_mnist_cnn_lite_holdout_v1/`
- **반드시 피할 주장:** arbitrary packed CNN support

## Q41. One-host limitation을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** The latency result is paired evidence on one declared host and workload set.
- **직관적 설명:** Pairing controls local noise but does not sample different processors or deployments.
- **기술적 설명:** Warm-up 1, six measured passes, balanced cyclic/reverse order, no outlier removal, and no concurrent CKKS process were enforced.
- **정확한 수치/증거:** 40/40 confirmatory workload-partition instances complete; failures 0. Evidence: `docs/evidence/paired_latency_final_v1/`
- **반드시 피할 주장:** production or universal speedup

## Q42. One-host limitation에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** The latency result is paired evidence on one declared host and workload set.
- **직관적 설명:** Pairing controls local noise but does not sample different processors or deployments.
- **기술적 설명:** Warm-up 1, six measured passes, balanced cyclic/reverse order, no outlier removal, and no concurrent CKKS process were enforced.
- **정확한 수치/증거:** 40/40 confirmatory workload-partition instances complete; failures 0. Evidence: `docs/evidence/paired_latency_final_v1/`
- **반드시 피할 주장:** production or universal speedup

## Q43. Abstention meaning을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** NO_SAFE means no SAFE candidate was established inside the declared set and budget.
- **직관적 설명:** It is a disciplined refusal to choose from what was tried, not a statement about all possible configurations.
- **기술적 설명:** The budget and finite-domain controls freeze their candidate sets before evaluation.
- **정확한 수치/증거:** 16/40 budget controls and 50/50 finite-domain controls returned NO_SAFE. Evidence: `docs/evidence/no_safe_controls_confirmatory_v1/manifest.json`
- **반드시 피할 주장:** global infeasibility

## Q44. Abstention meaning에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** NO_SAFE means no SAFE candidate was established inside the declared set and budget.
- **직관적 설명:** It is a disciplined refusal to choose from what was tried, not a statement about all possible configurations.
- **기술적 설명:** The budget and finite-domain controls freeze their candidate sets before evaluation.
- **정확한 수치/증거:** 16/40 budget controls and 50/50 finite-domain controls returned NO_SAFE. Evidence: `docs/evidence/no_safe_controls_confirmatory_v1/manifest.json`
- **반드시 피할 주장:** global infeasibility

## Q45. Ambiguous input accounting을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** All eight raw repeat flips are disclosed and attributed to one declared V_amb input.
- **직관적 설명:** One near-threshold input was re-run across keysets/passes and flipped repeatedly.
- **기술적 설명:** Unique-input and raw-observation counts are reported separately; P1/P2 remain blocked.
- **정확한 수치/증거:** 8 raw flips; 1 unique ambiguous input. Evidence: `docs/evidence/final_realistic_baseline_closure_v9/direct_repeat_flip_forensics/`
- **반드시 피할 주장:** eight unique inputs or stable direct arm

## Q46. Ambiguous input accounting에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** All eight raw repeat flips are disclosed and attributed to one declared V_amb input.
- **직관적 설명:** One near-threshold input was re-run across keysets/passes and flipped repeatedly.
- **기술적 설명:** Unique-input and raw-observation counts are reported separately; P1/P2 remain blocked.
- **정확한 수치/증거:** 8 raw flips; 1 unique ambiguous input. Evidence: `docs/evidence/final_realistic_baseline_closure_v9/direct_repeat_flip_forensics/`
- **반드시 피할 주장:** eight unique inputs or stable direct arm

## Q47. Frozen evidence verification을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** Manuscript dependencies are SHA-256 bound and checked without rewriting predecessor packs.
- **직관적 설명:** The audit records exactly which bytes support each result.
- **기술적 설명:** V8/V9 checksums pass; V3/V10 pass in tracked-only checkouts, while ignored-cache false failures are retained as P0 issues.
- **정확한 수치/증거:** new scientific executions 0; manuscript modifications 0. Evidence: `docs/evidence/final_manuscript_audit_v1/dependency_manifest.json`
- **반드시 피할 주장:** claiming legacy verifier robustness in dirty trees

## Q48. Frozen evidence verification에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** Manuscript dependencies are SHA-256 bound and checked without rewriting predecessor packs.
- **직관적 설명:** The audit records exactly which bytes support each result.
- **기술적 설명:** V8/V9 checksums pass; V3/V10 pass in tracked-only checkouts, while ignored-cache false failures are retained as P0 issues.
- **정확한 수치/증거:** new scientific executions 0; manuscript modifications 0. Evidence: `docs/evidence/final_manuscript_audit_v1/dependency_manifest.json`
- **반드시 피할 주장:** claiming legacy verifier robustness in dirty trees

## Q49. Audit failure handling을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** The candidate is not retuned on that audit; the rejection lowers the claim or blocks deployment under that policy.
- **직관적 설명:** The audit is a final exam, not a chance to revise the answer.
- **기술적 설명:** A new policy or candidate would require a new predeclared protocol and untouched audit artifact.
- **정확한 수치/증거:** structural retuning 0 after one rejection. Evidence: `docs/evidence/structural_extension_v1/summary/audit_summary.json`
- **반드시 피할 주장:** repairing against locked-audit data

## Q50. Audit failure handling에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** The candidate is not retuned on that audit; the rejection lowers the claim or blocks deployment under that policy.
- **직관적 설명:** The audit is a final exam, not a chance to revise the answer.
- **기술적 설명:** A new policy or candidate would require a new predeclared protocol and untouched audit artifact.
- **정확한 수치/증거:** structural retuning 0 after one rejection. Evidence: `docs/evidence/structural_extension_v1/summary/audit_summary.json`
- **반드시 피할 주장:** repairing against locked-audit data

## Q51. Seed roles을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** Seed 0 is reported descriptively; only seeds 1-4 enter formal confirmatory summaries.
- **직관적 설명:** The data used to develop policy choices are kept out of the final aggregate.
- **기술적 설명:** The five partitions reuse a fixed held-out artifact and are not independent training splits.
- **정확한 수치/증거:** 10 development instances and 40 confirmatory instances. Evidence: `docs/thesis/number_registry.json`
- **반드시 피할 주장:** 50 independent workloads

## Q52. Seed roles에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** Seed 0 is reported descriptively; only seeds 1-4 enter formal confirmatory summaries.
- **직관적 설명:** The data used to develop policy choices are kept out of the final aggregate.
- **기술적 설명:** The five partitions reuse a fixed held-out artifact and are not independent training splits.
- **정확한 수치/증거:** 10 development instances and 40 confirmatory instances. Evidence: `docs/thesis/number_registry.json`
- **반드시 피할 주장:** 50 independent workloads

## Q53. Training-seed extension을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** A separate 3-dataset x 3-training-seed extension tests nine independently trained models.
- **직관적 설명:** This extension changes trained model artifacts, unlike the five deterministic partitions.
- **기술적 설명:** Selection and no-retuning audit both pass for all nine under the declared scope.
- **정확한 수치/증거:** 9/9 models. Evidence: `docs/evidence/independent_training_seed_extension_v1/summary.json`
- **반드시 피할 주장:** universal model-seed generalization

## Q54. Training-seed extension에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** A separate 3-dataset x 3-training-seed extension tests nine independently trained models.
- **직관적 설명:** This extension changes trained model artifacts, unlike the five deterministic partitions.
- **기술적 설명:** Selection and no-retuning audit both pass for all nine under the declared scope.
- **정확한 수치/증거:** 9/9 models. Evidence: `docs/evidence/independent_training_seed_extension_v1/summary.json`
- **반드시 피할 주장:** universal model-seed generalization

## Q55. Natural gap activation을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** For the MLP-100 adapter, the natural top-two-gap contract changed the literal from graph-only S32 to gap-aware S29.
- **직관적 설명:** The observed decision gap allowed a smaller scale literal than a fixed tolerance rule.
- **기술적 설명:** Both literals remain finite-scope SAFE, but the paired S32/S29 CI includes one, so latency superiority is not claimed.
- **정확한 수치/증거:** S32/S29 ratio 0.999780; 95% CI [0.998648, 1.000920]. Evidence: `docs/evidence/journal_multiclass_extension_final_v1/`
- **반드시 피할 주장:** S29 is faster than S32

## Q56. Natural gap activation에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** For the MLP-100 adapter, the natural top-two-gap contract changed the literal from graph-only S32 to gap-aware S29.
- **직관적 설명:** The observed decision gap allowed a smaller scale literal than a fixed tolerance rule.
- **기술적 설명:** Both literals remain finite-scope SAFE, but the paired S32/S29 CI includes one, so latency superiority is not claimed.
- **정확한 수치/증거:** S32/S29 ratio 0.999780; 95% CI [0.998648, 1.000920]. Evidence: `docs/evidence/journal_multiclass_extension_final_v1/`
- **반드시 피할 주장:** S29 is faster than S32

## Q57. LeNet catalog unsupported을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** The exact state is PLAN_UNSUPPORTED_WITHIN_FROZEN_CATALOG.
- **직관적 설명:** Those profiles lack required depth; they were not executed and rejected as numerically unsafe.
- **기술적 설명:** Direct synthesis produced an admitted S44 literal, but no direct-vs-catalog LeNet latency claim exists.
- **정확한 수치/증거:** 7/7 frozen profiles plan-unsupported. Evidence: `docs/evidence/journal_multiclass_claim_admission_v2/claims.json`
- **반드시 피할 주장:** LeNet NO_SAFE or catalog latency superiority

## Q58. LeNet catalog unsupported에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** The exact state is PLAN_UNSUPPORTED_WITHIN_FROZEN_CATALOG.
- **직관적 설명:** Those profiles lack required depth; they were not executed and rejected as numerically unsafe.
- **기술적 설명:** Direct synthesis produced an admitted S44 literal, but no direct-vs-catalog LeNet latency claim exists.
- **정확한 수치/증거:** 7/7 frozen profiles plan-unsupported. Evidence: `docs/evidence/journal_multiclass_claim_admission_v2/claims.json`
- **반드시 피할 주장:** LeNet NO_SAFE or catalog latency superiority

## Q59. Manuscript authority을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** This audit treats DOCX/PDF as immutable inputs and records proposed patches separately.
- **직관적 설명:** The researcher reviews every correction before a manuscript byte changes.
- **기술적 설명:** Dependency digests bind both manuscripts, editable assets, BibTeX, V8/V9 manifests, V3/V10, and RC2.
- **정확한 수치/증거:** manuscript files modified 0. Evidence: `docs/evidence/final_manuscript_audit_v1/dependency_manifest.json`
- **반드시 피할 주장:** claiming patches were applied

## Q60. Manuscript authority에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** This audit treats DOCX/PDF as immutable inputs and records proposed patches separately.
- **직관적 설명:** The researcher reviews every correction before a manuscript byte changes.
- **기술적 설명:** Dependency digests bind both manuscripts, editable assets, BibTeX, V8/V9 manifests, V3/V10, and RC2.
- **정확한 수치/증거:** manuscript files modified 0. Evidence: `docs/evidence/final_manuscript_audit_v1/dependency_manifest.json`
- **반드시 피할 주장:** claiming patches were applied

## Q61. FAILED versus REJECTED을 비전공자에게 설명해 보십시오.
- **한 문장 결론:** FAILED denotes inability to obtain a valid execution result; REJECTED denotes a completed candidate that did not satisfy admission.
- **직관적 설명:** One is a run problem, the other is a valid negative scientific result.
- **기술적 설명:** NO_SAFE is emitted only after the declared candidate budget establishes no SAFE candidate, regardless of whether alternatives failed or were rejected.
- **정확한 수치/증거:** CoreLab has 2 execution failures; structural audit has 1 policy rejection and 0 execution failures. Evidence: `docs/evidence/final_realistic_baseline_closure_v9/; docs/evidence/structural_extension_v1/`
- **반드시 피할 주장:** converting failures to zero or omitting them

## Q62. FAILED versus REJECTED에 대한 가장 강한 기술적 반론과 답은 무엇입니까?
- **한 문장 결론:** FAILED denotes inability to obtain a valid execution result; REJECTED denotes a completed candidate that did not satisfy admission.
- **직관적 설명:** One is a run problem, the other is a valid negative scientific result.
- **기술적 설명:** NO_SAFE is emitted only after the declared candidate budget establishes no SAFE candidate, regardless of whether alternatives failed or were rejected.
- **정확한 수치/증거:** CoreLab has 2 execution failures; structural audit has 1 policy rejection and 0 execution failures. Evidence: `docs/evidence/final_realistic_baseline_closure_v9/; docs/evidence/structural_extension_v1/`
- **반드시 피할 주장:** converting failures to zero or omitting them
