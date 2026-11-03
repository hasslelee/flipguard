package analysis

import (
	"math"
	"testing"
)

func TestAnalyzeDecisionNoFlip(t *testing.T) {
	r := AnalyzeDecision(
		0,
		0.70, // plain
		0.68, // approx
		0.50, // threshold
		0.05, // gamma
	)

	if r.PlainDecision != DecisionPositive {
		t.Fatalf("plain decision mismatch")
	}
	if r.ApproxDecision != DecisionPositive {
		t.Fatalf("approx decision mismatch")
	}
	if r.Flip {
		t.Fatalf("expected no flip")
	}
	if r.Boundary {
		t.Fatalf("expected non-boundary sample")
	}
	if math.Abs(r.Margin-0.20) > 1e-12 {
		t.Fatalf("margin mismatch: got %.12f", r.Margin)
	}
	if math.Abs(r.OutputError-0.02) > 1e-12 {
		t.Fatalf("output error mismatch: got %.12f", r.OutputError)
	}
}

func TestAnalyzeDecisionFlip(t *testing.T) {
	r := AnalyzeDecision(
		0,
		0.51, // plain
		0.49, // approx
		0.50, // threshold
		0.05, // gamma
	)

	if r.PlainDecision != DecisionPositive {
		t.Fatalf("plain decision mismatch")
	}
	if r.ApproxDecision != DecisionNegative {
		t.Fatalf("approx decision mismatch")
	}
	if !r.Flip {
		t.Fatalf("expected flip")
	}
	if !r.Boundary {
		t.Fatalf("expected boundary sample")
	}
}

func TestSummarizeDecisions(t *testing.T) {
	records := []DecisionRecord{
		AnalyzeDecision(0, 0.70, 0.69, 0.50, 0.05), // no flip, non-boundary
		AnalyzeDecision(1, 0.51, 0.49, 0.50, 0.05), // flip, boundary
		AnalyzeDecision(2, 0.48, 0.47, 0.50, 0.05), // no flip, boundary
		AnalyzeDecision(3, 0.20, 0.25, 0.50, 0.05), // no flip, non-boundary
	}

	stats := SummarizeDecisions(records)

	if stats.Count != 4 {
		t.Fatalf("count mismatch: got %d", stats.Count)
	}
	if stats.FlipCount != 1 {
		t.Fatalf("flip count mismatch: got %d", stats.FlipCount)
	}
	if math.Abs(stats.FlipRate-0.25) > 1e-12 {
		t.Fatalf("flip rate mismatch: got %.12f", stats.FlipRate)
	}
	if stats.BoundaryCount != 2 {
		t.Fatalf("boundary count mismatch: got %d", stats.BoundaryCount)
	}
	if stats.BoundaryFlipCount != 1 {
		t.Fatalf("boundary flip count mismatch: got %d", stats.BoundaryFlipCount)
	}
	if math.Abs(stats.BoundaryFlipRate-0.5) > 1e-12 {
		t.Fatalf("boundary flip rate mismatch: got %.12f", stats.BoundaryFlipRate)
	}
	if math.Abs(stats.MaxError-0.05) > 1e-12 {
		t.Fatalf("max error mismatch: got %.12f", stats.MaxError)
	}
}
