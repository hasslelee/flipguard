package ckksbackend

import (
	"fmt"
	"math"

	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
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
//
// Flow:
//   - create CKKS parameters
//   - generate secret/public keys
//   - encode a real value into all slots
//   - encrypt the plaintext
//   - decrypt the ciphertext
//   - decode the result
//   - compare the first decoded slot with the input value
func RunRoundTripProbe() (RoundTripResult, error) {
	params, err := ckks.NewParametersFromLiteral(ckks.ExampleParameters128BitLogN14LogQP438)
	if err != nil {
		return RoundTripResult{}, fmt.Errorf("create CKKS parameters: %w", err)
	}

	encoder := ckks.NewEncoder(params)

	kgen := ckks.NewKeyGenerator(params)
	sk, pk := kgen.GenKeyPairNew()

	encryptor := ckks.NewEncryptor(params, pk)
	decryptor := ckks.NewDecryptor(params, sk)

	want := 1.2345

	values := make([]complex128, params.MaxSlots())
	for i := range values {
		values[i] = complex(want, 0)
	}

	pt := ckks.NewPlaintext(params, params.MaxLevel())

	if err := encoder.Encode(values, pt); err != nil {
		return RoundTripResult{}, fmt.Errorf("encode plaintext: %w", err)
	}

	ct, err := encryptor.EncryptNew(pt)
	if err != nil {
		return RoundTripResult{}, fmt.Errorf("encrypt plaintext: %w", err)
	}

	ptOut := decryptor.DecryptNew(ct)

	decoded := make([]complex128, params.MaxSlots())
	if err := encoder.Decode(ptOut, decoded); err != nil {
		return RoundTripResult{}, fmt.Errorf("decode plaintext: %w", err)
	}

	got := real(decoded[0])

	return RoundTripResult{
		Want: want,
		Got:  got,

		AbsError: math.Abs(got - want),

		MaxSlots:        params.MaxSlots(),
		MaxLevel:        params.MaxLevel(),
		LogDefaultScale: params.LogDefaultScale(),
	}, nil
}
