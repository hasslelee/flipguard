package ckksbackend

import "testing"

func TestEvalLogRegSmallPolynomialPlain(t *testing.T) {
	z := 0.61
	got := EvalLogRegSmallPolynomialPlain(z)
	want := 0.5 + 0.197*z - 0.004*z*z*z

	if got != want {
		t.Fatalf("unexpected polynomial value: got %.10f want %.10f", got, want)
	}
}

func TestRunPolynomialProbe(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	results, err := ctx.RunPolynomialProbe()
	if err != nil {
		t.Fatalf("RunPolynomialProbe failed: %v", err)
	}

	if len(results) != len(DefaultPolynomialProbeCases()) {
		t.Fatalf("expected %d polynomial probe results, got %d", len(DefaultPolynomialProbeCases()), len(results))
	}

	for i, result := range results {
		if result.ZDegree != 1 {
			t.Fatalf("case %d expected z degree 1, got %d", i, result.ZDegree)
		}

		if result.Z2Degree != 1 {
			t.Fatalf("case %d expected z2 degree 1, got %d", i, result.Z2Degree)
		}

		if result.Z3Degree != 1 {
			t.Fatalf("case %d expected z3 degree 1, got %d", i, result.Z3Degree)
		}

		if result.YDegree != 1 {
			t.Fatalf("case %d expected y degree 1, got %d", i, result.YDegree)
		}

		if result.AbsError > 1e-2 {
			t.Fatalf(
				"case %d polynomial error too large: z %.10f plain_y %.10f ckks_y %.10f abs_error %.10f",
				i,
				result.Z,
				result.PlainY,
				result.CKKSY,
				result.AbsError,
			)
		}
	}
}

func TestRunPolynomialProbeCase(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	result, err := ctx.RunPolynomialProbeCase(PolynomialProbeCase{
		Z: 0.61,
	})
	if err != nil {
		t.Fatalf("RunPolynomialProbeCase failed: %v", err)
	}

	if result.AbsError > 1e-2 {
		t.Fatalf(
			"polynomial error too large: z %.10f plain_y %.10f ckks_y %.10f abs_error %.10f",
			result.Z,
			result.PlainY,
			result.CKKSY,
			result.AbsError,
		)
	}

	t.Logf(
		"polynomial probe ok: z=%.10f plain_y=%.10f ckks_y=%.10f abs_error=%.10f z3=%.10f z_degree=%d z2_degree=%d z3_degree=%d y_degree=%d initial_level=%d z2_level=%d z3_level=%d y_level=%d",
		result.Z,
		result.PlainY,
		result.CKKSY,
		result.AbsError,
		result.Z3Value,
		result.ZDegree,
		result.Z2Degree,
		result.Z3Degree,
		result.YDegree,
		result.InitialLevel,
		result.Z2Level,
		result.Z3Level,
		result.YLevel,
	)
}
