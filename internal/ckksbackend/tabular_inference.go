package ckksbackend

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"time"

	"github.com/tuneinsight/lattigo/v6/core/rlwe"
)

// CKKSTabularInferenceConfig controls generic tabular encrypted inference.
type CKKSTabularInferenceConfig struct {
	ModelPath        string
	TestPath         string
	DatasetID        string
	ModelID          string
	MaxRows          int
	EvaluationMode   string
	ScoreAbsErrorCap float64
	ScoreRelErrorCap float64
}

// CKKSTabularInferenceRecord stores one generic tabular encrypted inference record.
type CKKSTabularInferenceRecord struct {
	RowID int
	Label int

	PlainZ         float64
	CKKSZ          float64
	ZError         float64
	PlainY         float64
	CKKSY          float64
	YError         float64
	ErrorBudget    float64
	ErrorUsage     float64
	ErrorViolation bool

	PlainDecision bool
	CKKSDecision  bool
	DecisionFlip  bool

	PlainCorrect bool
	CKKSCorrect  bool

	EncodeEncryptMS  float64
	ModelEvalMS      float64
	PolynomialEvalMS float64
	EvalOnlyMS       float64
	DecryptDecodeMS  float64
	TotalEvalMS      float64

	InitialLevel int
	ZLevel       int
	YLevel       int
	ZDegree      int
	YDegree      int
}

// CKKSTabularInferenceSummary stores aggregate generic tabular inference results.
type CKKSTabularInferenceSummary struct {
	DatasetID      string
	DatasetName    string
	ModelID        string
	ModelType      string
	TrainSamples   int
	TestSamples    int
	EvaluatedRows  int
	InputDim       int
	EvaluationMode string

	PlainAccuracy     float64
	CKKSAccuracy      float64
	DecisionMatchRate float64
	DecisionFlips     int

	ScoreAbsErrorCap     float64
	ScoreRelErrorCap     float64
	ScoreErrorViolations int
	MaxYError            float64
	MeanYError           float64
	MaxErrorUsage        float64
	MeanErrorUsage       float64

	MeanEncodeEncryptMS float64
	MeanModelEvalMS     float64
	MeanPolynomialMS    float64
	MeanEvalOnlyMS      float64
	MeanDecryptDecodeMS float64
	MeanTotalEvalMS     float64
	MedianTotalEvalMS   float64
	P95TotalEvalMS      float64

	InitialLevel    int
	FinalYLevel     int
	LogDefaultScale int
	MaxSlots        int
}

type tabularModelArtifact struct {
	DatasetID    string `json:"dataset_id"`
	DatasetName  string `json:"dataset_name"`
	ModelID      string `json:"model_id"`
	ModelType    string `json:"model_type"`
	TrainSamples int    `json:"train_samples"`
	TestSamples  int    `json:"test_samples"`
	InputDim     int    `json:"input_dim"`

	ScaledModelForCKKS tabularScaledModel `json:"scaled_model_for_ckks"`
}

type tabularScaledModel struct {
	Weights []float64 `json:"weights"`
	Bias    float64   `json:"bias"`

	HiddenWeights [][]float64 `json:"hidden_weights"`
	HiddenBias    []float64   `json:"hidden_bias"`
	OutputWeights []float64   `json:"output_weights"`
	OutputBias    float64     `json:"output_bias"`
}

type tabularTestRow struct {
	RowID         int
	Label         int
	Features      []float64
	PlainZ        float64
	PlainY        float64
	PlainDecision bool
}

type tabularModelEvalResult struct {
	ZCipher     *rlwe.Ciphertext
	ModelEvalMS float64
}

// DefaultCKKSTabularInferenceConfig returns default generic tabular config.
func DefaultCKKSTabularInferenceConfig(datasetID string, modelID string) CKKSTabularInferenceConfig {
	modelPath := fmt.Sprintf("datasets/tabular_suite/%s/%s/model.json", datasetID, modelID)
	testPath := fmt.Sprintf("datasets/tabular_suite/%s/%s/test.csv", datasetID, modelID)

	return CKKSTabularInferenceConfig{
		ModelPath:        modelPath,
		TestPath:         testPath,
		DatasetID:        datasetID,
		ModelID:          modelID,
		MaxRows:          0,
		EvaluationMode:   CKKSEvaluationModeRescale,
		ScoreAbsErrorCap: 1e-3,
		ScoreRelErrorCap: 1e-2,
	}
}

// RunCKKSTabularInference evaluates a generic exported tabular workload over CKKS.
func (c Context) RunCKKSTabularInference(
	config CKKSTabularInferenceConfig,
) ([]CKKSTabularInferenceRecord, CKKSTabularInferenceSummary, error) {
	if config.ScoreAbsErrorCap <= 0 && config.ScoreRelErrorCap <= 0 {
		return nil, CKKSTabularInferenceSummary{}, fmt.Errorf("at least one score error cap must be positive")
	}

	normalizedMode, err := normalizeCKKSEvaluationMode(config.EvaluationMode)
	if err != nil {
		return nil, CKKSTabularInferenceSummary{}, err
	}

	model, err := loadTabularModelArtifact(config.ModelPath)
	if err != nil {
		return nil, CKKSTabularInferenceSummary{}, err
	}

	if model.InputDim <= 0 {
		return nil, CKKSTabularInferenceSummary{}, fmt.Errorf("invalid input_dim %d", model.InputDim)
	}

	rows, err := loadTabularTestRows(config.TestPath, model.InputDim)
	if err != nil {
		return nil, CKKSTabularInferenceSummary{}, err
	}

	if config.MaxRows > 0 && config.MaxRows < len(rows) {
		rows = rows[:config.MaxRows]
	}

	if len(rows) == 0 {
		return nil, CKKSTabularInferenceSummary{}, fmt.Errorf("no tabular test rows selected")
	}

	runtimeState, err := c.newCKKSTimingRuntime()
	if err != nil {
		return nil, CKKSTabularInferenceSummary{}, fmt.Errorf("create CKKS runtime: %w", err)
	}

	records := make([]CKKSTabularInferenceRecord, 0, len(rows))

	for _, row := range rows {
		record, err := c.runTabularTimedInference(
			runtimeState,
			row,
			model,
			normalizedMode,
			config.ScoreAbsErrorCap,
			config.ScoreRelErrorCap,
		)
		if err != nil {
			return nil, CKKSTabularInferenceSummary{}, fmt.Errorf("tabular row %d: %w", row.RowID, err)
		}

		records = append(records, record)
	}

	summary := summarizeTabularInference(config, normalizedMode, model, c, records)

	return records, summary, nil
}

func (c Context) runTabularTimedInference(
	runtimeState ckksTimingRuntime,
	row tabularTestRow,
	model tabularModelArtifact,
	evaluationMode string,
	scoreAbsErrorCap float64,
	scoreRelErrorCap float64,
) (CKKSTabularInferenceRecord, error) {
	totalStart := time.Now()

	encodeEncryptStart := time.Now()

	cipherInputs := make([]*rlwe.Ciphertext, 0, len(row.Features))
	for _, feature := range row.Features {
		ct, err := c.encryptSingleFeature(runtimeState.encoder, runtimeState.encryptor, feature)
		if err != nil {
			return CKKSTabularInferenceRecord{}, fmt.Errorf("encrypt feature: %w", err)
		}

		cipherInputs = append(cipherInputs, ct)
	}

	encodeEncryptMS := durationMS(time.Since(encodeEncryptStart))

	modelResult, err := c.evalTabularModel(runtimeState, cipherInputs, model, evaluationMode)
	if err != nil {
		return CKKSTabularInferenceRecord{}, fmt.Errorf("evaluate tabular model: %w", err)
	}

	polynomialResult, err := c.evalTimedPolynomial(runtimeState, modelResult.ZCipher, evaluationMode)
	if err != nil {
		return CKKSTabularInferenceRecord{}, fmt.Errorf("evaluate polynomial score: %w", err)
	}

	evalOnlyMS := modelResult.ModelEvalMS + polynomialResult.PolynomialEvalMS

	decryptStart := time.Now()

	zDecoded, err := c.decryptFirstSlot(runtimeState.encoder, runtimeState.decryptor, modelResult.ZCipher)
	if err != nil {
		return CKKSTabularInferenceRecord{}, fmt.Errorf("decrypt z: %w", err)
	}

	yDecoded, err := c.decryptFirstSlot(runtimeState.encoder, runtimeState.decryptor, polynomialResult.YCipher)
	if err != nil {
		return CKKSTabularInferenceRecord{}, fmt.Errorf("decrypt y: %w", err)
	}

	decryptDecodeMS := durationMS(time.Since(decryptStart))
	totalEvalMS := durationMS(time.Since(totalStart))

	ckksDecision := yDecoded >= 0.5
	plainCorrect := row.PlainDecision == labelToDecision(row.Label)
	ckksCorrect := ckksDecision == labelToDecision(row.Label)

	yError := math.Abs(yDecoded - row.PlainY)
	errorBudget := scoreErrorBudget(row.PlainY, scoreAbsErrorCap, scoreRelErrorCap)

	errorUsage := 0.0
	if errorBudget > 0 {
		errorUsage = yError / errorBudget
	}

	return CKKSTabularInferenceRecord{
		RowID: row.RowID,
		Label: row.Label,

		PlainZ:         row.PlainZ,
		CKKSZ:          zDecoded,
		ZError:         math.Abs(zDecoded - row.PlainZ),
		PlainY:         row.PlainY,
		CKKSY:          yDecoded,
		YError:         yError,
		ErrorBudget:    errorBudget,
		ErrorUsage:     errorUsage,
		ErrorViolation: yError > errorBudget,

		PlainDecision: row.PlainDecision,
		CKKSDecision:  ckksDecision,
		DecisionFlip:  row.PlainDecision != ckksDecision,

		PlainCorrect: plainCorrect,
		CKKSCorrect:  ckksCorrect,

		EncodeEncryptMS:  encodeEncryptMS,
		ModelEvalMS:      modelResult.ModelEvalMS,
		PolynomialEvalMS: polynomialResult.PolynomialEvalMS,
		EvalOnlyMS:       evalOnlyMS,
		DecryptDecodeMS:  decryptDecodeMS,
		TotalEvalMS:      totalEvalMS,

		InitialLevel: c.MaxLevel(),
		ZLevel:       modelResult.ZCipher.Level(),
		YLevel:       polynomialResult.YCipher.Level(),
		ZDegree:      modelResult.ZCipher.Degree(),
		YDegree:      polynomialResult.YCipher.Degree(),
	}, nil
}

func (c Context) evalTabularModel(
	runtimeState ckksTimingRuntime,
	inputs []*rlwe.Ciphertext,
	model tabularModelArtifact,
	evaluationMode string,
) (tabularModelEvalResult, error) {
	switch model.ModelType {
	case "linear_poly3":
		return c.evalTabularLinearModel(runtimeState, inputs, model.ScaledModelForCKKS.Weights, model.ScaledModelForCKKS.Bias)
	case "mlp_square_poly3":
		return c.evalTabularSquareMLPModel(runtimeState, inputs, model.ScaledModelForCKKS, evaluationMode)
	default:
		return tabularModelEvalResult{}, fmt.Errorf("unsupported tabular model_type %q", model.ModelType)
	}
}

func (c Context) evalTabularLinearModel(
	runtimeState ckksTimingRuntime,
	inputs []*rlwe.Ciphertext,
	weights []float64,
	bias float64,
) (tabularModelEvalResult, error) {
	start := time.Now()

	zCipher, err := c.evalTabularWeightedSum(runtimeState, inputs, weights, bias)
	if err != nil {
		return tabularModelEvalResult{}, err
	}

	return tabularModelEvalResult{
		ZCipher:     zCipher,
		ModelEvalMS: durationMS(time.Since(start)),
	}, nil
}

func (c Context) evalTabularSquareMLPModel(
	runtimeState ckksTimingRuntime,
	inputs []*rlwe.Ciphertext,
	model tabularScaledModel,
	evaluationMode string,
) (tabularModelEvalResult, error) {
	start := time.Now()

	if len(model.HiddenWeights) == 0 {
		return tabularModelEvalResult{}, fmt.Errorf("MLP model has no hidden units")
	}

	if len(model.HiddenBias) != len(model.HiddenWeights) {
		return tabularModelEvalResult{}, fmt.Errorf("hidden bias count does not match hidden weight count")
	}

	if len(model.OutputWeights) != len(model.HiddenWeights) {
		return tabularModelEvalResult{}, fmt.Errorf("output weight count does not match hidden unit count")
	}

	hiddenCiphertexts := make([]*rlwe.Ciphertext, 0, len(model.HiddenWeights))

	for hiddenIndex, weights := range model.HiddenWeights {
		activationCipher, err := c.evalTabularWeightedSum(runtimeState, inputs, weights, model.HiddenBias[hiddenIndex])
		if err != nil {
			return tabularModelEvalResult{}, fmt.Errorf("hidden unit %d weighted sum: %w", hiddenIndex, err)
		}

		squaredCipher, err := c.squareTabularCiphertext(runtimeState, activationCipher, evaluationMode)
		if err != nil {
			return tabularModelEvalResult{}, fmt.Errorf("hidden unit %d square activation: %w", hiddenIndex, err)
		}

		hiddenCiphertexts = append(hiddenCiphertexts, squaredCipher)
	}

	zCipher, err := c.evalTabularWeightedSum(runtimeState, hiddenCiphertexts, model.OutputWeights, model.OutputBias)
	if err != nil {
		return tabularModelEvalResult{}, fmt.Errorf("output weighted sum: %w", err)
	}

	return tabularModelEvalResult{
		ZCipher:     zCipher,
		ModelEvalMS: durationMS(time.Since(start)),
	}, nil
}

func (c Context) evalTabularWeightedSum(
	runtimeState ckksTimingRuntime,
	inputs []*rlwe.Ciphertext,
	weights []float64,
	bias float64,
) (*rlwe.Ciphertext, error) {
	if len(inputs) != len(weights) {
		return nil, fmt.Errorf("input count %d does not match weight count %d", len(inputs), len(weights))
	}

	var acc *rlwe.Ciphertext

	for i, input := range inputs {
		term, err := runtimeState.evaluator.MulNew(input, weights[i])
		if err != nil {
			return nil, fmt.Errorf("multiply input %d by weight: %w", i, err)
		}

		if acc == nil {
			acc = term
			continue
		}

		targetLevel := acc.Level()
		termAligned := term

		if term.Level() != targetLevel {
			var err error
			termAligned, err = alignCiphertextToLevel(runtimeState.evaluator, term, targetLevel)
			if err != nil {
				return nil, fmt.Errorf("align weighted input %d: %w", i, err)
			}
		}

		if err := runtimeState.evaluator.Add(acc, termAligned, acc); err != nil {
			return nil, fmt.Errorf("add weighted input %d: %w", i, err)
		}
	}

	if acc == nil {
		return nil, fmt.Errorf("no weighted sum accumulator")
	}

	if bias != 0 {
		biasPlaintext, err := c.encodeReplicatedPlaintextAtLevel(runtimeState.encoder, bias, acc.Level())
		if err != nil {
			return nil, fmt.Errorf("encode weighted sum bias plaintext: %w", err)
		}

		zCipher, err := runtimeState.evaluator.AddNew(acc, biasPlaintext)
		if err != nil {
			return nil, fmt.Errorf("add weighted sum bias: %w", err)
		}

		return zCipher, nil
	}

	return acc, nil
}

func (c Context) squareTabularCiphertext(
	runtimeState ckksTimingRuntime,
	input *rlwe.Ciphertext,
	evaluationMode string,
) (*rlwe.Ciphertext, error) {
	squared, err := runtimeState.evaluator.MulNew(input, input)
	if err != nil {
		return nil, fmt.Errorf("multiply ciphertext by itself: %w", err)
	}

	squared, err = runtimeState.evaluator.RelinearizeNew(squared)
	if err != nil {
		return nil, fmt.Errorf("relinearize square: %w", err)
	}

	if evaluationMode == CKKSEvaluationModeRescale {
		if err := safeRescaleTo(runtimeState.evaluator, squared, c.Params.DefaultScale(), squared); err != nil {
			return nil, fmt.Errorf("rescale square: %w", err)
		}
	}

	return squared, nil
}

func loadTabularModelArtifact(path string) (tabularModelArtifact, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return tabularModelArtifact{}, fmt.Errorf("read tabular model artifact: %w", err)
	}

	var model tabularModelArtifact
	if err := json.Unmarshal(data, &model); err != nil {
		return tabularModelArtifact{}, fmt.Errorf("parse tabular model artifact: %w", err)
	}

	return model, nil
}

func loadTabularTestRows(path string, inputDim int) ([]tabularTestRow, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("open tabular test csv: %w", err)
	}
	defer f.Close()

	reader := csv.NewReader(f)

	records, err := reader.ReadAll()
	if err != nil {
		return nil, fmt.Errorf("read tabular test csv: %w", err)
	}

	if len(records) < 2 {
		return nil, fmt.Errorf("tabular test csv has no data rows")
	}

	header := make(map[string]int)
	for i, name := range records[0] {
		header[name] = i
	}

	rows := make([]tabularTestRow, 0, len(records)-1)

	for rowIndex, record := range records[1:] {
		row, err := parseTabularTestRow(rowIndex+2, header, record, inputDim)
		if err != nil {
			return nil, err
		}

		rows = append(rows, row)
	}

	return rows, nil
}

func parseTabularTestRow(
	csvRowNumber int,
	header map[string]int,
	record []string,
	inputDim int,
) (tabularTestRow, error) {
	rowID, err := parseRequiredIntField(header, record, "row_id")
	if err != nil {
		return tabularTestRow{}, fmt.Errorf("csv row %d row_id: %w", csvRowNumber, err)
	}

	label, err := parseRequiredIntField(header, record, "label")
	if err != nil {
		return tabularTestRow{}, fmt.Errorf("csv row %d label: %w", csvRowNumber, err)
	}

	plainZ, err := parseRequiredFloatField(header, record, "scaled_logit")
	if err != nil {
		return tabularTestRow{}, fmt.Errorf("csv row %d scaled_logit: %w", csvRowNumber, err)
	}

	plainY, err := parseRequiredFloatField(header, record, "polynomial_score")
	if err != nil {
		return tabularTestRow{}, fmt.Errorf("csv row %d polynomial_score: %w", csvRowNumber, err)
	}

	plainDecision, err := parseRequiredBoolField(header, record, "plaintext_decision")
	if err != nil {
		return tabularTestRow{}, fmt.Errorf("csv row %d plaintext_decision: %w", csvRowNumber, err)
	}

	features := make([]float64, 0, inputDim)
	for i := 0; i < inputDim; i++ {
		fieldName := fmt.Sprintf("x_%d", i)
		value, err := parseRequiredFloatField(header, record, fieldName)
		if err != nil {
			return tabularTestRow{}, fmt.Errorf("csv row %d %s: %w", csvRowNumber, fieldName, err)
		}

		features = append(features, value)
	}

	return tabularTestRow{
		RowID:         rowID,
		Label:         label,
		Features:      features,
		PlainZ:        plainZ,
		PlainY:        plainY,
		PlainDecision: plainDecision,
	}, nil
}

func summarizeTabularInference(
	config CKKSTabularInferenceConfig,
	normalizedMode string,
	model tabularModelArtifact,
	context Context,
	records []CKKSTabularInferenceRecord,
) CKKSTabularInferenceSummary {
	totalTimes := make([]float64, 0, len(records))

	plainCorrect := 0
	ckksCorrect := 0
	decisionFlips := 0
	errorViolations := 0

	maxYError := 0.0
	sumYError := 0.0
	maxErrorUsage := 0.0
	sumErrorUsage := 0.0

	sumEncodeEncrypt := 0.0
	sumModelEval := 0.0
	sumPolynomial := 0.0
	sumEvalOnly := 0.0
	sumDecryptDecode := 0.0
	sumTotal := 0.0

	finalYLevel := 0

	for _, record := range records {
		totalTimes = append(totalTimes, record.TotalEvalMS)

		if record.PlainCorrect {
			plainCorrect++
		}

		if record.CKKSCorrect {
			ckksCorrect++
		}

		if record.DecisionFlip {
			decisionFlips++
		}

		if record.ErrorViolation {
			errorViolations++
		}

		maxYError = math.Max(maxYError, record.YError)
		sumYError += record.YError

		maxErrorUsage = math.Max(maxErrorUsage, record.ErrorUsage)
		sumErrorUsage += record.ErrorUsage

		sumEncodeEncrypt += record.EncodeEncryptMS
		sumModelEval += record.ModelEvalMS
		sumPolynomial += record.PolynomialEvalMS
		sumEvalOnly += record.EvalOnlyMS
		sumDecryptDecode += record.DecryptDecodeMS
		sumTotal += record.TotalEvalMS

		finalYLevel = record.YLevel
	}

	count := float64(len(records))

	return CKKSTabularInferenceSummary{
		DatasetID:      model.DatasetID,
		DatasetName:    model.DatasetName,
		ModelID:        model.ModelID,
		ModelType:      model.ModelType,
		TrainSamples:   model.TrainSamples,
		TestSamples:    model.TestSamples,
		EvaluatedRows:  len(records),
		InputDim:       model.InputDim,
		EvaluationMode: normalizedMode,

		PlainAccuracy:     float64(plainCorrect) / count,
		CKKSAccuracy:      float64(ckksCorrect) / count,
		DecisionMatchRate: 1.0 - float64(decisionFlips)/count,
		DecisionFlips:     decisionFlips,

		ScoreAbsErrorCap:     config.ScoreAbsErrorCap,
		ScoreRelErrorCap:     config.ScoreRelErrorCap,
		ScoreErrorViolations: errorViolations,
		MaxYError:            maxYError,
		MeanYError:           sumYError / count,
		MaxErrorUsage:        maxErrorUsage,
		MeanErrorUsage:       sumErrorUsage / count,

		MeanEncodeEncryptMS: sumEncodeEncrypt / count,
		MeanModelEvalMS:     sumModelEval / count,
		MeanPolynomialMS:    sumPolynomial / count,
		MeanEvalOnlyMS:      sumEvalOnly / count,
		MeanDecryptDecodeMS: sumDecryptDecode / count,
		MeanTotalEvalMS:     sumTotal / count,
		MedianTotalEvalMS:   wdbcPercentile(totalTimes, 0.50),
		P95TotalEvalMS:      wdbcPercentile(totalTimes, 0.95),

		InitialLevel:    context.MaxLevel(),
		FinalYLevel:     finalYLevel,
		LogDefaultScale: context.LogDefaultScale(),
		MaxSlots:        context.MaxSlots(),
	}
}
