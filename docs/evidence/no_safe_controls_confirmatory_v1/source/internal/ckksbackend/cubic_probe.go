package ckksbackend

import (
	"fmt"
	"math"

	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// CubicProbeCase defines one encrypted cubic probe input.
type CubicProbeCase struct {
	Z float64
}

// CubicProbeResult records encrypted evaluation behavior for z3 = z*z*z.
//
// This probe uses relinearization after each ciphertext-ciphertext
// multiplication and intentionally does not rescale. It is a diagnostic step
// before implementing the full encrypted polynomial:
// y = 0.5 + 0.197*z - 0.004*z^3.
type CubicProbeResult struct {
	Z float64

	PlainZ3 float64

	RawDecodedZ3 float64
	RawAbsError  float64

	ScaledDecodedZ3 float64
	ScaledAbsError  float64

	SelectedInterpretation ScaleInterpretation
	SelectedZ3             float64
	SelectedAbsError       float64

	DecodeScaleCorrection float64

	InitialLevel int
	Z2Level      int
	Z3Level      int

	ZDegree  int
	Z2Degree int
	Z3Degree int

	LogDefaultScale int
}

// DefaultCubicProbeCases returns deterministic z values.
func DefaultCubicProbeCases() []CubicProbeCase {
	return []CubicProbeCase{
		{Z: 0.0},
		{Z: 0.095},
		{Z: -0.3},
		{Z: 0.61},
		{Z: -0.84},
		{Z: 1.2},
	}
}

// RunCubicProbe executes all default encrypted cubic probe cases.
func (c Context) RunCubicProbe() ([]CubicProbeResult, error) {
	cases := DefaultCubicProbeCases()
	results := make([]CubicProbeResult, 0, len(cases))

	for i, probeCase := range cases {
		result, err := c.RunCubicProbeCase(probeCase)
		if err != nil {
			return nil, fmt.Errorf("run cubic probe case %d: %w", i, err)
		}

		results = append(results, result)
	}

	return results, nil
}

// RunCubicProbeCase evaluates z3 = z*z*z with CKKS ciphertext operations.
func (c Context) RunCubicProbeCase(probeCase CubicProbeCase) (CubicProbeResult, error) {
	encoder := ckks.NewEncoder(c.Params)

	kgen := ckks.NewKeyGenerator(c.Params)
	sk, pk := kgen.GenKeyPairNew()
	rlk := kgen.GenRelinearizationKeyNew(sk)

	encryptor := ckks.NewEncryptor(c.Params, pk)
	decryptor := ckks.NewDecryptor(c.Params, sk)

	relinEvaluator := ckks.NewEvaluator(c.Params, rlwe.NewMemEvaluationKeySet(rlk))

	zCipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.Z)
	if err != nil {
		return CubicProbeResult{}, fmt.Errorf("encrypt z: %w", err)
	}

	z2Cipher, err := relinEvaluator.MulNew(zCipher, zCipher)
	if err != nil {
		return CubicProbeResult{}, fmt.Errorf("multiply z by z: %w", err)
	}

	z2Cipher, err = relinEvaluator.RelinearizeNew(z2Cipher)
	if err != nil {
		return CubicProbeResult{}, fmt.Errorf("relinearize z2: %w", err)
	}

	z3Cipher, err := relinEvaluator.MulNew(z2Cipher, zCipher)
	if err != nil {
		return CubicProbeResult{}, fmt.Errorf("multiply z2 by z: %w", err)
	}

	z3Cipher, err = relinEvaluator.RelinearizeNew(z3Cipher)
	if err != nil {
		return CubicProbeResult{}, fmt.Errorf("relinearize z3: %w", err)
	}

	raw, err := c.decryptFirstSlot(encoder, decryptor, z3Cipher)
	if err != nil {
		return CubicProbeResult{}, fmt.Errorf("decrypt z3: %w", err)
	}

	plain := probeCase.Z * probeCase.Z * probeCase.Z
	correction := math.Exp2(float64(c.LogDefaultScale()))

	rawAbsError := math.Abs(raw - plain)

	scaled := raw / correction
	scaledAbsError := math.Abs(scaled - plain)

	selectedInterpretation := ScaleInterpretationRaw
	selectedValue := raw
	selectedAbsError := rawAbsError

	if scaledAbsError < rawAbsError {
		selectedInterpretation = ScaleInterpretationDivideDefaultScale
		selectedValue = scaled
		selectedAbsError = scaledAbsError
	}

	return CubicProbeResult{
		Z: probeCase.Z,

		PlainZ3: plain,

		RawDecodedZ3: raw,
		RawAbsError:  rawAbsError,

		ScaledDecodedZ3: scaled,
		ScaledAbsError:  scaledAbsError,

		SelectedInterpretation: selectedInterpretation,
		SelectedZ3:             selectedValue,
		SelectedAbsError:       selectedAbsError,

		DecodeScaleCorrection: correction,

		InitialLevel: c.MaxLevel(),
		Z2Level:      z2Cipher.Level(),
		Z3Level:      z3Cipher.Level(),

		ZDegree:  zCipher.Degree(),
		Z2Degree: z2Cipher.Degree(),
		Z3Degree: z3Cipher.Degree(),

		LogDefaultScale: c.LogDefaultScale(),
	}, nil
}
