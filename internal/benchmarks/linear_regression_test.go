package benchmarks

import (
	"math"
	"testing"

	"github.com/hasslelee/flipguard/internal/runtime"
)

func TestLinearRegressionGraphMatchesPlainScore(t *testing.T) {
	graph := NewLinearRegressionGraph()

	for i, sample := range DefaultLinearRegressionSamples() {
		got, err := runtime.EvalPlain(graph, sample.Inputs())
		if err != nil {
			t.Fatalf("EvalPlain sample %d failed: %v", i, err)
		}

		want := LinearRegressionScore(sample)
		if math.Abs(got.Output-want) > 1e-12 {
			t.Fatalf(
				"sample %d output mismatch: got %.12f want %.12f",
				i,
				got.Output,
				want,
			)
		}
	}
}

func TestLinearRegressionBoundarySampleHasSmallMargin(t *testing.T) {
	sample := LinearRegressionSample{
		X1: 1.0 / 7.0,
		X2: 0.0,
		X3: 0.0,
		X4: 0.0,
	}

	margin := LinearRegressionMargin(sample, LinearRegressionThreshold)
	if margin > 1e-12 {
		t.Fatalf("expected near-zero margin, got %.12f", margin)
	}
}

func TestGenerateLinearRegressionSamplesReturnsBoundaryAndNonBoundary(t *testing.T) {
	opts := DefaultLinearRegressionSampleGenOptions()
	opts.MaxBoundary = 8
	opts.MaxNonBoundary = 8

	samples := GenerateLinearRegressionSamples(opts)
	if len(samples) == 0 {
		t.Fatal("expected generated samples")
	}

	boundaryCount := 0
	nonBoundaryCount := 0

	for _, sample := range samples {
		margin := LinearRegressionMargin(sample, opts.Threshold)
		if margin <= opts.Gamma {
			boundaryCount++
		} else {
			nonBoundaryCount++
		}
	}

	if boundaryCount == 0 {
		t.Fatal("expected at least one boundary sample")
	}

	if nonBoundaryCount == 0 {
		t.Fatal("expected at least one non-boundary sample")
	}

	if boundaryCount > opts.MaxBoundary {
		t.Fatalf("boundary count exceeds max: got %d max %d", boundaryCount, opts.MaxBoundary)
	}

	if nonBoundaryCount > opts.MaxNonBoundary {
		t.Fatalf("non-boundary count exceeds max: got %d max %d", nonBoundaryCount, opts.MaxNonBoundary)
	}
}

func TestLinearRegressionGeneratedSamplesMatchGraph(t *testing.T) {
	graph := NewLinearRegressionGraph()

	opts := DefaultLinearRegressionSampleGenOptions()
	opts.MaxBoundary = 4
	opts.MaxNonBoundary = 4

	samples := GenerateLinearRegressionSamples(opts)

	for i, sample := range samples {
		got, err := runtime.EvalPlain(graph, sample.Inputs())
		if err != nil {
			t.Fatalf("EvalPlain generated sample %d failed: %v", i, err)
		}

		want := LinearRegressionScore(sample)
		if math.Abs(got.Output-want) > 1e-12 {
			t.Fatalf(
				"generated sample %d output mismatch: got %.12f want %.12f",
				i,
				got.Output,
				want,
			)
		}
	}
}
