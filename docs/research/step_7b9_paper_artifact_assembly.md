# Step 7B.9: FlipGuard V2 paper artifact assembly

## Purpose

The legacy paper builders summarize the original fixed-profile experiments.
They must not be used for the V2 main claim. The V2 artifact builder reads
only frozen evidence packs that first pass their native verifiers.

The method and evidence roles are deliberately separated:

- input-conditioned direct synthesis and no-retuning locked audit: primary
  method evidence;
- fixed 22-candidate execution: bounded oracle and baseline;
- planner projection: candidate-provider ablation;
- linear rejection and NO_SAFE cases: negative/falsification controls;
- paired latency pilot: protocol-design evidence only.

## Build

```bash
python3 scripts/build_flipguard_v2_paper_artifacts.py --force
python3 scripts/build_flipguard_v2_paper_artifacts.py --verify
```

The default `auto` profile uses six preliminary inputs, including the
Security V2 static re-attestation pack. It switches to the final profile only
when all four confirmatory packs exist:

```text
direct_locked_audit_final_source_v1
no_safe_controls_confirmatory_v1
structural_extension_v1
paired_latency_final_v1
```

Use `--profile final` to fail closed when any final pack is missing.

## Publication gate

The generated manifest reports one of:

- `NON_AUTHORITATIVE_SCAFFOLD`: tables and figures are useful for protocol review, but
  their values cannot be promoted to final abstract or conclusion claims.
- `FINAL_ADMISSIBLE`: every confirmatory pack passes its native verifier,
  all semantic gates pass, the direct/structural packs contain
  workload-complete selection and locked-audit source replay evidence, and
  the four encrypted final packs bind one source commit. The independently
  versioned Security V2 static pack must also pass.

The bounded-oracle and policy-sensitivity packs retain their own scope
boundaries even in a final build. The 22-candidate catalog supports claims
only within its declared candidate domain.

## Outputs

The output root is:

```text
results/thesis_grade_protocol/paper_artifacts_v2/current/
```

It contains deterministic CSV/Markdown tables, SVG figures with visible
evidence status, and `appendix/evidence_manifest.json`. The manifest binds
the complete input evidence trees, their source commits, the builder, and
every generated output. It also binds the manuscript digest and the complete
Figure 1--6/Table 1--5 mapping.

Each final direct/structural pack is self-contained for its declared
tabular inputs: model artifacts and upstream source-test CSVs are deduplicated,
while selection/audit source and prepared partitions are snapshotted per
workload.

`figure_01_framework.svg` deliberately replaces the earlier
`Oracle-Calibrated Selection / Exhaustive Fastest-SAFE` emphasis. The primary
workflow now starts from a model artifact plus held-out raw or model-input
feature data, applies the artifact-bound selected-feature preprocessing when
needed, binds source and materialized validation artifacts in the workload
contract, synthesizes one executable literal, repairs only after an observed
failure, returns `NO_SAFE` when the budget is exhausted, and audits a SAFE
literal without retuning. The fixed catalog appears only in evaluation tables
as a bounded oracle.

The final-suite regression phase also runs:

```bash
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
```

These tests exercise the shared-source final gate, final paired-latency gate,
confirmatory finite-domain schema, deterministic tree comparison, and SVG
well-formedness without requiring the expensive final experiment to exist.
They also require every generated table/figure to be mapped into the
manuscript and prevent known preliminary metrics from entering the abstract
or conclusion. A `NON_AUTHORITATIVE_SCAFFOLD` manuscript must retain exact placeholder
content inside the final result/conclusion blocks. A `FINAL_ADMISSIBLE` build
deterministically replaces those blocks with evidence-conditioned claims and
then verifies their exact content. The builder enforces the same rule during
both build and deterministic verify, so the final artifact cannot be admitted
with preliminary or hand-edited headline claims.

## Current status

The current pack is expected to be `NON_AUTHORITATIVE_SCAFFOLD`. It supports the
methodological conclusion that direct synthesis replaces hand-enumerated
configuration search, while the old grid remains useful as a bounded oracle.
Final numerical claims remain gated on the clean-commit confirmatory suite.
