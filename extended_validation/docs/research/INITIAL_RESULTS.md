# DeciProtect 초기 실행 결과

이 보고서는 기존 논문을 바꾸지 않는 새 연구의 첫 checkpoint다. 아래 파일럿, 합성 스트레스, 독립 위험 감사는 서로 다른 실험이며 한 성공률로 합치지 않는다.

## 신규 자료와 모델

공식 UCI 자료를 사용했다. Spambase 원본 4,601행은 특징 중복·상충 레이블 처리 후 4,204행이다. 학습/개발/보정/평가는 seed별 2,102/630/630/842행이다. Wine은 178행이며 89/26/27/36행이다. 세 seed의 분할은 서로 겹칠 수 있으므로 독립된 새 데이터셋 세 개로 세지 않는다.

선형 logistic 분류기와 hidden 12의 square MLP를 각각 학습했다. square MLP의 200회 L-BFGS-B는 여섯 사례 모두 수렴 조건에 도달하지 못했다. 결과를 삭제하지 않았으며, 완전히 수렴한 최종 모델이라고 표현하지 않는다. 평문 accuracy는 아래 표와 raw 결과에 기록했다.

## 정규 입력 파일럿

| Dataset / model | Cases | Mean returned fraction | Returned flip events | Low / high timing interpretation |
|---|---:|---:|---:|---|
| spambase / logistic_linear | 3 | 1.0000 | 0 | Descriptive shared-VM measurements |
| spambase / square_mlp12 | 3 | 1.0000 | 0 | Descriptive shared-VM measurements |
| wine / logistic_linear | 3 | 0.0000 | 0 | Descriptive shared-VM measurements |
| wine / square_mlp12 | 3 | 0.0000 | 0 | Descriptive shared-VM measurements |

Spambase의 고정 저정밀도 선형 모델에서는 총 3회의 판정 반전이 관측됐고, 두 단계 방식은 842입력×6모델-seed 사례의 모든 입력을 세 키 실행에서 반환하면서 반전 0회를 보였다. 이는 5,052개의 독립 원자료가 아니라 5,052개 사례-입력 쌍이며, 반복 키를 포함하면 15,156개 관측이다. 고정 30비트 대조군도 이 자료에서 반전이 없었다.

Wine은 보정 입력 27개로 97.5% order statistic의 요구 순위 28을 만족하지 못해 구간을 무한대로 두고 모두 유보했다. 반전 0회를 성공으로 계산하지 않는다. 입력을 숨기거나 alpha를 완화해서 결과를 개선하지 않았다.

초기 DP_PILOT_V1의 18비트 square MLP 여섯 사례는 logN=13에서 필요한 18비트 소수 3개를 만들지 못해 암호화 전에 실패했다. 그 기록을 보존했다. V1A에서는 암호화 결과와 무관한 생성 제약에 따라 MLP의 낮은 scale을 22로 정했다. 선형 모델의 재실행은 새로운 독립 과학적 증거로 합산하지 않는다.

## 비용상의 음성 결과

재계산 대상 입력이 적어도, 현재 feature-ciphertext 배치 실행의 비용은 입력 수에 비례해 줄지 않았다. Spambase 선형 세 사례의 평균 배치 시간은 두 단계 방식 약 297–305ms, 고정 30비트 약 201–211ms였다. MLP는 양쪽 logN이 같아 낮은 scale의 이점도 작았다. 따라서 현재 naive cascade의 일반적인 속도 우월성 가설은 지지되지 않는다. 시간은 archive 작업과 공유 VM에서 수집한 기술적 수치이며 정식 성능 검정이 아니다.

## 경계와 분포 이동 스트레스

| Case | Inputs | Low flips / key observations | High flips | Cascade flips | Cascade coverage |
|---|---:|---:|---:|---:|---:|
| logistic_linear__20260905__boundary | 224 | 235/672 | 65 | 3 | 0.5997 |
| logistic_linear__20260905__shift_sigma05 | 256 | 3/768 | 0 | 0 | 1.0000 |
| square_mlp12__20260905__boundary | 224 | 204/672 | 74 | 0 | 0.5729 |
| square_mlp12__20260905__shift_sigma05 | 256 | 0/768 | 0 | 0 | 1.0000 |

합성 경계 입력에는 정답 레이블이 없다. 표는 고정된 평문 모델과의 일치만 뜻한다. 선형 모델 경계 스트레스에서 반환된 판정에도 3회의 오류가 존재한다. 표본 기반 오차 구간은 전역적인 결정 보존 certificate가 아니다. 이 결과를 이용한 보정값 재조정은 하지 않았다.

## 독립 입력·키 600회 감사

대상 모집단은 정규 입력 842행과 합성 경계 224행, 이동 입력 256행으로 미리 고정한 1,322행의 균등 분포다. 여기서 복원 추출한 입력과 새로운 키·암호화 난수를 매회 사용했다. 600회 중 567회 반환, 33회 유보, 반환 판정 오류 0회였다. 관측 반환율은 94.5%다.

같은 600회에서 고정 저정밀도는 29회 판정이 달랐다. 이 중 12회는 고정밀도 재계산 후 올바른 기준 판정으로 반환했고, 17회는 유보했다.

두 주장에 Bonferroni 보정한 가족 신뢰수준 95%에서 joint 위험의 단측 상한은 0.00612927, 반환 조건부 위험의 상한은 0.00648484이다. 둘 다 사전 목표 0.01을 통과했다. 시행 600개에서 뽑힌 고유 모집단 index는 502개이며, 중복 추출은 이 유한 모집단 확률 실험의 일부다.

**허용 주장:** 고정한 유한 모집단·모델·단일입력 실행·키 분포에서 두 위험 목표에 대한 감사가 통과했다. **허용하지 않는 주장:** 새로운 실제 스팸 분포에서 1% 보장, 모든 입력 무반전, packed batch에서 같은 보장, 암호학적 안전성 또는 정답 정확도 보장.

## 결과로 정해진 다음 연구

위험 제어와 유보 규칙의 실증은 시작됐지만 비용 이점은 미해결이다. 다음 단계는 같은 모델·키 영역에서의 재계산 batching과 queue 비용, 충분한 새 calibration 자료, 시간/도메인 이동, 강한 대조군과 독립 환경이다. 이는 새 protocol에서 수행하며 현재 결과를 덮어쓰지 않는다.

표 원본: PILOT_TABLE.csv, STRESS_TABLE.csv, SAMPLE_COMPLEXITY.csv. 검증: VERIFICATION.json. 프로토콜과 raw 결과는 각각 protocols/와 results/에 있다.
