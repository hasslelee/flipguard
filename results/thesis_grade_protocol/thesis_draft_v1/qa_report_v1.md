# FlipGuard Thesis Draft V1 QA Report

Status: `PASS`

이 문서는 `AUTHORITATIVE_DRAFT_V1`의 내용 품질 검증 범위와 판정을 고정한다.
검증 대상은 chapter source, claim registry, number registry, citation audit,
V3 표·그림, defense Q&A, RC2 release binding이다. `PASS`는 대학원 양식 적용이
완료됐다는 뜻이 아니라, 동결 evidence로 방어할 수 있는 content draft가 각 QA
기준을 통과했다는 뜻이다.

## QA pass 1: Claim lint

- Status: `PASS`
- Admitted claim은 source marker와 `claim_traceability.csv`에 연결했다.
- BLOCKED 또는 NOT_EVALUATED claim은 한계와 향후 연구 문맥에서만 허용한다.
- 초록, 결과, 결론 및 심사 Q&A의 금지 과장을 registry 기반 linter로 검사한다.

## QA pass 2: Number consistency

- Status: `PASS`
- Headline number는 `number_registry.json` marker를 통해서만 렌더링한다.
- Registry 값은 frozen evidence에서 다시 추출해 비교하며, formal catalog 분모
  700/560과 historical
  1,100 execution을 분리한다.
- Seed 0와 seeds 1--4, structural negative result, paired-latency cluster ratio를
  별도 key로 검증한다.

## QA pass 3: Citation verification

- Status: `PASS`
- 인용된 모든 primary source는 BibTeX와 citation audit 양쪽에 존재한다.
- Audit의 title, year, first author, DOI/ePrint/official URL을 BibTeX metadata와
  교차검사한다.
- Related-work 비교표의 모든 연구군 행은 최소 한 개 primary citation을 가진다.

## QA pass 4: Figure, table, and equation cross-reference

- Status: `PASS`
- V3의 모든 표와 그림에 대해 SHA-256, 번호, 장,
  최초 언급 행과 단일 배치를 검사한다.
- 각 asset은 본문에서 먼저 언급한 뒤 배치하며 orphan 또는 중복 번호를 허용하지 않는다.
- 결정 보존 충분조건 `e_c(x)<m(x)`과 운용 reserve policy
  `e_c(x)<0.5m(x)`를 초록, 배경 및 narrative contract에서 분리한다.

## QA pass 5: Advisor-question consistency

- Status: `PASS`
- 모든 심사 질문은 claim ID, 실제 evidence path, 금지 과장,
  3--8문장 답변과 짧은 구두 답변을 가진다.
- 수치 답변은 number registry marker를 사용하고 존재하지 않는 claim이나 path를
  fail-closed로 거부한다.

## QA pass 6: Korean academic prose

- Status: `PASS`
- 핵심 전문 용어는 최초 사용 시 한국어 의미를 설명하고 이후 표기를 일관되게 유지한다.
- 영어 용어는 artifact 상태명, 구현 literal, 국제적으로 고정된 암호 용어처럼 번역이
  오히려 identity를 흐리는 경우에 한정한다.
- 중복·과장 표현을 제거하고 주장의 주체, 통계 단위, 근거와 제한을 같은 절 또는
  바로 이어지는 논의 절에서 명시한다.

## QA pass 7: External reviewer attack

- Status: `PASS`
- Novelty, 평가 편향, 통계 단위, security, generalization, negative result,
  reproducibility 공격을 별도 checklist에서 검토했다.
- Natural data의 literal 불변성, one-host latency, structural REJECT, scalar-replicated
  packing, estimator/runtime distribution 차이를 residual risk로 공개한다.

## QA pass 8: Clean rebuild from chapter sources

- Status: `PASS`
- Builder는 exact source commit, RC2 binding, claim/number registry와 byte-identical
  V3 asset으로 full draft와 artifact pack을 재구성한다.
- 동일 source commit의 temporary output tree가 frozen draft output과 byte-for-byte
  같은지 검사하며 SHA256SUMS를 다시 검증한다.
- Git에서 제외된 RC2 전체 soak ledger는 원본이 있는 작업공간에서 SHA-256과
  cycle 수를 직접 대조하고, clean clone에서는 같은 digest와 RC2 source/archive에
  결합된 `release_qa_summary.json`을 사용한다.
- University template과 PDF toolchain은 research-content gate와 분리되며 현재 상태는
  `CONTENT_COMPLETE_TEMPLATE_PENDING`이다.

## Residual risks

논문 형식은 학교의 authoritative template을 받은 뒤 별도로 적용해야 한다. Citation
audit은 핵심 비교에 필요한 primary source를 검증하지만 체계적 문헌고찰을 표방하지
않는다. 현재 QA는 frozen finite evidence와 admitted wording의 내부 정합성을 보장할
뿐, 새로운 실험 결과나 분포 전체의 안전성 보장을 생성하지 않는다.

## Verification record

이 초안의 source QA에서 전체 Python unittest 275개가 1,829.789초에 PASS했다.
`go test ./...`, `go vet ./...`, 추적 Python 파일 255개의 `py_compile`, 추적
shell 파일 47개의 `bash -n`, `git diff --check`도 PASS했다. Paper claim admission,
Paper Artifacts V3, V10, RC2 binding, margin interpretation, paired-latency admission
verifier를 별도로 재실행했다. Citation audit의 14개 DOI·ePrint·공식 URL은
primary publisher 또는 공식 repository로 해석되는지 재확인했다.

RC2 tag 이후 diff audit에서 core `cmd/`, `internal/`, `research/` 변경과 기존
frozen evidence 수정은 각각 0건이었다. 새 evidence 경로는 요청된
`research_release_binding_rc2_v1` overlay뿐이다. Thesis branch를 새 clone으로
가져온 뒤 source-closure 검사, linter, temporary build, deterministic rebuild,
SHA256SUMS 검증도 PASS했다.

QA 중 복구 가능한 오류는 두 건이었다. 첫째, V3 verifier의 인자를
`--artifact-dir`로 잘못 호출했으나 실제 `--artifact-root` 인터페이스로 다시
실행해 PASS했다. 둘째, 첫 clean clone은 Git에서 제외된 RC2 `qa_soak.log`에
직접 의존해 실패했다. 원본 로그를 변경하지 않고 digest-bound
`release_qa_summary.json`을 추가했으며, 원본이 있을 때는 상호 검증하고 없을
때는 Git에 결합된 요약을 사용하는 방식으로 수정한 뒤 clean clone이 PASS했다.

최종 draft freeze에서는 두 건의 추가 배포 오류를 발견하고 수정했다. 전체
`py_compile`이 만든 ignored `__pycache__`를 source closure가 Git blob으로 오인한
문제는 V3 입력을 Git 추적 파일로만 열거하도록 builder를 제한하고 회귀 검사를
추가해 해결했다. 이어 첫 final clean clone에서 output pack의 필수 복사본 여섯
개가 `results/*` ignore 규칙 때문에 누락된 사실을 확인해 해당 파일만 명시적으로
추적했다. 새 clone에서 deterministic rebuild, 40개 SHA256SUMS, RC2/V3/V10/claim
verifier를 다시 실행해 모두 PASS했다.
