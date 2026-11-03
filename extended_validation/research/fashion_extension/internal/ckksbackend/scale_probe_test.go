package ckksbackend

import "testing"

func TestRunScalarScaleProbe(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	results, err := ctx.RunScalarScaleProbe()
	if err != nil {
		t.Fatalf("RunScalarScaleProbe failed: %v", err)
	}

	if len(results) == 0 {
		t.Fatalf("expected non-empty scalar scale probe results")
	}

	seenRaw := false
	seenScaled := false

	for i, result := range results {
		if result.DecodeScaleCorrection <= 0 {
			t.Fatalf("case %d has invalid decode scale correction: %.10f", i, result.DecodeScaleCorrection)
		}

		if result.SelectedAbsError > 1e-3 {
			t.Fatalf(
				"case %d selected error too large: input %.10f scalar %.10f bias %.10f plain %.10f raw %.10f scaled %.10f selected %.10f mode=%s error %.10f",
				i,
				result.Input,
				result.Scalar,
				result.Bias,
				result.PlainValue,
				result.RawDecodedValue,
				result.ScaledDecodedValue,
				result.SelectedValue,
				result.SelectedInterpretation,
				result.SelectedAbsError,
			)
		}

		switch result.SelectedInterpretation {
		case ScaleInterpretationRaw:
			seenRaw = true
		case ScaleInterpretationDivideDefaultScale:
			seenScaled = true
		default:
			t.Fatalf("case %d has unknown selected interpretation: %s", i, result.SelectedInterpretation)
		}

		if result.FinalLevel > result.InitialLevel {
			t.Fatalf("case %d final level exceeds initial level: initial=%d final=%d", i, result.InitialLevel, result.FinalLevel)
		}
	}

	if !seenRaw {
		t.Fatalf("expected at least one raw interpretation case")
	}

	if !seenScaled {
		t.Fatalf("expected at least one divide_default_scale interpretation case")
	}
}

func TestRunScalarScaleProbeCaseWithoutBiasUsesRawInterpretation(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	result, err := ctx.RunScalarScaleProbeCase(ScalarScaleProbeCase{
		Input:  1.0,
		Scalar: 0.8,
		Bias:   0.0,
	})
	if err != nil {
		t.Fatalf("RunScalarScaleProbeCase failed: %v", err)
	}

	if result.SelectedInterpretation != ScaleInterpretationRaw {
		t.Fatalf("expected raw interpretation, got %s", result.SelectedInterpretation)
	}

	if result.SelectedAbsError > 1e-3 {
		t.Fatalf("selected error too large: %.10f", result.SelectedAbsError)
	}
}

func TestRunScalarScaleProbeCaseWithBiasUsesScaledInterpretation(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	result, err := ctx.RunScalarScaleProbeCase(ScalarScaleProbeCase{
		Input:  0.8,
		Scalar: 0.8,
		Bias:   -0.3,
	})
	if err != nil {
		t.Fatalf("RunScalarScaleProbeCase failed: %v", err)
	}

	if result.SelectedInterpretation != ScaleInterpretationDivideDefaultScale {
		t.Fatalf("expected divide_default_scale interpretation, got %s", result.SelectedInterpretation)
	}

	if result.SelectedAbsError > 1e-3 {
		t.Fatalf(
			"selected error too large: plain %.10f selected %.10f raw %.10f scaled %.10f error %.10f",
			result.PlainValue,
			result.SelectedValue,
			result.RawDecodedValue,
			result.ScaledDecodedValue,
			result.SelectedAbsError,
		)
	}

	t.Logf(
		"scalar scale probe ok: plain=%.10f raw=%.10f scaled=%.10f selected=%.10f mode=%s error=%.10f",
		result.PlainValue,
		result.RawDecodedValue,
		result.ScaledDecodedValue,
		result.SelectedValue,
		result.SelectedInterpretation,
		result.SelectedAbsError,
	)
}
