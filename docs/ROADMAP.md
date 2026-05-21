# FlipGuard Roadmap

This document tracks the planned development stages of FlipGuard.

---

## Stage 1. Plain Simulation Prototype

Status: in progress.

Goals:

- Define a small computation graph IR.
- Implement plain and quantized evaluators.
- Generate boundary-focused samples.
- Measure decision flips and boundary-zone behavior.
- Implement interval-based sensitivity analysis.
- Implement the first FlipGuard precision scheduler.
- Compare against uniform and accuracy-only baselines.
- Export reproducible CSV and Markdown reports.

Current status:

- Basic prototype implemented.
- `logreg_small` experiment is reproducible through `scripts/run_logreg_small.sh`.

---

## Stage 2. Larger Plain Workloads

Status: planned.

Goals:

- Add larger synthetic polynomial inference workloads.
- Add multi-layer polynomial models.
- Add multiple thresholds and multi-output decision rules.
- Stress-test decision-margin certification under different boundary distributions.
- Add ablation studies for:
  - margin floor
  - safety factor
  - protected percentile
  - max precision bits
  - boundary-zone width

---

## Stage 3. Real Dataset Simulation

Status: planned.

Goals:

- Add tabular classification workloads.
- Use real or public datasets for threshold-based inference.
- Train small models outside the encrypted backend.
- Export polynomial approximation graphs for inference.
- Compare decision flip behavior across datasets.

Candidate workloads:

- credit-risk style binary classification
- fraud-detection style binary classification
- medical-risk style threshold inference

The repository should remain domain-general. Financial datasets may be used as evaluation workloads, but the core method targets CKKS-based encrypted inference in general.

---

## Stage 4. CKKS Backend

Status: planned.

Goals:

- Add a Lattigo-based CKKS execution backend.
- Map scheduled precision to CKKS scale and rescale choices.
- Measure:
  - runtime
  - level consumption
  - output error
  - decision flip rate
  - stable-boundary flip rate
  - certification success
- Compare simulation-level estimates with CKKS-observed errors.

---

## Stage 5. Paper-Ready Evaluation

Status: planned.

Goals:

- Build paper-ready tables and figures.
- Compare FlipGuard against:
  - uniform precision baselines
  - accuracy-only scheduling
  - CKKS compiler-inspired scale management baselines
- Report:
  - stable boundary flips
  - certification usage
  - precision saving
  - bound conservatism
  - runtime and level consumption
- Prepare a domestic conference paper first.
- Extend toward an international workshop submission if results remain strong.

---

## Stage 6. Packaging and Artifact

Status: planned.

Goals:

- Add a stable command-line interface.
- Add configuration files for experiments.
- Add artifact reproduction instructions.
- Add a license.
- Add citation metadata.
- Add versioned result snapshots.