package analysis

import (
	"fmt"
	"math"
)

// ErrorEnvelope bounds an exact scalar value and its approximation error.
//
// ExactAbsBound:
//
//	|v| <= ExactAbsBound
//
// ErrorAbsBound:
//
//	|vApprox - v| <= ErrorAbsBound
//
// The structure does not by itself prove where primitive residual bounds came
// from. It only propagates supplied bounds through supported arithmetic.
type ErrorEnvelope struct {
	ExactAbsBound float64
	ErrorAbsBound float64
}

// AffineEnvelopeConfig defines the primitive assumptions for:
//
//	z = sum_i weights[i] * inputs[i] + bias
//
// WeightAbsErrors bounds encoded coefficient errors. ProductResidualAbsErrors
// bounds residual error introduced by each ciphertext-plaintext product.
//
// AdditionResidualAbsError is an aggregate bound covering the weighted-term
// accumulation and bias addition. It must not be inferred from observations.
type AffineEnvelopeConfig struct {
	Inputs  []ErrorEnvelope
	Weights []float64
	Bias    float64

	WeightAbsErrors []float64
	BiasAbsError    float64

	ProductResidualAbsErrors []float64
	AdditionResidualAbsError float64
}

// LinearPoly3EnvelopeConfig defines primitive error assumptions for the exact
// supported graph:
//
//	z = w^T x + b
//	y = 0.5 + 0.197*z - 0.004*z^3
//
// Each residual field must be supplied by a separate CKKS primitive-bound
// derivation. Zero means that no additional residual is assumed for that
// operation; it must not be interpreted as proven unless its source supports
// zero.
type LinearPoly3EnvelopeConfig struct {
	Affine AffineEnvelopeConfig

	ZSquareResidualAbsError float64
	ZCubeResidualAbsError   float64

	LinearCoefficientAbsError float64
	CubicCoefficientAbsError  float64

	LinearScaleResidualAbsError float64
	CubicScaleResidualAbsError  float64

	TermAdditionResidualAbsError float64

	OutputBiasAbsError         float64
	OutputBiasAdditionAbsError float64
}

// LinearPoly3EnvelopeResult contains the bound at every supported graph node.
type LinearPoly3EnvelopeResult struct {
	Z ErrorEnvelope

	ZSquared ErrorEnvelope
	ZCubed   ErrorEnvelope

	LinearTerm ErrorEnvelope
	CubicTerm  ErrorEnvelope

	Score ErrorEnvelope
}

// ConstantErrorEnvelope constructs an envelope for an encoded constant.
func ConstantErrorEnvelope(
	value float64,
	encodingError float64,
) (ErrorEnvelope, error) {
	if !isFiniteEnvelopeValue(value) {
		return ErrorEnvelope{}, fmt.Errorf(
			"constant value must be finite",
		)
	}
	if err := validateEnvelopeResidual(
		"constant encoding error",
		encodingError,
	); err != nil {
		return ErrorEnvelope{}, err
	}

	return ErrorEnvelope{
		ExactAbsBound: math.Abs(value),
		ErrorAbsBound: encodingError,
	}, nil
}

// AddErrorEnvelopes propagates error through approximate addition.
//
// If the approximate addition itself introduces residual r:
//
//	e_out <= e_left + e_right + r
func AddErrorEnvelopes(
	left ErrorEnvelope,
	right ErrorEnvelope,
	residualAbsError float64,
) (ErrorEnvelope, error) {
	if err := validateErrorEnvelope(
		"left addend",
		left,
	); err != nil {
		return ErrorEnvelope{}, err
	}
	if err := validateErrorEnvelope(
		"right addend",
		right,
	); err != nil {
		return ErrorEnvelope{}, err
	}
	if err := validateEnvelopeResidual(
		"addition residual",
		residualAbsError,
	); err != nil {
		return ErrorEnvelope{}, err
	}

	return ErrorEnvelope{
		ExactAbsBound: left.ExactAbsBound +
			right.ExactAbsBound,

		ErrorAbsBound: left.ErrorAbsBound +
			right.ErrorAbsBound +
			residualAbsError,
	}, nil
}

// MultiplyErrorEnvelopes propagates error through approximate multiplication.
//
// For exact a,b and approximations a+da,b+db:
//
//	|(a+da)(b+db)-ab|
//	  <= |a||db| + |b||da| + |da||db|
//
// The supplied residual covers error introduced by the approximate multiply
// beyond operand uncertainty.
func MultiplyErrorEnvelopes(
	left ErrorEnvelope,
	right ErrorEnvelope,
	residualAbsError float64,
) (ErrorEnvelope, error) {
	if err := validateErrorEnvelope(
		"left multiplicand",
		left,
	); err != nil {
		return ErrorEnvelope{}, err
	}
	if err := validateErrorEnvelope(
		"right multiplicand",
		right,
	); err != nil {
		return ErrorEnvelope{}, err
	}
	if err := validateEnvelopeResidual(
		"multiplication residual",
		residualAbsError,
	); err != nil {
		return ErrorEnvelope{}, err
	}

	return ErrorEnvelope{
		ExactAbsBound: left.ExactAbsBound *
			right.ExactAbsBound,

		ErrorAbsBound: left.ExactAbsBound*
			right.ErrorAbsBound +
			right.ExactAbsBound*
				left.ErrorAbsBound +
			left.ErrorAbsBound*
				right.ErrorAbsBound +
			residualAbsError,
	}, nil
}

// ScaleErrorEnvelope propagates error through multiplication by an encoded
// scalar coefficient.
//
// For exact coefficient c with encoded error dc:
//
//	|(c+dc)(v+dv)-cv|
//	  <= |c||dv| + |dc||v| + |dc||dv|
func ScaleErrorEnvelope(
	input ErrorEnvelope,
	coefficient float64,
	coefficientAbsError float64,
	residualAbsError float64,
) (ErrorEnvelope, error) {
	if err := validateErrorEnvelope(
		"scale input",
		input,
	); err != nil {
		return ErrorEnvelope{}, err
	}
	if !isFiniteEnvelopeValue(coefficient) {
		return ErrorEnvelope{}, fmt.Errorf(
			"scale coefficient must be finite",
		)
	}
	if err := validateEnvelopeResidual(
		"coefficient encoding error",
		coefficientAbsError,
	); err != nil {
		return ErrorEnvelope{}, err
	}
	if err := validateEnvelopeResidual(
		"scale residual",
		residualAbsError,
	); err != nil {
		return ErrorEnvelope{}, err
	}

	coefficientAbs := math.Abs(coefficient)

	return ErrorEnvelope{
		ExactAbsBound: coefficientAbs *
			input.ExactAbsBound,

		ErrorAbsBound: coefficientAbs*
			input.ErrorAbsBound +
			coefficientAbsError*
				input.ExactAbsBound +
			coefficientAbsError*
				input.ErrorAbsBound +
			residualAbsError,
	}, nil
}

// EvaluateAffineEnvelope propagates conditional primitive bounds through an
// affine graph.
func EvaluateAffineEnvelope(
	config AffineEnvelopeConfig,
) (ErrorEnvelope, error) {
	if len(config.Inputs) == 0 {
		return ErrorEnvelope{}, fmt.Errorf(
			"affine input list is empty",
		)
	}
	if len(config.Weights) != len(config.Inputs) {
		return ErrorEnvelope{}, fmt.Errorf(
			"affine weight count %d does not match input count %d",
			len(config.Weights),
			len(config.Inputs),
		)
	}
	if len(config.WeightAbsErrors) != 0 &&
		len(config.WeightAbsErrors) != len(config.Inputs) {
		return ErrorEnvelope{}, fmt.Errorf(
			"affine weight-error count %d does not match input count %d",
			len(config.WeightAbsErrors),
			len(config.Inputs),
		)
	}
	if len(config.ProductResidualAbsErrors) != 0 &&
		len(config.ProductResidualAbsErrors) !=
			len(config.Inputs) {
		return ErrorEnvelope{}, fmt.Errorf(
			"affine product-residual count %d does not match input count %d",
			len(config.ProductResidualAbsErrors),
			len(config.Inputs),
		)
	}
	if !isFiniteEnvelopeValue(config.Bias) {
		return ErrorEnvelope{}, fmt.Errorf(
			"affine bias must be finite",
		)
	}
	if err := validateEnvelopeResidual(
		"affine bias encoding error",
		config.BiasAbsError,
	); err != nil {
		return ErrorEnvelope{}, err
	}
	if err := validateEnvelopeResidual(
		"affine addition residual",
		config.AdditionResidualAbsError,
	); err != nil {
		return ErrorEnvelope{}, err
	}

	result := ErrorEnvelope{
		ExactAbsBound: math.Abs(config.Bias),
		ErrorAbsBound: config.BiasAbsError +
			config.AdditionResidualAbsError,
	}

	for index, input := range config.Inputs {
		if err := validateErrorEnvelope(
			fmt.Sprintf(
				"affine input %d",
				index,
			),
			input,
		); err != nil {
			return ErrorEnvelope{}, err
		}

		weight := config.Weights[index]
		if !isFiniteEnvelopeValue(weight) {
			return ErrorEnvelope{}, fmt.Errorf(
				"affine weight %d must be finite",
				index,
			)
		}

		weightError := optionalEnvelopeResidual(
			config.WeightAbsErrors,
			index,
		)
		productResidual := optionalEnvelopeResidual(
			config.ProductResidualAbsErrors,
			index,
		)

		if err := validateEnvelopeResidual(
			fmt.Sprintf(
				"affine weight error %d",
				index,
			),
			weightError,
		); err != nil {
			return ErrorEnvelope{}, err
		}
		if err := validateEnvelopeResidual(
			fmt.Sprintf(
				"affine product residual %d",
				index,
			),
			productResidual,
		); err != nil {
			return ErrorEnvelope{}, err
		}

		weightAbs := math.Abs(weight)

		result.ExactAbsBound +=
			weightAbs * input.ExactAbsBound

		result.ErrorAbsBound +=
			weightAbs*input.ErrorAbsBound +
				weightError*input.ExactAbsBound +
				weightError*input.ErrorAbsBound +
				productResidual
	}

	return result, nil
}

// EvaluateLinearPoly3Envelope propagates supplied primitive error bounds through
// the exact linear_poly3 graph used by the tabular backend.
//
// This function is a conditional arithmetic derivation. It must not be used to
// issue an analytical certificate until every primitive residual in config has
// been bound by a scoped CKKS derivation.
func EvaluateLinearPoly3Envelope(
	config LinearPoly3EnvelopeConfig,
) (LinearPoly3EnvelopeResult, error) {
	residuals := []struct {
		name  string
		value float64
	}{
		{
			"z-square multiplication residual",
			config.ZSquareResidualAbsError,
		},
		{
			"z-cube multiplication residual",
			config.ZCubeResidualAbsError,
		},
		{
			"linear coefficient encoding error",
			config.LinearCoefficientAbsError,
		},
		{
			"cubic coefficient encoding error",
			config.CubicCoefficientAbsError,
		},
		{
			"linear scale residual",
			config.LinearScaleResidualAbsError,
		},
		{
			"cubic scale residual",
			config.CubicScaleResidualAbsError,
		},
		{
			"term addition residual",
			config.TermAdditionResidualAbsError,
		},
		{
			"output bias encoding error",
			config.OutputBiasAbsError,
		},
		{
			"output bias addition residual",
			config.OutputBiasAdditionAbsError,
		},
	}

	for _, residual := range residuals {
		if err := validateEnvelopeResidual(
			residual.name,
			residual.value,
		); err != nil {
			return LinearPoly3EnvelopeResult{}, err
		}
	}

	z, err := EvaluateAffineEnvelope(
		config.Affine,
	)
	if err != nil {
		return LinearPoly3EnvelopeResult{}, fmt.Errorf(
			"evaluate linear_poly3 affine envelope: %w",
			err,
		)
	}

	zSquared, err := MultiplyErrorEnvelopes(
		z,
		z,
		config.ZSquareResidualAbsError,
	)
	if err != nil {
		return LinearPoly3EnvelopeResult{}, fmt.Errorf(
			"evaluate linear_poly3 z squared: %w",
			err,
		)
	}

	zCubed, err := MultiplyErrorEnvelopes(
		zSquared,
		z,
		config.ZCubeResidualAbsError,
	)
	if err != nil {
		return LinearPoly3EnvelopeResult{}, fmt.Errorf(
			"evaluate linear_poly3 z cubed: %w",
			err,
		)
	}

	linearTerm, err := ScaleErrorEnvelope(
		z,
		0.197,
		config.LinearCoefficientAbsError,
		config.LinearScaleResidualAbsError,
	)
	if err != nil {
		return LinearPoly3EnvelopeResult{}, fmt.Errorf(
			"evaluate linear_poly3 linear term: %w",
			err,
		)
	}

	cubicTerm, err := ScaleErrorEnvelope(
		zCubed,
		-0.004,
		config.CubicCoefficientAbsError,
		config.CubicScaleResidualAbsError,
	)
	if err != nil {
		return LinearPoly3EnvelopeResult{}, fmt.Errorf(
			"evaluate linear_poly3 cubic term: %w",
			err,
		)
	}

	terms, err := AddErrorEnvelopes(
		linearTerm,
		cubicTerm,
		config.TermAdditionResidualAbsError,
	)
	if err != nil {
		return LinearPoly3EnvelopeResult{}, fmt.Errorf(
			"add linear_poly3 polynomial terms: %w",
			err,
		)
	}

	outputBias, err := ConstantErrorEnvelope(
		0.5,
		config.OutputBiasAbsError,
	)
	if err != nil {
		return LinearPoly3EnvelopeResult{}, fmt.Errorf(
			"construct linear_poly3 output bias: %w",
			err,
		)
	}

	score, err := AddErrorEnvelopes(
		terms,
		outputBias,
		config.OutputBiasAdditionAbsError,
	)
	if err != nil {
		return LinearPoly3EnvelopeResult{}, fmt.Errorf(
			"add linear_poly3 output bias: %w",
			err,
		)
	}

	return LinearPoly3EnvelopeResult{
		Z: z,

		ZSquared: zSquared,
		ZCubed:   zCubed,

		LinearTerm: linearTerm,
		CubicTerm:  cubicTerm,

		Score: score,
	}, nil
}

func validateErrorEnvelope(
	name string,
	envelope ErrorEnvelope,
) error {
	if !isFiniteEnvelopeValue(
		envelope.ExactAbsBound,
	) || envelope.ExactAbsBound < 0 {
		return fmt.Errorf(
			"%s exact absolute bound must be finite and non-negative",
			name,
		)
	}
	if !isFiniteEnvelopeValue(
		envelope.ErrorAbsBound,
	) || envelope.ErrorAbsBound < 0 {
		return fmt.Errorf(
			"%s error absolute bound must be finite and non-negative",
			name,
		)
	}

	return nil
}

func validateEnvelopeResidual(
	name string,
	value float64,
) error {
	if !isFiniteEnvelopeValue(value) ||
		value < 0 {
		return fmt.Errorf(
			"%s must be finite and non-negative",
			name,
		)
	}

	return nil
}

func optionalEnvelopeResidual(
	values []float64,
	index int,
) float64 {
	if len(values) == 0 {
		return 0
	}

	return values[index]
}

func isFiniteEnvelopeValue(
	value float64,
) bool {
	return !math.IsNaN(value) &&
		!math.IsInf(value, 0)
}
