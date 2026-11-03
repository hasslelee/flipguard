package ckksbackend

import "testing"

func TestRunCubicProbe(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	results, err := ctx.RunCubicProbe()
	if err != nil {
		t.Fatalf("RunCubicProbe failed: %v", err)
	}

	if len(results) != len(DefaultCubicProbeCases()) {
		t.Fatalf("expected %d cubic probe results, got %d", len(DefaultCubicProbeCases()), len(results))
	}

	for i, result := range results {
		if result.ZDegree != 1 {
			t.Fatalf("case %d expected z degree 1, got %d", i, result.ZDegree)
		}

		if result.Z2Degree != 1 {
			t.Fatalf("case %d expected z2 degree 1 after relinearization, got %d", i, result.Z2Degree)
		}

		if result.Z3Degree != 1 {
			t.Fatalf("case %d expected z3 degree 1 after relinearization, got %d", i, result.Z3Degree)
		}

		if result.Z2Level > result.InitialLevel {
			t.Fatalf("case %d z2 level exceeds initial level: initial=%d z2=%d", i, result.InitialLevel, result.Z2Level)
		}

		if result.Z3Level > result.Z2Level {
			t.Fatalf("case %d z3 level exceeds z2 level: z2=%d z3=%d", i, result.Z2Level, result.Z3Level)
		}

		if result.SelectedAbsError > 1e-2 {
			t.Fatalf(
				"case %d selected error too large: z %.10f plain_z3 %.10f raw %.10f scaled %.10f selected %.10f mode=%s error %.10f",
				i,
				result.Z,
				result.PlainZ3,
				result.RawDecodedZ3,
				result.ScaledDecodedZ3,
				result.SelectedZ3,
				result.SelectedInterpretation,
				result.SelectedAbsError,
			)
		}
	}
}

func TestRunCubicProbeCase(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	result, err := ctx.RunCubicProbeCase(CubicProbeCase{
		Z: 0.61,
	})
	if err != nil {
		t.Fatalf("RunCubicProbeCase failed: %v", err)
	}

	if result.SelectedAbsError > 1e-2 {
		t.Fatalf(
			"selected error too large: z %.10f plain_z3 %.10f selected_z3 %.10f mode=%s error %.10f",
			result.Z,
			result.PlainZ3,
			result.SelectedZ3,
			result.SelectedInterpretation,
			result.SelectedAbsError,
		)
	}

	t.Logf(
		"cubic probe ok: z=%.10f plain_z3=%.10f raw=%.10f scaled=%.10f selected=%.10f mode=%s error=%.10f z_degree=%d z2_degree=%d z3_degree=%d initial_level=%d z2_level=%d z3_level=%d",
		result.Z,
		result.PlainZ3,
		result.RawDecodedZ3,
		result.ScaledDecodedZ3,
		result.SelectedZ3,
		result.SelectedInterpretation,
		result.SelectedAbsError,
		result.ZDegree,
		result.Z2Degree,
		result.Z3Degree,
		result.InitialLevel,
		result.Z2Level,
		result.Z3Level,
	)
}
