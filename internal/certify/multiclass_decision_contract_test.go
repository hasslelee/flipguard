package certify

import (
	"math"
	"testing"
)

func TestMulticlassArgmaxProposition(t *testing.T) {
	certificate, err := CertifyMulticlassArgmaxBounds(
		[]float64{0.1, 0.9, 0.4},
		[]float64{0.03, 0.04, 0.02},
	)
	if err != nil {
		t.Fatal(err)
	}
	if !certificate.StrictlyProved || certificate.PlainClass != 1 ||
		certificate.RunnerUp != 2 || certificate.TopTwoGap != 0.5 {
		t.Fatalf("unexpected certificate: %+v", certificate)
	}
}

func TestMulticlassArgmaxRejectsEqualityBoundary(t *testing.T) {
	certificate, err := CertifyMulticlassArgmaxBounds(
		[]float64{1.0, 0.5},
		[]float64{0.2, 0.3},
	)
	if err != nil {
		t.Fatal(err)
	}
	if certificate.StrictlyProved || certificate.MinimumGapSlack != 0 {
		t.Fatalf("equality boundary must not prove preservation: %+v", certificate)
	}
}

func TestMulticlassUniformBoundCorollary(t *testing.T) {
	certificate, err := CertifyMulticlassUniformBound(
		[]float64{0.2, 0.8, 0.4},
		0.19,
	)
	if err != nil {
		t.Fatal(err)
	}
	if !certificate.StrictlyProved {
		t.Fatalf("2B < gap should pass: %+v", certificate)
	}
	certificate, err = CertifyMulticlassUniformBound(
		[]float64{0.2, 0.8, 0.4},
		0.2,
	)
	if err != nil {
		t.Fatal(err)
	}
	if certificate.StrictlyProved {
		t.Fatal("2B == gap must fail the strict corollary")
	}
}

func TestMulticlassTieIsAmbiguousWithLowestIndexRule(t *testing.T) {
	certificate, err := CertifyMulticlassArgmaxBounds(
		[]float64{0.9, 0.9, 0.1},
		[]float64{0, 0, 0},
	)
	if err != nil {
		t.Fatal(err)
	}
	if certificate.PlainClass != 0 || !certificate.PlainTie ||
		certificate.StrictlyProved {
		t.Fatalf("unexpected tie handling: %+v", certificate)
	}
}

func TestMulticlassRejectsNonFiniteLogitsAndBounds(t *testing.T) {
	if _, err := CertifyMulticlassArgmaxBounds(
		[]float64{0, math.NaN()},
		[]float64{0, 0},
	); err == nil {
		t.Fatal("expected NaN plaintext rejection")
	}
	if _, err := CertifyMulticlassArgmaxBounds(
		[]float64{0, 1},
		[]float64{0, math.Inf(1)},
	); err == nil {
		t.Fatal("expected infinite bound rejection")
	}
}

func TestAggregateObservedMulticlassCandidate(t *testing.T) {
	aggregation, err := AggregateObservedMulticlassCandidate(
		[]MulticlassObservedSample{
			{
				ID:          "safe",
				PlainLogits: []float64{0.1, 1.0, 0.2},
				ApproxLogits: [][]float64{
					{0.11, 0.97, 0.22},
					{0.09, 0.98, 0.21},
				},
			},
			{
				ID:          "ambiguous_tie",
				PlainLogits: []float64{0.5, 0.5, 0.1},
				ApproxLogits: [][]float64{
					{0.49, 0.51, 0.1},
					{0.51, 0.49, 0.1},
				},
			},
		},
		0,
		0.001,
		0.5,
	)
	if err != nil {
		t.Fatal(err)
	}
	if aggregation.Status != StatusSafe || aggregation.VCert != 1 ||
		aggregation.VAmb != 1 || aggregation.TotalObservations != 4 ||
		aggregation.CertifiedObservations != 2 {
		t.Fatalf("unexpected aggregation: %+v", aggregation)
	}
}

func TestAggregateMulticlassPolicyRejectWithoutFlip(t *testing.T) {
	aggregation, err := AggregateObservedMulticlassCandidate(
		[]MulticlassObservedSample{
			{
				ID:          "near_budget",
				PlainLogits: []float64{1.0, 0.8, 0.0},
				ApproxLogits: [][]float64{
					{0.94, 0.85, 0.0},
				},
			},
		},
		0,
		0.001,
		0.5,
	)
	if err != nil {
		t.Fatal(err)
	}
	if aggregation.Status != StatusRejected || aggregation.ArgmaxFlips != 0 ||
		aggregation.ReserveViolations != 1 {
		t.Fatalf("expected reserve rejection without flip: %+v", aggregation)
	}
}

func TestAggregateMulticlassDetectsArgmaxFlip(t *testing.T) {
	aggregation, err := AggregateObservedMulticlassCandidate(
		[]MulticlassObservedSample{
			{
				ID:          "flip",
				PlainLogits: []float64{1.0, 0.8},
				ApproxLogits: [][]float64{
					{0.7, 0.9},
				},
			},
		},
		0,
		0.001,
		0.5,
	)
	if err != nil {
		t.Fatal(err)
	}
	if aggregation.Status != StatusRejected || aggregation.ArgmaxFlips != 1 {
		t.Fatalf("expected argmax flip rejection: %+v", aggregation)
	}
}

func TestAggregateMulticlassRejectsRunShapeMismatch(t *testing.T) {
	_, err := AggregateObservedMulticlassCandidate(
		[]MulticlassObservedSample{
			{
				ID:           "a",
				PlainLogits:  []float64{1, 0},
				ApproxLogits: [][]float64{{1, 0}, {1, 0}},
			},
			{
				ID:           "b",
				PlainLogits:  []float64{1, 0},
				ApproxLogits: [][]float64{{1, 0}},
			},
		},
		0,
		0.001,
		0.5,
	)
	if err == nil {
		t.Fatal("expected key-run shape mismatch")
	}
}
