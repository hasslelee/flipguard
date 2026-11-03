# V18 Comparison Extension Pre-flight

- Generated (UTC): `2026-08-23T20:24:20.449749+00:00`
- Branch: `research/comparison-extension-v18`
- HEAD: `86b0403208abbc741a65934358a5dea4a66e4d88`
- Scientific execution source commit: `cefc44b0d7e351db2a34886dd758a2d31a3e4c12`
- Post-run aggregation/tooling commit: `86b0403208abbc741a65934358a5dea4a66e4d88`
- Inventory: `4201` files, `1924200265` bytes
- Missing declared inputs: `0`
- Existing untracked/user files preserved: `65` status rows
- V17 writes performed: `0`
- Encrypted executions performed: `0`

## Locked Counts

- V17 matrix: `204/204`
- Formal latency: `68/68`
- Scientific recomputation: `489/489 PASS`
- Latency reconstruction: `15/15 PASS`

## Protection Rule

V18 reads the paths bound in `input_binding.json` by path and SHA-256. It does
not symlink, import completion markers, rewrite V17 manifests, or regenerate
V17 tables. All derived outputs remain under the V18 checkpoint, evidence,
report, and result roots.
