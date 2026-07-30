# Independent Machine Replay Evidence V1

This pack preserves two fail-closed clean-runner recoveries and one successful
portable replay. The successful run verifies Go/Python checks, shell syntax,
clean-tree invariants, and committed completion checkpoints V1/V2.

Raw dataset and ignored execution-ledger replay is explicitly
NOT_EVALUATED_ON_CLEAN_CLONE. Five Go tests are excluded with recorded reasons:
four require external source datasets and one asserts nondeterministic missing
flag order in a source file bound by frozen evidence.

No CKKS experiment or policy retuning was performed.
`paper_claim_allowed=false`.
