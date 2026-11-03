package main

import (
	"math"
	"testing"
)

func TestEncryptedAffineSquareMatchesHandComputed(t *testing.T) {
	r := Request{Inputs: [][]float64{{1, 2}, {-1, .5}, {0, 0}}, Scale: 30, Repeats: 2,
		Layers: []Layer{{Weights: [][]float64{{.25, -.5}, {.7, .2}}, Bias: []float64{.1, -.3}, Square: true}, {Weights: [][]float64{{.6, -.4}}, Bias: []float64{.2}}}}
	got, err := run(r)
	if err != nil {
		t.Fatal(err)
	}
	for _, m := range got.Measurements {
		for i, x := range r.Inputs {
			a := .25*x[0] - .5*x[1] + .1
			b := .7*x[0] + .2*x[1] - .3
			want := .6*a*a - .4*b*b + .2
			if math.Abs(m.Logits[i][0]-want) > 1e-4 {
				t.Fatalf("row %d got %.8g want %.8g", i, m.Logits[i][0], want)
			}
		}
	}
}

func TestRejectMalformedRequest(t *testing.T) {
	if _, err := run(Request{Inputs: [][]float64{{math.NaN()}}, Scale: 30, Repeats: 1}); err == nil {
		t.Fatal("accepted malformed request")
	}
}
