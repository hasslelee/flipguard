package ckksbackend

import (
	"fmt"

	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// ConstantEncodingMode selects the scale used to encode a plaintext constant
// that is added to a ciphertext.
type ConstantEncodingMode string

const (
	// ConstantEncodingDefaultScale encodes the constant at the parameter
	// default scale. This is the as-run behavior of every frozen evaluation.
	ConstantEncodingDefaultScale ConstantEncodingMode = ""

	// ConstantEncodingCiphertextScale encodes the constant at the exact scale
	// of the ciphertext it is added to. The ciphertext scale after RescaleTo
	// differs from the default scale by the product of prime-to-scale ratios,
	// and ckks.Evaluator.Add does not correct a non-integer scale ratio.
	ConstantEncodingCiphertextScale ConstantEncodingMode = "ciphertext_scale"
)

// ParseConstantEncodingMode validates a command-line constant-encoding mode.
func ParseConstantEncodingMode(value string) (ConstantEncodingMode, error) {
	switch ConstantEncodingMode(value) {
	case ConstantEncodingDefaultScale, "default_scale":
		return ConstantEncodingDefaultScale, nil
	case ConstantEncodingCiphertextScale:
		return ConstantEncodingCiphertextScale, nil
	default:
		return "", fmt.Errorf("unsupported constant encoding mode %q", value)
	}
}

// encodeReplicatedPlaintextForCiphertext encodes value for addition to target
// according to the context constant-encoding mode.
func (c Context) encodeReplicatedPlaintextForCiphertext(
	encoder *ckks.Encoder,
	value float64,
	target *rlwe.Ciphertext,
) (*rlwe.Plaintext, error) {
	if c.ConstantEncoding != ConstantEncodingCiphertextScale {
		return c.encodeReplicatedPlaintextAtLevel(encoder, value, target.Level())
	}

	values := make([]complex128, c.Params.MaxSlots())
	for i := range values {
		values[i] = complex(value, 0)
	}

	pt := ckks.NewPlaintext(c.Params, target.Level())
	pt.Scale = target.Scale
	if err := encoder.Encode(values, pt); err != nil {
		return nil, fmt.Errorf("encode replicated plaintext at ciphertext scale: %w", err)
	}

	return pt, nil
}
