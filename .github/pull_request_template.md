## Summary

Describe the problem and the smallest complete change.

## Change Class

- [ ] Execution-critical
- [ ] Evidence
- [ ] Interpretation/reporting
- [ ] Documentation
- [ ] Verification/CI

## Research Integrity

- [ ] I identified whether execution semantics change.
- [ ] I did not overwrite a frozen evidence pack.
- [ ] I did not retune Direct Policy V2 or Security Policy V2 from confirmatory/audit results.
- [ ] I preserved scientific negative results.
- [ ] I used formal Security-V2 catalog denominators and scoped claim wording.
- [ ] New evidence, if any, binds source, binary, model, input, split, policy, and candidate identities.

Execution-semantics impact:

Frozen-evidence impact:

## Verification

- [ ] `go test ./...`
- [ ] `go vet ./...`
- [ ] relevant Python tests and `py_compile`
- [ ] relevant shell `bash -n`
- [ ] `git diff --check`
- [ ] pack-local verifier, if evidence changed
- [ ] public README/claim lint, if documentation changed

List exact commands and important outputs:

## Claim and Security Impact

State any affected claim ID, security policy/model qualification, limitation, and prohibited overclaim. Write `none` when the change is operational only.
