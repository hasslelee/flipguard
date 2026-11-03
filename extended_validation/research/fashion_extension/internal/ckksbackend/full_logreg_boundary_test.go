package ckksbackend

import (
	"math"
	"testing"
)

func TestRunFullLogRegBoundaryProbe(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	results, err := ctx.RunFullLogRegBoundaryProbe()
	if err != nil {
		t.Fatalf("RunFullLogRegBoundaryProbe failed: %v", err)
	}

	if len(results) != len(DefaultFullLogRegBoundaryCases()) {
		t.Fatalf("expected %d boundary results, got %d", len(DefaultFullLogRegBoundaryCases()), len(results))
	}

	stableCount := 0
	ambiguousCount := 0
	flipCount := 0

	for i, result := range results {
		if result.TargetError > 1e-9 {
			t.Fatalf(
				"case %d target z mismatch: target %.10f plain_z %.10f error %.10f",
				i,
				result.Case.TargetZ,
				result.Result.PlainZ,
				result.TargetError,
			)
		}

		if !result.Boundary {
			t.Fatalf("case %d expected boundary sample", i)
		}

		if result.Stable {
			stableCount++
		}

		if result.Ambiguous {
			ambiguousCount++
		}

		if result.Result.DecisionFlip {
			flipCount++
		}

		if result.Result.YError > 1e-2 {
			t.Fatalf(
				"case %d y error too large: target_z %.10f plain_y %.10f ckks_y %.10f y_error %.10f",
				i,
				result.Case.TargetZ,
				result.Result.PlainY,
				result.Result.CKKSY,
				result.Result.YError,
			)
		}

		if result.Stable && result.Result.DecisionFlip {
			t.Fatalf(
				"case %d stable boundary decision flip: target_z %.10f margin %.10f plain_y %.10f ckks_y %.10f",
				i,
				result.Case.TargetZ,
				result.Margin,
				result.Result.PlainY,
				result.Result.CKKSY,
			)
		}
	}

	if stableCount == 0 {
		t.Fatalf("expected at least one stable boundary sample")
	}

	if ambiguousCount == 0 {
		t.Fatalf("expected at least one ambiguous boundary sample")
	}

	if flipCount != 0 {
		t.Fatalf("expected zero CKKS decision flips, got %d", flipCount)
	}
}

func TestInputForTargetZ(t *testing.T) {
	targetZ := 0.01
	input := inputForTargetZ(targetZ)

	got := EvalLogRegSmallLinearPlain(input)
	if math.Abs(got-targetZ) > 1e-12 {
		t.Fatalf("unexpected target z reconstruction: got %.16f want %.16f", got, targetZ)
	}
}
