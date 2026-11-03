package ckksbackend

import (
	"fmt"
	"math"

	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// ScaleInterpretation identifies how a raw decoded CKKS value is interpreted.
type ScaleInterpretation string

const (
	// ScaleInterpretationRaw means the raw decoded value already matches the
	// plaintext-domain value.
	ScaleInterpretationRaw ScaleInterpretation = "raw"

	// ScaleInterpretationDivideDefaultScale means the raw decoded value should
	// be divided by 2^log_default_scale.
	ScaleInterpretationDivideDefaultScale ScaleInterpretation = "divide_default_scale"
)

// ScalarScaleProbeCase defines one ciphertext-scalar multiplication probe.
type ScalarScaleProbeCase struct {
	Input  float64
	Scalar float64
	Bias   float64
}

// ScalarScaleProbeResult records the observed scale behavior of a simple
// ciphertext-scalar multiplication path.
//
// Expression:
//
//	y = scalar * input + bias
//
// This probe intentionally records both interpretations:
//
//   - raw decoded value
//   - raw decoded value divided by 2^log_default_scale
//
// The selected value is the interpretation with the smaller absolute error.
// This is diagnostic only. It is not the final CKKS scale-management design.
type ScalarScaleProbeResult struct {
	Input  float64
	Scalar float64
	Bias   float64

	PlainValue float64

	RawDecodedValue float64
	RawAbsError     float64

	ScaledDecodedValue float64
	ScaledAbsError     float64

	SelectedInterpretation ScaleInterpretation
	SelectedValue          float64
	SelectedAbsError       float64

	DecodeScaleCorrection float64

	RawOverPlain      float64
	ScaledOverPlain   float64
	CorrectionOverRaw float64

	InitialLevel int
	FinalLevel   int

	LogDefaultScale int
}

// DefaultScalarScaleProbeCases returns deterministic probe cases.
func DefaultScalarScaleProbeCases() []ScalarScaleProbeCase {
	return []ScalarScaleProbeCase{
		{Input: 1.0, Scalar: 1.0, Bias: 0.0},
		{Input: 1.0, Scalar: 0.8, Bias: 0.0},
		{Input: -0.3, Scalar: -0.5, Bias: 0.0},
		{Input: 0.1, Scalar: 1.2, Bias: 0.0},
		{Input: 0.8, Scalar: 0.8, Bias: -0.3},
		{Input: -0.7, Scalar: 1.2, Bias: 0.25},
	}
}

// RunScalarScaleProbe executes all default scalar scale probe cases.
func (c Context) RunScalarScaleProbe() ([]ScalarScaleProbeResult, error) {
	cases := DefaultScalarScaleProbeCases()
	results := make([]ScalarScaleProbeResult, 0, len(cases))

	for i, probeCase := range cases {
		result, err := c.RunScalarScaleProbeCase(probeCase)
		if err != nil {
			return nil, fmt.Errorf("run scalar scale probe case %d: %w", i, err)
		}

		results = append(results, result)
	}

	return results, nil
}

// RunScalarScaleProbeCase executes one ciphertext-scalar multiplication probe.
func (c Context) RunScalarScaleProbeCase(probeCase ScalarScaleProbeCase) (ScalarScaleProbeResult, error) {
	encoder := ckks.NewEncoder(c.Params)

	kgen := ckks.NewKeyGenerator(c.Params)
	sk, pk := kgen.GenKeyPairNew()

	encryptor := ckks.NewEncryptor(c.Params, pk)
	decryptor := ckks.NewDecryptor(c.Params, sk)

	evaluator := ckks.NewEvaluator(c.Params, nil)

	ct, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.Input)
	if err != nil {
		return ScalarScaleProbeResult{}, fmt.Errorf("encrypt input: %w", err)
	}

	mul, err := evaluator.MulNew(ct, probeCase.Scalar)
	if err != nil {
		return ScalarScaleProbeResult{}, fmt.Errorf("multiply by scalar: %w", err)
	}

	var out *rlwe.Ciphertext
	if probeCase.Bias != 0 {
		out, err = evaluator.AddNew(mul, probeCase.Bias)
		if err != nil {
			return ScalarScaleProbeResult{}, fmt.Errorf("add bias: %w", err)
		}
	} else {
		out = mul
	}

	raw, err := c.decryptFirstSlot(encoder, decryptor, out)
	if err != nil {
		return ScalarScaleProbeResult{}, fmt.Errorf("decrypt probe output: %w", err)
	}

	plain := probeCase.Scalar*probeCase.Input + probeCase.Bias
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

	rawOverPlain := 0.0
	scaledOverPlain := 0.0
	if plain != 0 {
		rawOverPlain = raw / plain
		scaledOverPlain = scaled / plain
	}

	correctionOverRaw := 0.0
	if raw != 0 {
		correctionOverRaw = correction / raw
	}

	return ScalarScaleProbeResult{
		Input:  probeCase.Input,
		Scalar: probeCase.Scalar,
		Bias:   probeCase.Bias,

		PlainValue: plain,

		RawDecodedValue: raw,
		RawAbsError:     rawAbsError,

		ScaledDecodedValue: scaled,
		ScaledAbsError:     scaledAbsError,

		SelectedInterpretation: selectedInterpretation,
		SelectedValue:          selectedValue,
		SelectedAbsError:       selectedAbsError,

		DecodeScaleCorrection: correction,

		RawOverPlain:      rawOverPlain,
		ScaledOverPlain:   scaledOverPlain,
		CorrectionOverRaw: correctionOverRaw,

		InitialLevel: c.MaxLevel(),
		FinalLevel:   out.Level(),

		LogDefaultScale: c.LogDefaultScale(),
	}, nil
}
