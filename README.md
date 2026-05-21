# FlipGuard

FlipGuard is a research prototype for **decision-stability-aware precision scheduling** in CKKS-based encrypted inference.

FlipGuard는 CKKS 기반 암호화 추론에서 **판정 안정성(decision stability)을 고려한 정밀도 스케줄링**을 연구하기 위한 프로토타입입니다.

---

## 1. Overview

The central idea is to allocate node-wise precision budgets so that threshold-based decisions remain stable under approximation errors.

Instead of minimizing only average output error, FlipGuard treats **decision stability near a threshold** as a first-class scheduling objective.

In other words, FlipGuard asks the following question:

> How much precision is actually needed at each intermediate node to prevent the final decision from flipping?

---

## 1. 개요

FlipGuard의 핵심 아이디어는 CKKS 근사 연산 과정에서 발생하는 오차가 최종 판정을 뒤집지 않도록, 각 중간 연산 노드에 필요한 정밀도 예산을 다르게 배정하는 것입니다.

기존 방식이 주로 평균 출력 오차나 전체 정확도만 줄이는 데 집중했다면, FlipGuard는 **임계값 근처에서 판정이 뒤집히지 않는 것**을 핵심 목표로 둡니다.

즉, FlipGuard는 다음 질문에서 출발합니다.

> 최종 판정이 뒤집히지 않게 하려면 각 중간 연산 노드에 어느 정도의 정밀도가 필요한가?

---

## 2. Research Motivation

CKKS enables approximate arithmetic over encrypted real-valued data, but approximation errors may change downstream decisions when the output is close to a threshold.

For example, in a threshold-based inference pipeline:

```text
decision = 1 if f(x) >= T
decision = 0 otherwise
```

even a small approximation error can cause a **decision flip** when `f(x)` is close to `T`.

FlipGuard targets this problem by using a sufficient decision-stability condition:

```text
estimated_error <= safety_factor * protected_margin
```

where `protected_margin` is derived from the distance between the plaintext score and the decision threshold.

---

## 2. 연구 동기

CKKS는 실수 기반 데이터를 암호화한 상태에서 근사 연산을 수행할 수 있게 해주지만, CKKS의 근사 오차는 최종 출력값이 판정 임계값에 가까울 때 판정을 뒤집을 수 있습니다.

예를 들어, 다음과 같은 임계값 기반 추론이 있다고 가정합니다.

```text
decision = 1 if f(x) >= T
decision = 0 otherwise
```

이때 `f(x)`가 임계값 `T`에 매우 가까우면, 작은 근사 오차만으로도 최종 판정이 바뀔 수 있습니다. 이를 본 연구에서는 **decision flip**, 즉 판정 뒤집힘 문제로 다룹니다.

FlipGuard는 이 문제를 해결하기 위해 다음과 같은 충분조건을 사용합니다.

```text
estimated_error <= safety_factor * protected_margin
```

여기서 `protected_margin`은 평문 기준 출력값과 판정 임계값 사이의 거리에서 유도됩니다.

---

## 3. Current Status

The current implementation is a plain simulation prototype.

### Implemented

- Basic IR graph representation
- Plain evaluator
- Quantized plain evaluator
- Boundary-focused sample generation
- Decision flip / boundary / ambiguous sample analysis
- Interval-based sensitivity analysis
- FlipGuard precision scheduler
- Uniform precision baselines
- Accuracy-only scheduler baselines
- Decision certification metrics
- Precision saving metrics
- Bound conservatism metrics
- CSV and Markdown report export
- CLI experiment selector

### Not Yet Implemented

- Real CKKS backend
- Lattigo-based encrypted execution
- Real-world datasets
- Multiple benchmark workloads
- Runtime / level / rescale-chain measurement

---

## 3. 현재 구현 상태

현재 구현은 실제 CKKS 암호문 연산이 아닌, **평문 기반 정밀도 시뮬레이션 프로토타입**입니다.

### 구현 완료

- 기본 IR 그래프 구조
- 평문 evaluator
- quantized plain evaluator
- boundary-focused sample 생성
- decision flip / boundary / ambiguous sample 분석
- interval-based sensitivity analysis
- FlipGuard precision scheduler
- uniform precision baseline
- accuracy-only scheduler baseline
- decision certification metric
- precision saving metric
- bound conservatism metric
- CSV 및 Markdown report export
- CLI experiment selector

### 아직 구현하지 않은 부분

- 실제 CKKS backend
- Lattigo 기반 암호문 연산
- 실제 데이터셋 실험
- 복수 benchmark workload
- runtime / level / rescale-chain 측정

---

## 4. Current Experiment

The current default experiment is:

```text
logreg_small
```

It uses a small logistic-style polynomial inference example:

```text
z = 0.8*x1 - 0.5*x2 + 1.2*x3 - 0.3
y = 0.5 + 0.197*z - 0.004*z^3
T = 0.5
```

The experiment compares:

- Uniform precision schedules
- Accuracy-only schedules
- FlipGuard decision-margin-aware schedules

---

## 4. 현재 실험

현재 기본 실험은 다음과 같습니다.

```text
logreg_small
```

이 실험은 작은 logistic-style polynomial inference 예제를 사용합니다.

```text
z = 0.8*x1 - 0.5*x2 + 1.2*x3 - 0.3
y = 0.5 + 0.197*z - 0.004*z^3
T = 0.5
```

비교 대상은 다음과 같습니다.

- Uniform precision schedule
- Accuracy-only schedule
- FlipGuard decision-margin-aware schedule

---

## 5. How to Run

List available experiments:

```bash
go run ./cmd/flipguard -list
```

Run the default experiment:

```bash
go run ./cmd/flipguard
```

Run `logreg_small` explicitly:

```bash
go run ./cmd/flipguard -experiment logreg_small
```

Run tests:

```bash
go test ./...
```

---

## 5. 실행 방법

사용 가능한 실험 목록 확인:

```bash
go run ./cmd/flipguard -list
```

기본 실험 실행:

```bash
go run ./cmd/flipguard
```

`logreg_small` 실험 명시 실행:

```bash
go run ./cmd/flipguard -experiment logreg_small
```

테스트 실행:

```bash
go test ./...
```

---

## 6. Output Files

The experiment exports result files under:

```text
results/logreg_small/
```

Generated files include:

```text
summary.csv
report.md
paper_table.md
schedule_*.csv
records_*.csv
```

These generated result files are intentionally ignored by Git.

---

## 6. 출력 파일

실험 결과는 다음 경로에 생성됩니다.

```text
results/logreg_small/
```

생성되는 주요 파일은 다음과 같습니다.

```text
summary.csv
report.md
paper_table.md
schedule_*.csv
records_*.csv
```

이 결과 파일들은 Git에 포함하지 않도록 설정되어 있습니다.

---

## 7. Current Key Result

In the current `logreg_small` benchmark, FlipGuard shows the following behavior:

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

A focused paper-ready table is generated at:

```text
results/logreg_small/paper_table.md
```

---

## 7. 현재 핵심 결과

현재 `logreg_small` benchmark에서 FlipGuard는 다음과 같은 결과를 보입니다.

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

논문 표에 바로 옮길 수 있는 요약 결과는 다음 파일로 생성됩니다.

```text
results/logreg_small/paper_table.md
```

---

## 8. Interpretation

The current result does not claim that FlipGuard is already a complete CKKS compiler.

Rather, it shows that the proposed decision-margin-aware scheduling principle can be implemented and evaluated in a controlled simulation setting.

The current prototype supports the following preliminary claim:

```text
FlipGuard can reduce average scheduled precision while satisfying
decision-margin certification on stable boundary samples.
```

The next development stage is to extend the prototype toward larger workloads and a real CKKS backend.

---

## 8. 결과 해석

현재 결과는 FlipGuard가 이미 완성된 CKKS 컴파일러라는 의미는 아닙니다.

현재 프로토타입은 decision-margin-aware precision scheduling이라는 핵심 아이디어가 통제된 시뮬레이션 환경에서 구현 가능하며, 실험적으로 평가될 수 있음을 보여주는 단계입니다.

현재 프로토타입을 통해 다음과 같은 예비 주장을 뒷받침할 수 있습니다.

```text
FlipGuard는 stable boundary sample에서 decision-margin certification을 만족하면서
평균 scheduled precision을 줄일 수 있다.
```

다음 개발 단계는 더 큰 workload와 실제 CKKS backend로 확장하는 것입니다.

---

## 9. Repository Structure

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
  Experiment runners

internal/report/
  CSV and Markdown report generation

results/
  Generated experiment outputs
```

---

## 9. 저장소 구조

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
  experiment runner

internal/report/
  CSV 및 Markdown report 생성

results/
  생성된 실험 결과 파일
```

---

## 10. Research Direction

Working title:

```text
FlipGuard: Decision-Stability-Aware Error-Budgeted Precision Scheduling for CKKS-Based Encrypted Inference
```

Korean title draft:

```text
FlipGuard: CKKS 기반 암호화 추론의 판정 안정성 보장을 위한 오차 예산 기반 정밀도 스케줄링 기법
```

---

## 10. 연구 방향

현재 연구 제목 초안은 다음과 같습니다.

```text
FlipGuard: Decision-Stability-Aware Error-Budgeted Precision Scheduling for CKKS-Based Encrypted Inference
```

국문 제목 초안은 다음과 같습니다.

```text
FlipGuard: CKKS 기반 암호화 추론의 판정 안정성 보장을 위한 오차 예산 기반 정밀도 스케줄링 기법
```

---

## 11. License

This repository is currently a research prototype. A license will be added later.

---

## 11. 라이선스

현재 이 저장소는 연구 프로토타입 단계입니다. 라이선스는 추후 추가할 예정입니다.