package ckksbackend

import (
	"fmt"
	"math"

	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// MultiplicationProbeMethod identifies one ciphertext-ciphertext multiplication path.
type MultiplicationProbeMethod string

const (
	MultiplicationMulOnly         MultiplicationProbeMethod = "mul_only"
	MultiplicationMulRelin        MultiplicationProbeMethod = "mul_relin"
	MultiplicationMulRescale      MultiplicationProbeMethod = "mul_rescale"
	MultiplicationMulRelinRescale MultiplicationProbeMethod = "mul_relin_rescale"
)

// MultiplicationProbeCase defines one ciphertext-ciphertext multiplication probe.
type MultiplicationProbeCase struct {
	Z float64
}

// MultiplicationProbeResult records the observed behavior of z*z under CKKS.
type MultiplicationProbeResult struct {
	Method MultiplicationProbeMethod

	Z float64

	PlainZ2 float64

	RawDecodedZ2 float64
	RawAbsError  float64

	ScaledDecodedZ2 float64
	ScaledAbsError  float64

	SelectedInterpretation ScaleInterpretation
	SelectedZ2             float64
	SelectedAbsError       float64

	DecodeScaleCorrection float64

	InitialLevel int
	FinalLevel   int

	InputDegree  int
	OutputDegree int

	LogDefaultScale int
}

// DefaultMultiplicationProbeCases returns deterministic z values.
func DefaultMultiplicationProbeCases() []MultiplicationProbeCase {
	return []MultiplicationProbeCase{
		{Z: 0.0},
		{Z: 0.095},
		{Z: -0.3},
		{Z: 0.61},
		{Z: -0.84},
		{Z: 1.2},
	}
}

// DefaultMultiplicationProbeMethods returns the multiplication paths compared by the probe.
func DefaultMultiplicationProbeMethods() []MultiplicationProbeMethod {
	return []MultiplicationProbeMethod{
		MultiplicationMulOnly,
		MultiplicationMulRelin,
		MultiplicationMulRescale,
		MultiplicationMulRelinRescale,
	}
}

// RunMultiplicationProbe executes all default multiplication probe cases and methods.
func (c Context) RunMultiplicationProbe() ([]MultiplicationProbeResult, error) {
	cases := DefaultMultiplicationProbeCases()
	methods := DefaultMultiplicationProbeMethods()

	results := make([]MultiplicationProbeResult, 0, len(cases)*len(methods))

	for caseIndex, probeCase := range cases {
		for _, method := range methods {
			result, err := c.RunMultiplicationProbeCase(probeCase, method)
			if err != nil {
				return nil, fmt.Errorf("run multiplication probe case %d method %s: %w", caseIndex, method, err)
			}

			results = append(results, result)
		}
	}

	return results, nil
}

// RunMultiplicationProbeCase evaluates z2 = z*z using the selected CKKS multiplication path.
func (c Context) RunMultiplicationProbeCase(
	probeCase MultiplicationProbeCase,
	method MultiplicationProbeMethod,
) (MultiplicationProbeResult, error) {
	encoder := ckks.NewEncoder(c.Params)

	kgen := ckks.NewKeyGenerator(c.Params)
	sk, pk := kgen.GenKeyPairNew()
	rlk := kgen.GenRelinearizationKeyNew(sk)

	encryptor := ckks.NewEncryptor(c.Params, pk)
	decryptor := ckks.NewDecryptor(c.Params, sk)

	evaluator := ckks.NewEvaluator(c.Params, nil)
	relinEvaluator := ckks.NewEvaluator(c.Params, rlwe.NewMemEvaluationKeySet(rlk))

	zCipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.Z)
	if err != nil {
		return MultiplicationProbeResult{}, fmt.Errorf("encrypt z: %w", err)
	}

	out, err := evaluateSquareByMethod(c, evaluator, relinEvaluator, zCipher, method)
	if err != nil {
		return MultiplicationProbeResult{}, err
	}

	raw, err := c.decryptFirstSlot(encoder, decryptor, out)
	if err != nil {
		return MultiplicationProbeResult{}, fmt.Errorf("decrypt z2: %w", err)
	}

	plain := probeCase.Z * probeCase.Z
	correction := math.Exp2(float64(c.LogDefaultScale()))

	rawAbsError := math.Abs(raw - plain)

	scaled := raw / correction
	scaledAbsError := math.Abs(scaled - plain)

	selectedInterpretation := ScaleInterpretationRaw
	selectedValue := raw
	selectedAbsError := rawAbsError

	if scaledAbsError < rawAbsError {
		selectedInterpretation = ScaleInterpretationDivideDefaultScale
		selectedValue = scaled
		selectedAbsError = scaledAbsError
	}

	return MultiplicationProbeResult{
		Method: method,

		Z: probeCase.Z,

		PlainZ2: plain,

		RawDecodedZ2: raw,
		RawAbsError:  rawAbsError,

		ScaledDecodedZ2: scaled,
		ScaledAbsError:  scaledAbsError,

		SelectedInterpretation: selectedInterpretation,
		SelectedZ2:             selectedValue,
		SelectedAbsError:       selectedAbsError,

		DecodeScaleCorrection: correction,

		InitialLevel: c.MaxLevel(),
		FinalLevel:   out.Level(),

		InputDegree:  zCipher.Degree(),
		OutputDegree: out.Degree(),

		LogDefaultScale: c.LogDefaultScale(),
	}, nil
}

func evaluateSquareByMethod(
	c Context,
	evaluator *ckks.Evaluator,
	relinEvaluator *ckks.Evaluator,
	zCipher *rlwe.Ciphertext,
	method MultiplicationProbeMethod,
) (*rlwe.Ciphertext, error) {
	switch method {
	case MultiplicationMulOnly:
		out, err := evaluator.MulNew(zCipher, zCipher)
		if err != nil {
			return nil, fmt.Errorf("multiply z by z: %w", err)
		}

		return out, nil

	case MultiplicationMulRelin:
		out, err := relinEvaluator.MulNew(zCipher, zCipher)
		if err != nil {
			return nil, fmt.Errorf("multiply z by z: %w", err)
		}

		out, err = relinEvaluator.RelinearizeNew(out)
		if err != nil {
			return nil, fmt.Errorf("relinearize z2: %w", err)
		}

		return out, nil

	case MultiplicationMulRescale:
		out, err := evaluator.MulNew(zCipher, zCipher)
		if err != nil {
			return nil, fmt.Errorf("multiply z by z: %w", err)
		}

		out, err = c.rescaleNew(evaluator, out)
		if err != nil {
			return nil, fmt.Errorf("rescale z2: %w", err)
		}

		return out, nil

	case MultiplicationMulRelinRescale:
		out, err := relinEvaluator.MulNew(zCipher, zCipher)
		if err != nil {
			return nil, fmt.Errorf("multiply z by z: %w", err)
		}

		out, err = relinEvaluator.RelinearizeNew(out)
		if err != nil {
			return nil, fmt.Errorf("relinearize z2: %w", err)
		}

		out, err = c.rescaleNew(relinEvaluator, out)
		if err != nil {
			return nil, fmt.Errorf("rescale z2: %w", err)
		}

		return out, nil

	default:
		return nil, fmt.Errorf("unsupported multiplication probe method: %s", method)
	}
}

func (c Context) rescaleNew(evaluator *ckks.Evaluator, ct *rlwe.Ciphertext) (*rlwe.Ciphertext, error) {
	levels := c.Params.LevelsConsumedPerRescaling()
	if levels <= 0 {
		levels = 1
	}

	if ct.Level() < levels {
		return nil, fmt.Errorf("cannot rescale ciphertext at level %d by %d level(s)", ct.Level(), levels)
	}

	out := ckks.NewCiphertext(c.Params, ct.Degree(), ct.Level()-levels)

	if err := evaluator.Rescale(ct, out); err != nil {
		return nil, fmt.Errorf("rescale ciphertext: %w", err)
	}

	return out, nil
}
