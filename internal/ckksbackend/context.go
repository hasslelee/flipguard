package ckksbackend

import (
	"fmt"

	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// Context contains reusable CKKS backend state.
type Context struct {
	Params  ckks.Parameters
	Profile CKKSProfile
}

// NewDefaultContext creates a CKKS backend context using the default FlipGuard profile.
func NewDefaultContext() (Context, error) {
	return NewContextFromProfileName("default")
}

// NewContextFromProfileName creates a CKKS backend context from a built-in profile name.
func NewContextFromProfileName(name string) (Context, error) {
	profile, err := FindCKKSProfile(name)
	if err != nil {
		return Context{}, err
	}

	return NewContextFromProfile(profile)
}

// NewContextFromProfile creates a CKKS backend context from a profile.
func NewContextFromProfile(profile CKKSProfile) (Context, error) {
	params, err := ckks.NewParametersFromLiteral(profile.Literal)
	if err != nil {
		return Context{}, fmt.Errorf("create CKKS parameters for profile %s: %w", profile.Name, err)
	}

	return Context{
		Params:  params,
		Profile: profile,
	}, nil
}

// ProfileName returns the CKKS profile name.
func (c Context) ProfileName() string {
	if c.Profile.Name == "" {
		return "default"
	}

	return c.Profile.Name
}

// ProfileDescription returns the CKKS profile description.
func (c Context) ProfileDescription() string {
	return c.Profile.Description
}

// LogQCount returns the number of Q primes in the selected profile.
func (c Context) LogQCount() int {
	return c.Profile.LogQCount()
}

// LogPCount returns the number of P primes in the selected profile.
func (c Context) LogPCount() int {
	return c.Profile.LogPCount()
}

// LogQPSum returns the total bit-size of Q and P primes in the selected profile literal.
func (c Context) LogQPSum() int {
	return c.Profile.LogQPSum()
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
