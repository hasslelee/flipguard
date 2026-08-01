package ckksbackend

import (
	"fmt"
	"math"
	"runtime"
	"time"

	"github.com/hasslelee/flipguard/internal/journalmnist"
	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

const JournalMNISTMulticlassExecutionAdapterV1 = "mnist_multiclass_feature_ciphertext_batch_adapter_v1"

type JournalMNISTMulticlassConfig struct {
	ModelPath string
	DataPath  string
	Role      string
}

type JournalMNISTMulticlassRecord struct {
	RowID           int       `json:"row_id"`
	SampleID        string    `json:"sample_id"`
	SourceIndex     int       `json:"source_index"`
	SourcePartition string    `json:"source_partition"`
	Role            string    `json:"role"`
	Label           int       `json:"label"`
	PlainLogits     []float64 `json:"plaintext_logits"`
	CKKSLogits      []float64 `json:"ckks_logits"`
	PlainTop1       int       `json:"plaintext_top_1"`
	CKKSTop1        int       `json:"ckks_top_1"`
	TopTwoGap       float64   `json:"top_two_gap"`
	ArgmaxFlip      bool      `json:"argmax_flip"`
}

type JournalMNISTMulticlassSummary struct {
	ExecutionAdapter string `json:"execution_adapter"`
	DatasetID        string `json:"dataset_id"`
	ModelID          string `json:"model_id"`
	ModelType        string `json:"model_type"`
	Role             string `json:"role"`
	EvaluatedRows    int    `json:"evaluated_rows"`
	ClassCount       int    `json:"class_count"`

	CryptoSetupMS    float64 `json:"crypto_setup_ms"`
	EncodeEncryptMS  float64 `json:"encode_encrypt_ms"`
	EvaluationOnlyMS float64 `json:"evaluation_only_ms"`
	DecryptDecodeMS  float64 `json:"decrypt_decode_ms"`
	TotalMS          float64 `json:"total_ms"`
	AmortizedMS      float64 `json:"amortized_total_ms_per_image"`

	InputCiphertexts  int `json:"input_ciphertexts"`
	OutputCiphertexts int `json:"output_ciphertexts"`
	InitialLevel      int `json:"initial_level"`
	FinalLevel        int `json:"final_level"`
	RequiredSlots     int `json:"required_slots"`
	AvailableSlots    int `json:"available_slots"`
	ArgmaxFlips       int `json:"argmax_flips"`
}

func (c Context) RunCKKSJournalMNISTMulticlassInference(
	config JournalMNISTMulticlassConfig,
) ([]JournalMNISTMulticlassRecord, JournalMNISTMulticlassSummary, error) {
	modelArtifact, err := journalmnist.LoadModelArtifact(config.ModelPath)
	if err != nil {
		return nil, JournalMNISTMulticlassSummary{}, err
	}
	rows, err := journalmnist.LoadPartitionCSV(config.DataPath, config.Role)
	if err != nil {
		return nil, JournalMNISTMulticlassSummary{}, err
	}
	if len(rows) > c.Params.MaxSlots() {
		return nil, JournalMNISTMulticlassSummary{}, fmt.Errorf(
			"required samples %d exceed CKKS slots %d",
			len(rows),
			c.Params.MaxSlots(),
		)
	}
	totalStart := time.Now()
	setupStart := time.Now()
	runtimeState, err := c.newCKKSTimingRuntime()
	if err != nil {
		return nil, JournalMNISTMulticlassSummary{}, fmt.Errorf("create multiclass runtime: %w", err)
	}
	setupMS := durationMS(time.Since(setupStart))
	encodeStart := time.Now()
	inputs, err := c.encryptMNISTFeatureVectors(runtimeState, rows)
	if err != nil {
		return nil, JournalMNISTMulticlassSummary{}, err
	}
	encodeMS := durationMS(time.Since(encodeStart))
	evalStart := time.Now()
	var output []*rlwe.Ciphertext
	switch modelArtifact.ModelType {
	case journalmnist.MLPModelType:
		output, err = c.evaluateMNISTMLP(runtimeState, journalmnist.MLPModel{Parameters: modelArtifact.Parameters}, inputs)
	case journalmnist.LeNetModelType:
		output, err = c.evaluateMNISTLeNet(runtimeState, journalmnist.LeNetModel{Parameters: modelArtifact.Parameters}, inputs)
	default:
		err = fmt.Errorf("unsupported journal multiclass model %q", modelArtifact.ModelType)
	}
	if err != nil {
		return nil, JournalMNISTMulticlassSummary{}, err
	}
	evalMS := durationMS(time.Since(evalStart))
	// Inputs are no longer live after model evaluation. Encourage release before
	// decoding large LeNet runs without changing arithmetic semantics.
	inputs = nil
	runtime.GC()
	decodeStart := time.Now()
	decoded := make([][]float64, len(output))
	for classIndex, ciphertext := range output {
		values, err := c.decryptRealSlots(runtimeState.encoder, runtimeState.decryptor, ciphertext, len(rows))
		if err != nil {
			return nil, JournalMNISTMulticlassSummary{}, fmt.Errorf("decode class %d: %w", classIndex, err)
		}
		decoded[classIndex] = values
	}
	decodeMS := durationMS(time.Since(decodeStart))
	records := make([]JournalMNISTMulticlassRecord, 0, len(rows))
	flips := 0
	for rowIndex, row := range rows {
		plainArray, err := modelArtifact.Logits(row)
		if err != nil {
			return nil, JournalMNISTMulticlassSummary{}, err
		}
		plain := append([]float64(nil), plainArray[:]...)
		approximate := make([]float64, journalmnist.ClassCount)
		for classIndex := range approximate {
			approximate[classIndex] = decoded[classIndex][rowIndex]
		}
		plainTop, _, gap := topTwoJournalLogits(plain)
		approxTop, _, _ := topTwoJournalLogits(approximate)
		flip := plainTop != approxTop
		if flip {
			flips++
		}
		records = append(records, JournalMNISTMulticlassRecord{
			RowID: row.RowID, SampleID: row.SampleID, SourceIndex: row.SourceIndex,
			SourcePartition: row.SourcePartition, Role: row.Role, Label: row.Label,
			PlainLogits: plain, CKKSLogits: approximate, PlainTop1: plainTop,
			CKKSTop1: approxTop, TopTwoGap: gap, ArgmaxFlip: flip,
		})
	}
	finalLevel := -1
	if len(output) > 0 {
		finalLevel = output[0].Level()
	}
	totalMS := durationMS(time.Since(totalStart))
	return records, JournalMNISTMulticlassSummary{
		ExecutionAdapter: JournalMNISTMulticlassExecutionAdapterV1,
		DatasetID:        modelArtifact.DatasetID, ModelID: modelArtifact.ModelID,
		ModelType: modelArtifact.ModelType, Role: config.Role,
		EvaluatedRows: len(rows), ClassCount: journalmnist.ClassCount,
		CryptoSetupMS: setupMS, EncodeEncryptMS: encodeMS,
		EvaluationOnlyMS: evalMS, DecryptDecodeMS: decodeMS, TotalMS: totalMS,
		AmortizedMS: totalMS / float64(len(rows)), InputCiphertexts: journalmnist.PixelCount,
		OutputCiphertexts: len(output), InitialLevel: c.MaxLevel(), FinalLevel: finalLevel,
		RequiredSlots: len(rows), AvailableSlots: c.Params.MaxSlots(), ArgmaxFlips: flips,
	}, nil
}

func (c Context) encryptMNISTFeatureVectors(runtimeState ckksTimingRuntime, rows []journalmnist.PartitionRow) ([]*rlwe.Ciphertext, error) {
	inputs := make([]*rlwe.Ciphertext, journalmnist.PixelCount)
	values := make([]complex128, c.Params.MaxSlots())
	for pixel := 0; pixel < journalmnist.PixelCount; pixel++ {
		for index := range values {
			values[index] = 0
		}
		for rowIndex, row := range rows {
			values[rowIndex] = complex(float64(row.Pixels[pixel])/255, 0)
		}
		plaintext := ckks.NewPlaintext(c.Params, c.Params.MaxLevel())
		if err := runtimeState.encoder.Encode(values, plaintext); err != nil {
			return nil, fmt.Errorf("encode pixel feature %d: %w", pixel, err)
		}
		ciphertext, err := runtimeState.encryptor.EncryptNew(plaintext)
		if err != nil {
			return nil, fmt.Errorf("encrypt pixel feature %d: %w", pixel, err)
		}
		inputs[pixel] = ciphertext
	}
	return inputs, nil
}

func (c Context) evaluateMNISTMLP(runtimeState ckksTimingRuntime, model journalmnist.MLPModel, inputs []*rlwe.Ciphertext) ([]*rlwe.Ciphertext, error) {
	hidden := make([]*rlwe.Ciphertext, journalmnist.MLPHidden)
	weights := make([]float64, journalmnist.PixelCount)
	for unit := 0; unit < journalmnist.MLPHidden; unit++ {
		for pixel := range weights {
			weights[pixel] = model.HiddenWeight(unit, pixel)
		}
		affine, err := c.weightedCipherSum(runtimeState, inputs, weights, model.HiddenBias(unit))
		if err != nil {
			return nil, fmt.Errorf("MLP hidden unit %d: %w", unit, err)
		}
		hidden[unit], err = c.squareAndRescale(runtimeState, affine)
		if err != nil {
			return nil, fmt.Errorf("MLP hidden square %d: %w", unit, err)
		}
	}
	outputs := make([]*rlwe.Ciphertext, journalmnist.ClassCount)
	weights = make([]float64, journalmnist.MLPHidden)
	for classIndex := 0; classIndex < journalmnist.ClassCount; classIndex++ {
		for unit := range weights {
			weights[unit] = model.OutputWeight(classIndex, unit)
		}
		output, err := c.weightedCipherSum(runtimeState, hidden, weights, model.OutputBias(classIndex))
		if err != nil {
			return nil, fmt.Errorf("MLP output class %d: %w", classIndex, err)
		}
		outputs[classIndex] = output
	}
	return outputs, nil
}

func (c Context) evaluateMNISTLeNet(runtimeState ckksTimingRuntime, model journalmnist.LeNetModel, inputs []*rlwe.Ciphertext) ([]*rlwe.Ciphertext, error) {
	p1 := make([]*rlwe.Ciphertext, journalmnist.LeNetC1Channels*journalmnist.LeNetP1Side*journalmnist.LeNetP1Side)
	for channel := 0; channel < journalmnist.LeNetC1Channels; channel++ {
		for poolRow := 0; poolRow < journalmnist.LeNetP1Side; poolRow++ {
			for poolColumn := 0; poolColumn < journalmnist.LeNetP1Side; poolColumn++ {
				squares := make([]*rlwe.Ciphertext, 0, 4)
				for deltaRow := 0; deltaRow < 2; deltaRow++ {
					for deltaColumn := 0; deltaColumn < 2; deltaColumn++ {
						row := 2*poolRow + deltaRow
						column := 2*poolColumn + deltaColumn
						terms := make([]*rlwe.Ciphertext, 0, 25)
						weights := make([]float64, 0, 25)
						for kernelRow := 0; kernelRow < journalmnist.LeNetKernelSide; kernelRow++ {
							for kernelColumn := 0; kernelColumn < journalmnist.LeNetKernelSide; kernelColumn++ {
								pixel, exists := journalmnist.PaddedPixelIndex(row+kernelRow, column+kernelColumn)
								if exists {
									terms = append(terms, inputs[pixel])
									weights = append(weights, model.C1Weight(channel, kernelRow, kernelColumn))
								}
							}
						}
						affine, err := c.weightedCipherSum(runtimeState, terms, weights, model.C1Bias(channel))
						if err != nil {
							return nil, fmt.Errorf("LeNet C1 c=%d r=%d col=%d: %w", channel, row, column, err)
						}
						squared, err := c.squareAndRescale(runtimeState, affine)
						if err != nil {
							return nil, fmt.Errorf("LeNet C1 square: %w", err)
						}
						squares = append(squares, squared)
					}
				}
				pooled, err := c.averageFour(runtimeState, squares)
				if err != nil {
					return nil, fmt.Errorf("LeNet pool1: %w", err)
				}
				p1[journalmnist.LeNetP1Index(channel, poolRow, poolColumn)] = pooled
			}
		}
	}
	inputs = nil
	runtime.GC()
	p2 := make([]*rlwe.Ciphertext, journalmnist.LeNetP2Features)
	for outputChannel := 0; outputChannel < journalmnist.LeNetC2Channels; outputChannel++ {
		for poolRow := 0; poolRow < journalmnist.LeNetP2Side; poolRow++ {
			for poolColumn := 0; poolColumn < journalmnist.LeNetP2Side; poolColumn++ {
				squares := make([]*rlwe.Ciphertext, 0, 4)
				for deltaRow := 0; deltaRow < 2; deltaRow++ {
					for deltaColumn := 0; deltaColumn < 2; deltaColumn++ {
						row := 2*poolRow + deltaRow
						column := 2*poolColumn + deltaColumn
						terms := make([]*rlwe.Ciphertext, 0, 150)
						weights := make([]float64, 0, 150)
						for inputChannel := 0; inputChannel < journalmnist.LeNetC1Channels; inputChannel++ {
							for kernelRow := 0; kernelRow < journalmnist.LeNetKernelSide; kernelRow++ {
								for kernelColumn := 0; kernelColumn < journalmnist.LeNetKernelSide; kernelColumn++ {
									terms = append(terms, p1[journalmnist.LeNetP1Index(inputChannel, row+kernelRow, column+kernelColumn)])
									weights = append(weights, model.C2Weight(outputChannel, inputChannel, kernelRow, kernelColumn))
								}
							}
						}
						affine, err := c.weightedCipherSum(runtimeState, terms, weights, model.C2Bias(outputChannel))
						if err != nil {
							return nil, fmt.Errorf("LeNet C2 c=%d r=%d col=%d: %w", outputChannel, row, column, err)
						}
						squared, err := c.squareAndRescale(runtimeState, affine)
						if err != nil {
							return nil, fmt.Errorf("LeNet C2 square: %w", err)
						}
						squares = append(squares, squared)
					}
				}
				pooled, err := c.averageFour(runtimeState, squares)
				if err != nil {
					return nil, fmt.Errorf("LeNet pool2: %w", err)
				}
				p2[journalmnist.LeNetP2Index(outputChannel, poolRow, poolColumn)] = pooled
			}
		}
	}
	p1 = nil
	runtime.GC()
	fc1, err := c.evaluateSquareAffineLayer(runtimeState, p2, journalmnist.LeNetFC1,
		func(unit, input int) float64 { return model.FC1Weight(unit, input) }, model.FC1Bias)
	if err != nil {
		return nil, fmt.Errorf("LeNet FC1: %w", err)
	}
	p2 = nil
	runtime.GC()
	fc2, err := c.evaluateSquareAffineLayer(runtimeState, fc1, journalmnist.LeNetFC2,
		func(unit, input int) float64 { return model.FC2Weight(unit, input) }, model.FC2Bias)
	if err != nil {
		return nil, fmt.Errorf("LeNet FC2: %w", err)
	}
	fc1 = nil
	runtime.GC()
	outputs := make([]*rlwe.Ciphertext, journalmnist.ClassCount)
	weights := make([]float64, journalmnist.LeNetFC2)
	for classIndex := 0; classIndex < journalmnist.ClassCount; classIndex++ {
		for input := range weights {
			weights[input] = model.OutputWeight(classIndex, input)
		}
		outputs[classIndex], err = c.weightedCipherSum(runtimeState, fc2, weights, model.OutputBias(classIndex))
		if err != nil {
			return nil, fmt.Errorf("LeNet output %d: %w", classIndex, err)
		}
	}
	return outputs, nil
}

func (c Context) evaluateSquareAffineLayer(runtimeState ckksTimingRuntime, inputs []*rlwe.Ciphertext, units int,
	weight func(int, int) float64, bias func(int) float64) ([]*rlwe.Ciphertext, error) {
	outputs := make([]*rlwe.Ciphertext, units)
	weights := make([]float64, len(inputs))
	for unit := 0; unit < units; unit++ {
		for input := range weights {
			weights[input] = weight(unit, input)
		}
		affine, err := c.weightedCipherSum(runtimeState, inputs, weights, bias(unit))
		if err != nil {
			return nil, fmt.Errorf("unit %d affine: %w", unit, err)
		}
		outputs[unit], err = c.squareAndRescale(runtimeState, affine)
		if err != nil {
			return nil, fmt.Errorf("unit %d square: %w", unit, err)
		}
	}
	return outputs, nil
}

func (c Context) weightedCipherSum(runtimeState ckksTimingRuntime, inputs []*rlwe.Ciphertext, weights []float64, bias float64) (*rlwe.Ciphertext, error) {
	if len(inputs) == 0 || len(inputs) != len(weights) {
		return nil, fmt.Errorf("weighted sum inputs=%d weights=%d", len(inputs), len(weights))
	}
	accumulator, err := runtimeState.evaluator.MulNew(inputs[0], weights[0])
	if err != nil {
		return nil, err
	}
	for index := 1; index < len(inputs); index++ {
		if err := runtimeState.evaluator.MulThenAdd(inputs[index], weights[index], accumulator); err != nil {
			return nil, fmt.Errorf("term %d: %w", index, err)
		}
	}
	if bias != 0 {
		if err := runtimeState.evaluator.Add(accumulator, bias, accumulator); err != nil {
			return nil, fmt.Errorf("bias: %w", err)
		}
	}
	return accumulator, nil
}

func (c Context) squareAndRescale(runtimeState ckksTimingRuntime, input *rlwe.Ciphertext) (*rlwe.Ciphertext, error) {
	squared, err := runtimeState.evaluator.MulRelinNew(input, input)
	if err != nil {
		return nil, err
	}
	if err := safeRescaleTo(runtimeState.evaluator, squared, c.Params.DefaultScale(), squared); err != nil {
		return nil, err
	}
	return squared, nil
}

func (c Context) averageFour(runtimeState ckksTimingRuntime, inputs []*rlwe.Ciphertext) (*rlwe.Ciphertext, error) {
	if len(inputs) != 4 {
		return nil, fmt.Errorf("average pool requires four inputs")
	}
	sum := inputs[0].CopyNew()
	for index := 1; index < len(inputs); index++ {
		if err := runtimeState.evaluator.Add(sum, inputs[index], sum); err != nil {
			return nil, err
		}
	}
	return runtimeState.evaluator.MulNew(sum, 0.25)
}

func (c Context) decryptRealSlots(encoder *ckks.Encoder, decryptor *rlwe.Decryptor, ciphertext *rlwe.Ciphertext, count int) ([]float64, error) {
	plaintext := decryptor.DecryptNew(ciphertext)
	decoded := make([]complex128, c.Params.MaxSlots())
	if err := encoder.Decode(plaintext, decoded); err != nil {
		return nil, err
	}
	result := make([]float64, count)
	for index := range result {
		value := real(decoded[index])
		if math.IsNaN(value) || math.IsInf(value, 0) {
			return nil, fmt.Errorf("decoded slot %d is non-finite", index)
		}
		result[index] = value
	}
	return result, nil
}

func topTwoJournalLogits(logits []float64) (top, runner int, gap float64) {
	top = 0
	for index := 1; index < len(logits); index++ {
		if logits[index] > logits[top] {
			top = index
		}
	}
	runner = -1
	for index := range logits {
		if index != top && (runner == -1 || logits[index] > logits[runner]) {
			runner = index
		}
	}
	return top, runner, logits[top] - logits[runner]
}
