package benchmarks

import (
	"math"
	"testing"

	"github.com/hasslelee/flipguard/internal/runtime"
)

func TestNewLogRegSmallGraph(t *testing.T) {
	g := NewLogRegSmallGraph()

	if err := g.Validate(); err != nil {
		t.Fatalf("graph validation failed: %v", err)
	}

	if g.Len() == 0 {
		t.Fatalf("graph should not be empty")
	}

	if g.Output != "y" {
		t.Fatalf("unexpected output node: got %s, want y", g.Output)
	}
}

func TestLogRegSmallFirstSample(t *testing.T) {
	g := NewLogRegSmallGraph()
	samples := DefaultLogRegSmallSamples()

	result, err := runtime.EvalPlain(g, samples[0].Inputs())
	if err != nil {
		t.Fatalf("EvalPlain failed: %v", err)
	}

	// For sample {x1=1.0, x2=2.0, x3=0.5}:
	// z = 0.8 - 1.0 + 0.6 - 0.3 = 0.1
	// y = 0.5 + 0.197*0.1 - 0.004*(0.1^3) = 0.519696
	want := 0.519696

	if math.Abs(result.Output-want) > 1e-12 {
		t.Fatalf("unexpected output: got %.12f, want %.12f", result.Output, want)
	}

	direct := LogRegSmallScore(samples[0])
	if math.Abs(direct-want) > 1e-12 {
		t.Fatalf("direct score mismatch: got %.12f, want %.12f", direct, want)
	}
}

func TestGenerateLogRegSmallSamples(t *testing.T) {
	opts := LogRegSmallSampleGenOptions{
		RangeMin: -1.0,
		RangeMax: 1.0,
		Step:     0.1,

		Threshold: LogRegSmallThreshold,
		Gamma:     0.05,

		MaxBoundary:    10,
		MaxNonBoundary: 10,
	}

	samples := GenerateLogRegSmallSamples(opts)

	if len(samples) == 0 {
		t.Fatalf("expected generated samples")
	}

	boundaryCount := 0
	nonBoundaryCount := 0

	for _, s := range samples {
		margin := LogRegSmallMargin(s, opts.Threshold)
		if margin <= opts.Gamma {
			boundaryCount++
		} else {
			nonBoundaryCount++
		}
	}

	if boundaryCount == 0 {
		t.Fatalf("expected at least one boundary sample")
	}
	if nonBoundaryCount == 0 {
		t.Fatalf("expected at least one non-boundary sample")
	}
}
