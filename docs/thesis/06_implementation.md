# 제6장 구현

## 6.1 구현 개요

FlipGuard는 Go로 작성한 CKKS 실행·직접 합성 구성요소, Python으로 작성한 artifact 준비·분석·evidence builder·verifier, Bash suite orchestrator로 구성된다. 암호화 실행은 Lattigo v6.2.0을 사용한다. 최종 confirmatory run manifest가 기록한 환경은 Go 1.25.9, Ubuntu 24.04.4 LTS, Linux x86-64 VMware 가상 환경, 약 16 GB 메모리다. Python은 dataset materialization, manifest construction, 통계 및 deterministic artifact build를 담당한다.

구현을 파일 목록보다 책임 경계로 나누면 네 계층이다. 첫째, **contract layer**는 model/input/graph/policy identity를 정규화한다. 둘째, **synthesis and execution layer**는 graph fact를 literal로 변환하고 Lattigo object를 생성해 candidate를 실행한다. 셋째, **assurance layer**는 security, decision certificate, repair, locked replay를 수행한다. 넷째, **evidence layer**는 ledger와 manifest를 freeze하고 verifier와 paper artifact를 생성한다.

## 6.2 Graph contract와 adapter

각 adapter는 model artifact에서 computation formula를 읽고 operation trace를 canonical graph signature로 내보낸다. Primary graph는 `linear_poly3`와 `mlp_square_linear_score` 두 종류며, 5개 dataset은 `banknote`, `digits_binary`, `iris_binary`, `mnist_pool16`, `wdbc`다. `mlp_square_poly3`는 추가 polynomial stage를 포함한 structural holdout이다. Non-tabular adapter는 BSDS500에서 추출한 Sobel patch, Harris window, MNIST 0-vs-1 CNN-lite graph를 scalar-replicated 방식으로 실행한다 [@martin2001bsds; @lecun1998gradient].

Adapter contract는 graph depth뿐 아니라 formula version과 extraction policy digest를 포함한다. 새로운 operation support는 adapter version을 추가하는 방식으로 구현되며 Direct Policy V2의 scale/repair 상수를 바꾸지 않는다. 이 구조 때문에 structural 및 non-tabular holdout 결과를 본 뒤 primary policy를 retune하지 않고도 지원 범위를 확장할 수 있었다.

## 6.3 Candidate materialization

Synthesizer output은 symbolic profile이 아니라 exact literal이다. JSON에는 LogN, 각 Q prime의 bit target과 concrete prime, P prime, default scale, path, candidate digest가 기록된다. Materializer는 Lattigo parameter literal을 생성한 뒤 실제 `LogQ`, `LogP`, `LogQP`를 다시 계산한다. 선언값과 concrete object가 다르면 실행 전에 실패한다.

Catalog candidate도 같은 literal schema로 정규화한다. Profile과 path mapping은 candidate identity에 포함되고 Security-V2 excluded 여부가 표시된다. Reference candidate `deep_chain_8_scale45__rescale_aware` 역시 security admission과 decision certificate를 workload별로 별도 기록한다. Security PASS만으로 SAFE reference라 부르지 않으며, formal safe-to-safe comparison에는 decision SAFE인 row만 허용한다.

## 6.4 Lattigo execution과 key repetition

Candidate runner는 parameter literal로 context, encoder, encryptor, decryptor, evaluator와 evaluation key를 생성한다. Input scalar를 지정 slot에 복제해 encode/encrypt하고 graph operation을 실행한 뒤 decrypt/decode한다. 각 trial은 독립된 fresh key material로 {{N:fresh_key_repeats}}번 반복한다. 이 반복은 같은 model artifact의 독립 학습을 의미하지 않으며 encryption randomness와 key material 변화에 대한 관측이다.

Execution ledger는 candidate trial과 key run을 분리한다. Sample row에는 source row ID, key repeat, plaintext score, CKKS score, absolute error, threshold, margin, budget, utilization, decisions, flip과 violation을 저장한다. Candidate summary는 max error와 max utilization만으로 raw row를 대체하지 않는다. Failure analysis가 필요한 경우 원 ledger에서 특정 sample과 key repeat를 재구성할 수 있다.

## 6.5 Security gate 구현

Security gate는 policy JSON에서 LogN별 cap과 runtime distribution metadata를 읽는다. Ciphertext-Q admission은 `LogQ`를 cap과 비교하고, evaluation-key-QP admission은 `LogQP`를 비교한다. Candidate가 실제로 evaluation key를 필요로 하면 두 검사 모두 PASS여야 final admission이 PASS다. Headroom은 cap에서 object modulus bit 크기를 뺀 값으로 기록한다.

Static re-attestation은 direct-selected {{N:security_direct_pass}}개 row, distinct direct literal, catalog {{N:security_catalog_profiles_total}} profile, profile/path identity, reference, latency arm을 machine-readable CSV/JSON으로 재생했다. Catalog의 {{N:security_catalog_profiles_excluded}}개 profile은 Security-V2에서 제외되었고 {{N:security_catalog_profiles_admitted}}개만 formal comparison에 남았다. Exact estimator artifact는 exact Q/P prime과 {{N:security_estimator_models}}개 cost model에서 object를 평가하지만, Lattigo `Xe`의 finite bound가 estimator distribution과 완전히 같지 않음을 manifest에 기록한다.

## 6.6 Failure classifier와 repair executor

Execution failure는 reason code로 분류된다. Numerical reject는 실행은 성공했지만 reserve-policy violation이 있는 경우다. Level failure는 graph가 필요한 level을 소진한 경우다. NTT-prime materialization failure는 요청 bit 크기에 적합한 concrete prime 생성 문제다. Provenance mismatch, unsupported graph, Security-V2 inadmission은 repair할 수 없는 integrity class다.

Repair executor는 policy JSON에 있는 transition만 수행한다. Numerical repair는 scale-related bit를 {{N:numerical_repair_scale_bits}}만큼 증가시키고, level repair는 Q prime {{N:level_repair_q_primes}}개를 추가한다. 각 transition은 parent candidate digest와 cause를 ledger에 남긴다. Maximum trial {{N:max_encrypted_trials}}번 또는 maximum additional level에 도달하면 종료한다. Mutable default를 CLI에 따로 두지 않고 모든 component가 동일 policy digest를 요구한다.

## 6.7 Locked audit runner

Locked audit runner의 input은 selection result와 audit artifact뿐이다. Candidate generator interface를 link하지 않도록 실행 path를 분리하고, selection literal digest와 audit materialization literal digest를 비교한다. Model/source/candidate digest가 다르면 결과를 만들지 않는다. Audit에서는 fresh key {{N:fresh_key_repeats}}개를 생성하지만 literal parameter는 변경하지 않는다.

Retuning count는 manifest의 정책 선언과 실행 log 양쪽에서 확인한다. Audit 결과를 보고 후속 candidate가 생성된 흔적, repair event, policy digest 변경이 있으면 verifier가 실패한다. Primary audit {{N:combined_descriptive_instances}}건의 retuning count는 {{N:primary_locked_audit_retuning}}이었고, structural audit {{N:structural_instances}}건의 retuning count도 {{N:structural_retuning}}이었다.

## 6.8 Paired latency runner

Paired latency runner는 direct-selected, Security-V2 bounded-catalog fastest-safe, fixed reference의 {{N:paired_arms}}개 arm을 frozen identity로 받는다. Workload마다 warm-up {{N:paired_warmup_runs}}회 후 measurement run {{N:paired_measurement_runs}}회를 수행하고, arm 순서는 balanced cyclic 및 reverse 규칙으로 배치한다. Outlier를 제거하지 않으며 setup/keygen, evaluation-only, total latency를 분리한다. Process restart, arm position, workload order와 host metadata를 ledger에 저장한다.

총 {{N:combined_descriptive_instances}} workload-partition instance에서 {{N:paired_arms}}개 arm, {{N:paired_measurement_runs}}회 measurement run, workload당 {{N:paired_rows_per_workload}}개 측정 row가 결합되어 `{{N:combined_descriptive_instances}} x {{N:paired_arms}} x {{N:paired_measurement_runs}} x {{N:paired_rows_per_workload}} = {{N:paired_raw_records|,}}` latency record가 생성되었다. Setup/evaluation/total은 각 record의 분리된 측정 열이며 별도 record로 세지 않는다. 분석기는 raw record를 독립 표본으로 취급하지 않고 {{N:primary_dataset_model_clusters}} dataset-model cluster를 primary inference unit으로 사용한다. Seed 0는 descriptive output으로, seeds 1--4는 confirmatory output으로 분리한다.

## 6.9 Evidence freezer와 verifier

Evidence freezer는 source artifact를 snapshot하고 manifest에 relative path와 digest를 기록한다. Pack root의 SHA256SUMS는 manifest 자체를 제외하거나 포함하는 규칙을 schema에서 명시하며, verifier는 예상 파일 집합과 checksum을 비교한다. Frozen pack 뒤에 새로운 해석이 필요하면 기존 파일을 수정하지 않고 overlay pack을 만든다. Security re-attestation, validation identity v2, margin utilization, paired latency admission, paper claim admission이 이 방식으로 구축되었다.

Verifier는 단순 파일 존재 검사보다 의미 조건을 확인한다. 예를 들어 trial-reduction verifier는 formal denominator가 {{N:formal_catalog_all}}/{{N:formal_catalog_confirmatory}}인지, {{N:raw_historical_catalog_executions|,}}이 headline denominator로 사용되지 않는지 검사한다. Structural verifier는 {{N:structural_audit_pass}} PASS와 {{N:structural_reserve_reject}} REJECT가 모두 있어야 통과하며 negative row 삭제를 실패로 처리한다. Claim registry는 admitted 문장과 prohibited overclaim을 분리하고 paper builder는 admitted claim만 소비한다.

## 6.10 RC2 reproducibility artifact

최종 연구 배포 기준은 tag `flipguard-thesis-v1.0.0-rc2`, source commit `6c5f8b234f9f9da91a189fa0f2dc180bb996abf5`다. RC2 archive SHA-256은 `05ef70306a11ab577243b0c708489864f19ccd104e6036e28fc6bd1dab45c0be`다. RC2는 RC1 이후 OpenML server-gzip transport를 byte-identical replay로 보존하는 release repair만 포함하고, encrypted result, claim, policy, Paper Artifacts V3를 변경하지 않는다.

RC2 binding overlay는 V10 core-completion checkpoint, V3 publication input, paper claim admission manifest와 RC2 source/archive/tag를 결합한다. 논문은 이 overlay를 최종 배포 기준으로 사용한다. Raw MNIST와 BSDS500 같은 외부 dataset은 license 조건에 따라 archive에 임의 포함하지 않고 source URL, expected digest, fetch 및 extraction rule을 제공한다.

## 6.11 Packing과 구현 범위

Primary 및 extension implementation은 scalar-replicated packing을 중심으로 한다. 이는 graph semantics와 decision error를 명확히 추적하는 데 유리하지만 SIMD slot 활용을 극대화한 production inference와는 다르다. CNN-lite는 학습된 MNIST binary graph를 지원하지만 packed convolution, general LeNet, multiclass encrypted argmax를 구현하지 않는다. Sobel과 Harris도 전체 이미지 처리 throughput 또는 vision task accuracy가 아니라 선언된 patch/window score의 threshold decision을 평가한다.

이 범위는 latency 해석에도 영향을 준다. Paired direct/catalog 비교는 동일 scalar-replicated workload와 host 안에서 유효하지만, batch packing을 사용하는 서비스로 외삽할 수 없다. 구현의 목적은 decision-integrity layer와 evidence protocol을 검증하는 것이며, 모든 FHE compiler optimization을 포함하는 완성형 runtime을 만드는 것이 아니다.
