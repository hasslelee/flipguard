# FlipGuard

**Decision-Stability-Aware Error-Budgeted Precision Scheduling for CKKS-Based Encrypted Inference**

FlipGuard is a research prototype for studying **decision-stability-aware precision scheduling** in CKKS-based encrypted inference.

The project explores how node-wise precision budgets can be allocated so that threshold-based decisions remain stable under approximation errors.

> Status: research prototype. The current implementation uses a plain simulation backend. A real CKKS backend will be added in later stages.

---

# English

## 1. Overview

CKKS supports approximate arithmetic over encrypted real-valued data. This makes it attractive for privacy-preserving inference, but approximation errors can change the final decision when the model output is close to a decision threshold.

For a threshold-based inference rule:

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

## 2. Key Features

FlipGuard currently provides:

- Computation graph IR for small encrypted-inference workloads
- Plain evaluator
- Quantized plain evaluator
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

## 3. Current Experiment

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

## 4. Quick Start

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

## 5. Output Files

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

## 6. Current Key Result

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

## 7. Interpretation

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

## 8. Repository Structure

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

## 9. Documentation

- [Roadmap](docs/ROADMAP.md)
- [Current logreg_small result](docs/RESULTS_LOGREG_SMALL.md)
- [Development notes](docs/DEVELOPMENT.md)

## 10. Research Direction

Working title:

```text
FlipGuard: Decision-Stability-Aware Error-Budgeted Precision Scheduling for CKKS-Based Encrypted Inference
```

## 11. Citation

A formal citation entry will be added after the first technical report or paper draft is released.

For now, please cite the repository as:

```text
Lee, G. FlipGuard: Decision-Stability-Aware Error-Budgeted Precision Scheduling for CKKS-Based Encrypted Inference. Research prototype, 2026.
```

## 12. License

This repository is currently a research prototype. A license will be added later.

---

# 한국어

## 1. 개요

FlipGuard는 CKKS 기반 암호화 추론에서 **판정 안정성(decision stability)** 을 고려한 정밀도 스케줄링을 연구하기 위한 프로토타입입니다.

CKKS는 암호화된 실수 데이터에 대해 근사 연산을 수행할 수 있다는 장점이 있지만, 근사 오차로 인해 모델 출력값이 임계값 근처에 있을 때 최종 판정이 뒤집힐 수 있습니다.

예를 들어 다음과 같은 임계값 기반 추론 규칙이 있다고 가정합니다.

```text
decision = 1 if f(x) >= T
decision = 0 otherwise
```

이때 `f(x)`가 임계값 `T`에 가까우면 작은 근사 오차만으로도 최종 판정이 바뀔 수 있습니다. 본 연구에서는 이를 **decision flip**, 즉 판정 뒤집힘 문제로 다룹니다.

FlipGuard는 이 문제를 정밀도 스케줄링 문제로 바라봅니다. 단순히 평균 출력 오차를 줄이는 것이 아니라, 다음과 같은 decision-margin-aware 충분조건을 이용합니다.

```text
estimated_error <= safety_factor * protected_margin
```

여기서 `protected_margin`은 평문 기준 출력값과 판정 임계값 사이의 거리에서 유도됩니다.

## 2. 주요 기능

현재 FlipGuard에는 다음 기능이 구현되어 있습니다.

- 소규모 암호화 추론 workload를 위한 계산 그래프 IR
- 평문 evaluator
- quantized plain evaluator
- boundary-focused sample 생성
- decision flip, boundary, ambiguous sample 분석
- interval-based sensitivity analysis
- uniform precision baseline
- accuracy-only scheduler baseline
- FlipGuard decision-margin-aware scheduler
- decision certification metric
- precision saving metric
- bound conservatism metric
- CSV 및 Markdown 결과 export
- 현재 benchmark 재현 스크립트
- CLI experiment selector

## 3. 현재 실험

현재 기본 실험은 다음과 같습니다.

```text
logreg_small
```

이 실험은 작은 logistic-style polynomial inference 그래프를 사용합니다.

```text
z = 0.8*x1 - 0.5*x2 + 1.2*x3 - 0.3
y = 0.5 + 0.197*z - 0.004*z^3
T = 0.5
```

비교 대상은 다음과 같습니다.

- `uniform_bits_*`
- `accuracy_only_*`
- `flipguard_*`

## 4. 빠른 실행 방법

### 요구사항

- Go 1.25 이상
- Linux 환경 권장

### 실험 목록 확인

```bash
go run ./cmd/flipguard -list
```

### 기본 실험 실행

```bash
go run ./cmd/flipguard
```

### `logreg_small` 실험 실행

```bash
go run ./cmd/flipguard -experiment logreg_small
```

### 테스트 실행

```bash
go test ./...
```

### 현재 결과 재현

```bash
./scripts/run_logreg_small.sh
```

## 5. 출력 파일

`logreg_small` 실험을 실행하면 다음 경로에 결과 파일이 생성됩니다.

```text
results/logreg_small/
```

주요 생성 파일은 다음과 같습니다.

```text
summary.csv
report.md
paper_table.md
schedule_*.csv
records_*.csv
```

생성된 결과 파일은 Git에 포함하지 않도록 설정되어 있습니다.

## 6. 현재 핵심 결과

현재 `logreg_small` benchmark에서 FlipGuard는 다음과 같은 예비 결과를 보입니다.

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

논문 표에 바로 옮길 수 있는 결과표는 다음 경로에 생성됩니다.

```text
results/logreg_small/paper_table.md
```

현재 결과에 대한 상세 요약은 다음 문서에 정리되어 있습니다.

```text
docs/RESULTS_LOGREG_SMALL.md
```

## 7. 결과 해석

현재 프로토타입은 완성된 CKKS 컴파일러라고 주장하지 않습니다.

현재 결과는 다음과 같은 제한된 예비 주장을 뒷받침합니다.

```text
FlipGuard는 통제된 시뮬레이션 환경에서 stable boundary sample에 대한
decision-margin certification을 만족하면서 평균 scheduled precision을 줄일 수 있다.
```

다음 개발 단계는 다음과 같습니다.

1. 더 큰 synthetic workload 추가
2. 실제 tabular inference workload 추가
3. Lattigo 기반 CKKS backend 추가
4. runtime, level consumption, rescale-chain behavior 측정
5. 더 강한 CKKS scheduling baseline과 비교

## 8. 저장소 구조

```text
cmd/flipguard/
  CLI 진입점

internal/ir/
  계산 그래프 표현

internal/runtime/
  평문 및 quantized evaluator

internal/analysis/
  decision analysis, boundary analysis, interval sensitivity analysis

internal/scheduler/
  uniform, accuracy-only, FlipGuard scheduling logic

internal/benchmarks/
  benchmark graph 및 sample generator

internal/experiment/
  experiment runner 및 experiment configuration

internal/report/
  CSV 및 Markdown report 생성

scripts/
  재현성 스크립트

docs/
  연구 노트, 결과 요약, 로드맵

results/
  생성된 실험 결과 파일
```

## 9. 문서

- [로드맵](docs/ROADMAP.md)
- [현재 logreg_small 결과](docs/RESULTS_LOGREG_SMALL.md)
- [개발 노트](docs/DEVELOPMENT.md)

## 10. 연구 방향

영문 제목 초안은 다음과 같습니다.

```text
FlipGuard: Decision-Stability-Aware Error-Budgeted Precision Scheduling for CKKS-Based Encrypted Inference
```

국문 제목 초안은 다음과 같습니다.

```text
FlipGuard: CKKS 기반 암호화 추론의 판정 안정성 보장을 위한 오차 예산 기반 정밀도 스케줄링 기법
```

## 11. 인용

첫 번째 기술보고서 또는 논문 초안이 공개된 이후 정식 citation entry를 추가할 예정입니다.

현재는 다음과 같이 인용할 수 있습니다.

```text
Lee, G. FlipGuard: Decision-Stability-Aware Error-Budgeted Precision Scheduling for CKKS-Based Encrypted Inference. Research prototype, 2026.
```

## 12. 라이선스

현재 이 저장소는 연구 프로토타입 단계입니다. 라이선스는 추후 추가할 예정입니다.