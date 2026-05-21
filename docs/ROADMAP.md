# FlipGuard Roadmap

---

# English

This document tracks the planned development stages of FlipGuard.

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

## Stage 6. Packaging and Artifact

Status: planned.

Goals:

- Add a stable command-line interface.
- Add configuration files for experiments.
- Add artifact reproduction instructions.
- Add a license.
- Add citation metadata.
- Add versioned result snapshots.

---

# 한국어

이 문서는 FlipGuard의 개발 로드맵을 정리합니다.

## Stage 1. 평문 기반 시뮬레이션 프로토타입

상태: 진행 중.

목표:

- 소규모 계산 그래프 IR 정의
- 평문 및 quantized evaluator 구현
- boundary-focused sample 생성
- decision flip 및 boundary-zone behavior 측정
- interval-based sensitivity analysis 구현
- 첫 번째 FlipGuard precision scheduler 구현
- uniform baseline 및 accuracy-only baseline과 비교
- 재현 가능한 CSV 및 Markdown report export

현재 상태:

- 기본 프로토타입 구현 완료
- `logreg_small` 실험은 `scripts/run_logreg_small.sh`로 재현 가능

## Stage 2. 더 큰 평문 기반 workload

상태: 계획 중.

목표:

- 더 큰 synthetic polynomial inference workload 추가
- multi-layer polynomial model 추가
- multiple threshold 및 multi-output decision rule 추가
- 다양한 boundary distribution에서 decision-margin certification stress-test
- 다음 항목에 대한 ablation study 추가:
  - margin floor
  - safety factor
  - protected percentile
  - max precision bits
  - boundary-zone width

## Stage 3. 실제 데이터셋 기반 시뮬레이션

상태: 계획 중.

목표:

- tabular classification workload 추가
- threshold-based inference에 적합한 실제 또는 공개 데이터셋 사용
- 암호화 backend 외부에서 소규모 모델 학습
- inference를 위한 polynomial approximation graph export
- 데이터셋별 decision flip behavior 비교

후보 workload:

- credit-risk style binary classification
- fraud-detection style binary classification
- medical-risk style threshold inference

저장소의 핵심 방향은 특정 도메인에 한정되지 않는 범용성입니다. 금융 데이터셋은 평가 workload로 사용할 수 있지만, 핵심 방법론은 일반적인 CKKS 기반 암호화 추론을 대상으로 합니다.

## Stage 4. CKKS Backend

상태: 계획 중.

목표:

- Lattigo 기반 CKKS execution backend 추가
- scheduled precision을 CKKS scale 및 rescale choice와 연결
- 다음 항목 측정:
  - runtime
  - level consumption
  - output error
  - decision flip rate
  - stable-boundary flip rate
  - certification success
- simulation-level estimate와 실제 CKKS 관측 오차 비교

## Stage 5. 논문용 평가

상태: 계획 중.

목표:

- 논문용 표와 그림 생성
- FlipGuard를 다음 기준과 비교:
  - uniform precision baseline
  - accuracy-only scheduling
  - CKKS compiler-inspired scale management baseline
- 다음 지표 보고:
  - stable boundary flips
  - certification usage
  - precision saving
  - bound conservatism
  - runtime and level consumption
- 우선 국내 학술대회 논문 준비
- 결과가 충분히 강할 경우 국제 workshop 제출로 확장

## Stage 6. 패키징 및 Artifact 정리

상태: 계획 중.

목표:

- 안정적인 command-line interface 추가
- 실험용 configuration file 추가
- artifact reproduction instruction 추가
- license 추가
- citation metadata 추가
- versioned result snapshot 추가