package ckksbackend

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// CKKSWDBCInferenceConfig controls WDBC encrypted inference evaluation.
type CKKSWDBCInferenceConfig struct {
	ModelPath        string
	TestPath         string
	MaxRows          int
	EvaluationMode   string
	ScoreAbsErrorCap float64
	ScoreRelErrorCap float64
}

// CKKSWDBCInferenceRecord stores one WDBC encrypted inference record.
type CKKSWDBCInferenceRecord struct {
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
	LinearEvalMS     float64
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

// CKKSWDBCInferenceSummary stores aggregate WDBC encrypted inference results.
type CKKSWDBCInferenceSummary struct {
	Dataset        string
	Model          string
	TestSamples    int
	EvaluatedRows  int
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

	MeanEncodeEncryptMS  float64
	MeanLinearEvalMS     float64
	MeanPolynomialEvalMS float64
	MeanEvalOnlyMS       float64
	MeanDecryptDecodeMS  float64
	MeanTotalEvalMS      float64
	MedianTotalEvalMS    float64
	P95TotalEvalMS       float64

	InitialLevel    int
	FinalYLevel     int
	LogDefaultScale int
	MaxSlots        int
}

// DefaultCKKSWDBCInferenceConfig returns default WDBC inference config.
func DefaultCKKSWDBCInferenceConfig() CKKSWDBCInferenceConfig {
	return CKKSWDBCInferenceConfig{
		ModelPath:        "datasets/wdbc_logreg3/model.json",
		TestPath:         "datasets/wdbc_logreg3/test.csv",
		MaxRows:          0,
		EvaluationMode:   CKKSEvaluationModeRescale,
		ScoreAbsErrorCap: 1e-3,
		ScoreRelErrorCap: 1e-2,
	}
}

type wdbcModelArtifact struct {
	Dataset              string   `json:"dataset"`
	Model                string   `json:"model"`
	SelectedFeatureNames []string `json:"selected_feature_names"`

	ScaledLogitModelForCKKS struct {
		Weights []float64 `json:"weights"`
		Bias    float64   `json:"bias"`
	} `json:"scaled_logit_model_for_ckks"`

	Metrics struct {
		TestSamples                 float64 `json:"test_samples"`
		RawLogisticAccuracy         float64 `json:"raw_logistic_accuracy"`
		RawLogisticF1               float64 `json:"raw_logistic_f1"`
		RawLogisticAUC              float64 `json:"raw_logistic_auc"`
		PolynomialDecisionMatchRate float64 `json:"polynomial_decision_match_rate"`
	} `json:"metrics"`
}

type wdbcTestRow struct {
	RowID         int
	Label         int
	Features      []float64
	PlainZ        float64
	PlainY        float64
	PlainDecision bool
}

// RunCKKSWDBCInference evaluates the WDBC exported model over CKKS.
func (c Context) RunCKKSWDBCInference(
	config CKKSWDBCInferenceConfig,
) ([]CKKSWDBCInferenceRecord, CKKSWDBCInferenceSummary, error) {
	if config.ScoreAbsErrorCap <= 0 && config.ScoreRelErrorCap <= 0 {
		return nil, CKKSWDBCInferenceSummary{}, fmt.Errorf("at least one score error cap must be positive")
	}

	normalizedMode, err := normalizeCKKSEvaluationMode(config.EvaluationMode)
	if err != nil {
		return nil, CKKSWDBCInferenceSummary{}, err
	}

	model, err := loadWDBCModelArtifact(config.ModelPath)
	if err != nil {
		return nil, CKKSWDBCInferenceSummary{}, err
	}

	if len(model.ScaledLogitModelForCKKS.Weights) != 3 {
		return nil, CKKSWDBCInferenceSummary{}, fmt.Errorf("WDBC model must have exactly 3 weights, got %d", len(model.ScaledLogitModelForCKKS.Weights))
	}

	if len(model.SelectedFeatureNames) != 3 {
		return nil, CKKSWDBCInferenceSummary{}, fmt.Errorf("WDBC model must have exactly 3 selected feature names, got %d", len(model.SelectedFeatureNames))
	}

	rows, err := loadWDBCTestRows(config.TestPath, model.SelectedFeatureNames)
	if err != nil {
		return nil, CKKSWDBCInferenceSummary{}, err
	}

	if config.MaxRows > 0 && config.MaxRows < len(rows) {
		rows = rows[:config.MaxRows]
	}

	if len(rows) == 0 {
		return nil, CKKSWDBCInferenceSummary{}, fmt.Errorf("no WDBC test rows selected")
	}

	runtimeState, err := c.newCKKSTimingRuntime()
	if err != nil {
		return nil, CKKSWDBCInferenceSummary{}, fmt.Errorf("create CKKS runtime: %w", err)
	}

	records := make([]CKKSWDBCInferenceRecord, 0, len(rows))

	for _, row := range rows {
		record, err := c.runWDBCTimedInference(
			runtimeState,
			row,
			model.ScaledLogitModelForCKKS.Weights,
			model.ScaledLogitModelForCKKS.Bias,
			normalizedMode,
			config.ScoreAbsErrorCap,
			config.ScoreRelErrorCap,
		)
		if err != nil {
			return nil, CKKSWDBCInferenceSummary{}, fmt.Errorf("WDBC row %d: %w", row.RowID, err)
		}

		records = append(records, record)
	}

	summary := summarizeWDBCInference(config, normalizedMode, model, c, records)

	return records, summary, nil
}

func (c Context) runWDBCTimedInference(
	runtimeState ckksTimingRuntime,
	row wdbcTestRow,
	weights []float64,
	bias float64,
	evaluationMode string,
	scoreAbsErrorCap float64,
	scoreRelErrorCap float64,
) (CKKSWDBCInferenceRecord, error) {
	totalStart := time.Now()

	encodeEncryptStart := time.Now()

	cipherInputs, err := c.encryptWDBCFeatures(runtimeState, row.Features)
	if err != nil {
		return CKKSWDBCInferenceRecord{}, fmt.Errorf("encrypt features: %w", err)
	}

	encodeEncryptMS := durationMS(time.Since(encodeEncryptStart))

	linearResult, err := c.evalWDBCLinear(runtimeState, cipherInputs, weights, bias)
	if err != nil {
		return CKKSWDBCInferenceRecord{}, fmt.Errorf("evaluate linear score: %w", err)
	}

	polynomialResult, err := c.evalTimedPolynomial(runtimeState, linearResult.ZCipher, evaluationMode)
	if err != nil {
		return CKKSWDBCInferenceRecord{}, fmt.Errorf("evaluate polynomial score: %w", err)
	}

	evalOnlyMS := linearResult.LinearEvalMS + polynomialResult.PolynomialEvalMS

	decryptStart := time.Now()

	zDecoded, err := c.decryptFirstSlot(runtimeState.encoder, runtimeState.decryptor, linearResult.ZCipher)
	if err != nil {
		return CKKSWDBCInferenceRecord{}, fmt.Errorf("decrypt z: %w", err)
	}

	yDecoded, err := c.decryptFirstSlot(runtimeState.encoder, runtimeState.decryptor, polynomialResult.YCipher)
	if err != nil {
		return CKKSWDBCInferenceRecord{}, fmt.Errorf("decrypt y: %w", err)
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

	return CKKSWDBCInferenceRecord{
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
		LinearEvalMS:     linearResult.LinearEvalMS,
		PolynomialEvalMS: polynomialResult.PolynomialEvalMS,
		EvalOnlyMS:       evalOnlyMS,
		DecryptDecodeMS:  decryptDecodeMS,
		TotalEvalMS:      totalEvalMS,

		InitialLevel: c.MaxLevel(),
		ZLevel:       linearResult.ZCipher.Level(),
		YLevel:       polynomialResult.YCipher.Level(),
		ZDegree:      linearResult.ZCipher.Degree(),
		YDegree:      polynomialResult.YCipher.Degree(),
	}, nil
}

func (c Context) encryptWDBCFeatures(
	runtimeState ckksTimingRuntime,
	features []float64,
) ([]*rlwe.Ciphertext, error) {
	ciphertexts := make([]*rlwe.Ciphertext, 0, len(features))

	for _, feature := range features {
		ct, err := c.encryptSingleFeature(runtimeState.encoder, runtimeState.encryptor, feature)
		if err != nil {
			return nil, err
		}

		ciphertexts = append(ciphertexts, ct)
	}

	return ciphertexts, nil
}

func (c Context) encryptSingleFeature(
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
		return nil, fmt.Errorf("encode feature: %w", err)
	}

	ct, err := encryptor.EncryptNew(pt)
	if err != nil {
		return nil, fmt.Errorf("encrypt feature: %w", err)
	}

	return ct, nil
}

func (c Context) evalWDBCLinear(
	runtimeState ckksTimingRuntime,
	inputs []*rlwe.Ciphertext,
	weights []float64,
	bias float64,
) (ckksTimedLinearResult, error) {
	if len(inputs) != len(weights) {
		return ckksTimedLinearResult{}, fmt.Errorf("input count %d does not match weight count %d", len(inputs), len(weights))
	}

	start := time.Now()

	var acc *rlwe.Ciphertext

	for i, input := range inputs {
		term, err := runtimeState.evaluator.MulNew(input, weights[i])
		if err != nil {
			return ckksTimedLinearResult{}, fmt.Errorf("multiply feature %d by weight: %w", i, err)
		}

		if acc == nil {
			acc = term
			continue
		}

		if err := runtimeState.evaluator.Add(acc, term, acc); err != nil {
			return ckksTimedLinearResult{}, fmt.Errorf("add weighted feature %d: %w", i, err)
		}
	}

	if acc == nil {
		return ckksTimedLinearResult{}, fmt.Errorf("no linear accumulator")
	}

	if bias != 0 {
		if err := runtimeState.evaluator.Add(acc, bias, acc); err != nil {
			return ckksTimedLinearResult{}, fmt.Errorf("add bias: %w", err)
		}
	}

	return ckksTimedLinearResult{
		ZCipher:      acc,
		LinearEvalMS: durationMS(time.Since(start)),
	}, nil
}

func loadWDBCModelArtifact(path string) (wdbcModelArtifact, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return wdbcModelArtifact{}, fmt.Errorf("read WDBC model artifact: %w", err)
	}

	var model wdbcModelArtifact
	if err := json.Unmarshal(data, &model); err != nil {
		return wdbcModelArtifact{}, fmt.Errorf("parse WDBC model artifact: %w", err)
	}

	return model, nil
}

func loadWDBCTestRows(path string, featureNames []string) ([]wdbcTestRow, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("open WDBC test csv: %w", err)
	}
	defer f.Close()

	reader := csv.NewReader(f)

	records, err := reader.ReadAll()
	if err != nil {
		return nil, fmt.Errorf("read WDBC test csv: %w", err)
	}

	if len(records) < 2 {
		return nil, fmt.Errorf("WDBC test csv has no data rows")
	}

	header := make(map[string]int)
	for i, name := range records[0] {
		header[name] = i
	}

	rows := make([]wdbcTestRow, 0, len(records)-1)

	for rowIndex, record := range records[1:] {
		row, err := parseWDBCTestRow(rowIndex+2, header, record, featureNames)
		if err != nil {
			return nil, err
		}

		rows = append(rows, row)
	}

	return rows, nil
}

func parseWDBCTestRow(
	csvRowNumber int,
	header map[string]int,
	record []string,
	featureNames []string,
) (wdbcTestRow, error) {
	rowID, err := parseRequiredIntField(header, record, "row_id")
	if err != nil {
		return wdbcTestRow{}, fmt.Errorf("csv row %d row_id: %w", csvRowNumber, err)
	}

	label, err := parseRequiredIntField(header, record, "label")
	if err != nil {
		return wdbcTestRow{}, fmt.Errorf("csv row %d label: %w", csvRowNumber, err)
	}

	plainZ, err := parseRequiredFloatField(header, record, "scaled_logit")
	if err != nil {
		return wdbcTestRow{}, fmt.Errorf("csv row %d scaled_logit: %w", csvRowNumber, err)
	}

	plainY, err := parseRequiredFloatField(header, record, "polynomial_score")
	if err != nil {
		return wdbcTestRow{}, fmt.Errorf("csv row %d polynomial_score: %w", csvRowNumber, err)
	}

	plainDecision, err := parseRequiredBoolField(header, record, "plaintext_decision")
	if err != nil {
		return wdbcTestRow{}, fmt.Errorf("csv row %d plaintext_decision: %w", csvRowNumber, err)
	}

	features := make([]float64, 0, len(featureNames))

	for _, featureName := range featureNames {
		fieldName := "std_" + safeWDBCFeatureName(featureName)
		value, err := parseRequiredFloatField(header, record, fieldName)
		if err != nil {
			return wdbcTestRow{}, fmt.Errorf("csv row %d %s: %w", csvRowNumber, fieldName, err)
		}

		features = append(features, value)
	}

	return wdbcTestRow{
		RowID:         rowID,
		Label:         label,
		Features:      features,
		PlainZ:        plainZ,
		PlainY:        plainY,
		PlainDecision: plainDecision,
	}, nil
}

func safeWDBCFeatureName(name string) string {
	name = strings.ReplaceAll(name, " ", "_")
	name = strings.ReplaceAll(name, "/", "_")
	return name
}

func parseRequiredStringField(header map[string]int, record []string, name string) (string, error) {
	index, ok := header[name]
	if !ok {
		return "", fmt.Errorf("missing field %s", name)
	}

	if index < 0 || index >= len(record) {
		return "", fmt.Errorf("field %s index out of range", name)
	}

	value := strings.TrimSpace(record[index])
	if value == "" {
		return "", fmt.Errorf("field %s is empty", name)
	}

	return value, nil
}

func parseRequiredIntField(header map[string]int, record []string, name string) (int, error) {
	value, err := parseRequiredStringField(header, record, name)
	if err != nil {
		return 0, err
	}

	parsed, err := strconv.Atoi(value)
	if err != nil {
		return 0, fmt.Errorf("parse int %q: %w", value, err)
	}

	return parsed, nil
}

func parseRequiredFloatField(header map[string]int, record []string, name string) (float64, error) {
	value, err := parseRequiredStringField(header, record, name)
	if err != nil {
		return 0, err
	}

	parsed, err := strconv.ParseFloat(value, 64)
	if err != nil {
		return 0, fmt.Errorf("parse float %q: %w", value, err)
	}

	return parsed, nil
}

func parseRequiredBoolField(header map[string]int, record []string, name string) (bool, error) {
	value, err := parseRequiredStringField(header, record, name)
	if err != nil {
		return false, err
	}

	parsed, err := strconv.ParseBool(value)
	if err != nil {
		return false, fmt.Errorf("parse bool %q: %w", value, err)
	}

	return parsed, nil
}

func normalizeCKKSEvaluationMode(mode string) (string, error) {
	switch mode {
	case CKKSEvaluationModeNaive, "baseline_non_rescale":
		return CKKSEvaluationModeNaive, nil
	case CKKSEvaluationModeRescale, "rescale_aware":
		return CKKSEvaluationModeRescale, nil
	default:
		return "", fmt.Errorf("unsupported CKKS evaluation mode %q", mode)
	}
}

func scoreErrorBudget(plainY float64, absCap float64, relCap float64) float64 {
	budget := math.Inf(1)

	if absCap > 0 {
		budget = math.Min(budget, absCap)
	}

	if relCap > 0 {
		budget = math.Min(budget, relCap*math.Max(math.Abs(plainY), 1e-12))
	}

	if math.IsInf(budget, 1) {
		return 0
	}

	return budget
}

func labelToDecision(label int) bool {
	return label == 1
}

func summarizeWDBCInference(
	config CKKSWDBCInferenceConfig,
	normalizedMode string,
	model wdbcModelArtifact,
	context Context,
	records []CKKSWDBCInferenceRecord,
) CKKSWDBCInferenceSummary {
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
	sumLinear := 0.0
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
		sumLinear += record.LinearEvalMS
		sumPolynomial += record.PolynomialEvalMS
		sumEvalOnly += record.EvalOnlyMS
		sumDecryptDecode += record.DecryptDecodeMS
		sumTotal += record.TotalEvalMS

		finalYLevel = record.YLevel
	}

	count := float64(len(records))

	return CKKSWDBCInferenceSummary{
		Dataset:        model.Dataset,
		Model:          model.Model,
		TestSamples:    int(model.Metrics.TestSamples),
		EvaluatedRows:  len(records),
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

		MeanEncodeEncryptMS:  sumEncodeEncrypt / count,
		MeanLinearEvalMS:     sumLinear / count,
		MeanPolynomialEvalMS: sumPolynomial / count,
		MeanEvalOnlyMS:       sumEvalOnly / count,
		MeanDecryptDecodeMS:  sumDecryptDecode / count,
		MeanTotalEvalMS:      sumTotal / count,
		MedianTotalEvalMS:    wdbcPercentile(totalTimes, 0.50),
		P95TotalEvalMS:       wdbcPercentile(totalTimes, 0.95),

		InitialLevel:    context.MaxLevel(),
		FinalYLevel:     finalYLevel,
		LogDefaultScale: context.LogDefaultScale(),
		MaxSlots:        context.MaxSlots(),
	}
}

func wdbcPercentile(values []float64, p float64) float64 {
	if len(values) == 0 {
		return 0
	}

	sortedValues := append([]float64(nil), values...)
	sort.Float64s(sortedValues)

	if p <= 0 {
		return sortedValues[0]
	}

	if p >= 1 {
		return sortedValues[len(sortedValues)-1]
	}

	position := p * float64(len(sortedValues)-1)
	lower := int(math.Floor(position))
	upper := int(math.Ceil(position))

	if lower == upper {
		return sortedValues[lower]
	}

	weight := position - float64(lower)
	return sortedValues[lower]*(1-weight) + sortedValues[upper]*weight
}
