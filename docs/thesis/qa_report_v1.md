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
  {{N:formal_catalog_all}}/{{N:formal_catalog_confirmatory}}과 historical
  {{N:raw_historical_catalog_executions|,}} execution을 분리한다.
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
  `e_c(x)<{{N:primary_alpha}}m(x)`를 초록, 배경 및 narrative contract에서 분리한다.

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
- University template과 PDF toolchain은 research-content gate와 분리되며 현재 상태는
  `CONTENT_COMPLETE_TEMPLATE_PENDING`이다.

## Residual risks

논문 형식은 학교의 authoritative template을 받은 뒤 별도로 적용해야 한다. Citation
audit은 핵심 비교에 필요한 primary source를 검증하지만 체계적 문헌고찰을 표방하지
않는다. 현재 QA는 frozen finite evidence와 admitted wording의 내부 정합성을 보장할
뿐, 새로운 실험 결과나 분포 전체의 안전성 보장을 생성하지 않는다.
