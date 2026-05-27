package ckksbackend

import (
	"fmt"
	"math"

	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// BiasAdditionMethod identifies how a scalar bias is added to a CKKS value.
type BiasAdditionMethod string

const (
	// BiasAdditionScalar uses evaluator.AddNew(ct, float64).
	BiasAdditionScalar BiasAdditionMethod = "scalar_bias"

	// BiasAdditionPlaintext encodes the bias as a CKKS plaintext and uses
	// evaluator.AddNew(ct, plaintext).
	BiasAdditionPlaintext BiasAdditionMethod = "plaintext_bias"
)

// BiasAdditionProbeCase defines one linear scalar-multiply-and-bias probe.
type BiasAdditionProbeCase struct {
	Input  float64
	Scalar float64
	Bias   float64
}

// BiasAdditionProbeResult records one bias-addition probe result.
type BiasAdditionProbeResult struct {
	Method BiasAdditionMethod

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

	InitialLevel int
	FinalLevel   int

	LogDefaultScale int
}

// BiasAdditionProbePair stores the scalar-bias and plaintext-bias results for
// the same logical expression.
type BiasAdditionProbePair struct {
	Case BiasAdditionProbeCase

	ScalarBias    BiasAdditionProbeResult
	PlaintextBias BiasAdditionProbeResult
}

// DefaultBiasAdditionProbeCases returns deterministic cases that include the
// bias patterns used by logreg_small.
func DefaultBiasAdditionProbeCases() []BiasAdditionProbeCase {
	return []BiasAdditionProbeCase{
		{
			Input:  0.8,
			Scalar: 0.8,
			Bias:   -0.3,
		},
		{
			Input:  -0.7,
			Scalar: 1.2,
			Bias:   0.25,
		},
		{
			Input:  1.0,
			Scalar: -0.5,
			Bias:   -0.3,
		},
		{
			Input:  0.25,
			Scalar: 0.197,
			Bias:   0.5,
		},
	}
}

// RunBiasAdditionProbe compares scalar-bias addition and plaintext-bias addition.
func (c Context) RunBiasAdditionProbe() ([]BiasAdditionProbePair, error) {
	cases := DefaultBiasAdditionProbeCases()
	pairs := make([]BiasAdditionProbePair, 0, len(cases))

	for i, probeCase := range cases {
		scalarResult, err := c.RunBiasAdditionProbeCase(probeCase, BiasAdditionScalar)
		if err != nil {
			return nil, fmt.Errorf("run scalar-bias probe case %d: %w", i, err)
		}

		plaintextResult, err := c.RunBiasAdditionProbeCase(probeCase, BiasAdditionPlaintext)
		if err != nil {
			return nil, fmt.Errorf("run plaintext-bias probe case %d: %w", i, err)
		}

		pairs = append(pairs, BiasAdditionProbePair{
			Case: probeCase,

			ScalarBias:    scalarResult,
			PlaintextBias: plaintextResult,
		})
	}

	return pairs, nil
}

// RunBiasAdditionProbeCase evaluates y = scalar*input + bias using the selected
// bias-addition method.
func (c Context) RunBiasAdditionProbeCase(
	probeCase BiasAdditionProbeCase,
	method BiasAdditionMethod,
) (BiasAdditionProbeResult, error) {
	encoder := ckks.NewEncoder(c.Params)

	kgen := ckks.NewKeyGenerator(c.Params)
	sk, pk := kgen.GenKeyPairNew()

	encryptor := ckks.NewEncryptor(c.Params, pk)
	decryptor := ckks.NewDecryptor(c.Params, sk)

	evaluator := ckks.NewEvaluator(c.Params, nil)

	ct, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.Input)
	if err != nil {
		return BiasAdditionProbeResult{}, fmt.Errorf("encrypt input: %w", err)
	}

	mul, err := evaluator.MulNew(ct, probeCase.Scalar)
	if err != nil {
		return BiasAdditionProbeResult{}, fmt.Errorf("multiply by scalar: %w", err)
	}

	var out *rlwe.Ciphertext

	switch method {
	case BiasAdditionScalar:
		out, err = evaluator.AddNew(mul, probeCase.Bias)
		if err != nil {
			return BiasAdditionProbeResult{}, fmt.Errorf("add scalar bias: %w", err)
		}

	case BiasAdditionPlaintext:
		biasPlaintext, err := c.encodeReplicatedPlaintextAtLevel(encoder, probeCase.Bias, mul.Level())
		if err != nil {
			return BiasAdditionProbeResult{}, fmt.Errorf("encode plaintext bias: %w", err)
		}

		out, err = evaluator.AddNew(mul, biasPlaintext)
		if err != nil {
			return BiasAdditionProbeResult{}, fmt.Errorf("add plaintext bias: %w", err)
		}

	default:
		return BiasAdditionProbeResult{}, fmt.Errorf("unsupported bias addition method: %s", method)
	}

	raw, err := c.decryptFirstSlot(encoder, decryptor, out)
	if err != nil {
		return BiasAdditionProbeResult{}, fmt.Errorf("decrypt probe output: %w", err)
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

	return BiasAdditionProbeResult{
		Method: method,

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

		InitialLevel: c.MaxLevel(),
		FinalLevel:   out.Level(),

		LogDefaultScale: c.LogDefaultScale(),
	}, nil
}

func (c Context) encodeReplicatedPlaintextAtLevel(
	encoder *ckks.Encoder,
	value float64,
	level int,
) (*rlwe.Plaintext, error) {
	values := make([]complex128, c.Params.MaxSlots())
	for i := range values {
		values[i] = complex(value, 0)
	}

	pt := ckks.NewPlaintext(c.Params, level)
	if err := encoder.Encode(values, pt); err != nil {
		return nil, fmt.Errorf("encode replicated plaintext: %w", err)
	}

	return pt, nil
}
