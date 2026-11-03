# Dependency security

`.github/workflows/dependency-security.yml` keeps a record of the third-party
code this repository depends on and checks it against public vulnerability
data. It does not touch research code, frozen evidence, or experiment results.

| Job | What it does | Blocks the build? |
|---|---|---|
| Go modules | `go mod verify` against `go.sum`, CycloneDX SBOM of `go.mod` (uploaded as the `sbom-go-cyclonedx` artifact and listed in the job summary), `govulncheck` (report uploaded as `govulncheck-json`, called advisories listed in the job summary) | Yes, when a required module has a known vulnerability that this code calls. Called advisories in the Go standard library are reported with a warning |
| CI Python requirements | `pip-audit` on `requirements-ci.txt`, report uploaded as `pip-audit-ci-requirements` | No. It reports with a warning |

It runs on pushes and pull requests to `main`, every Monday 00:00 UTC, and on
demand.

## Why Go standard library findings only warn

`go.mod` pins Go 1.25.9, and the same version is recorded in
`release/environment_requirements_v1.json` and
`docs/reproducibility/final_release_readiness_v1/ENVIRONMENT_LOCK.json`. The
toolchain is part of the reproduction environment, so a standard library
advisory is fixed by moving that lock on purpose, not by CI.

`.github/scripts/govulncheck_gate.py` reads the JSON report and counts only
findings whose call trace reaches a function. A called advisory in a required
module fails the job, because the fix is a dependency bump in this repository.
A called advisory in the standard library is listed with its fixed Go version
and a warning.

As of 2026-11-03, govulncheck reports 13 called standard library advisories for
go1.25.9. Five are fixed in later 1.25 releases (go1.25.11 to go1.25.13). The
other eight have no 1.25 fix listed and are fixed in go1.26.9 or go1.26.10, so
fixing all 13 needs go1.26.10 or later. No called advisory was found in a
required module.

## Why the Python check only reports

`requirements-ci.txt` pins Pillow 10.2.0 for the replay workflows
(`independent-artifact-replay.yml`, `external-source-replay.yml`). Those pins
are part of the replay environment, so changing them is a deliberate decision
rather than an automatic one.

As of 2026-11-03, `pip-audit` lists 48 advisories for Pillow 10.2.0. Fixing all
of them needs Pillow 13.0.0. The two replay workflows are the only places that
install it, and they run in short-lived CI runners. Upgrading should be checked
against the replay results before the pin changes.

## 한국어 요약

이 저장소가 쓰는 외부 코드 목록(SBOM)을 만들고 공개 취약점 DB와 대조한다. Go 의존
모듈은 이 코드가 실제로 호출하는 취약점이 있으면 빌드를 실패시킨다. Go 표준 라이브러리
취약점은 경고로 보고만 한다. Go 1.25.9가 재현 환경 고정값(go.mod, 환경 잠금 파일)이라
툴체인을 올리는 일은 따로 결정하기 때문이다. 2026-11-03 기준 go1.25.9에서 호출되는 표준
라이브러리 권고는 13건이다. 5건은 go1.25.11~1.25.13에서 고쳐졌고, 나머지 8건은 1.25 계열
수정판이 없고 go1.26.9~1.26.10에서 고쳐졌다. 13건을 모두 고치려면 go1.26.10 이상이 필요하다. CI 전용 Python 의존성은
보고만 한다. CI 전용 Pillow 10.2.0에는 2026-11-03 기준 알려진 권고 48건이 있고, 모두
고치려면 13.0.0이 필요하다. 재현 환경에 묶인 고정 버전이라 올릴지는 재현 결과를 확인한 뒤
따로 결정한다.
