package ckksbackend

import (
	"math"
	"testing"
)

func TestRunMLPSquareProbeCaseMatchesPlain(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	result, err := ctx.RunMLPSquareProbeCase(MLPSquareProbeCase{
		X1: 1.0,
		X2: -1.0,
		X3: 1.0,
		X4: -1.0,
	})
	if err != nil {
		t.Fatalf("RunMLPSquareProbeCase failed: %v", err)
	}

	if math.Abs(result.PlainScore-0.7180000000) > 1e-12 {
		t.Fatalf("unexpected plain MLP-square score: got %.12f want %.12f", result.PlainScore, 0.7180000000)
	}

	if result.AbsError > 1e-3 {
		t.Fatalf(
			"expected small CKKS MLP-square score error, got %.12f: plain_score=%.12f ckks_score=%.12f",
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

	if result.LogicalDegree != 2 {
		t.Fatalf("expected logical MLP-square degree 2, got %d", result.LogicalDegree)
	}

	if result.A1Degree != 1 {
		t.Fatalf("expected a1 ciphertext degree 1 after relinearization, got %d", result.A1Degree)
	}

	if result.A2Degree != 1 {
		t.Fatalf("expected a2 ciphertext degree 1 after relinearization, got %d", result.A2Degree)
	}

	if result.A3Degree != 1 {
		t.Fatalf("expected a3 ciphertext degree 1 after relinearization, got %d", result.A3Degree)
	}

	if result.U1Degree != 1 {
		t.Fatalf("expected u1 ciphertext degree 1 after relinearization, got %d", result.U1Degree)
	}

	if result.U2Degree != 1 {
		t.Fatalf("expected u2 ciphertext degree 1 after relinearization, got %d", result.U2Degree)
	}

	if result.ScoreDegree != 1 {
		t.Fatalf("expected score ciphertext degree 1 after relinearization, got %d", result.ScoreDegree)
	}

	if result.ScoreLevel > result.InitialLevel {
		t.Fatalf("score level exceeds initial level: initial=%d score=%d", result.InitialLevel, result.ScoreLevel)
	}
}

func TestRunMLPSquareProbeDefaultCases(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	results, err := ctx.RunMLPSquareProbe()
	if err != nil {
		t.Fatalf("RunMLPSquareProbe failed: %v", err)
	}

	if len(results) != len(DefaultMLPSquareProbeCases()) {
		t.Fatalf("unexpected result count: got %d want %d", len(results), len(DefaultMLPSquareProbeCases()))
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

		if result.LogicalDegree != 2 {
			t.Fatalf("case %d expected logical MLP-square degree 2, got %d", i, result.LogicalDegree)
		}

		if result.ScoreDegree != 1 {
			t.Fatalf("case %d expected score ciphertext degree 1 after relinearization, got %d", i, result.ScoreDegree)
		}

		if result.ScoreLevel > result.InitialLevel {
			t.Fatalf("case %d score level exceeds initial level: initial=%d score=%d", i, result.InitialLevel, result.ScoreLevel)
		}
	}

	if positiveCount == 0 {
		t.Fatalf("expected at least one threshold-positive MLP-square probe case")
	}

	if negativeCount == 0 {
		t.Fatalf("expected at least one threshold-negative MLP-square probe case")
	}

	if maxError > 1e-3 {
		t.Fatalf("expected max CKKS MLP-square score error <= 1e-3, got %.12f", maxError)
	}

	if flipCount != 0 {
		t.Fatalf("expected no decision flips in default non-exact-boundary cases, got %d", flipCount)
	}
}
