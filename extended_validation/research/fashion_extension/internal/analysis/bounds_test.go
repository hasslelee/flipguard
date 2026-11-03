package analysis

import (
	"testing"

	"github.com/hasslelee/flipguard/internal/benchmarks"
	"github.com/hasslelee/flipguard/internal/ir"
)

func TestAnalyzeBoundsAndSensitivityLogRegSmall(t *testing.T) {
	g := benchmarks.NewLogRegSmallGraph()

	opts := benchmarks.DefaultBoundaryFocusedOptions()
	opts.MaxBoundary = 20
	opts.MaxNonBoundary = 20

	samples := benchmarks.GenerateLogRegSmallSamples(opts)
	inputs := make([]map[ir.NodeID]float64, 0, len(samples))

	for _, sample := range samples {
		inputs = append(inputs, sample.Inputs())
	}

	result, err := AnalyzeBoundsAndSensitivity(
		g,
		inputs,
		opts.Threshold,
		0.05,
	)
	if err != nil {
		t.Fatalf("AnalyzeBoundsAndSensitivity failed: %v", err)
	}

	if len(result.Intervals) == 0 {
		t.Fatalf("expected intervals")
	}

	if len(result.Sensitivity) == 0 {
		t.Fatalf("expected sensitivity values")
	}

	if len(result.Margins) != len(samples) {
		t.Fatalf("margin count mismatch: got %d, want %d", len(result.Margins), len(samples))
	}

	if _, ok := result.Intervals[ir.NodeID("z")]; !ok {
		t.Fatalf("expected interval for z")
	}

	if result.Sensitivity[ir.NodeID("y")] != 1.0 {
		t.Fatalf("output sensitivity should be 1, got %.12f", result.Sensitivity[ir.NodeID("y")])
	}

	if result.Sensitivity[ir.NodeID("z")] <= 0 {
		t.Fatalf("expected positive sensitivity for z")
	}

	if result.Sensitivity[ir.NodeID("x1")] <= 0 {
		t.Fatalf("expected positive sensitivity for x1")
	}

	if result.ProtectedPercentile != 0.05 {
		t.Fatalf("protected percentile mismatch: got %.12f", result.ProtectedPercentile)
	}
}

func TestMaxAbsPolyDerivativeCubic(t *testing.T) {
	// f(x) = 0.5 + 0.197x - 0.004x^3
	// f'(x) = 0.197 - 0.012x^2
	coeffs := []float64{0.5, 0.197, 0.0, -0.004}

	got := maxAbsPolyDerivative(coeffs, Interval{
		Low:  -1,
		High: 1,
	})

	if got <= 0 {
		t.Fatalf("expected positive derivative bound")
	}

	if got < 0.185 || got > 0.198 {
		t.Fatalf("unexpected derivative bound: got %.12f", got)
	}
}
