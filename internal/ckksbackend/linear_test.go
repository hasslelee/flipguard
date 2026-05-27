package ckksbackend

import "testing"

func TestEvalLogRegSmallLinearPlain(t *testing.T) {
	input := LogRegSmallInput{
		X1: 0.8,
		X2: -0.3,
		X3: 0.1,
	}

	got := EvalLogRegSmallLinearPlain(input)

	want := 0.8*input.X1 - 0.5*input.X2 + 1.2*input.X3 - 0.3
	if got != want {
		t.Fatalf("unexpected plain z: got %.10f want %.10f", got, want)
	}
}

func TestEvalLogRegSmallLinearEncrypted(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	input := LogRegSmallInput{
		X1: 0.8,
		X2: -0.3,
		X3: 0.1,
	}

	result, err := ctx.EvalLogRegSmallLinearEncrypted(input)
	if err != nil {
		t.Fatalf("EvalLogRegSmallLinearEncrypted failed: %v", err)
	}

	if result.AbsError > 1e-3 {
		t.Fatalf(
			"linear encrypted error too large: plain_z %.10f ckks_z %.10f abs_error %.10f",
			result.PlainZ,
			result.CKKSZ,
			result.AbsError,
		)
	}

	if result.FinalLevel > result.InitialLevel {
		t.Fatalf("final level must not exceed initial level: initial=%d final=%d", result.InitialLevel, result.FinalLevel)
	}

	t.Logf(
		"linear encrypted ok: plain_z=%.10f ckks_z=%.10f abs_error=%.10f initial_level=%d final_level=%d log_default_scale=%d",
		result.PlainZ,
		result.CKKSZ,
		result.AbsError,
		result.InitialLevel,
		result.FinalLevel,
		result.LogDefaultScale,
	)
}

func TestEvalLogRegSmallLinearEncryptedMultipleInputs(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	inputs := []LogRegSmallInput{
		{X1: 0.0, X2: 0.0, X3: 0.0},
		{X1: 1.0, X2: 0.5, X3: -0.25},
		{X1: -0.7, X2: 0.25, X3: 0.9},
	}

	for _, input := range inputs {
		result, err := ctx.EvalLogRegSmallLinearEncrypted(input)
		if err != nil {
			t.Fatalf("EvalLogRegSmallLinearEncrypted failed for input %+v: %v", input, err)
		}

		if result.AbsError > 1e-3 {
			t.Fatalf(
				"linear encrypted error too large for input %+v: plain_z %.10f ckks_z %.10f abs_error %.10f",
				input,
				result.PlainZ,
				result.CKKSZ,
				result.AbsError,
			)
		}
	}
}
