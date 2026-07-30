package ckksbackend

import (
	"fmt"
	"math"

	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// PolynomialProbeCase defines one encrypted polynomial probe input.
type PolynomialProbeCase struct {
	Z float64
}

// PolynomialProbeResult records encrypted evaluation behavior for:
//
// y = 0.5 + 0.197*z - 0.004*z^3
type PolynomialProbeResult struct {
	Z float64

	PlainY float64
	CKKSY  float64

	AbsError float64

	Z3Value float64

	InitialLevel int
	Z2Level      int
	Z3Level      int
	YLevel       int

	ZDegree  int
	Z2Degree int
	Z3Degree int
	YDegree  int

	LogDefaultScale int
}

// EvalLogRegSmallPolynomialPlain evaluates the current logreg_small polynomial.
func EvalLogRegSmallPolynomialPlain(z float64) float64 {
	return 0.5 + 0.197*z - 0.004*z*z*z
}

// DefaultPolynomialProbeCases returns deterministic z values.
func DefaultPolynomialProbeCases() []PolynomialProbeCase {
	return []PolynomialProbeCase{
		{Z: 0.0},
		{Z: 0.095},
		{Z: -0.3},
		{Z: 0.61},
		{Z: -0.84},
		{Z: 1.2},
	}
}

// RunPolynomialProbe executes all default encrypted polynomial probe cases.
func (c Context) RunPolynomialProbe() ([]PolynomialProbeResult, error) {
	cases := DefaultPolynomialProbeCases()
	results := make([]PolynomialProbeResult, 0, len(cases))

	for i, probeCase := range cases {
		result, err := c.RunPolynomialProbeCase(probeCase)
		if err != nil {
			return nil, fmt.Errorf("run polynomial probe case %d: %w", i, err)
		}

		results = append(results, result)
	}

	return results, nil
}

// RunPolynomialProbeCase evaluates y = 0.5 + 0.197*z - 0.004*z^3 using CKKS.
func (c Context) RunPolynomialProbeCase(probeCase PolynomialProbeCase) (PolynomialProbeResult, error) {
	encoder := ckks.NewEncoder(c.Params)

	kgen := ckks.NewKeyGenerator(c.Params)
	sk, pk := kgen.GenKeyPairNew()
	rlk := kgen.GenRelinearizationKeyNew(sk)

	encryptor := ckks.NewEncryptor(c.Params, pk)
	decryptor := ckks.NewDecryptor(c.Params, sk)

	relinEvaluator := ckks.NewEvaluator(c.Params, rlwe.NewMemEvaluationKeySet(rlk))

	zCipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.Z)
	if err != nil {
		return PolynomialProbeResult{}, fmt.Errorf("encrypt z: %w", err)
	}

	z2Cipher, err := relinEvaluator.MulNew(zCipher, zCipher)
	if err != nil {
		return PolynomialProbeResult{}, fmt.Errorf("multiply z by z: %w", err)
	}

	z2Cipher, err = relinEvaluator.RelinearizeNew(z2Cipher)
	if err != nil {
		return PolynomialProbeResult{}, fmt.Errorf("relinearize z2: %w", err)
	}

	z3Cipher, err := relinEvaluator.MulNew(z2Cipher, zCipher)
	if err != nil {
		return PolynomialProbeResult{}, fmt.Errorf("multiply z2 by z: %w", err)
	}

	z3Cipher, err = relinEvaluator.RelinearizeNew(z3Cipher)
	if err != nil {
		return PolynomialProbeResult{}, fmt.Errorf("relinearize z3: %w", err)
	}

	linearTerm, err := relinEvaluator.MulNew(zCipher, 0.197)
	if err != nil {
		return PolynomialProbeResult{}, fmt.Errorf("multiply z by 0.197: %w", err)
	}

	cubicTerm, err := relinEvaluator.MulNew(z3Cipher, -0.004)
	if err != nil {
		return PolynomialProbeResult{}, fmt.Errorf("multiply z3 by -0.004: %w", err)
	}

	sum, err := relinEvaluator.AddNew(linearTerm, cubicTerm)
	if err != nil {
		return PolynomialProbeResult{}, fmt.Errorf("add linear and cubic terms: %w", err)
	}

	biasPlaintext, err := c.encodeReplicatedPlaintextAtLevel(encoder, 0.5, sum.Level())
	if err != nil {
		return PolynomialProbeResult{}, fmt.Errorf("encode polynomial bias plaintext: %w", err)
	}

	yCipher, err := relinEvaluator.AddNew(sum, biasPlaintext)
	if err != nil {
		return PolynomialProbeResult{}, fmt.Errorf("add polynomial bias: %w", err)
	}

	yDecoded, err := c.decryptFirstSlot(encoder, decryptor, yCipher)
	if err != nil {
		return PolynomialProbeResult{}, fmt.Errorf("decrypt y: %w", err)
	}

	z3Decoded, err := c.decryptFirstSlot(encoder, decryptor, z3Cipher)
	if err != nil {
		return PolynomialProbeResult{}, fmt.Errorf("decrypt z3: %w", err)
	}

	plainY := EvalLogRegSmallPolynomialPlain(probeCase.Z)

	return PolynomialProbeResult{
		Z: probeCase.Z,

		PlainY: plainY,
		CKKSY:  yDecoded,

		AbsError: math.Abs(yDecoded - plainY),

		Z3Value: z3Decoded,

		InitialLevel: c.MaxLevel(),
		Z2Level:      z2Cipher.Level(),
		Z3Level:      z3Cipher.Level(),
		YLevel:       yCipher.Level(),

		ZDegree:  zCipher.Degree(),
		Z2Degree: z2Cipher.Degree(),
		Z3Degree: z3Cipher.Degree(),
		YDegree:  yCipher.Degree(),

		LogDefaultScale: c.LogDefaultScale(),
	}, nil
}
