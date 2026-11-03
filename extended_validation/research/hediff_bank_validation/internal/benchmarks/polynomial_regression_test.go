package benchmarks

import (
	"math"
	"testing"

	"github.com/hasslelee/flipguard/internal/runtime"
)

func TestPolynomialRegressionGraphMatchesPlainEvaluator(t *testing.T) {
	g := NewPolynomialRegressionGraph()

	for _, sample := range DefaultPolynomialRegressionSamples() {
		got, err := runtime.EvalPlain(g, sample.Inputs())
		if err != nil {
			t.Fatalf("EvalPlain failed for x=%f: %v", sample.X, err)
		}

		want := PolynomialRegressionScore(sample)

		if math.Abs(got.Output-want) > 1e-12 {
			t.Fatalf(
				"graph output mismatch for x=%f: got %.15f want %.15f diff %.15f",
				sample.X,
				got.Output,
				want,
				math.Abs(got.Output-want),
			)
		}
	}
}

func TestPolynomialRegressionGraphExposesProgramPoints(t *testing.T) {
	g := NewPolynomialRegressionGraph()

	required := []string{
		"x",
		"x2",
		"x3",
		"x4",
		"x5",
		"t1",
		"t2",
		"t3",
		"t4",
		"t5",
		"y",
	}

	nodes := map[string]bool{}
	for _, node := range g.Nodes() {
		nodes[string(node.ID)] = true
	}

	for _, id := range required {
		if !nodes[id] {
			t.Fatalf("expected node %s in polynomial regression graph", id)
		}
	}
}

func TestGeneratePolynomialRegressionSamples(t *testing.T) {
	samples := GeneratePolynomialRegressionSamples(DefaultPolynomialRegressionBoundaryOptions())
	if len(samples) == 0 {
		t.Fatal("expected generated samples")
	}

	boundaryCount := 0
	nonBoundaryCount := 0

	opts := DefaultPolynomialRegressionBoundaryOptions()

	for _, sample := range samples {
		margin := PolynomialRegressionMargin(sample, opts.Threshold)
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
}
