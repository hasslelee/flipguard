package ckksbackend

import (
	"fmt"
	"math"

	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// InputVectorRoundTripResult summarizes an encode-encrypt-decrypt-decode
// roundtrip for a packed input vector.
type InputVectorRoundTripResult struct {
	Want []float64
	Got  []float64

	MaxAbsError  float64
	MeanAbsError float64

	Slots           int
	UsedSlots       int
	MaxLevel        int
	LogDefaultScale int
}

// LogRegSmallInput contains the three real-valued inputs used by the current
// logreg_small benchmark.
type LogRegSmallInput struct {
	X1 float64
	X2 float64
	X3 float64
}

// Vector returns the packed slot values for logreg_small.
//
// Slot layout:
//
//	slot 0: x1
//	slot 1: x2
//	slot 2: x3
func (x LogRegSmallInput) Vector() []float64 {
	return []float64{x.X1, x.X2, x.X3}
}

// EncodeEncryptDecryptDecodeVector performs a CKKS roundtrip for a real-valued
// input vector.
//
// The input values are placed in the first len(values) slots. Remaining slots
// are filled with zero. The returned Got slice contains only the decoded values
// for the originally used slots.
func (c Context) EncodeEncryptDecryptDecodeVector(values []float64) (InputVectorRoundTripResult, error) {
	if len(values) == 0 {
		return InputVectorRoundTripResult{}, fmt.Errorf("input vector must not be empty")
	}

	if len(values) > c.Params.MaxSlots() {
		return InputVectorRoundTripResult{}, fmt.Errorf(
			"input vector has %d values but CKKS context only supports %d slots",
			len(values),
			c.Params.MaxSlots(),
		)
	}

	encoder := ckks.NewEncoder(c.Params)

	kgen := ckks.NewKeyGenerator(c.Params)
	sk, pk := kgen.GenKeyPairNew()

	encryptor := ckks.NewEncryptor(c.Params, pk)
	decryptor := ckks.NewDecryptor(c.Params, sk)

	slots := make([]complex128, c.Params.MaxSlots())
	for i, value := range values {
		slots[i] = complex(value, 0)
	}

	pt := ckks.NewPlaintext(c.Params, c.Params.MaxLevel())

	if err := encoder.Encode(slots, pt); err != nil {
		return InputVectorRoundTripResult{}, fmt.Errorf("encode input vector: %w", err)
	}

	ct, err := encryptor.EncryptNew(pt)
	if err != nil {
		return InputVectorRoundTripResult{}, fmt.Errorf("encrypt input vector: %w", err)
	}

	ptOut := decryptor.DecryptNew(ct)

	decodedSlots := make([]complex128, c.Params.MaxSlots())
	if err := encoder.Decode(ptOut, decodedSlots); err != nil {
		return InputVectorRoundTripResult{}, fmt.Errorf("decode input vector: %w", err)
	}

	got := make([]float64, len(values))
	for i := range values {
		got[i] = real(decodedSlots[i])
	}

	maxAbsError, meanAbsError := vectorError(values, got)

	return InputVectorRoundTripResult{
		Want: append([]float64(nil), values...),
		Got:  got,

		MaxAbsError:  maxAbsError,
		MeanAbsError: meanAbsError,

		Slots:           c.Params.MaxSlots(),
		UsedSlots:       len(values),
		MaxLevel:        c.Params.MaxLevel(),
		LogDefaultScale: c.Params.LogDefaultScale(),
	}, nil
}

// EncodeEncryptDecryptDecodeLogRegSmallInput performs a CKKS input roundtrip
// for the current logreg_small input layout.
func (c Context) EncodeEncryptDecryptDecodeLogRegSmallInput(input LogRegSmallInput) (InputVectorRoundTripResult, error) {
	return c.EncodeEncryptDecryptDecodeVector(input.Vector())
}

func vectorError(want []float64, got []float64) (float64, float64) {
	if len(want) == 0 || len(want) != len(got) {
		return 0, 0
	}

	maxAbsError := 0.0
	sumAbsError := 0.0

	for i := range want {
		err := math.Abs(got[i] - want[i])
		sumAbsError += err

		if err > maxAbsError {
			maxAbsError = err
		}
	}

	return maxAbsError, sumAbsError / float64(len(want))
}
