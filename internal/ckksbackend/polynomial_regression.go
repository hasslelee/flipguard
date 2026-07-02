package ckksbackend

import (
	"fmt"
	"math"

	"github.com/hasslelee/flipguard/internal/benchmarks"
	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// PolynomialRegressionProbeCase defines one encrypted polynomial regression
// input sample.
type PolynomialRegressionProbeCase struct {
	X float64
}

// PolynomialRegressionProbeResult records CKKS evaluation behavior for:
//
// y = 0.12 + 0.70*x - 0.25*x^2 + 0.11*x^3 - 0.035*x^4 + 0.006*x^5
type PolynomialRegressionProbeResult struct {
	X float64

	Threshold float64

	PlainY float64
	CKKSY  float64

	AbsError float64

	PlainDecision bool
	CKKSDecision  bool
	DecisionFlip  bool

	X2Value float64
	X3Value float64
	X4Value float64
	X5Value float64

	InitialLevel int
	X2Level      int
	X3Level      int
	X4Level      int
	X5Level      int
	YLevel       int

	XDegree  int
	X2Degree int
	X3Degree int
	X4Degree int
	X5Degree int
	YDegree  int

	LogDefaultScale int
}

// DefaultPolynomialRegressionProbeCases returns deterministic scalar samples.
func DefaultPolynomialRegressionProbeCases() []PolynomialRegressionProbeCase {
	samples := benchmarks.GeneratePolynomialRegressionSamples(
		benchmarks.DefaultPolynomialRegressionBoundaryOptions(),
	)

	if len(samples) == 0 {
		samples = benchmarks.DefaultPolynomialRegressionSamples()
	}

	// Keep the first CKKS probe small. The plain benchmark can generate many
	// samples, but encrypted execution is intentionally bounded here.
	maxCases := 16
	if len(samples) > maxCases {
		samples = samples[:maxCases]
	}

	cases := make([]PolynomialRegressionProbeCase, 0, len(samples))
	for _, sample := range samples {
		cases = append(cases, PolynomialRegressionProbeCase{
			X: sample.X,
		})
	}

	return cases
}

// RunPolynomialRegressionProbe executes all default encrypted polynomial
// regression cases.
func (c Context) RunPolynomialRegressionProbe() ([]PolynomialRegressionProbeResult, error) {
	cases := DefaultPolynomialRegressionProbeCases()
	results := make([]PolynomialRegressionProbeResult, 0, len(cases))

	for i, probeCase := range cases {
		result, err := c.RunPolynomialRegressionProbeCase(probeCase)
		if err != nil {
			return nil, fmt.Errorf("run polynomial regression probe case %d: %w", i, err)
		}

		results = append(results, result)
	}

	return results, nil
}

// RunPolynomialRegressionProbeCase evaluates the fixed polynomial regression
// benchmark using CKKS.
func (c Context) RunPolynomialRegressionProbeCase(
	probeCase PolynomialRegressionProbeCase,
) (PolynomialRegressionProbeResult, error) {
	encoder := ckks.NewEncoder(c.Params)

	kgen := ckks.NewKeyGenerator(c.Params)
	sk, pk := kgen.GenKeyPairNew()
	rlk := kgen.GenRelinearizationKeyNew(sk)

	encryptor := ckks.NewEncryptor(c.Params, pk)
	decryptor := ckks.NewDecryptor(c.Params, sk)

	relinEvaluator := ckks.NewEvaluator(c.Params, rlwe.NewMemEvaluationKeySet(rlk))

	xCipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.X)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("encrypt x: %w", err)
	}

	x2Cipher, err := relinEvaluator.MulNew(xCipher, xCipher)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("multiply x by x: %w", err)
	}

	x2Cipher, err = relinEvaluator.RelinearizeNew(x2Cipher)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("relinearize x2: %w", err)
	}

	x3Cipher, err := relinEvaluator.MulNew(x2Cipher, xCipher)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("multiply x2 by x: %w", err)
	}

	x3Cipher, err = relinEvaluator.RelinearizeNew(x3Cipher)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("relinearize x3: %w", err)
	}

	x4Cipher, err := relinEvaluator.MulNew(x2Cipher, x2Cipher)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("multiply x2 by x2: %w", err)
	}

	x4Cipher, err = relinEvaluator.RelinearizeNew(x4Cipher)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("relinearize x4: %w", err)
	}

	x5Cipher, err := relinEvaluator.MulNew(x4Cipher, xCipher)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("multiply x4 by x: %w", err)
	}

	x5Cipher, err = relinEvaluator.RelinearizeNew(x5Cipher)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("relinearize x5: %w", err)
	}

	t1, err := relinEvaluator.MulNew(xCipher, 0.70)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("multiply x by 0.70: %w", err)
	}

	t2, err := relinEvaluator.MulNew(x2Cipher, -0.25)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("multiply x2 by -0.25: %w", err)
	}

	t3, err := relinEvaluator.MulNew(x3Cipher, 0.11)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("multiply x3 by 0.11: %w", err)
	}

	t4, err := relinEvaluator.MulNew(x4Cipher, -0.035)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("multiply x4 by -0.035: %w", err)
	}

	t5, err := relinEvaluator.MulNew(x5Cipher, 0.006)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("multiply x5 by 0.006: %w", err)
	}

	sum12, err := relinEvaluator.AddNew(t1, t2)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("add t1 and t2: %w", err)
	}

	sum123, err := relinEvaluator.AddNew(sum12, t3)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("add t3: %w", err)
	}

	sum1234, err := relinEvaluator.AddNew(sum123, t4)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("add t4: %w", err)
	}

	sum12345, err := relinEvaluator.AddNew(sum1234, t5)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("add t5: %w", err)
	}

	biasPlaintext, err := c.encodeReplicatedPlaintextAtLevel(encoder, 0.12, sum12345.Level())
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("encode polynomial regression bias plaintext: %w", err)
	}

	yCipher, err := relinEvaluator.AddNew(sum12345, biasPlaintext)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("add polynomial regression bias: %w", err)
	}

	yDecoded, err := c.decryptFirstSlot(encoder, decryptor, yCipher)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("decrypt y: %w", err)
	}

	x2Decoded, err := c.decryptFirstSlot(encoder, decryptor, x2Cipher)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("decrypt x2: %w", err)
	}

	x3Decoded, err := c.decryptFirstSlot(encoder, decryptor, x3Cipher)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("decrypt x3: %w", err)
	}

	x4Decoded, err := c.decryptFirstSlot(encoder, decryptor, x4Cipher)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("decrypt x4: %w", err)
	}

	x5Decoded, err := c.decryptFirstSlot(encoder, decryptor, x5Cipher)
	if err != nil {
		return PolynomialRegressionProbeResult{}, fmt.Errorf("decrypt x5: %w", err)
	}

	plainY := benchmarks.EvalPolynomialRegressionPlain(probeCase.X)
	threshold := benchmarks.PolynomialRegressionThreshold

	plainDecision := plainY >= threshold
	ckksDecision := yDecoded >= threshold

	return PolynomialRegressionProbeResult{
		X: probeCase.X,

		Threshold: threshold,

		PlainY: plainY,
		CKKSY:  yDecoded,

		AbsError: math.Abs(yDecoded - plainY),

		PlainDecision: plainDecision,
		CKKSDecision:  ckksDecision,
		DecisionFlip:  plainDecision != ckksDecision,

		X2Value: x2Decoded,
		X3Value: x3Decoded,
		X4Value: x4Decoded,
		X5Value: x5Decoded,

		InitialLevel: c.MaxLevel(),
		X2Level:      x2Cipher.Level(),
		X3Level:      x3Cipher.Level(),
		X4Level:      x4Cipher.Level(),
		X5Level:      x5Cipher.Level(),
		YLevel:       yCipher.Level(),

		XDegree:  xCipher.Degree(),
		X2Degree: x2Cipher.Degree(),
		X3Degree: x3Cipher.Degree(),
		X4Degree: x4Cipher.Degree(),
		X5Degree: x5Cipher.Degree(),
		YDegree:  yCipher.Degree(),

		LogDefaultScale: c.LogDefaultScale(),
	}, nil
}
