# 제10장 재현성 및 보안 Artifact

## 10.1 재현성 목표

본 연구의 재현성 목표는 논문 표의 숫자를 다시 계산할 수 있다는 수준을 넘어선다. 어떤 source commit과 binary가 어떤 policy, model, input, split, candidate literal을 사용해 encrypted record를 만들었는지 추적하고, frozen evidence에서 publication input을 결정론적으로 재구축할 수 있어야 한다. 이를 위해 execution artifact와 interpretation overlay, paper claim admission을 분리했다.

## 10.2 Release binding

논문 배포 기준은 `flipguard-thesis-v1.0.0-rc2` tag와 commit `6c5f8b234f9f9da91a189fa0f2dc180bb996abf5`다. Archive SHA-256은 `05ef70306a11ab577243b0c708489864f19ccd104e6036e28fc6bd1dab45c0be`다. V10 core-completion manifest SHA-256은 `f7123b0a6ed4846dd7b62848471d9e8aadc679d222bfa451f1503951a49d8d9f`, V3 manifest는 `32d378b371b75d31b8e39ef2acce4c3c7353581ccfbd5e6c7d22b30ffaf4743b`, claim admission manifest는 `d982f0f81915b760c537244fc71aa992bf521eaf65d57a67c2d96dbae0607b8d`다.

V10은 RC1 시점의 core-completion checkpoint다. RC2는 OpenML server-gzip transport를 byte-identical하게 보존하도록 release workflow를 수리했으며 claim, encrypted result, policy, V3를 변경하지 않았다. RC1은 immutable predecessor로 보존한다. `research_release_binding_rc2_v1` overlay가 이 관계와 allowlisted RC1--RC2 diff를 검증한다.

## 10.3 Frozen evidence 계층

Evidence pack은 raw execution ledger, source/model/input snapshots, summary, failure record, manifest, SHA256SUMS, verifier를 포함한다. Preliminary, pilot, pre-security, historical checkpoint는 final pack과 다른 status로 보존하며 덮어쓰지 않는다. Security-V2 재해석처럼 기존 execution을 새 policy로 필터링하는 경우에도 raw record를 수정하지 않고 derived pack을 만든다.

Primary direct, development seed0, locked audit, validation identity v2, Security-V2 attestation, bounded oracle, NO_SAFE, policy sensitivity, structural extension, paired latency가 각각 독립 pack이다. Final suite manifest는 execution commit과 comparator/evidence commit의 역할을 구분한다. 이 분리는 report code 변경이 encrypted execution semantics를 바꾸지 않았는지 검증하는 데 사용된다.

## 10.4 Paper Artifacts V3와 claim registry

Paper Artifacts V3는 13개 table, 10개 figure, equation list, caption input, allowed/prohibited claim block을 제공하며 status는 `FINAL_ADMISSIBLE`이다. Builder는 structural outcome을 {{N:structural_instances}}/{{N:structural_instances}} PASS로 바꾸지 않고 {{N:structural_audit_pass}} PASS와 {{N:structural_reserve_reject}} reserve-policy REJECT를 필수 입력으로 요구한다. Formal catalog denominator는 전체 {{N:formal_catalog_all}}, confirmatory {{N:formal_catalog_confirmatory}}이며 provider/EVA는 appendix-only다.

Paper claim admission registry에는 {{N:paper_admitted_claims}} admitted claim과 {{N:paper_blocked_claims}} blocked/not-evaluated claim이 있다. `paper_claim_allowed=true`는 모든 claim이 지지되었다는 뜻이 아니라, 논문이 `paper_admitted=true`인 문장만 사용할 수 있다는 뜻이다. Thesis lint는 abstract, contribution, results, conclusion을 claim ID와 연결하고 prohibited overclaim을 검사한다.

## 10.5 Clean-clone 및 soak verification

Release workflow는 새 임시 clone에서 exact HEAD checkout, dependency 확인, external source manifest checksum, frozen verifier, V3 rebuild, rebuilt tree digest, untracked required source 부재를 검사했다. Core closure 후 {{N:release_soak_cycles}} soak cycle과 {{N:release_clean_clone_rebuilds}} clean-clone rebuild가 기록되었다. 두 수치는 RC2 `qa_soak.log`의 `cycle=` 행과 `deep=clean_clone_pass` 행을 thesis linter가 직접 계산한다. 반복 verification은 encrypted experiment를 다시 수행하는 것이 아니라 frozen artifact의 deterministic reconstruction과 checksum을 확인한 것이다.

OpenML source는 server가 gzip transport를 반환하는 경우에도 decompressed canonical byte가 expected source digest와 일치하는지 검증한다. RC2 repair는 이 transport 차이를 provenance 손실 없이 처리한다. Dataset raw file을 repository에 무단 포함하는 대신 fetch script, source URL, expected SHA-256, extraction rule, derived artifact manifest를 배포한다.

## 10.6 Security artifact 재현

Security Policy V2 ID는 `security_guidelines_cic2025_table5_2_ternary_128_v2`다. Policy artifact는 paper title, DOI, publication date, exact table, target category, cost-model metadata, Lattigo module/version, concrete `Xs/Xe`, modulus semantics와 generated-at commit을 포함한다. Static re-attestation CSV/JSON은 candidate source, ID, profile/path, LogN, LogQ, LogP, LogQP, old/v2 headroom, admission, identity change, rerun requirement와 reason을 기록한다.

Exact estimator artifact는 concrete Q/P prime을 estimator-compatible JSON으로 내보낸다. Ciphertext와 evaluation key를 별도 object로 평가하고 두 estimator model의 결과를 남긴다. Verifier는 excluded object가 formal result에 들어오지 않았는지 확인한다. 이 artifact가 runtime distribution과 estimator distribution의 차이를 없애는 것은 아니므로 caveat가 manifest와 논문에 유지된다.

## 10.7 논문 draft 재현

Authoritative thesis source는 장별 Markdown, `number_registry.json`, `claim_traceability.csv`, `figure_table_map.csv`, `citation_audit.csv`, BibTeX, RC2 binding overlay를 입력으로 한다. Draft builder는 V3 table을 byte-identical하게 삽입하고 SVG는 source digest를 확인한 뒤 참조한다. Build output은 chapter assembly, abstract, registries, lint report, build report, manifest, SHA256SUMS를 포함한다.

학교의 실제 Word 또는 LaTeX template이 제공되지 않았으므로 본 artifact는 content-complete draft이며 submission-ready typeset document가 아니다. Pandoc/XeLaTeX가 이미 설치된 환경에서 생성하는 PDF도 `CONTENT_PREVIEW_ONLY`로 표시한다. 향후 학교 양식 적용은 내용과 evidence binding을 바꾸지 않는 presentation step이어야 한다.

## 10.8 Reproduction 절차

재현 사용자는 먼저 RC2 tag와 archive digest를 확인한다. 다음으로 external source fetch manifest를 검증하고 각 frozen evidence verifier를 실행한다. Paper claim admission, V3, V10, RC2 binding verifier가 PASS한 뒤 thesis builder를 실행한다. 마지막으로 draft lint와 SHA256SUMS를 검사한다.

Encrypted execution 전체를 재현하려면 높은 계산비용이 필요하지만 publication claim 검증은 frozen raw ledger와 deterministic derived artifact로 수행할 수 있다. Release archive에서 대용량 중복 raw file을 제외한 경우 manifest에 제외 목록과 fetch/rebuild 경로가 있어야 한다. 이러한 계층은 논문 독자가 headline number에서 raw evidence와 source identity까지 역추적할 수 있게 한다.

## 10.9 공개와 책임 있는 사용

Local archive와 pushed tag는 artifact identity를 제공하지만 GitHub Release, Zenodo 또는 외부 public archive 업로드는 repository owner의 credential과 공개 결정을 요구한다. Dataset license와 model artifact의 배포 조건도 공개 전에 재검토해야 한다. 본 연구는 release candidate를 공개 준비 상태로 만들었으나 자동으로 외부 저장소에 게시하지 않았다.

운영 적용 시 사용자는 threshold 의미, `rho`, margin floor, validation/audit data governance, acceptable abstention을 제공해야 한다. FlipGuard가 기본 policy를 갖더라도 application risk owner의 책임을 대체하지 않는다. Audit REJECT 또는 NO_SAFE가 발생하면 시스템은 결과를 성공으로 완화하지 않고 배포를 보류하거나 별도의 사전 등록 절차를 시작해야 한다.
