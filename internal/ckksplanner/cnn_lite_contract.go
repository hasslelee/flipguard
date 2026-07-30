package ckksplanner

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"strconv"
	"strings"

	"github.com/hasslelee/flipguard/internal/analysis"
	"github.com/hasslelee/flipguard/internal/benchmarks"
	"github.com/hasslelee/flipguard/internal/ir"
	fgruntime "github.com/hasslelee/flipguard/internal/runtime"
	"github.com/hasslelee/flipguard/internal/tuner"
)

const (
	MNISTCNNLiteModelSchemaV1  = "flipguard_mnist_cnn_lite_holdout_v1"
	MNISTCNNLiteModelType      = "cnn_lite_square_binary01"
	MNISTCNNLiteGraphAdapterV1 = "mnist_cnn_lite_scalar_replicated_graph_adapter_v1"

	MNISTCNNLiteExtractionPolicyV1      = "mnist_binary01_cnn_lite_export_v1"
	MNISTCNNLiteMaterializationSchemaV1 = "flipguard_mnist_cnn_lite_materialization_v1"
	MNISTCNNLiteSourceFeatureSpaceV1    = "mnist_28x28_grayscale_image_v1"
)

type CNNLiteContractOptions struct {
	ModelPath      string
	ValidationPath string
	SourcePath     string
	SplitID        string

	MarginFloor  float64
	SafetyFactor float64

	SecurityBits         int
	MaxEncryptedTrials   int
	ValidationKeyRepeats int
	AllowedPaths         []tuner.ExecutionPath
}

type cnnLiteModelArtifact struct {
	SchemaVersion     string  `json:"schema_version"`
	DatasetID         string  `json:"dataset_id"`
	DatasetName       string  `json:"dataset_name"`
	ModelID           string  `json:"model_id"`
	ModelType         string  `json:"model_type"`
	GraphAdapterID    string  `json:"graph_adapter_id"`
	GraphFormula      string  `json:"graph_formula"`
	InputDim          int     `json:"input_dim"`
	DecisionThreshold float64 `json:"decision_threshold"`
	PackingScope      string  `json:"packing_scope"`

	SourceArchive struct {
		URL         string `json:"url"`
		OriginalURL string `json:"original_url"`
		SHA256      string `json:"sha256"`
	} `json:"source_archive"`

	ExtractionPolicyID     string `json:"extraction_policy_id"`
	ExtractionPolicyDigest string `json:"extraction_policy_digest"`

	Architecture struct {
		InputShape         [2]int `json:"input_shape"`
		ConvolutionFilters int    `json:"convolution_filters"`
		KernelShape        [2]int `json:"kernel_shape"`
		Stride             int    `json:"stride"`
		Padding            string `json:"padding"`
		Activation         string `json:"activation"`
		OutputShape        [3]int `json:"output_shape_before_head"`
		LinearHeadOutputs  int    `json:"linear_head_outputs"`
	} `json:"architecture"`

	LearnedParameters struct {
		ConvolutionFilters [benchmarks.CNNLiteFilters]struct {
			Weights [benchmarks.CNNLiteFilterSide][benchmarks.CNNLiteFilterSide]float64 `json:"weights"`
			Bias    float64                                                             `json:"bias"`
		} `json:"convolution_filters"`
		OutputWeights [benchmarks.CNNLiteFilters][benchmarks.CNNLiteConvSide][benchmarks.CNNLiteConvSide]float64 `json:"output_weights"`
		OutputBias    float64                                                                                    `json:"output_bias"`
	} `json:"learned_parameters"`

	DirectPolicyReference struct {
		PolicyID     string `json:"policy_id"`
		PolicyDigest string `json:"policy_digest"`
		Relationship string `json:"relationship"`
	} `json:"direct_policy_reference"`
}

type cnnLiteValidationSample struct {
	ID            string
	Pixels        [benchmarks.CNNLiteInputSide][benchmarks.CNNLiteInputSide]float64
	PlainScore    float64
	PlainDecision bool
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

func DefaultPrimaryCNNLiteContractOptions() CNNLiteContractOptions {
	tabular := DefaultPrimaryTabularContractOptions()
	return CNNLiteContractOptions{
		MarginFloor:          tabular.MarginFloor,
		SafetyFactor:         tabular.SafetyFactor,
		SecurityBits:         tabular.SecurityBits,
		MaxEncryptedTrials:   tabular.MaxEncryptedTrials,
		ValidationKeyRepeats: tabular.ValidationKeyRepeats,
		AllowedPaths: []tuner.ExecutionPath{
			tuner.PathRescale,
		},
	}
}

func BuildCNNLiteWorkloadContract(
	options CNNLiteContractOptions,
) (WorkloadContract, error) {
	normalizeCNNLiteContractOptions(&options)
	modelBytes, err := os.ReadFile(options.ModelPath)
	if err != nil {
		return WorkloadContract{}, fmt.Errorf(
			"read CNN-lite model artifact: %w",
			err,
		)
	}
	model := cnnLiteModelArtifact{}
	if err := json.Unmarshal(modelBytes, &model); err != nil {
		return WorkloadContract{}, fmt.Errorf(
			"parse CNN-lite model artifact: %w",
			err,
		)
	}
	if err := validateCNNLiteModel(model); err != nil {
		return WorkloadContract{}, err
	}

	validationBytes, err := os.ReadFile(options.ValidationPath)
	if err != nil {
		return WorkloadContract{}, fmt.Errorf(
			"read CNN-lite validation data: %w",
			err,
		)
	}
	samples, sourceDigestFromRows, extractionDigest, err :=
		parseCNNLiteValidation(validationBytes, model)
	if err != nil {
		return WorkloadContract{}, err
	}
	sourceBytes, err := os.ReadFile(options.SourcePath)
	if err != nil {
		return WorkloadContract{}, fmt.Errorf(
			"read MNIST source: %w",
			err,
		)
	}
	sourceDigest := digestBytes(sourceBytes)
	if sourceDigest != model.SourceArchive.SHA256 ||
		sourceDigest != sourceDigestFromRows {
		return WorkloadContract{}, fmt.Errorf(
			"MNIST source digest mismatch: source=%s model=%s validation=%s",
			sourceDigest,
			model.SourceArchive.SHA256,
			sourceDigestFromRows,
		)
	}
	if extractionDigest != model.ExtractionPolicyDigest {
		return WorkloadContract{}, fmt.Errorf(
			"CNN-lite extraction policy digest mismatch",
		)
	}

	benchmarkModel := model.benchmarkModel()
	graph := benchmarks.NewCNNLiteSquareGraph(benchmarkModel)
	if err := graph.Validate(); err != nil {
		return WorkloadContract{}, fmt.Errorf(
			"validate CNN-lite planner graph: %w",
			err,
		)
	}
	analysisSamples := make(
		[]map[ir.NodeID]float64,
		0,
		len(samples),
	)
	sampleOrder := make([]string, 0, len(samples))
	plainScores := make(map[string]float64, len(samples))
	maxInputAbs := 0.0
	maxOutputAbs := 0.0
	protectedMargin := math.Inf(1)
	vCert := 0
	vAmb := 0
	for index, sample := range samples {
		inputs := cnnLiteInputs(sample.Pixels)
		for row := range sample.Pixels {
			for _, value := range sample.Pixels[row] {
				maxInputAbs = math.Max(maxInputAbs, math.Abs(value))
			}
		}
		plain, err := fgruntime.EvalPlain(graph, inputs)
		if err != nil {
			return WorkloadContract{}, fmt.Errorf(
				"evaluate CNN-lite validation row %d: %w",
				index+2,
				err,
			)
		}
		if !closeFloatAtTolerance(
			plain.Output,
			sample.PlainScore,
			1e-12,
		) {
			return WorkloadContract{}, fmt.Errorf(
				"CNN-lite validation row %d score %.12g does not match graph %.12g",
				index+2,
				sample.PlainScore,
				plain.Output,
			)
		}
		decision := sample.PlainScore >= model.DecisionThreshold
		if decision != sample.PlainDecision {
			return WorkloadContract{}, fmt.Errorf(
				"CNN-lite validation row %d decision mismatch",
				index+2,
			)
		}
		margin := math.Abs(
			sample.PlainScore - model.DecisionThreshold,
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
			"CNN-lite validation has no certifiable sample above margin floor %.12g",
			options.MarginFloor,
		)
	}
	bounds, err := analysis.AnalyzeBoundsAndSensitivity(
		graph,
		analysisSamples,
		model.DecisionThreshold,
		0.05,
	)
	if err != nil {
		return WorkloadContract{}, fmt.Errorf(
			"analyze CNN-lite graph sensitivity: %w",
			err,
		)
	}
	aggregateSensitivity := aggregateOperationSensitivity(graph, bounds)
	if aggregateSensitivity <= 0 {
		return WorkloadContract{}, fmt.Errorf(
			"derived CNN-lite aggregate sensitivity is not positive",
		)
	}
	graphSummary, err := summarizeTabularGraph(graph)
	if err != nil {
		return WorkloadContract{}, err
	}
	graphSummary.Notes = []string{
		"exact learned 4x4-input valid-convolution square-activation DAG",
		"2x2 filter coefficients are shared across nine spatial positions",
		"predeclared scalar-replicated CNN-lite graph-adapter extension",
		"mean pooling is verified input materialization, not encrypted execution",
	}
	scaleDemand, err := analyzeLattigoRescaleDemand(graph)
	if err != nil {
		return WorkloadContract{}, err
	}

	modelDigest := digestBytes(modelBytes)
	validationArtifactDigest := digestBytes(validationBytes)
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
			Path: options.ModelPath, SHA256: modelDigest,
		},
		ValidationData: ArtifactBinding{
			Path: options.ValidationPath, SHA256: validationArtifactDigest,
		},
		SourceData: &ArtifactBinding{
			Path: options.SourcePath, SHA256: sourceDigest,
		},
		InputMaterialization: &InputMaterializationContract{
			SchemaVersion:        MNISTCNNLiteMaterializationSchemaV1,
			SourceFeatureSpace:   MNISTCNNLiteSourceFeatureSpaceV1,
			PreprocessingMethod:  MNISTCNNLiteExtractionPolicyV1,
			SourceReplayVerified: true,
		},
		Graph: graphSummary,
		Decision: DecisionStabilityContract{
			Threshold:          model.DecisionThreshold,
			MarginFloor:        options.MarginFloor,
			SafetyFactor:       options.SafetyFactor,
			ProtectedMargin:    protectedMargin,
			OutputErrorBudget:  options.SafetyFactor * protectedMargin,
			ValidationDigest:   digestValidationScores(sampleOrder, plainScores),
			ValidationSamples:  len(samples),
			CertifiableSamples: vCert,
			AmbiguousSamples:   vAmb,
		},
		Calibration: NumericalCalibration{
			MaxInputAbs:           maxInputAbs,
			MaxPlaintextOutputAbs: maxOutputAbs,
			AggregateSensitivity:  aggregateSensitivity,
			SensitivityMethod:     EmpiricalIntervalDAGSensitivityV1,
			CalibrationScope: "observed_validation_artifact:" +
				validationArtifactDigest,
		},
		Deployment: DeploymentContract{
			SecurityBits:         options.SecurityBits,
			RequiredSlots:        1,
			MaxEncryptedTrials:   options.MaxEncryptedTrials,
			ValidationKeyRepeats: options.ValidationKeyRepeats,
			PackingStrategy:      ScalarReplicatedPackingV1,
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
			"validate derived CNN-lite workload contract: %w",
			err,
		)
	}
	return contract, nil
}

func normalizeCNNLiteContractOptions(options *CNNLiteContractOptions) {
	defaults := DefaultPrimaryCNNLiteContractOptions()
	options.ModelPath = strings.TrimSpace(options.ModelPath)
	options.ValidationPath = strings.TrimSpace(options.ValidationPath)
	options.SourcePath = strings.TrimSpace(options.SourcePath)
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

func validateCNNLiteModel(model cnnLiteModelArtifact) error {
	if model.SchemaVersion != MNISTCNNLiteModelSchemaV1 ||
		model.DatasetID != "mnist_binary01" ||
		model.ModelID != MNISTCNNLiteModelType ||
		model.ModelType != MNISTCNNLiteModelType ||
		model.GraphAdapterID != MNISTCNNLiteGraphAdapterV1 ||
		model.GraphFormula !=
			"linear_head(square(valid_conv2x2(mean_pool7x7(image))))" ||
		model.InputDim != 16 {
		return fmt.Errorf(
			"CNN-lite model identity or graph formula changed",
		)
	}
	if model.DecisionThreshold != 0 ||
		model.PackingScope != ScalarReplicatedPackingV1 {
		return fmt.Errorf(
			"CNN-lite decision or packing scope changed",
		)
	}
	if model.Architecture.InputShape != [2]int{4, 4} ||
		model.Architecture.ConvolutionFilters != 4 ||
		model.Architecture.KernelShape != [2]int{2, 2} ||
		model.Architecture.Stride != 1 ||
		model.Architecture.Padding != "valid" ||
		model.Architecture.Activation != "square" ||
		model.Architecture.OutputShape != [3]int{4, 3, 3} ||
		model.Architecture.LinearHeadOutputs != 1 {
		return fmt.Errorf("CNN-lite architecture changed")
	}
	if model.ExtractionPolicyID !=
		MNISTCNNLiteExtractionPolicyV1 {
		return fmt.Errorf(
			"CNN-lite extraction policy identity changed",
		)
	}
	if err := validateSHA256(model.SourceArchive.SHA256); err != nil {
		return fmt.Errorf("MNIST source digest: %w", err)
	}
	if err := validateSHA256(
		model.ExtractionPolicyDigest,
	); err != nil {
		return fmt.Errorf(
			"CNN-lite extraction policy digest: %w",
			err,
		)
	}
	direct := DefaultDirectSynthesisPolicyContract()
	if model.DirectPolicyReference.PolicyID != direct.PolicyID ||
		model.DirectPolicyReference.PolicyDigest !=
			MustDefaultDirectSynthesisPolicyDigest() {
		return fmt.Errorf(
			"CNN-lite direct policy reference changed",
		)
	}
	if !strings.Contains(
		model.DirectPolicyReference.Relationship,
		"model_type_not_added_to_policy_supported_models",
	) {
		return fmt.Errorf(
			"CNN-lite must remain an explicit graph-adapter extension",
		)
	}
	graph := benchmarks.NewCNNLiteSquareGraph(model.benchmarkModel())
	for _, node := range graph.Nodes() {
		if !finite(node.Const) {
			return fmt.Errorf(
				"CNN-lite model contains non-finite parameter",
			)
		}
	}
	return nil
}

func parseCNNLiteValidation(
	data []byte,
	model cnnLiteModelArtifact,
) (
	[]cnnLiteValidationSample,
	string,
	string,
	error,
) {
	reader := csv.NewReader(strings.NewReader(string(data)))
	records, err := reader.ReadAll()
	if err != nil {
		return nil, "", "", fmt.Errorf(
			"read CNN-lite validation CSV: %w",
			err,
		)
	}
	if len(records) < 2 {
		return nil, "", "", fmt.Errorf(
			"CNN-lite validation CSV has no data rows",
		)
	}
	header := make(map[string]int, len(records[0]))
	for index, name := range records[0] {
		header[name] = index
	}
	required := []string{
		"row_id",
		"sample_id",
		"source_partition",
		"digit_label",
		"binary_label",
		"plaintext_score",
		"decision_threshold",
		"decision_margin",
		"plaintext_decision",
		"source_sha256",
		"extraction_policy_digest",
	}
	for row := 0; row < benchmarks.CNNLiteInputSide; row++ {
		for column := 0; column < benchmarks.CNNLiteInputSide; column++ {
			required = append(
				required,
				fmt.Sprintf("pool%d%d", row, column),
			)
		}
	}
	for _, field := range required {
		if _, ok := header[field]; !ok {
			return nil, "", "", fmt.Errorf(
				"CNN-lite validation CSV missing %s",
				field,
			)
		}
	}

	samples := make(
		[]cnnLiteValidationSample,
		0,
		len(records)-1,
	)
	seen := make(map[string]struct{}, len(records)-1)
	sourceDigest := ""
	extractionDigest := ""
	benchmarkModel := model.benchmarkModel()
	for rowIndex, record := range records[1:] {
		field := func(name string) (string, error) {
			index := header[name]
			if index >= len(record) {
				return "", fmt.Errorf(
					"CNN-lite validation row %d missing %s",
					rowIndex+2,
					name,
				)
			}
			return strings.TrimSpace(record[index]), nil
		}
		id, _ := field("row_id")
		if id == "" {
			return nil, "", "", fmt.Errorf(
				"CNN-lite validation row %d has empty row_id",
				rowIndex+2,
			)
		}
		sampleID, _ := field("sample_id")
		rowID, err := strconv.Atoi(id)
		if err != nil ||
			sampleID != fmt.Sprintf("mnist_%05d", rowID) {
			return nil, "", "", fmt.Errorf(
				"CNN-lite validation row %d identity changed",
				rowIndex+2,
			)
		}
		if _, exists := seen[id]; exists {
			return nil, "", "", fmt.Errorf(
				"duplicate CNN-lite row_id %s",
				id,
			)
		}
		seen[id] = struct{}{}
		var pixels [benchmarks.CNNLiteInputSide][benchmarks.CNNLiteInputSide]float64
		for row := 0; row < benchmarks.CNNLiteInputSide; row++ {
			for column := 0; column < benchmarks.CNNLiteInputSide; column++ {
				name := fmt.Sprintf("pool%d%d", row, column)
				raw, _ := field(name)
				value, err := strconv.ParseFloat(raw, 64)
				if err != nil || !finite(value) ||
					value < 0 || value > 1 {
					return nil, "", "", fmt.Errorf(
						"CNN-lite validation row %d invalid %s",
						rowIndex+2,
						name,
					)
				}
				pixels[row][column] = value
			}
		}
		rawScore, _ := field("plaintext_score")
		score, err := strconv.ParseFloat(rawScore, 64)
		if err != nil || !finite(score) {
			return nil, "", "", fmt.Errorf(
				"CNN-lite validation row %d invalid score",
				rowIndex+2,
			)
		}
		recomputed := benchmarks.CNNLiteSquareScore(
			benchmarks.CNNLiteSquareSample{Pixels: pixels},
			benchmarkModel,
		)
		if !closeFloatAtTolerance(score, recomputed, 1e-12) {
			return nil, "", "", fmt.Errorf(
				"CNN-lite validation row %d plaintext score changed",
				rowIndex+2,
			)
		}
		rawThreshold, _ := field("decision_threshold")
		threshold, err := strconv.ParseFloat(rawThreshold, 64)
		if err != nil || threshold != model.DecisionThreshold {
			return nil, "", "", fmt.Errorf(
				"CNN-lite validation row %d threshold changed",
				rowIndex+2,
			)
		}
		rawMargin, _ := field("decision_margin")
		margin, err := strconv.ParseFloat(rawMargin, 64)
		if err != nil ||
			!closeFloatAtTolerance(
				margin,
				math.Abs(score-threshold),
				1e-15,
			) {
			return nil, "", "", fmt.Errorf(
				"CNN-lite validation row %d margin changed",
				rowIndex+2,
			)
		}
		rawDecision, _ := field("plaintext_decision")
		decision, err := strconv.ParseBool(rawDecision)
		if err != nil || decision != (score >= threshold) {
			return nil, "", "", fmt.Errorf(
				"CNN-lite validation row %d decision changed",
				rowIndex+2,
			)
		}
		digitRaw, _ := field("digit_label")
		binaryRaw, _ := field("binary_label")
		digit, digitErr := strconv.Atoi(digitRaw)
		binary, binaryErr := strconv.Atoi(binaryRaw)
		if digitErr != nil || binaryErr != nil ||
			(digit != 0 && digit != 1) ||
			digit != binary {
			return nil, "", "", fmt.Errorf(
				"CNN-lite validation row %d task changed",
				rowIndex+2,
			)
		}
		rowSource, _ := field("source_sha256")
		rowExtraction, _ := field("extraction_policy_digest")
		if rowIndex == 0 {
			sourceDigest = rowSource
			extractionDigest = rowExtraction
		} else if rowSource != sourceDigest ||
			rowExtraction != extractionDigest {
			return nil, "", "", fmt.Errorf(
				"CNN-lite provenance changes at row %d",
				rowIndex+2,
			)
		}
		samples = append(samples, cnnLiteValidationSample{
			ID:            id,
			Pixels:        pixels,
			PlainScore:    score,
			PlainDecision: decision,
		})
	}
	return samples, sourceDigest, extractionDigest, nil
}

func cnnLiteInputs(
	pixels [benchmarks.CNNLiteInputSide][benchmarks.CNNLiteInputSide]float64,
) map[ir.NodeID]float64 {
	inputs := make(
		map[ir.NodeID]float64,
		benchmarks.CNNLiteInputSide*benchmarks.CNNLiteInputSide,
	)
	for row := 0; row < benchmarks.CNNLiteInputSide; row++ {
		for column := 0; column < benchmarks.CNNLiteInputSide; column++ {
			id := ir.NodeID(fmt.Sprintf("pool%d%d", row, column))
			inputs[id] = pixels[row][column]
		}
	}
	return inputs
}
