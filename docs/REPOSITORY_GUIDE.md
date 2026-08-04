# FlipGuard Repository Guide

FlipGuard combines software, protocol documents, frozen encrypted evidence, derived claim overlays, and publication inputs. This guide explains how to navigate those layers without mistaking a historical result for a current claim.

## Top-Level Map

| Path | Role |
|---|---|
| `cmd/` | Go command-line programs for synthesis, execution, audit, and analysis |
| `internal/` | core Go packages and supported graph adapters |
| `configs/` | configuration and ablation inputs |
| `datasets/` | models, source metadata, split identities, and derived inputs |
| `scripts/` | protocol runners, builders, freezers, and verifiers |
| `docs/research/` | design decisions, predeclared protocols, and reviewer-oriented analysis |
| `docs/evidence/` | immutable evidence packs and later overlays |
| `results/` | raw ledgers, summaries, and deterministic publication inputs |
| `docs/assets/` | public brand and repository figures |

## Evidence Lifecycle

Evidence directories use explicit status and versioning. Common roles include:

- `PRELIMINARY` or `PILOT_ONLY`: useful development evidence, not a final headline source;
- `PRE_SECURITY_V2`: encrypted execution preserved before the current security filter;
- `HISTORICAL_CHECKPOINT`: an immutable state snapshot;
- final frozen packs: verified source, policy, inputs, summaries, failures, and checksums;
- interpretation or admission overlays: derived views that cite frozen predecessors without rewriting them.

Do not choose a directory only because its name contains `final`. Verify its manifest, source commit, policy digests, claim state, and predecessor dependencies.

## Reading a Pack

Start with these files when present:

1. `README.md` for purpose and scope;
2. `manifest.json` for schema, identities, and dependencies;
3. `summary.json` or equivalent for derived observations;
4. failure records and negative-result taxonomy;
5. `SHA256SUMS` for byte integrity;
6. the local verifier for deterministic validation.

Never edit a frozen pack to update wording. Add a new versioned overlay and bind its predecessor digest.

## Current Public Evidence Entry Points

- Core claims: [`docs/evidence/paper_claim_admission_v1`](evidence/paper_claim_admission_v1/)
- Core completion: [`docs/evidence/research_completion_checkpoint_v10`](evidence/research_completion_checkpoint_v10/)
- Core release binding: [`docs/evidence/research_release_binding_rc2_v1`](evidence/research_release_binding_rc2_v1/)
- Security-V2 oracle: [`docs/evidence/security_v2_bounded_oracle_v1`](evidence/security_v2_bounded_oracle_v1/)
- Multiclass final: [`docs/evidence/journal_multiclass_extension_final_v1`](evidence/journal_multiclass_extension_final_v1/)
- Multiclass claims: [`docs/evidence/journal_multiclass_claim_admission_v2`](evidence/journal_multiclass_claim_admission_v2/)
- Public summary: [`docs/RESULTS.md`](RESULTS.md)

## Historical Execution Counts

The pre-security catalog ledger has 1,100 encrypted execution records. Security Policy V2 excludes 4 of 11 profiles, leaving 7 profiles, 2 paths, and 50 workload-partition instances: 700 formal candidates. Use 700 for the all-instance formal trial comparison and 560 for confirmatory seeds 1–4. Use 1,100 only to describe historical execution work or security sensitivity.

## Source and Prepared Inputs

Source artifacts and prepared execution artifacts can differ byte-for-byte while preserving the same ordered semantic rows. FlipGuard therefore tracks source, prepared, semantic, ordered-row, and model digests separately. A comparator must not substitute one identity layer for another.

## Public Export

The research worktree can contain large duplicate ledgers, third-party official forms, anonymous review content, and local historical metadata that should not be included in a redistributable source bundle. The [public-export manifest](../.github/public-export-manifest.json) records exclusions without deleting frozen files.

Never publish raw secret keys, credentials, access tokens, licensed templates, private datasets, or anonymous review materials. GitHub's source view and a curated public artifact export are different surfaces and must be audited separately.

## Contribution Rule

Before changing a research path, classify the change as execution-critical, interpretation-only, documentation-only, or verification-only. Documentation work must not change model artifacts, split assignments, policies, encrypted ledgers, or candidate identities. See [CONTRIBUTING.md](../CONTRIBUTING.md).
