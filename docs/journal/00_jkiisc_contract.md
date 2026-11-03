# JKIISC Manuscript Contract

## Artifact status

- Manuscript type: general paper
- Delivery: template-ready authorless content pack
- Official HWP conversion: not performed
- Frozen research source: `journal_multiclass_extension_final_v1`
- Core RC2, Paper Artifacts V3, Completion V10, authoritative thesis: immutable
- New dataset/model/policy optimization: none

## Title

- Korean: 결정 무결성 계약 기반 CKKS 실행 구성 직접 합성 및 검증
- English: FlipGuard: Direct Synthesis and Validation of CKKS Configurations
  under Decision-Integrity Contracts

## Official format binding

The initial submission is an authorless PDF. The official source form is HWP;
the repository output remains template-ready until it is placed in that form.
The manuscript is Korean with an English title and abstract, uses a Korean
abstract of at most 700 characters and an English abstract of at most 250
words, and lists no more than five English keywords. Body layout is two-column
with 150% line spacing and at most 20 A4 pages including figures and tables.

Chapters use Roman numerals and sections use Arabic numerals. Figure captions
appear below figures; table titles appear above tables. Figure titles/content,
table titles/content, and references are English. Citations appear before the
sentence-ending period in the final HWP layout. The intended content budget is
9-11 pages; six pages are included in the base publication charge, with the
official extra-page schedule beginning at page seven.

## Research message

FlipGuard is a decision-integrity layer, not a universal or first CKKS
autotuner claim. It directly synthesizes a literal from a supported graph and
decision contract, runs bounded encrypted validation and failure-aware repair,
abstains with `NO_SAFE` when no candidate is admitted, and replays the selected
literal without retuning on a disjoint locked audit. A Security-V2 bounded
catalog is an evaluation-only comparator.

The manuscript reports three evidence tiers: Controlled Primary, Standard
Multiclass Generalization, and Additional Robustness. The MLP-100 result
establishes a natural top-two-gap literal effect, but its S29/S32 paired latency
interval includes one. The LeNet result is finite direct-selection and audit
evidence with `PLAN_UNSUPPORTED_WITHIN_FROZEN_CATALOG`; no LeNet catalog speed
claim is allowed.

## Claim and security boundary

Journal claims must be exact wording or scoped paraphrases of entries with
`paper_admitted=true` in `journal_multiclass_claim_admission_v2`, together with
the admitted core claims in `paper_claim_admission_v1`. Security wording must
state both Security-V2 admission and the two declared classical estimator
adapters. Exact runtime error-distribution equivalence, quantum 128-bit
security, arbitrary packed-CNN support, global optimality, distribution-wide
decision safety, and a complete analytical CKKS certificate are prohibited.

## Falsification rules

The content pack is invalid if it changes a frozen evidence digest, presents
1,100 as the formal catalog denominator, describes 50 repeated partitions as
independent workloads, omits the structural reserve-policy rejection, reports
S29 as faster than S32, implies a LeNet catalog comparison, includes author
identity, or violates the official English figure/table/reference rule.
