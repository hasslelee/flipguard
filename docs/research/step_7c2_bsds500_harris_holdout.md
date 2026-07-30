# Step 7C.2 BSDS500 Harris Non-Tabular Holdout

Status: `PREDECLARED_NOT_EVALUATED` on 2026-07-30. Source replay, plaintext
graph equivalence, static synthesis, Security V2 admission, and one-patch CKKS
smoke execution pass. No encrypted selection or locked-audit result is claimed
by this document.

## Research question

This extension asks whether the frozen synthesis constants, Security V2 gate,
bounded repairs, first-SAFE rule, and locked audit can be applied without
retuning to a deeper thresholded vision graph:

```text
Sxx = sum(Ix^2)
Syy = sum(Iy^2)
Sxy = sum(Ix*Iy)
R = Sxx*Syy - Sxy^2 - 0.04*(Sxx+Syy)^2
decision = R >= threshold
```

The graph follows the response introduced by Harris and Stephens, but the
evaluation unit is one 5x5 window. This is not a full corner detector: it does
not implement Gaussian weighting, non-maximum suppression, localization, or
BSDS boundary/corner accuracy.

Primary sources:

- Harris and Stephens, *A Combined Corner and Edge Detector*,
  DOI `10.5244/C.2.23`.
- Official BSDS500 release:
  `https://www2.eecs.berkeley.edu/Research/Projects/CS/vision/grouping/resources.html`.

## Frozen input protocol

Source archive:

```text
results/source_datasets/bsds500/BSR_bsds500.tgz
sha256:97e49d31764f3912f0c4122707d53062ac9e783ba0f095e447a4d53c1a41af8e
```

Extraction policy:

```text
ID: bsds500_harris_patch_extraction_v1
sha256:90befad9bdf9c58b817a54664348b421233e5834995a2648793024892b5cb291
```

Images and patch centers are chosen by domain-separated SHA-256 ranking and
streams. RGB is converted to normalized luma using:

```text
(299*R + 587*G + 114*B) / 255000
```

The official partition roles remain:

| Role | Images | Patches per image | Windows |
|---|---:|---:|---:|
| Train threshold calibration | 100 | 4 | 400 |
| Configuration validation | 50 | 4 | 200 |
| Locked audit test | 50 | 4 | 200 |

Images, not patches, are the statistical clusters. Validation and audit share
neither row IDs nor image IDs. Four windows per image keep the 25-ciphertext,
depth-2 encrypted cost bounded while retaining 50 distinct natural-image
clusters in each evaluated partition.

The application threshold is the nearest-rank 80th percentile of the 400
train-only Harris responses:

```text
threshold = 0.13363183503481268
```

Validation has 51 positive and 149 negative decisions. All 200 validation
windows are certifiable at the frozen `0.001` margin floor. Audit has 42
positive and 158 negative decisions; 199 are certifiable and one is ambiguous.
Audit distribution facts are descriptive only and are not used to alter the
candidate, repair, or policy.

## Graph adapter

The adapter ID is:

```text
bsds500_harris_square_rescale_graph_adapter_v1
```

It uses the exact identity:

```text
2ab = (a+b)^2 - a^2 - b^2
```

for `Ix*Iy` and `Sxx*Syy`. Every multiplication layer therefore uses the
existing `Pow2 -> relinearize -> rescale` primitive. This keeps the planner
scale trace and Lattigo execution path identical without changing the Direct
Policy primitive set.

Static graph facts:

| Property | Value |
|---|---:|
| Inputs | 25 scalar-replicated ciphertexts |
| Multiplicative depth | 2 |
| Rescale levels consumed | 4 |
| Terminal scale exponent | 2 |
| Required Q primes | 6 |
| Rotations | 0 |

The algebraic square-only path is exact in plaintext arithmetic. Tests compare
it to the direct Harris formula over the existing synthetic patterns. The CSV
loader independently recomputes every Harris response from the 25 pixels.

## Frozen policy boundary

Direct Policy V2 remains byte-identical:

```text
sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603
```

Security Policy V2 remains byte-identical:

```text
sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055
```

`harris_corner_response` is not added to the V2 supported-model table. The
adapter reuses the frozen alpha `0.5`, margin floor `0.001`, numerical repair
`+4` bits, level repair `+1` Q prime, maximum two added levels, maximum four
encrypted trials, first-SAFE rule, and NO_SAFE rule.

## Static plan

| Property | Value |
|---|---:|
| Validation samples / certifiable / ambiguous | 200 / 200 / 0 |
| Protected margin | 0.014321705839330248 |
| Alpha-margin error budget | 0.007160852919665124 |
| Initial candidate | `N13 / Q6 / scale26` |
| LogQ / LogP / LogQP | 165 / 35 / 200 |
| Security V2 cap / headroom | 214 / 14 bits |

Candidate:

```text
synth_analysis_minimum_rescale_N13_Q6_S26_b9a6f9573340
```

The one-row diagnostic CKKS smoke test completes at final degree one and a
nonnegative remaining level. Static feasibility and smoke success are not
decision-integrity evidence.

## Encrypted protocol

Configuration validation:

1. Execute at most four literal candidates.
2. Evaluate all 200 validation windows under three fresh keys per trial.
3. Persist every patch-by-key score, error, budget use, flip, and violation.
4. Apply only the frozen failure classifier and monotone repair.
5. Stop at the first SAFE candidate or return NO_SAFE.

Locked audit:

1. Verify the selection, model, source archive, extraction policy, validation
   digest, and selected literal.
2. Verify row and image disjointness.
3. Replay the byte-identical selected literal on all 200 test windows under
   three new keys.
4. Never invoke synthesis or repair.
5. Preserve SAFE, REJECTED, FAILED, or ambiguous outcomes without retuning.

Success supports only this scalar-replicated single-window Harris graph over
the declared BSDS500 extraction. It does not support arbitrary graphs, packed
full-image execution, CNNs, or universal autotuning.

## Reproduction

```bash
python3 scripts/export_bsds500_harris_holdout.py --verify
python3 scripts/verify_bsds500_harris_holdout.py --source-replay

go run ./cmd/flipguard-harris-autotune \
  --model datasets/vision_suite/bsds500/harris_corner_response/model.json \
  --validation datasets/vision_suite/bsds500/harris_corner_response/configuration_validation.csv \
  --source-archive results/source_datasets/bsds500/BSR_bsds500.tgz \
  --split-id bsds500/train_threshold_val_selection_test_audit_harris_v1 \
  --out results/thesis_grade_protocol/non_tabular_harris_holdout_v1/selection.json

go run ./cmd/flipguard-harris-audit \
  --selection results/thesis_grade_protocol/non_tabular_harris_holdout_v1/selection.json \
  --audit datasets/vision_suite/bsds500/harris_corner_response/locked_audit_test.csv \
  --source-archive results/source_datasets/bsds500/BSR_bsds500.tgz \
  --extraction-manifest datasets/vision_suite/bsds500/harris_corner_response/extraction_manifest.json \
  --out results/thesis_grade_protocol/non_tabular_harris_holdout_v1/locked_audit.json
```
