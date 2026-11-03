package main

import (
	"math"
	"testing"
)

func TestDiagnosticOccupancyDoesNotReduceLinearCiphertextWork(t *testing.T) {
	layers := []Layer{{Weights: [][]float64{{.25, -.5}}, Bias: []float64{.1}}}
	var previous DiagnosticResult
	for _, inputs := range [][][]float64{{{1, 2}}, {{1, 2}, {-1, .5}, {0, 0}}} {
		got, err := runDiagnostic(DiagnosticRequest{Request: Request{Layers: layers, Inputs: inputs, Scale: 30, Repeats: 1}})
		if err != nil {
			t.Fatal(err)
		}
		for i, x := range inputs {
			if math.Abs(got.ClientLogits[i][0]-(.25*x[0]-.5*x[1]+.1)) > 1e-4 {
				t.Fatal("incorrect affine result")
			}
		}
		for k, want := range map[string]int{"input_ciphertexts": 2, "output_ciphertexts": 1, "ct_pt_multiply": 2, "ct_add": 1, "rescale": 1, "bias_add": 1, "weight_plaintext_encodes": 2, "server_evaluations_started": 1} {
			if got.Cost.Counts[k] != want {
				t.Fatalf("%s got %d want %d", k, got.Cost.Counts[k], want)
			}
		}
		total := 0.0
		for _, v := range got.Cost.Milliseconds {
			if v < 0 {
				t.Fatal("negative duration")
			}
			total += v
		}
		if total > got.NativeTotalMS {
			t.Fatal("timing intervals overlap")
		}
		if previous.ParameterID != "" && (previous.ParameterID != got.ParameterID || previous.KeyContextID == got.KeyContextID) {
			t.Fatal("parameter/key identity invalid")
		}
		previous = got
	}
}
