package ckksbackend

import (
	"fmt"
	"math"
)

// RoundTripResult summarizes a minimal CKKS encode-encrypt-decrypt-decode
// roundtrip.
//
// This is not a FlipGuard workload evaluation yet. It only verifies that the
// Lattigo CKKS backend can be instantiated and used from this repository.
type RoundTripResult struct {
	Want float64
	Got  float64

	AbsError float64

	MaxSlots        int
	MaxLevel        int
	LogDefaultScale int
}

// RunRoundTripProbe runs a minimal CKKS roundtrip with Lattigo.
func RunRoundTripProbe() (RoundTripResult, error) {
	ctx, err := NewDefaultContext()
	if err != nil {
		return RoundTripResult{}, fmt.Errorf("create CKKS context: %w", err)
	}

	want := 1.2345

	got, err := ctx.EncodeEncryptDecryptDecode(want)
	if err != nil {
		return RoundTripResult{}, fmt.Errorf("run CKKS encode-encrypt-decrypt-decode roundtrip: %w", err)
	}

	return RoundTripResult{
		Want: want,
		Got:  got,

		AbsError: math.Abs(got - want),

		MaxSlots:        ctx.MaxSlots(),
		MaxLevel:        ctx.MaxLevel(),
		LogDefaultScale: ctx.LogDefaultScale(),
	}, nil
}
