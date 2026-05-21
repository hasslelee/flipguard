# FlipGuard

**Decision-Stability-Aware Error-Budgeted Precision Scheduling for CKKS-Based Encrypted Inference**

FlipGuard is a research prototype for studying **decision-stability-aware precision scheduling** in CKKS-based encrypted inference.  
The project explores how node-wise precision budgets can be allocated so that threshold-based decisions remain stable under approximation errors.

> Status: research prototype. The current implementation is a plain simulation backend; a real CKKS backend will be added in later stages.

---

## Overview

CKKS supports approximate arithmetic over encrypted real-valued data. This makes it attractive for privacy-preserving inference, but approximation errors can change the final decision when the model output is close to a decision threshold.

For a threshold-based inference rule,

```text
decision = 1 if f(x) >= T
decision = 0 otherwise
```

a small approximation error may cause a **decision flip** when `f(x)` is close to `T`.

FlipGuard treats this problem as a precision scheduling problem. Instead of only minimizing average output error, FlipGuard uses a decision-margin-aware sufficient condition:

```text
estimated_error <= safety_factor * protected_margin
```

where `protected_margin` is derived from the distance between the plaintext score and the decision threshold.

---

## 핵심 개요

FlipGuard는 CKKS 기반 암호화 추론에서 **판정 안정성(decision stability)** 을 고려한 정밀도 스케줄링을 연구하기 위한 프로토타입입니다.

CKKS는 실수 기반 근사 연산을 지원하지만, 모델 출력이 임계값 근처에 있을 경우 작은 근사 오차만으로도 최종 판정이 바뀔 수 있습니다. FlipGuard는 이러한 **판정 뒤집힘(decision flip)** 문제를 줄이기 위해, 각 중간 연산 노드에 필요한 정밀도를 decision margin에 따라 다르게 배정합니다.

현재 구현은 실제 CKKS 암호문 연산이 아니라, 연구 아이디어를 검증하기 위한 **평문 기반 정밀도 시뮬레이션 단계**입니다.

---

## Key Features

- Computation graph IR for small encrypted-inference workloads
- Plain and quantized evaluators
- Boundary-focused sample generation
- Decision flip, boundary, and ambiguous sample analysis
- Interval-based sensitivity analysis
- Uniform precision baselines
- Accuracy-only scheduler baselines
- FlipGuard decision-margin-aware scheduler
- Decision certification metrics
- Precision saving metrics
- Bound conservatism metrics
- CSV and Markdown result export
- Reproducibility script for the current benchmark
- CLI experiment selector

---

## Current Experiment

The current default experiment is:

```text
logreg_small
```

It uses a small logistic-style polynomial inference graph:

```text
z = 0.8*x1 - 0.5*x2 + 1.2*x3 - 0.3
y = 0.5 + 0.197*z - 0.004*z^3
T = 0.5
```

Compared methods:

- `uniform_bits_*`
- `accuracy_only_*`
- `flipguard_*`

---

## Quick Start

### Requirements

- Go 1.25 or later
- Linux environment recommended

### List experiments

```bash
go run ./cmd/flipguard -list
```

### Run the default experiment

```bash
go run ./cmd/flipguard
```

### Run `logreg_small`

```bash
go run ./cmd/flipguard -experiment logreg_small
```

### Run tests

```bash
go test ./...
```

### Reproduce current results

```bash
./scripts/run_logreg_small.sh
```

---

## Output Files

Running the `logreg_small` experiment generates files under:

```text
results/logreg_small/
```

Main generated files:

```text
summary.csv
report.md
paper_table.md
schedule_*.csv
records_*.csv
```

Generated result files are intentionally ignored by Git.

---

## Current Key Result

In the current `logreg_small` benchmark, FlipGuard shows the following preliminary behavior:

```text
flipguard_p5_m12:
  stable boundary flips = 0
  p5 certification = true
  average bits = 9.09
  saving vs uniform_bits_12 = 24.24%

flipguard_p1_m16:
  stable boundary flips = 0
  p5 + p1 certification = true
  average bits = 11.36
  saving vs uniform_bits_16 = 28.98%
```

The paper-ready table is generated at:

```text
results/logreg_small/paper_table.md
```

A detailed summary of the current result is maintained in:

```text
docs/RESULTS_LOGREG_SMALL.md
```

---

## Interpretation

The current prototype does **not** claim to be a complete CKKS compiler.

The current result supports a narrower preliminary claim:

```text
FlipGuard can reduce average scheduled precision while satisfying
decision-margin certification on stable boundary samples in a controlled simulation setting.
```

The next development stages are:

1. Add larger synthetic workloads.
2. Add real tabular inference workloads.
3. Add a Lattigo-based CKKS backend.
4. Measure runtime, level consumption, and rescale-chain behavior.
5. Compare against stronger CKKS scheduling baselines.

---

## Repository Structure

```text
cmd/flipguard/
  CLI entry point

internal/ir/
  Computation graph representation

internal/runtime/
  Plain and quantized evaluators

internal/analysis/
  Decision analysis, boundary analysis, interval sensitivity analysis

internal/scheduler/
  Uniform, accuracy-only, and FlipGuard scheduling logic

internal/benchmarks/
  Benchmark graph and sample generators

internal/experiment/
  Experiment runners and experiment configuration

internal/report/
  CSV and Markdown report generation

scripts/
  Reproducibility scripts

docs/
  Research notes, result summaries, and roadmap

results/
  Generated experiment outputs
```

---

## Documentation

- [Roadmap](docs/ROADMAP.md)
- [Current logreg_small result](docs/RESULTS_LOGREG_SMALL.md)
- [Development notes](docs/DEVELOPMENT.md)

---

## Research Direction

Working title:

```text
FlipGuard: Decision-Stability-Aware Error-Budgeted Precision Scheduling for CKKS-Based Encrypted Inference
```

Korean title draft:

```text
FlipGuard: CKKS 기반 암호화 추론의 판정 안정성 보장을 위한 오차 예산 기반 정밀도 스케줄링 기법
```

---

## Citation

A formal citation entry will be added after the first technical report or paper draft is released.

For now, please cite the repository as:

```text
Lee, G. FlipGuard: Decision-Stability-Aware Error-Budgeted Precision Scheduling for CKKS-Based Encrypted Inference. Research prototype, 2026.
```

---

## License

This repository is currently a research prototype. A license will be added later.