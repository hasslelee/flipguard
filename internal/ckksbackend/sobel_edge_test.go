package ckksbackend

import (
	"math"
	"testing"
)

func TestRunSobelEdgeProbeCaseMatchesPlain(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	result, err := ctx.RunSobelEdgeProbeCase(SobelEdgeProbeCase{
		P00: 0.0, P01: 0.0, P02: 1.05,
		P10: 0.0, P11: 0.0, P12: 1.05,
		P20: 0.0, P21: 0.0, P22: 1.05,
	})
	if err != nil {
		t.Fatalf("RunSobelEdgeProbeCase failed: %v", err)
	}

	if math.Abs(result.PlainGX-4.2) > 1e-12 {
		t.Fatalf("expected plain gx=4.2, got %.12f", result.PlainGX)
	}

	if math.Abs(result.PlainGY) > 1e-12 {
		t.Fatalf("expected plain gy=0, got %.12f", result.PlainGY)
	}

	if result.AbsError > 1e-5 {
		t.Fatalf("expected small CKKS score error, got %.12f", result.AbsError)
	}

	if result.Flip {
		t.Fatalf(
			"unexpected decision flip: plain_score=%.12f ckks_score=%.12f",
			result.PlainScore,
			result.CKKSScore,
		)
	}

	if result.GXDegree != 1 {
		t.Fatalf("expected gx degree 1, got %d", result.GXDegree)
	}

	if result.GYDegree != 1 {
		t.Fatalf("expected gy degree 1, got %d", result.GYDegree)
	}

	if result.ScoreDegree != 2 {
		t.Fatalf("expected score degree 2, got %d", result.ScoreDegree)
	}
}

func TestRunSobelEdgeProbeDefaultCases(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	results, err := ctx.RunSobelEdgeProbe()
	if err != nil {
		t.Fatalf("RunSobelEdgeProbe failed: %v", err)
	}

	if len(results) != len(DefaultSobelEdgeProbeCases()) {
		t.Fatalf("unexpected result count: got %d want %d", len(results), len(DefaultSobelEdgeProbeCases()))
	}

	maxError := 0.0
	flipCount := 0

	for _, result := range results {
		maxError = math.Max(maxError, result.AbsError)

		if result.Flip {
			flipCount++
		}

		if result.GXDegree != 1 {
			t.Fatalf("expected gx degree 1, got %d", result.GXDegree)
		}

		if result.GYDegree != 1 {
			t.Fatalf("expected gy degree 1, got %d", result.GYDegree)
		}

		if result.ScoreDegree != 2 {
			t.Fatalf("expected score degree 2, got %d", result.ScoreDegree)
		}
	}

	if maxError > 1e-5 {
		t.Fatalf("expected max CKKS score error <= 1e-5, got %.12f", maxError)
	}

	if flipCount != 0 {
		t.Fatalf("expected no decision flips in default non-exact-boundary cases, got %d", flipCount)
	}
}
