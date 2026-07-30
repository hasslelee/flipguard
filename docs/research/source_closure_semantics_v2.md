# Source Closure Semantics V2

Status: implemented for future artifacts only. This protocol does not
reinterpret or modify any frozen evidence. `paper_claim_allowed=false`.

## Motivation

Several historical runners bound every tracked Go file below `cmd/` and
`internal/` as execution-critical source. That conservative rule also included
`_test.go` files that cannot enter a default Go binary. As a result, an
assurance-only test change could invalidate an otherwise byte-identical build
closure.

## Three Separate Bindings

1. **Execution-critical closure**: source files selected by `go list -deps
   -json` for declared entrypoints under the active default build constraints,
   plus explicitly declared orchestration scripts and policy inputs.
2. **Comparison/report closure**: explicitly declared comparator, freezer,
   verifier, and report-builder files.
3. **Repository-assurance closure**: tracked implementation, tests, workflows,
   and research-support source. This closure records `_test.go` changes without
   claiming that they alter an already built execution binary.

Each layer has a separate canonical SHA-256 digest. Binary digests, policy
digests, input digests, and candidate identities remain separate required
bindings.

## Non-Retroactivity

V1 source closures in frozen evidence retain their original meaning. Source
Closure V2 is used only by future manifests that explicitly declare schema
`flipguard_source_closure_v2`. It does not make an older run reproducible under
a newer source tree and does not authorize encrypted-evidence reuse when the
actual V2 execution closure changes.

## Fail-Closed Rules

- Every bound file must be tracked and inside the repository.
- Generation requires a clean working tree.
- At least one Go entrypoint is required.
- Default-build files are taken from the Go toolchain, not filename heuristics.
- Orchestrators, policy inputs, and comparison sources must be explicit.
- Existing manifests are never overwritten.
- A changed execution-critical digest blocks reuse of affected execution
  evidence; a comparison-only change requires comparison re-verification but
  does not by itself invalidate the frozen binary.
