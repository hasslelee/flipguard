# CKKS Backend Plan

---

# English

This document defines the planned CKKS backend integration for FlipGuard.

The current FlipGuard implementation is a plain simulation prototype. It evaluates whether node-wise precision scheduling can preserve threshold-based decisions under controlled quantization errors.

The next research step is to connect this scheduling principle to real CKKS execution.

## 1. Goal

The CKKS backend should evaluate whether FlipGuard schedules remain effective when the computation is executed over actual CKKS ciphertexts.

The backend should measure:

- encrypted evaluation runtime
- output approximation error
- decision flip rate
- stable-boundary flip rate
- CKKS level consumption
- rescale-chain behavior
- final scale behavior
- agreement between simulation-level bound and CKKS-observed error

The goal is not to build a full CKKS compiler at this stage.

The goal is to build a controlled CKKS execution backend for validating the FlipGuard scheduling principle.

## 2. Current Simulation Model

The current simulation model uses node-wise dyadic quantization.

For each scheduled node `v`, FlipGuard assigns a precision bit value `b_v`.

The simulation uses:

```text
step_v  = 2^(-b_v)
delta_v = step_v / 2
```

The sufficient output error bound is:

```text
estimated_error = Σ_v S_v * delta_v
```

where:

- `S_v` is the output sensitivity of node `v`
- `delta_v` is the local quantization error bound at node `v`

A schedule is decision-certified if:

```text
estimated_error <= safety_factor * protected_margin
```

## 3. CKKS Mapping Problem

CKKS does not expose node-wise dyadic rounding exactly in the same way as the simulation model.

Therefore, the CKKS backend must treat the simulation schedule as a control signal, not as a direct one-to-one CKKS primitive.

The mapping problem is:

```text
simulation precision bits b_v
        ↓
CKKS scale / rescale / level choice
        ↓
observed ciphertext output error
        ↓
decision stability result
```

The first CKKS backend should use a conservative and simple mapping before implementing compiler-level scale optimization.

## 4. Initial Mapping Strategy

The initial backend will use fixed CKKS parameters and evaluate several scale policies.

### Policy A. Uniform Scale Baseline

Use one global scale for all nodes.

Example:

```text
scale = 2^40
```

This corresponds to a conventional high-precision CKKS baseline.

Expected role:

- baseline for output error
- baseline for runtime
- baseline for level consumption

### Policy B. Uniform Low-Scale Baseline

Use a lower global scale.

Example:

```text
scale = 2^30 or 2^35
```

Expected role:

- lower-cost baseline
- likely higher error
- possible decision flips near boundary samples

### Policy C. FlipGuard-Informed Scale Groups

Map scheduled bit values into a small number of scale groups.

Example:

```text
high precision nodes:
  scale = 2^40

medium precision nodes:
  scale = 2^35

low precision nodes:
  scale = 2^30
```

The initial implementation does not need arbitrary per-node scale. A small number of scale groups is enough for the first CKKS validation.

Expected role:

- test whether FlipGuard can lower precision for insensitive nodes
- preserve decision stability near threshold
- reduce level or rescale cost where possible

## 5. Backend Scope

The first CKKS backend should support the current `logreg_small` graph.

Target graph:

```text
z = 0.8*x1 - 0.5*x2 + 1.2*x3 - 0.3
y = 0.5 + 0.197*z - 0.004*z^3
T = 0.5
```

Required CKKS operations:

- encode plaintext vector
- encrypt input values
- ciphertext-plaintext multiplication by constants
- ciphertext-ciphertext multiplication for `z^2`
- ciphertext-ciphertext multiplication for `z^3`
- addition
- rescale
- decrypt
- decode
- compare output with plain reference

## 6. Lattigo Integration Plan

The backend will use Lattigo.

Planned package structure:

```text
internal/ckksbackend/
  params.go
  encoder.go
  evaluator.go
  metrics.go
  logreg_small.go
```

Planned responsibilities:

```text
params.go
  CKKS parameter selection and validation

encoder.go
  input encoding, encryption, decryption, decoding helpers

evaluator.go
  core encrypted evaluation helpers

metrics.go
  runtime, level, scale, and error measurements

logreg_small.go
  encrypted execution of the current benchmark graph
```

## 7. Metrics

The CKKS backend should export a result row with at least:

```text
method
samples
runtime_ms
mean_error
max_error
p95_error
p99_error
flips
stable_boundary_flips
final_level
min_level
max_scale_log2
min_scale_log2
rescale_count
```

These metrics should be written to:

```text
results/logreg_small_ckks/summary.csv
results/logreg_small_ckks/report.md
```

## 8. Expected Research Value

The CKKS backend can answer the following research questions.

### RQ1. Simulation-to-CKKS Agreement

Does the simulation-level FlipGuard bound predict CKKS-observed output error with useful conservatism?

### RQ2. Decision Stability

Does FlipGuard preserve stable-boundary decisions under real CKKS approximation noise?

### RQ3. Precision Saving

Can FlipGuard reduce scale or level cost compared with uniform high-precision CKKS evaluation?

### RQ4. Bound Conservatism

How conservative is the sufficient error bound when compared with CKKS-observed maximum error?

## 9. Risk

The main risk is that CKKS scale management may not map cleanly to the current node-wise quantization model.

Possible outcomes:

1. FlipGuard schedule works directly with grouped CKKS scale policies.
2. FlipGuard requires a calibration layer between simulation bits and CKKS scale bits.
3. FlipGuard remains useful as an analysis pass but needs a different CKKS execution mapping.

All three outcomes are still research-useful.

## 10. Near-Term Implementation Plan

Implementation order:

1. Add `internal/ckksbackend` package skeleton.
2. Add Lattigo dependency.
3. Create CKKS parameter selection helper.
4. Implement a minimal encrypt-decrypt roundtrip test.
5. Implement encrypted evaluation for `z`.
6. Implement encrypted evaluation for `z^2` and `z^3`.
7. Implement full `logreg_small` encrypted evaluation.
8. Compare plain output and CKKS output.
9. Export CKKS summary CSV.
10. Compare uniform high-scale, uniform low-scale, and FlipGuard-informed scale groups.

---

# 한국어

이 문서는 FlipGuard의 CKKS backend 연동 계획 정의.

현재 FlipGuard 구현은 평문 기반 시뮬레이션 프로토타입이다. 통제된 quantization error 환경에서 node-wise precision scheduling이 threshold-based decision을 보존할 수 있는지 평가한다.

다음 연구 단계는 이 scheduling 원리를 실제 CKKS execution과 연결하는 것이다.

## 1. 목표

CKKS backend의 목표는 FlipGuard schedule이 실제 CKKS ciphertext 연산에서도 유효한지 평가하는 것이다.

측정 항목:

- encrypted evaluation runtime
- output approximation error
- decision flip rate
- stable-boundary flip rate
- CKKS level consumption
- rescale-chain behavior
- final scale behavior
- simulation-level bound와 CKKS-observed error의 일치성

현 단계 목표는 완전한 CKKS compiler 구축이 아니다.

현 단계 목표는 FlipGuard scheduling 원리 검증용 controlled CKKS execution backend 구축이다.

## 2. 현재 Simulation Model

현재 simulation model은 node-wise dyadic quantization 사용.

각 scheduled node `v`에 대해 FlipGuard는 precision bit 값 `b_v`를 할당한다.

Simulation에서 사용하는 값:

```text
step_v  = 2^(-b_v)
delta_v = step_v / 2
```

충분조건 기반 output error bound:

```text
estimated_error = Σ_v S_v * delta_v
```

여기서:

- `S_v`: node `v`의 output sensitivity
- `delta_v`: node `v`의 local quantization error bound

Schedule이 decision-certified 되기 위한 조건:

```text
estimated_error <= safety_factor * protected_margin
```

## 3. CKKS Mapping Problem

CKKS는 simulation model의 node-wise dyadic rounding을 그대로 제공하지 않는다.

따라서 CKKS backend는 simulation schedule을 직접적인 CKKS primitive가 아니라 control signal로 취급해야 한다.

Mapping problem:

```text
simulation precision bits b_v
        ↓
CKKS scale / rescale / level choice
        ↓
observed ciphertext output error
        ↓
decision stability result
```

첫 CKKS backend는 compiler-level scale optimization 구현 전, 보수적이고 단순한 mapping 사용.

## 4. 초기 Mapping Strategy

초기 backend는 고정 CKKS parameter를 사용하고, 여러 scale policy를 평가한다.

### Policy A. Uniform Scale Baseline

모든 node에 하나의 global scale 사용.

예시:

```text
scale = 2^40
```

역할:

- output error baseline
- runtime baseline
- level consumption baseline

### Policy B. Uniform Low-Scale Baseline

더 낮은 global scale 사용.

예시:

```text
scale = 2^30 or 2^35
```

역할:

- lower-cost baseline
- 더 큰 error 가능성
- boundary sample 근처 decision flip 발생 가능성

### Policy C. FlipGuard-Informed Scale Groups

Scheduled bit 값을 소수의 scale group으로 mapping.

예시:

```text
high precision nodes:
  scale = 2^40

medium precision nodes:
  scale = 2^35

low precision nodes:
  scale = 2^30
```

초기 구현에서 arbitrary per-node scale까지 필요하지 않다. 첫 CKKS validation에는 소수의 scale group으로 충분하다.

역할:

- insensitive node의 precision 완화 가능성 확인
- threshold 근처 decision stability 보존 확인
- 가능한 경우 level 또는 rescale cost 감소 확인

## 5. Backend Scope

첫 CKKS backend는 현재 `logreg_small` graph 지원.

Target graph:

```text
z = 0.8*x1 - 0.5*x2 + 1.2*x3 - 0.3
y = 0.5 + 0.197*z - 0.004*z^3
T = 0.5
```

필요 CKKS operations:

- plaintext vector encoding
- input value encryption
- constant에 의한 ciphertext-plaintext multiplication
- `z^2` 계산용 ciphertext-ciphertext multiplication
- `z^3` 계산용 ciphertext-ciphertext multiplication
- addition
- rescale
- decryption
- decoding
- plain reference와 output 비교

## 6. Lattigo Integration Plan

Backend는 Lattigo 사용.

예정 package structure:

```text
internal/ckksbackend/
  params.go
  encoder.go
  evaluator.go
  metrics.go
  logreg_small.go
```

역할:

```text
params.go
  CKKS parameter selection and validation

encoder.go
  input encoding, encryption, decryption, decoding helper

evaluator.go
  core encrypted evaluation helper

metrics.go
  runtime, level, scale, error measurement

logreg_small.go
  current benchmark graph의 encrypted execution
```

## 7. Metrics

CKKS backend는 최소한 다음 result row export.

```text
method
samples
runtime_ms
mean_error
max_error
p95_error
p99_error
flips
stable_boundary_flips
final_level
min_level
max_scale_log2
min_scale_log2
rescale_count
```

결과 파일 경로:

```text
results/logreg_small_ckks/summary.csv
results/logreg_small_ckks/report.md
```

## 8. Expected Research Value

CKKS backend가 답해야 할 연구 질문.

### RQ1. Simulation-to-CKKS Agreement

Simulation-level FlipGuard bound가 CKKS-observed output error를 유용한 보수성으로 예측하는가?

### RQ2. Decision Stability

FlipGuard가 실제 CKKS approximation noise 하에서도 stable-boundary decision을 보존하는가?

### RQ3. Precision Saving

FlipGuard가 uniform high-precision CKKS evaluation 대비 scale 또는 level cost를 줄일 수 있는가?

### RQ4. Bound Conservatism

충분조건 error bound는 CKKS-observed maximum error 대비 얼마나 보수적인가?

## 9. Risk

주요 risk는 CKKS scale management가 현재 node-wise quantization model에 깔끔하게 mapping되지 않을 가능성.

가능한 결과:

1. FlipGuard schedule이 grouped CKKS scale policy와 직접 결합
2. Simulation bit와 CKKS scale bit 사이 calibration layer 필요
3. FlipGuard는 analysis pass로 유용하지만 CKKS execution mapping은 별도 설계 필요

세 결과 모두 연구적으로 유효하다.

## 10. 단기 구현 계획

구현 순서:

1. `internal/ckksbackend` package skeleton 추가
2. Lattigo dependency 추가
3. CKKS parameter selection helper 구현
4. 최소 encrypt-decrypt roundtrip test 구현
5. `z` encrypted evaluation 구현
6. `z^2`, `z^3` encrypted evaluation 구현
7. 전체 `logreg_small` encrypted evaluation 구현
8. plain output과 CKKS output 비교
9. CKKS summary CSV export
10. uniform high-scale, uniform low-scale, FlipGuard-informed scale groups 비교