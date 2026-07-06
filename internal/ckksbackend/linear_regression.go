package ckksbackend

import (
	"fmt"
	"math"

	"github.com/hasslelee/flipguard/internal/benchmarks"
	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// LinearRegressionProbeCase defines one encrypted linear regression probe input.
type LinearRegressionProbeCase struct {
	X1 float64
	X2 float64
	X3 float64
	X4 float64
}

// LinearRegressionProbeResult records encrypted evaluation behavior for:
//
// y = 0.35*x1 - 0.20*x2 + 0.15*x3 + 0.10*x4 - 0.05
type LinearRegressionProbeResult struct {
	X1 float64
	X2 float64
	X3 float64
	X4 float64

	Threshold float64

	PlainY float64
	CKKSY  float64

	AbsError float64

	PlainDecision bool
	CKKSDecision  bool
	Flip          bool

	T1Value float64
	T2Value float64
	T3Value float64
	T4Value float64

	InitialLevel int
	X1Level      int
	X2Level      int
	X3Level      int
	X4Level      int
	YLevel       int

	X1Degree int
	X2Degree int
	X3Degree int
	X4Degree int
	YDegree  int

	LogDefaultScale int
}

// DefaultLinearRegressionProbeCases returns deterministic non-exact-boundary
// samples for CKKS evaluation.
//
// Exact-boundary cases are intentionally avoided here because tiny CKKS
// approximation noise around y=0 can turn them into expected uncertified cases.
// Boundary-focused samples are still available in the benchmark generator.
func DefaultLinearRegressionProbeCases() []LinearRegressionProbeCase {
	return []LinearRegressionProbeCase{
		// Near-boundary positive and negative cases.
		{X1: 0.15, X2: 0.0, X3: 0.0, X4: 0.0},
		{X1: 0.13, X2: 0.0, X3: 0.0, X4: 0.0},

		// Positive side.
		{X1: 1.0, X2: 0.0, X3: 0.5, X4: 0.0},
		{X1: 0.5, X2: -0.5, X3: 0.25, X4: 0.75},
		{X1: 2.0, X2: -1.0, X3: 1.0, X4: 1.0},

		// Negative side.
		{X1: 0.0, X2: 1.0, X3: 0.0, X4: 0.0},
		{X1: -1.0, X2: 0.5, X3: 0.0, X4: -0.5},
		{X1: -2.0, X2: 1.0, X3: -1.0, X4: 0.0},
	}
}

// RunLinearRegressionProbe executes all default encrypted linear regression
// probe cases.
func (c Context) RunLinearRegressionProbe() ([]LinearRegressionProbeResult, error) {
	cases := DefaultLinearRegressionProbeCases()
	results := make([]LinearRegressionProbeResult, 0, len(cases))

	for i, probeCase := range cases {
		result, err := c.RunLinearRegressionProbeCase(probeCase)
		if err != nil {
			return nil, fmt.Errorf("run linear regression probe case %d: %w", i, err)
		}

		results = append(results, result)
	}

	return results, nil
}

// RunLinearRegressionProbeCase evaluates:
//
// y = 0.35*x1 - 0.20*x2 + 0.15*x3 + 0.10*x4 - 0.05
//
// using CKKS.
func (c Context) RunLinearRegressionProbeCase(
	probeCase LinearRegressionProbeCase,
) (LinearRegressionProbeResult, error) {
	encoder := ckks.NewEncoder(c.Params)

	kgen := ckks.NewKeyGenerator(c.Params)
	sk, pk := kgen.GenKeyPairNew()
	rlk := kgen.GenRelinearizationKeyNew(sk)

	encryptor := ckks.NewEncryptor(c.Params, pk)
	decryptor := ckks.NewDecryptor(c.Params, sk)

	evaluator := ckks.NewEvaluator(c.Params, rlwe.NewMemEvaluationKeySet(rlk))

	x1Cipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.X1)
	if err != nil {
		return LinearRegressionProbeResult{}, fmt.Errorf("encrypt x1: %w", err)
	}

	x2Cipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.X2)
	if err != nil {
		return LinearRegressionProbeResult{}, fmt.Errorf("encrypt x2: %w", err)
	}

	x3Cipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.X3)
	if err != nil {
		return LinearRegressionProbeResult{}, fmt.Errorf("encrypt x3: %w", err)
	}

	x4Cipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.X4)
	if err != nil {
		return LinearRegressionProbeResult{}, fmt.Errorf("encrypt x4: %w", err)
	}

	t1Cipher, err := evaluator.MulNew(x1Cipher, 0.35)
	if err != nil {
		return LinearRegressionProbeResult{}, fmt.Errorf("multiply x1 by 0.35: %w", err)
	}

	t2Cipher, err := evaluator.MulNew(x2Cipher, -0.20)
	if err != nil {
		return LinearRegressionProbeResult{}, fmt.Errorf("multiply x2 by -0.20: %w", err)
	}

	t3Cipher, err := evaluator.MulNew(x3Cipher, 0.15)
	if err != nil {
		return LinearRegressionProbeResult{}, fmt.Errorf("multiply x3 by 0.15: %w", err)
	}

	t4Cipher, err := evaluator.MulNew(x4Cipher, 0.10)
	if err != nil {
		return LinearRegressionProbeResult{}, fmt.Errorf("multiply x4 by 0.10: %w", err)
	}

	sum12Cipher, err := evaluator.AddNew(t1Cipher, t2Cipher)
	if err != nil {
		return LinearRegressionProbeResult{}, fmt.Errorf("add t1 and t2: %w", err)
	}

	sum123Cipher, err := evaluator.AddNew(sum12Cipher, t3Cipher)
	if err != nil {
		return LinearRegressionProbeResult{}, fmt.Errorf("add t3: %w", err)
	}

	sumCipher, err := evaluator.AddNew(sum123Cipher, t4Cipher)
	if err != nil {
		return LinearRegressionProbeResult{}, fmt.Errorf("add t4: %w", err)
	}

	biasPlaintext, err := c.encodeReplicatedPlaintextAtLevel(encoder, -0.05, sumCipher.Level())
	if err != nil {
		return LinearRegressionProbeResult{}, fmt.Errorf("encode linear regression bias plaintext: %w", err)
	}

	yCipher, err := evaluator.AddNew(sumCipher, biasPlaintext)
	if err != nil {
		return LinearRegressionProbeResult{}, fmt.Errorf("add linear regression bias: %w", err)
	}

	yDecoded, err := c.decryptFirstSlot(encoder, decryptor, yCipher)
	if err != nil {
		return LinearRegressionProbeResult{}, fmt.Errorf("decrypt y: %w", err)
	}

	t1Decoded, err := c.decryptFirstSlot(encoder, decryptor, t1Cipher)
	if err != nil {
		return LinearRegressionProbeResult{}, fmt.Errorf("decrypt t1: %w", err)
	}

	t2Decoded, err := c.decryptFirstSlot(encoder, decryptor, t2Cipher)
	if err != nil {
		return LinearRegressionProbeResult{}, fmt.Errorf("decrypt t2: %w", err)
	}

	t3Decoded, err := c.decryptFirstSlot(encoder, decryptor, t3Cipher)
	if err != nil {
		return LinearRegressionProbeResult{}, fmt.Errorf("decrypt t3: %w", err)
	}

	t4Decoded, err := c.decryptFirstSlot(encoder, decryptor, t4Cipher)
	if err != nil {
		return LinearRegressionProbeResult{}, fmt.Errorf("decrypt t4: %w", err)
	}

	plainSample := benchmarks.LinearRegressionSample{
		X1: probeCase.X1,
		X2: probeCase.X2,
		X3: probeCase.X3,
		X4: probeCase.X4,
	}

	plainY := benchmarks.LinearRegressionScore(plainSample)
	threshold := benchmarks.LinearRegressionThreshold

	plainDecision := plainY >= threshold
	ckksDecision := yDecoded >= threshold

	return LinearRegressionProbeResult{
		X1: probeCase.X1,
		X2: probeCase.X2,
		X3: probeCase.X3,
		X4: probeCase.X4,

		Threshold: threshold,

		PlainY: plainY,
		CKKSY:  yDecoded,

		AbsError: math.Abs(yDecoded - plainY),

		PlainDecision: plainDecision,
		CKKSDecision:  ckksDecision,
		Flip:          plainDecision != ckksDecision,

		T1Value: t1Decoded,
		T2Value: t2Decoded,
		T3Value: t3Decoded,
		T4Value: t4Decoded,

		InitialLevel: c.MaxLevel(),
		X1Level:      x1Cipher.Level(),
		X2Level:      x2Cipher.Level(),
		X3Level:      x3Cipher.Level(),
		X4Level:      x4Cipher.Level(),
		YLevel:       yCipher.Level(),

		X1Degree: x1Cipher.Degree(),
		X2Degree: x2Cipher.Degree(),
		X3Degree: x3Cipher.Degree(),
		X4Degree: x4Cipher.Degree(),
		YDegree:  yCipher.Degree(),

		LogDefaultScale: c.LogDefaultScale(),
	}, nil
}
