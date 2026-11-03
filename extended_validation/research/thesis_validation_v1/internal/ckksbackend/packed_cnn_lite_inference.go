package ckksbackend

import (
	"fmt"
	"math"
	"time"

	"github.com/hasslelee/flipguard/internal/benchmarks"
	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

var packedCNNLiteSpatialPositions = []int{0, 1, 2, 4, 5, 6, 8, 9, 10}

// RunCKKSPackedCNNLiteInference evaluates the existing learned CNN-lite model
// with one image packed over sixteen slots. No model parameter is changed.
func (c Context) RunCKKSPackedCNNLiteInference(
	config CKKSCNNLiteConfig,
) ([]CKKSCNNLiteRecord, error) {
	model, err := loadCNNLiteModel(config.ModelPath)
	if err != nil {
		return nil, err
	}
	rows, err := loadCNNLiteRows(config.DataPath, model)
	if err != nil {
		return nil, err
	}
	if config.MaxRows > 0 && config.MaxRows < len(rows) {
		rows = rows[:config.MaxRows]
	}
	if len(rows) == 0 {
		return nil, fmt.Errorf("packed CNN-lite data has no rows")
	}
	rotations := []int{1, 4, 5, 2, 6, 8, 9, 10}
	runtimeState, err := c.newCKKSTimingRuntimeWithRotations(rotations)
	if err != nil {
		return nil, fmt.Errorf("create packed CNN-lite CKKS runtime: %w", err)
	}
	records := make([]CKKSCNNLiteRecord, 0, len(rows))
	for _, row := range rows {
		record, err := c.runPackedCNNLiteSample(runtimeState, row, model)
		if err != nil {
			return nil, fmt.Errorf("packed CNN-lite row %d: %w", row.RowID, err)
		}
		records = append(records, record)
	}
	return records, nil
}

func (c Context) runPackedCNNLiteSample(
	runtimeState ckksTimingRuntime,
	row cnnLiteRow,
	model cnnLiteModelArtifact,
) (CKKSCNNLiteRecord, error) {
	totalStart := time.Now()
	encryptStart := time.Now()
	values := make([]complex128, c.Params.MaxSlots())
	for inputRow := 0; inputRow < benchmarks.CNNLiteInputSide; inputRow++ {
		for column := 0; column < benchmarks.CNNLiteInputSide; column++ {
			values[inputRow*benchmarks.CNNLiteInputSide+column] = complex(row.Pixels[inputRow][column], 0)
		}
	}
	plaintext := ckks.NewPlaintext(c.Params, c.MaxLevel())
	if err := runtimeState.encoder.Encode(values, plaintext); err != nil {
		return CKKSCNNLiteRecord{}, fmt.Errorf("encode packed image: %w", err)
	}
	input, err := runtimeState.encryptor.EncryptNew(plaintext)
	if err != nil {
		return CKKSCNNLiteRecord{}, fmt.Errorf("encrypt packed image: %w", err)
	}
	encodeEncryptMS := durationMS(time.Since(encryptStart))

	evalStart := time.Now()
	offsetCiphertexts := map[int]*rlwe.Ciphertext{0: input}
	for _, offset := range []int{1, 4, 5} {
		rotated, err := runtimeState.evaluator.RotateNew(input, offset)
		if err != nil {
			return CKKSCNNLiteRecord{}, fmt.Errorf("rotate input by %d: %w", offset, err)
		}
		offsetCiphertexts[offset] = rotated
	}
	var weightedActivations *rlwe.Ciphertext
	for filter := 0; filter < benchmarks.CNNLiteFilters; filter++ {
		artifact := model.LearnedParameters.ConvolutionFilters[filter]
		hidden, err := c.evalTabularWeightedSum(
			runtimeState,
			[]*rlwe.Ciphertext{
				offsetCiphertexts[0], offsetCiphertexts[1],
				offsetCiphertexts[4], offsetCiphertexts[5],
			},
			[]float64{
				artifact.Weights[0][0], artifact.Weights[0][1],
				artifact.Weights[1][0], artifact.Weights[1][1],
			},
			artifact.Bias,
		)
		if err != nil {
			return CKKSCNNLiteRecord{}, fmt.Errorf("packed convolution filter %d: %w", filter, err)
		}
		activation, err := c.squareTabularCiphertext(runtimeState, hidden, CKKSEvaluationModeRescale)
		if err != nil {
			return CKKSCNNLiteRecord{}, fmt.Errorf("packed square filter %d: %w", filter, err)
		}
		mask := make([]float64, c.Params.MaxSlots())
		for positionIndex, slot := range packedCNNLiteSpatialPositions {
			rowIndex := positionIndex / benchmarks.CNNLiteConvSide
			column := positionIndex % benchmarks.CNNLiteConvSide
			mask[slot] = model.LearnedParameters.OutputWeights[filter][rowIndex][column]
		}
		weighted, err := runtimeState.evaluator.MulNew(activation, mask)
		if err != nil {
			return CKKSCNNLiteRecord{}, fmt.Errorf("packed output mask filter %d: %w", filter, err)
		}
		if err := safeRescaleTo(runtimeState.evaluator, weighted, c.Params.DefaultScale(), weighted); err != nil {
			return CKKSCNNLiteRecord{}, fmt.Errorf("rescale packed output filter %d: %w", filter, err)
		}
		if weightedActivations == nil {
			weightedActivations = weighted
		} else if err := runtimeState.evaluator.Add(weightedActivations, weighted, weightedActivations); err != nil {
			return CKKSCNNLiteRecord{}, fmt.Errorf("add packed output filter %d: %w", filter, err)
		}
	}
	if weightedActivations == nil {
		return CKKSCNNLiteRecord{}, fmt.Errorf("packed output is empty")
	}
	result := weightedActivations.CopyNew()
	for _, slot := range packedCNNLiteSpatialPositions[1:] {
		rotated, err := runtimeState.evaluator.RotateNew(weightedActivations, slot)
		if err != nil {
			return CKKSCNNLiteRecord{}, fmt.Errorf("reduce packed slot %d: %w", slot, err)
		}
		if err := runtimeState.evaluator.Add(result, rotated, result); err != nil {
			return CKKSCNNLiteRecord{}, fmt.Errorf("add packed slot %d: %w", slot, err)
		}
	}
	bias := make([]complex128, c.Params.MaxSlots())
	bias[0] = complex(model.LearnedParameters.OutputBias, 0)
	biasPlaintext := ckks.NewPlaintext(c.Params, result.Level())
	if err := runtimeState.encoder.Encode(bias, biasPlaintext); err != nil {
		return CKKSCNNLiteRecord{}, fmt.Errorf("encode packed output bias: %w", err)
	}
	if err := runtimeState.evaluator.Add(result, biasPlaintext, result); err != nil {
		return CKKSCNNLiteRecord{}, fmt.Errorf("add packed output bias: %w", err)
	}
	evalOnlyMS := durationMS(time.Since(evalStart))
	decryptStart := time.Now()
	decoded, err := c.decryptFirstSlot(runtimeState.encoder, runtimeState.decryptor, result)
	if err != nil {
		return CKKSCNNLiteRecord{}, fmt.Errorf("decrypt packed score: %w", err)
	}
	decryptDecodeMS := durationMS(time.Since(decryptStart))
	decision := decoded >= model.DecisionThreshold
	return CKKSCNNLiteRecord{
		RowID: row.RowID, SampleID: row.SampleID,
		SourcePartition: row.SourcePartition, DigitLabel: row.DigitLabel,
		PlainScore: row.PlainScore, CKKSScore: decoded,
		AbsError:      math.Abs(decoded - row.PlainScore),
		PlainDecision: row.PlainDecision, CKKSDecision: decision,
		DecisionFlip:    row.PlainDecision != decision,
		EncodeEncryptMS: encodeEncryptMS, EvalOnlyMS: evalOnlyMS,
		DecryptDecodeMS: decryptDecodeMS, TotalEvalMS: durationMS(time.Since(totalStart)),
		InitialLevel: c.MaxLevel(), FinalLevel: result.Level(), FinalDegree: result.Degree(),
	}, nil
}
