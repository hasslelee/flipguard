package benchmarks

import (
	"math"
	"testing"

	"github.com/hasslelee/flipguard/internal/runtime"
)

func TestSobelEdgeGraphMatchesPlainScore(t *testing.T) {
	graph := NewSobelEdgeGraph()

	for i, sample := range DefaultSobelEdgeSamples() {
		got, err := runtime.EvalPlain(graph, sample.Inputs())
		if err != nil {
			t.Fatalf("EvalPlain sample %d failed: %v", i, err)
		}

		want := SobelEdgeScore(sample)
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

func TestSobelEdgeKnownFlatPatch(t *testing.T) {
	sample := SobelEdgeSample{
		P00: 1.0, P01: 1.0, P02: 1.0,
		P10: 1.0, P11: 1.0, P12: 1.0,
		P20: 1.0, P21: 1.0, P22: 1.0,
	}

	response := SobelEdgeResponse(sample)
	score := SobelEdgeScore(sample)

	if response.GX != 0 {
		t.Fatalf("expected gx=0, got %.12f", response.GX)
	}

	if response.GY != 0 {
		t.Fatalf("expected gy=0, got %.12f", response.GY)
	}

	if score != 0 {
		t.Fatalf("expected score=0, got %.12f", score)
	}

	if SobelEdgeDecision(sample, SobelEdgeThreshold) {
		t.Fatal("flat patch should not be classified as an edge")
	}
}

func TestSobelEdgeKnownVerticalEdge(t *testing.T) {
	sample := SobelEdgeSample{
		P00: 0.0, P01: 0.0, P02: 1.0,
		P10: 0.0, P11: 0.0, P12: 1.0,
		P20: 0.0, P21: 0.0, P22: 1.0,
	}

	response := SobelEdgeResponse(sample)
	score := SobelEdgeScore(sample)

	if math.Abs(response.GX-4.0) > 1e-12 {
		t.Fatalf("expected gx=4, got %.12f", response.GX)
	}

	if math.Abs(response.GY) > 1e-12 {
		t.Fatalf("expected gy=0, got %.12f", response.GY)
	}

	if math.Abs(score-16.0) > 1e-12 {
		t.Fatalf("expected score=16, got %.12f", score)
	}

	if !SobelEdgeDecision(sample, SobelEdgeThreshold) {
		t.Fatal("canonical vertical edge should be classified as an edge")
	}
}

func TestSobelEdgeKnownHorizontalEdge(t *testing.T) {
	sample := SobelEdgeSample{
		P00: 0.0, P01: 0.0, P02: 0.0,
		P10: 0.0, P11: 0.0, P12: 0.0,
		P20: 1.0, P21: 1.0, P22: 1.0,
	}

	response := SobelEdgeResponse(sample)
	score := SobelEdgeScore(sample)

	if math.Abs(response.GX) > 1e-12 {
		t.Fatalf("expected gx=0, got %.12f", response.GX)
	}

	if math.Abs(response.GY-4.0) > 1e-12 {
		t.Fatalf("expected gy=4, got %.12f", response.GY)
	}

	if math.Abs(score-16.0) > 1e-12 {
		t.Fatalf("expected score=16, got %.12f", score)
	}

	if !SobelEdgeDecision(sample, SobelEdgeThreshold) {
		t.Fatal("canonical horizontal edge should be classified as an edge")
	}
}

func TestGenerateSobelEdgeSamplesReturnsBoundaryAndNonBoundary(t *testing.T) {
	opts := DefaultSobelEdgeSampleGenOptions()
	opts.MaxBoundary = 8
	opts.MaxNonBoundary = 8

	samples := GenerateSobelEdgeSamples(opts)
	if len(samples) == 0 {
		t.Fatal("expected generated samples")
	}

	boundaryCount := 0
	nonBoundaryCount := 0

	for _, sample := range samples {
		margin := SobelEdgeMargin(sample, opts.Threshold)
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

func TestSobelEdgeGeneratedSamplesMatchGraph(t *testing.T) {
	graph := NewSobelEdgeGraph()

	opts := DefaultSobelEdgeSampleGenOptions()
	opts.MaxBoundary = 4
	opts.MaxNonBoundary = 4

	samples := GenerateSobelEdgeSamples(opts)

	for i, sample := range samples {
		got, err := runtime.EvalPlain(graph, sample.Inputs())
		if err != nil {
			t.Fatalf("EvalPlain generated sample %d failed: %v", i, err)
		}

		want := SobelEdgeScore(sample)
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
