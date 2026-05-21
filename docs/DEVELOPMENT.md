# FlipGuard Development Notes

---

# English

This document describes the current development workflow.

## 1. Basic Commands

Run all tests:

```bash
go test ./...
```

Run the default experiment:

```bash
go run ./cmd/flipguard
```

List available experiments:

```bash
go run ./cmd/flipguard -list
```

Run the current reproducibility script:

```bash
./scripts/run_logreg_small.sh
```

## 2. Git Workflow

During the early research-prototype stage:

- Commit small, meaningful changes locally.
- Push several steps together rather than after every small edit.
- Keep `main` buildable.
- Run `go test ./...` before committing.
- Run the reproducibility script before milestone pushes.

Recommended local workflow:

```bash
go test ./...
./scripts/run_logreg_small.sh
git status
git add <changed-files>
git commit -m "Clear feature-level message"
```

Recommended milestone push:

```bash
git log --oneline --max-count=8
git push
```

## 3. Result Files

Generated result files are written under:

```text
results/logreg_small/
```

These files are intentionally ignored by Git.

Important generated files:

```text
summary.csv
report.md
paper_table.md
schedule_*.csv
records_*.csv
```

## 4. Coding Guidelines

General rules:

- Keep packages small and purpose-specific.
- Keep `cmd/flipguard/main.go` as a CLI entry point only.
- Put experiment logic under `internal/experiment`.
- Put benchmark graph definitions under `internal/benchmarks`.
- Put analysis logic under `internal/analysis`.
- Put scheduling logic under `internal/scheduler`.
- Put result writers under `internal/report`.

Before committing:

```bash
gofmt -w <changed-go-files>
go test ./...
```

Before milestone push:

```bash
./scripts/run_logreg_small.sh
```

## 5. Near-Term Development Tasks

Planned next steps:

1. Add configuration reporting to generated Markdown files.
2. Add ablation over safety factor.
3. Add ablation over protected percentile.
4. Add a second synthetic benchmark.
5. Add real dataset preprocessing.
6. Add CKKS backend design document.
7. Add Lattigo dependency only after the plain simulation path is stable.

---

# 한국어

이 문서는 현재 FlipGuard의 개발 workflow를 설명한다.

## 1. 기본 명령어

전체 테스트 실행:

```bash
go test ./...
```

기본 실험 실행:

```bash
go run ./cmd/flipguard
```

사용 가능한 실험 목록 확인:

```bash
go run ./cmd/flipguard -list
```

현재 재현성 스크립트 실행:

```bash
./scripts/run_logreg_small.sh
```

## 2. Git Workflow

초기 연구 프로토타입 단계에서는 다음 흐름을 사용한다.

- 작고 의미 있는 단위로 로컬 commit을 생성한다.
- 너무 작은 수정마다 push하지 않고, 여러 step을 묶어서 push한다.
- `main` branch는 항상 build 가능한 상태로 유지한다.
- commit 전 `go test ./...`를 실행한다.
- milestone push 전 재현성 스크립트를 실행한다.

권장 로컬 workflow:

```bash
go test ./...
./scripts/run_logreg_small.sh
git status
git add <changed-files>
git commit -m "Clear feature-level message"
```

권장 milestone push:

```bash
git log --oneline --max-count=8
git push
```

## 3. 결과 파일

생성 결과 파일 경로.

```text
results/logreg_small/
```

이 파일들은 Git에 포함하지 않도록 설정되어 있다.

중요한 생성 파일은 다음과 같습니다.

```text
summary.csv
report.md
paper_table.md
schedule_*.csv
records_*.csv
```

## 4. 코딩 가이드라인

일반 규칙.

- package는 작고 목적이 명확하게 유지한다.
- `cmd/flipguard/main.go`는 CLI entry point 역할만 수행하도록 유지한다.
- 실험 로직은 `internal/experiment`에 둔다.
- benchmark graph 정의는 `internal/benchmarks`에 둔다.
- 분석 로직은 `internal/analysis`에 둔다.
- scheduling logic은 `internal/scheduler`에 둔다.
- 결과 writer는 `internal/report`에 둔다.

commit 전.

```bash
gofmt -w <changed-go-files>
go test ./...
```

milestone push 전.

```bash
./scripts/run_logreg_small.sh
```

## 5. 단기 개발 작업

예정된 다음 작업은 다음과 같습니다.

1. 생성된 Markdown 파일에 configuration reporting 추가
2. safety factor에 대한 ablation 추가
3. protected percentile에 대한 ablation 추가
4. 두 번째 synthetic benchmark 추가
5. 실제 데이터셋 preprocessing 추가
6. CKKS backend 설계 문서 추가
7. 평문 시뮬레이션 경로가 안정화된 이후 Lattigo dependency 추가