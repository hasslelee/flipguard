# Structural locked-audit failure analysis

- Analysis: `structural_audit_failure_analysis_v1`
- Classification: `VALIDATION_NEAR_BUDGET_LIMIT_AUDIT_OVERRUN`
- Scope: explanatory post-hoc static analysis; no encrypted rerun and no policy change
- Workload: seed 4 / banknote / mlp_square_poly3
- Candidate: `synth_analysis_minimum_rescale_N14_Q10_S22_01ae407b2f60`
- Validation: SAFE, 0 flips, 0 violations, max usage 0.941306
- Locked audit: REJECTED, 0 flips, 1 violation, max usage 1.122737
- Observation accounting: exactly 1 of 621 sample-key observations violated the alpha-margin budget
- Key scope: exactly one key repeat for one sample; the row and repeat identities were not persisted
- Margin evidence: validation min 0.012218, audit min 0.013422
- Error evidence: validation max 0.055838, audit max 0.064058
- No-flip explanation: alpha=0.5 rejects at normalized usage 1, while a threshold crossing requires usage at least 2; observed max usage was 1.122737
- Claim consequence: structural generalization is `PARTIALLY_SUPPORTED` (24/25 audit PASS, 1/25 numerical REJECT)

## Evidence limit

The execution artifact persisted aggregate certificate values but not the in-memory
per-sample CKKS scores. Exact row ID, CKKS score, absolute error, and key-repeat
identity are therefore reported as `NOT_RECORDED_IN_EXECUTION_ARTIFACT` rather than reconstructed.
