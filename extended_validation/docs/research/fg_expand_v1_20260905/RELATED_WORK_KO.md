# 관련 CKKS 원문 검토와 최소 보강안

확인일: 2026-09-05. 최종 PDF 4쪽 §2.4와 참고문헌 [1]–[8]을 출발점으로 했다. 아래는 기술적 교집합과 평가 범위를 확인한 기록이며 신규 외부 compiler 성능 실험이 아니다. 검색 결과의 수집 날짜를 논문 발표일로 사용하지 않았다. 원문 PDF는 로컬 `work/fg_expand_v1_20260905/literature/`에서 확인했고, 취득 URL·버전별 hash는 `LITERATURE_FETCH*.json`에 남겼다. 전문을 새 GitHub에 재배포하지 않는다.

## 기존 인용의 확인

**CHET.** R. Dathathri, O. Saarikivi, H. Chen, K. Laine, K. Lauter, S. Maleki, M. Musuvathi, T. Mytkowicz, “CHET: An Optimizing Compiler for Fully-Homomorphic Neural-Network Inferencing,” PLDI 2019, pp. 142–156, DOI [10.1145/3314221.3314628](https://doi.org/10.1145/3314221.3314628). [공식 저자·발표 기록](https://www.microsoft.com/en-us/research/publication/chet-an-optimizing-compiler-for-fully-homomorphic-neural-network-inferencing/)으로 서지를 확인했다. 저자가 연결한 PLDI 전문 URL은 404, ACM PDF는 403이어서 **발표본 전문을 확보했다고 하지 않는다**. 별도로 읽은 [arXiv:1810.00845v1](https://arxiv.org/abs/1810.00845v1), 2018-10-01, 제목 “Compiler and Runtime for Homomorphic Evaluation of Tensor Programs”는 이전 판본이다. 그 §6–7의 사용자 정밀도 기반 N/Q 결정, 레이아웃 선택, MNIST LeNet·CIFAR SqueezeNet·비공개 산업 모델 평가를 2019판의 세부 수치로 이식하지 않는다. 기존 §2.4 인용은 유지하되 새로운 정량 비교는 보류한다. CHET가 정확성을 전혀 고려하지 않는다는 서술은 공식 설명과 맞지 않는다.

**EVA.** R. Dathathri, B. Kostova, O. Saarikivi, W. Dai, K. Laine, M. Musuvathi, “EVA: An Encrypted Vector Arithmetic Language and Compiler for Efficient Homomorphic Computation,” PLDI 2020, pp. 546–561, DOI [10.1145/3385412.3386023](https://doi.org/10.1145/3385412.3386023). 확인 전문은 [arXiv:1912.11951v2](https://arxiv.org/abs/1912.11951v2), 2020-06-26이다. §4와 §8, PDF 11–13쪽 Tables 3–5: 사용자 지정 scale, rescale/modswitch와 파라미터 결정, SEAL 3.3.1·128bit. LeNet 세 크기·산업 구조·SqueezeNet 등 다섯 구조를 평가한다. 분류 정확도는 전체 test, 그 밖의 DNN 측정은 첫 20입력 평균이고 batch=1이다. 첫 20 test로 scale을 정하는 절차도 명시되어 있어 우리 연구의 선택/별도 평가 분리와 같다고 보지 않는다. 산업 모델은 실제 가중치·시험자료가 없어 난수로 평가한다. “전체 test 정확도가 비슷함”은 개별 입력의 판정 동일성과 다른 지표다. §2.4 EVA 문단 및 §5.7 외부 비교의 측정 범위 설명에 활용한다.

**HECATE.** Y. Lee, S. Heo, S. Cheon, S. Jeong, C. Kim, E. Kim, D. Lee, H. Kim, “HECATE: Performance-Aware Scale Optimization for Homomorphic Encryption Compiler,” CGO 2022, pp. 193–204, DOI [10.1109/CGO53902.2022.9741265](https://doi.org/10.1109/CGO53902.2022.9741265). 확인 전문: [저자 연구실 PDF](http://www.corelab.or.kr/Pubs/cgo22_hecate.pdf). HTTPS 호스트 인증서 불일치와 실패 경로를 기록하고 공개 HTTP 전문을 읽었다. §VI–VII, PDF 7–9쪽 Tables II–III: scale/level 동시 관리, downscale와 비용 추정 탐색. **평가에서 36개 waterline을 시도해 허용 오차 한도 2^-8을 넘지 않는 최소 지연을 고른다.** 따라서 “오차를 검사하지 않는 비교법”으로 단순화할 수 없다. 여섯 응용, 회귀는 변수당 난수 16,384개·2/3 epoch, 영상 필터 64×64, DNN은 MNIST의 임의 입력이다. SEAL 3.5.9, 128bit, RMSE·추론 지연·탐색/컴파일 비용을 제시한다. 우리 기준은 관측된 입력별 마진과 판정에 연결되며 RMSE 한도와 동일하지 않다. §2.4 HECATE 설명에 활용한다.

**ELASM.** Y. Lee, S. Cheon, D. Kim, D. Lee, H. Kim, “ELASM: Error-Latency Aware Scale Management for Fully Homomorphic Encryption,” 32nd USENIX Security Symposium, 2023, pp. 4697–4714. [공식 발표·전문](https://www.usenix.org/conference/usenixsecurity23/presentation/lee-yongwoo). §5–7, PDF 11–14쪽 Figs. 11–15: 오차와 지연을 함께 추정하고 SNR 기반 scale 계획을 탐색한다. 7응용 계열·epoch를 구분한 10조건, 12,000개 탐색 표본, 회귀 변수당 16,384 난수, 64×64 영상, 기본 DNN은 MNIST 임의 입력. §7.4는 LeNet 분류 정확도와 1Gbps client/server 비용까지 평가한다. 이 사례의 평가 이미지 총수·키 반복 수는 해당 절에서 확인되지 않았다. “수치 오차만 고려하고 응용 정확성은 보지 않는다”는 서술은 부적절하다. 우리 연구의 입력별 판정·오차 수용 조건과 선택 후 별도 입력 재평가를 비교하되, ELASM 서비스 시간과 로컬 추론 시간을 한 표에 합산하지 않는다. §2.4 ELASM 문단을 보강한다.

**FHE-Agent.** N. Xu, Z. Gong, R. Ran, J. Tang, W. Wen, C. Ding, “FHE-Agent: Automating CKKS Configuration for Practical Encrypted Inference via an LLM-Guided Agentic Framework,” [arXiv:2511.18653v1](https://arxiv.org/abs/2511.18653v1), 2025-11-23 공개 전초본. PDF 6–7쪽 §5, Tables 1–2를 확인했다. 본문 머리글의 Conference’17 표기는 실제 출판 정보로 채택하지 않는다. 정적 분석·평문 근사·소수 암호화 평가·최종 암호화 평가를 구분하고, 정확도/MAE/유효 정밀도·보안 제약 아래 구성·packing·활성화 등을 탐색한다. 이 구조는 분석 후 실제 후보를 점검한다는 점에서 상당히 겹친다. MNIST MLP/LeNet/LoLa와 CIFAR-10 AlexNet, Orion+Lattigo 5.0.2 단일 thread, 입력당 시간은 키 생성 제외다. 검증 입력의 정확한 개수는 §5.1에서 확인되지 않는다. 학습된 controller 및 활성화 변경을 허용하는 범위를 우리 고정 평문 모델·고정 조정 규칙과 구분한다. 최종 전체 검증을 전혀 하지 않는다는 주장을 하지 않는다. §2.4 해당 문단에서 교집합을 명시한다.

**HEIR.** A. Ali, J. Choi, B. Gipson, S. Gorantala, J. Kun, W. Legiest, L. Lim, A. Viand, M. Zerihun Demissie, H. Zheng, “HEIR: A Universal Compiler for Homomorphic Encryption,” [arXiv:2508.11095v1](https://arxiv.org/abs/2508.11095v1), 2025-08-14 공개 전초본. PDF §3–6, 특히 §5 최적화와 §6 pipeline을 확인했다. 다양한 HE 중간 표현·pass·backend를 결합하는 기반이며 이 논문이 모든 모델에 동일한 판정 수용 검사를 제공한다는 뜻이 아니다. 본문에서 우리와 같은 고정 데이터/모델/키 반복의 판정률 표는 확인되지 않는다. 이를 0회 실패로 기입하지 않고 ‘공통 비교 표 미제공’으로 기록한다. 기존 PDF의 HEIR 단일 다항식 500입력 비교를 일반 신경망이나 native 시간 우월성으로 확대하지 않는다. §2.4 및 §5.7 지원 범위 설명에 활용한다.

## 추가 채택과 최신 후보의 검토

**Orion — 관련 연구 보강에 채택, 이번 실행 비교는 보류.** A. Ebel, K. Garimella, B. Reagen, “Orion: A Fully Homomorphic Encryption Framework for Deep Learning,” ASPLOS 2025, DOI [10.1145/3676641.3716008](https://doi.org/10.1145/3676641.3716008); 확인 전문 [arXiv:2311.03470v3](https://arxiv.org/abs/2311.03470v3), 2025-02-12. PDF 10–11쪽 §7·Table 2: PyTorch 출력과 암호화 출력, 정확도·평균 정밀도·회전·bootstrapping·시간을 함께 평가한다. MNIST 10,000, CIFAR-10 1,000, Tiny ImageNet 100, ImageNet은 자원 제한으로 1입력이다. 큰 모델을 포함하지만 모두 같은 검증 강도가 아니다. 자동 packing·bootstrap 배치·scale 관리와 우리 선택 수용 조건은 다른 층위다. Table 2의 정확도 변화가 작거나 같은 항목을 모든 입력 판정 일치로 읽지 않는다. 키 준비/암호화의 시간 포함 범위가 우리 지표와 완전히 같다고 확인하지 않았으므로 속도 수치를 직접 대조하지 않는다. 2026-02 저자 소개 글은 2025 논문의 설명이며 새 2026 논문으로 세지 않는다. §2.4의 FHE-Agent 앞뒤에 짧게 보강할 수 있다.

**El Bouabidi 등 2026 — 교집합 기록, 정량 인용·실행 비교 보류.** H. El Bouabidi, M. El Ghmary, S. E. Hebabaze, M. Amnai, “Machine learning-driven adaptive parameter selection for homomorphic encryption in edge computing,” Scientific Reports 16, 21594, 2026-05-12, DOI [10.1038/s41598-026-52587-4](https://www.nature.com/articles/s41598-026-52587-4). 출판사 전문의 식 (12), Experimental evaluation·Workload categories·Parameter selection distribution을 확인했다. 지연 예측과 정확성 제약을 이용한 20구성 선택이므로 관련성이 있다. 918행·5수치 특징에서 만든 60 workload(40/20), 10회 시간 반복을 명시한다. 다만 ‘computational accuracy’를 개별 분류 판정 일치로 동일시할 정의는 확인되지 않았다. 저강도 조건에 80bit를 쓰는 절과 전체 128bit 이상의 서술, Rule-Based의 N4096 설명과 뒤의 N8192/16384 선택 분포가 서로 맞지 않는 지점이 있다. 동일 보안·분모·모델 조건을 독립 확인하기 전 유리한 속도 수치를 인용하지 않는다. 이는 해당 논문의 모든 결과가 틀렸다는 판정이 아니다.

**최신이지만 현재 보강에서 제외/보류한 후보.** [pFedCKKS, arXiv:2606.08521](https://arxiv.org/abs/2606.08521)는 개인화 연합학습의 암호화 업데이트 집계가 중심이라 이번 고정 모델 추론 선택의 직접 비교에서 제외한다. 전문 검토를 완료한 채택 문헌으로 세지 않는다. [CHEHAB 공식 구현](https://github.com/Modern-Compilers-Lab/CHEHAB)은 현재 SEAL BFV를 지원한다고 명시하므로 이름이나 2026 발표만 보고 CKKS 비교 대상으로 설치하지 않는다. 최신 GPU 구현 소개 역시 현재 동일 CPU 백엔드 실험의 선행 과제가 아니다. 문헌 확인은 체계적 전수 문헌고찰을 완료했다는 주장이 아니다.

## 원고에 넣을 수 있는 짧은 문단 — 제안, 미적용

삽입 위치 A: **4쪽 §2.4의 HECATE·ELASM 설명 다음.**

> HECATE는 정해진 오차 한도를 만족하는 실행의 지연을 비교하며, ELASM은 수치 오차와 실행 비용의 관계를 탐색하고 분류 정확도도 평가한다. 본 연구는 이러한 평가와 구별하여, 각 입력의 판정 마진에 연결된 오차 조건과 평문·암호화 판정 일치를 실행 구성의 수용 조건으로 사용한다.

삽입 위치 B: **같은 절의 FHE-Agent 설명 다음.**

> FHE-Agent는 분석과 실제 암호화 평가를 단계적으로 결합하므로 본 연구와 구성 검증의 필요성을 공유한다. 본 연구에서는 평문 기준 모델과 조정 규칙을 고정하고, 선택에 사용하지 않은 입력과 새 키로 선택 결과를 다시 평가한다. Orion도 다양한 신경망에서 평문·암호화 출력과 정확도를 비교하므로, 평균 정확도의 유지와 입력별 판정 일치는 구분할 필요가 있다.

이는 원문을 베낀 인용이 아닌 신규 한국어 초안이다. 원고의 기존 용어·절 구조를 유지하며 삭제한 수식·알고리즘·내부 구현명·운영 유보 서술을 복원하지 않았다. 두 문단 모두 선택 조건의 차이를 설명할 뿐 최초성·전역 최적성·모든 미래 입력 보장을 선언하지 않는다.
