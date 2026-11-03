# DeciProtect

평문 추론과 CKKS 추론의 **판정 일치를 실행 구성 선택에 반영하는 기존 연구**의 확대 검증.
사용자가 최종 검수한 2026-09-05 정보보호학회논문지 PDF의 방법과 편집 방향을 유지한다.
DeciProtect는 독립 작업 공간과 저장소 이름이다.

현재 결과는 초기 연구 checkpoint다. 일반적인 미래 입력의 무반전, 임의 모델/백엔드,
악의적인 서버에 대한 계산 검증, 실제 의료·금융 안전성은 주장하지 않는다.

- [두 번째 확대: Fashion-MNIST와 수치 기준·공식 EVA 비교](docs/research/fg_expand_v2_20260905/REPORT_KO.md)
- [비교 목적과 함수·비용 경계](docs/research/fg_expand_v2_20260905/RESEARCH_QUESTION_AND_METHOD_KO.md)
- [선행연구 조건 구분과 FHE-Agent 정정](docs/research/fg_expand_v2_20260905/RELATED_WORK_CRITERIA_KO.md)
- [첫 구성 선택 확대 실험 보고서](docs/research/fg_expand_v1_20260905/REPORT_KO.md)
- [첫 확대의 추가 원시 분석](docs/research/fg_expand_v2_20260905/FIRST_EXPANSION_ADDENDUM_KO.md)
- [최종 PDF와 방법·구현 대응](docs/research/fg_expand_v1_20260905/PDF_METHOD_MAP_KO.md)
- [기존 실험 목록](docs/research/fg_expand_v1_20260905/LEGACY_ASSETS_KO.md)
- [첫 확대 당시 관련 연구 기록](docs/research/fg_expand_v1_20260905/RELATED_WORK_KO.md) — FHE-Agent 설명은 위 정정 기록을 우선한다.
- [확대 행렬과 검토 결정](docs/research/fg_expand_v1_20260905/DECISIONS_AND_MATRIX_KO.md)
- [현재 확장 계획](docs/research/THESIS_ROADMAP.md)
- [최신 ChatGPT 인계](docs/project_sync/CHATGPT_HANDOFF.md)

과거 별도 운영 정책의 결과는 [초기 파일럿](docs/research/INITIAL_RESULTS.md),
[DP-03 비용 진단](docs/research/dp03_cost_diag_v1_20260905/REPORT_KO.md),
[당시 심사 기록](docs/review/REVIEW_KO.md)에 그대로 보존했다.
재계산·유보·배치 큐는 현재 구성 선택 확대 실험의 필수 과제가 아니다.

## 재현

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-lock.txt
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/analyze_fg_expand_v1.py --check
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/analyze_external_fg_expand_v2.py --check
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/analyze_fg_expand_v2.py --check
```

이 명령은 보존된 원시 관측에서 분모·판정·오차·선택·시간을 다시 집계하며 새 암호화를
실행하지 않는다. 실제 실행 명령과 소스·모델·입력 잠금은
[첫 확대 재현 기록](docs/research/fg_expand_v1_20260905/REPRODUCTION.md)과
[두 번째 확대 재현 기록](docs/research/fg_expand_v2_20260905/REPRODUCTION.md)에 연결했다.
완료된 protocol/run은 재사용하지 않는다. 후속 실행에는 새 규격과 run ID가 필요하다.

DP-03 원시 비용 결과와 입력별 재계산·반환 이력은
`results/dp03_cost_diag_v1_20260905/`에 있다. 새 암호화 실행 없이 검증하려면
`.venv/bin/python scripts/check_cost_report.py`를 사용한다. 기존 `INITIAL_RESULTS.md`는
이전 checkpoint로 보존했다. 비용 진단은 탐색적이며 네트워크·큐 비용이나 새 위험 보장을
포함하지 않는다. 과거 보고서의 큐 제안은 보존된 제안이며 현재 기본 후속 작업이 아니다.

Go 1.25.9, Lattigo 6.2.0을 사용한다. Python과 패키지 버전은 requirements 및
환경 lock에 고정했다. 암호키·암호화 난수가 새로 생성되므로 재실행의 수치가 bitwise
동일할 필요는 없다. 기존 run 폴더는 덮어쓰지 않는다. 새 run-id를 사용한다.
stress와 유한 모집단 감사 스크립트는 최초 checkpoint의 경로를 명시적으로 참조한다.
이들을 새로운 재현본에 적용하려면 새 protocol/run ID와 parent binding을 작성한다.

## 보존 구조

`baseline/`에는 최종 PDF와 원래 동기화 문서, 수정하지 않은 소스 복사가 있다.
`archive/`에는 Git 미추적·무시 파일과 외부 빌드까지 포함하는 전체 로컬 보존본이 있다.
이 보존본은 외부 도구·개인 설정을 포함하므로 Git에 올리지 않는다.
`baseline/FREEZE_MANIFEST.json`이 보존 시점·hash·검증 상태를 기록한다.
원본 `/home/ckks2/flipguard`와 원격 `hasslelee/flipguard`에는 변경을 쓰지 않는다.

최초 환경 버전 확인이 원본에 새 Python 캐시 967개를 생성한 일이 있어,
그 파일만 해시 검증 후 격리·제거했다. 기존 연구 파일은 수정되지 않았다.
첫 archive 시도와 복구 후 초기 목록에 대한 전수 대조 기록은 별도로 보존했다.
그 검증 기록을 재사용하며 새 확대 작업마다 전체 archive 해시 작업을 반복하지 않는다.
경위는 `docs/review/CACHE_RESTORATION.json`, 최종 상태는
`docs/review/SOURCE_STATE_FINAL.json`에 기록한다. 디렉터리 메타데이터와 접근 시각은
동일성 주장 범위에서 제외한다. 전체 보존본은 같은 장비의 로컬 보존본이다.

검증 중 장비가 재시작되면서 과거 V7/V8 자동 서비스가 운영 파일을 갱신했다.
해당 서비스 5개의 자동 시작을 해제하고, 변경분을 별도 보관한 뒤 운영 파일 7개를
초기 hash로 복구했다. Git 객체 내용과 HEAD·브랜치·원격·작업 내용은 같지만,
Git 객체 수정 시각과 Codex 추적 ref에는 차이가 남아 있다. 최종 판정은
`docs/review/SOURCE_STATE_RESOLUTION.json`을 따른다. 보존본 전체의 파일·링크는
초기 목록과 전수 일치하며, 현재 `.git` 전체가 바이트 단위로 같다고 주장하지 않는다.

과거 source 테스트에는 별도 historical results fixture가 필요하다.
해당 fixture는 로컬 완전 보존본에 있으며 소스만 받은 clone의 기본 테스트 대상은
DeciProtect의 새 구현이다. 현재 원본 환경의 패키지 버전을 과거 실험 버전으로 소급하지 않는다.

새 연구의 실제 암호화 요청 JSON과 출력은 원격 저장소에도 포함한다. 원본 UCI zip은
공식 URL과 SHA-256으로 결속하고 로컬에 보관한다. 따라서 보존된 새 실험의 입력·출력
검증과 부모 입력을 사용하는 stress/IID 감사에는 기존 FlipGuard 작업 폴더가 필요하지 않다.
