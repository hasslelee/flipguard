package ckksbackend

import (
	"fmt"
	"math"
	"time"

	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

const (
	// ExternalExecutionScheduleEVAV101LinearPoly3 identifies the only external
	// compiled schedule currently implemented by the tabular backend.
	ExternalExecutionScheduleEVAV101LinearPoly3 = "microsoft_eva_v1.0.1_iris_linear_poly3_scalar_v1"

	evaV101InputScaleBits  = 20
	evaV101WeightScaleBits = 20
	evaV101BiasScaleBits   = 40
	evaV101OutputScaleBits = 20
	evaV101RequiredQPrimes = 3
	evaV101RescaleLevels   = 2
)

// ExternalExecutionScheduleRequirements are trusted backend facts for a
// compiled external schedule. They are not inferred from a provider request.
type ExternalExecutionScheduleRequirements struct {
	ScheduleID           string
	EvaluationMode       string
	ModelType            string
	ScoreFormula         string
	InputScaleBits       int
	OutputScaleBits      int
	RequiredQPrimes      int
	RescaleLevels        int
	ScalarReplicatedOnly bool
}

// LookupExternalExecutionSchedule returns the immutable backend contract for a
// supported compiled schedule.
func LookupExternalExecutionSchedule(
	scheduleID string,
) (ExternalExecutionScheduleRequirements, error) {
	switch scheduleID {
	case ExternalExecutionScheduleEVAV101LinearPoly3:
		return ExternalExecutionScheduleRequirements{
			ScheduleID:           scheduleID,
			EvaluationMode:       CKKSEvaluationModeEVAV101LinearPoly3,
			ModelType:            "linear_poly3",
			ScoreFormula:         "0.5 + 0.197*z - 0.004*z^3",
			InputScaleBits:       evaV101InputScaleBits,
			OutputScaleBits:      evaV101OutputScaleBits,
			RequiredQPrimes:      evaV101RequiredQPrimes,
			RescaleLevels:        evaV101RescaleLevels,
			ScalarReplicatedOnly: true,
		}, nil
	default:
		return ExternalExecutionScheduleRequirements{}, fmt.Errorf(
			"unsupported external execution schedule %q",
			scheduleID,
		)
	}
}

func (c Context) evalTabularEVALinearModel(
	runtimeState ckksTimingRuntime,
	inputs []*rlwe.Ciphertext,
	weights []float64,
	bias float64,
) (tabularModelEvalResult, error) {
	start := time.Now()
	if c.LogQCount() != evaV101RequiredQPrimes {
		return tabularModelEvalResult{}, fmt.Errorf(
			"EVA schedule requires exactly %d Q primes, got %d",
			evaV101RequiredQPrimes,
			c.LogQCount(),
		)
	}
	if c.LogDefaultScale() != evaV101InputScaleBits {
		return tabularModelEvalResult{}, fmt.Errorf(
			"EVA schedule requires default scale %d, got %d",
			evaV101InputScaleBits,
			c.LogDefaultScale(),
		)
	}
	if len(inputs) != len(weights) {
		return tabularModelEvalResult{}, fmt.Errorf(
			"input count %d does not match weight count %d",
			len(inputs),
			len(weights),
		)
	}

	var zCipher *rlwe.Ciphertext
	for index, input := range inputs {
		if err := requireEVAState(
			fmt.Sprintf("input %d", index),
			input,
			2,
			evaV101InputScaleBits,
			1,
		); err != nil {
			return tabularModelEvalResult{}, err
		}
		weight, err := c.encodeReplicatedPlaintextAtScale(
			runtimeState.encoder,
			weights[index],
			input.Level(),
			evaV101WeightScaleBits,
		)
		if err != nil {
			return tabularModelEvalResult{}, fmt.Errorf(
				"encode EVA weight %d: %w",
				index,
				err,
			)
		}
		term, err := runtimeState.evaluator.MulNew(input, weight)
		if err != nil {
			return tabularModelEvalResult{}, fmt.Errorf(
				"multiply EVA input %d by weight: %w",
				index,
				err,
			)
		}
		if zCipher == nil {
			zCipher = term
			continue
		}
		if err := runtimeState.evaluator.Add(
			zCipher,
			term,
			zCipher,
		); err != nil {
			return tabularModelEvalResult{}, fmt.Errorf(
				"add EVA weighted input %d: %w",
				index,
				err,
			)
		}
	}
	if zCipher == nil {
		return tabularModelEvalResult{}, fmt.Errorf(
			"EVA schedule has no weighted-sum accumulator",
		)
	}
	biasPlaintext, err := c.encodeReplicatedPlaintextAtScale(
		runtimeState.encoder,
		bias,
		zCipher.Level(),
		evaV101BiasScaleBits,
	)
	if err != nil {
		return tabularModelEvalResult{}, fmt.Errorf(
			"encode EVA linear bias: %w",
			err,
		)
	}
	zCipher, err = runtimeState.evaluator.AddNew(
		zCipher,
		biasPlaintext,
	)
	if err != nil {
		return tabularModelEvalResult{}, fmt.Errorf(
			"add EVA linear bias: %w",
			err,
		)
	}
	if err := requireEVAState(
		"linear output z",
		zCipher,
		2,
		40,
		1,
	); err != nil {
		return tabularModelEvalResult{}, err
	}
	return tabularModelEvalResult{
		ZCipher:     zCipher,
		ModelEvalMS: durationMS(time.Since(start)),
	}, nil
}

func (c Context) evalTabularEVALinearPoly3Score(
	runtimeState ckksTimingRuntime,
	zCipher *rlwe.Ciphertext,
) (ckksTimedPolynomialResult, error) {
	start := time.Now()
	if err := requireEVAState(
		"EVA polynomial input z",
		zCipher,
		2,
		40,
		1,
	); err != nil {
		return ckksTimedPolynomialResult{}, err
	}

	zSquared, err := runtimeState.evaluator.MulNew(zCipher, zCipher)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf(
			"EVA square z: %w",
			err,
		)
	}
	if err := runtimeState.evaluator.Rescale(
		zSquared,
		zSquared,
	); err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf(
			"EVA first Rescale(60): %w",
			err,
		)
	}
	zSquared, err = runtimeState.evaluator.RelinearizeNew(zSquared)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf(
			"EVA relinearize z squared: %w",
			err,
		)
	}
	if err := requireEVAState(
		"EVA z squared",
		zSquared,
		1,
		20,
		1,
	); err != nil {
		return ckksTimedPolynomialResult{}, err
	}

	zLevelOne := runtimeState.evaluator.DropLevelNew(zCipher, 1)
	if err := requireEVAState(
		"EVA mod-switched z",
		zLevelOne,
		1,
		40,
		1,
	); err != nil {
		return ckksTimedPolynomialResult{}, err
	}

	cubicCoefficient, err := c.encodeReplicatedPlaintextAtScale(
		runtimeState.encoder,
		-0.004,
		1,
		20,
	)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf(
			"encode EVA cubic coefficient: %w",
			err,
		)
	}
	cubicLinear, err := runtimeState.evaluator.MulNew(
		zLevelOne,
		cubicCoefficient,
	)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf(
			"EVA multiply cubic coefficient by z: %w",
			err,
		)
	}
	cubicTerm, err := runtimeState.evaluator.MulNew(
		cubicLinear,
		zSquared,
	)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf(
			"EVA form cubic term: %w",
			err,
		)
	}

	linearCoefficient, err := c.encodeReplicatedPlaintextAtScale(
		runtimeState.encoder,
		0.197,
		1,
		20,
	)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf(
			"encode EVA linear coefficient: %w",
			err,
		)
	}
	affineTerm, err := runtimeState.evaluator.MulNew(
		zLevelOne,
		linearCoefficient,
	)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf(
			"EVA multiply linear coefficient by z: %w",
			err,
		)
	}
	outputBias, err := c.encodeReplicatedPlaintextAtScale(
		runtimeState.encoder,
		0.5,
		1,
		60,
	)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf(
			"encode EVA output bias: %w",
			err,
		)
	}
	affineTerm, err = runtimeState.evaluator.AddNew(
		affineTerm,
		outputBias,
	)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf(
			"EVA add output bias: %w",
			err,
		)
	}
	scaleLift, err := c.encodeReplicatedPlaintextAtScale(
		runtimeState.encoder,
		1,
		1,
		20,
	)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf(
			"encode EVA affine scale lift: %w",
			err,
		)
	}
	affineTerm, err = runtimeState.evaluator.MulNew(
		affineTerm,
		scaleLift,
	)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf(
			"EVA lift affine scale: %w",
			err,
		)
	}
	yCipher, err := runtimeState.evaluator.SubNew(
		affineTerm,
		cubicTerm,
	)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf(
			"EVA subtract cubic term: %w",
			err,
		)
	}
	if err := runtimeState.evaluator.Rescale(
		yCipher,
		yCipher,
	); err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf(
			"EVA second Rescale(60): %w",
			err,
		)
	}
	yCipher, err = runtimeState.evaluator.RelinearizeNew(yCipher)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf(
			"EVA relinearize output: %w",
			err,
		)
	}
	if err := requireEVAState(
		"EVA output",
		yCipher,
		0,
		evaV101OutputScaleBits,
		1,
	); err != nil {
		return ckksTimedPolynomialResult{}, err
	}
	return ckksTimedPolynomialResult{
		YCipher:          yCipher,
		PolynomialEvalMS: durationMS(time.Since(start)),
	}, nil
}

func (c Context) encodeReplicatedPlaintextAtScale(
	encoder *ckks.Encoder,
	value float64,
	level int,
	logScale int,
) (*rlwe.Plaintext, error) {
	if level < 0 || level > c.MaxLevel() {
		return nil, fmt.Errorf(
			"plaintext level %d outside [0,%d]",
			level,
			c.MaxLevel(),
		)
	}
	if logScale <= 0 || logScale > 60 {
		return nil, fmt.Errorf(
			"plaintext log scale %d outside [1,60]",
			logScale,
		)
	}
	values := make([]complex128, c.Params.MaxSlots())
	for index := range values {
		values[index] = complex(value, 0)
	}
	plaintext := ckks.NewPlaintext(c.Params, level)
	plaintext.Scale = rlwe.NewScale(math.Exp2(float64(logScale)))
	if err := encoder.Encode(values, plaintext); err != nil {
		return nil, fmt.Errorf(
			"encode replicated plaintext at scale 2^%d: %w",
			logScale,
			err,
		)
	}
	return plaintext, nil
}

func requireEVAState(
	label string,
	ciphertext *rlwe.Ciphertext,
	level int,
	logScale float64,
	degree int,
) error {
	if ciphertext == nil {
		return fmt.Errorf("%s ciphertext is nil", label)
	}
	if ciphertext.Level() != level {
		return fmt.Errorf(
			"%s level mismatch: got %d expected %d",
			label,
			ciphertext.Level(),
			level,
		)
	}
	if ciphertext.Degree() != degree {
		return fmt.Errorf(
			"%s degree mismatch: got %d expected %d",
			label,
			ciphertext.Degree(),
			degree,
		)
	}
	actual := ciphertext.Scale.Log2()
	if math.Abs(actual-logScale) > 0.01 {
		return fmt.Errorf(
			"%s scale mismatch: got %.8f expected %.8f",
			label,
			actual,
			logScale,
		)
	}
	return nil
}
