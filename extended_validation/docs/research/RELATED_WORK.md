# 선행 연구와 확장 위치

2026-09-05에 아래 저자·학회·기관의 원자료를 확인했다. 이는 초기 문헌 검토이며
완전한 선행연구 전수조사나 DeciProtect의 최초성 증명이 아니다.

| Source | What it establishes | DeciProtect comparison requirement |
|---|---|---|
| [ELASM, USENIX Security 2023](https://www.usenix.org/conference/usenixsecurity23/presentation/lee-yongwoo) | CKKS의 오차·지연시간을 함께 고려하는 scale 관리 | 단순 MSE 대조군만으로 기존 기술 전체보다 우수하다고 결론 내리지 않는다 |
| [AutoFHE, USENIX Security 2024](https://www.usenix.org/conference/usenixsecurity24/presentation/ao) | CNN의 다항식 변환과 accuracy/latency trade-off | 원래 모델과 암호화용 변환 모델의 결정 차이를 별도 측정한다 |
| [FHE-Agent, arXiv:2511.18653](https://arxiv.org/abs/2511.18653) | CKKS 구성 생성과 단계별 수정 자동화 | 자동 생성·실패 후 수정만으로 차별성을 주장하지 않는다 |
| [HEIR, arXiv:2508.11095](https://arxiv.org/abs/2508.11095) | 여러 HE 최적화를 결합·비교하는 compiler 기반 | backend 비교에서 그래프, 출력 의미, 보안과 packing을 맞춘다 |
| [Conformal Risk Control](https://arxiv.org/abs/2208.02814) | 단조 loss에 대한 기대 위험 제어 | 오차 quantile을 쓰는 것만으로 새 키·분포 이동에서 보장하지 않는다 |
| [Learn then Test](https://arxiv.org/abs/2110.01052) | 여러 후보에 대한 통계적 위험 검정을 통한 calibration | 튜닝과 독립 위험 평가를 분리하고 다중 비교를 보정한다 |
| [HE Security Guidelines](https://cic.iacr.org/p/1/4/26) | 분포와 공격 모델에 의존하는 구현용 보안 파라미터 지침 | Q와 QP, 비밀키·오차분포, 실제 파라미터를 결속한다 |

DeciProtect의 연구 가설은 **주어진 CKKS 평문 기준의 결정을 유지하는 데 필요한
반환 규칙과 비용을 함께 설계하는 것**이다. 위험 제어나 interval gate 자체를 새로운
이론으로 제시하는 것이 아니라, 암호키·packing·재계산·클라이언트/서버 경계를
고려했을 때도 통계적 의미와 비용상의 이점이 유지되는지 검증한다.

새로운 실험 자료의 출처는 [UCI Spambase](https://archive.ics.uci.edu/dataset/94/spambase)와
[UCI Wine](https://archive.ics.uci.edu/dataset/109/wine)이다. 공식 zip을 직접 받아
해시와 제거된 중복/충돌 행을 기록했다. Spambase는 오래된 스팸 자료이며 현대 네트워크
침입 탐지의 대표라고 주장하지 않는다. Wine은 큰 표본의 증거가 아니라 부족한 calibration
표본에서 유보 동작을 확인하는 대조군으로 사용한다.

후속 자료는 [credit default](https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients),
[Fashion-MNIST](https://github.com/zalandoresearch/fashion-mnist),
[UNSW-NB15](https://research.unsw.edu.au/projects/unsw-nb15-dataset),
[CIC-IDS2017](https://www.unb.ca/cic/datasets/ids-2017.html)를 우선 검토한다.
마지막 자료는 날짜·공격 시나리오가 구조화돼 있어 무작위 행 분할과 시간 분할을
구분할 이유가 있다. 단순히 데이터를 많이 추가하는 대신 누수 방지와 도메인 이동을
검증하는 데 사용한다. 아직 이 자료들의 새 CKKS 실험을 완료하지 않았다.
