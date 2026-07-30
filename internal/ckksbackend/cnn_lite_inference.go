package ckksbackend

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"strconv"
	"time"

	"github.com/hasslelee/flipguard/internal/benchmarks"
	"github.com/tuneinsight/lattigo/v6/core/rlwe"
)

type CKKSCNNLiteConfig struct {
	ModelPath string
	DataPath  string
	MaxRows   int
}

type CKKSCNNLiteRecord struct {
	RowID           int    `json:"row_id"`
	SampleID        string `json:"sample_id"`
	SourcePartition string `json:"source_partition"`
	DigitLabel      int    `json:"digit_label"`

	PlainScore float64 `json:"plain_score"`
	CKKSScore  float64 `json:"ckks_score"`
	AbsError   float64 `json:"abs_error"`

	PlainDecision bool `json:"plain_decision"`
	CKKSDecision  bool `json:"ckks_decision"`
	DecisionFlip  bool `json:"decision_flip"`

	EncodeEncryptMS float64 `json:"encode_encrypt_ms"`
	EvalOnlyMS      float64 `json:"eval_only_ms"`
	DecryptDecodeMS float64 `json:"decrypt_decode_ms"`
	TotalEvalMS     float64 `json:"total_eval_ms"`

	InitialLevel int `json:"initial_level"`
	FinalLevel   int `json:"final_level"`
	FinalDegree  int `json:"final_degree"`
}

type cnnLiteModelArtifact struct {
	SchemaVersion     string  `json:"schema_version"`
	DatasetID         string  `json:"dataset_id"`
	ModelID           string  `json:"model_id"`
	ModelType         string  `json:"model_type"`
	GraphAdapterID    string  `json:"graph_adapter_id"`
	InputDim          int     `json:"input_dim"`
	DecisionThreshold float64 `json:"decision_threshold"`
	PackingScope      string  `json:"packing_scope"`

	LearnedParameters struct {
		ConvolutionFilters [benchmarks.CNNLiteFilters]struct {
			Weights [benchmarks.CNNLiteFilterSide][benchmarks.CNNLiteFilterSide]float64 `json:"weights"`
			Bias    float64                                                             `json:"bias"`
		} `json:"convolution_filters"`
		OutputWeights [benchmarks.CNNLiteFilters][benchmarks.CNNLiteConvSide][benchmarks.CNNLiteConvSide]float64 `json:"output_weights"`
		OutputBias    float64                                                                                    `json:"output_bias"`
	} `json:"learned_parameters"`
}

type cnnLiteRow struct {
	RowID           int
	SampleID        string
	SourcePartition string
	DigitLabel      int
	Pixels          [benchmarks.CNNLiteInputSide][benchmarks.CNNLiteInputSide]float64
	PlainScore      float64
	PlainDecision   bool
}

func (model cnnLiteModelArtifact) benchmarkModel() benchmarks.CNNLiteSquareModel {
	converted := benchmarks.CNNLiteSquareModel{
		OutputWeights: model.LearnedParameters.OutputWeights,
		OutputBias:    model.LearnedParameters.OutputBias,
	}
	for filter := 0; filter < benchmarks.CNNLiteFilters; filter++ {
		converted.FilterWeights[filter] =
			model.LearnedParameters.ConvolutionFilters[filter].Weights
		converted.FilterBias[filter] =
			model.LearnedParameters.ConvolutionFilters[filter].Bias
	}
	return converted
}

func (c Context) RunCKKSCNNLiteInference(
	config CKKSCNNLiteConfig,
) ([]CKKSCNNLiteRecord, error) {
	model, err := loadCNNLiteModel(config.ModelPath)
	if err != nil {
		return nil, err
	}
	rows, err := loadCNNLiteRows(
		config.DataPath,
		model,
	)
	if err != nil {
		return nil, err
	}
	if len(rows) == 0 {
		return nil, fmt.Errorf("CNN-lite data has no rows")
	}
	if config.MaxRows > 0 && config.MaxRows < len(rows) {
		rows = rows[:config.MaxRows]
	}

	runtimeState, err := c.newCKKSTimingRuntime()
	if err != nil {
		return nil, fmt.Errorf("create CNN-lite CKKS runtime: %w", err)
	}
	records := make([]CKKSCNNLiteRecord, 0, len(rows))
	for _, row := range rows {
		record, err := c.runCNNLiteSample(
			runtimeState,
			row,
			model,
		)
		if err != nil {
			return nil, fmt.Errorf(
				"CNN-lite row %d: %w",
				row.RowID,
				err,
			)
		}
		records = append(records, record)
	}
	return records, nil
}

func (c Context) runCNNLiteSample(
	runtimeState ckksTimingRuntime,
	row cnnLiteRow,
	model cnnLiteModelArtifact,
) (CKKSCNNLiteRecord, error) {
	totalStart := time.Now()
	encryptStart := time.Now()
	var inputs [benchmarks.CNNLiteInputSide][benchmarks.CNNLiteInputSide]*rlwe.Ciphertext
	for inputRow := 0; inputRow < benchmarks.CNNLiteInputSide; inputRow++ {
		for column := 0; column < benchmarks.CNNLiteInputSide; column++ {
			ciphertext, err := c.encryptSingleFeature(
				runtimeState.encoder,
				runtimeState.encryptor,
				row.Pixels[inputRow][column],
			)
			if err != nil {
				return CKKSCNNLiteRecord{}, fmt.Errorf(
					"encrypt pool%d%d: %w",
					inputRow,
					column,
					err,
				)
			}
			inputs[inputRow][column] = ciphertext
		}
	}
	encodeEncryptMS := durationMS(time.Since(encryptStart))

	evalStart := time.Now()
	squared := make(
		[]*rlwe.Ciphertext,
		0,
		benchmarks.CNNLiteFilters*
			benchmarks.CNNLiteConvSide*
			benchmarks.CNNLiteConvSide,
	)
	outputWeights := make(
		[]float64,
		0,
		cap(squared),
	)
	for filter := 0; filter < benchmarks.CNNLiteFilters; filter++ {
		filterArtifact :=
			model.LearnedParameters.ConvolutionFilters[filter]
		for convRow := 0; convRow < benchmarks.CNNLiteConvSide; convRow++ {
			for column := 0; column < benchmarks.CNNLiteConvSide; column++ {
				convInputs := make([]*rlwe.Ciphertext, 0, 4)
				weights := make([]float64, 0, 4)
				for kernelRow := 0; kernelRow < benchmarks.CNNLiteFilterSide; kernelRow++ {
					for kernelColumn := 0; kernelColumn < benchmarks.CNNLiteFilterSide; kernelColumn++ {
						convInputs = append(
							convInputs,
							inputs[convRow+kernelRow][column+kernelColumn],
						)
						weights = append(
							weights,
							filterArtifact.Weights[kernelRow][kernelColumn],
						)
					}
				}
				hidden, err := c.evalTabularWeightedSum(
					runtimeState,
					convInputs,
					weights,
					filterArtifact.Bias,
				)
				if err != nil {
					return CKKSCNNLiteRecord{}, fmt.Errorf(
						"convolution filter=%d row=%d column=%d: %w",
						filter,
						convRow,
						column,
						err,
					)
				}
				activation, err := c.squareTabularCiphertext(
					runtimeState,
					hidden,
					CKKSEvaluationModeRescale,
				)
				if err != nil {
					return CKKSCNNLiteRecord{}, fmt.Errorf(
						"square filter=%d row=%d column=%d: %w",
						filter,
						convRow,
						column,
						err,
					)
				}
				squared = append(squared, activation)
				outputWeights = append(
					outputWeights,
					model.LearnedParameters.OutputWeights[filter][convRow][column],
				)
			}
		}
	}
	scoreCipher, err := c.evalTabularWeightedSum(
		runtimeState,
		squared,
		outputWeights,
		model.LearnedParameters.OutputBias,
	)
	if err != nil {
		return CKKSCNNLiteRecord{}, fmt.Errorf(
			"linear output head: %w",
			err,
		)
	}
	evalOnlyMS := durationMS(time.Since(evalStart))

	decryptStart := time.Now()
	decoded, err := c.decryptFirstSlot(
		runtimeState.encoder,
		runtimeState.decryptor,
		scoreCipher,
	)
	if err != nil {
		return CKKSCNNLiteRecord{}, fmt.Errorf(
			"decrypt score: %w",
			err,
		)
	}
	decryptDecodeMS := durationMS(time.Since(decryptStart))
	ckksDecision := decoded >= model.DecisionThreshold
	return CKKSCNNLiteRecord{
		RowID:           row.RowID,
		SampleID:        row.SampleID,
		SourcePartition: row.SourcePartition,
		DigitLabel:      row.DigitLabel,
		PlainScore:      row.PlainScore,
		CKKSScore:       decoded,
		AbsError:        math.Abs(decoded - row.PlainScore),
		PlainDecision:   row.PlainDecision,
		CKKSDecision:    ckksDecision,
		DecisionFlip:    row.PlainDecision != ckksDecision,
		EncodeEncryptMS: encodeEncryptMS,
		EvalOnlyMS:      evalOnlyMS,
		DecryptDecodeMS: decryptDecodeMS,
		TotalEvalMS:     durationMS(time.Since(totalStart)),
		InitialLevel:    c.MaxLevel(),
		FinalLevel:      scoreCipher.Level(),
		FinalDegree:     scoreCipher.Degree(),
	}, nil
}

func loadCNNLiteModel(path string) (cnnLiteModelArtifact, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return cnnLiteModelArtifact{}, fmt.Errorf(
			"read CNN-lite model artifact: %w",
			err,
		)
	}
	model := cnnLiteModelArtifact{}
	if err := json.Unmarshal(data, &model); err != nil {
		return cnnLiteModelArtifact{}, fmt.Errorf(
			"parse CNN-lite model artifact: %w",
			err,
		)
	}
	if model.SchemaVersion != "flipguard_mnist_cnn_lite_holdout_v1" ||
		model.DatasetID != "mnist_binary01" ||
		model.ModelID != "cnn_lite_square_binary01" ||
		model.ModelType != "cnn_lite_square_binary01" ||
		model.GraphAdapterID !=
			"mnist_cnn_lite_scalar_replicated_graph_adapter_v1" ||
		model.InputDim != 16 ||
		model.DecisionThreshold != 0 ||
		model.PackingScope !=
			"scalar_replicated_per_ciphertext_v1" {
		return cnnLiteModelArtifact{}, fmt.Errorf(
			"CNN-lite model identity changed",
		)
	}
	converted := model.benchmarkModel()
	graph := benchmarks.NewCNNLiteSquareGraph(converted)
	if err := graph.Validate(); err != nil {
		return cnnLiteModelArtifact{}, fmt.Errorf(
			"validate CNN-lite graph: %w",
			err,
		)
	}
	for _, node := range graph.Nodes() {
		if !finiteCNNLiteValue(node.Const) {
			return cnnLiteModelArtifact{}, fmt.Errorf(
				"CNN-lite model contains non-finite parameter",
			)
		}
	}
	return model, nil
}

func loadCNNLiteRows(
	path string,
	model cnnLiteModelArtifact,
) ([]cnnLiteRow, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("open CNN-lite CSV: %w", err)
	}
	defer file.Close()
	records, err := csv.NewReader(file).ReadAll()
	if err != nil {
		return nil, fmt.Errorf("read CNN-lite CSV: %w", err)
	}
	if len(records) < 2 {
		return nil, fmt.Errorf("CNN-lite CSV has no data rows")
	}
	header := make(map[string]int, len(records[0]))
	for index, name := range records[0] {
		header[name] = index
	}
	rows := make([]cnnLiteRow, 0, len(records)-1)
	benchmarkModel := model.benchmarkModel()
	for rowIndex, record := range records[1:] {
		rowID, err := parseRequiredIntField(
			header,
			record,
			"row_id",
		)
		if err != nil {
			return nil, fmt.Errorf(
				"CNN-lite row %d row_id: %w",
				rowIndex+2,
				err,
			)
		}
		sampleID, err := parseRequiredStringField(
			header,
			record,
			"sample_id",
		)
		if err != nil ||
			sampleID != fmt.Sprintf("mnist_%05d", rowID) {
			return nil, fmt.Errorf(
				"CNN-lite row %d sample identity changed",
				rowIndex+2,
			)
		}
		sourcePartition, err := parseRequiredStringField(
			header,
			record,
			"source_partition",
		)
		if err != nil ||
			(sourcePartition != "train" &&
				sourcePartition != "test") {
			return nil, fmt.Errorf(
				"CNN-lite row %d source partition changed",
				rowIndex+2,
			)
		}
		digitLabel, err := parseRequiredIntField(
			header,
			record,
			"digit_label",
		)
		if err != nil || (digitLabel != 0 && digitLabel != 1) {
			return nil, fmt.Errorf(
				"CNN-lite row %d digit label changed",
				rowIndex+2,
			)
		}
		var pixels [benchmarks.CNNLiteInputSide][benchmarks.CNNLiteInputSide]float64
		for inputRow := 0; inputRow < benchmarks.CNNLiteInputSide; inputRow++ {
			for column := 0; column < benchmarks.CNNLiteInputSide; column++ {
				name := fmt.Sprintf("pool%d%d", inputRow, column)
				value, err := parseRequiredFloatField(
					header,
					record,
					name,
				)
				if err != nil || !finiteCNNLiteValue(value) ||
					value < 0 || value > 1 {
					return nil, fmt.Errorf(
						"CNN-lite row %d invalid %s",
						rowIndex+2,
						name,
					)
				}
				pixels[inputRow][column] = value
			}
		}
		plainScore, err := parseRequiredFloatField(
			header,
			record,
			"plaintext_score",
		)
		if err != nil || !finiteCNNLiteValue(plainScore) {
			return nil, fmt.Errorf(
				"CNN-lite row %d invalid plaintext score",
				rowIndex+2,
			)
		}
		recomputed := benchmarks.CNNLiteSquareScore(
			benchmarks.CNNLiteSquareSample{Pixels: pixels},
			benchmarkModel,
		)
		if math.Abs(plainScore-recomputed) >
			1e-12*math.Max(1, math.Abs(recomputed)) {
			return nil, fmt.Errorf(
				"CNN-lite row %d plaintext score changed",
				rowIndex+2,
			)
		}
		threshold, err := parseRequiredFloatField(
			header,
			record,
			"decision_threshold",
		)
		if err != nil || threshold != model.DecisionThreshold {
			return nil, fmt.Errorf(
				"CNN-lite row %d threshold changed",
				rowIndex+2,
			)
		}
		plainDecision, err := parseRequiredBoolField(
			header,
			record,
			"plaintext_decision",
		)
		if err != nil ||
			plainDecision !=
				(plainScore >= model.DecisionThreshold) {
			return nil, fmt.Errorf(
				"CNN-lite row %d plaintext decision changed",
				rowIndex+2,
			)
		}
		binaryLabel, err := parseRequiredIntField(
			header,
			record,
			"binary_label",
		)
		if err != nil || binaryLabel != digitLabel {
			return nil, fmt.Errorf(
				"CNN-lite row %d binary task changed",
				rowIndex+2,
			)
		}
		marginRaw, err := parseRequiredStringField(
			header,
			record,
			"decision_margin",
		)
		if err != nil {
			return nil, err
		}
		margin, err := strconv.ParseFloat(marginRaw, 64)
		if err != nil ||
			math.Abs(margin-math.Abs(plainScore)) > 1e-15 {
			return nil, fmt.Errorf(
				"CNN-lite row %d margin changed",
				rowIndex+2,
			)
		}
		rows = append(rows, cnnLiteRow{
			RowID:           rowID,
			SampleID:        sampleID,
			SourcePartition: sourcePartition,
			DigitLabel:      digitLabel,
			Pixels:          pixels,
			PlainScore:      plainScore,
			PlainDecision:   plainDecision,
		})
	}
	return rows, nil
}

func finiteCNNLiteValue(value float64) bool {
	return !math.IsNaN(value) && !math.IsInf(value, 0)
}
