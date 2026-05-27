package ckksbackend

import (
	"fmt"

	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// Context contains reusable CKKS backend state.
//
// At this stage, Context owns CKKS parameters and exposes small helper methods.
// The encrypted logreg_small evaluator will later build on top of this type.
type Context struct {
	Params ckks.Parameters
}

// NewDefaultContext creates a CKKS backend context using the current default
// Lattigo parameter literal selected for FlipGuard experiments.
func NewDefaultContext() (Context, error) {
	params, err := ckks.NewParametersFromLiteral(ckks.ExampleParameters128BitLogN14LogQP438)
	if err != nil {
		return Context{}, fmt.Errorf("create CKKS parameters: %w", err)
	}

	return Context{
		Params: params,
	}, nil
}

// MaxSlots returns the maximum number of CKKS slots supported by the context.
func (c Context) MaxSlots() int {
	return c.Params.MaxSlots()
}

// MaxLevel returns the maximum available CKKS level.
func (c Context) MaxLevel() int {
	return c.Params.MaxLevel()
}

// LogDefaultScale returns log2 of the default CKKS scale.
func (c Context) LogDefaultScale() int {
	return c.Params.LogDefaultScale()
}

// EncodeEncryptDecryptDecode performs a minimal CKKS roundtrip for one real value.
//
// The value is replicated across all available slots. The first decoded slot is
// returned as the representative result.
func (c Context) EncodeEncryptDecryptDecode(value float64) (float64, error) {
	encoder := ckks.NewEncoder(c.Params)

	kgen := ckks.NewKeyGenerator(c.Params)
	sk, pk := kgen.GenKeyPairNew()

	encryptor := ckks.NewEncryptor(c.Params, pk)
	decryptor := ckks.NewDecryptor(c.Params, sk)

	values := make([]complex128, c.Params.MaxSlots())
	for i := range values {
		values[i] = complex(value, 0)
	}

	pt := ckks.NewPlaintext(c.Params, c.Params.MaxLevel())

	if err := encoder.Encode(values, pt); err != nil {
		return 0, fmt.Errorf("encode plaintext: %w", err)
	}

	ct, err := encryptor.EncryptNew(pt)
	if err != nil {
		return 0, fmt.Errorf("encrypt plaintext: %w", err)
	}

	ptOut := decryptor.DecryptNew(ct)

	decoded := make([]complex128, c.Params.MaxSlots())
	if err := encoder.Decode(ptOut, decoded); err != nil {
		return 0, fmt.Errorf("decode plaintext: %w", err)
	}

	return real(decoded[0]), nil
}
