package ckksbackend

import (
	"fmt"
	"math"

	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// MultiplicationProbeCase defines one ciphertext-ciphertext multiplication probe.
type MultiplicationProbeCase struct {
	Z float64
}

// MultiplicationProbeResult records the observed behavior of z*z under CKKS.
//
// This probe intentionally uses evaluator.MulNew without relinearization or
// rescaling. It is a diagnostic step before implementing the full polynomial
// path y = 0.5 + 0.197*z - 0.004*z^3.
type MultiplicationProbeResult struct {
	Z float64

	PlainZ2 float64

	RawDecodedZ2 float64
	RawAbsError  float64

	ScaledDecodedZ2 float64
	ScaledAbsError  float64

	SelectedInterpretation ScaleInterpretation
	SelectedZ2             float64
	SelectedAbsError       float64

	DecodeScaleCorrection float64

	InitialLevel int
	FinalLevel   int

	InputDegree  int
	OutputDegree int

	LogDefaultScale int
}

// DefaultMultiplicationProbeCases returns deterministic z values.
func DefaultMultiplicationProbeCases() []MultiplicationProbeCase {
	return []MultiplicationProbeCase{
		{Z: 0.0},
		{Z: 0.095},
		{Z: -0.3},
		{Z: 0.61},
		{Z: -0.84},
		{Z: 1.2},
	}
}

// RunMultiplicationProbe executes all default ciphertext-ciphertext
// multiplication probe cases.
func (c Context) RunMultiplicationProbe() ([]MultiplicationProbeResult, error) {
	cases := DefaultMultiplicationProbeCases()
	results := make([]MultiplicationProbeResult, 0, len(cases))

	for i, probeCase := range cases {
		result, err := c.RunMultiplicationProbeCase(probeCase)
		if err != nil {
			return nil, fmt.Errorf("run multiplication probe case %d: %w", i, err)
		}

		results = append(results, result)
	}

	return results, nil
}

// RunMultiplicationProbeCase evaluates z2 = z*z using CKKS ciphertext
// multiplication without relinearization and without rescaling.
func (c Context) RunMultiplicationProbeCase(probeCase MultiplicationProbeCase) (MultiplicationProbeResult, error) {
	encoder := ckks.NewEncoder(c.Params)

	kgen := ckks.NewKeyGenerator(c.Params)
	sk, pk := kgen.GenKeyPairNew()

	encryptor := ckks.NewEncryptor(c.Params, pk)
	decryptor := ckks.NewDecryptor(c.Params, sk)

	evaluator := ckks.NewEvaluator(c.Params, nil)

	zCipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.Z)
	if err != nil {
		return MultiplicationProbeResult{}, fmt.Errorf("encrypt z: %w", err)
	}

	z2Cipher, err := evaluator.MulNew(zCipher, zCipher)
	if err != nil {
		return MultiplicationProbeResult{}, fmt.Errorf("multiply z by z: %w", err)
	}

	raw, err := c.decryptFirstSlot(encoder, decryptor, z2Cipher)
	if err != nil {
		return MultiplicationProbeResult{}, fmt.Errorf("decrypt z2: %w", err)
	}

	plain := probeCase.Z * probeCase.Z
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

	return MultiplicationProbeResult{
		Z: probeCase.Z,

		PlainZ2: plain,

		RawDecodedZ2: raw,
		RawAbsError:  rawAbsError,

		ScaledDecodedZ2: scaled,
		ScaledAbsError:  scaledAbsError,

		SelectedInterpretation: selectedInterpretation,
		SelectedZ2:             selectedValue,
		SelectedAbsError:       selectedAbsError,

		DecodeScaleCorrection: correction,

		InitialLevel: c.MaxLevel(),
		FinalLevel:   z2Cipher.Level(),

		InputDegree:  zCipher.Degree(),
		OutputDegree: z2Cipher.Degree(),

		LogDefaultScale: c.LogDefaultScale(),
	}, nil
}
