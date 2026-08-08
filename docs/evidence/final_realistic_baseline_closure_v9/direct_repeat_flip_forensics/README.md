# Direct Repeated-Flip Forensics

The eight V8 common-executor flips all occur on locked-audit row 711. Its plaintext score is `0.50001463545326585`, only `1.4635453265854359e-05` from threshold `0.5`, below the frozen ambiguity floor `0.001`. It is therefore `V_amb`, and the final class is `F4_NEAR_BOUNDARY_AMBIGUITY`.

The original locked-audit summary retained aggregate V_cert counts but no per-row decrypted values. This pack records those unavailable fields as `NOT_RECORDED_IN_FROZEN_SUMMARY`; it does not impute zeros. No encrypted replay was run because V9 permits targeted replay only for F1/F2. The direct arm remains in diagnostic latency data, while comparisons that require its repeated decision stability are blocked.
