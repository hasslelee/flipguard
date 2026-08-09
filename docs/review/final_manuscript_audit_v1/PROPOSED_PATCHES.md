# Proposed Manuscript Patches

These patches are review proposals only. They have not been applied to a DOCX, PDF, table, figure, BibTeX file, or frozen evidence pack.

## P0-001
**Target:** Frozen V3 verifier - results/thesis_grade_protocol/paper_artifacts_v3/final/verify_flipguard_v3_paper_artifacts.py

**Current:** The legacy tree digest traverses ignored __pycache__ files.

**Proposed:** Do not change frozen V3. In release verification, reconstruct a tracked-only checkout or use an allowlisted tree digest and document the legacy false-failure condition.

**Evidence guard:** tracked-only git-archive verification PASS; SHA256SUMS PASS

## P0-002
**Target:** Frozen V10 verifier - docs/evidence/research_completion_checkpoint_v10/verify_research_completion_checkpoint_v10.py

**Current:** The legacy dependency tree digest traverses ignored __pycache__ files.

**Proposed:** Keep V10 immutable and make the final release verifier operate on tracked-only inputs.

**Evidence guard:** tracked-only git-archive verification PASS

## P0-003
**Target:** Journal and thesis editable bibliography - common BibTeX versus manuscript reference lists

**Current:** The thesis DOCX contains 21 numbered works and the journal contains 16, while the shared editable BibTeX contains 14 entries.

**Proposed:** After approval, add verified BibTeX entries for the seven missing sources and rebuild both reference lists without changing citation numbering silently.

**Evidence guard:** citation_audit.csv entries 10-13 and 17, 20-21

## P0-004
**Target:** Journal and thesis - reference entry for Orion

**Current:** Orion: A Compiler for Encrypted Deep Learning

**Proposed:** Orion: A Fully Homomorphic Encryption Framework for Deep Learning

**Evidence guard:** DOI 10.1145/3676641.3716008

## P0-005
**Target:** Journal and thesis - reference entry for LOHEN

**Current:** LOHEN: Layer-Wise Optimization for FHE Neural Inference

**Proposed:** LOHEN: Layer-wise Optimizations for Neural Network Inferences over Encrypted Data with High Performance or Accuracy

**Evidence guard:** USENIX Security 2025 official proceedings, pp. 5583-5600

## P0-006
**Target:** Journal and thesis - reference entry for SLOTHE

**Current:** SLOTHE: Efficient Approximation for Encrypted Neural Networks

**Proposed:** SLOTHE: Lazy Approximation of Non-Arithmetic Neural Network Functions over Encrypted Data

**Evidence guard:** USENIX Security 2025 official proceedings, pp. 3083-3102

## P0-007
**Target:** Anonymous journal manuscript - Tables 1-7

**Current:** Table titles and many cell entries are Korean or mixed Korean/English.

**Proposed:** Translate every table title, header, and body cell to technical English while preserving all values and evidence bindings.

**Evidence guard:** docs/journal/00_jkiisc_contract.md and DOCX table extraction

## P0-008
**Target:** Thesis - Table 20, catalog scope row

**Current:** bounded catalog, 22-profile scope

**Proposed:** bounded catalog, 11 profiles x 2 execution paths (22 candidate identities per workload)

**Evidence guard:** docs/thesis/number_registry.json: security_catalog_profiles_total=11 and catalog_execution_paths=2

## P0-009
**Target:** Release-readiness workflow - clean-clone go test ./...

**Current:** The first valid clean-clone test run omitted ignored MNIST and BSDS500 source archives and four graph-contract tests failed with file-not-found errors.

**Proposed:** Before tests, restore only the recorded MNIST and BSDS500 archives through the documented fetch/checksum path; verify SHA-256, run tests, then remove the archives before the clean-tree check.

**Evidence guard:** clean_clone_audit.json recovery_attempts and source archive SHA-256 records

## P0-010
**Target:** Release-readiness workflow - clean-clone Python unittest discovery

**Current:** The first dependency-restored clean-clone run still omitted five git-ignored files bound by the EVA, HIT, and provider-gate contracts; 13 tests errored or failed before their intended assertions.

**Proposed:** Restore only the three iris split files, one direct-selection JSON, and one Security-V2 bounded-oracle CSV after verifying their frozen SHA-256 values; remove them before the final clean-tree assertion.

**Evidence guard:** clean_clone_audit.json recovery_attempts and bound_runtime_test_inputs

## P0-011
**Target:** Release-readiness workflow - clean-clone provider evidence-freezer tests

**Current:** After the five contract files were restored, three deep-validation tests still lacked the ignored provider-gate run_707441b and run_f84ecff trees.

**Proposed:** Restore the two frozen run trees only after verifying their aggregate relative-path/per-file SHA-256 bindings; remove both trees before the final clean-tree assertion.

**Evidence guard:** clean_clone_audit.json recovery_attempts and bound_runtime_test_trees

## P0-012
**Target:** Release-readiness workflow - clean-clone V7 evidence-builder regression

**Current:** After provider-gate inputs were restored, one fail-closed V7 evidence-builder test still lacked the ignored external/v7/status and external/v7/outputs trees.

**Proposed:** Restore only the digest-bound V7 status and normalized-output trees for the regression suite; do not copy logs, build trees, containers, or caches, and remove both trees before the clean-tree assertion.

**Evidence guard:** clean_clone_audit.json recovery_attempts and bound_runtime_test_trees

## P0-013
**Target:** Release-readiness workflow - targeted clean-clone V7 overlay regression

**Current:** With V7 status and outputs restored, the overlay identity check still lacked three official HEIR dot-product source files.

**Proposed:** Restore only the three digest-bound HEIR dot-product source files used by input_identities(); do not restore external repositories, build products, or caches.

**Evidence guard:** clean_clone_audit.json recovery_attempts and bound_runtime_test_inputs

## P0-014
**Target:** Release-readiness workflow - clean-clone Go/Python input staging

**Current:** The first run with HEIR source bindings restored them before go test, which discovered an external generated test package without its generated implementation.

**Proposed:** Stage external inputs by consumer: restore only MNIST/BSDS500 before Go tests, then restore HEIR source and V7/provider runtime inputs before Python regression tests.

**Evidence guard:** clean_clone_audit.json recovery_attempts and staged command records

## P0-015
**Target:** Release-readiness workflow - clean-clone deterministic audit rebuild

**Current:** All source tests and verifiers passed, but the audit builder changed rc2_archive.present from true to false because the ignored RC2 release archive was absent.

**Proposed:** Verify the RC2 archive against 05ef7030...c0be, restore it only for the audit rebuild, and remove it before the final clean-tree assertion.

**Evidence guard:** clean_clone_audit.json recovery_attempts and rebuild_archive_inputs

## P1-001
**Target:** Journal - page 8 references and dense tables

**Current:** References and several table cells render at a very small visual size.

**Proposed:** After content approval, enlarge reference/table type or move secondary detail to an appendix/supplement without changing claims.

**Evidence guard:** 8-page PDF visual audit; fonts embedded

## P1-002
**Target:** Thesis - external comparison discussion

**Current:** HEIR의 더 빠른 stable 후보

**Proposed:** 동일 Lattigo 실행기에서 exact shared polynomial로 재현한 HEIR 후보는 해당 P3 비교에서 더 낮은 total latency를 보였다.

**Evidence guard:** V9 P3 claim admission; P1 and P2 are blocked

## P1-003
**Target:** Journal and thesis - Lattigo bibliography entry

**Current:** Hybrid author/title metadata for Lattigo v6.2.0

**Proposed:** Use a verified software citation with version, repository URL, and access/release year; cite a paper separately only when its claims are used.

**Evidence guard:** official tuneinsight/lattigo repository and v6.2.0 release

## P1-004
**Target:** Thesis - approval and administrative pages

**Current:** Advisor/committee/signature fields remain blank or generic.

**Proposed:** Fill only from official university records immediately before submission.

**Evidence guard:** 64-page PDF visual audit

## P1-005
**Target:** Journal and thesis - figure/table asset provenance

**Current:** Editable sources are present, but a per-asset generation script is not recorded for every imported object.

**Proposed:** Retain the byte-bound editable sources and add generator provenance for future revisions; do not retroactively claim deterministic generation where absent.

**Evidence guard:** table_figure_source_binding.csv

## P1-006
**Target:** Manuscript input package - docs/manuscript_review_input and flat ZIP

**Current:** The immutable review input is untracked in the audit branch.

**Proposed:** Keep the authoring bundle private/untracked for anonymous review; distribute it through an approved private channel with the recorded SHA-256.

**Evidence guard:** git status --short and dependency_manifest.json

## P1-007
**Target:** Journal - conclusion, extracted p320.s2

**Current:** 적합한 후보 중 가장 빠른 구성을 선택하거나 NO_SAFE로 중단한다.

**Proposed:** 선언된 후보 집합과 동일 측정 경계에서 적합한 후보 중 가장 빠른 구성을 선택하며, 그 집합에서 SAFE 후보를 확립하지 못하면 NO_SAFE로 중단한다.

**Evidence guard:** claim_sentence_traceability.csv and bounded-catalog claim boundary

## P1-008
**Target:** Journal and thesis - figure/table cross-references

**Current:** Only 5 of 54 numbered assets have an explicit numbered in-text reference before the caption; 49 captions precede their first explicit numbered reference or have none.

**Proposed:** Before each affected caption, add one concise sentence that explicitly cites the figure/table number and states the evidence question it answers; do not duplicate result numbers.

**Evidence guard:** table_figure_source_binding.csv, in_text_reference_before_appearance column
