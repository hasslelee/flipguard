# FlipGuard Research Release Binding RC2

This immutable overlay binds the authoritative thesis source to the RC2
reproducibility release without modifying V10 or RC1.

- V10 is the core-completion checkpoint created with the RC1-era release
  binding.
- RC1 remains an immutable predecessor.
- RC2 changes no claim, encrypted result, Direct Policy V2, Security Policy
  V2, or Paper Artifacts V3 content.
- RC2 repairs the release transport by preserving OpenML's server-provided
  gzip stream byte-for-byte and by binding versioned archive identifiers.
- The thesis and reproduction guide use RC2 as their final distribution
  baseline.
- New encrypted executions: `0`.
- Policy retuning: `0`.

Verification checks the RC1-to-RC2 changed-path allowlist, Git tag identities,
V10/V3/claim manifest digests, pack checksums, and the RC2 archive when it is
available or explicitly supplied.

```bash
python3 docs/evidence/research_release_binding_rc2_v1/verify_research_release_binding_rc2.py \
  --archive dist/flipguard-thesis-artifact-v1.0.0-rc2.tar.zst
```
