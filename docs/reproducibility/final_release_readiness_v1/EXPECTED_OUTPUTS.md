# Expected Outputs

- `verify_frozen_evidence.sh`: V8/V9 and registry checks PASS; V3/V10 are verified in a tracked-only view.
- `verify_manuscript_numbers.py`: registry source digests and critical values PASS.
- `verify_claim_sentence_traceability.py`: required documents/states and prohibited admissions PASS.
- `reproduce_quick_demo.sh`: prints `SAFE`, `REJECTED`, and `NO_SAFE` examples with `DEMONSTRATION_ONLY`.
- `verify_final_manuscript_audit_v1.py`: checks the audit pack checksum and completeness.

A mismatch is a P0 integrity event. Do not regenerate or overwrite predecessor evidence to make it disappear.
