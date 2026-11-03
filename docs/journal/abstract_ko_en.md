# 국문 요약

CKKS 동형암호의 구성은 계산 그래프를 실행할 수 있을 뿐 아니라 근사 오차가 최종 결정을 바꾸지 않도록 선택되어야 한다. 본 논문은 계산 그래프와 결정 무결성 계약으로부터 CKKS literal을 직접 합성하고, 제한된 암호화 검증과 bounded repair를 거쳐 SAFE, REJECTED, FAILED 또는 NO_SAFE를 판정하는 FlipGuard를 제안한다. Controlled Primary에서 direct trial은 Security-V2 bounded catalog 대비 70/700 및 confirmatory 56/560으로 90% 감소했고, confirmatory locked audit 40/40을 retuning 없이 통과했다. Catalog/direct total-latency ratio의 cluster geometric mean은 3.140660(95% CI 2.342334-4.215313)이었다. MNIST MLP-100과 LeNet-5-small은 각각 500개 validation과 500개 audit 영상에서 argmax flip 없이 SAFE였다. MLP의 natural top-two-gap 계약은 S32 대신 S29 literal을 생성했지만 두 literal의 latency 차이는 관측되지 않았다. 결과는 유한 입력, 지원 adapter, 한 host 및 명시적 보안 모델 범위에 한정된다.

**주요어:** CKKS, 동형암호, 결정 무결성, 구성 합성, 암호화 추론

# English abstract

CKKS configuration selection must support the computation graph while
controlling approximation error so that the final decision is preserved.
This paper presents FlipGuard, which directly synthesizes a CKKS literal from
a computation graph and a decision-integrity contract, evaluates it through a
bounded number of encrypted trials and failure-aware repairs, and returns SAFE,
REJECTED, FAILED, or NO_SAFE. In the Controlled Primary study, FlipGuard used
70 trials against 700 Security-V2 bounded-catalog candidates overall and 56
against 560 in the confirmatory partitions, a 90% reduction in both cases. All
40 confirmatory selected literals passed a no-retuning locked audit. The
dataset-model-cluster geometric mean of catalog total latency divided by direct
total latency was 3.140660 (95% CI: 2.342334-4.215313). On MNIST MLP-100 and
FHE-compatible LeNet-5-small, the selected literals were SAFE with zero argmax
flips on disjoint 500-image validation and 500-image audit sets. The natural
top-two-gap contract changed the MLP literal from S32 to S29, although the
paired latency interval showed no S29-over-S32 advantage. The claims are
limited to finite declared inputs, supported adapters, one measured host, and
explicit security models.

**Keywords:** CKKS, homomorphic encryption, decision integrity, configuration synthesis, encrypted inference
