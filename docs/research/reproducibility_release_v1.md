# FlipGuard Reproducibility Release Candidate

## Scope

The release candidate verifies the already frozen FlipGuard evidence and
rebuilds the V3 publication inputs. It does not execute CKKS workloads, create
keys, collect latency, retune Direct Policy V2, or retune Security Policy V2.

The archive contains every file tracked by the bound source commit, plus a
deterministic archive manifest and environment record. It includes source,
policies, protocol documents, frozen evidence, verifiers, and paper artifacts
V3.

## External Data

Raw MNIST and BSDS500 archives are not redistributed. Their source URLs,
expected SHA-256 values, extraction scripts, and derived-artifact manifests
are recorded in `release/external_sources_v1.json`.

Fetch and checksum verification are explicit:

```bash
python3 scripts/fetch_release_external_sources.py --dataset BSDS500
python3 scripts/fetch_release_external_sources.py --dataset MNIST_OPENML_554
```

The MNIST fetch requests and preserves OpenML's gzip response byte-for-byte;
it verifies both the compressed container and the decompressed ARFF content.
It does not locally recompress the transport payload.

Downloading is not necessary to verify the frozen evidence because the
release contains the bound derived artifacts and their manifests.

## Frozen Verification

From the repository root:

```bash
python3 scripts/bind_eva_selected_exact_materialization_v1.py --verify
python3 scripts/verify_margin_utilization_interpretation_v1.py
python3 scripts/verify_paired_latency_claim_admission_v1.py
python3 scripts/verify_paper_claim_admission.py
python3 scripts/verify_flipguard_v3_paper_artifacts.py --rebuild
```

The clean-clone release verifier checks a detached checkout of the exact
source commit, runs the static verifiers, rebuilds the archive, compares its
digest, and validates the internal `SHA256SUMS`.

Historical freezer modes that insist on ignored `results/` source paths are
not represented as clean-clone source replays. The release verifies their
frozen snapshot checksums and manifest file bindings instead. This distinction
prevents an omitted local working ledger from being confused with corrupted
frozen evidence. The exact EVA materialization replay is also an auxiliary
check and is recorded separately from the core clean-clone gate.

## Exclusions

The following are intentionally excluded from the release archive:

- `.git/` repository metadata;
- ignored raw source archives under `results/source_datasets/`;
- ignored working ledgers and duplicate experiment outputs under `results/`;
- caches, temporary files, local virtual environments, and `dist/`.

Tracked frozen evidence under `docs/evidence/` and tracked V3 publication
inputs under `results/thesis_grade_protocol/paper_artifacts_v3/final/` remain
included.

## Publication Boundary

The release only admits claims listed with `paper_admitted=true` in
`docs/evidence/paper_claim_admission_v1/claims.json`. Provider and EVA evidence
is appendix-only. Cross-runtime numerical equivalence, arbitrary packed CNN
support, universal security, and global optimality are not admitted.
