# Public export of the extended validation workspace

This folder holds the extended validation that followed the submitted manuscript (September to October 2026). It was developed in a separate private workspace (internal name DeciProtect) and copied here on 2026-11-03 so that the public FlipGuard repository holds the final state of the research.

## Included

- Source code: `cmd/`, `src/`, `research/`, `tests/`, `scripts/`
- Protocols: `protocols/`
- Research reports: `docs/research/`, `docs/review/`, `docs/project_sync/`
- Result files of 256 KiB or less under `results/`

Every included file is byte-identical to the workspace copy (`* -text` in `.gitattributes`).

## Withheld

- 2,158 raw result files larger than 256 KiB (about 1.75 GB). Their paths and sizes are listed in [`WITHHELD_LARGE_RESULTS.tsv`](WITHHELD_LARGE_RESULTS.tsv). Some `--check` re-aggregation scripts read these files and will not run without them.
- Manuscript and thesis documents and their text extractions, which carry author, affiliation and contact details: `baseline/`, `docs/thesis/`, `docs/research/fg_journal_integration_v1_20260906/`, `docs/research/fg_journal_integration_v2_20260907/`, `docs/research/fg_journal_review_v1_20260906/`, the matching `results/` runs, `results/fg_thesis_final_v1_20260925_run01/`, `THESIS_DRAFT_KO.*`, and bundled ZIP copies.
- Local environments and archives: `archive/`, `.venv/`, `work/`, `bin/`, `data/raw/`.

Some links and hash manifests inside the reports therefore point to files that are not in this repository.

`AGENTS.md` and `README.md` are kept as they were in the workspace. The rule in `AGENTS.md` not to push to `hasslelee/flipguard` protected the frozen submission tree during the experiments; the author decided on 2026-11-03 to publish the final state here.

---

# 확대 검증 작업 공간 공개본

투고 원고 이후 2026년 9~10월에 진행한 확대 검증입니다. 별도 비공개 작업 공간(내부 이름 DeciProtect)에서 진행했고, 공개 FlipGuard 저장소가 연구의 최종 상태를 담도록 2026-11-03에 이곳으로 옮겼습니다.

포함한 것은 소스 코드, 프로토콜, 연구 보고서, 256 KiB 이하의 결과 파일입니다. 포함한 파일은 작업 공간 원본과 바이트 단위로 같습니다.

빼 둔 것은 다음과 같습니다.

- 256 KiB를 넘는 원시 결과 파일 2,158개(약 1.75 GB). 경로와 크기는 `WITHHELD_LARGE_RESULTS.tsv`에 있습니다. 일부 `--check` 재집계 스크립트는 이 파일이 있어야 실행됩니다.
- 저자·소속·연락처가 들어 있는 원고와 학위논문 문서, 그 텍스트 추출본
- 로컬 실행 환경과 보존본

그래서 보고서 안의 일부 링크와 해시 목록은 이 저장소에 없는 파일을 가리킵니다.
