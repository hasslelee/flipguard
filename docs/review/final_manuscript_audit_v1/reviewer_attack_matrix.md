# Reviewer Attack Matrix

The questions below intentionally assume a hostile but technically competent reviewer. Evidence answers are scoped; no manuscript patch is applied in this stage.

## R1. Your treatment of Security-V2 admission is not sufficient. Why should I trust it?
- **Category:** CKKS and cryptographic assumptions
- **Reviewer concern:** Table-based admission may be mistaken for an exact runtime-distribution security proof.
- **Severity:** P0
- **Evidence-based answer:** The paper may claim Security-V2 policy admission, not universal exact 128-bit security. Ciphertext Q and evaluation-key QP are checked separately; the exact-estimator overlay reports model sensitivity and the Lattigo Xe truncation caveat.
- **Evidence:** `docs/evidence/security_v2_static_attestation_formal_v2/`
- **Prohibited overclaim:** universally 128-bit secure
- **30-second answer:** The paper may claim Security-V2 policy admission, not universal exact 128-bit security. 7 of 11 catalog profiles admitted; 4 excluded; target category 128.
- **Two-minute answer:** The policy checks the exact Q/P material against a published conservative cap, while the runtime error distribution is not claimed identical to the table model. Ciphertext Q and evaluation-key QP are checked separately; the exact-estimator overlay reports model sensitivity and the Lattigo Xe truncation caveat. The exact evidence is 7 of 11 catalog profiles admitted; 4 excluded; target category 128.
- **Manuscript change required:** YES
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R2. What concrete observation would falsify or narrow the paper's claim about Security-V2 admission?
- **Category:** CKKS and cryptographic assumptions
- **Reviewer concern:** Table-based admission may be mistaken for an exact runtime-distribution security proof.
- **Severity:** P0
- **Evidence-based answer:** The paper may claim Security-V2 policy admission, not universal exact 128-bit security. Ciphertext Q and evaluation-key QP are checked separately; the exact-estimator overlay reports model sensitivity and the Lattigo Xe truncation caveat.
- **Evidence:** `docs/evidence/security_v2_static_attestation_formal_v2/`
- **Prohibited overclaim:** universally 128-bit secure
- **30-second answer:** The paper may claim Security-V2 policy admission, not universal exact 128-bit security. 7 of 11 catalog profiles admitted; 4 excluded; target category 128.
- **Two-minute answer:** The policy checks the exact Q/P material against a published conservative cap, while the runtime error distribution is not claimed identical to the table model. Ciphertext Q and evaluation-key QP are checked separately; the exact-estimator overlay reports model sensitivity and the Lattigo Xe truncation caveat. The exact evidence is 7 of 11 catalog profiles admitted; 4 excluded; target category 128.
- **Manuscript change required:** YES
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R3. Your treatment of Q versus QP is not sufficient. Why should I trust it?
- **Category:** CKKS and cryptographic assumptions
- **Reviewer concern:** The manuscript could admit ciphertext parameters while ignoring evaluation keys.
- **Severity:** P0
- **Evidence-based answer:** Final admission requires every required object to pass its applicable Q or QP check. The policy records logQ, logP, logQP, per-object admission, headroom, and a final conjunction.
- **Evidence:** `docs/evidence/security_v2_static_attestation_formal_v2/`
- **Prohibited overclaim:** Q-only candidate security
- **30-second answer:** Final admission requires every required object to pass its applicable Q or QP check. 11 profiles audited; 7 admitted and 4 excluded.
- **Two-minute answer:** A safe ciphertext modulus alone does not cover the larger modulus material used by relinearization or key switching. The policy records logQ, logP, logQP, per-object admission, headroom, and a final conjunction. The exact evidence is 11 profiles audited; 7 admitted and 4 excluded.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R4. What concrete observation would falsify or narrow the paper's claim about Q versus QP?
- **Category:** CKKS and cryptographic assumptions
- **Reviewer concern:** The manuscript could admit ciphertext parameters while ignoring evaluation keys.
- **Severity:** P0
- **Evidence-based answer:** Final admission requires every required object to pass its applicable Q or QP check. The policy records logQ, logP, logQP, per-object admission, headroom, and a final conjunction.
- **Evidence:** `docs/evidence/security_v2_static_attestation_formal_v2/`
- **Prohibited overclaim:** Q-only candidate security
- **30-second answer:** Final admission requires every required object to pass its applicable Q or QP check. 11 profiles audited; 7 admitted and 4 excluded.
- **Two-minute answer:** A safe ciphertext modulus alone does not cover the larger modulus material used by relinearization or key switching. The policy records logQ, logP, logQP, per-object admission, headroom, and a final conjunction. The exact evidence is 11 profiles audited; 7 admitted and 4 excluded.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R5. Your treatment of Binary sufficient condition is not sufficient. Why should I trust it?
- **Category:** decision-stability theorem
- **Reviewer concern:** The paper may confuse an observed margin test with an analytical CKKS proof.
- **Severity:** P0
- **Evidence-based answer:** `e<m` is a pointwise sufficient decision condition; the evidence supplies observed encrypted errors on finite artifacts. The implication assumes finite values and strict inequality; it does not bound error on unseen inputs.
- **Evidence:** `docs/research/flipguard_v3_equation_list.md`
- **Prohibited overclaim:** complete analytical certificate
- **30-second answer:** `e<m` is a pointwise sufficient decision condition; the evidence supplies observed encrypted errors on finite artifacts. rho=0.5 is applied after the theorem as an operational cap.
- **Two-minute answer:** If the approximation error is smaller than the distance to the threshold, the score cannot cross the threshold. The implication assumes finite values and strict inequality; it does not bound error on unseen inputs. The exact evidence is rho=0.5 is applied after the theorem as an operational cap.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R6. What concrete observation would falsify or narrow the paper's claim about Binary sufficient condition?
- **Category:** decision-stability theorem
- **Reviewer concern:** The paper may confuse an observed margin test with an analytical CKKS proof.
- **Severity:** P0
- **Evidence-based answer:** `e<m` is a pointwise sufficient decision condition; the evidence supplies observed encrypted errors on finite artifacts. The implication assumes finite values and strict inequality; it does not bound error on unseen inputs.
- **Evidence:** `docs/research/flipguard_v3_equation_list.md`
- **Prohibited overclaim:** complete analytical certificate
- **30-second answer:** `e<m` is a pointwise sufficient decision condition; the evidence supplies observed encrypted errors on finite artifacts. rho=0.5 is applied after the theorem as an operational cap.
- **Two-minute answer:** If the approximation error is smaller than the distance to the threshold, the score cannot cross the threshold. The implication assumes finite values and strict inequality; it does not bound error on unseen inputs. The exact evidence is rho=0.5 is applied after the theorem as an operational cap.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R7. Your treatment of Multiclass proposition is not sufficient. Why should I trust it?
- **Category:** decision-stability theorem
- **Reviewer concern:** The top-two rule may omit class-wise errors or ties.
- **Severity:** P0
- **Evidence-based answer:** Argmax preservation follows only when every plaintext pairwise gap strictly exceeds the sum of the two class-wise error bounds. For uniform B, `2B<g`; equality, NaN/Inf, and plaintext ties are not certified.
- **Evidence:** `internal/certify/multiclass_decision_contract.go`
- **Prohibited overclaim:** non-strict or distribution-wide argmax guarantee
- **30-second answer:** Argmax preservation follows only when every plaintext pairwise gap strictly exceeds the sum of the two class-wise error bounds. 10 logits in the MLP-100 and LeNet-5-small adapters.
- **Two-minute answer:** Even if the top score moves down and a competitor moves up, their error intervals must not touch. For uniform B, `2B<g`; equality, NaN/Inf, and plaintext ties are not certified. The exact evidence is 10 logits in the MLP-100 and LeNet-5-small adapters.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R8. What concrete observation would falsify or narrow the paper's claim about Multiclass proposition?
- **Category:** decision-stability theorem
- **Reviewer concern:** The top-two rule may omit class-wise errors or ties.
- **Severity:** P0
- **Evidence-based answer:** Argmax preservation follows only when every plaintext pairwise gap strictly exceeds the sum of the two class-wise error bounds. For uniform B, `2B<g`; equality, NaN/Inf, and plaintext ties are not certified.
- **Evidence:** `internal/certify/multiclass_decision_contract.go`
- **Prohibited overclaim:** non-strict or distribution-wide argmax guarantee
- **30-second answer:** Argmax preservation follows only when every plaintext pairwise gap strictly exceeds the sum of the two class-wise error bounds. 10 logits in the MLP-100 and LeNet-5-small adapters.
- **Two-minute answer:** Even if the top score moves down and a competitor moves up, their error intervals must not touch. For uniform B, `2B<g`; equality, NaN/Inf, and plaintext ties are not certified. The exact evidence is 10 logits in the MLP-100 and LeNet-5-small adapters.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R9. Your treatment of Operational reserve policy is not sufficient. Why should I trust it?
- **Category:** rho = 0.5
- **Reviewer concern:** Why should reviewers accept an apparently arbitrary 0.5 constant?
- **Severity:** P1
- **Evidence-based answer:** rho=0.5 is a predeclared conservative utilization policy, not an optimal or theorem-derived constant. The alpha sensitivity grid did not change primary candidate states or initial literals because the minimum synthesis floor dominated.
- **Evidence:** `docs/evidence/margin_utilization_interpretation_v1/`
- **Prohibited overclaim:** theoretically optimal 0.5
- **30-second answer:** rho=0.5 is a predeclared conservative utilization policy, not an optimal or theorem-derived constant. rho=0.5; tested grid 0.1, 0.25, 0.5, 0.75, 0.9.
- **Two-minute answer:** Half the observed margin is used as the acceptance budget and half is reserved against finite-sample uncertainty. The alpha sensitivity grid did not change primary candidate states or initial literals because the minimum synthesis floor dominated. The exact evidence is rho=0.5; tested grid 0.1, 0.25, 0.5, 0.75, 0.9.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R10. What concrete observation would falsify or narrow the paper's claim about Operational reserve policy?
- **Category:** rho = 0.5
- **Reviewer concern:** Why should reviewers accept an apparently arbitrary 0.5 constant?
- **Severity:** P2
- **Evidence-based answer:** rho=0.5 is a predeclared conservative utilization policy, not an optimal or theorem-derived constant. The alpha sensitivity grid did not change primary candidate states or initial literals because the minimum synthesis floor dominated.
- **Evidence:** `docs/evidence/margin_utilization_interpretation_v1/`
- **Prohibited overclaim:** theoretically optimal 0.5
- **30-second answer:** rho=0.5 is a predeclared conservative utilization policy, not an optimal or theorem-derived constant. rho=0.5; tested grid 0.1, 0.25, 0.5, 0.75, 0.9.
- **Two-minute answer:** Half the observed margin is used as the acceptance budget and half is reserved against finite-sample uncertainty. The alpha sensitivity grid did not change primary candidate states or initial literals because the minimum synthesis floor dominated. The exact evidence is rho=0.5; tested grid 0.1, 0.25, 0.5, 0.75, 0.9.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R11. Your treatment of No-retuning audit is not sufficient. Why should I trust it?
- **Category:** validation versus audit
- **Reviewer concern:** The audit may secretly function as another tuning split.
- **Severity:** P1
- **Evidence-based answer:** The audit replays the selected literal byte-identically; synthesis, repair, and retuning are prohibited. Candidate, model, source, split, policy, and binary digests are recorded, with retuning count required to be zero.
- **Evidence:** `docs/evidence/direct_locked_audit_final_source_v1/`
- **Prohibited overclaim:** audit-guided selection
- **30-second answer:** The audit replays the selected literal byte-identically; synthesis, repair, and retuning are prohibited. 40/40 confirmatory and 10/10 development primary audits passed; retuning 0.
- **Two-minute answer:** Configuration selection ends before the audit data are opened. Candidate, model, source, split, policy, and binary digests are recorded, with retuning count required to be zero. The exact evidence is 40/40 confirmatory and 10/10 development primary audits passed; retuning 0.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R12. What concrete observation would falsify or narrow the paper's claim about No-retuning audit?
- **Category:** validation versus audit
- **Reviewer concern:** The audit may secretly function as another tuning split.
- **Severity:** P2
- **Evidence-based answer:** The audit replays the selected literal byte-identically; synthesis, repair, and retuning are prohibited. Candidate, model, source, split, policy, and binary digests are recorded, with retuning count required to be zero.
- **Evidence:** `docs/evidence/direct_locked_audit_final_source_v1/`
- **Prohibited overclaim:** audit-guided selection
- **30-second answer:** The audit replays the selected literal byte-identically; synthesis, repair, and retuning are prohibited. 40/40 confirmatory and 10/10 development primary audits passed; retuning 0.
- **Two-minute answer:** Configuration selection ends before the audit data are opened. Candidate, model, source, split, policy, and binary digests are recorded, with retuning count required to be zero. The exact evidence is 40/40 confirmatory and 10/10 development primary audits passed; retuning 0.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R13. Your treatment of Meaning of SAFE is not sufficient. Why should I trust it?
- **Category:** empirical finite-set scope
- **Reviewer concern:** SAFE may sound like a universal cryptographic correctness certificate.
- **Severity:** P1
- **Evidence-based answer:** SAFE means that one candidate passed execution, security admission, and the finite declared decision-reserve checks. The state binds the input/model/split/policy digests and observed fresh-key repetitions.
- **Evidence:** `docs/evidence/paper_claim_admission_v1/claims.json`
- **Prohibited overclaim:** distribution-wide safety
- **30-second answer:** SAFE means that one candidate passed execution, security admission, and the finite declared decision-reserve checks. 50 workload-partition instances in the controlled primary.
- **Two-minute answer:** It is a checked claim about named inputs and keys, not every future input. The state binds the input/model/split/policy digests and observed fresh-key repetitions. The exact evidence is 50 workload-partition instances in the controlled primary.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R14. What concrete observation would falsify or narrow the paper's claim about Meaning of SAFE?
- **Category:** empirical finite-set scope
- **Reviewer concern:** SAFE may sound like a universal cryptographic correctness certificate.
- **Severity:** P2
- **Evidence-based answer:** SAFE means that one candidate passed execution, security admission, and the finite declared decision-reserve checks. The state binds the input/model/split/policy digests and observed fresh-key repetitions.
- **Evidence:** `docs/evidence/paper_claim_admission_v1/claims.json`
- **Prohibited overclaim:** distribution-wide safety
- **30-second answer:** SAFE means that one candidate passed execution, security admission, and the finite declared decision-reserve checks. 50 workload-partition instances in the controlled primary.
- **Two-minute answer:** It is a checked claim about named inputs and keys, not every future input. The state binds the input/model/split/policy digests and observed fresh-key repetitions. The exact evidence is 50 workload-partition instances in the controlled primary.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R15. Your treatment of Provider-independent positioning is not sufficient. Why should I trust it?
- **Category:** direct synthesis algorithm
- **Reviewer concern:** The contribution may be misread as merely another autotuner.
- **Severity:** P1
- **Evidence-based answer:** FlipGuard is a decision-integrity layer with a built-in direct-synthesis provider. Manual, catalog, external-provider, and direct literals share security, encrypted-validation, state, and audit semantics.
- **Evidence:** `docs/evidence/final_realistic_baseline_closure_v9/final_baseline_matrix.csv`
- **Prohibited overclaim:** first or universal CKKS autotuner
- **30-second answer:** FlipGuard is a decision-integrity layer with a built-in direct-synthesis provider. External measured providers include EVA and HEIR; HECATE remains paper-only.
- **Two-minute answer:** Candidate generators propose configurations; the same gate decides whether any proposal is acceptable. Manual, catalog, external-provider, and direct literals share security, encrypted-validation, state, and audit semantics. The exact evidence is External measured providers include EVA and HEIR; HECATE remains paper-only.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R16. What concrete observation would falsify or narrow the paper's claim about Provider-independent positioning?
- **Category:** direct synthesis algorithm
- **Reviewer concern:** The contribution may be misread as merely another autotuner.
- **Severity:** P2
- **Evidence-based answer:** FlipGuard is a decision-integrity layer with a built-in direct-synthesis provider. Manual, catalog, external-provider, and direct literals share security, encrypted-validation, state, and audit semantics.
- **Evidence:** `docs/evidence/final_realistic_baseline_closure_v9/final_baseline_matrix.csv`
- **Prohibited overclaim:** first or universal CKKS autotuner
- **30-second answer:** FlipGuard is a decision-integrity layer with a built-in direct-synthesis provider. External measured providers include EVA and HEIR; HECATE remains paper-only.
- **Two-minute answer:** Candidate generators propose configurations; the same gate decides whether any proposal is acceptable. Manual, catalog, external-provider, and direct literals share security, encrypted-validation, state, and audit semantics. The exact evidence is External measured providers include EVA and HEIR; HECATE remains paper-only.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R17. Your treatment of Heuristic nature is not sufficient. Why should I trust it?
- **Category:** direct synthesis algorithm
- **Reviewer concern:** Direct synthesis could be dismissed as handcrafted constants fitted to two graphs.
- **Severity:** P1
- **Evidence-based answer:** It is a frozen graph-fact-to-literal policy with bounded empirical repairs, and its supported adapter scope is explicit. There is no model-specific lookup table in the policy; structural and multiclass adapters are evaluated without retuning policy constants.
- **Evidence:** `docs/evidence/direct_synthesis_policy_v2.json`
- **Prohibited overclaim:** universal synthesis optimality
- **30-second answer:** It is a frozen graph-fact-to-literal policy with bounded empirical repairs, and its supported adapter scope is explicit. 70 trials for 50 primary instances; observed maximum 2 under a policy maximum of 4.
- **Two-minute answer:** The graph supplies depth and scale requirements; the policy maps them to an admissible literal and tests it. There is no model-specific lookup table in the policy; structural and multiclass adapters are evaluated without retuning policy constants. The exact evidence is 70 trials for 50 primary instances; observed maximum 2 under a policy maximum of 4.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R18. What concrete observation would falsify or narrow the paper's claim about Heuristic nature?
- **Category:** direct synthesis algorithm
- **Reviewer concern:** Direct synthesis could be dismissed as handcrafted constants fitted to two graphs.
- **Severity:** P2
- **Evidence-based answer:** It is a frozen graph-fact-to-literal policy with bounded empirical repairs, and its supported adapter scope is explicit. There is no model-specific lookup table in the policy; structural and multiclass adapters are evaluated without retuning policy constants.
- **Evidence:** `docs/evidence/direct_synthesis_policy_v2.json`
- **Prohibited overclaim:** universal synthesis optimality
- **30-second answer:** It is a frozen graph-fact-to-literal policy with bounded empirical repairs, and its supported adapter scope is explicit. 70 trials for 50 primary instances; observed maximum 2 under a policy maximum of 4.
- **Two-minute answer:** The graph supplies depth and scale requirements; the policy maps them to an admissible literal and tests it. There is no model-specific lookup table in the policy; structural and multiclass adapters are evaluated without retuning policy constants. The exact evidence is 70 trials for 50 primary instances; observed maximum 2 under a policy maximum of 4.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R19. Your treatment of Repair causality is not sufficient. Why should I trust it?
- **Category:** repair and stopping rule
- **Reviewer concern:** Repair might be unconstrained search disguised as a rule.
- **Severity:** P1
- **Evidence-based answer:** Only classified numerical and level failures trigger fixed, bounded changes. Numerical repair adds four scale bits; level repair adds one Q prime; no audit-triggered repair is allowed.
- **Evidence:** `docs/evidence/direct_synthesis_policy_v2.json`
- **Prohibited overclaim:** unlimited adaptive search
- **30-second answer:** Only classified numerical and level failures trigger fixed, bounded changes. 20 primary repair events; policy trial limit 4.
- **Two-minute answer:** The system applies a small predeclared correction and stops once a candidate passes or the budget ends. Numerical repair adds four scale bits; level repair adds one Q prime; no audit-triggered repair is allowed. The exact evidence is 20 primary repair events; policy trial limit 4.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R20. What concrete observation would falsify or narrow the paper's claim about Repair causality?
- **Category:** repair and stopping rule
- **Reviewer concern:** Repair might be unconstrained search disguised as a rule.
- **Severity:** P2
- **Evidence-based answer:** Only classified numerical and level failures trigger fixed, bounded changes. Numerical repair adds four scale bits; level repair adds one Q prime; no audit-triggered repair is allowed.
- **Evidence:** `docs/evidence/direct_synthesis_policy_v2.json`
- **Prohibited overclaim:** unlimited adaptive search
- **30-second answer:** Only classified numerical and level failures trigger fixed, bounded changes. 20 primary repair events; policy trial limit 4.
- **Two-minute answer:** The system applies a small predeclared correction and stops once a candidate passes or the budget ends. Numerical repair adds four scale bits; level repair adds one Q prime; no audit-triggered repair is allowed. The exact evidence is 20 primary repair events; policy trial limit 4.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R21. Your treatment of Formal denominator is not sufficient. Why should I trust it?
- **Category:** bounded catalog fairness
- **Reviewer concern:** The 90% reduction could be inflated by using 1,100 insecure candidates.
- **Severity:** P1
- **Evidence-based answer:** The formal denominator is 700 Security-V2-admitted candidates, not the historical 1,100 executions. 7 admitted profiles x 2 paths x 50 instances = 700; confirmatory is 7 x 2 x 40 = 560.
- **Evidence:** `docs/thesis/number_registry.json`
- **Prohibited overclaim:** 90% versus 1,100 or global search
- **30-second answer:** The formal denominator is 700 Security-V2-admitted candidates, not the historical 1,100 executions. 70/700 and 56/560, both 90% reductions.
- **Two-minute answer:** Four of eleven profiles are retained as history but removed before formal selection accounting. 7 admitted profiles x 2 paths x 50 instances = 700; confirmatory is 7 x 2 x 40 = 560. The exact evidence is 70/700 and 56/560, both 90% reductions.
- **Manuscript change required:** YES
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R22. What concrete observation would falsify or narrow the paper's claim about Formal denominator?
- **Category:** bounded catalog fairness
- **Reviewer concern:** The 90% reduction could be inflated by using 1,100 insecure candidates.
- **Severity:** P2
- **Evidence-based answer:** The formal denominator is 700 Security-V2-admitted candidates, not the historical 1,100 executions. 7 admitted profiles x 2 paths x 50 instances = 700; confirmatory is 7 x 2 x 40 = 560.
- **Evidence:** `docs/thesis/number_registry.json`
- **Prohibited overclaim:** 90% versus 1,100 or global search
- **30-second answer:** The formal denominator is 700 Security-V2-admitted candidates, not the historical 1,100 executions. 70/700 and 56/560, both 90% reductions.
- **Two-minute answer:** Four of eleven profiles are retained as history but removed before formal selection accounting. 7 admitted profiles x 2 paths x 50 instances = 700; confirmatory is 7 x 2 x 40 = 560. The exact evidence is 70/700 and 56/560, both 90% reductions.
- **Manuscript change required:** YES
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R23. Your treatment of Oracle terminology is not sufficient. Why should I trust it?
- **Category:** bounded catalog fairness
- **Reviewer concern:** Calling the comparator an oracle may imply global optimality.
- **Severity:** P1
- **Evidence-based answer:** It is the fastest SAFE candidate only within the frozen Security-V2 bounded catalog. Inadmissible profiles and unsupported plans are excluded under declared rules.
- **Evidence:** `docs/evidence/security_v2_bounded_oracle_v1/`
- **Prohibited overclaim:** global oracle or global optimum
- **30-second answer:** It is the fastest SAFE candidate only within the frozen Security-V2 bounded catalog. 11 raw profiles, 7 admitted, two paths.
- **Two-minute answer:** The comparator exhausts a declared small shelf, not all possible CKKS parameters. Inadmissible profiles and unsupported plans are excluded under declared rules. The exact evidence is 11 raw profiles, 7 admitted, two paths.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R24. What concrete observation would falsify or narrow the paper's claim about Oracle terminology?
- **Category:** bounded catalog fairness
- **Reviewer concern:** Calling the comparator an oracle may imply global optimality.
- **Severity:** P2
- **Evidence-based answer:** It is the fastest SAFE candidate only within the frozen Security-V2 bounded catalog. Inadmissible profiles and unsupported plans are excluded under declared rules.
- **Evidence:** `docs/evidence/security_v2_bounded_oracle_v1/`
- **Prohibited overclaim:** global oracle or global optimum
- **30-second answer:** It is the fastest SAFE candidate only within the frozen Security-V2 bounded catalog. 11 raw profiles, 7 admitted, two paths.
- **Two-minute answer:** The comparator exhausts a declared small shelf, not all possible CKKS parameters. Inadmissible profiles and unsupported plans are excluded under declared rules. The exact evidence is 11 raw profiles, 7 admitted, two paths.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R25. Your treatment of HEIR role is not sufficient. Why should I trust it?
- **Category:** HEIR/EVA/CoreLab comparison
- **Reviewer concern:** HEIR may be mislabeled as an autotuner to enlarge the baseline set.
- **Severity:** P1
- **Evidence-based answer:** HEIR is reported as an external compiler/configuration provider. Only exact shared-graph common-Lattigo comparisons support the P3 latency claim.
- **Evidence:** `docs/evidence/final_realistic_baseline_closure_v9/tables/table_04_heir_common_executor_candidates.csv`
- **Prohibited overclaim:** HEIR autotuner unless exact context supports it
- **30-second answer:** HEIR is reported as an external compiler/configuration provider. HEIR validation/audit flips 0/0 across 500/500 inputs and three contexts.
- **Two-minute answer:** It emits a configuration for the shared polynomial; FlipGuard then applies the common gate. Only exact shared-graph common-Lattigo comparisons support the P3 latency claim. The exact evidence is HEIR validation/audit flips 0/0 across 500/500 inputs and three contexts.
- **Manuscript change required:** YES
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R26. What concrete observation would falsify or narrow the paper's claim about HEIR role?
- **Category:** HEIR/EVA/CoreLab comparison
- **Reviewer concern:** HEIR may be mislabeled as an autotuner to enlarge the baseline set.
- **Severity:** P2
- **Evidence-based answer:** HEIR is reported as an external compiler/configuration provider. Only exact shared-graph common-Lattigo comparisons support the P3 latency claim.
- **Evidence:** `docs/evidence/final_realistic_baseline_closure_v9/tables/table_04_heir_common_executor_candidates.csv`
- **Prohibited overclaim:** HEIR autotuner unless exact context supports it
- **30-second answer:** HEIR is reported as an external compiler/configuration provider. HEIR validation/audit flips 0/0 across 500/500 inputs and three contexts.
- **Two-minute answer:** It emits a configuration for the shared polynomial; FlipGuard then applies the common gate. Only exact shared-graph common-Lattigo comparisons support the P3 latency claim. The exact evidence is HEIR validation/audit flips 0/0 across 500/500 inputs and three contexts.
- **Manuscript change required:** YES
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R27. Your treatment of P1/P2 instability is not sufficient. Why should I trust it?
- **Category:** HEIR/EVA/CoreLab comparison
- **Reviewer concern:** Why are attractive direct latency comparisons omitted?
- **Severity:** P1
- **Evidence-based answer:** P1 HEIR/direct and P2 catalog/direct are blocked because the repeated direct arm flipped on one V_amb input. Eight raw flips came from one unique near-boundary input; the arm remains diagnostic but not a stable-speed denominator.
- **Evidence:** `docs/evidence/final_realistic_baseline_closure_v9/direct_repeat_flip_forensics/`
- **Prohibited overclaim:** eight failed inputs or admitted direct speedup
- **30-second answer:** P1 HEIR/direct and P2 catalog/direct are blocked because the repeated direct arm flipped on one V_amb input. 8 raw repeats, 1 unique V_amb input.
- **Two-minute answer:** A fast arm is not an admissible stable baseline when repeated execution changes the decision. Eight raw flips came from one unique near-boundary input; the arm remains diagnostic but not a stable-speed denominator. The exact evidence is 8 raw repeats, 1 unique V_amb input.
- **Manuscript change required:** YES
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R28. What concrete observation would falsify or narrow the paper's claim about P1/P2 instability?
- **Category:** HEIR/EVA/CoreLab comparison
- **Reviewer concern:** Why are attractive direct latency comparisons omitted?
- **Severity:** P2
- **Evidence-based answer:** P1 HEIR/direct and P2 catalog/direct are blocked because the repeated direct arm flipped on one V_amb input. Eight raw flips came from one unique near-boundary input; the arm remains diagnostic but not a stable-speed denominator.
- **Evidence:** `docs/evidence/final_realistic_baseline_closure_v9/direct_repeat_flip_forensics/`
- **Prohibited overclaim:** eight failed inputs or admitted direct speedup
- **30-second answer:** P1 HEIR/direct and P2 catalog/direct are blocked because the repeated direct arm flipped on one V_amb input. 8 raw repeats, 1 unique V_amb input.
- **Two-minute answer:** A fast arm is not an admissible stable baseline when repeated execution changes the decision. Eight raw flips came from one unique near-boundary input; the arm remains diagnostic but not a stable-speed denominator. The exact evidence is 8 raw repeats, 1 unique V_amb input.
- **Manuscript change required:** YES
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R29. Your treatment of CoreLab scope is not sufficient. Why should I trust it?
- **Category:** HEIR/EVA/CoreLab comparison
- **Reviewer concern:** The 72-plan grid may be presented as decision-stability evidence.
- **Severity:** P1
- **Evidence-based answer:** CoreLab EVA/ELASM is NUMERICAL_ONLY error-latency plan evidence. Seventy plans executed successfully and two failed; 14,000 rows are plan-input observations, not independent decision samples.
- **Evidence:** `docs/evidence/final_realistic_baseline_closure_v9/tables/table_06_corelab_eva_hecate_elasm_grid.csv`
- **Prohibited overclaim:** decision-bearing CoreLab baseline
- **30-second answer:** CoreLab EVA/ELASM is NUMERICAL_ONLY error-latency plan evidence. 36 EVA + 36 ELASM plans; 70 PASS, 2 failures.
- **Two-minute answer:** Those rows measure numerical behavior but do not carry the threshold decision contract used by the main evaluation. Seventy plans executed successfully and two failed; 14,000 rows are plan-input observations, not independent decision samples. The exact evidence is 36 EVA + 36 ELASM plans; 70 PASS, 2 failures.
- **Manuscript change required:** YES
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R30. What concrete observation would falsify or narrow the paper's claim about CoreLab scope?
- **Category:** HEIR/EVA/CoreLab comparison
- **Reviewer concern:** The 72-plan grid may be presented as decision-stability evidence.
- **Severity:** P2
- **Evidence-based answer:** CoreLab EVA/ELASM is NUMERICAL_ONLY error-latency plan evidence. Seventy plans executed successfully and two failed; 14,000 rows are plan-input observations, not independent decision samples.
- **Evidence:** `docs/evidence/final_realistic_baseline_closure_v9/tables/table_06_corelab_eva_hecate_elasm_grid.csv`
- **Prohibited overclaim:** decision-bearing CoreLab baseline
- **30-second answer:** CoreLab EVA/ELASM is NUMERICAL_ONLY error-latency plan evidence. 36 EVA + 36 ELASM plans; 70 PASS, 2 failures.
- **Two-minute answer:** Those rows measure numerical behavior but do not carry the threshold decision contract used by the main evaluation. Seventy plans executed successfully and two failed; 14,000 rows are plan-input observations, not independent decision samples. The exact evidence is 36 EVA + 36 ELASM plans; 70 PASS, 2 failures.
- **Manuscript change required:** YES
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R31. Your treatment of HECATE and Orion depth is not sufficient. Why should I trust it?
- **Category:** security alignment
- **Reviewer concern:** The paper could imply more external experimental coverage than exists.
- **Severity:** P0
- **Evidence-based answer:** HECATE is a paper baseline only; Orion is a 10-input official self-test pilot. Their states are NOT_EVALUATED and PILOT_ONLY in V9 claim admission.
- **Evidence:** `docs/evidence/final_realistic_baseline_closure_v9/manifest.json`
- **Prohibited overclaim:** measured HECATE or formal Orion validation
- **30-second answer:** HECATE is a paper baseline only; Orion is a 10-input official self-test pilot. HECATE plans attempted 0; Orion preflight inputs 10.
- **Two-minute answer:** Neither is counted as a formal measured decision baseline. Their states are NOT_EVALUATED and PILOT_ONLY in V9 claim admission. The exact evidence is HECATE plans attempted 0; Orion preflight inputs 10.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R32. What concrete observation would falsify or narrow the paper's claim about HECATE and Orion depth?
- **Category:** security alignment
- **Reviewer concern:** The paper could imply more external experimental coverage than exists.
- **Severity:** P0
- **Evidence-based answer:** HECATE is a paper baseline only; Orion is a 10-input official self-test pilot. Their states are NOT_EVALUATED and PILOT_ONLY in V9 claim admission.
- **Evidence:** `docs/evidence/final_realistic_baseline_closure_v9/manifest.json`
- **Prohibited overclaim:** measured HECATE or formal Orion validation
- **30-second answer:** HECATE is a paper baseline only; Orion is a 10-input official self-test pilot. HECATE plans attempted 0; Orion preflight inputs 10.
- **Two-minute answer:** Neither is counted as a formal measured decision baseline. Their states are NOT_EVALUATED and PILOT_ONLY in V9 claim admission. The exact evidence is HECATE plans attempted 0; Orion preflight inputs 10.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R33. Your treatment of Primary latency inference is not sufficient. Why should I trust it?
- **Category:** statistical unit and confidence intervals
- **Reviewer concern:** Forty partitions or 5,400 records may be treated as independent.
- **Severity:** P0
- **Evidence-based answer:** The primary inference unit is the 10 dataset-model clusters; partitions are within-cluster repetitions. The ratio uses a dataset-model-cluster geometric mean and a cluster bootstrap, with no raw record-level p-value.
- **Evidence:** `results/thesis_grade_protocol/paired_latency_claim_admission_v1/seeds1_4_confirmatory_summary.json`
- **Prohibited overclaim:** 50 or 5,400 independent samples
- **30-second answer:** The primary inference unit is the 10 dataset-model clusters; partitions are within-cluster repetitions. ratio 3.140660; 95% CI [2.342334, 4.215313].
- **Two-minute answer:** Repeated measurements of the same workload do not create new workloads. The ratio uses a dataset-model-cluster geometric mean and a cluster bootstrap, with no raw record-level p-value. The exact evidence is ratio 3.140660; 95% CI [2.342334, 4.215313].
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R34. What concrete observation would falsify or narrow the paper's claim about Primary latency inference?
- **Category:** statistical unit and confidence intervals
- **Reviewer concern:** Forty partitions or 5,400 records may be treated as independent.
- **Severity:** P0
- **Evidence-based answer:** The primary inference unit is the 10 dataset-model clusters; partitions are within-cluster repetitions. The ratio uses a dataset-model-cluster geometric mean and a cluster bootstrap, with no raw record-level p-value.
- **Evidence:** `results/thesis_grade_protocol/paired_latency_claim_admission_v1/seeds1_4_confirmatory_summary.json`
- **Prohibited overclaim:** 50 or 5,400 independent samples
- **30-second answer:** The primary inference unit is the 10 dataset-model clusters; partitions are within-cluster repetitions. ratio 3.140660; 95% CI [2.342334, 4.215313].
- **Two-minute answer:** Repeated measurements of the same workload do not create new workloads. The ratio uses a dataset-model-cluster geometric mean and a cluster bootstrap, with no raw record-level p-value. The exact evidence is ratio 3.140660; 95% CI [2.342334, 4.215313].
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R35. Your treatment of P3 latency inference is not sufficient. Why should I trust it?
- **Category:** statistical unit and confidence intervals
- **Reviewer concern:** The 1,800 pairs could falsely narrow the confidence interval.
- **Severity:** P0
- **Evidence-based answer:** P3 reports input-cluster inference; keysets and passes are repeated measurements. Three keysets and six passes produce 1,800 raw pairs; the bootstrap clusters by input.
- **Evidence:** `docs/evidence/final_realistic_baseline_closure_v9/tables/table_05_pairwise_latency_claims.csv`
- **Prohibited overclaim:** raw-pair independence
- **30-second answer:** P3 reports input-cluster inference; keysets and passes are repeated measurements. 6.393517, 95% CI [6.361222, 6.427118].
- **Two-minute answer:** The same 100 inputs are timed repeatedly, so there are 100 input clusters, not 1,800 independent inputs. Three keysets and six passes produce 1,800 raw pairs; the bootstrap clusters by input. The exact evidence is 6.393517, 95% CI [6.361222, 6.427118].
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R36. What concrete observation would falsify or narrow the paper's claim about P3 latency inference?
- **Category:** statistical unit and confidence intervals
- **Reviewer concern:** The 1,800 pairs could falsely narrow the confidence interval.
- **Severity:** P0
- **Evidence-based answer:** P3 reports input-cluster inference; keysets and passes are repeated measurements. Three keysets and six passes produce 1,800 raw pairs; the bootstrap clusters by input.
- **Evidence:** `docs/evidence/final_realistic_baseline_closure_v9/tables/table_05_pairwise_latency_claims.csv`
- **Prohibited overclaim:** raw-pair independence
- **30-second answer:** P3 reports input-cluster inference; keysets and passes are repeated measurements. 6.393517, 95% CI [6.361222, 6.427118].
- **Two-minute answer:** The same 100 inputs are timed repeatedly, so there are 100 input clusters, not 1,800 independent inputs. Three keysets and six passes produce 1,800 raw pairs; the bootstrap clusters by input. The exact evidence is 6.393517, 95% CI [6.361222, 6.427118].
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R37. Your treatment of Structural negative result is not sufficient. Why should I trust it?
- **Category:** generalization
- **Reviewer concern:** Reporting 24/25 may undermine the claimed audit protocol.
- **Severity:** P1
- **Evidence-based answer:** The one rejection is preserved and demonstrates that validation SAFE does not guarantee unseen reserve-policy acceptance. It is OBSERVED_DECISION_PRESERVED and RESERVE_POLICY_REJECTED, with retuning zero.
- **Evidence:** `docs/evidence/structural_audit_failure_analysis_v1/`
- **Prohibited overclaim:** all structural audits passed or cryptographic correctness failure
- **30-second answer:** The one rejection is preserved and demonstrates that validation SAFE does not guarantee unseen reserve-policy acceptance. 24 PASS, 1 reserve-policy rejection, 0 flips.
- **Two-minute answer:** The decision did not flip, but the encrypted error used more than the reserved half-margin on one audit observation. It is OBSERVED_DECISION_PRESERVED and RESERVE_POLICY_REJECTED, with retuning zero. The exact evidence is 24 PASS, 1 reserve-policy rejection, 0 flips.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R38. What concrete observation would falsify or narrow the paper's claim about Structural negative result?
- **Category:** generalization
- **Reviewer concern:** Reporting 24/25 may undermine the claimed audit protocol.
- **Severity:** P2
- **Evidence-based answer:** The one rejection is preserved and demonstrates that validation SAFE does not guarantee unseen reserve-policy acceptance. It is OBSERVED_DECISION_PRESERVED and RESERVE_POLICY_REJECTED, with retuning zero.
- **Evidence:** `docs/evidence/structural_audit_failure_analysis_v1/`
- **Prohibited overclaim:** all structural audits passed or cryptographic correctness failure
- **30-second answer:** The one rejection is preserved and demonstrates that validation SAFE does not guarantee unseen reserve-policy acceptance. 24 PASS, 1 reserve-policy rejection, 0 flips.
- **Two-minute answer:** The decision did not flip, but the encrypted error used more than the reserved half-margin on one audit observation. It is OBSERVED_DECISION_PRESERVED and RESERVE_POLICY_REJECTED, with retuning zero. The exact evidence is 24 PASS, 1 reserve-policy rejection, 0 flips.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R39. Your treatment of Non-tabular scope is not sufficient. Why should I trust it?
- **Category:** generalization
- **Reviewer concern:** Sobel, Harris, and CNN-lite could be stretched into arbitrary image/CNN support.
- **Severity:** P1
- **Evidence-based answer:** They are scoped scalar-replicated adapter observations only. Each adapter has frozen finite inputs and a separate source replay manifest.
- **Evidence:** `docs/evidence/non_tabular_sobel_holdout_v1/; docs/evidence/non_tabular_harris_holdout_v1/; docs/evidence/non_tabular_mnist_cnn_lite_holdout_v1/`
- **Prohibited overclaim:** arbitrary packed CNN support
- **30-second answer:** They are scoped scalar-replicated adapter observations only. Sobel 400/400, Harris 200/200, CNN-lite 250/250.
- **Two-minute answer:** They broaden operation shapes but do not implement general packed neural inference. Each adapter has frozen finite inputs and a separate source replay manifest. The exact evidence is Sobel 400/400, Harris 200/200, CNN-lite 250/250.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R40. What concrete observation would falsify or narrow the paper's claim about Non-tabular scope?
- **Category:** generalization
- **Reviewer concern:** Sobel, Harris, and CNN-lite could be stretched into arbitrary image/CNN support.
- **Severity:** P2
- **Evidence-based answer:** They are scoped scalar-replicated adapter observations only. Each adapter has frozen finite inputs and a separate source replay manifest.
- **Evidence:** `docs/evidence/non_tabular_sobel_holdout_v1/; docs/evidence/non_tabular_harris_holdout_v1/; docs/evidence/non_tabular_mnist_cnn_lite_holdout_v1/`
- **Prohibited overclaim:** arbitrary packed CNN support
- **30-second answer:** They are scoped scalar-replicated adapter observations only. Sobel 400/400, Harris 200/200, CNN-lite 250/250.
- **Two-minute answer:** They broaden operation shapes but do not implement general packed neural inference. Each adapter has frozen finite inputs and a separate source replay manifest. The exact evidence is Sobel 400/400, Harris 200/200, CNN-lite 250/250.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R41. Your treatment of One-host limitation is not sufficient. Why should I trust it?
- **Category:** latency measurement
- **Reviewer concern:** A 3.14 ratio could be advertised as production performance.
- **Severity:** P1
- **Evidence-based answer:** The latency result is paired evidence on one declared host and workload set. Warm-up 1, six measured passes, balanced cyclic/reverse order, no outlier removal, and no concurrent CKKS process were enforced.
- **Evidence:** `docs/evidence/paired_latency_final_v1/`
- **Prohibited overclaim:** production or universal speedup
- **30-second answer:** The latency result is paired evidence on one declared host and workload set. 40/40 confirmatory workload-partition instances complete; failures 0.
- **Two-minute answer:** Pairing controls local noise but does not sample different processors or deployments. Warm-up 1, six measured passes, balanced cyclic/reverse order, no outlier removal, and no concurrent CKKS process were enforced. The exact evidence is 40/40 confirmatory workload-partition instances complete; failures 0.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R42. What concrete observation would falsify or narrow the paper's claim about One-host limitation?
- **Category:** latency measurement
- **Reviewer concern:** A 3.14 ratio could be advertised as production performance.
- **Severity:** P2
- **Evidence-based answer:** The latency result is paired evidence on one declared host and workload set. Warm-up 1, six measured passes, balanced cyclic/reverse order, no outlier removal, and no concurrent CKKS process were enforced.
- **Evidence:** `docs/evidence/paired_latency_final_v1/`
- **Prohibited overclaim:** production or universal speedup
- **30-second answer:** The latency result is paired evidence on one declared host and workload set. 40/40 confirmatory workload-partition instances complete; failures 0.
- **Two-minute answer:** Pairing controls local noise but does not sample different processors or deployments. Warm-up 1, six measured passes, balanced cyclic/reverse order, no outlier removal, and no concurrent CKKS process were enforced. The exact evidence is 40/40 confirmatory workload-partition instances complete; failures 0.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R43. Your treatment of Abstention meaning is not sufficient. Why should I trust it?
- **Category:** NO_SAFE
- **Reviewer concern:** NO_SAFE may be misread as proof that no CKKS parameters can work.
- **Severity:** P1
- **Evidence-based answer:** NO_SAFE means no SAFE candidate was established inside the declared set and budget. The budget and finite-domain controls freeze their candidate sets before evaluation.
- **Evidence:** `docs/evidence/no_safe_controls_confirmatory_v1/manifest.json`
- **Prohibited overclaim:** global infeasibility
- **30-second answer:** NO_SAFE means no SAFE candidate was established inside the declared set and budget. 16/40 budget controls and 50/50 finite-domain controls returned NO_SAFE.
- **Two-minute answer:** It is a disciplined refusal to choose from what was tried, not a statement about all possible configurations. The budget and finite-domain controls freeze their candidate sets before evaluation. The exact evidence is 16/40 budget controls and 50/50 finite-domain controls returned NO_SAFE.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R44. What concrete observation would falsify or narrow the paper's claim about Abstention meaning?
- **Category:** NO_SAFE
- **Reviewer concern:** NO_SAFE may be misread as proof that no CKKS parameters can work.
- **Severity:** P2
- **Evidence-based answer:** NO_SAFE means no SAFE candidate was established inside the declared set and budget. The budget and finite-domain controls freeze their candidate sets before evaluation.
- **Evidence:** `docs/evidence/no_safe_controls_confirmatory_v1/manifest.json`
- **Prohibited overclaim:** global infeasibility
- **30-second answer:** NO_SAFE means no SAFE candidate was established inside the declared set and budget. 16/40 budget controls and 50/50 finite-domain controls returned NO_SAFE.
- **Two-minute answer:** It is a disciplined refusal to choose from what was tried, not a statement about all possible configurations. The budget and finite-domain controls freeze their candidate sets before evaluation. The exact evidence is 16/40 budget controls and 50/50 finite-domain controls returned NO_SAFE.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R45. Your treatment of Ambiguous input accounting is not sufficient. Why should I trust it?
- **Category:** V_amb
- **Reviewer concern:** The direct arm's eight flips could be hidden by aggregate counts.
- **Severity:** P1
- **Evidence-based answer:** All eight raw repeat flips are disclosed and attributed to one declared V_amb input. Unique-input and raw-observation counts are reported separately; P1/P2 remain blocked.
- **Evidence:** `docs/evidence/final_realistic_baseline_closure_v9/direct_repeat_flip_forensics/`
- **Prohibited overclaim:** eight unique inputs or stable direct arm
- **30-second answer:** All eight raw repeat flips are disclosed and attributed to one declared V_amb input. 8 raw flips; 1 unique ambiguous input.
- **Two-minute answer:** One near-threshold input was re-run across keysets/passes and flipped repeatedly. Unique-input and raw-observation counts are reported separately; P1/P2 remain blocked. The exact evidence is 8 raw flips; 1 unique ambiguous input.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R46. What concrete observation would falsify or narrow the paper's claim about Ambiguous input accounting?
- **Category:** V_amb
- **Reviewer concern:** The direct arm's eight flips could be hidden by aggregate counts.
- **Severity:** P2
- **Evidence-based answer:** All eight raw repeat flips are disclosed and attributed to one declared V_amb input. Unique-input and raw-observation counts are reported separately; P1/P2 remain blocked.
- **Evidence:** `docs/evidence/final_realistic_baseline_closure_v9/direct_repeat_flip_forensics/`
- **Prohibited overclaim:** eight unique inputs or stable direct arm
- **30-second answer:** All eight raw repeat flips are disclosed and attributed to one declared V_amb input. 8 raw flips; 1 unique ambiguous input.
- **Two-minute answer:** One near-threshold input was re-run across keysets/passes and flipped repeatedly. Unique-input and raw-observation counts are reported separately; P1/P2 remain blocked. The exact evidence is 8 raw flips; 1 unique ambiguous input.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R47. Your treatment of Frozen evidence verification is not sufficient. Why should I trust it?
- **Category:** reproducibility
- **Reviewer concern:** Large evidence packs can silently drift after manuscript writing.
- **Severity:** P1
- **Evidence-based answer:** Manuscript dependencies are SHA-256 bound and checked without rewriting predecessor packs. V8/V9 checksums pass; V3/V10 pass in tracked-only checkouts, while ignored-cache false failures are retained as P0 issues.
- **Evidence:** `docs/evidence/final_manuscript_audit_v1/dependency_manifest.json`
- **Prohibited overclaim:** claiming legacy verifier robustness in dirty trees
- **30-second answer:** Manuscript dependencies are SHA-256 bound and checked without rewriting predecessor packs. new scientific executions 0; manuscript modifications 0.
- **Two-minute answer:** The audit records exactly which bytes support each result. V8/V9 checksums pass; V3/V10 pass in tracked-only checkouts, while ignored-cache false failures are retained as P0 issues. The exact evidence is new scientific executions 0; manuscript modifications 0.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R48. What concrete observation would falsify or narrow the paper's claim about Frozen evidence verification?
- **Category:** reproducibility
- **Reviewer concern:** Large evidence packs can silently drift after manuscript writing.
- **Severity:** P2
- **Evidence-based answer:** Manuscript dependencies are SHA-256 bound and checked without rewriting predecessor packs. V8/V9 checksums pass; V3/V10 pass in tracked-only checkouts, while ignored-cache false failures are retained as P0 issues.
- **Evidence:** `docs/evidence/final_manuscript_audit_v1/dependency_manifest.json`
- **Prohibited overclaim:** claiming legacy verifier robustness in dirty trees
- **30-second answer:** Manuscript dependencies are SHA-256 bound and checked without rewriting predecessor packs. new scientific executions 0; manuscript modifications 0.
- **Two-minute answer:** The audit records exactly which bytes support each result. V8/V9 checksums pass; V3/V10 pass in tracked-only checkouts, while ignored-cache false failures are retained as P0 issues. The exact evidence is new scientific executions 0; manuscript modifications 0.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R49. Your treatment of Audit failure handling is not sufficient. Why should I trust it?
- **Category:** practical deployment
- **Reviewer concern:** What happens operationally when a locked audit rejects a selected candidate?
- **Severity:** P1
- **Evidence-based answer:** The candidate is not retuned on that audit; the rejection lowers the claim or blocks deployment under that policy. A new policy or candidate would require a new predeclared protocol and untouched audit artifact.
- **Evidence:** `docs/evidence/structural_extension_v1/summary/audit_summary.json`
- **Prohibited overclaim:** repairing against locked-audit data
- **30-second answer:** The candidate is not retuned on that audit; the rejection lowers the claim or blocks deployment under that policy. structural retuning 0 after one rejection.
- **Two-minute answer:** The audit is a final exam, not a chance to revise the answer. A new policy or candidate would require a new predeclared protocol and untouched audit artifact. The exact evidence is structural retuning 0 after one rejection.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.

## R50. What concrete observation would falsify or narrow the paper's claim about Audit failure handling?
- **Category:** practical deployment
- **Reviewer concern:** What happens operationally when a locked audit rejects a selected candidate?
- **Severity:** P2
- **Evidence-based answer:** The candidate is not retuned on that audit; the rejection lowers the claim or blocks deployment under that policy. A new policy or candidate would require a new predeclared protocol and untouched audit artifact.
- **Evidence:** `docs/evidence/structural_extension_v1/summary/audit_summary.json`
- **Prohibited overclaim:** repairing against locked-audit data
- **30-second answer:** The candidate is not retuned on that audit; the rejection lowers the claim or blocks deployment under that policy. structural retuning 0 after one rejection.
- **Two-minute answer:** The audit is a final exam, not a chance to revise the answer. A new policy or candidate would require a new predeclared protocol and untouched audit artifact. The exact evidence is structural retuning 0 after one rejection.
- **Manuscript change required:** NO
- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.
