package ckksbackend

import "testing"

func TestRunMultiplicationProbe(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	results, err := ctx.RunMultiplicationProbe()
	if err != nil {
		t.Fatalf("RunMultiplicationProbe failed: %v", err)
	}

	if len(results) == 0 {
		t.Fatalf("expected non-empty multiplication probe results")
	}

	for i, result := range results {
		if result.InputDegree != 1 {
			t.Fatalf("case %d expected input degree 1, got %d", i, result.InputDegree)
		}

		if result.OutputDegree < 1 {
			t.Fatalf("case %d expected positive output degree, got %d", i, result.OutputDegree)
		}

		if result.FinalLevel > result.InitialLevel {
			t.Fatalf("case %d final level exceeds initial level: initial=%d final=%d", i, result.InitialLevel, result.FinalLevel)
		}

		if result.SelectedAbsError > 1e-2 {
			t.Fatalf(
				"case %d selected error too large: z %.10f plain_z2 %.10f raw %.10f scaled %.10f selected %.10f mode=%s error %.10f",
				i,
				result.Z,
				result.PlainZ2,
				result.RawDecodedZ2,
				result.ScaledDecodedZ2,
				result.SelectedZ2,
				result.SelectedInterpretation,
				result.SelectedAbsError,
			)
		}
	}
}

func TestRunMultiplicationProbeCase(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	result, err := ctx.RunMultiplicationProbeCase(MultiplicationProbeCase{
		Z: 0.61,
	})
	if err != nil {
		t.Fatalf("RunMultiplicationProbeCase failed: %v", err)
	}

	if result.SelectedAbsError > 1e-2 {
		t.Fatalf(
			"selected error too large: z %.10f plain_z2 %.10f selected_z2 %.10f mode=%s error %.10f",
			result.Z,
			result.PlainZ2,
			result.SelectedZ2,
			result.SelectedInterpretation,
			result.SelectedAbsError,
		)
	}

	t.Logf(
		"multiplication probe ok: z=%.10f plain_z2=%.10f raw=%.10f scaled=%.10f selected=%.10f mode=%s error=%.10f input_degree=%d output_degree=%d initial_level=%d final_level=%d",
		result.Z,
		result.PlainZ2,
		result.RawDecodedZ2,
		result.ScaledDecodedZ2,
		result.SelectedZ2,
		result.SelectedInterpretation,
		result.SelectedAbsError,
		result.InputDegree,
		result.OutputDegree,
		result.InitialLevel,
		result.FinalLevel,
	)
}
