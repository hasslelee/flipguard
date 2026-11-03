# Final Realistic Baseline Closure V9

- Completion state: `FINAL_BASELINE_V8_SUFFICIENT_OPTIONALS_BLOCKED`
- Direct repeat classification: `F4_NEAR_BOUNDARY_AMBIGUITY` (8 flips, 1 unique input, no replay)
- P1: `BLOCKED_UNSTABLE_ARM`
- P2: `BLOCKED_UNSTABLE_ARM`
- P3: `PAPER_ADMITTED`, ratio 6.393517, 95% CI [6.361222, 6.427118]
- HECATE: `HECATE_PAPER_BASELINE_ONLY`, 0 plans attempted
- Orion: 10-input official encrypted self-test PASS with 0 flips; full trained-model extension blocked because no official trained MLP weights are distributed
- External comparison manuscript readiness: `true`
- Repository-wide paper flag: unchanged

## Verification

- `go test ./...`: PASS after isolating the ignored HEIR/Bazel build cache from the root Go module
- `go vet ./...`: PASS
- Python unittest: 349 tests PASS in 1,994.372 seconds
- Python bytecode compilation: PASS with bytecode redirected outside frozen evidence trees
- V7, V8, direct-forensic, and V9 deterministic verifiers: PASS
- V9 evidence checksums: PASS
- V9 publication-input checksums and SVG parsing: PASS

## Recovery record

- The first root Go test traversed ignored HEIR/Bazel Go-toolchain test fixtures and failed outside FlipGuard packages. A local untracked nested-module boundary isolated that cache; the unchanged root command then passed.
- Orion attempt 1 failed on Python 3.12/Torch Dynamo compatibility before encrypted inference.
- Orion attempt 2 failed because the isolated Python 3.11 image lacked the `git` provenance executable.
- Orion attempt 3 completed actual keygen, encryption, evaluation, decryption, and ten-logit extraction.

## Remaining manuscript risks

- P1 and P2 are not admissible repeated-stability claims because the direct arm flips on one declared ambiguous input.
- P3 covers one exact shared polynomial and one measured host.
- HECATE has no separately invocable official mode in the pinned artifact.
- Orion full trained-model validation/audit is blocked by absent official trained MLP weights.
- Native-runtime timings remain non-comparable as raw speed rankings.

- Next action: rewrite the manuscript using only `final_claim_admission.json` and the V9 publication inputs
- Run disposition: `PAUSE_FOR_FINAL_MANUSCRIPT_REWRITE`
