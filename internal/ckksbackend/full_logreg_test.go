package ckksbackend

import "testing"

func TestRunFullLogRegProbe(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	results, err := ctx.RunFullLogRegProbe()
	if err != nil {
		t.Fatalf("RunFullLogRegProbe failed: %v", err)
	}

	if len(results) != len(DefaultFullLogRegProbeCases()) {
		t.Fatalf("expected %d full logreg results, got %d", len(DefaultFullLogRegProbeCases()), len(results))
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

		if result.ZError > 1e-2 {
			t.Fatalf(
				"case %d z error too large: plain_z %.10f ckks_z %.10f z_error %.10f",
				i,
				result.PlainZ,
				result.CKKSZ,
				result.ZError,
			)
		}

		if result.YError > 1e-2 {
			t.Fatalf(
				"case %d y error too large: plain_y %.10f ckks_y %.10f y_error %.10f",
				i,
				result.PlainY,
				result.CKKSY,
				result.YError,
			)
		}
	}
}

func TestRunFullLogRegProbeCase(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	result, err := ctx.RunFullLogRegProbeCase(FullLogRegProbeCase{
		Input: LogRegSmallInput{
			X1: 0.8,
			X2: -0.3,
			X3: 0.1,
		},
	})
	if err != nil {
		t.Fatalf("RunFullLogRegProbeCase failed: %v", err)
	}

	if result.DecisionFlip {
		t.Fatalf(
			"unexpected decision flip: plain_y %.10f ckks_y %.10f threshold %.10f",
			result.PlainY,
			result.CKKSY,
			result.Threshold,
		)
	}

	if result.YError > 1e-2 {
		t.Fatalf(
			"y error too large: plain_y %.10f ckks_y %.10f y_error %.10f",
			result.PlainY,
			result.CKKSY,
			result.YError,
		)
	}

	t.Logf(
		"full logreg probe ok: plain_z=%.10f ckks_z=%.10f z_error=%.10f plain_y=%.10f ckks_y=%.10f y_error=%.10f plain_decision=%t ckks_decision=%t flip=%t",
		result.PlainZ,
		result.CKKSZ,
		result.ZError,
		result.PlainY,
		result.CKKSY,
		result.YError,
		result.PlainDecision,
		result.CKKSDecision,
		result.DecisionFlip,
	)
}
