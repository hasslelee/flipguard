package benchmarks

import (
	"math"
	"testing"

	"github.com/hasslelee/flipguard/internal/ir"
)

func TestHarrisCornerFlatWindowHasZeroResponse(t *testing.T) {
	sample := HarrisCornerWindowSample{}

	response := HarrisCornerResponse(sample)

	if math.Abs(response.SXX) > 1e-12 {
		t.Fatalf("expected Sxx=0, got %.12f", response.SXX)
	}
	if math.Abs(response.SYY) > 1e-12 {
		t.Fatalf("expected Syy=0, got %.12f", response.SYY)
	}
	if math.Abs(response.SXY) > 1e-12 {
		t.Fatalf("expected Sxy=0, got %.12f", response.SXY)
	}
	if math.Abs(response.Score) > 1e-12 {
		t.Fatalf("expected Harris score=0, got %.12f", response.Score)
	}
	if HarrisCornerDecision(sample, HarrisCornerThreshold) {
		t.Fatalf("flat window should not be classified as a corner")
	}
}

func TestHarrisCornerDefaultSamplesContainCornerAndNonCornerCases(t *testing.T) {
	samples := DefaultHarrisCornerSamples()

	if len(samples) == 0 {
		t.Fatalf("expected non-empty default Harris samples")
	}

	positiveCorners := 0
	nonCorners := 0
	maxScore := math.Inf(-1)
	minScore := math.Inf(1)

	for _, sample := range samples {
		score := HarrisCornerScore(sample)
		maxScore = math.Max(maxScore, score)
		minScore = math.Min(minScore, score)

		if HarrisCornerDecision(sample, HarrisCornerThreshold) {
			positiveCorners++
		} else {
			nonCorners++
		}
	}

	if positiveCorners == 0 {
		t.Fatalf("expected at least one default sample above Harris threshold; max_score=%.12f", maxScore)
	}
	if nonCorners == 0 {
		t.Fatalf("expected at least one default sample below Harris threshold; min_score=%.12f", minScore)
	}
}

func TestHarrisCornerGraphAndInputsAreConstructible(t *testing.T) {
	graph := NewHarrisCornerResponseGraph()
	if graph == nil {
		t.Fatalf("expected non-nil Harris graph")
	}

	samples := GenerateHarrisCornerSamples(DefaultHarrisCornerSampleGenOptions())
	if len(samples) == 0 {
		t.Fatalf("expected generated Harris samples")
	}

	inputs := samples[0].Inputs()
	if len(inputs) != 25 {
		t.Fatalf("expected 25 Harris window inputs, got %d", len(inputs))
	}

	for _, id := range []ir.NodeID{"p00", "p04", "p22", "p40", "p44"} {
		if _, ok := inputs[id]; !ok {
			t.Fatalf("missing input %s", id)
		}
	}
}
