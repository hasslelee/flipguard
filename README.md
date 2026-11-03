# FlipGuard

**Selecting CKKS execution configurations that keep encrypted decisions consistent with plaintext**

CKKS 동형암호로 암호화한 채 추론할 때, 정해진 평가 입력의 판정 적용 영역에서 평문과 같은 판정과 오차 기준을 지키는 실행 구성을 고르는 연구 코드입니다.

- Status: research code. A Korean journal paper based on this work is under review.
- Stack: Go 1.25.9 · [Lattigo v6.2.0](https://github.com/tuneinsight/lattigo) (CKKS) · Python for data export, analysis and figures
- Implementation: the Go implementation was developed with AI coding assistance. The research question, acceptance criteria, experiment design and validation of reported results were determined by the author.

[English](#english) · [한국어](#한국어)

---

## English

### Problem

CKKS returns approximate results. When a model's score sits close to its decision threshold, or two class scores are close, a small encryption error can change the final decision (approve ↔ reject, benign ↔ malicious). Choosing a configuration only by average error or speed does not rule this out.

### Approach

1. Compute each input's plaintext decision margin: the distance from the score to the threshold, or between the top two class scores.
2. Derive an initial execution configuration (ring degree, modulus chain, scale) from the computation graph and those margins.
3. Run the encrypted inference. Accept the configuration only when, on the decision-applicable selection inputs, decisions match plaintext and per-input errors stay within their limits, and the parameters pass the declared 128-bit security policy.
4. Otherwise adjust it by a fixed rule within an evaluation budget. If nothing passes, return `NO_SAFE` instead of an unsafe configuration.
5. Re-check the selected configuration on separate inputs.

### Results

68 declared cases (66 binary-threshold, 2 multiclass).

| | |
|---|---|
| Without the decision check: initial configurations with a decision change or error-limit violation | 21 / 68 (decision changed in 20) |
| Configurations changed by FlipGuard | 21, with one additional encrypted evaluation each; the other 47 kept |
| Encrypted candidate evaluations | 89 instead of 537 for the finite reference set (−83.43%) |
| False `NO_SAFE` in the 68 reported cases | 0 |
| Final configurations passing separate-input evaluation (decision-applicable inputs) | 68 / 68 |

Decision-applicable inputs are those whose plaintext decision margin exceeds δ = 0.001. In the separate-input evaluation, 16,049 of 18,367 inputs (87.38%) met this condition, and the 68/68 result means every such input in every case passed under three key repeats. Boundary inputs are excluded from the claim. `NO_SAFE` means no passing configuration was found within the stated policy and budget, not that none exists.

These results hold for the declared candidate set and measurement environment. They do not claim global optimality, safety for every future input, or protection against a malicious server.

Evidence: [`docs/reports/comparison_extension_v18/ABSTRACT_RESULT_FACTS_V18_KO_EN.md`](docs/reports/comparison_extension_v18/ABSTRACT_RESULT_FACTS_V18_KO_EN.md), code verification reports on the [`paper/v25-v34-verification`](https://github.com/hasslelee/flipguard/tree/paper/v25-v34-verification/docs/verification) branch.

### Extended validation (September–October 2026)

After the 68-case evaluation, the same selection method was tested further in [`extended_validation/`](extended_validation/). Negative and limited results are reported as observed. The reports are in Korean.

- **First expansion** (Spambase and HTRU2, four cases, [report](extended_validation/docs/research/fg_expand_v1_20260905/REPORT_KO.md)): on 820 decision-applicable case–input pairs not used for selection, the selected configurations showed 0 decision changes and 0 error-limit violations, against 201 and 675 for the initial configurations (per-key observation counts).
- **Second expansion** (Fashion-MNIST with three training initializations, numerical-error criteria and official EVA execution, [report](extended_validation/docs/research/fg_expand_v2_20260905/REPORT_KO.md)): the numerical criteria and the decision criterion accepted the same candidates.
- **Contribution check** (seven models, [report](extended_validation/docs/research/fg_contrib_v1_20260906/REPORT_KO.md)): adding the decision condition to selection did not change the chosen configuration in any of 14 case–selection blocks, and the proposed procedure did not need fewer candidate evaluations than plain decision-based selection. On an external stress set its selected configurations still showed 1 decision change and 6 error-limit violations, so passing selection is not a guarantee for new inputs.
- **Precision-slack option** (Bank, Spambase MLP and Fashion-MNIST, [report](extended_validation/docs/research/fg_thesis_v1_20260908/THESIS_EXPERIMENTS_KO.md)): on the Bank reserved audit, decision mismatches in the applicable region fell from 8 to 0, but a simpler decision-based baseline also had 0, so the option is kept separate rather than made the default.

Raw result files over 256 KiB and documents carrying author details are not included; see [`extended_validation/PUBLIC_EXPORT.md`](extended_validation/PUBLIC_EXPORT.md).

### Quick start

```bash
go version                            # Go 1.25.9 or later
go run ./cmd/flipguard -list          # list experiments
```

Experiment outputs are written to `results/<experiment>/` as CSV and Markdown.

### Tests and required inputs

A fresh clone does not contain `results/`. Six tests under `internal/ckksplanner` read MNIST, BSDS500 or v17 input files from that folder and fail until those inputs are provided. In the maintainer's run on 2026-11-03 all other packages passed. `go test ./...` is therefore not a clean-clone check, and `-list` is not a command that reproduces the 68 cases.

```bash
go test ./...                         # after placing the required inputs under results/
```

### Branches

| Branch | Contents |
|---|---|
| `main` | Code and locked paper facts at manuscript submission, plus `extended_validation/` |
| `paper/v25-v34-verification` | Code verification reports for the submitted manuscript |
| `research/model-family-expansion-v17-vcpu6-20260811` | 68-case runs and as-run source tracking |
| `paper/final-audit-defense-v1`, `experiments/*`, `research/*` | Earlier audits and comparisons with external tools (EVA, HECATE, ELASM, Orion) |

### Project history

The project started in May 2026 as node-wise precision scheduling on a plain simulator. After moving to the real Lattigo CKKS backend, the work shifted to selecting whole execution configurations, with decision consistency as the acceptance rule (June to August 2026). The full history is kept in the commit log.

---

## 한국어

### 문제

CKKS는 근사 연산이라, 모델 점수가 임곗값 근처에 있거나 두 클래스 점수가 비슷하면 작은 암호화 오차로 최종 판정이 바뀔 수 있습니다. 평균 오차나 속도만 보고 구성을 고르면 이 문제를 막지 못합니다.

### 방법

1. 입력마다 평문 판정 여유(점수와 임곗값의 거리, 또는 상위 두 클래스 점수의 차이)를 계산합니다.
2. 계산 그래프와 판정 여유로 초기 실행 구성(링 차원, 모듈러스 체인, 스케일)을 정합니다.
3. 암호화 추론을 실행해, 채택용 입력 중 판정 적용 영역의 입력에서 판정이 평문과 같고 입력별 오차가 한계 안이며, 파라미터가 명시한 128비트 보안 정책을 통과할 때만 채택합니다.
4. 통과하지 못하면 정해진 규칙으로 평가 예산 안에서 조정하고, 끝내 통과하는 구성이 없으면 안전하지 않은 구성을 내놓지 않고 `NO_SAFE`로 끝냅니다.
5. 선택한 구성을 별도 입력으로 다시 확인합니다.

### 결과

선언한 68개 사례(이진 판정 66, 다중 클래스 2) 기준입니다.

| | |
|---|---|
| 판정 일관성 검사 없이 고른 초기 구성 중 판정 변화·오차 기준 위반 | 68개 중 21개 (판정 변화 20개) |
| FlipGuard가 바꾼 구성 | 21개, 각각 암호화 평가 1회 추가. 나머지 47개는 그대로 |
| 암호화 후보 평가 횟수 | 유한 비교 집합 537회 대신 89회 (83.43% 감소) |
| 보고한 68개 사례에서 잘못된 `NO_SAFE` | 0 |
| 최종 구성의 별도 입력 평가 통과 (판정 적용 영역) | 68개 중 68개 |

판정 적용 영역은 평문 판정 여유가 δ = 0.001보다 큰 입력입니다. 별도 입력 평가에서 18,367개 중 16,049개(87.38%)가 이 영역에 들어갔고, 68/68은 모든 사례에서 이 영역의 입력이 세 번의 키 반복 모두 통과했다는 뜻입니다. 경계 입력은 이 주장에 포함하지 않습니다. `NO_SAFE`는 정한 정책과 예산 안에서 통과 구성을 찾지 못했다는 뜻이지, 통과 구성이 아예 없다는 증명은 아닙니다.

이 결과는 선언한 후보 집합과 측정 환경에 한정되며, 전역 최적성이나 모든 미래 입력의 안전, 악의적인 서버에 대한 보호를 주장하지 않습니다.

### 확대 검증 (2026년 9~10월)

68개 사례 평가 뒤 같은 선택 방법을 [`extended_validation/`](extended_validation/)에서 더 시험했습니다. 효과가 없거나 제한적이었던 결과도 관측한 그대로 적었습니다.

- **첫 확대**(Spambase·HTRU2 네 사례, [보고서](extended_validation/docs/research/fg_expand_v1_20260905/REPORT_KO.md)): 선택에 쓰지 않은 판정 적용 영역 820개 사례–입력 쌍에서 선택 구성은 판정 변화 0회·오차 위반 0회, 초기 구성은 201회·675회였습니다(키별 관측 수).
- **두 번째 확대**(Fashion-MNIST 세 학습 초기값, 수치 오차 기준, 공식 EVA 실행, [보고서](extended_validation/docs/research/fg_expand_v2_20260905/REPORT_KO.md)): 수치 기준과 판정 기준의 통과 후보가 같았습니다.
- **기여 검증**(7개 모델, [보고서](extended_validation/docs/research/fg_contrib_v1_20260906/REPORT_KO.md)): 판정 조건을 선택에 넣어도 14개 사례–선택 블록 모두에서 고른 구성이 같았고, 제안 절차가 단순 판정 기반 선택보다 후보 평가를 덜 하지도 않았습니다. 외부 스트레스 입력에서는 선택 구성에도 판정 변화 1회와 오차 위반 6회가 있어, 선택 통과가 새 입력에 대한 보장은 아닙니다.
- **정밀도 여유 옵션**(Bank, Spambase MLP, Fashion-MNIST, [보고서](extended_validation/docs/research/fg_thesis_v1_20260908/THESIS_EXPERIMENTS_KO.md)): Bank 예약 감사에서 적용 영역 판정 불일치가 8회에서 0회로 줄었지만 더 단순한 판정 기반 비교군도 0회여서, 기본값으로 바꾸지 않고 별도 옵션으로 두었습니다.

256 KiB를 넘는 원시 결과와 저자 정보가 들어 있는 문서는 넣지 않았습니다. 자세한 내용은 [`extended_validation/PUBLIC_EXPORT.md`](extended_validation/PUBLIC_EXPORT.md)에 있습니다.

### 실행

```bash
go version                            # Go 1.25.9 이상
go run ./cmd/flipguard -list          # 실험 목록
```

실험 결과는 `results/<실험명>/`에 CSV와 Markdown으로 저장됩니다.

### 테스트와 필요한 입력

새로 받은 저장소에는 `results/`가 없습니다. `internal/ckksplanner`의 테스트 6개는 이 폴더의 MNIST·BSDS500·v17 입력 파일을 읽기 때문에, 그 파일을 넣기 전까지 실패합니다. 2026-11-03 점검에서 나머지 패키지는 모두 통과했습니다. 따라서 `go test ./...`는 새로 받은 저장소만으로 통과를 확인하는 명령이 아니고, `-list`도 68개 사례를 재현하는 명령이 아닙니다.

```bash
go test ./...                         # results/에 필요한 입력을 넣은 뒤
```

### 브랜치

| 브랜치 | 내용 |
|---|---|
| `main` | 논문 투고 시점 코드와 고정된 논문 수치, `extended_validation/` 확대 검증 |
| `paper/v25-v34-verification` | 투고 원고에 대한 코드 검증 보고서 |
| `research/model-family-expansion-v17-vcpu6-20260811` | 68개 사례 실행과 실행 시점 소스 기록 |
| `paper/final-audit-defense-v1`, `experiments/*`, `research/*` | 이전 감사, 외부 도구(EVA, HECATE, ELASM, Orion)와의 비교 |

### 진행 과정

2026년 5월 평문 시뮬레이터에서 노드별 정밀도 배분으로 시작했습니다. 실제 Lattigo CKKS 백엔드로 옮긴 뒤에는 판정 일관성을 채택 조건으로 삼아 실행 구성 전체를 고르는 방식으로 바뀌었습니다(2026년 6~8월). 전체 과정은 커밋 기록에 남아 있습니다.

Go 구현은 AI 코딩 도구의 도움을 받아 개발했습니다. 연구 질문, 채택 기준, 실험 설계와 보고한 결과의 검증은 직접 정했습니다.
