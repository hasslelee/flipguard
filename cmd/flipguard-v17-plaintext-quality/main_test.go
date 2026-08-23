package main

import (
	"math"
	"testing"
)

func TestQuantileInterpolates(t *testing.T) {
	values := []float64{0, 10, 20, 30, 40}
	if got := quantile(values, 0.25); got != 10 {
		t.Fatalf("p25=%v, want 10", got)
	}
	if got := quantile(values, 0.9); math.Abs(got-36) > 1e-12 {
		t.Fatalf("p90=%v, want 36", got)
	}
}

func TestTopTwoUsesLowestIndexTieBreak(t *testing.T) {
	values := [10]float64{1, 1, 0, 0, 0, 0, 0, 0, 0, 0}
	top, runner := topTwo(values)
	if top != 0 || runner != 1 {
		t.Fatalf("top=%d runner=%d, want 0,1", top, runner)
	}
}
