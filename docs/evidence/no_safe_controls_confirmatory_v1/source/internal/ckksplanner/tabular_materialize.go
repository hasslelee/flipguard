package ckksplanner

import (
	"bytes"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/hasslelee/flipguard/internal/ir"
	fgruntime "github.com/hasslelee/flipguard/internal/runtime"
)

const (
	TabularValidationMaterializationSchemaV1 = "flipguard_tabular_validation_v1"
	TabularValidationMaterializationSchemaV2 = "flipguard_tabular_validation_v2"

	TabularPreprocessingIdentityV1                = "identity_model_input_v1"
	TabularPreprocessingSelectedStandardizationV1 = "selected_feature_standardization_v1"
)

// TabularDataSpace identifies whether feature columns are already in the
// model input space or require the model artifact's frozen preprocessing.
type TabularDataSpace string

const (
	TabularDataSpaceAuto       TabularDataSpace = "auto"
	TabularDataSpaceModelInput TabularDataSpace = "model_input"
	TabularDataSpaceRaw        TabularDataSpace = "raw"
)

// TabularMaterializationOptions controls source feature interpretation.
type TabularMaterializationOptions struct {
	DataSpace TabularDataSpace
}

// TabularValidationMaterialization records deterministic feature-data
// normalization performed before contract construction.
type TabularValidationMaterialization struct {
	SchemaVersion int `json:"schema_version"`

	DatasetID string `json:"dataset_id"`
	ModelID   string `json:"model_id"`
	Rows      int    `json:"rows"`

	ModelPath      string `json:"model_path"`
	SourceDataPath string `json:"source_data_path"`
	ValidationPath string `json:"validation_path"`

	ModelSHA256      string `json:"model_sha256"`
	SourceDataSHA256 string `json:"source_data_sha256"`
	ValidationSHA256 string `json:"validation_sha256"`

	SourceFeatureSpace  string `json:"source_feature_space"`
	PreprocessingMethod string `json:"preprocessing_method"`
}

type tabularFeatureRow struct {
	ID       int
	Label    int
	Features []float64
}

// MaterializeTabularValidation derives all plaintext score and decision
// columns required by the encrypted backend from held-out feature data.
func MaterializeTabularValidation(
	modelPath string,
	sourceDataPath string,
	validationPath string,
) (TabularValidationMaterialization, error) {
	return MaterializeTabularValidationWithOptions(
		modelPath,
		sourceDataPath,
		validationPath,
		TabularMaterializationOptions{
			DataSpace: TabularDataSpaceAuto,
		},
	)
}

// MaterializeTabularValidationWithOptions derives the backend validation
// artifact while recording the exact source feature-space interpretation.
func MaterializeTabularValidationWithOptions(
	modelPath string,
	sourceDataPath string,
	validationPath string,
	options TabularMaterializationOptions,
) (TabularValidationMaterialization, error) {
	if strings.TrimSpace(modelPath) == "" {
		return TabularValidationMaterialization{},
			fmt.Errorf("model path is empty")
	}
	if strings.TrimSpace(sourceDataPath) == "" {
		return TabularValidationMaterialization{},
			fmt.Errorf("source data path is empty")
	}
	if strings.TrimSpace(validationPath) == "" {
		return TabularValidationMaterialization{},
			fmt.Errorf("validation output path is empty")
	}

	sourceAbsolute, err := filepath.Abs(sourceDataPath)
	if err != nil {
		return TabularValidationMaterialization{},
			fmt.Errorf("resolve source data path: %w", err)
	}
	validationAbsolute, err := filepath.Abs(validationPath)
	if err != nil {
		return TabularValidationMaterialization{},
			fmt.Errorf("resolve validation output path: %w", err)
	}
	if filepath.Clean(sourceAbsolute) == filepath.Clean(validationAbsolute) {
		return TabularValidationMaterialization{},
			fmt.Errorf("validation output must not overwrite source data")
	}
	dataSpace, err := normalizeTabularDataSpace(options.DataSpace)
	if err != nil {
		return TabularValidationMaterialization{}, err
	}

	modelBytes, err := os.ReadFile(modelPath)
	if err != nil {
		return TabularValidationMaterialization{},
			fmt.Errorf("read tabular model artifact: %w", err)
	}
	model := tabularModelArtifact{}
	if err := json.Unmarshal(modelBytes, &model); err != nil {
		return TabularValidationMaterialization{},
			fmt.Errorf("parse tabular model artifact: %w", err)
	}
	if err := validateTabularModel(model); err != nil {
		return TabularValidationMaterialization{}, err
	}

	sourceBytes, err := os.ReadFile(sourceDataPath)
	if err != nil {
		return TabularValidationMaterialization{},
			fmt.Errorf("read tabular source data: %w", err)
	}
	rows, resolvedDataSpace, preprocessingMethod, err :=
		parseTabularFeatureRows(
			sourceBytes,
			model,
			dataSpace,
		)
	if err != nil {
		return TabularValidationMaterialization{}, err
	}
	graph, err := buildTabularIRGraph(model)
	if err != nil {
		return TabularValidationMaterialization{}, err
	}

	modelDigest := digestBytes(modelBytes)
	sourceDigest := digestBytes(sourceBytes)
	var output bytes.Buffer
	writer := csv.NewWriter(&output)
	header := []string{
		"row_id",
		"label",
		"scaled_logit",
		"polynomial_score",
		"plaintext_decision",
		"materialization_schema",
		"source_data_sha256",
		"source_model_sha256",
		"source_feature_space",
		"preprocessing_method",
	}
	for index := 0; index < model.InputDim; index++ {
		header = append(header, fmt.Sprintf("x_%d", index))
	}
	if err := writer.Write(header); err != nil {
		return TabularValidationMaterialization{},
			fmt.Errorf("write materialized validation header: %w", err)
	}

	for _, row := range rows {
		inputs := make(map[ir.NodeID]float64, len(row.Features))
		for index, feature := range row.Features {
			inputs[tabularInputID(index)] = feature
		}
		plainResult, err := fgruntime.EvalPlain(graph, inputs)
		if err != nil {
			return TabularValidationMaterialization{},
				fmt.Errorf(
					"evaluate source row %d plaintext graph: %w",
					row.ID,
					err,
				)
		}
		scaledLogit, err := evaluateTabularScaledLogit(
			model,
			row.Features,
		)
		if err != nil {
			return TabularValidationMaterialization{}, err
		}
		expectedScore, err := evaluateTabularScore(
			model.PolynomialScore.Formula,
			scaledLogit,
		)
		if err != nil {
			return TabularValidationMaterialization{}, err
		}
		if !closeFloatAtTolerance(
			plainResult.Output,
			expectedScore,
			1e-12,
		) {
			return TabularValidationMaterialization{},
				fmt.Errorf(
					"source row %d materialized score %.12g does not match graph %.12g",
					row.ID,
					expectedScore,
					plainResult.Output,
				)
		}
		decision := expectedScore >=
			model.PolynomialScore.DecisionThreshold
		record := []string{
			strconv.Itoa(row.ID),
			strconv.Itoa(row.Label),
			formatMaterializedFloat(scaledLogit),
			formatMaterializedFloat(expectedScore),
			strconv.FormatBool(decision),
			TabularValidationMaterializationSchemaV2,
			sourceDigest,
			modelDigest,
			string(resolvedDataSpace),
			preprocessingMethod,
		}
		for _, feature := range row.Features {
			record = append(record, formatMaterializedFloat(feature))
		}
		if err := writer.Write(record); err != nil {
			return TabularValidationMaterialization{},
				fmt.Errorf(
					"write materialized validation row %d: %w",
					row.ID,
					err,
				)
		}
	}
	writer.Flush()
	if err := writer.Error(); err != nil {
		return TabularValidationMaterialization{},
			fmt.Errorf("finalize materialized validation: %w", err)
	}

	if err := writeAtomicFile(
		validationPath,
		output.Bytes(),
		0o644,
	); err != nil {
		return TabularValidationMaterialization{}, err
	}

	return TabularValidationMaterialization{
		SchemaVersion: 2,
		DatasetID:     model.DatasetID,
		ModelID:       model.ModelID,
		Rows:          len(rows),

		ModelPath:      modelPath,
		SourceDataPath: sourceDataPath,
		ValidationPath: validationPath,

		ModelSHA256:      modelDigest,
		SourceDataSHA256: sourceDigest,
		ValidationSHA256: digestBytes(output.Bytes()),

		SourceFeatureSpace:  string(resolvedDataSpace),
		PreprocessingMethod: preprocessingMethod,
	}, nil
}

func parseTabularFeatureRows(
	data []byte,
	model tabularModelArtifact,
	requestedDataSpace TabularDataSpace,
) (
	[]tabularFeatureRow,
	TabularDataSpace,
	string,
	error,
) {
	reader := csv.NewReader(bytes.NewReader(data))
	rawHeader, err := reader.Read()
	if err != nil {
		return nil, "", "", fmt.Errorf(
			"read tabular source header: %w",
			err,
		)
	}
	columns := make(map[string]int, len(rawHeader))
	for index, rawName := range rawHeader {
		name := strings.TrimSpace(rawName)
		if name == "" {
			return nil, "", "", fmt.Errorf(
				"tabular source column %d is empty",
				index,
			)
		}
		if _, exists := columns[name]; exists {
			return nil, "", "", fmt.Errorf(
				"tabular source has duplicate column %q",
				name,
			)
		}
		columns[name] = index
	}
	for _, name := range []string{"row_id", "label"} {
		if _, exists := columns[name]; !exists {
			return nil, "", "", fmt.Errorf(
				"tabular source is missing column %q",
				name,
			)
		}
	}
	featureColumns, resolvedDataSpace, preprocessingMethod, err :=
		resolveTabularFeatureColumns(
			columns,
			model,
			requestedDataSpace,
		)
	if err != nil {
		return nil, "", "", err
	}

	rows := make([]tabularFeatureRow, 0)
	seen := make(map[int]bool)
	for rowNumber := 2; ; rowNumber++ {
		record, err := reader.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, "", "", fmt.Errorf(
				"read tabular source row %d: %w",
				rowNumber,
				err,
			)
		}
		if len(record) != len(rawHeader) {
			return nil, "", "", fmt.Errorf(
				"tabular source row %d has %d fields, expected %d",
				rowNumber,
				len(record),
				len(rawHeader),
			)
		}
		id, err := strconv.Atoi(
			strings.TrimSpace(record[columns["row_id"]]),
		)
		if err != nil {
			return nil, "", "", fmt.Errorf(
				"parse tabular source row %d row_id: %w",
				rowNumber,
				err,
			)
		}
		if seen[id] {
			return nil, "", "", fmt.Errorf(
				"tabular source has duplicate row_id %d",
				id,
			)
		}
		seen[id] = true
		label, err := strconv.Atoi(
			strings.TrimSpace(record[columns["label"]]),
		)
		if err != nil {
			return nil, "", "", fmt.Errorf(
				"parse tabular source row %d label: %w",
				rowNumber,
				err,
			)
		}
		if label != 0 && label != 1 {
			return nil, "", "", fmt.Errorf(
				"tabular source row %d label must be 0 or 1",
				rowNumber,
			)
		}
		features := make([]float64, model.InputDim)
		for index := range features {
			name := featureColumns[index]
			value, err := strconv.ParseFloat(
				strings.TrimSpace(record[columns[name]]),
				64,
			)
			if err != nil {
				return nil, "", "", fmt.Errorf(
					"parse tabular source row %d %s: %w",
					rowNumber,
					name,
					err,
				)
			}
			if !finite(value) {
				return nil, "", "", fmt.Errorf(
					"tabular source row %d %s is non-finite",
					rowNumber,
					name,
				)
			}
			if resolvedDataSpace == TabularDataSpaceRaw {
				value = (value - model.Standardization.Mean[index]) /
					model.Standardization.Std[index]
				if !finite(value) {
					return nil, "", "", fmt.Errorf(
						"tabular source row %d %s preprocessing produced a non-finite value",
						rowNumber,
						name,
					)
				}
			}
			features[index] = value
		}
		rows = append(rows, tabularFeatureRow{
			ID:       id,
			Label:    label,
			Features: features,
		})
	}
	if len(rows) == 0 {
		return nil, "", "", fmt.Errorf(
			"tabular source data is empty",
		)
	}
	return rows, resolvedDataSpace, preprocessingMethod, nil
}

func normalizeTabularDataSpace(
	value TabularDataSpace,
) (TabularDataSpace, error) {
	normalized := strings.TrimSpace(string(value))
	switch normalized {
	case "", string(TabularDataSpaceAuto):
		return TabularDataSpaceAuto, nil
	case "model", string(TabularDataSpaceModelInput):
		return TabularDataSpaceModelInput, nil
	case string(TabularDataSpaceRaw):
		return TabularDataSpaceRaw, nil
	default:
		return "", fmt.Errorf(
			"unsupported tabular data space %q; expected auto, model, or raw",
			value,
		)
	}
}

func resolveTabularFeatureColumns(
	columns map[string]int,
	model tabularModelArtifact,
	requested TabularDataSpace,
) ([]string, TabularDataSpace, string, error) {
	modelColumns := make([]string, model.InputDim)
	for index := range modelColumns {
		modelColumns[index] = fmt.Sprintf("x_%d", index)
	}
	modelColumnsPresent := allColumnsPresent(columns, modelColumns)
	modelColumnsExact := modelColumnsPresent &&
		hasOnlyExpectedIndexedColumns(columns, model.InputDim)

	rawMetadataErr := validateRawPreprocessingMetadata(model)
	var namedRawColumns []string
	var indexedRawColumns []string
	rawNamedPresent := false
	rawIndexedPresent := false
	if rawMetadataErr == nil {
		namedRawColumns = append(
			[]string(nil),
			model.SelectedFeatureNames...,
		)
		indexedRawColumns = make([]string, model.InputDim)
		for index, sourceIndex := range model.SelectedFeatureIndices {
			indexedRawColumns[index] = fmt.Sprintf(
				"x_%d",
				sourceIndex,
			)
		}
		rawNamedPresent = allColumnsPresent(
			columns,
			namedRawColumns,
		)
		rawIndexedPresent = allColumnsPresent(
			columns,
			indexedRawColumns,
		)
	}

	switch requested {
	case TabularDataSpaceModelInput:
		if !modelColumnsPresent {
			return nil, "", "", fmt.Errorf(
				"model-input data requires columns x_0 through x_%d",
				model.InputDim-1,
			)
		}
		if !modelColumnsExact {
			return nil, "", "", fmt.Errorf(
				"tabular source has unexpected model-input x_* columns for input_dim=%d",
				model.InputDim,
			)
		}
		return modelColumns,
			TabularDataSpaceModelInput,
			TabularPreprocessingIdentityV1,
			nil

	case TabularDataSpaceRaw:
		if rawMetadataErr != nil {
			return nil, "", "", rawMetadataErr
		}
		rawColumns, err := chooseRawFeatureColumns(
			namedRawColumns,
			rawNamedPresent,
			indexedRawColumns,
			rawIndexedPresent,
		)
		if err != nil {
			return nil, "", "", err
		}
		return rawColumns,
			TabularDataSpaceRaw,
			TabularPreprocessingSelectedStandardizationV1,
			nil

	case TabularDataSpaceAuto:
		if rawNamedPresent &&
			!sameStrings(namedRawColumns, modelColumns) {
			if modelColumnsExact || (rawIndexedPresent &&
				!sameStrings(namedRawColumns, indexedRawColumns)) {
				return nil, "", "", fmt.Errorf(
					"tabular source feature space is ambiguous; use --data-space model or --data-space raw",
				)
			}
			return namedRawColumns,
				TabularDataSpaceRaw,
				TabularPreprocessingSelectedStandardizationV1,
				nil
		}
		if modelColumnsExact {
			return modelColumns,
				TabularDataSpaceModelInput,
				TabularPreprocessingIdentityV1,
				nil
		}
		if rawIndexedPresent {
			return indexedRawColumns,
				TabularDataSpaceRaw,
				TabularPreprocessingSelectedStandardizationV1,
				nil
		}
		if rawMetadataErr != nil {
			return nil, "", "", fmt.Errorf(
				"cannot infer tabular source feature space and raw preprocessing metadata is invalid: %w",
				rawMetadataErr,
			)
		}
		return nil, "", "", fmt.Errorf(
			"cannot infer tabular source feature space; expected exact model-input x_0..x_%d columns or the model's selected raw feature names/indices",
			model.InputDim-1,
		)
	default:
		return nil, "", "", fmt.Errorf(
			"unsupported normalized tabular data space %q",
			requested,
		)
	}
}

func validateRawPreprocessingMetadata(
	model tabularModelArtifact,
) error {
	if len(model.SelectedFeatureIndices) != model.InputDim ||
		len(model.SelectedFeatureNames) != model.InputDim ||
		len(model.Standardization.Mean) != model.InputDim ||
		len(model.Standardization.Std) != model.InputDim {
		return fmt.Errorf(
			"raw data requires %d selected feature indices, names, means, and standard deviations in the model artifact",
			model.InputDim,
		)
	}

	seenIndices := make(map[int]bool, model.InputDim)
	seenNames := make(map[string]bool, model.InputDim)
	for index := 0; index < model.InputDim; index++ {
		sourceIndex := model.SelectedFeatureIndices[index]
		if sourceIndex < 0 || seenIndices[sourceIndex] {
			return fmt.Errorf(
				"raw preprocessing selected feature index %d is invalid or duplicated",
				sourceIndex,
			)
		}
		seenIndices[sourceIndex] = true

		name := strings.TrimSpace(model.SelectedFeatureNames[index])
		if name == "" || name != model.SelectedFeatureNames[index] ||
			seenNames[name] {
			return fmt.Errorf(
				"raw preprocessing selected feature name %q is invalid or duplicated",
				model.SelectedFeatureNames[index],
			)
		}
		seenNames[name] = true

		mean := model.Standardization.Mean[index]
		std := model.Standardization.Std[index]
		if !finite(mean) || !finite(std) || std <= 0 {
			return fmt.Errorf(
				"raw preprocessing feature %d requires finite mean and positive finite standard deviation",
				index,
			)
		}
	}
	return nil
}

func chooseRawFeatureColumns(
	named []string,
	namedPresent bool,
	indexed []string,
	indexedPresent bool,
) ([]string, error) {
	if namedPresent && indexedPresent &&
		!sameStrings(named, indexed) {
		return nil, fmt.Errorf(
			"raw data contains both named and indexed selected features; remove one representation",
		)
	}
	if namedPresent {
		return named, nil
	}
	if indexedPresent {
		return indexed, nil
	}
	return nil, fmt.Errorf(
		"raw data is missing the model's selected feature names and indexed x_* columns",
	)
}

func allColumnsPresent(
	columns map[string]int,
	required []string,
) bool {
	for _, name := range required {
		if _, exists := columns[name]; !exists {
			return false
		}
	}
	return true
}

func hasOnlyExpectedIndexedColumns(
	columns map[string]int,
	inputDim int,
) bool {
	for name := range columns {
		if !strings.HasPrefix(name, "x_") {
			continue
		}
		index, err := strconv.Atoi(strings.TrimPrefix(name, "x_"))
		if err != nil || index < 0 || index >= inputDim {
			return false
		}
	}
	return true
}

func sameStrings(left []string, right []string) bool {
	if len(left) != len(right) {
		return false
	}
	for index := range left {
		if left[index] != right[index] {
			return false
		}
	}
	return true
}

func evaluateTabularScaledLogit(
	model tabularModelArtifact,
	features []float64,
) (float64, error) {
	scaled := model.ScaledModelForCKKS
	switch model.ModelType {
	case "linear_poly3":
		return affineValue(
			features,
			scaled.Weights,
			scaled.Bias,
		)
	case "mlp_square_linear_score", "mlp_square_poly3":
		hidden := make([]float64, len(scaled.HiddenWeights))
		for index, weights := range scaled.HiddenWeights {
			value, err := affineValue(
				features,
				weights,
				scaled.HiddenBias[index],
			)
			if err != nil {
				return 0, err
			}
			hidden[index] = value * value
		}
		return affineValue(
			hidden,
			scaled.OutputWeights,
			scaled.OutputBias,
		)
	default:
		return 0, fmt.Errorf(
			"unsupported tabular model_type %q",
			model.ModelType,
		)
	}
}

func affineValue(
	values []float64,
	weights []float64,
	bias float64,
) (float64, error) {
	if len(values) != len(weights) {
		return 0, fmt.Errorf(
			"affine input dimension %d does not match weights %d",
			len(values),
			len(weights),
		)
	}
	result := bias
	for index, value := range values {
		result += value * weights[index]
	}
	if !finite(result) {
		return 0, fmt.Errorf("materialized affine value is non-finite")
	}
	return result, nil
}

func evaluateTabularScore(
	formula string,
	z float64,
) (float64, error) {
	var score float64
	switch formula {
	case "0.5 + 0.197*z":
		score = 0.5 + 0.197*z
	case "0.5 + 0.197*z - 0.004*z^3":
		score = 0.5 + 0.197*z - 0.004*z*z*z
	default:
		return 0, fmt.Errorf(
			"unsupported tabular score formula %q",
			formula,
		)
	}
	if !finite(score) {
		return 0, fmt.Errorf("materialized score is non-finite")
	}
	return score, nil
}

func formatMaterializedFloat(value float64) string {
	if math.Abs(value) < 1e-18 {
		value = 0
	}
	return strconv.FormatFloat(value, 'g', 17, 64)
}

func writeAtomicFile(
	path string,
	data []byte,
	mode os.FileMode,
) error {
	directory := filepath.Dir(path)
	temporary, err := os.CreateTemp(
		directory,
		"."+filepath.Base(path)+".tmp-*",
	)
	if err != nil {
		return fmt.Errorf(
			"create temporary materialized validation: %w",
			err,
		)
	}
	temporaryPath := temporary.Name()
	cleanup := func() {
		_ = temporary.Close()
		_ = os.Remove(temporaryPath)
	}
	if _, err := temporary.Write(data); err != nil {
		cleanup()
		return fmt.Errorf(
			"write temporary materialized validation: %w",
			err,
		)
	}
	if err := temporary.Chmod(mode); err != nil {
		cleanup()
		return fmt.Errorf(
			"chmod temporary materialized validation: %w",
			err,
		)
	}
	if err := temporary.Sync(); err != nil {
		cleanup()
		return fmt.Errorf(
			"sync temporary materialized validation: %w",
			err,
		)
	}
	if err := temporary.Close(); err != nil {
		_ = os.Remove(temporaryPath)
		return fmt.Errorf(
			"close temporary materialized validation: %w",
			err,
		)
	}
	if err := os.Rename(temporaryPath, path); err != nil {
		_ = os.Remove(temporaryPath)
		return fmt.Errorf(
			"replace materialized validation %s: %w",
			path,
			err,
		)
	}
	return nil
}
