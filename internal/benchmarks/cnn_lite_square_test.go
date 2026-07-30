package benchmarks

import (
	"math"
	"testing"

	fgruntime "github.com/hasslelee/flipguard/internal/runtime"
)

func TestCNNLiteSquareGraphMatchesPlainScore(t *testing.T) {
	model := CNNLiteSquareModel{}
	for filter := 0; filter < CNNLiteFilters; filter++ {
		model.FilterBias[filter] = float64(filter-1) * 0.1
		for row := 0; row < CNNLiteFilterSide; row++ {
			for column := 0; column < CNNLiteFilterSide; column++ {
				model.FilterWeights[filter][row][column] =
					float64(1+filter+row-column) * 0.07
			}
		}
		for row := 0; row < CNNLiteConvSide; row++ {
			for column := 0; column < CNNLiteConvSide; column++ {
				model.OutputWeights[filter][row][column] =
					float64(1+filter+row+column) * 0.013
			}
		}
	}
	model.OutputBias = -0.08
	sample := CNNLiteSquareSample{}
	for row := 0; row < CNNLiteInputSide; row++ {
		for column := 0; column < CNNLiteInputSide; column++ {
			sample.Pixels[row][column] =
				float64(1+row*CNNLiteInputSide+column) / 17
		}
	}
	graph := NewCNNLiteSquareGraph(model)
	if err := graph.Validate(); err != nil {
		t.Fatalf("Validate failed: %v", err)
	}
	got, err := fgruntime.EvalPlain(graph, sample.Inputs())
	if err != nil {
		t.Fatalf("EvalPlain failed: %v", err)
	}
	want := CNNLiteSquareScore(sample, model)
	if math.Abs(got.Output-want) > 1e-12 {
		t.Fatalf(
			"CNN-lite output mismatch: got %.12g want %.12g",
			got.Output,
			want,
		)
	}
}

func TestCNNLiteSquareGraphSharesFilterWeights(t *testing.T) {
	model := CNNLiteSquareModel{}
	model.FilterWeights[0][0][0] = 0.75
	graph := NewCNNLiteSquareGraph(model)
	first, ok := graph.Node("f0_r0_c0_k00")
	if !ok {
		t.Fatal("first convolution term is missing")
	}
	last, ok := graph.Node("f0_r2_c2_k00")
	if !ok {
		t.Fatal("last convolution term is missing")
	}
	if first.Const != 0.75 || last.Const != 0.75 {
		t.Fatalf(
			"shared filter coefficient changed: first=%g last=%g",
			first.Const,
			last.Const,
		)
	}
}
