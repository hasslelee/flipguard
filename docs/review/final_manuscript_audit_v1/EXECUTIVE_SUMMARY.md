# Final Manuscript Audit Executive Summary

## Disposition

**PAUSE_FOR_USER_MANUSCRIPT_REVIEW.** The evidence and manuscripts were audited read-only. No scientific experiment, policy change, manuscript edit, or predecessor evidence rewrite was performed.

## Bound inputs

- Source checkpoint: `98e5e4105c0b0597d6fb245b5718a00eb4828349` on `experiments/final-realistic-baseline-v9`
- Journal DOCX/PDF: discovered and SHA-256 bound
- Thesis DOCX/PDF: discovered and SHA-256 bound
- V8/V9, V3, V10, RC2, and both claim registries: bound in `dependency_manifest.json`
- Editable tables, figures, equations, and BibTeX: digest-bound as immutable review inputs

## Audit coverage

- Number registry entries: **64**
- Traceability rows: **888**
- Positive technical sentences: **341**
- Positive states: {'BACKGROUND': 169, 'PARTIALLY_SUPPORTED': 75, 'SUPPORTED': 97}
- Table/figure bindings: **54** (54 bound)
- Bibliography records audited: **21**
- Reviewer attacks: **50**
- Defense questions: **62**

## Highest-risk findings

1. The legacy V3 and V10 verifiers falsely fail when ignored `__pycache__` directories appear inside hashed roots; tracked-only verification passes. This is recorded as P0 rather than bypassed.
2. The editable BibTeX has 14 entries while the manuscripts contain 21 references. Seven entries must be added from verified primary/software sources after approval.
3. Orion, LOHEN, and SLOTHE titles do not match their official records.
4. Journal table titles/cells do not meet the frozen English-only KIISC table requirement.
5. Thesis Table 20 says “22 profiles”; the authoritative meaning is 11 profiles x 2 paths = 22 candidate identities.

## Issue counts

- P0: **8**
- P1: **8**
- P2: **3**

The proposed edits are in `PROPOSED_PATCHES.md`; none were applied automatically.
