package benchmarks

import (
	"math"
	"testing"

	fgruntime "github.com/hasslelee/flipguard/internal/runtime"
)

func TestHarrisCornerRescaleGraphMatchesPlainScore(t *testing.T) {
	graph := NewHarrisCornerRescaleGraph()
	if err := graph.Validate(); err != nil {
		t.Fatalf("Validate failed: %v", err)
	}
	for index, sample := range DefaultHarrisCornerSamples() {
		got, err := fgruntime.EvalPlain(graph, sample.Inputs())
		if err != nil {
			t.Fatalf("EvalPlain sample %d failed: %v", index, err)
		}
		want := HarrisCornerScore(sample)
		if math.Abs(got.Output-want) > 1e-10*math.Max(1, math.Abs(want)) {
			t.Fatalf(
				"sample %d output mismatch: got %.12g want %.12g",
				index,
				got.Output,
				want,
			)
		}
	}
}
