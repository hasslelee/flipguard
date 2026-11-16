# Step-0 재측정 규격: 상수의 암호문 스케일 인코딩

- Run ID: `scale_exact_step0_20261116`
- 작성 시각(UTC): 2026-11-16T04:10:07Z — 전체 실행 시작 전에 작성
- 소스 commit: `c754ca699eacd79c9da1afa07f218ec86845cb1c` (branch `claude/project-thread-kwt56m`)
- 실행 바이너리 SHA-256: `7f85ca259e2b7e3f0caa3519f1ea356de7540e67dc607086a163ef105e0f2aa2`
- 환경: 기존 V17과 같은 VM, GOMAXPROCS=6, taskset 0-5, 한 번에 CKKS 사례 하나

## 목적

V17 주요 평가의 다항식 모델에서 관측된 판정 변화가 CKKS 잡음이 아니라, 출력 상수(0.5)를 기본 스케일로
인코딩해 실제 스케일이 다른 암호문에 더할 때 생기는 고정 편향이라는 가설을 실제 실행으로 확인한다.

## 바꾸는 것 (한 가지)

`ConstantEncoding = ciphertext_scale`: 암호문에 더하는 평문 상수를 그 암호문의 실제 스케일로 인코딩한다
(`internal/ckksbackend/constant_encoding.go`). 기본값(빈 값)은 동결 실행과 같은 동작이다.

## 바꾸지 않는 것

Direct Policy V2, Security Policy V2, rho=0.5, delta=0.001, B=4, 키 세트 3, 조정 규칙(스케일 +4, Q 소수 +1),
모델·입력·분할(`results/model_family_expansion_v17/plaintext/primary`), 수용 조건. 동결 결과 폴더에는 쓰지 않는다.

## 범위

1. 주요 정형 65개 사례 전체를 `ciphertext_scale`로 선택 + 별도 입력 재평가.
2. 대조: 조합별 첫 분할 13개를 `default_scale`로 같은 바이너리에서 실행(동결 결과 재현 확인).
3. packed CNN-lite, MLP-100, LeNet-5-small은 실행 경로가 달라 이번 범위에 넣지 않는다.

## 실행 전 예측 (2026-11-16 보고서 2장)

- 스케일 20 다항식 초기 구성의 실제 판정 변화 횟수는 크게 줄어든다(편향 -0.0127 제거).
- 무작위 성분 표준편차가 약 0.0007~0.0008이므로 허용오차가 약 0.0005인 Digits·MNIST(짝홀) 다항식은
  수정 후에도 오차 조건 위반으로 거부될 가능성이 높다.
- MLP 40개 사례의 결과는 사실상 변하지 않는다.

## 미리 확인된 것

- `go test ./internal/ckksbackend -run TestConstantEncodingScaleMismatch -v`:
  스케일 20에서 최종 스케일/기본 스케일 = 1.02603, 스케일 24에서 0.95600 (예측과 일치).
- Banknote 다항식 fold 0 시험 실행(`smoke/`): default_scale 초기 거부 판정 변화 12·오차 위반 45,
  ciphertext_scale 초기 거부 판정 변화 0·오차 위반 4. 두 방식 모두 스케일 24 선택, 별도 입력 수용.
