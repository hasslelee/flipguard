package ckksbackend

import (
	"math"
	"testing"
)

func TestRunLinearRegressionProbeCaseMatchesPlain(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	result, err := ctx.RunLinearRegressionProbeCase(LinearRegressionProbeCase{
		X1: 0.5,
		X2: -0.5,
		X3: 0.25,
		X4: 0.75,
	})
	if err != nil {
		t.Fatalf("RunLinearRegressionProbeCase failed: %v", err)
	}

	if result.AbsError > 1e-6 {
		t.Fatalf("expected small CKKS error, got %.12f", result.AbsError)
	}

	if result.Flip {
		t.Fatalf(
			"unexpected decision flip: plain_y=%.12f ckks_y=%.12f",
			result.PlainY,
			result.CKKSY,
		)
	}

	if result.YDegree != 1 {
		t.Fatalf("expected affine output degree 1, got %d", result.YDegree)
	}

	if result.YLevel != result.InitialLevel {
		t.Fatalf("expected affine evaluation to preserve level: initial=%d y=%d", result.InitialLevel, result.YLevel)
	}
}

func TestRunLinearRegressionProbeDefaultCases(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	results, err := ctx.RunLinearRegressionProbe()
	if err != nil {
		t.Fatalf("RunLinearRegressionProbe failed: %v", err)
	}

	if len(results) != len(DefaultLinearRegressionProbeCases()) {
		t.Fatalf("unexpected result count: got %d want %d", len(results), len(DefaultLinearRegressionProbeCases()))
	}

	maxError := 0.0
	flipCount := 0

	for _, result := range results {
		maxError = math.Max(maxError, result.AbsError)

		if result.Flip {
			flipCount++
		}

		if result.YDegree != 1 {
			t.Fatalf("expected affine output degree 1, got %d", result.YDegree)
		}
	}

	if maxError > 1e-6 {
		t.Fatalf("expected max CKKS error <= 1e-6, got %.12f", maxError)
	}

	if flipCount != 0 {
		t.Fatalf("expected no decision flips in default non-exact-boundary cases, got %d", flipCount)
	}
}
