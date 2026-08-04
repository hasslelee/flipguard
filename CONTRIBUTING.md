# Contributing to FlipGuard

Thank you for improving FlipGuard. This repository is both software and a versioned research artifact, so changes must preserve reproducibility and claim boundaries.

## Development Setup

```bash
git clone https://github.com/hasslelee/flipguard.git
cd flipguard
go mod download
python3 -m pip install --requirement requirements-ci.txt
```

The Go version is declared in `go.mod`. Do not silently upgrade Go, Lattigo, policy files, model artifacts, or source datasets in an unrelated pull request.

## Choose a Change Class

Every pull request should identify one class:

- **execution-critical:** changes candidate generation, certification, CKKS execution, graph semantics, security admission, or audit behavior;
- **evidence:** adds a new immutable result pack produced by a frozen protocol;
- **interpretation:** derives a new summary or claim overlay from frozen records;
- **documentation:** changes public explanation without changing research semantics;
- **verification:** strengthens tests, schemas, provenance checks, or deterministic rebuilds.

If a change crosses classes, separate it into logical commits and explain the dependency.

## Research Evidence Rules

- Never overwrite a frozen evidence pack. Add a versioned successor or overlay.
- Preserve `REJECTED`, `FAILED`, `NO_SAFE`, and locked-audit negative results.
- Never retune Direct Policy V2 or Security Policy V2 from confirmatory or audit outcomes.
- Do not move audit samples into validation or select a policy from locked-audit performance.
- Distinguish source, prepared, semantic, model, split, policy, binary, and candidate identities.
- Use only Security-V2-admitted profiles in formal bounded-catalog denominators.
- Call the comparison a bounded-catalog fastest-safe result, not a global optimum.
- Report seed 0 separately from post-freeze confirmatory seeds 1–4.
- Add a falsification condition before new research execution.

## Code and Tests

Use the repository's existing package boundaries and structured formats. Run focused tests while developing and the following gate before requesting review:

```bash
go test ./...
go vet ./...
python3 -m unittest scripts.tests.test_lint_public_readme
python3 scripts/lint_public_readme.py
python3 -m py_compile scripts/lint_public_readme.py
git diff --check
```

For shell changes, run `bash -n` on every modified shell script. For an evidence change, run the pack-local verifier and `sha256sum --check SHA256SUMS` from the directory expected by that pack.

## Documentation and Claims

Public prose must follow [`docs/CLAIM_SCOPE.md`](docs/CLAIM_SCOPE.md) and the canonical claim registries. Keep binary threshold theorem wording separate from the operational `rho=0.5` reserve policy. Preserve formal denominators, negative results, security qualifications, and the one-host latency scope.

English and Korean root READMEs must keep the same section order, commands, headline numbers, and limitations. Run the public README linter after changing either file.

## Pull Requests

1. Open an issue for substantial research-semantic changes before implementation.
2. Branch from the intended frozen or development baseline; do not rewrite shared history.
3. Keep commits logical and avoid generated or unrelated metadata churn.
4. Fill in the pull request template, including execution-semantics and frozen-evidence declarations.
5. Wait for CI and artifact verification to pass.

Reviewers may require a new protocol and source freeze before accepting an execution-critical change. A scientific negative result is acceptable; missing or ambiguous provenance is not.

## Reporting Security Issues

Do not include secrets, raw key material, or exploit details in a public issue. Follow [`SECURITY.md`](SECURITY.md).
