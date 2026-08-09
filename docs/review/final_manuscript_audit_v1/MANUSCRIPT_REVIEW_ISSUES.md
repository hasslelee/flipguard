# Manuscript Review Issues

Status: **PROPOSED ONLY - authoritative manuscripts remain byte-identical.**

Issue count: P0=14, P1=8, P2=3.

## P0-001: An ignored Python bytecode cache makes the legacy verifier report a false integrity failure in a dirty checkout; the same tracked-only checkout verifies successfully.
- **Document:** Frozen V3 verifier
- **Section/page/paragraph:** results/thesis_grade_protocol/paper_artifacts_v3/final/verify_flipguard_v3_paper_artifacts.py
- **Current text/state:** The legacy tree digest traverses ignored __pycache__ files.
- **Problem:** An ignored Python bytecode cache makes the legacy verifier report a false integrity failure in a dirty checkout; the same tracked-only checkout verifies successfully.
- **Severity:** P0
- **Evidence:** tracked-only git-archive verification PASS; SHA256SUMS PASS
- **Exact proposed replacement/action:** Do not change frozen V3. In release verification, reconstruct a tracked-only checkout or use an allowlisted tree digest and document the legacy false-failure condition.
- **Applies to:** repository verifier
- **User decision required:** No manuscript decision; preserve the P0 record.
- **Auto-fix permitted:** NO

## P0-002: An ignored bytecode cache causes a false V10 digest failure in a dirty checkout; the tracked-only checkout verifies paper_writing_allowed=true.
- **Document:** Frozen V10 verifier
- **Section/page/paragraph:** docs/evidence/research_completion_checkpoint_v10/verify_research_completion_checkpoint_v10.py
- **Current text/state:** The legacy dependency tree digest traverses ignored __pycache__ files.
- **Problem:** An ignored bytecode cache causes a false V10 digest failure in a dirty checkout; the tracked-only checkout verifies paper_writing_allowed=true.
- **Severity:** P0
- **Evidence:** tracked-only git-archive verification PASS
- **Exact proposed replacement/action:** Keep V10 immutable and make the final release verifier operate on tracked-only inputs.
- **Applies to:** repository verifier
- **User decision required:** No manuscript decision; preserve the P0 record.
- **Auto-fix permitted:** NO

## P0-003: The complete thesis source lacks HEIR, Orion, LOHEN, SLOTHE, Lattigo, OpenML, and UCI entries; the journal additionally depends on the missing HEIR and Orion entries. Citation regeneration is therefore incomplete.
- **Document:** Journal and thesis editable bibliography
- **Section/page/paragraph:** common BibTeX versus manuscript reference lists
- **Current text/state:** The thesis DOCX contains 21 numbered works and the journal contains 16, while the shared editable BibTeX contains 14 entries.
- **Problem:** The complete thesis source lacks HEIR, Orion, LOHEN, SLOTHE, Lattigo, OpenML, and UCI entries; the journal additionally depends on the missing HEIR and Orion entries. Citation regeneration is therefore incomplete.
- **Severity:** P0
- **Evidence:** citation_audit.csv entries 10-13 and 17, 20-21
- **Exact proposed replacement/action:** After approval, add verified BibTeX entries for the seven missing sources and rebuild both reference lists without changing citation numbering silently.
- **Applies to:** both
- **User decision required:** Approve verified metadata and citation-key names.
- **Auto-fix permitted:** NO

## P0-004: The title does not match the official ASPLOS 2025 paper title.
- **Document:** Journal and thesis
- **Section/page/paragraph:** reference entry for Orion
- **Current text/state:** Orion: A Compiler for Encrypted Deep Learning
- **Problem:** The title does not match the official ASPLOS 2025 paper title.
- **Severity:** P0
- **Evidence:** DOI 10.1145/3676641.3716008
- **Exact proposed replacement/action:** Orion: A Fully Homomorphic Encryption Framework for Deep Learning
- **Applies to:** both
- **User decision required:** Approve bibliographic correction.
- **Auto-fix permitted:** NO

## P0-005: The title is abbreviated and does not match the official USENIX Security 2025 title.
- **Document:** Journal and thesis
- **Section/page/paragraph:** reference entry for LOHEN
- **Current text/state:** LOHEN: Layer-Wise Optimization for FHE Neural Inference
- **Problem:** The title is abbreviated and does not match the official USENIX Security 2025 title.
- **Severity:** P0
- **Evidence:** USENIX Security 2025 official proceedings, pp. 5583-5600
- **Exact proposed replacement/action:** LOHEN: Layer-wise Optimizations for Neural Network Inferences over Encrypted Data with High Performance or Accuracy
- **Applies to:** both
- **User decision required:** Approve bibliographic correction.
- **Auto-fix permitted:** NO

## P0-006: The title does not match the official USENIX Security 2025 title.
- **Document:** Journal and thesis
- **Section/page/paragraph:** reference entry for SLOTHE
- **Current text/state:** SLOTHE: Efficient Approximation for Encrypted Neural Networks
- **Problem:** The title does not match the official USENIX Security 2025 title.
- **Severity:** P0
- **Evidence:** USENIX Security 2025 official proceedings, pp. 3083-3102
- **Exact proposed replacement/action:** SLOTHE: Lazy Approximation of Non-Arithmetic Neural Network Functions over Encrypted Data
- **Applies to:** both
- **User decision required:** Approve bibliographic correction.
- **Auto-fix permitted:** NO

## P0-007: The frozen KIISC contract requires table and figure titles and content, plus references, to be in English.
- **Document:** Anonymous journal manuscript
- **Section/page/paragraph:** Tables 1-7
- **Current text/state:** Table titles and many cell entries are Korean or mixed Korean/English.
- **Problem:** The frozen KIISC contract requires table and figure titles and content, plus references, to be in English.
- **Severity:** P0
- **Evidence:** docs/journal/00_jkiisc_contract.md and DOCX table extraction
- **Exact proposed replacement/action:** Translate every table title, header, and body cell to technical English while preserving all values and evidence bindings.
- **Applies to:** journal
- **User decision required:** Approve a format-only table translation pass after this audit.
- **Auto-fix permitted:** NO

## P0-008: The formal catalog has 11 profiles and two execution paths, yielding 22 candidate identities per workload; calling these 22 profiles is factually wrong.
- **Document:** Thesis
- **Section/page/paragraph:** Table 20, catalog scope row
- **Current text/state:** bounded catalog, 22-profile scope
- **Problem:** The formal catalog has 11 profiles and two execution paths, yielding 22 candidate identities per workload; calling these 22 profiles is factually wrong.
- **Severity:** P0
- **Evidence:** docs/thesis/number_registry.json: security_catalog_profiles_total=11 and catalog_execution_paths=2
- **Exact proposed replacement/action:** bounded catalog, 11 profiles x 2 execution paths (22 candidate identities per workload)
- **Applies to:** thesis
- **User decision required:** Approve terminology correction.
- **Auto-fix permitted:** NO

## P0-009: A source-only clone cannot run the full test suite until external dataset restoration is executed and verified.
- **Document:** Release-readiness workflow
- **Section/page/paragraph:** clean-clone go test ./...
- **Current text/state:** The first valid clean-clone test run omitted ignored MNIST and BSDS500 source archives and four graph-contract tests failed with file-not-found errors.
- **Problem:** A source-only clone cannot run the full test suite until external dataset restoration is executed and verified.
- **Severity:** P0
- **Evidence:** clean_clone_audit.json recovery_attempts and source archive SHA-256 records
- **Exact proposed replacement/action:** Before tests, restore only the recorded MNIST and BSDS500 archives through the documented fetch/checksum path; verify SHA-256, run tests, then remove the archives before the clean-tree check.
- **Applies to:** artifact evaluation
- **User decision required:** No manuscript decision; retain the dependency explicitly in release instructions.
- **Auto-fix permitted:** NO

## P0-010: A source-only clone cannot execute the complete Python regression suite without restoring these frozen runtime inputs, even though their expected digests remain embedded in the contracts.
- **Document:** Release-readiness workflow
- **Section/page/paragraph:** clean-clone Python unittest discovery
- **Current text/state:** The first dependency-restored clean-clone run still omitted five git-ignored files bound by the EVA, HIT, and provider-gate contracts; 13 tests errored or failed before their intended assertions.
- **Problem:** A source-only clone cannot execute the complete Python regression suite without restoring these frozen runtime inputs, even though their expected digests remain embedded in the contracts.
- **Severity:** P0
- **Evidence:** clean_clone_audit.json recovery_attempts and bound_runtime_test_inputs
- **Exact proposed replacement/action:** Restore only the three iris split files, one direct-selection JSON, and one Security-V2 bounded-oracle CSV after verifying their frozen SHA-256 values; remove them before the final clean-tree assertion.
- **Applies to:** artifact evaluation
- **User decision required:** No manuscript decision; document the five-file artifact dependency in release instructions.
- **Auto-fix permitted:** NO

## P0-011: The regression suite verifies both the preserved fail-closed incident and the corrected provider run, but a source-only clone does not contain either runtime tree.
- **Document:** Release-readiness workflow
- **Section/page/paragraph:** clean-clone provider evidence-freezer tests
- **Current text/state:** After the five contract files were restored, three deep-validation tests still lacked the ignored provider-gate run_707441b and run_f84ecff trees.
- **Problem:** The regression suite verifies both the preserved fail-closed incident and the corrected provider run, but a source-only clone does not contain either runtime tree.
- **Severity:** P0
- **Evidence:** clean_clone_audit.json recovery_attempts and bound_runtime_test_trees
- **Exact proposed replacement/action:** Restore the two frozen run trees only after verifying their aggregate relative-path/per-file SHA-256 bindings; remove both trees before the final clean-tree assertion.
- **Applies to:** artifact evaluation
- **User decision required:** No manuscript decision; list both provider-gate runtime trees as required artifact-test inputs.
- **Auto-fix permitted:** NO

## P0-012: The source-only checkout contains the deterministic builder and frozen V7 pack, but not the raw status/normalized-output inputs used by that regression test.
- **Document:** Release-readiness workflow
- **Section/page/paragraph:** clean-clone V7 evidence-builder regression
- **Current text/state:** After provider-gate inputs were restored, one fail-closed V7 evidence-builder test still lacked the ignored external/v7/status and external/v7/outputs trees.
- **Problem:** The source-only checkout contains the deterministic builder and frozen V7 pack, but not the raw status/normalized-output inputs used by that regression test.
- **Severity:** P0
- **Evidence:** clean_clone_audit.json recovery_attempts and bound_runtime_test_trees
- **Exact proposed replacement/action:** Restore only the digest-bound V7 status and normalized-output trees for the regression suite; do not copy logs, build trees, containers, or caches, and remove both trees before the clean-tree assertion.
- **Applies to:** artifact evaluation
- **User decision required:** No manuscript decision; list the two V7 regression-input trees in artifact evaluation instructions.
- **Auto-fix permitted:** NO

## P0-013: The overlay intentionally hashes the MLIR, OpenFHE test, and Lattigo test sources, but these files live in an ignored external checkout.
- **Document:** Release-readiness workflow
- **Section/page/paragraph:** targeted clean-clone V7 overlay regression
- **Current text/state:** With V7 status and outputs restored, the overlay identity check still lacked three official HEIR dot-product source files.
- **Problem:** The overlay intentionally hashes the MLIR, OpenFHE test, and Lattigo test sources, but these files live in an ignored external checkout.
- **Severity:** P0
- **Evidence:** clean_clone_audit.json recovery_attempts and bound_runtime_test_inputs
- **Exact proposed replacement/action:** Restore only the three digest-bound HEIR dot-product source files used by input_identities(); do not restore external repositories, build products, or caches.
- **Applies to:** artifact evaluation
- **User decision required:** No manuscript decision; add the three HEIR source bindings to the artifact evaluator input inventory.
- **Auto-fix permitted:** NO

## P0-014: The same source file is a Python evidence-builder input but must not expand the repository Go package set during the native source test gate.
- **Document:** Release-readiness workflow
- **Section/page/paragraph:** clean-clone Go/Python input staging
- **Current text/state:** The first run with HEIR source bindings restored them before go test, which discovered an external generated test package without its generated implementation.
- **Problem:** The same source file is a Python evidence-builder input but must not expand the repository Go package set during the native source test gate.
- **Severity:** P0
- **Evidence:** clean_clone_audit.json recovery_attempts and staged command records
- **Exact proposed replacement/action:** Stage external inputs by consumer: restore only MNIST/BSDS500 before Go tests, then restore HEIR source and V7/provider runtime inputs before Python regression tests.
- **Applies to:** artifact evaluation
- **User decision required:** No manuscript decision; retain staged restoration in the clean-clone protocol.
- **Auto-fix permitted:** NO

## P1-001: The content is present but readability may be inadequate in print or reviewer PDF viewers.
- **Document:** Journal
- **Section/page/paragraph:** page 8 references and dense tables
- **Current text/state:** References and several table cells render at a very small visual size.
- **Problem:** The content is present but readability may be inadequate in print or reviewer PDF viewers.
- **Severity:** P1
- **Evidence:** 8-page PDF visual audit; fonts embedded
- **Exact proposed replacement/action:** After content approval, enlarge reference/table type or move secondary detail to an appendix/supplement without changing claims.
- **Applies to:** journal
- **User decision required:** Choose page budget versus readability trade-off.
- **Auto-fix permitted:** NO

## P1-002: The phrase can be read as a native cross-runtime ranking rather than the exact shared polynomial in the common Lattigo executor.
- **Document:** Thesis
- **Section/page/paragraph:** external comparison discussion
- **Current text/state:** HEIR의 더 빠른 stable 후보
- **Problem:** The phrase can be read as a native cross-runtime ranking rather than the exact shared polynomial in the common Lattigo executor.
- **Severity:** P1
- **Evidence:** V9 P3 claim admission; P1 and P2 are blocked
- **Exact proposed replacement/action:** 동일 Lattigo 실행기에서 exact shared polynomial로 재현한 HEIR 후보는 해당 P3 비교에서 더 낮은 total latency를 보였다.
- **Applies to:** thesis
- **User decision required:** Approve scope-explicit wording.
- **Auto-fix permitted:** NO

## P1-003: Software artifact metadata should follow one verified citation form and should not imply a peer-reviewed paper for the release itself.
- **Document:** Journal and thesis
- **Section/page/paragraph:** Lattigo bibliography entry
- **Current text/state:** Hybrid author/title metadata for Lattigo v6.2.0
- **Problem:** Software artifact metadata should follow one verified citation form and should not imply a peer-reviewed paper for the release itself.
- **Severity:** P1
- **Evidence:** official tuneinsight/lattigo repository and v6.2.0 release
- **Exact proposed replacement/action:** Use a verified software citation with version, repository URL, and access/release year; cite a paper separately only when its claims are used.
- **Applies to:** both
- **User decision required:** Select institutional software citation style.
- **Auto-fix permitted:** NO

## P1-004: Submission cannot be finalized until institution-specific data are supplied; guessing would be improper.
- **Document:** Thesis
- **Section/page/paragraph:** approval and administrative pages
- **Current text/state:** Advisor/committee/signature fields remain blank or generic.
- **Problem:** Submission cannot be finalized until institution-specific data are supplied; guessing would be improper.
- **Severity:** P1
- **Evidence:** 64-page PDF visual audit
- **Exact proposed replacement/action:** Fill only from official university records immediately before submission.
- **Applies to:** thesis
- **User decision required:** Provide advisor, committee, date, program, and signature requirements.
- **Auto-fix permitted:** NO

## P1-005: A reviewer can verify digests but cannot rebuild every layout object from raw evidence automatically.
- **Document:** Journal and thesis
- **Section/page/paragraph:** figure/table asset provenance
- **Current text/state:** Editable sources are present, but a per-asset generation script is not recorded for every imported object.
- **Problem:** A reviewer can verify digests but cannot rebuild every layout object from raw evidence automatically.
- **Severity:** P1
- **Evidence:** table_figure_source_binding.csv
- **Exact proposed replacement/action:** Retain the byte-bound editable sources and add generator provenance for future revisions; do not retroactively claim deterministic generation where absent.
- **Applies to:** both
- **User decision required:** No content decision; prioritize only figures likely to change.
- **Auto-fix permitted:** NO

## P1-006: The audit binds its digest, but another clone cannot obtain the manuscripts without the separately transferred bundle.
- **Document:** Manuscript input package
- **Section/page/paragraph:** docs/manuscript_review_input and flat ZIP
- **Current text/state:** The immutable review input is untracked in the audit branch.
- **Problem:** The audit binds its digest, but another clone cannot obtain the manuscripts without the separately transferred bundle.
- **Severity:** P1
- **Evidence:** git status --short and dependency_manifest.json
- **Exact proposed replacement/action:** Keep the authoring bundle private/untracked for anonymous review; distribute it through an approved private channel with the recorded SHA-256.
- **Applies to:** release process
- **User decision required:** Choose the private manuscript transfer mechanism.
- **Auto-fix permitted:** NO

## P1-007: The conclusion compresses the selection rule without restating that fastest selection is only within the declared candidate set and identical measurement boundary.
- **Document:** Journal
- **Section/page/paragraph:** conclusion, extracted p320.s2
- **Current text/state:** 적합한 후보 중 가장 빠른 구성을 선택하거나 NO_SAFE로 중단한다.
- **Problem:** The conclusion compresses the selection rule without restating that fastest selection is only within the declared candidate set and identical measurement boundary.
- **Severity:** P1
- **Evidence:** claim_sentence_traceability.csv and bounded-catalog claim boundary
- **Exact proposed replacement/action:** 선언된 후보 집합과 동일 측정 경계에서 적합한 후보 중 가장 빠른 구성을 선택하며, 그 집합에서 SAFE 후보를 확립하지 못하면 NO_SAFE로 중단한다.
- **Applies to:** journal
- **User decision required:** Approve scope-explicit conclusion wording.
- **Auto-fix permitted:** NO

## P1-008: The assets are not orphaned, but the placement convention requested for review is not met and readers may encounter tables/figures before a direct callout.
- **Document:** Journal and thesis
- **Section/page/paragraph:** figure/table cross-references
- **Current text/state:** Only 5 of 54 numbered assets have an explicit numbered in-text reference before the caption; 49 captions precede their first explicit numbered reference or have none.
- **Problem:** The assets are not orphaned, but the placement convention requested for review is not met and readers may encounter tables/figures before a direct callout.
- **Severity:** P1
- **Evidence:** table_figure_source_binding.csv, in_text_reference_before_appearance column
- **Exact proposed replacement/action:** Before each affected caption, add one concise sentence that explicitly cites the figure/table number and states the evidence question it answers; do not duplicate result numbers.
- **Applies to:** both
- **User decision required:** Approve a cross-reference-only formatting pass after content review.
- **Auto-fix permitted:** NO

## P2-001: The stale Word application metadata does not match the rendered 8-page PDF, although it does not affect content.
- **Document:** Journal DOCX
- **Section/page/paragraph:** core/app properties
- **Current text/state:** Application statistics report Pages=1 and Words=0.
- **Problem:** The stale Word application metadata does not match the rendered 8-page PDF, although it does not affect content.
- **Severity:** P2
- **Evidence:** DOCX metadata and PDF page count
- **Exact proposed replacement/action:** Let the final approved word processor refresh document statistics during export.
- **Applies to:** journal
- **User decision required:** None.
- **Auto-fix permitted:** NO

## P2-002: The relationship is understandable but should be defined once: integrity is the contract/layer, stability is the observed preservation property.
- **Document:** Journal and thesis
- **Section/page/paragraph:** terminology throughout
- **Current text/state:** decision integrity and decision stability are both used.
- **Problem:** The relationship is understandable but should be defined once: integrity is the contract/layer, stability is the observed preservation property.
- **Severity:** P2
- **Evidence:** formal_definition_audit.md
- **Exact proposed replacement/action:** Define the distinction at first use and keep later terminology role-specific.
- **Applies to:** both
- **User decision required:** Approve terminology convention.
- **Auto-fix permitted:** NO

## P2-003: The manuscript exceeds the basic six-page allocation but remains within the declared maximum; additional publication fees may apply.
- **Document:** Journal
- **Section/page/paragraph:** page budget
- **Current text/state:** Rendered preview is 8 pages.
- **Problem:** The manuscript exceeds the basic six-page allocation but remains within the declared maximum; additional publication fees may apply.
- **Severity:** P2
- **Evidence:** official KIISC contract and PDF page count
- **Exact proposed replacement/action:** No scientific edit required; confirm the page-fee decision before submission.
- **Applies to:** journal
- **User decision required:** Accept extra-page cost or compress after content approval.
- **Auto-fix permitted:** NO
