package ckksbackend

import (
	"math"
	"testing"
)

func TestRunHarrisCornerProbeCaseMatchesPlain(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	result, err := ctx.RunHarrisCornerProbeCase(newQuadrantHarrisCornerProbeCase(1.0))
	if err != nil {
		t.Fatalf("RunHarrisCornerProbeCase failed: %v", err)
	}

	if math.Abs(result.PlainScore-2015.36) > 1e-9 {
		t.Fatalf("unexpected plain Harris score: got %.12f want %.12f", result.PlainScore, 2015.36)
	}

	if result.AbsError > 1e-1 {
		t.Fatalf(
			"expected small CKKS Harris score error, got %.12f: plain_score=%.12f ckks_score=%.12f",
			result.AbsError,
			result.PlainScore,
			result.CKKSScore,
		)
	}

	if result.Flip {
		t.Fatalf(
			"unexpected decision flip: plain_score=%.12f ckks_score=%.12f threshold=%.12f",
			result.PlainScore,
			result.CKKSScore,
			result.Threshold,
		)
	}

	if result.LogicalDegree != 4 {
		t.Fatalf("expected logical Harris degree 4, got %d", result.LogicalDegree)
	}

	if result.SXXDegree != 1 {
		t.Fatalf("expected Sxx ciphertext degree 1 after relinearization, got %d", result.SXXDegree)
	}

	if result.SYYDegree != 1 {
		t.Fatalf("expected Syy ciphertext degree 1 after relinearization, got %d", result.SYYDegree)
	}

	if result.SXYDegree != 1 {
		t.Fatalf("expected Sxy ciphertext degree 1 after relinearization, got %d", result.SXYDegree)
	}

	if result.ScoreDegree != 1 {
		t.Fatalf("expected score ciphertext degree 1 after relinearization, got %d", result.ScoreDegree)
	}

	if result.ScoreLevel > result.InitialLevel {
		t.Fatalf("score level exceeds initial level: initial=%d score=%d", result.InitialLevel, result.ScoreLevel)
	}
}

func TestRunHarrisCornerProbeDefaultCases(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	results, err := ctx.RunHarrisCornerProbe()
	if err != nil {
		t.Fatalf("RunHarrisCornerProbe failed: %v", err)
	}

	if len(results) != len(DefaultHarrisCornerProbeCases()) {
		t.Fatalf("unexpected result count: got %d want %d", len(results), len(DefaultHarrisCornerProbeCases()))
	}

	maxError := 0.0
	flipCount := 0
	positiveCount := 0
	negativeCount := 0

	for i, result := range results {
		maxError = math.Max(maxError, result.AbsError)

		if result.Flip {
			flipCount++
		}

		if result.PlainDecision {
			positiveCount++
		} else {
			negativeCount++
		}

		if result.LogicalDegree != 4 {
			t.Fatalf("case %d expected logical Harris degree 4, got %d", i, result.LogicalDegree)
		}

		if result.ScoreDegree != 1 {
			t.Fatalf("case %d expected score ciphertext degree 1 after relinearization, got %d", i, result.ScoreDegree)
		}

		if result.ScoreLevel > result.InitialLevel {
			t.Fatalf("case %d score level exceeds initial level: initial=%d score=%d", i, result.InitialLevel, result.ScoreLevel)
		}
	}

	if positiveCount == 0 {
		t.Fatalf("expected at least one corner-positive Harris probe case")
	}

	if negativeCount == 0 {
		t.Fatalf("expected at least one corner-negative Harris probe case")
	}

	if maxError > 1e-1 {
		t.Fatalf("expected max CKKS Harris score error <= 1e-1, got %.12f", maxError)
	}

	if flipCount != 0 {
		t.Fatalf("expected no decision flips in default non-exact-boundary cases, got %d", flipCount)
	}
}

func newQuadrantHarrisCornerProbeCase(scale float64) HarrisCornerProbeCase {
	var probeCase HarrisCornerProbeCase

	for r := 0; r < 5; r++ {
		for c := 0; c < 5; c++ {
			if r >= 2 && c >= 2 {
				probeCase.Pixels[r][c] = scale
			}
		}
	}

	return probeCase
}
