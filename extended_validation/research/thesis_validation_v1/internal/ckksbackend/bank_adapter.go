package ckksbackend

import (
	"fmt"
	"github.com/hasslelee/flipguard/internal/bankadapter"
	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
	"runtime"
	"time"
)

func (c Context) RunCKKSBankInference(
	config JournalMNISTMulticlassConfig,
) ([]JournalMNISTMulticlassRecord, JournalMNISTMulticlassSummary, error) {
	modelArtifact, err := bankadapter.LoadModelArtifact(config.ModelPath)
	if err != nil {
		return nil, JournalMNISTMulticlassSummary{}, err
	}
	rows, err := bankadapter.LoadPartitionCSV(config.DataPath, config.Role)
	if err != nil {
		return nil, JournalMNISTMulticlassSummary{}, err
	}
	if len(config.SelectedRowIDs) > 0 {
		byID := make(map[int]bankadapter.PartitionRow, len(rows))
		for _, row := range rows {
			byID[row.RowID] = row
		}
		selected := make([]bankadapter.PartitionRow, 0, len(config.SelectedRowIDs))
		seen := make(map[int]struct{}, len(config.SelectedRowIDs))
		for _, rowID := range config.SelectedRowIDs {
			if _, duplicate := seen[rowID]; duplicate {
				return nil, JournalMNISTMulticlassSummary{}, fmt.Errorf(
					"duplicate selected MNIST row_id %d", rowID,
				)
			}
			seen[rowID] = struct{}{}
			row, ok := byID[rowID]
			if !ok {
				return nil, JournalMNISTMulticlassSummary{}, fmt.Errorf(
					"selected MNIST row_id %d is outside verified partition", rowID,
				)
			}
			selected = append(selected, row)
		}
		rows = selected
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
	evalStart := time.Now()
	var output []*rlwe.Ciphertext
	stats := journalMNISTExecutionStats{}
	switch modelArtifact.ModelType {
	case bankadapter.MLPModelType:
		encodeStart := time.Now()
		inputs, encryptErr := c.encryptBankFeatureVectors(runtimeState, rows)
		stats.EncodeDuration = time.Since(encodeStart)
		stats.InputCiphertexts = len(inputs)
		if encryptErr != nil {
			return nil, JournalMNISTMulticlassSummary{}, encryptErr
		}
		output, err = c.evaluateBankMLP(runtimeState, modelArtifact, inputs)
		inputs = nil
	default:
		err = fmt.Errorf("unsupported journal multiclass model %q", modelArtifact.ModelType)
	}
	if err != nil {
		return nil, JournalMNISTMulticlassSummary{}, err
	}
	evalWall := time.Since(evalStart)
	encodeMS := durationMS(stats.EncodeDuration)
	adapterIOMS := durationMS(stats.AdapterIODuration)
	evalMS := durationMS(evalWall - stats.EncodeDuration - stats.AdapterIODuration)
	if evalMS < 0 {
		evalMS = 0
	}
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
		approximate := make([]float64, bankadapter.ClassCount)
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
		ExecutionAdapter: "hediff_bank_exact_two_logit_adapter_v1",
		DatasetID:        modelArtifact.DatasetID, ModelID: modelArtifact.ModelID,
		ModelType: modelArtifact.ModelType, Role: config.Role,
		EvaluatedRows: len(rows), ClassCount: bankadapter.ClassCount,
		CryptoSetupMS: setupMS, EncodeEncryptMS: encodeMS,
		EvaluationOnlyMS: evalMS, AdapterIOMS: adapterIOMS, DecryptDecodeMS: decodeMS, TotalMS: totalMS,
		AmortizedMS: totalMS / float64(len(rows)), InputCiphertexts: stats.InputCiphertexts,
		OutputCiphertexts: len(output), InitialLevel: c.MaxLevel(), FinalLevel: finalLevel,
		RequiredSlots: len(rows), AvailableSlots: c.Params.MaxSlots(), ArgmaxFlips: flips,
		SpoolBytes: stats.SpoolBytes,
	}, nil
}

func (c Context) encryptBankFeatureVectors(runtimeState ckksTimingRuntime, rows []bankadapter.PartitionRow) ([]*rlwe.Ciphertext, error) {
	inputs := make([]*rlwe.Ciphertext, bankadapter.PixelCount)
	values := make([]complex128, c.Params.MaxSlots())
	for pixel := 0; pixel < bankadapter.PixelCount; pixel++ {
		for index := range values {
			values[index] = 0
		}
		for rowIndex, row := range rows {
			values[rowIndex] = complex(row.Pixels[pixel], 0)
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

func (c Context) evaluateBankMLP(runtimeState ckksTimingRuntime, model bankadapter.ModelArtifact, inputs []*rlwe.Ciphertext) ([]*rlwe.Ciphertext, error) {
	hidden := make([]*rlwe.Ciphertext, bankadapter.MLPHidden)
	weights := make([]float64, bankadapter.PixelCount)
	for unit := 0; unit < bankadapter.MLPHidden; unit++ {
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
	outputs := make([]*rlwe.Ciphertext, bankadapter.ClassCount)
	weights = make([]float64, bankadapter.MLPHidden)
	for classIndex := 0; classIndex < bankadapter.ClassCount; classIndex++ {
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
