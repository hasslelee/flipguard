package benchmarks

import (
	"math"
	"testing"

	"github.com/hasslelee/flipguard/internal/runtime"
)

func TestMLPSquareGraphMatchesPlainScore(t *testing.T) {
	graph := NewMLPSquareGraph()

	sample := MLPSquareSample{
		X1: 1.0,
		X2: -1.0,
		X3: 1.0,
		X4: -1.0,
	}

	result, err := runtime.EvalPlain(graph, sample.Inputs())
	if err != nil {
		t.Fatalf("EvalPlain failed: %v", err)
	}

	want := MLPSquareScore(sample)
	if math.Abs(result.Output-want) > 1e-12 {
		t.Fatalf("MLP-square output mismatch: got %.12f want %.12f", result.Output, want)
	}
}

func TestMLPSquareDefaultSamplesContainBothClasses(t *testing.T) {
	samples := DefaultMLPSquareSamples()

	positive := 0
	negative := 0

	for _, sample := range samples {
		if MLPSquareDecision(sample, MLPSquareThreshold) {
			positive++
		} else {
			negative++
		}
	}

	if positive == 0 {
		t.Fatalf("expected at least one positive MLP-square sample")
	}
	if negative == 0 {
		t.Fatalf("expected at least one negative MLP-square sample")
	}
}

func TestGenerateMLPSquareSamples(t *testing.T) {
	opts := DefaultMLPSquareSampleGenOptions()
	opts.MaxBoundary = 16
	opts.MaxNonBoundary = 16

	samples := GenerateMLPSquareSamples(opts)

	if len(samples) != 32 {
		t.Fatalf("unexpected generated sample count: got %d want %d", len(samples), 32)
	}

	positive := 0
	negative := 0
	minMargin := math.Inf(1)

	for _, sample := range samples {
		margin := MLPSquareMargin(sample, opts.Threshold)
		minMargin = math.Min(minMargin, margin)

		if MLPSquareDecision(sample, opts.Threshold) {
			positive++
		} else {
			negative++
		}
	}

	if positive == 0 {
		t.Fatalf("expected generated samples to contain positive decisions")
	}
	if negative == 0 {
		t.Fatalf("expected generated samples to contain negative decisions")
	}
	if math.IsInf(minMargin, 0) || math.IsNaN(minMargin) {
		t.Fatalf("expected finite margin")
	}
}
