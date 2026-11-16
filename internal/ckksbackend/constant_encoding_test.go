package ckksbackend

import (
	"math"
	"testing"

	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

func constantEncodingProbeContext(t *testing.T, scaleBits int, mode ConstantEncodingMode) Context {
	t.Helper()
	logQ := []int{scaleBits + 3}
	for i := 0; i < 6; i++ {
		logQ = append(logQ, scaleBits)
	}
	params, err := ckks.NewParametersFromLiteral(ckks.ParametersLiteral{
		LogN:            13,
		LogQ:            logQ,
		LogP:            []int{30},
		LogDefaultScale: scaleBits,
	})
	if err != nil {
		t.Fatalf("create parameters: %v", err)
	}
	return Context{Params: params, ConstantEncoding: mode}
}

// polynomialScaleProbe runs the as-run Horner polynomial path on one input and
// returns the final-ciphertext-to-default scale ratio and the signed error.
func polynomialScaleProbe(t *testing.T, context Context, input float64, weight float64) (float64, float64) {
	t.Helper()
	runtimeState, err := context.newCKKSTimingRuntime()
	if err != nil {
		t.Fatalf("create runtime: %v", err)
	}
	inputCipher, err := context.encryptSingleFeature(runtimeState.encoder, runtimeState.encryptor, input)
	if err != nil {
		t.Fatalf("encrypt input: %v", err)
	}
	zCipher, err := context.evalTabularWeightedSum(runtimeState, []*rlwe.Ciphertext{inputCipher}, []float64{weight}, 0)
	if err != nil {
		t.Fatalf("weighted sum: %v", err)
	}
	result, err := context.evalTimedPolynomialRescale(runtimeState, zCipher)
	if err != nil {
		t.Fatalf("polynomial: %v", err)
	}
	decoded, err := context.decryptFirstSlot(runtimeState.encoder, runtimeState.decryptor, result.YCipher)
	if err != nil {
		t.Fatalf("decrypt: %v", err)
	}
	z := input * weight
	plain := 0.5 + 0.197*z - 0.004*z*z*z
	ratio := result.YCipher.Scale.Float64() / context.Params.DefaultScale().Float64()
	return ratio, decoded - plain
}

// TestConstantEncodingScaleMismatch records the deterministic bias introduced
// when the output constant is encoded at the default scale, and confirms that
// encoding it at the ciphertext scale removes that bias.
func TestConstantEncodingScaleMismatch(t *testing.T) {
	for _, scaleBits := range []int{20, 24} {
		for _, mode := range []ConstantEncodingMode{ConstantEncodingDefaultScale, ConstantEncodingCiphertextScale} {
			context := constantEncodingProbeContext(t, scaleBits, mode)
			for _, input := range []float64{-1.5, 0.02, 1.5} {
				ratio, signedError := polynomialScaleProbe(t, context, input, 0.8)
				t.Logf("scale=%d mode=%q input=%+.2f final_scale_over_default=%.5f signed_error=%+.6f",
					scaleBits, string(mode), input, ratio, signedError)
				if mode == ConstantEncodingCiphertextScale && math.Abs(signedError) > 0.005 {
					t.Fatalf("ciphertext-scale constant encoding left error %.6f at scale %d", signedError, scaleBits)
				}
			}
		}
	}
}
