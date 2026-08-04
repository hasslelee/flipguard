# Reproducing FlipGuard

FlipGuard separates quick source checks, deterministic artifact verification, and full encrypted reproduction. Choose the lightest level that answers your question.

## Frozen References

| Artifact | Reference |
|---|---|
| Core research release | tag `flipguard-thesis-v1.0.0-rc2` |
| Core source commit | `6c5f8b234f9f9da91a189fa0f2dc180bb996abf5` |
| Core release archive SHA-256 | `05ef70306a11ab577243b0c708489864f19ccd104e6036e28fc6bd1dab45c0be` |
| Latest frozen journal research source | `fd53d9f23040fd1490d9816a928dd04ec58eb473` |
| Core release binding | [`research_release_binding_rc2_v1`](evidence/research_release_binding_rc2_v1/) |
| Multiclass final pack | [`journal_multiclass_extension_final_v1`](evidence/journal_multiclass_extension_final_v1/) |

Public-documentation commits after the journal source do not alter research execution semantics or frozen evidence.

## Environment

- Go 1.25.9
- Lattigo v6.2.0, as pinned in `go.mod`
- Python 3 for builders and deterministic verifiers
- Pillow 10.2.0 for selected artifact and public-preview tools
- Linux host for recorded encrypted executions

Exact host, binary, policy, model, split, and input digests are stored in their run manifests. Paired latency is hardware-specific and should be reproduced on a dedicated host with no concurrent CKKS process.

## Level 1: Five-Minute Smoke

```bash
go version
go mod download
go run ./cmd/flipguard-synthesize --help
go run ./cmd/flipguard-synthesize \
  --model datasets/tabular_suite/banknote/mlp_square_linear_score/model.json \
  --validation results/thesis_grade_protocol/tabular_splits_v1/split_seed_0/banknote/mlp_square_linear_score/configuration_validation.csv \
  --split-id public_smoke_v1 > /tmp/flipguard-public-smoke.json
python3 -m json.tool /tmp/flipguard-public-smoke.json >/dev/null
```

This checks dependency resolution, CLI construction, model parsing, policy binding, and static direct synthesis. It does not create new thesis-grade encrypted evidence.

## Level 2: Focused Source Verification

```bash
go test ./...
go vet ./...
python3 -m unittest scripts.tests.test_lint_public_readme
python3 scripts/lint_public_readme.py
```

This level is appropriate for pull requests. CI does not run long encrypted experiments or depend on private data.

## Level 3: Artifact-Only Deterministic Verification

The reproducibility workflow executes representative static verifiers. They consume frozen records and do not launch new candidate or latency runs.

```bash
python3 docs/evidence/research_release_binding_rc2_v1/verify_research_release_binding_rc2.py
python3 docs/evidence/paper_claim_admission_v1/verify_paper_claim_admission.py
python3 scripts/verify_flipguard_v3_paper_artifacts.py
python3 docs/evidence/research_completion_checkpoint_v10/verify_research_completion_checkpoint_v10.py
python3 docs/evidence/journal_multiclass_extension_final_v1/verify_journal_multiclass_extension_final_v1.py
python3 docs/evidence/journal_multiclass_claim_admission_v2/verify_journal_multiclass_claim_admission_v2.py
python3 scripts/verify_journal_mlp_paired_latency_evidence_v1.py
```

Each frozen pack includes its own `SHA256SUMS` and verifier. If a verifier reports an identity or digest mismatch, do not regenerate or overwrite the pack. Treat it as an integrity failure and identify the exact source, representation, or artifact layer involved.

## Level 4: Full Thesis-Grade Reproduction

Full encrypted reproduction is a multi-stage research protocol rather than a quick command. It requires:

- checkout of the execution commit named by the relevant manifest;
- a clean working tree and recorded binary digest;
- exact model, source, split, Direct Policy V2, and Security Policy V2 digests;
- sufficient disk and memory;
- no concurrent CKKS process during paired latency;
- stage ledgers, fresh-key accounting, and resumable atomic workloads;
- preservation of `REJECTED`, `FAILED`, `NO_SAFE`, and audit-negative results.

Read [`docs/research/step_7b8_final_confirmatory_suite.md`](research/step_7b8_final_confirmatory_suite.md) and the final-suite manifest before running an orchestrator. Runtime is host-dependent and can span many hours; no duration is promised by the project.

## External Datasets

Raw external datasets are not assumed to be redistributable merely because derived evidence is versioned.

- Tabular sources are bound through source metadata, OpenML identifiers, checksums, and deterministic materialization records.
- MNIST inputs are bound by [`datasets/journal_multiclass_extension_v1/mnist/input_split_manifest.json`](../datasets/journal_multiclass_extension_v1/mnist/input_split_manifest.json).
- Licensed external data and official submission templates should be fetched from their authoritative sources rather than copied into a public artifact export.

Validate every downloaded byte stream against its expected digest before materialization. The OpenML source replay distinguishes transport encoding from byte-identical decompressed content.

## Failure Handling

Scientific negative results lower the relevant claim but do not invalidate independent stages. Integrity failures are different:

| Condition | Required action |
|---|---|
| candidate `REJECTED`, `NO_SAFE`, or audit violation | preserve result and continue independent stages |
| parser, path, or report bug | repair the reporting layer and rerun the affected verifier |
| source, split, policy, security, or candidate mismatch | stop formal use of the affected evidence |
| frozen pack checksum mismatch | do not overwrite; investigate provenance |
| disk, OOM, or corruption risk | stop before artifact integrity is threatened |

The repository-level rule is claim-level fail-closed behavior with pipeline-level continuation.

## Public Export Hygiene

The development repository contains large and historical evidence, including materials that should not be copied into every public source bundle. The public-export policy in [`.github/public-export-manifest.json`](../.github/public-export-manifest.json) identifies exclusions such as official third-party forms, anonymous review content, large duplicate raw ledgers, generated binaries, and key material. Exclusion from a public export does not delete or rewrite frozen provenance.
