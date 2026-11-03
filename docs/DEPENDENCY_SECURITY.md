# Dependency security

`.github/workflows/dependency-security.yml` keeps a record of the third-party
code this repository depends on and checks it against public vulnerability
data. It does not touch research code, frozen evidence, or experiment results.

| Job | What it does | Blocks the build? |
|---|---|---|
| Go modules | `go mod verify` against `go.sum`, CycloneDX SBOM of `go.mod` (uploaded as the `sbom-go-cyclonedx` artifact and listed in the job summary), `govulncheck ./...` | Yes, when a known vulnerability is reachable from this code |
| CI Python requirements | `pip-audit` on `requirements-ci.txt`, report uploaded as `pip-audit-ci-requirements` | No. It reports with a warning |

It runs on pushes and pull requests to `main`, every Monday 00:00 UTC, and on
demand.

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

이 저장소가 쓰는 외부 코드 목록(SBOM)을 만들고 공개 취약점 DB와 대조한다. Go 의존성은
이 코드에서 실제로 호출되는 취약점이 있으면 빌드를 실패시키고, CI 전용 Python 의존성은
보고만 한다. CI 전용 Pillow 10.2.0에는 2026-11-03 기준 알려진 권고 48건이 있고, 모두
고치려면 13.0.0이 필요하다. 재현 환경에 묶인 고정 버전이라 올릴지는 재현 결과를 확인한 뒤
따로 결정한다.
