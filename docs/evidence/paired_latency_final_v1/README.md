# FlipGuard Paired Selected-Literal Latency Evidence

- Mode: `FINAL`
- Workloads: `50`
- Raw measured records: `5400`
- Decision flips: `0`
- Primary catalog/direct total ratio:
  `3.141755`
- 95% workload-bootstrap interval:
  `[2.347031, 4.215680]`
- Paper latency claim: `not allowed from this evidence`

The inference unit is one workload. Raw repeated timings are not treated as
independent workload samples. The catalog comparison is bounded to the
declared candidate space.

Verify copied files, all external input bindings, every three-arm pairing,
the final balanced order, flip accounting, and independently recomputed
workload-level estimates with:

```bash
python3 scripts/freeze_paired_latency_evidence.py \
  --output-root docs/evidence/paired_latency_final_v1 \
  --verify
```
