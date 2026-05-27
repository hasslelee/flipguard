package ckksbackend

import "testing"

func TestRunBiasAdditionProbe(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	pairs, err := ctx.RunBiasAdditionProbe()
	if err != nil {
		t.Fatalf("RunBiasAdditionProbe failed: %v", err)
	}

	if len(pairs) == 0 {
		t.Fatalf("expected non-empty bias addition probe pairs")
	}

	for i, pair := range pairs {
		if pair.ScalarBias.Method != BiasAdditionScalar {
			t.Fatalf("case %d expected scalar bias method, got %s", i, pair.ScalarBias.Method)
		}

		if pair.PlaintextBias.Method != BiasAdditionPlaintext {
			t.Fatalf("case %d expected plaintext bias method, got %s", i, pair.PlaintextBias.Method)
		}

		if pair.ScalarBias.SelectedAbsError > 1e-3 {
			t.Fatalf(
				"case %d scalar-bias selected error too large: plain %.10f selected %.10f mode=%s error %.10f",
				i,
				pair.ScalarBias.PlainValue,
				pair.ScalarBias.SelectedValue,
				pair.ScalarBias.SelectedInterpretation,
				pair.ScalarBias.SelectedAbsError,
			)
		}

		if pair.PlaintextBias.SelectedAbsError > 1e-3 {
			t.Fatalf(
				"case %d plaintext-bias selected error too large: plain %.10f selected %.10f mode=%s error %.10f",
				i,
				pair.PlaintextBias.PlainValue,
				pair.PlaintextBias.SelectedValue,
				pair.PlaintextBias.SelectedInterpretation,
				pair.PlaintextBias.SelectedAbsError,
			)
		}
	}
}

func TestPlaintextBiasPrefersRawInterpretation(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	result, err := ctx.RunBiasAdditionProbeCase(BiasAdditionProbeCase{
		Input:  0.8,
		Scalar: 0.8,
		Bias:   -0.3,
	}, BiasAdditionPlaintext)
	if err != nil {
		t.Fatalf("RunBiasAdditionProbeCase failed: %v", err)
	}

	if result.SelectedInterpretation != ScaleInterpretationRaw {
		t.Fatalf(
			"expected plaintext bias to prefer raw interpretation, got %s: plain %.10f raw %.10f scaled %.10f raw_error %.10f scaled_error %.10f",
			result.SelectedInterpretation,
			result.PlainValue,
			result.RawDecodedValue,
			result.ScaledDecodedValue,
			result.RawAbsError,
			result.ScaledAbsError,
		)
	}

	if result.SelectedAbsError > 1e-3 {
		t.Fatalf("plaintext-bias selected error too large: %.10f", result.SelectedAbsError)
	}
}

func TestScalarBiasMayPreferScaledInterpretation(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	result, err := ctx.RunBiasAdditionProbeCase(BiasAdditionProbeCase{
		Input:  0.8,
		Scalar: 0.8,
		Bias:   -0.3,
	}, BiasAdditionScalar)
	if err != nil {
		t.Fatalf("RunBiasAdditionProbeCase failed: %v", err)
	}

	if result.SelectedInterpretation != ScaleInterpretationDivideDefaultScale {
		t.Fatalf(
			"expected scalar bias to prefer divide_default_scale interpretation, got %s: plain %.10f raw %.10f scaled %.10f raw_error %.10f scaled_error %.10f",
			result.SelectedInterpretation,
			result.PlainValue,
			result.RawDecodedValue,
			result.ScaledDecodedValue,
			result.RawAbsError,
			result.ScaledAbsError,
		)
	}
}
