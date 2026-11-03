# V9 Manuscript Change Map

## Required replacements

- Replace the single blocked common-executor latency claim with three independently audited pairs. P1 and P2 remain blocked because the direct arm flips on one `V_amb` input; P3 is admitted.
- State that the eight direct measurement flips are four passes across three keysets for one near-boundary input, not eight independent failed inputs.
- Preserve the original zero-flip finite `V_cert` locked audit while excluding repeated-stability claims for `V_amb`.
- Present CoreLab EVA/ELASM as a numerical error-latency plan grid, not a decision-bearing provider panel.
- Keep HECATE as an official-paper baseline because the pinned artifact exposes no standalone HECATE mode.
- Describe Orion only as a successful ten-input official untrained self-test; do not present it as a trained-model baseline.
- Report the direct trial distribution once: 50 instances, 70 trials, mean 1.4, median 1, IQR 1, maximum 2, 30 one-trial, 20 two-trial, and 20 repaired instances.

## Admitted common-executor sentence

On the exact shared polynomial and common Lattigo v6.2.0 executor, the Security-V2 bounded-catalog total latency divided by HEIR-generated total latency had a geometric mean of 6.393517 (cluster-bootstrap 95% CI [6.361222, 6.427118]) over 100 frozen input clusters and 1,800 paired measurements.

## Scope sentence

The result is limited to one exact shared workload, its frozen inputs, one host, and Security-V2-aligned Lattigo candidates; it does not establish HEIR as globally optimal or universally faster.
