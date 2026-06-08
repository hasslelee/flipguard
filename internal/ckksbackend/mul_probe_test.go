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

	wantCount := len(DefaultMultiplicationProbeCases()) * len(DefaultMultiplicationProbeMethods())
	if len(results) != wantCount {
		t.Fatalf("expected %d multiplication probe results, got %d", wantCount, len(results))
	}

	seen := map[MultiplicationProbeMethod]bool{}

	for i, result := range results {
		seen[result.Method] = true

		if result.InputDegree != 1 {
			t.Fatalf("case %d expected input degree 1, got %d", i, result.InputDegree)
		}

		if result.OutputDegree < 1 {
			t.Fatalf("case %d expected positive output degree, got %d", i, result.OutputDegree)
		}

		if methodUsesRelinearization(result.Method) && result.OutputDegree != 1 {
			t.Fatalf("case %d method %s expected output degree 1, got %d", i, result.Method, result.OutputDegree)
		}

		if methodUsesRescale(result.Method) && result.FinalLevel >= result.InitialLevel {
			t.Fatalf("case %d method %s expected level consumption, initial=%d final=%d", i, result.Method, result.InitialLevel, result.FinalLevel)
		}

		if !methodUsesRescale(result.Method) && result.FinalLevel > result.InitialLevel {
			t.Fatalf("case %d method %s final level exceeds initial level: initial=%d final=%d", i, result.Method, result.InitialLevel, result.FinalLevel)
		}

		if result.SelectedAbsError > 1e-2 {
			t.Fatalf(
				"case %d method %s selected error too large: z %.10f plain_z2 %.10f raw %.10f scaled %.10f selected %.10f mode=%s error %.10f",
				i,
				result.Method,
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

	for _, method := range DefaultMultiplicationProbeMethods() {
		if !seen[method] {
			t.Fatalf("expected method %s to be present", method)
		}
	}
}

func TestRunMultiplicationProbeCaseMulOnly(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	result, err := ctx.RunMultiplicationProbeCase(MultiplicationProbeCase{
		Z: 0.61,
	}, MultiplicationMulOnly)
	if err != nil {
		t.Fatalf("RunMultiplicationProbeCase failed: %v", err)
	}

	if result.OutputDegree != 2 {
		t.Fatalf("expected output degree 2 for mul_only, got %d", result.OutputDegree)
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
}

func TestRunMultiplicationProbeCaseMulRelinRescale(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	result, err := ctx.RunMultiplicationProbeCase(MultiplicationProbeCase{
		Z: 0.61,
	}, MultiplicationMulRelinRescale)
	if err != nil {
		t.Fatalf("RunMultiplicationProbeCase failed: %v", err)
	}

	if result.OutputDegree != 1 {
		t.Fatalf("expected output degree 1 for mul_relin_rescale, got %d", result.OutputDegree)
	}

	if result.FinalLevel >= result.InitialLevel {
		t.Fatalf("expected level consumption for mul_relin_rescale, initial=%d final=%d", result.InitialLevel, result.FinalLevel)
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
		"multiplication relin/rescale probe ok: z=%.10f plain_z2=%.10f raw=%.10f scaled=%.10f selected=%.10f mode=%s error=%.10f input_degree=%d output_degree=%d initial_level=%d final_level=%d",
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

func methodUsesRelinearization(method MultiplicationProbeMethod) bool {
	return method == MultiplicationMulRelin || method == MultiplicationMulRelinRescale
}

func methodUsesRescale(method MultiplicationProbeMethod) bool {
	return method == MultiplicationMulRescale || method == MultiplicationMulRelinRescale
}
