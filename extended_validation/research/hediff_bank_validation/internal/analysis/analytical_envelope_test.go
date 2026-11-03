package analysis

import (
	"math"
	"strings"
	"testing"
)

func TestEvaluateLinearPoly3EnvelopeZeroUncertainty(
	t *testing.T,
) {
	result, err := EvaluateLinearPoly3Envelope(
		LinearPoly3EnvelopeConfig{
			Affine: AffineEnvelopeConfig{
				Inputs: []ErrorEnvelope{
					{
						ExactAbsBound: 2,
					},
				},
				Weights: []float64{3},
				Bias:    1,
			},
		},
	)
	if err != nil {
		t.Fatalf(
			"EvaluateLinearPoly3Envelope failed: %v",
			err,
		)
	}

	if result.Z.ExactAbsBound != 7 {
		t.Fatalf(
			"z exact bound: got %.12g, expected 7",
			result.Z.ExactAbsBound,
		)
	}
	if result.Z.ErrorAbsBound != 0 {
		t.Fatalf(
			"z error bound: got %.12g, expected 0",
			result.Z.ErrorAbsBound,
		)
	}
	if result.Score.ErrorAbsBound != 0 {
		t.Fatalf(
			"score error bound: got %.12g, expected 0",
			result.Score.ErrorAbsBound,
		)
	}
}

func TestEvaluateLinearPoly3EnvelopeBoundsPerturbedExecution(
	t *testing.T,
) {
	exactInput := 1.2
	inputDelta := -0.01

	exactWeight := 0.8
	weightDelta := 0.005

	exactBias := -0.1
	biasDelta := 0.002

	linearCoefficientDelta := 0.0001
	cubicCoefficientDelta := -0.00002
	outputBiasDelta := 0.00003

	result, err := EvaluateLinearPoly3Envelope(
		LinearPoly3EnvelopeConfig{
			Affine: AffineEnvelopeConfig{
				Inputs: []ErrorEnvelope{
					{
						ExactAbsBound: math.Abs(exactInput),
						ErrorAbsBound: math.Abs(inputDelta),
					},
				},
				Weights: []float64{
					exactWeight,
				},
				Bias: exactBias,

				WeightAbsErrors: []float64{
					math.Abs(weightDelta),
				},
				BiasAbsError: math.Abs(biasDelta),
			},

			LinearCoefficientAbsError: math.Abs(linearCoefficientDelta),
			CubicCoefficientAbsError:  math.Abs(cubicCoefficientDelta),

			OutputBiasAbsError: math.Abs(outputBiasDelta),
		},
	)
	if err != nil {
		t.Fatalf(
			"EvaluateLinearPoly3Envelope failed: %v",
			err,
		)
	}

	exactZ :=
		exactWeight*exactInput +
			exactBias
	approxZ :=
		(exactWeight+weightDelta)*
			(exactInput+inputDelta) +
			exactBias +
			biasDelta

	exactScore :=
		0.5 +
			0.197*exactZ -
			0.004*exactZ*exactZ*exactZ

	approxScore :=
		(0.5 + outputBiasDelta) +
			(0.197+linearCoefficientDelta)*
				approxZ +
			(-0.004+cubicCoefficientDelta)*
				approxZ*approxZ*approxZ

	actualError := math.Abs(
		approxScore - exactScore,
	)

	if actualError >
		result.Score.ErrorAbsBound {
		t.Fatalf(
			"actual score error %.12g exceeds propagated bound %.12g",
			actualError,
			result.Score.ErrorAbsBound,
		)
	}

	if math.Abs(approxZ-exactZ) >
		result.Z.ErrorAbsBound {
		t.Fatalf(
			"actual z error %.12g exceeds propagated bound %.12g",
			math.Abs(approxZ-exactZ),
			result.Z.ErrorAbsBound,
		)
	}
}

func TestEvaluateLinearPoly3EnvelopeResidualsAreMonotone(
	t *testing.T,
) {
	baseConfig := LinearPoly3EnvelopeConfig{
		Affine: AffineEnvelopeConfig{
			Inputs: []ErrorEnvelope{
				{
					ExactAbsBound: 1,
					ErrorAbsBound: 0.01,
				},
			},
			Weights: []float64{0.5},
		},
	}

	base, err := EvaluateLinearPoly3Envelope(
		baseConfig,
	)
	if err != nil {
		t.Fatalf(
			"base envelope failed: %v",
			err,
		)
	}

	baseConfig.ZSquareResidualAbsError = 0.001
	baseConfig.ZCubeResidualAbsError = 0.002
	baseConfig.LinearScaleResidualAbsError = 0.003
	baseConfig.CubicScaleResidualAbsError = 0.004
	baseConfig.TermAdditionResidualAbsError = 0.005
	baseConfig.OutputBiasAdditionAbsError = 0.006

	withResiduals, err :=
		EvaluateLinearPoly3Envelope(baseConfig)
	if err != nil {
		t.Fatalf(
			"residual envelope failed: %v",
			err,
		)
	}

	if withResiduals.Score.ErrorAbsBound <=
		base.Score.ErrorAbsBound {
		t.Fatalf(
			"expected positive primitive residuals to increase score bound: base=%.12g residual=%.12g",
			base.Score.ErrorAbsBound,
			withResiduals.Score.ErrorAbsBound,
		)
	}
}

func TestEvaluateAffineEnvelopeRejectsDimensionMismatch(
	t *testing.T,
) {
	_, err := EvaluateAffineEnvelope(
		AffineEnvelopeConfig{
			Inputs: []ErrorEnvelope{
				{
					ExactAbsBound: 1,
				},
				{
					ExactAbsBound: 2,
				},
			},
			Weights: []float64{1},
		},
	)
	if err == nil {
		t.Fatal(
			"expected affine dimension mismatch to fail",
		)
	}
	if !strings.Contains(
		err.Error(),
		"weight count",
	) {
		t.Fatalf(
			"unexpected dimension error: %v",
			err,
		)
	}
}

func TestMultiplyErrorEnvelopesMatchesExpansion(
	t *testing.T,
) {
	left := ErrorEnvelope{
		ExactAbsBound: 2,
		ErrorAbsBound: 0.1,
	}
	right := ErrorEnvelope{
		ExactAbsBound: 3,
		ErrorAbsBound: 0.2,
	}

	result, err := MultiplyErrorEnvelopes(
		left,
		right,
		0.03,
	)
	if err != nil {
		t.Fatalf(
			"MultiplyErrorEnvelopes failed: %v",
			err,
		)
	}

	expected :=
		2*0.2 +
			3*0.1 +
			0.1*0.2 +
			0.03

	if math.Abs(
		result.ErrorAbsBound-expected,
	) > 1e-15 {
		t.Fatalf(
			"multiply bound: got %.12g, expected %.12g",
			result.ErrorAbsBound,
			expected,
		)
	}
}
