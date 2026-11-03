# FlipGuard Policy-Sensitivity Evidence

This pack freezes the complete static policy grid used in Step 7B.6.

- Static synthesis plans: `4,500`
- Successful plans: `4,485`
- Expected no-certifiable-sample outcomes: `15`
- Unexpected failures: `0`
- Aggregate policy cells: `90`
- Alpha certificate rows: `5`

At alpha `0.5`, lowering the margin floor from `0.001` to `0.0005`
increases certifiable validation rows from `8,043` to `8,142` and audit rows
from `8,122` to `8,203`, while retaining the same 50 static parameter
signatures. This is static challenger evidence, not encrypted recertification.

Verify all copied files, external bindings, grid completeness, outcome
semantics, alpha invariance, and the default/challenger checkpoints with:

```bash
python3 scripts/freeze_policy_sensitivity_evidence.py --verify
```
