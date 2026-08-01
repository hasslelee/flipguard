# 부록

## A.1 Auxiliary provider-format evidence

Core evaluation은 direct synthesizer와 Security-V2 bounded catalog를 사용했다. 별도의 auxiliary study는 manual/provider candidate를 동일 admission gate에 넣기 위한 import schema를 점검했다. 이 evidence에는 synthetic provider-format interoperability, Orion fail-closed import, AWS HIT rejection, EVA native scale sensitivity, scale-30 native locked audit, exact EVA Q/P materialization이 포함된다.

Provider evidence의 목적은 일반 외부 autotuner 호환성을 입증하는 것이 아니다. Candidate source, runtime, Q/P materialization 의미가 다를 때 identity와 security를 fail-closed로 처리할 수 있는지 확인하는 것이다. Orion import와 HIT rejection은 받아들일 수 없는 입력을 성공으로 바꾸지 않았고, EVA evidence는 한정된 native runtime candidate의 materialization을 기록했다.

## A.2 EVA boundary

EVA는 CKKS compiler와 parameter automation의 중요한 선행 체계다 [@dathathri2020eva]. 본 연구의 auxiliary artifact는 EVA scale sensitivity와 exact Q/P materialization provenance를 보존한다. 그러나 scale-30 Lattigo operation adapter, matched Lattigo--SEAL row/key execution, cross-runtime numerical equivalence, runtime-specific equivalent security는 수행하지 않았다.

따라서 EVA 결과는 `PARTIALLY_SUPPORTED` auxiliary interoperability evidence다. 한 native EVA candidate의 success 또는 다른 scale의 rejection은 Lattigo direct arm과의 수치 동등성이나 모든 external autotuner output의 admission 가능성을 뜻하지 않는다. 이러한 비교에는 동일 graph semantics, input ordering, scale interpretation, key distribution, Q/P object와 error metric을 맞춘 별도 사전 등록 protocol이 필요하다.

## A.3 Validation identity incident

Comparator schema v1은 direct source artifact와 catalog source artifact의 representation layer를 혼동하여 validation identity mismatch로 fail-closed했다. {{N:validation_identity_class_a}}/{{N:combined_descriptive_instances}} source artifact는 byte-identical했으나 prepared artifact는 provenance/full-precision representation 때문에 raw byte가 달랐다. Identity audit v2는 source raw digest, prepared raw digest, semantic digest, ordered-row digest, model digest를 분리했다.

V2 결과는 CLASS A {{N:validation_identity_class_a}}였으며 CLASS B/C/D/E는 관측되지 않았다. Execution semantics와 source replay가 {{N:validation_identity_class_a}}/{{N:combined_descriptive_instances}}에서 확인되어 encrypted rerun은 필요하지 않았다. Original v1 fail-closed record는 삭제하지 않고 final evidence에 포함했다. 이 사례는 checksum 하나가 의미 identity의 모든 층을 대신할 수 없으며, raw representation과 computation semantics를 동시에 기록해야 함을 보여준다.

## A.4 Failure taxonomy detail

`NUMERICAL_REJECT`는 candidate가 실행되었지만 reserve-policy violation이 발생한 상태다. `LEVEL_FAILURE`는 graph execution에 필요한 modulus level이 부족한 상태다. `NO_SAFE`는 bounded candidate budget에서 SAFE가 확립되지 않은 selection outcome이다. `VALIDATION_NEAR_BUDGET_LIMIT_AUDIT_OVERRUN`은 validation utilization이 cap 아래였으나 disjoint audit에서 cap을 넘은 structural negative result다.

`POLICY_REJECTED_WITHOUT_FLIP`은 decision이 관측상 보존되었지만 operational reserve를 초과한 경우다. Cryptographic correctness failure나 decision failure로 해석하지 않는다. `VALIDATION_IDENTITY_UNRESOLVED_FAIL_CLOSED`는 provenance layer를 해소하기 전 comparator가 비교를 중단한 상태다. 이러한 class는 원인과 claim effect를 분리해 자동 repair가 허용되는지 판단한다.

## A.5 Claim registry summary

Paper-admitted claim은 scoped direct synthesis, adaptive repair, formal trial reduction, primary no-retuning locked audit, scoped NO_SAFE, paired latency, structural extension, scoped non-tabular extension, independent training/data-seed extension, security attestation, finite-scope decision-integrity admission의 {{N:paper_admitted_claims}}개다.

본문 claim으로 admit되지 않은 항목은 natural-data margin에 의한 literal 변화, instantiated analytical CKKS certificate, distribution-wide safety, arbitrary graph support, configuration space 전체의 최적성, cross-runtime numerical equivalence, general external-autotuner integration, production latency, universal runtime security다. 이 항목은 실패를 의미하는 단일 집합이 아니라 BLOCKED 또는 NOT_EVALUATED 상태의 future-work boundary다.

## A.6 Artifact identifiers

- RC2 tag: `flipguard-thesis-v1.0.0-rc2`
- RC2 source: `6c5f8b234f9f9da91a189fa0f2dc180bb996abf5`
- RC2 archive SHA-256: `05ef70306a11ab577243b0c708489864f19ccd104e6036e28fc6bd1dab45c0be`
- Paper Artifacts V3 manifest SHA-256: `32d378b371b75d31b8e39ef2acce4c3c7353581ccfbd5e6c7d22b30ffaf4743b`
- Claim admission manifest SHA-256: `d982f0f81915b760c537244fc71aa992bf521eaf65d57a67c2d96dbae0607b8d`
- Margin interpretation manifest SHA-256: `12626638b1abb5d57155345ee84e7e145dc13bfc947767f4484b1e18475cdce0`

## A.7 University template status

현재 원고는 `AUTHORITATIVE_DRAFT_V1` 내용 원본이며 university formatting status는 `CONTENT_COMPLETE_TEMPLATE_PENDING`이다. 학교/대학원 공식 Word 또는 LaTeX template, 표지 규정, 초록 순서, bibliography style, margin, chapter numbering, page limit, figure/table placement rule이 제공되면 별도의 presentation pass에서 적용한다. 이 과정에서 evidence number와 claim wording을 변경해서는 안 된다.
