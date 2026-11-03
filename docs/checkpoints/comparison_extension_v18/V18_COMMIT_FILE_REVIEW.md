# V18 Local Commit File Review

Decision: `APPROVED_FOR_SINGLE_LOCAL_COMMIT`

## Purpose

The commit binds the deterministic V18 comparison replay, its frozen protocol,
the 43-file package selected by the immutable V18 manifest, and the small
manuscript-facing locked-facts overlay. It does not change or rebind any V17 or
V18 scientific result.

## Included classes

1. The exact 43 files listed in the V18 package manifest. These include the
   preflight input inventory, replay source, protocol, compact derived ledgers,
   figures/tables as CSV, and final reports required by the package verifier.
2. The V18 `manifest.json` and `SHA256SUMS` that bind those 43 files.
3. The locked paper-facts JSON/Markdown and four case-level comparison tables.
4. Deterministic paper-facts and PRIMARY-68 inventory builders/verifiers.
5. The exact PRIMARY-68 case inventory and its unit-definition report.
6. This review and the literal approved path list.

## Explicit exclusions

- V17 raw encrypted results, keyset records, recovery originals, and large run
  directories.
- Any modified V17 final evidence or frozen protocol.
- Existing DOCX, PDF, PPTX, HWP, ZIP, and user-edited manuscript files.
- Unrelated audit/checkpoint directories.
- Python environments, caches, bytecode, build trees, and external artifacts.
- Any commit, push, tag, or history rewrite outside the one approved local
  commit.

## Scientific and publication integrity

- Scientific execution source remains
  `cefc44b0d7e351db2a34886dd758a2d31a3e4c12`.
- Post-run aggregation/tooling predecessor remains
  `86b0403208abbc741a65934358a5dea4a66e4d88`.
- V18 package payload remains
  `884d979087b62a1f4e2ca066902f4deb603589dbff6fd5349c57bead5539aded`.
- New encrypted candidate evaluations remain zero.
- `git_add_v18_comparison.txt` is the complete stage allowlist; no directory
  wildcard is permitted.

## Stage acceptance rules

Before commit, the staged paths must equal the allowlist byte-for-byte, contain
no cache or manuscript binary, and pass `git diff --cached --check`. The full
Go, Python, shell, V17 R3, V18, paper-facts, PRIMARY-68, and deterministic
rebuild gates must pass before the local commit is created.
