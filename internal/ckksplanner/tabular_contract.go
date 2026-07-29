package ckksplanner

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"os"
	"strconv"
	"strings"

	"github.com/hasslelee/flipguard/internal/analysis"
	"github.com/hasslelee/flipguard/internal/ir"
	fgruntime "github.com/hasslelee/flipguard/internal/runtime"
	"github.com/hasslelee/flipguard/internal/tuner"
)

// TabularContractOptions controls normalization of a user model and validation
// dataset into a digest-bound planner contract.
type TabularContractOptions struct {
	ModelPath      string
	ValidationPath string
	SourceDataPath string
	SplitID        string

	MarginFloor  float64
	SafetyFactor float64

	SecurityBits         int
	MaxEncryptedTrials   int
	ValidationKeyRepeats int
	AllowedPaths         []tuner.ExecutionPath
}

// DefaultTabularContractOptions returns backward-compatible base defaults.
// Callers still have to provide model, validation, and split identities.
func DefaultTabularContractOptions() TabularContractOptions {
	policy := DefaultDirectSynthesisPolicyContract()
	return TabularContractOptions{
		MarginFloor:  policy.PrimaryMarginFloor,
		SafetyFactor: policy.PrimaryAlpha,

		SecurityBits:         128,
		MaxEncryptedTrials:   policy.MaxEncryptedTrials,
		ValidationKeyRepeats: 1,
		AllowedPaths: []tuner.ExecutionPath{
			tuner.PathRescale,
		},
	}
}

// DefaultPrimaryTabularContractOptions returns the fresh-key policy evaluated
// by the primary direct-synthesis and locked-audit protocol.
func DefaultPrimaryTabularContractOptions() TabularContractOptions {
	options := DefaultTabularContractOptions()
	options.ValidationKeyRepeats = 3
	return options
}

type tabularModelArtifact struct {
	DatasetID   string `json:"dataset_id"`
	DatasetName string `json:"dataset_name"`
	ModelID     string `json:"model_id"`
	ModelType   string `json:"model_type"`
	InputDim    int    `json:"input_dim"`

	SelectedFeatureIndices []int                  `json:"selected_feature_indices"`
	SelectedFeatureNames   []string               `json:"selected_feature_names"`
	Standardization        tabularStandardization `json:"standardization"`

	ScaledModelForCKKS tabularScaledModel     `json:"scaled_model_for_ckks"`
	PolynomialScore    tabularPolynomialScore `json:"polynomial_score"`
}

type tabularStandardization struct {
	Mean []float64 `json:"mean"`
	Std  []float64 `json:"std"`
}

type tabularPolynomialScore struct {
	Formula           string  `json:"formula"`
	DecisionThreshold float64 `json:"decision_threshold"`
}

type tabularScaledModel struct {
	Weights []float64 `json:"weights"`
	Bias    float64   `json:"bias"`

	HiddenWeights [][]float64 `json:"hidden_weights"`
	HiddenBias    []float64   `json:"hidden_bias"`
	OutputWeights []float64   `json:"output_weights"`
	OutputBias    float64     `json:"output_bias"`
}

type tabularValidationSample struct {
	ID            string
	Features      []float64
	PlainScore    float64
	PlainDecision bool
}

// BuildTabularWorkloadContract parses the supplied model and validation data,
// verifies that their plaintext scores match the derived computation graph,
// and returns all signals needed for direct CKKS parameter synthesis.
func BuildTabularWorkloadContract(
	options TabularContractOptions,
) (WorkloadContract, error) {
	normalizeTabularContractOptions(&options)

	modelBytes, err := os.ReadFile(options.ModelPath)
	if err != nil {
		return WorkloadContract{}, fmt.Errorf(
			"read tabular model artifact: %w",
			err,
		)
	}

	model := tabularModelArtifact{}
	if err := json.Unmarshal(modelBytes, &model); err != nil {
		return WorkloadContract{}, fmt.Errorf(
			"parse tabular model artifact: %w",
			err,
		)
	}
	if err := validateTabularModel(model); err != nil {
		return WorkloadContract{}, err
	}

	graph, err := buildTabularIRGraph(model)
	if err != nil {
		return WorkloadContract{}, err
	}

	validationBytes, err := os.ReadFile(options.ValidationPath)
	if err != nil {
		return WorkloadContract{}, fmt.Errorf(
			"read tabular validation data: %w",
			err,
		)
	}

	samples, provenance, err := parseTabularValidation(
		validationBytes,
		model.InputDim,
	)
	if err != nil {
		return WorkloadContract{}, err
	}

	analysisSamples := make(
		[]map[ir.NodeID]float64,
		0,
		len(samples),
	)
	plainScores := make(map[string]float64, len(samples))
	sampleOrder := make([]string, 0, len(samples))

	maxInputAbs := 0.0
	maxOutputAbs := 0.0
	protectedMargin := math.Inf(1)
	vCert := 0
	vAmb := 0

	for rowIndex, sample := range samples {
		inputs := make(map[ir.NodeID]float64, len(sample.Features))
		for featureIndex, feature := range sample.Features {
			inputs[tabularInputID(featureIndex)] = feature
			maxInputAbs = math.Max(maxInputAbs, math.Abs(feature))
		}

		plainResult, err := fgruntime.EvalPlain(graph, inputs)
		if err != nil {
			return WorkloadContract{}, fmt.Errorf(
				"evaluate validation row %d plaintext graph: %w",
				rowIndex+2,
				err,
			)
		}
		if !closeFloatAtTolerance(
			plainResult.Output,
			sample.PlainScore,
			1e-9,
		) {
			return WorkloadContract{}, fmt.Errorf(
				"validation row %d score %.12g does not match model graph %.12g",
				rowIndex+2,
				sample.PlainScore,
				plainResult.Output,
			)
		}

		decision :=
			sample.PlainScore >= model.PolynomialScore.DecisionThreshold
		if decision != sample.PlainDecision {
			return WorkloadContract{}, fmt.Errorf(
				"validation row %d plaintext decision does not match threshold",
				rowIndex+2,
			)
		}

		margin := math.Abs(
			sample.PlainScore -
				model.PolynomialScore.DecisionThreshold,
		)
		if margin <= options.MarginFloor {
			vAmb++
		} else {
			vCert++
			protectedMargin = math.Min(protectedMargin, margin)
		}

		maxOutputAbs = math.Max(
			maxOutputAbs,
			math.Abs(sample.PlainScore),
		)
		analysisSamples = append(analysisSamples, inputs)
		sampleOrder = append(sampleOrder, sample.ID)
		plainScores[sample.ID] = sample.PlainScore
	}

	if vCert == 0 || math.IsInf(protectedMargin, 1) {
		return WorkloadContract{}, fmt.Errorf(
			"validation data has no certifiable sample above margin floor %.12g",
			options.MarginFloor,
		)
	}

	bounds, err := analysis.AnalyzeBoundsAndSensitivity(
		graph,
		analysisSamples,
		model.PolynomialScore.DecisionThreshold,
		0.05,
	)
	if err != nil {
		return WorkloadContract{}, fmt.Errorf(
			"analyze tabular graph sensitivity: %w",
			err,
		)
	}

	aggregateSensitivity := aggregateOperationSensitivity(graph, bounds)
	if aggregateSensitivity <= 0 {
		return WorkloadContract{}, fmt.Errorf(
			"derived aggregate sensitivity is not positive",
		)
	}

	modelDigest := digestBytes(modelBytes)
	if provenance.ModelSHA256 != "" &&
		provenance.ModelSHA256 != modelDigest {
		return WorkloadContract{}, fmt.Errorf(
			"validation materialization model digest %s does not match model artifact %s",
			provenance.ModelSHA256,
			modelDigest,
		)
	}
	validationArtifactDigest := digestBytes(validationBytes)
	validationDigest := digestValidationScores(sampleOrder, plainScores)
	graphSummary, err := summarizeTabularGraph(graph)
	if err != nil {
		return WorkloadContract{}, err
	}
	scaleDemand, err := analyzeLattigoRescaleDemand(graph)
	if err != nil {
		return WorkloadContract{}, err
	}

	var sourceDataBinding *ArtifactBinding
	if strings.TrimSpace(options.SourceDataPath) != "" {
		sourceBytes, err := os.ReadFile(options.SourceDataPath)
		if err != nil {
			return WorkloadContract{}, fmt.Errorf(
				"read source data for contract binding: %w",
				err,
			)
		}
		sourceDigest := digestBytes(sourceBytes)
		if provenance.SourceDataSHA256 == "" {
			return WorkloadContract{}, fmt.Errorf(
				"validation data has no materialized source digest",
			)
		}
		if provenance.SourceDataSHA256 != sourceDigest {
			return WorkloadContract{}, fmt.Errorf(
				"validation materialization source digest %s does not match source data %s",
				provenance.SourceDataSHA256,
				sourceDigest,
			)
		}
		if err := verifySourceMaterialization(
			model,
			sourceBytes,
			samples,
			provenance,
		); err != nil {
			return WorkloadContract{}, err
		}
		sourceDataBinding = &ArtifactBinding{
			Path:   options.SourceDataPath,
			SHA256: sourceDigest,
		}
	}
	var inputMaterialization *InputMaterializationContract
	if provenance.SchemaVersion != "" {
		inputMaterialization = &InputMaterializationContract{
			SchemaVersion:        provenance.SchemaVersion,
			SourceFeatureSpace:   provenance.SourceFeatureSpace,
			PreprocessingMethod:  provenance.PreprocessingMethod,
			SourceReplayVerified: sourceDataBinding != nil,
		}
	}

	contract := WorkloadContract{
		SchemaVersion: WorkloadContractSchemaVersion,

		WorkloadID: strings.Join(
			[]string{options.SplitID, model.DatasetID, model.ModelID},
			"/",
		),
		DatasetID: model.DatasetID,
		ModelID:   model.ModelID,
		ModelType: model.ModelType,
		SplitID:   options.SplitID,

		ModelArtifact: ArtifactBinding{
			Path:   options.ModelPath,
			SHA256: modelDigest,
		},
		ValidationData: ArtifactBinding{
			Path:   options.ValidationPath,
			SHA256: validationArtifactDigest,
		},
		SourceData:           sourceDataBinding,
		InputMaterialization: inputMaterialization,

		Graph: graphSummary,
		Decision: DecisionStabilityContract{
			Threshold:    model.PolynomialScore.DecisionThreshold,
			MarginFloor:  options.MarginFloor,
			SafetyFactor: options.SafetyFactor,

			ProtectedMargin: protectedMargin,
			OutputErrorBudget: options.SafetyFactor *
				protectedMargin,

			ValidationDigest: validationDigest,

			ValidationSamples:  len(samples),
			CertifiableSamples: vCert,
			AmbiguousSamples:   vAmb,
		},
		Calibration: NumericalCalibration{
			MaxInputAbs:           maxInputAbs,
			MaxPlaintextOutputAbs: maxOutputAbs,

			AggregateSensitivity: aggregateSensitivity,
			SensitivityMethod:    EmpiricalIntervalDAGSensitivityV1,
			CalibrationScope: "observed_validation_artifact:" +
				validationArtifactDigest,
		},
		Deployment: DeploymentContract{
			SecurityBits:         options.SecurityBits,
			RequiredSlots:        1,
			MaxEncryptedTrials:   options.MaxEncryptedTrials,
			ValidationKeyRepeats: options.ValidationKeyRepeats,

			PackingStrategy: ScalarReplicatedPackingV1,
			AllowedPaths: append(
				[]tuner.ExecutionPath(nil),
				options.AllowedPaths...,
			),

			ScaleTraceMethod:      LattigoRescaleScaleTraceV1,
			RescaleLevelsConsumed: scaleDemand.LevelsConsumed,
			TerminalScaleExponent: scaleDemand.ScaleExponent,
			RequiredQPrimes:       scaleDemand.RequiredQPrimes,
		},
	}

	if err := contract.Validate(); err != nil {
		return WorkloadContract{}, fmt.Errorf(
			"validate derived tabular workload contract: %w",
			err,
		)
	}

	return contract, nil
}

func normalizeTabularContractOptions(options *TabularContractOptions) {
	defaults := DefaultTabularContractOptions()

	options.ModelPath = strings.TrimSpace(options.ModelPath)
	options.ValidationPath = strings.TrimSpace(options.ValidationPath)
	options.SplitID = strings.TrimSpace(options.SplitID)

	if options.MarginFloor < 0 || !finite(options.MarginFloor) {
		options.MarginFloor = defaults.MarginFloor
	}
	if options.SafetyFactor <= 0 ||
		options.SafetyFactor > 1 ||
		!finite(options.SafetyFactor) {
		options.SafetyFactor = defaults.SafetyFactor
	}
	if options.SecurityBits <= 0 {
		options.SecurityBits = defaults.SecurityBits
	}
	if options.MaxEncryptedTrials <= 0 {
		options.MaxEncryptedTrials = defaults.MaxEncryptedTrials
	}
	if options.ValidationKeyRepeats <= 0 {
		options.ValidationKeyRepeats =
			defaults.ValidationKeyRepeats
	}
	if len(options.AllowedPaths) == 0 {
		options.AllowedPaths = append(
			[]tuner.ExecutionPath(nil),
			defaults.AllowedPaths...,
		)
	}
}

func validateTabularModel(model tabularModelArtifact) error {
	if strings.TrimSpace(model.DatasetID) == "" {
		return fmt.Errorf("tabular model dataset_id is empty")
	}
	if strings.TrimSpace(model.ModelID) == "" {
		return fmt.Errorf("tabular model model_id is empty")
	}
	if model.InputDim <= 0 {
		return fmt.Errorf("tabular model input_dim must be positive")
	}
	if !finite(model.PolynomialScore.DecisionThreshold) {
		return fmt.Errorf("tabular model decision threshold must be finite")
	}

	scaled := model.ScaledModelForCKKS
	switch model.ModelType {
	case "linear_poly3":
		if len(scaled.Weights) != model.InputDim {
			return fmt.Errorf(
				"linear model has %d weights, expected %d",
				len(scaled.Weights),
				model.InputDim,
			)
		}
		if model.PolynomialScore.Formula !=
			"0.5 + 0.197*z - 0.004*z^3" {
			return fmt.Errorf(
				"linear_poly3 has unsupported score formula %q",
				model.PolynomialScore.Formula,
			)
		}

	case "mlp_square_linear_score", "mlp_square_poly3":
		hiddenUnits := len(scaled.HiddenWeights)
		if hiddenUnits == 0 {
			return fmt.Errorf("square MLP has no hidden units")
		}
		if len(scaled.HiddenBias) != hiddenUnits ||
			len(scaled.OutputWeights) != hiddenUnits {
			return fmt.Errorf(
				"square MLP hidden/output dimensions are inconsistent",
			)
		}
		for index, weights := range scaled.HiddenWeights {
			if len(weights) != model.InputDim {
				return fmt.Errorf(
					"square MLP hidden unit %d has %d weights, expected %d",
					index,
					len(weights),
					model.InputDim,
				)
			}
		}

		expectedFormula := "0.5 + 0.197*z"
		if model.ModelType == "mlp_square_poly3" {
			expectedFormula = "0.5 + 0.197*z - 0.004*z^3"
		}
		if model.PolynomialScore.Formula != expectedFormula {
			return fmt.Errorf(
				"%s has unsupported score formula %q",
				model.ModelType,
				model.PolynomialScore.Formula,
			)
		}

	default:
		return fmt.Errorf(
			"unsupported tabular model_type %q",
			model.ModelType,
		)
	}

	if err := validateFiniteModelValues(model); err != nil {
		return err
	}
	return nil
}

func validateFiniteModelValues(model tabularModelArtifact) error {
	values := append(
		[]float64(nil),
		model.ScaledModelForCKKS.Weights...,
	)
	values = append(values, model.ScaledModelForCKKS.Bias)
	values = append(values, model.ScaledModelForCKKS.HiddenBias...)
	values = append(values, model.ScaledModelForCKKS.OutputWeights...)
	values = append(values, model.ScaledModelForCKKS.OutputBias)
	for _, weights := range model.ScaledModelForCKKS.HiddenWeights {
		values = append(values, weights...)
	}
	for index, value := range values {
		if !finite(value) {
			return fmt.Errorf(
				"tabular model contains non-finite scaled value at index %d",
				index,
			)
		}
	}
	return nil
}

func buildTabularIRGraph(model tabularModelArtifact) (*ir.Graph, error) {
	graph := ir.NewGraph()
	inputs := make([]ir.NodeID, model.InputDim)
	for index := range inputs {
		inputs[index] = tabularInputID(index)
		graph.MustAddNode(
			ir.NewInput(inputs[index], string(inputs[index])),
		)
	}

	var zID ir.NodeID
	switch model.ModelType {
	case "linear_poly3":
		zID = addTabularAffine(
			graph,
			"model",
			inputs,
			model.ScaledModelForCKKS.Weights,
			model.ScaledModelForCKKS.Bias,
		)

	case "mlp_square_linear_score", "mlp_square_poly3":
		hiddenOutputs := make(
			[]ir.NodeID,
			len(model.ScaledModelForCKKS.HiddenWeights),
		)
		for hiddenIndex, weights := range model.ScaledModelForCKKS.HiddenWeights {
			hiddenID := addTabularAffine(
				graph,
				fmt.Sprintf("hidden_%d", hiddenIndex),
				inputs,
				weights,
				model.ScaledModelForCKKS.HiddenBias[hiddenIndex],
			)
			squaredID := ir.NodeID(
				fmt.Sprintf("hidden_%d_square", hiddenIndex),
			)
			graph.MustAddNode(
				ir.NewUnary(
					squaredID,
					string(squaredID),
					ir.OpPow2,
					hiddenID,
				),
			)
			hiddenOutputs[hiddenIndex] = squaredID
		}

		zID = addTabularAffine(
			graph,
			"output",
			hiddenOutputs,
			model.ScaledModelForCKKS.OutputWeights,
			model.ScaledModelForCKKS.OutputBias,
		)
	}

	var outputID ir.NodeID
	switch model.PolynomialScore.Formula {
	case "0.5 + 0.197*z":
		const scaledID ir.NodeID = "score_scaled"
		const biasID ir.NodeID = "score_bias"
		outputID = "score"

		graph.MustAddNode(
			ir.NewMulConst(scaledID, string(scaledID), zID, 0.197),
		)
		graph.MustAddNode(ir.NewConst(biasID, string(biasID), 0.5))
		graph.MustAddNode(
			ir.NewBinary(
				outputID,
				string(outputID),
				ir.OpAdd,
				scaledID,
				biasID,
			),
		)

	case "0.5 + 0.197*z - 0.004*z^3":
		outputID = "score"
		graph.MustAddNode(
			ir.NewPoly(
				outputID,
				string(outputID),
				zID,
				[]float64{0.5, 0.197, 0, -0.004},
			),
		)

	default:
		return nil, fmt.Errorf(
			"unsupported tabular score formula %q",
			model.PolynomialScore.Formula,
		)
	}

	graph.MustSetOutput(outputID)
	if err := graph.Validate(); err != nil {
		return nil, fmt.Errorf("validate tabular planner graph: %w", err)
	}
	return graph, nil
}

func addTabularAffine(
	graph *ir.Graph,
	prefix string,
	inputs []ir.NodeID,
	weights []float64,
	bias float64,
) ir.NodeID {
	terms := make([]ir.NodeID, len(inputs))
	for index, input := range inputs {
		termID := ir.NodeID(fmt.Sprintf("%s_term_%d", prefix, index))
		graph.MustAddNode(
			ir.NewMulConst(
				termID,
				string(termID),
				input,
				weights[index],
			),
		)
		terms[index] = termID
	}

	accumulator := terms[0]
	for index := 1; index < len(terms); index++ {
		sumID := ir.NodeID(fmt.Sprintf("%s_sum_%d", prefix, index))
		graph.MustAddNode(
			ir.NewBinary(
				sumID,
				string(sumID),
				ir.OpAdd,
				accumulator,
				terms[index],
			),
		)
		accumulator = sumID
	}

	if bias == 0 {
		return accumulator
	}

	biasID := ir.NodeID(prefix + "_bias")
	outputID := ir.NodeID(prefix + "_affine")
	graph.MustAddNode(ir.NewConst(biasID, string(biasID), bias))
	graph.MustAddNode(
		ir.NewBinary(
			outputID,
			string(outputID),
			ir.OpAdd,
			accumulator,
			biasID,
		),
	)
	return outputID
}

type tabularValidationProvenance struct {
	SchemaVersion       string
	ModelSHA256         string
	SourceDataSHA256    string
	SourceFeatureSpace  string
	PreprocessingMethod string
}

func parseTabularValidation(
	data []byte,
	inputDim int,
) ([]tabularValidationSample, tabularValidationProvenance, error) {
	reader := csv.NewReader(strings.NewReader(string(data)))
	header, err := reader.Read()
	if err != nil {
		return nil, tabularValidationProvenance{},
			fmt.Errorf("read tabular validation header: %w", err)
	}

	columns := make(map[string]int, len(header))
	for index, name := range header {
		name = strings.TrimSpace(name)
		if name == "" {
			return nil, tabularValidationProvenance{}, fmt.Errorf(
				"tabular validation column %d is empty",
				index,
			)
		}
		if _, exists := columns[name]; exists {
			return nil, tabularValidationProvenance{}, fmt.Errorf(
				"tabular validation has duplicate column %q",
				name,
			)
		}
		columns[name] = index
	}

	required := []string{
		"row_id",
		"polynomial_score",
		"plaintext_decision",
	}
	for featureIndex := 0; featureIndex < inputDim; featureIndex++ {
		required = append(required, fmt.Sprintf("x_%d", featureIndex))
	}
	for _, name := range required {
		if _, exists := columns[name]; !exists {
			return nil, tabularValidationProvenance{}, fmt.Errorf(
				"tabular validation is missing column %q",
				name,
			)
		}
	}
	_, hasMaterializationSchema := columns["materialization_schema"]
	_, hasSourceModelDigest := columns["source_model_sha256"]
	_, hasSourceDataDigest := columns["source_data_sha256"]
	_, hasSourceFeatureSpace := columns["source_feature_space"]
	_, hasPreprocessingMethod := columns["preprocessing_method"]
	hasAnyProvenance := hasMaterializationSchema ||
		hasSourceModelDigest ||
		hasSourceDataDigest ||
		hasSourceFeatureSpace ||
		hasPreprocessingMethod
	if hasAnyProvenance &&
		!(hasMaterializationSchema &&
			hasSourceModelDigest &&
			hasSourceDataDigest) {
		return nil, tabularValidationProvenance{}, fmt.Errorf(
			"tabular validation materialization provenance columns are incomplete",
		)
	}

	samples := make([]tabularValidationSample, 0)
	seenIDs := map[string]bool{}
	provenance := tabularValidationProvenance{}

	for rowNumber := 2; ; rowNumber++ {
		record, err := reader.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, tabularValidationProvenance{}, fmt.Errorf(
				"read tabular validation row %d: %w",
				rowNumber,
				err,
			)
		}
		if len(record) != len(header) {
			return nil, tabularValidationProvenance{}, fmt.Errorf(
				"tabular validation row %d has %d fields, expected %d",
				rowNumber,
				len(record),
				len(header),
			)
		}

		id := strings.TrimSpace(record[columns["row_id"]])
		if id == "" {
			return nil, tabularValidationProvenance{}, fmt.Errorf(
				"tabular validation row %d has empty row_id",
				rowNumber,
			)
		}
		if seenIDs[id] {
			return nil, tabularValidationProvenance{}, fmt.Errorf(
				"tabular validation has duplicate row_id %q",
				id,
			)
		}
		seenIDs[id] = true

		score, err := parseFiniteCSVFloat(
			record[columns["polynomial_score"]],
			"polynomial_score",
			rowNumber,
		)
		if err != nil {
			return nil, tabularValidationProvenance{}, err
		}
		decision, err := strconv.ParseBool(
			strings.TrimSpace(record[columns["plaintext_decision"]]),
		)
		if err != nil {
			return nil, tabularValidationProvenance{}, fmt.Errorf(
				"parse tabular validation row %d plaintext_decision: %w",
				rowNumber,
				err,
			)
		}

		features := make([]float64, inputDim)
		for featureIndex := range features {
			name := fmt.Sprintf("x_%d", featureIndex)
			features[featureIndex], err = parseFiniteCSVFloat(
				record[columns[name]],
				name,
				rowNumber,
			)
			if err != nil {
				return nil, tabularValidationProvenance{}, err
			}
		}

		if schemaIndex, exists := columns["materialization_schema"]; exists {
			schema := strings.TrimSpace(record[schemaIndex])
			sourceFeatureSpace :=
				string(TabularDataSpaceModelInput)
			preprocessingMethod :=
				TabularPreprocessingIdentityV1
			switch schema {
			case TabularValidationMaterializationSchemaV1:
				if hasSourceFeatureSpace ||
					hasPreprocessingMethod {
					return nil, tabularValidationProvenance{}, fmt.Errorf(
						"tabular validation row %d schema v1 must not declare v2 preprocessing columns",
						rowNumber,
					)
				}
			case TabularValidationMaterializationSchemaV2:
				if !hasSourceFeatureSpace ||
					!hasPreprocessingMethod {
					return nil, tabularValidationProvenance{}, fmt.Errorf(
						"tabular validation row %d schema v2 preprocessing provenance columns are incomplete",
						rowNumber,
					)
				}
				sourceFeatureSpace = strings.TrimSpace(
					record[columns["source_feature_space"]],
				)
				preprocessingMethod = strings.TrimSpace(
					record[columns["preprocessing_method"]],
				)
			default:
				return nil, tabularValidationProvenance{}, fmt.Errorf(
					"tabular validation row %d has unsupported materialization schema %q",
					rowNumber,
					schema,
				)
			}
			modelDigestIndex := columns["source_model_sha256"]
			sourceDigestIndex := columns["source_data_sha256"]
			modelDigest := strings.TrimSpace(
				record[modelDigestIndex],
			)
			sourceDigest := strings.TrimSpace(
				record[sourceDigestIndex],
			)
			if err := validateSHA256(modelDigest); err != nil {
				return nil, tabularValidationProvenance{}, fmt.Errorf(
					"tabular validation row %d model digest: %w",
					rowNumber,
					err,
				)
			}
			if err := validateSHA256(sourceDigest); err != nil {
				return nil, tabularValidationProvenance{}, fmt.Errorf(
					"tabular validation row %d source digest: %w",
					rowNumber,
					err,
				)
			}
			materialization := InputMaterializationContract{
				SchemaVersion:       schema,
				SourceFeatureSpace:  sourceFeatureSpace,
				PreprocessingMethod: preprocessingMethod,
			}
			if err := materialization.validate(); err != nil {
				return nil, tabularValidationProvenance{}, fmt.Errorf(
					"tabular validation row %d materialization contract: %w",
					rowNumber,
					err,
				)
			}
			if provenance.SchemaVersion == "" {
				provenance.SchemaVersion = schema
				provenance.ModelSHA256 = modelDigest
				provenance.SourceDataSHA256 = sourceDigest
				provenance.SourceFeatureSpace =
					sourceFeatureSpace
				provenance.PreprocessingMethod =
					preprocessingMethod
			} else if provenance.SchemaVersion != schema ||
				provenance.ModelSHA256 != modelDigest ||
				provenance.SourceDataSHA256 != sourceDigest ||
				provenance.SourceFeatureSpace !=
					sourceFeatureSpace ||
				provenance.PreprocessingMethod !=
					preprocessingMethod {
				return nil, tabularValidationProvenance{}, fmt.Errorf(
					"tabular validation row %d materialization provenance changed",
					rowNumber,
				)
			}
		}

		samples = append(samples, tabularValidationSample{
			ID:            id,
			Features:      features,
			PlainScore:    score,
			PlainDecision: decision,
		})
	}

	if len(samples) == 0 {
		return nil, tabularValidationProvenance{},
			fmt.Errorf("tabular validation data is empty")
	}
	return samples, provenance, nil
}

func verifySourceMaterialization(
	model tabularModelArtifact,
	sourceData []byte,
	preparedSamples []tabularValidationSample,
	provenance tabularValidationProvenance,
) error {
	if provenance.SchemaVersion == "" {
		return fmt.Errorf(
			"validation data has no materialization schema",
		)
	}
	sourceRows, resolvedSpace, preprocessingMethod, err :=
		parseTabularFeatureRows(
			sourceData,
			model,
			TabularDataSpace(provenance.SourceFeatureSpace),
		)
	if err != nil {
		return fmt.Errorf(
			"replay source preprocessing: %w",
			err,
		)
	}
	if string(resolvedSpace) != provenance.SourceFeatureSpace ||
		preprocessingMethod != provenance.PreprocessingMethod {
		return fmt.Errorf(
			"source preprocessing replay resolved %s/%s, expected %s/%s",
			resolvedSpace,
			preprocessingMethod,
			provenance.SourceFeatureSpace,
			provenance.PreprocessingMethod,
		)
	}
	if len(sourceRows) != len(preparedSamples) {
		return fmt.Errorf(
			"source preprocessing produced %d rows, prepared validation has %d",
			len(sourceRows),
			len(preparedSamples),
		)
	}
	for rowIndex, sourceRow := range sourceRows {
		prepared := preparedSamples[rowIndex]
		expectedID := strconv.Itoa(sourceRow.ID)
		if prepared.ID != expectedID {
			return fmt.Errorf(
				"prepared validation row %d id %q does not match source preprocessing id %q",
				rowIndex+2,
				prepared.ID,
				expectedID,
			)
		}
		if len(sourceRow.Features) != len(prepared.Features) {
			return fmt.Errorf(
				"prepared validation row %d feature count does not match source preprocessing",
				rowIndex+2,
			)
		}
		for featureIndex, expected := range sourceRow.Features {
			if prepared.Features[featureIndex] != expected {
				return fmt.Errorf(
					"prepared validation row %d x_%d %.17g does not match source preprocessing %.17g",
					rowIndex+2,
					featureIndex,
					prepared.Features[featureIndex],
					expected,
				)
			}
		}
	}
	return nil
}

func parseFiniteCSVFloat(
	raw string,
	field string,
	rowNumber int,
) (float64, error) {
	value, err := strconv.ParseFloat(strings.TrimSpace(raw), 64)
	if err != nil {
		return 0, fmt.Errorf(
			"parse tabular validation row %d %s: %w",
			rowNumber,
			field,
			err,
		)
	}
	if !finite(value) {
		return 0, fmt.Errorf(
			"tabular validation row %d %s is non-finite",
			rowNumber,
			field,
		)
	}
	return value, nil
}

func summarizeTabularGraph(graph *ir.Graph) (tuner.GraphSummary, error) {
	if graph == nil {
		return tuner.GraphSummary{}, fmt.Errorf("tabular graph is nil")
	}
	if err := graph.Validate(); err != nil {
		return tuner.GraphSummary{}, err
	}

	depths := make(map[ir.NodeID]int, graph.Len())
	summary := tuner.GraphSummary{}

	for _, node := range graph.Nodes() {
		maxInputDepth := 0
		for _, input := range node.Inputs {
			depth, exists := depths[input]
			if !exists {
				return tuner.GraphSummary{}, fmt.Errorf(
					"tabular graph node %s is not topologically ordered",
					node.ID,
				)
			}
			maxInputDepth = maxInt(maxInputDepth, depth)
		}

		depth := maxInputDepth
		switch node.Op {
		case ir.OpInput, ir.OpConst:
		case ir.OpAdd, ir.OpSub:
			summary.AddOps++
		case ir.OpMulConst:
			summary.MulOps++
		case ir.OpMul, ir.OpPow2:
			summary.MulOps++
			depth++
		case ir.OpPow3:
			summary.MulOps += 2
			depth += 2
		case ir.OpPoly:
			degree := len(node.Coeffs) - 1
			polyDepth := ceilLog2(maxInt(1, degree))
			summary.MulOps += polyDepth
			depth += polyDepth
		default:
			return tuner.GraphSummary{}, fmt.Errorf(
				"unsupported tabular planner op %s",
				node.Op,
			)
		}

		depths[node.ID] = depth
		summary.MultiplicativeDepth =
			maxInt(summary.MultiplicativeDepth, depth)
	}

	summary.RescaleOps = summary.MultiplicativeDepth
	summary.Notes = []string{
		"derived from the exact tabular plaintext DAG",
		"rescale count is the maximum multiplicative path depth",
	}
	return summary, nil
}

func aggregateOperationSensitivity(
	graph *ir.Graph,
	bounds *analysis.BoundSensitivityResult,
) float64 {
	total := 0.0
	for _, node := range graph.Nodes() {
		switch node.Op {
		case ir.OpInput, ir.OpConst:
			continue
		default:
			total += bounds.Sensitivity[node.ID]
		}
	}
	return total
}

type lattigoScaleState struct {
	IsCiphertext bool

	ScaleExponent  int
	LevelsConsumed int
}

type lattigoScaleDemand struct {
	LevelsConsumed  int
	ScaleExponent   int
	RequiredQPrimes int
}

// analyzeLattigoRescaleDemand models the current backend rather than equating
// multiplicative depth with modulus levels. In Lattigo v6, multiplication by a
// non-integer scalar adds the current Q-prime scale. RescaleTo can therefore
// consume several primes in one call.
func analyzeLattigoRescaleDemand(
	graph *ir.Graph,
) (lattigoScaleDemand, error) {
	states := make(map[ir.NodeID]lattigoScaleState, graph.Len())

	for _, node := range graph.Nodes() {
		inputStates := make(
			[]lattigoScaleState,
			0,
			len(node.Inputs),
		)
		for _, inputID := range node.Inputs {
			state, exists := states[inputID]
			if !exists {
				return lattigoScaleDemand{}, fmt.Errorf(
					"scale trace input %s for node %s is missing",
					inputID,
					node.ID,
				)
			}
			inputStates = append(inputStates, state)
		}

		state := lattigoScaleState{}
		switch node.Op {
		case ir.OpInput:
			state = lattigoScaleState{
				IsCiphertext:  true,
				ScaleExponent: 1,
			}

		case ir.OpConst:
			state = lattigoScaleState{}

		case ir.OpAdd, ir.OpSub:
			for _, input := range inputStates {
				if !input.IsCiphertext {
					continue
				}
				state.IsCiphertext = true
				state.ScaleExponent = maxInt(
					state.ScaleExponent,
					input.ScaleExponent,
				)
				state.LevelsConsumed = maxInt(
					state.LevelsConsumed,
					input.LevelsConsumed,
				)
			}
			if !state.IsCiphertext {
				return lattigoScaleDemand{}, fmt.Errorf(
					"scale trace node %s adds only plaintext values",
					node.ID,
				)
			}

		case ir.OpMulConst:
			input := inputStates[0]
			if !input.IsCiphertext {
				return lattigoScaleDemand{}, fmt.Errorf(
					"scale trace node %s multiplies a plaintext",
					node.ID,
				)
			}
			state = input
			state.ScaleExponent++

		case ir.OpMul:
			left := inputStates[0]
			right := inputStates[1]
			if !left.IsCiphertext || !right.IsCiphertext {
				return lattigoScaleDemand{}, fmt.Errorf(
					"scale trace node %s requires ciphertext inputs",
					node.ID,
				)
			}
			state = lattigoScaleState{
				IsCiphertext: true,
				ScaleExponent: left.ScaleExponent +
					right.ScaleExponent,
				LevelsConsumed: maxInt(
					left.LevelsConsumed,
					right.LevelsConsumed,
				),
			}

		case ir.OpPow2:
			input := inputStates[0]
			productExponent := 2 * input.ScaleExponent
			state = lattigoScaleState{
				IsCiphertext:  true,
				ScaleExponent: 1,
				LevelsConsumed: input.LevelsConsumed +
					productExponent - 1,
			}

		case ir.OpPow3:
			return lattigoScaleDemand{}, fmt.Errorf(
				"standalone pow3 has no declared rescale implementation",
			)

		case ir.OpPoly:
			input := inputStates[0]
			degree := len(node.Coeffs) - 1
			if degree != 3 {
				return lattigoScaleDemand{}, fmt.Errorf(
					"scale trace supports cubic polynomial only, got degree %d",
					degree,
				)
			}

			// Current Horner backend:
			// z2=rescale(z*z), inner=(-.004*z2)+.197,
			// y=rescale(inner*z)+.5.
			cubicLevels := 3 * input.ScaleExponent
			state = lattigoScaleState{
				IsCiphertext:  true,
				ScaleExponent: 1,
				LevelsConsumed: input.LevelsConsumed +
					cubicLevels,
			}

		default:
			return lattigoScaleDemand{}, fmt.Errorf(
				"unsupported scale trace op %s",
				node.Op,
			)
		}

		states[node.ID] = state
	}

	output, exists := states[graph.Output]
	if !exists || !output.IsCiphertext {
		return lattigoScaleDemand{}, fmt.Errorf(
			"scale trace output is not a ciphertext",
		)
	}

	return lattigoScaleDemand{
		LevelsConsumed: output.LevelsConsumed,
		ScaleExponent:  output.ScaleExponent,
		RequiredQPrimes: output.LevelsConsumed +
			output.ScaleExponent,
	}, nil
}

func digestBytes(data []byte) string {
	sum := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(sum[:])
}

func digestValidationScores(
	sampleOrder []string,
	plainScores map[string]float64,
) string {
	hasher := sha256.New()
	var encoded [8]byte

	for _, sampleID := range sampleOrder {
		binary.BigEndian.PutUint64(encoded[:], uint64(len(sampleID)))
		_, _ = hasher.Write(encoded[:])
		_, _ = hasher.Write([]byte(sampleID))

		binary.BigEndian.PutUint64(
			encoded[:],
			math.Float64bits(plainScores[sampleID]),
		)
		_, _ = hasher.Write(encoded[:])
	}

	return "sha256:" + hex.EncodeToString(hasher.Sum(nil))
}

func tabularInputID(index int) ir.NodeID {
	return ir.NodeID(fmt.Sprintf("x_%d", index))
}

func ceilLog2(value int) int {
	if value <= 1 {
		return 0
	}
	return int(math.Ceil(math.Log2(float64(value))))
}

func maxInt(left int, right int) int {
	if left > right {
		return left
	}
	return right
}

func closeFloatAtTolerance(
	left float64,
	right float64,
	tolerance float64,
) bool {
	scale := math.Max(1, math.Max(math.Abs(left), math.Abs(right)))
	return math.Abs(left-right) <= tolerance*scale
}
