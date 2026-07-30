package ckksbackend

import (
	"fmt"
	"math"

	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// LinearLogRegResult summarizes encrypted evaluation of the linear part of
// the current logreg_small benchmark.
//
// Target expression:
//
//	z = 0.8*x1 - 0.5*x2 + 1.2*x3 - 0.3
//
// This step intentionally encrypts x1, x2, and x3 as separate ciphertexts.
// Slot packing with rotations will be added after this linear encrypted path is
// stable.
type LinearLogRegResult struct {
	Input LogRegSmallInput

	PlainZ float64

	// RawCKKSZ is the directly decoded first slot.
	//
	// After the bias-addition probe, the linear evaluator now adds the bias as a
	// CKKS plaintext rather than as a float64 scalar operand. Therefore RawCKKSZ
	// is expected to already be in the plaintext domain.
	RawCKKSZ float64

	// CKKSZ is the decoded value used for comparison with PlainZ.
	//
	// In the current plaintext-bias implementation, CKKSZ equals RawCKKSZ.
	CKKSZ float64

	// DecodeScaleCorrection records any post-decode correction factor.
	//
	// The old scalar-bias path used 2^LogDefaultScale as a temporary correction.
	// The current plaintext-bias path should not require post-decode correction,
	// so this value is 1.
	DecodeScaleCorrection float64

	AbsError float64

	InitialLevel int
	FinalLevel   int

	LogDefaultScale int
}

// EvalLogRegSmallLinearPlain evaluates the linear part in plaintext.
func EvalLogRegSmallLinearPlain(input LogRegSmallInput) float64 {
	return 0.8*input.X1 - 0.5*input.X2 + 1.2*input.X3 - 0.3
}

// EvalLogRegSmallLinearEncrypted evaluates the linear part of logreg_small
// using Lattigo CKKS ciphertext operations.
//
// The constant bias term is encoded as a CKKS plaintext and then added to the
// ciphertext expression. This avoids the temporary decode-scale correction that
// was required when using evaluator.AddNew(ciphertext, float64_bias).
func (c Context) EvalLogRegSmallLinearEncrypted(input LogRegSmallInput) (LinearLogRegResult, error) {
	encoder := ckks.NewEncoder(c.Params)

	kgen := ckks.NewKeyGenerator(c.Params)
	sk, pk := kgen.GenKeyPairNew()

	encryptor := ckks.NewEncryptor(c.Params, pk)
	decryptor := ckks.NewDecryptor(c.Params, sk)

	// No relinearization or rotation key is required in this step because this
	// function only uses ciphertext-constant multiplication and addition.
	evaluator := ckks.NewEvaluator(c.Params, nil)

	x1, err := c.encryptReplicatedScalar(encoder, encryptor, input.X1)
	if err != nil {
		return LinearLogRegResult{}, fmt.Errorf("encrypt x1: %w", err)
	}

	x2, err := c.encryptReplicatedScalar(encoder, encryptor, input.X2)
	if err != nil {
		return LinearLogRegResult{}, fmt.Errorf("encrypt x2: %w", err)
	}

	x3, err := c.encryptReplicatedScalar(encoder, encryptor, input.X3)
	if err != nil {
		return LinearLogRegResult{}, fmt.Errorf("encrypt x3: %w", err)
	}

	t1, err := evaluator.MulNew(x1, 0.8)
	if err != nil {
		return LinearLogRegResult{}, fmt.Errorf("multiply x1 by 0.8: %w", err)
	}

	t2, err := evaluator.MulNew(x2, -0.5)
	if err != nil {
		return LinearLogRegResult{}, fmt.Errorf("multiply x2 by -0.5: %w", err)
	}

	t3, err := evaluator.MulNew(x3, 1.2)
	if err != nil {
		return LinearLogRegResult{}, fmt.Errorf("multiply x3 by 1.2: %w", err)
	}

	sum12, err := evaluator.AddNew(t1, t2)
	if err != nil {
		return LinearLogRegResult{}, fmt.Errorf("add t1 and t2: %w", err)
	}

	sum123, err := evaluator.AddNew(sum12, t3)
	if err != nil {
		return LinearLogRegResult{}, fmt.Errorf("add t3: %w", err)
	}

	biasPlaintext, err := c.encodeReplicatedPlaintextAtLevel(encoder, -0.3, sum123.Level())
	if err != nil {
		return LinearLogRegResult{}, fmt.Errorf("encode bias plaintext: %w", err)
	}

	zCipher, err := evaluator.AddNew(sum123, biasPlaintext)
	if err != nil {
		return LinearLogRegResult{}, fmt.Errorf("add plaintext bias -0.3: %w", err)
	}

	zDecoded, err := c.decryptFirstSlot(encoder, decryptor, zCipher)
	if err != nil {
		return LinearLogRegResult{}, fmt.Errorf("decrypt z: %w", err)
	}

	plainZ := EvalLogRegSmallLinearPlain(input)

	return LinearLogRegResult{
		Input: input,

		PlainZ: plainZ,

		RawCKKSZ: zDecoded,
		CKKSZ:    zDecoded,

		DecodeScaleCorrection: 1.0,

		AbsError: math.Abs(zDecoded - plainZ),

		InitialLevel: c.MaxLevel(),
		FinalLevel:   zCipher.Level(),

		LogDefaultScale: c.LogDefaultScale(),
	}, nil
}

func (c Context) encryptReplicatedScalar(
	encoder *ckks.Encoder,
	encryptor *rlwe.Encryptor,
	value float64,
) (*rlwe.Ciphertext, error) {
	values := make([]complex128, c.Params.MaxSlots())
	for i := range values {
		values[i] = complex(value, 0)
	}

	pt := ckks.NewPlaintext(c.Params, c.Params.MaxLevel())

	if err := encoder.Encode(values, pt); err != nil {
		return nil, fmt.Errorf("encode replicated scalar: %w", err)
	}

	ct, err := encryptor.EncryptNew(pt)
	if err != nil {
		return nil, fmt.Errorf("encrypt replicated scalar: %w", err)
	}

	return ct, nil
}

func (c Context) decryptFirstSlot(
	encoder *ckks.Encoder,
	decryptor *rlwe.Decryptor,
	ct *rlwe.Ciphertext,
) (float64, error) {
	pt := decryptor.DecryptNew(ct)

	decoded := make([]complex128, c.Params.MaxSlots())
	if err := encoder.Decode(pt, decoded); err != nil {
		return 0, fmt.Errorf("decode first slot: %w", err)
	}

	return real(decoded[0]), nil
}
