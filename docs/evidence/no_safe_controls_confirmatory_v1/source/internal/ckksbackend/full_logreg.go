package ckksbackend

import (
	"fmt"
	"math"

	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// FullLogRegProbeCase defines one end-to-end encrypted logreg_small input.
type FullLogRegProbeCase struct {
	Input LogRegSmallInput
}

// FullLogRegProbeResult records end-to-end encrypted logreg_small evaluation.
//
// Flow:
//
//	x1, x2, x3 -> z -> y -> decision
//
// The current encrypted polynomial is:
//
//	z = 0.8*x1 - 0.5*x2 + 1.2*x3 - 0.3
//	y = 0.5 + 0.197*z - 0.004*z^3
type FullLogRegProbeResult struct {
	Input LogRegSmallInput

	Threshold float64

	PlainZ float64
	CKKSZ  float64
	ZError float64

	PlainY float64
	CKKSY  float64
	YError float64

	PlainDecision bool
	CKKSDecision  bool
	DecisionFlip  bool

	InitialLevel int
	ZLevel       int
	Z2Level      int
	Z3Level      int
	YLevel       int

	ZDegree  int
	Z2Degree int
	Z3Degree int
	YDegree  int

	LogDefaultScale int
}

// DefaultFullLogRegProbeCases returns deterministic end-to-end cases.
func DefaultFullLogRegProbeCases() []FullLogRegProbeCase {
	return []FullLogRegProbeCase{
		{
			Input: LogRegSmallInput{
				X1: 0.8,
				X2: -0.3,
				X3: 0.1,
			},
		},
		{
			Input: LogRegSmallInput{
				X1: 0.0,
				X2: 0.0,
				X3: 0.0,
			},
		},
		{
			Input: LogRegSmallInput{
				X1: 1.0,
				X2: 0.5,
				X3: -0.25,
			},
		},
		{
			Input: LogRegSmallInput{
				X1: -0.7,
				X2: 0.25,
				X3: 0.9,
			},
		},
		{
			Input: LogRegSmallInput{
				X1: 0.3875,
				X2: 0.0,
				X3: 0.0,
			},
		},
		{
			Input: LogRegSmallInput{
				X1: 0.3625,
				X2: 0.0,
				X3: 0.0,
			},
		},
	}
}

// RunFullLogRegProbe executes all default end-to-end encrypted logreg_small cases.
func (c Context) RunFullLogRegProbe() ([]FullLogRegProbeResult, error) {
	cases := DefaultFullLogRegProbeCases()
	results := make([]FullLogRegProbeResult, 0, len(cases))

	for i, probeCase := range cases {
		result, err := c.RunFullLogRegProbeCase(probeCase)
		if err != nil {
			return nil, fmt.Errorf("run full logreg probe case %d: %w", i, err)
		}

		results = append(results, result)
	}

	return results, nil
}

// RunFullLogRegProbeCase evaluates the full logreg_small path with CKKS.
func (c Context) RunFullLogRegProbeCase(probeCase FullLogRegProbeCase) (FullLogRegProbeResult, error) {
	encoder := ckks.NewEncoder(c.Params)

	kgen := ckks.NewKeyGenerator(c.Params)
	sk, pk := kgen.GenKeyPairNew()
	rlk := kgen.GenRelinearizationKeyNew(sk)

	encryptor := ckks.NewEncryptor(c.Params, pk)
	decryptor := ckks.NewDecryptor(c.Params, sk)

	relinEvaluator := ckks.NewEvaluator(c.Params, rlwe.NewMemEvaluationKeySet(rlk))

	zCipher, err := c.evalEncryptedLogRegSmallLinearCipher(encoder, encryptor, relinEvaluator, probeCase.Input)
	if err != nil {
		return FullLogRegProbeResult{}, fmt.Errorf("evaluate encrypted linear z: %w", err)
	}

	z2Cipher, err := relinEvaluator.MulNew(zCipher, zCipher)
	if err != nil {
		return FullLogRegProbeResult{}, fmt.Errorf("multiply z by z: %w", err)
	}

	z2Cipher, err = relinEvaluator.RelinearizeNew(z2Cipher)
	if err != nil {
		return FullLogRegProbeResult{}, fmt.Errorf("relinearize z2: %w", err)
	}

	z3Cipher, err := relinEvaluator.MulNew(z2Cipher, zCipher)
	if err != nil {
		return FullLogRegProbeResult{}, fmt.Errorf("multiply z2 by z: %w", err)
	}

	z3Cipher, err = relinEvaluator.RelinearizeNew(z3Cipher)
	if err != nil {
		return FullLogRegProbeResult{}, fmt.Errorf("relinearize z3: %w", err)
	}

	linearTerm, err := relinEvaluator.MulNew(zCipher, 0.197)
	if err != nil {
		return FullLogRegProbeResult{}, fmt.Errorf("multiply z by 0.197: %w", err)
	}

	cubicTerm, err := relinEvaluator.MulNew(z3Cipher, -0.004)
	if err != nil {
		return FullLogRegProbeResult{}, fmt.Errorf("multiply z3 by -0.004: %w", err)
	}

	sum, err := relinEvaluator.AddNew(linearTerm, cubicTerm)
	if err != nil {
		return FullLogRegProbeResult{}, fmt.Errorf("add linear and cubic terms: %w", err)
	}

	biasPlaintext, err := c.encodeReplicatedPlaintextAtLevel(encoder, 0.5, sum.Level())
	if err != nil {
		return FullLogRegProbeResult{}, fmt.Errorf("encode polynomial bias plaintext: %w", err)
	}

	yCipher, err := relinEvaluator.AddNew(sum, biasPlaintext)
	if err != nil {
		return FullLogRegProbeResult{}, fmt.Errorf("add polynomial bias: %w", err)
	}

	zDecoded, err := c.decryptFirstSlot(encoder, decryptor, zCipher)
	if err != nil {
		return FullLogRegProbeResult{}, fmt.Errorf("decrypt z: %w", err)
	}

	yDecoded, err := c.decryptFirstSlot(encoder, decryptor, yCipher)
	if err != nil {
		return FullLogRegProbeResult{}, fmt.Errorf("decrypt y: %w", err)
	}

	plainZ := EvalLogRegSmallLinearPlain(probeCase.Input)
	plainY := EvalLogRegSmallPolynomialPlain(plainZ)

	threshold := 0.5
	plainDecision := plainY >= threshold
	ckksDecision := yDecoded >= threshold

	return FullLogRegProbeResult{
		Input: probeCase.Input,

		Threshold: threshold,

		PlainZ: plainZ,
		CKKSZ:  zDecoded,
		ZError: math.Abs(zDecoded - plainZ),

		PlainY: plainY,
		CKKSY:  yDecoded,
		YError: math.Abs(yDecoded - plainY),

		PlainDecision: plainDecision,
		CKKSDecision:  ckksDecision,
		DecisionFlip:  plainDecision != ckksDecision,

		InitialLevel: c.MaxLevel(),
		ZLevel:       zCipher.Level(),
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

func (c Context) evalEncryptedLogRegSmallLinearCipher(
	encoder *ckks.Encoder,
	encryptor *rlwe.Encryptor,
	evaluator *ckks.Evaluator,
	input LogRegSmallInput,
) (*rlwe.Ciphertext, error) {
	x1, err := c.encryptReplicatedScalar(encoder, encryptor, input.X1)
	if err != nil {
		return nil, fmt.Errorf("encrypt x1: %w", err)
	}

	x2, err := c.encryptReplicatedScalar(encoder, encryptor, input.X2)
	if err != nil {
		return nil, fmt.Errorf("encrypt x2: %w", err)
	}

	x3, err := c.encryptReplicatedScalar(encoder, encryptor, input.X3)
	if err != nil {
		return nil, fmt.Errorf("encrypt x3: %w", err)
	}

	t1, err := evaluator.MulNew(x1, 0.8)
	if err != nil {
		return nil, fmt.Errorf("multiply x1 by 0.8: %w", err)
	}

	t2, err := evaluator.MulNew(x2, -0.5)
	if err != nil {
		return nil, fmt.Errorf("multiply x2 by -0.5: %w", err)
	}

	t3, err := evaluator.MulNew(x3, 1.2)
	if err != nil {
		return nil, fmt.Errorf("multiply x3 by 1.2: %w", err)
	}

	sum12, err := evaluator.AddNew(t1, t2)
	if err != nil {
		return nil, fmt.Errorf("add t1 and t2: %w", err)
	}

	sum123, err := evaluator.AddNew(sum12, t3)
	if err != nil {
		return nil, fmt.Errorf("add t3: %w", err)
	}

	biasPlaintext, err := c.encodeReplicatedPlaintextAtLevel(encoder, -0.3, sum123.Level())
	if err != nil {
		return nil, fmt.Errorf("encode linear bias plaintext: %w", err)
	}

	zCipher, err := evaluator.AddNew(sum123, biasPlaintext)
	if err != nil {
		return nil, fmt.Errorf("add linear bias: %w", err)
	}

	return zCipher, nil
}
