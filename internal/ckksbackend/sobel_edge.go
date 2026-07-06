package ckksbackend

import (
	"fmt"
	"math"

	"github.com/hasslelee/flipguard/internal/benchmarks"
	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// SobelEdgeProbeCase defines one encrypted Sobel 3x3 patch probe input.
type SobelEdgeProbeCase struct {
	P00 float64
	P01 float64
	P02 float64

	P10 float64
	P11 float64
	P12 float64

	P20 float64
	P21 float64
	P22 float64
}

// SobelEdgeProbeResult records encrypted evaluation behavior for:
//
// gx = -p00 + p02 - 2*p10 + 2*p12 - p20 + p22
// gy = -p00 - 2*p01 - p02 + p20 + 2*p21 + p22
// score = gx^2 + gy^2
type SobelEdgeProbeResult struct {
	P00 float64
	P01 float64
	P02 float64

	P10 float64
	P11 float64
	P12 float64

	P20 float64
	P21 float64
	P22 float64

	Threshold float64

	PlainGX    float64
	PlainGY    float64
	PlainScore float64

	CKKSGX    float64
	CKKSGY    float64
	CKKSGX2   float64
	CKKSGY2   float64
	CKKSScore float64

	AbsError float64

	PlainDecision bool
	CKKSDecision  bool
	Flip          bool

	InitialLevel int
	GXLevel      int
	GYLevel      int
	GX2Level     int
	GY2Level     int
	ScoreLevel   int

	GXDegree    int
	GYDegree    int
	GX2Degree   int
	GY2Degree   int
	ScoreDegree int

	LogDefaultScale int
}

// DefaultSobelEdgeProbeCases returns deterministic non-exact-boundary Sobel
// patches for CKKS evaluation.
//
// Exact score=threshold cases are intentionally avoided here because tiny CKKS
// approximation noise around the edge threshold can turn them into expected
// uncertified cases. Boundary-focused cases still exist in the benchmark
// generator.
func DefaultSobelEdgeProbeCases() []SobelEdgeProbeCase {
	return []SobelEdgeProbeCase{
		// Flat non-edge patches.
		{
			P00: 0.0, P01: 0.0, P02: 0.0,
			P10: 0.0, P11: 0.0, P12: 0.0,
			P20: 0.0, P21: 0.0, P22: 0.0,
		},
		{
			P00: 1.0, P01: 1.0, P02: 1.0,
			P10: 1.0, P11: 1.0, P12: 1.0,
			P20: 1.0, P21: 1.0, P22: 1.0,
		},

		// Weak vertical edges: one below, one above threshold.
		{
			P00: 0.0, P01: 0.0, P02: 0.95,
			P10: 0.0, P11: 0.0, P12: 0.95,
			P20: 0.0, P21: 0.0, P22: 0.95,
		},
		{
			P00: 0.0, P01: 0.0, P02: 1.05,
			P10: 0.0, P11: 0.0, P12: 1.05,
			P20: 0.0, P21: 0.0, P22: 1.05,
		},

		// Weak horizontal edges: one below, one above threshold.
		{
			P00: 0.0, P01: 0.0, P02: 0.0,
			P10: 0.0, P11: 0.0, P12: 0.0,
			P20: 0.95, P21: 0.95, P22: 0.95,
		},
		{
			P00: 0.0, P01: 0.0, P02: 0.0,
			P10: 0.0, P11: 0.0, P12: 0.0,
			P20: 1.05, P21: 1.05, P22: 1.05,
		},

		// Strong vertical and horizontal edges.
		{
			P00: 0.0, P01: 0.0, P02: 1.25,
			P10: 0.0, P11: 0.0, P12: 1.25,
			P20: 0.0, P21: 0.0, P22: 1.25,
		},
		{
			P00: 0.0, P01: 0.0, P02: 0.0,
			P10: 0.0, P11: 0.0, P12: 0.0,
			P20: 1.25, P21: 1.25, P22: 1.25,
		},

		// Diagonal contrast patterns.
		{
			P00: 0.0, P01: 0.0, P02: 1.0,
			P10: 0.0, P11: 1.0, P12: 1.0,
			P20: 1.0, P21: 1.0, P22: 1.0,
		},
		{
			P00: 1.0, P01: 1.0, P02: 0.0,
			P10: 1.0, P11: 1.0, P12: 0.0,
			P20: 0.0, P21: 0.0, P22: 0.0,
		},
	}
}

// RunSobelEdgeProbe executes all default encrypted Sobel edge probe cases.
func (c Context) RunSobelEdgeProbe() ([]SobelEdgeProbeResult, error) {
	cases := DefaultSobelEdgeProbeCases()
	results := make([]SobelEdgeProbeResult, 0, len(cases))

	for i, probeCase := range cases {
		result, err := c.RunSobelEdgeProbeCase(probeCase)
		if err != nil {
			return nil, fmt.Errorf("run Sobel edge probe case %d: %w", i, err)
		}

		results = append(results, result)
	}

	return results, nil
}

// RunSobelEdgeProbeCase evaluates:
//
// gx = -p00 + p02 - 2*p10 + 2*p12 - p20 + p22
// gy = -p00 - 2*p01 - p02 + p20 + 2*p21 + p22
// score = gx^2 + gy^2
//
// using CKKS.
func (c Context) RunSobelEdgeProbeCase(
	probeCase SobelEdgeProbeCase,
) (SobelEdgeProbeResult, error) {
	encoder := ckks.NewEncoder(c.Params)

	kgen := ckks.NewKeyGenerator(c.Params)
	sk, pk := kgen.GenKeyPairNew()
	rlk := kgen.GenRelinearizationKeyNew(sk)

	encryptor := ckks.NewEncryptor(c.Params, pk)
	decryptor := ckks.NewDecryptor(c.Params, sk)

	evaluator := ckks.NewEvaluator(c.Params, rlwe.NewMemEvaluationKeySet(rlk))

	p00Cipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.P00)
	if err != nil {
		return SobelEdgeProbeResult{}, fmt.Errorf("encrypt p00: %w", err)
	}

	p01Cipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.P01)
	if err != nil {
		return SobelEdgeProbeResult{}, fmt.Errorf("encrypt p01: %w", err)
	}

	p02Cipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.P02)
	if err != nil {
		return SobelEdgeProbeResult{}, fmt.Errorf("encrypt p02: %w", err)
	}

	p10Cipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.P10)
	if err != nil {
		return SobelEdgeProbeResult{}, fmt.Errorf("encrypt p10: %w", err)
	}

	p12Cipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.P12)
	if err != nil {
		return SobelEdgeProbeResult{}, fmt.Errorf("encrypt p12: %w", err)
	}

	p20Cipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.P20)
	if err != nil {
		return SobelEdgeProbeResult{}, fmt.Errorf("encrypt p20: %w", err)
	}

	p21Cipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.P21)
	if err != nil {
		return SobelEdgeProbeResult{}, fmt.Errorf("encrypt p21: %w", err)
	}

	p22Cipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.P22)
	if err != nil {
		return SobelEdgeProbeResult{}, fmt.Errorf("encrypt p22: %w", err)
	}

	gxCipher, err := evalSobelGX(
		evaluator,
		p00Cipher,
		p02Cipher,
		p10Cipher,
		p12Cipher,
		p20Cipher,
		p22Cipher,
	)
	if err != nil {
		return SobelEdgeProbeResult{}, fmt.Errorf("evaluate gx: %w", err)
	}

	gyCipher, err := evalSobelGY(
		evaluator,
		p00Cipher,
		p01Cipher,
		p02Cipher,
		p20Cipher,
		p21Cipher,
		p22Cipher,
	)
	if err != nil {
		return SobelEdgeProbeResult{}, fmt.Errorf("evaluate gy: %w", err)
	}

	gx2Cipher, err := evaluator.MulNew(gxCipher, gxCipher)
	if err != nil {
		return SobelEdgeProbeResult{}, fmt.Errorf("square gx: %w", err)
	}

	gy2Cipher, err := evaluator.MulNew(gyCipher, gyCipher)
	if err != nil {
		return SobelEdgeProbeResult{}, fmt.Errorf("square gy: %w", err)
	}

	scoreCipher, err := evaluator.AddNew(gx2Cipher, gy2Cipher)
	if err != nil {
		return SobelEdgeProbeResult{}, fmt.Errorf("add gx2 and gy2: %w", err)
	}

	gxDecoded, err := c.decryptFirstSlot(encoder, decryptor, gxCipher)
	if err != nil {
		return SobelEdgeProbeResult{}, fmt.Errorf("decrypt gx: %w", err)
	}

	gyDecoded, err := c.decryptFirstSlot(encoder, decryptor, gyCipher)
	if err != nil {
		return SobelEdgeProbeResult{}, fmt.Errorf("decrypt gy: %w", err)
	}

	gx2Decoded, err := c.decryptFirstSlot(encoder, decryptor, gx2Cipher)
	if err != nil {
		return SobelEdgeProbeResult{}, fmt.Errorf("decrypt gx2: %w", err)
	}

	gy2Decoded, err := c.decryptFirstSlot(encoder, decryptor, gy2Cipher)
	if err != nil {
		return SobelEdgeProbeResult{}, fmt.Errorf("decrypt gy2: %w", err)
	}

	scoreDecoded, err := c.decryptFirstSlot(encoder, decryptor, scoreCipher)
	if err != nil {
		return SobelEdgeProbeResult{}, fmt.Errorf("decrypt score: %w", err)
	}

	plainSample := benchmarks.SobelEdgeSample{
		P00: probeCase.P00,
		P01: probeCase.P01,
		P02: probeCase.P02,
		P10: probeCase.P10,
		P11: probeCase.P11,
		P12: probeCase.P12,
		P20: probeCase.P20,
		P21: probeCase.P21,
		P22: probeCase.P22,
	}

	plainResponse := benchmarks.SobelEdgeResponse(plainSample)
	plainScore := benchmarks.SobelEdgeScore(plainSample)
	threshold := benchmarks.SobelEdgeThreshold

	plainDecision := plainScore >= threshold
	ckksDecision := scoreDecoded >= threshold

	return SobelEdgeProbeResult{
		P00: probeCase.P00,
		P01: probeCase.P01,
		P02: probeCase.P02,

		P10: probeCase.P10,
		P11: probeCase.P11,
		P12: probeCase.P12,

		P20: probeCase.P20,
		P21: probeCase.P21,
		P22: probeCase.P22,

		Threshold: threshold,

		PlainGX:    plainResponse.GX,
		PlainGY:    plainResponse.GY,
		PlainScore: plainScore,

		CKKSGX:    gxDecoded,
		CKKSGY:    gyDecoded,
		CKKSGX2:   gx2Decoded,
		CKKSGY2:   gy2Decoded,
		CKKSScore: scoreDecoded,

		AbsError: math.Abs(scoreDecoded - plainScore),

		PlainDecision: plainDecision,
		CKKSDecision:  ckksDecision,
		Flip:          plainDecision != ckksDecision,

		InitialLevel: c.MaxLevel(),
		GXLevel:      gxCipher.Level(),
		GYLevel:      gyCipher.Level(),
		GX2Level:     gx2Cipher.Level(),
		GY2Level:     gy2Cipher.Level(),
		ScoreLevel:   scoreCipher.Level(),

		GXDegree:    gxCipher.Degree(),
		GYDegree:    gyCipher.Degree(),
		GX2Degree:   gx2Cipher.Degree(),
		GY2Degree:   gy2Cipher.Degree(),
		ScoreDegree: scoreCipher.Degree(),

		LogDefaultScale: c.LogDefaultScale(),
	}, nil
}

func evalSobelGX(
	evaluator *ckks.Evaluator,
	p00Cipher *rlwe.Ciphertext,
	p02Cipher *rlwe.Ciphertext,
	p10Cipher *rlwe.Ciphertext,
	p12Cipher *rlwe.Ciphertext,
	p20Cipher *rlwe.Ciphertext,
	p22Cipher *rlwe.Ciphertext,
) (*rlwe.Ciphertext, error) {
	t00, err := evaluator.MulNew(p00Cipher, -1.0)
	if err != nil {
		return nil, fmt.Errorf("multiply p00 by -1: %w", err)
	}

	t02, err := evaluator.MulNew(p02Cipher, 1.0)
	if err != nil {
		return nil, fmt.Errorf("multiply p02 by 1: %w", err)
	}

	t10, err := evaluator.MulNew(p10Cipher, -2.0)
	if err != nil {
		return nil, fmt.Errorf("multiply p10 by -2: %w", err)
	}

	t12, err := evaluator.MulNew(p12Cipher, 2.0)
	if err != nil {
		return nil, fmt.Errorf("multiply p12 by 2: %w", err)
	}

	t20, err := evaluator.MulNew(p20Cipher, -1.0)
	if err != nil {
		return nil, fmt.Errorf("multiply p20 by -1: %w", err)
	}

	t22, err := evaluator.MulNew(p22Cipher, 1.0)
	if err != nil {
		return nil, fmt.Errorf("multiply p22 by 1: %w", err)
	}

	s1, err := evaluator.AddNew(t00, t02)
	if err != nil {
		return nil, fmt.Errorf("add gx t00 and t02: %w", err)
	}

	s2, err := evaluator.AddNew(s1, t10)
	if err != nil {
		return nil, fmt.Errorf("add gx t10: %w", err)
	}

	s3, err := evaluator.AddNew(s2, t12)
	if err != nil {
		return nil, fmt.Errorf("add gx t12: %w", err)
	}

	s4, err := evaluator.AddNew(s3, t20)
	if err != nil {
		return nil, fmt.Errorf("add gx t20: %w", err)
	}

	gx, err := evaluator.AddNew(s4, t22)
	if err != nil {
		return nil, fmt.Errorf("add gx t22: %w", err)
	}

	return gx, nil
}

func evalSobelGY(
	evaluator *ckks.Evaluator,
	p00Cipher *rlwe.Ciphertext,
	p01Cipher *rlwe.Ciphertext,
	p02Cipher *rlwe.Ciphertext,
	p20Cipher *rlwe.Ciphertext,
	p21Cipher *rlwe.Ciphertext,
	p22Cipher *rlwe.Ciphertext,
) (*rlwe.Ciphertext, error) {
	t00, err := evaluator.MulNew(p00Cipher, -1.0)
	if err != nil {
		return nil, fmt.Errorf("multiply p00 by -1: %w", err)
	}

	t01, err := evaluator.MulNew(p01Cipher, -2.0)
	if err != nil {
		return nil, fmt.Errorf("multiply p01 by -2: %w", err)
	}

	t02, err := evaluator.MulNew(p02Cipher, -1.0)
	if err != nil {
		return nil, fmt.Errorf("multiply p02 by -1: %w", err)
	}

	t20, err := evaluator.MulNew(p20Cipher, 1.0)
	if err != nil {
		return nil, fmt.Errorf("multiply p20 by 1: %w", err)
	}

	t21, err := evaluator.MulNew(p21Cipher, 2.0)
	if err != nil {
		return nil, fmt.Errorf("multiply p21 by 2: %w", err)
	}

	t22, err := evaluator.MulNew(p22Cipher, 1.0)
	if err != nil {
		return nil, fmt.Errorf("multiply p22 by 1: %w", err)
	}

	s1, err := evaluator.AddNew(t00, t01)
	if err != nil {
		return nil, fmt.Errorf("add gy t00 and t01: %w", err)
	}

	s2, err := evaluator.AddNew(s1, t02)
	if err != nil {
		return nil, fmt.Errorf("add gy t02: %w", err)
	}

	s3, err := evaluator.AddNew(s2, t20)
	if err != nil {
		return nil, fmt.Errorf("add gy t20: %w", err)
	}

	s4, err := evaluator.AddNew(s3, t21)
	if err != nil {
		return nil, fmt.Errorf("add gy t21: %w", err)
	}

	gy, err := evaluator.AddNew(s4, t22)
	if err != nil {
		return nil, fmt.Errorf("add gy t22: %w", err)
	}

	return gy, nil
}
