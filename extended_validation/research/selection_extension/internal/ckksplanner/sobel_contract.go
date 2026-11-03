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
	VisionPatchMaterializationSchemaV1 = "flipguard_vision_patch_v1"
	VisionPatchSourceFeatureSpaceV1    = "normalized_image_patch_v1"
	BSDS500SobelPatchExtractionV1      = "bsds500_sobel_patch_extraction_v1"
	BSDS500SobelModelSchemaV1          = "flipguard_bsds500_sobel_holdout_v1"
	BSDS500SobelModelType              = "sobel_edge_score"
)

type SobelContractOptions struct {
	ModelPath         string
	ValidationPath    string
	SourceArchivePath string
	SplitID           string

	MarginFloor  float64
	SafetyFactor float64

	SecurityBits         int
	MaxEncryptedTrials   int
	ValidationKeyRepeats int
	AllowedPaths         []tuner.ExecutionPath
}

type sobelModelArtifact struct {
	SchemaVersion string `json:"schema_version"`
	DatasetID     string `json:"dataset_id"`
	DatasetName   string `json:"dataset_name"`
	ModelID       string `json:"model_id"`
	ModelType     string `json:"model_type"`
	InputDim      int    `json:"input_dim"`
	GraphFormula  string `json:"graph_formula"`

	DecisionThreshold float64 `json:"decision_threshold"`

	PackingScope string `json:"packing_scope"`

	SourceArchive struct {
		URL    string `json:"url"`
		SHA256 string `json:"sha256"`
	} `json:"source_archive"`

	ExtractionPolicyID     string `json:"extraction_policy_id"`
	ExtractionPolicyDigest string `json:"extraction_policy_digest"`

	DirectPolicyReference struct {
		PolicyID     string `json:"policy_id"`
		PolicyDigest string `json:"policy_digest"`
		Relationship string `json:"relationship"`
	} `json:"direct_policy_reference"`
}

type sobelValidationSample struct {
	ID            string
	Pixels        [9]float64
	PlainScore    float64
	PlainDecision bool
}

func DefaultPrimarySobelContractOptions() SobelContractOptions {
	tabular := DefaultPrimaryTabularContractOptions()
	return SobelContractOptions{
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

func BuildSobelWorkloadContract(
	options SobelContractOptions,
) (WorkloadContract, error) {
	normalizeSobelContractOptions(&options)

	modelBytes, err := os.ReadFile(options.ModelPath)
	if err != nil {
		return WorkloadContract{}, fmt.Errorf(
			"read Sobel model artifact: %w",
			err,
		)
	}
	model := sobelModelArtifact{}
	if err := json.Unmarshal(modelBytes, &model); err != nil {
		return WorkloadContract{}, fmt.Errorf(
			"parse Sobel model artifact: %w",
			err,
		)
	}
	if err := validateSobelModel(model); err != nil {
		return WorkloadContract{}, err
	}

	validationBytes, err := os.ReadFile(options.ValidationPath)
	if err != nil {
		return WorkloadContract{}, fmt.Errorf(
			"read Sobel validation data: %w",
			err,
		)
	}
	samples, archiveDigest, extractionDigest, err :=
		parseSobelValidation(validationBytes, model)
	if err != nil {
		return WorkloadContract{}, err
	}

	sourceBytes, err := os.ReadFile(options.SourceArchivePath)
	if err != nil {
		return WorkloadContract{}, fmt.Errorf(
			"read Sobel source archive: %w",
			err,
		)
	}
	sourceDigest := digestBytes(sourceBytes)
	if sourceDigest != model.SourceArchive.SHA256 ||
		sourceDigest != archiveDigest {
		return WorkloadContract{}, fmt.Errorf(
			"Sobel source archive digest mismatch: source=%s model=%s validation=%s",
			sourceDigest,
			model.SourceArchive.SHA256,
			archiveDigest,
		)
	}
	if extractionDigest != model.ExtractionPolicyDigest {
		return WorkloadContract{}, fmt.Errorf(
			"Sobel extraction policy digest mismatch",
		)
	}

	graph := benchmarks.NewSobelEdgeRescaleGraph()
	if err := graph.Validate(); err != nil {
		return WorkloadContract{}, fmt.Errorf(
			"validate Sobel planner graph: %w",
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
		inputs := sobelInputs(sample.Pixels)
		for _, value := range sample.Pixels {
			maxInputAbs = math.Max(maxInputAbs, math.Abs(value))
		}
		plain, err := fgruntime.EvalPlain(graph, inputs)
		if err != nil {
			return WorkloadContract{}, fmt.Errorf(
				"evaluate Sobel validation row %d: %w",
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
				"Sobel validation row %d score %.12g does not match graph %.12g",
				index+2,
				sample.PlainScore,
				plain.Output,
			)
		}
		decision := sample.PlainScore >= model.DecisionThreshold
		if decision != sample.PlainDecision {
			return WorkloadContract{}, fmt.Errorf(
				"Sobel validation row %d plaintext decision mismatch",
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
			"Sobel validation has no certifiable sample above margin floor %.12g",
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
			"analyze Sobel graph sensitivity: %w",
			err,
		)
	}
	aggregateSensitivity := aggregateOperationSensitivity(graph, bounds)
	if aggregateSensitivity <= 0 {
		return WorkloadContract{}, fmt.Errorf(
			"derived Sobel aggregate sensitivity is not positive",
		)
	}
	graphSummary, err := summarizeTabularGraph(graph)
	if err != nil {
		return WorkloadContract{}, err
	}
	graphSummary.Notes = []string{
		"derived from the exact Sobel rescale-aware plaintext DAG",
		"predeclared non-tabular graph-adapter extension",
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
			Path: options.SourceArchivePath, SHA256: sourceDigest,
		},
		InputMaterialization: &InputMaterializationContract{
			SchemaVersion:        VisionPatchMaterializationSchemaV1,
			SourceFeatureSpace:   VisionPatchSourceFeatureSpaceV1,
			PreprocessingMethod:  BSDS500SobelPatchExtractionV1,
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
			"validate derived Sobel workload contract: %w",
			err,
		)
	}
	return contract, nil
}

func normalizeSobelContractOptions(options *SobelContractOptions) {
	defaults := DefaultPrimarySobelContractOptions()
	options.ModelPath = strings.TrimSpace(options.ModelPath)
	options.ValidationPath = strings.TrimSpace(options.ValidationPath)
	options.SourceArchivePath = strings.TrimSpace(options.SourceArchivePath)
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

func validateSobelModel(model sobelModelArtifact) error {
	if model.SchemaVersion != BSDS500SobelModelSchemaV1 {
		return fmt.Errorf(
			"unsupported Sobel model schema %q",
			model.SchemaVersion,
		)
	}
	if model.DatasetID != "bsds500" ||
		model.ModelID != BSDS500SobelModelType ||
		model.ModelType != BSDS500SobelModelType ||
		model.InputDim != 9 ||
		model.GraphFormula != "Gx^2 + Gy^2" {
		return fmt.Errorf("Sobel model identity or graph formula changed")
	}
	if !finite(model.DecisionThreshold) ||
		model.DecisionThreshold <= 0 {
		return fmt.Errorf("Sobel decision threshold must be positive")
	}
	if model.PackingScope != ScalarReplicatedPackingV1 {
		return fmt.Errorf("unsupported Sobel packing scope")
	}
	if model.ExtractionPolicyID != BSDS500SobelPatchExtractionV1 ||
		strings.TrimSpace(model.ExtractionPolicyDigest) == "" {
		return fmt.Errorf("Sobel extraction policy binding changed")
	}
	direct := DefaultDirectSynthesisPolicyContract()
	if model.DirectPolicyReference.PolicyID != direct.PolicyID ||
		model.DirectPolicyReference.PolicyDigest !=
			MustDefaultDirectSynthesisPolicyDigest() {
		return fmt.Errorf("Sobel direct policy reference changed")
	}
	if !strings.Contains(
		model.DirectPolicyReference.Relationship,
		"model_type_not_added_to_policy_supported_models",
	) {
		return fmt.Errorf(
			"Sobel model must remain an explicit graph-adapter extension",
		)
	}
	if err := validateSHA256(model.SourceArchive.SHA256); err != nil {
		return fmt.Errorf("Sobel source archive digest: %w", err)
	}
	if err := validateSHA256(model.ExtractionPolicyDigest); err != nil {
		return fmt.Errorf("Sobel extraction policy digest: %w", err)
	}
	return nil
}

func parseSobelValidation(
	data []byte,
	model sobelModelArtifact,
) (
	[]sobelValidationSample,
	string,
	string,
	error,
) {
	reader := csv.NewReader(strings.NewReader(string(data)))
	records, err := reader.ReadAll()
	if err != nil {
		return nil, "", "", fmt.Errorf(
			"read Sobel validation CSV: %w",
			err,
		)
	}
	if len(records) < 2 {
		return nil, "", "", fmt.Errorf(
			"Sobel validation CSV has no data rows",
		)
	}
	header := make(map[string]int, len(records[0]))
	for index, name := range records[0] {
		header[name] = index
	}
	required := []string{
		"row_id",
		"plaintext_score",
		"decision_threshold",
		"plaintext_decision",
		"source_archive_sha256",
		"extraction_policy_digest",
		"p00", "p01", "p02",
		"p10", "p11", "p12",
		"p20", "p21", "p22",
	}
	for _, field := range required {
		if _, ok := header[field]; !ok {
			return nil, "", "", fmt.Errorf(
				"Sobel validation CSV missing %s",
				field,
			)
		}
	}

	samples := make([]sobelValidationSample, 0, len(records)-1)
	seen := make(map[string]struct{}, len(records)-1)
	archiveDigest := ""
	extractionDigest := ""
	for rowIndex, record := range records[1:] {
		field := func(name string) (string, error) {
			index := header[name]
			if index >= len(record) {
				return "", fmt.Errorf(
					"Sobel validation row %d missing %s",
					rowIndex+2,
					name,
				)
			}
			return strings.TrimSpace(record[index]), nil
		}
		id, _ := field("row_id")
		if id == "" {
			return nil, "", "", fmt.Errorf(
				"Sobel validation row %d has empty row_id",
				rowIndex+2,
			)
		}
		if _, exists := seen[id]; exists {
			return nil, "", "", fmt.Errorf(
				"duplicate Sobel row_id %s",
				id,
			)
		}
		seen[id] = struct{}{}
		var pixels [9]float64
		for index, name := range required[6:] {
			raw, _ := field(name)
			value, err := strconv.ParseFloat(raw, 64)
			if err != nil || !finite(value) || value < 0 || value > 1 {
				return nil, "", "", fmt.Errorf(
					"Sobel validation row %d invalid %s",
					rowIndex+2,
					name,
				)
			}
			pixels[index] = value
		}
		rawScore, _ := field("plaintext_score")
		score, err := strconv.ParseFloat(rawScore, 64)
		if err != nil || !finite(score) {
			return nil, "", "", fmt.Errorf(
				"Sobel validation row %d invalid plaintext_score",
				rowIndex+2,
			)
		}
		rawThreshold, _ := field("decision_threshold")
		threshold, err := strconv.ParseFloat(rawThreshold, 64)
		if err != nil ||
			!closeFloatAtTolerance(
				threshold,
				model.DecisionThreshold,
				1e-15,
			) {
			return nil, "", "", fmt.Errorf(
				"Sobel validation row %d threshold changed",
				rowIndex+2,
			)
		}
		rawDecision, _ := field("plaintext_decision")
		decision, err := strconv.ParseBool(rawDecision)
		if err != nil {
			return nil, "", "", fmt.Errorf(
				"Sobel validation row %d invalid decision",
				rowIndex+2,
			)
		}
		rowArchive, _ := field("source_archive_sha256")
		rowExtraction, _ := field("extraction_policy_digest")
		if rowIndex == 0 {
			archiveDigest = rowArchive
			extractionDigest = rowExtraction
		} else if rowArchive != archiveDigest ||
			rowExtraction != extractionDigest {
			return nil, "", "", fmt.Errorf(
				"Sobel validation provenance changes at row %d",
				rowIndex+2,
			)
		}
		samples = append(samples, sobelValidationSample{
			ID:            id,
			Pixels:        pixels,
			PlainScore:    score,
			PlainDecision: decision,
		})
	}
	return samples, archiveDigest, extractionDigest, nil
}

func sobelInputs(pixels [9]float64) map[ir.NodeID]float64 {
	ids := [...]ir.NodeID{
		"p00", "p01", "p02",
		"p10", "p11", "p12",
		"p20", "p21", "p22",
	}
	inputs := make(map[ir.NodeID]float64, len(ids))
	for index, id := range ids {
		inputs[id] = pixels[index]
	}
	return inputs
}
