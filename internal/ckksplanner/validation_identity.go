package ckksplanner

import (
	"bytes"
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

	"github.com/hasslelee/flipguard/internal/ir"
	fgruntime "github.com/hasslelee/flipguard/internal/runtime"
)

const ValidationSemanticIdentitySchemaV1 = "validation_semantic_digest_v1"

// ValidationSemanticIdentityOptions binds the metadata that is not stored in
// the CSV but is part of one formal workload-partition execution identity.
type ValidationSemanticIdentityOptions struct {
	ModelPath      string
	ValidationPath string
	DatasetID      string
	ModelID        string
	SplitID        string
	PartitionRole  string
	MarginFloor    float64
}

// ValidationFileStructure records byte- and CSV-level provenance separately
// from execution semantics.
type ValidationFileStructure struct {
	RawSHA256            string   `json:"raw_sha256"`
	ByteSize             int      `json:"byte_size"`
	NewlineStyle         string   `json:"newline_style"`
	Header               []string `json:"header"`
	ColumnCount          int      `json:"column_count"`
	RowCount             int      `json:"row_count"`
	OrderedRowIDs        []string `json:"ordered_row_ids"`
	OrderedRowIDDigest   string   `json:"ordered_row_id_digest"`
	DuplicateRowIDs      []string `json:"duplicate_row_ids"`
	FirstRow             []string `json:"first_row"`
	LastRow              []string `json:"last_row"`
	FeatureFieldCount    int      `json:"feature_field_count"`
	NumericSerialization string   `json:"numeric_serialization"`
}

// ValidationSemanticIdentity is the canonical, model-replayed identity of the
// values consumed by encrypted evaluation and decision certification.
type ValidationSemanticIdentity struct {
	SchemaVersion string `json:"schema_version"`

	DatasetID     string `json:"dataset_id"`
	ModelID       string `json:"model_id"`
	SplitID       string `json:"split_id"`
	PartitionRole string `json:"partition_role"`

	ModelPath   string `json:"model_path"`
	ModelSHA256 string `json:"model_sha256"`
	InputDim    int    `json:"input_dim"`

	OrderedFeatureNames []string `json:"ordered_feature_names"`
	Threshold           float64  `json:"threshold"`
	ThresholdBits       string   `json:"threshold_bits"`
	MarginFloor         float64  `json:"margin_floor"`

	File ValidationFileStructure `json:"file"`

	FeatureSemanticDigest    string `json:"feature_semantic_digest"`
	DecisionSemanticDigest   string `json:"decision_semantic_digest"`
	ValidationSemanticDigest string `json:"validation_semantic_digest"`
	StoredScoreDigest        string `json:"stored_score_digest"`

	ValidationSamples int `json:"validation_samples"`
	VCert             int `json:"v_cert"`
	VAmb              int `json:"v_amb"`
}

type validationCanonicalRow struct {
	id       string
	features []float64
	score    float64
	decision bool
}

// ComputeValidationSemanticIdentity parses a validation artifact, rejects
// malformed identities, replays the model graph, and hashes canonical IEEE-754
// binary64 values rather than their CSV spelling.
func ComputeValidationSemanticIdentity(
	options ValidationSemanticIdentityOptions,
) (ValidationSemanticIdentity, error) {
	if strings.TrimSpace(options.ModelPath) == "" ||
		strings.TrimSpace(options.ValidationPath) == "" {
		return ValidationSemanticIdentity{},
			fmt.Errorf("model and validation paths are required")
	}
	for name, value := range map[string]string{
		"dataset ID":     options.DatasetID,
		"model ID":       options.ModelID,
		"split ID":       options.SplitID,
		"partition role": options.PartitionRole,
	} {
		if strings.TrimSpace(value) == "" {
			return ValidationSemanticIdentity{},
				fmt.Errorf("%s is required", name)
		}
	}
	if !finite(options.MarginFloor) || options.MarginFloor < 0 {
		return ValidationSemanticIdentity{},
			fmt.Errorf("margin floor must be finite and non-negative")
	}

	modelBytes, err := os.ReadFile(options.ModelPath)
	if err != nil {
		return ValidationSemanticIdentity{},
			fmt.Errorf("read model artifact: %w", err)
	}
	model := tabularModelArtifact{}
	if err := json.Unmarshal(modelBytes, &model); err != nil {
		return ValidationSemanticIdentity{},
			fmt.Errorf("parse model artifact: %w", err)
	}
	if err := validateTabularModel(model); err != nil {
		return ValidationSemanticIdentity{}, err
	}
	if model.DatasetID != options.DatasetID ||
		model.ModelID != options.ModelID {
		return ValidationSemanticIdentity{}, fmt.Errorf(
			"model identity %s/%s does not match requested %s/%s",
			model.DatasetID,
			model.ModelID,
			options.DatasetID,
			options.ModelID,
		)
	}

	validationBytes, err := os.ReadFile(options.ValidationPath)
	if err != nil {
		return ValidationSemanticIdentity{},
			fmt.Errorf("read validation artifact: %w", err)
	}
	structure, err := inspectValidationCSV(
		validationBytes,
		model.InputDim,
	)
	if err != nil {
		return ValidationSemanticIdentity{}, err
	}
	samples, _, err := parseTabularValidation(
		validationBytes,
		model.InputDim,
	)
	if err != nil {
		return ValidationSemanticIdentity{}, err
	}
	graph, err := buildTabularIRGraph(model)
	if err != nil {
		return ValidationSemanticIdentity{}, err
	}

	rows := make([]validationCanonicalRow, 0, len(samples))
	storedScores := make(map[string]float64, len(samples))
	sampleOrder := make([]string, 0, len(samples))
	vCert := 0
	vAmb := 0
	threshold := normalizeSemanticFloat(
		model.PolynomialScore.DecisionThreshold,
	)
	for rowIndex, sample := range samples {
		inputs := make(map[ir.NodeID]float64, len(sample.Features))
		features := make([]float64, len(sample.Features))
		for featureIndex, feature := range sample.Features {
			feature = normalizeSemanticFloat(feature)
			features[featureIndex] = feature
			inputs[tabularInputID(featureIndex)] = feature
		}
		plainResult, err := fgruntime.EvalPlain(graph, inputs)
		if err != nil {
			return ValidationSemanticIdentity{}, fmt.Errorf(
				"evaluate validation row %d plaintext graph: %w",
				rowIndex+2,
				err,
			)
		}
		score := normalizeSemanticFloat(plainResult.Output)
		if !finite(score) {
			return ValidationSemanticIdentity{}, fmt.Errorf(
				"validation row %d graph score is non-finite",
				rowIndex+2,
			)
		}
		if !closeFloatAtTolerance(score, sample.PlainScore, 1e-9) {
			return ValidationSemanticIdentity{}, fmt.Errorf(
				"validation row %d stored score %.17g does not match graph %.17g",
				rowIndex+2,
				sample.PlainScore,
				score,
			)
		}
		decision := score >= threshold
		if decision != sample.PlainDecision {
			return ValidationSemanticIdentity{}, fmt.Errorf(
				"validation row %d stored decision does not match replay",
				rowIndex+2,
			)
		}
		if math.Abs(score-threshold) <= options.MarginFloor {
			vAmb++
		} else {
			vCert++
		}
		rows = append(rows, validationCanonicalRow{
			id:       sample.ID,
			features: features,
			score:    score,
			decision: decision,
		})
		sampleOrder = append(sampleOrder, sample.ID)
		storedScores[sample.ID] = sample.PlainScore
	}

	featureNames := make([]string, model.InputDim)
	for index := range featureNames {
		featureNames[index] = fmt.Sprintf("x_%d", index)
	}
	structure.OrderedRowIDs = append(
		[]string(nil),
		sampleOrder...,
	)
	structure.OrderedRowIDDigest = digestCanonicalRowIDs(rows)

	identity := ValidationSemanticIdentity{
		SchemaVersion:          ValidationSemanticIdentitySchemaV1,
		DatasetID:              options.DatasetID,
		ModelID:                options.ModelID,
		SplitID:                options.SplitID,
		PartitionRole:          options.PartitionRole,
		ModelPath:              options.ModelPath,
		ModelSHA256:            digestBytes(modelBytes),
		InputDim:               model.InputDim,
		OrderedFeatureNames:    featureNames,
		Threshold:              threshold,
		ThresholdBits:          floatBitsHex(threshold),
		MarginFloor:            normalizeSemanticFloat(options.MarginFloor),
		File:                   structure,
		FeatureSemanticDigest:  digestCanonicalFeatures(rows),
		DecisionSemanticDigest: digestCanonicalDecisions(rows),
		StoredScoreDigest: digestValidationScores(
			sampleOrder,
			storedScores,
		),
		ValidationSamples: len(rows),
		VCert:             vCert,
		VAmb:              vAmb,
	}
	identity.ValidationSemanticDigest = digestCanonicalValidation(
		identity,
		rows,
	)
	return identity, nil
}

func inspectValidationCSV(
	data []byte,
	inputDim int,
) (ValidationFileStructure, error) {
	reader := csv.NewReader(bytes.NewReader(data))
	records := make([][]string, 0)
	for {
		record, err := reader.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			return ValidationFileStructure{},
				fmt.Errorf("inspect validation CSV: %w", err)
		}
		records = append(records, append([]string(nil), record...))
	}
	if len(records) < 2 {
		return ValidationFileStructure{},
			fmt.Errorf("validation CSV requires a header and at least one row")
	}
	header := records[0]
	rowIDIndex := -1
	featureCount := 0
	for index, name := range header {
		switch strings.TrimSpace(name) {
		case "row_id":
			rowIDIndex = index
		}
		if strings.HasPrefix(strings.TrimSpace(name), "x_") {
			featureCount++
		}
	}
	if rowIDIndex < 0 {
		return ValidationFileStructure{},
			fmt.Errorf("validation CSV has no row_id column")
	}
	if featureCount != inputDim {
		return ValidationFileStructure{}, fmt.Errorf(
			"validation CSV has %d x_i fields, expected %d",
			featureCount,
			inputDim,
		)
	}
	seen := map[string]bool{}
	duplicates := make([]string, 0)
	rowIDs := make([]string, 0, len(records)-1)
	for rowNumber, record := range records[1:] {
		if len(record) != len(header) {
			return ValidationFileStructure{}, fmt.Errorf(
				"validation CSV row %d has %d columns, expected %d",
				rowNumber+2,
				len(record),
				len(header),
			)
		}
		id := strings.TrimSpace(record[rowIDIndex])
		if seen[id] {
			duplicates = append(duplicates, id)
		}
		seen[id] = true
		rowIDs = append(rowIDs, id)
	}
	if len(duplicates) != 0 {
		return ValidationFileStructure{}, fmt.Errorf(
			"validation CSV has duplicate row IDs %v",
			duplicates,
		)
	}
	return ValidationFileStructure{
		RawSHA256:            digestBytes(data),
		ByteSize:             len(data),
		NewlineStyle:         detectNewlineStyle(data),
		Header:               append([]string(nil), header...),
		ColumnCount:          len(header),
		RowCount:             len(records) - 1,
		OrderedRowIDs:        rowIDs,
		DuplicateRowIDs:      duplicates,
		FirstRow:             append([]string(nil), records[1]...),
		LastRow:              append([]string(nil), records[len(records)-1]...),
		FeatureFieldCount:    featureCount,
		NumericSerialization: detectNumericSerialization(records),
	}, nil
}

func detectNewlineStyle(data []byte) string {
	crlf := bytes.Count(data, []byte("\r\n"))
	lf := bytes.Count(data, []byte("\n"))
	switch {
	case lf == 0:
		return "NONE"
	case crlf == 0:
		return "LF"
	case crlf == lf:
		return "CRLF"
	default:
		return "MIXED"
	}
}

func detectNumericSerialization(records [][]string) string {
	hasInteger := false
	hasFixed := false
	hasScientific := false
	for _, record := range records[1:] {
		for _, raw := range record {
			value := strings.TrimSpace(raw)
			if value == "" {
				continue
			}
			if _, err := strconv.ParseFloat(value, 64); err != nil {
				continue
			}
			switch {
			case strings.ContainsAny(value, "eE"):
				hasScientific = true
			case strings.Contains(value, "."):
				hasFixed = true
			default:
				hasInteger = true
			}
		}
	}
	forms := make([]string, 0, 3)
	if hasInteger {
		forms = append(forms, "integer")
	}
	if hasFixed {
		forms = append(forms, "fixed_decimal")
	}
	if hasScientific {
		forms = append(forms, "scientific")
	}
	if len(forms) == 0 {
		return "none"
	}
	return strings.Join(forms, "+") + "_parsed_as_binary64"
}

func digestCanonicalRowIDs(rows []validationCanonicalRow) string {
	encoder := newSemanticEncoder("ordered_row_ids_v1")
	for _, row := range rows {
		encoder.writeString(row.id)
	}
	return encoder.digest()
}

func digestCanonicalFeatures(rows []validationCanonicalRow) string {
	encoder := newSemanticEncoder("ordered_feature_semantics_v1")
	for _, row := range rows {
		encoder.writeString(row.id)
		for _, value := range row.features {
			encoder.writeFloat(value)
		}
	}
	return encoder.digest()
}

func digestCanonicalDecisions(rows []validationCanonicalRow) string {
	encoder := newSemanticEncoder("ordered_decision_semantics_v1")
	for _, row := range rows {
		encoder.writeString(row.id)
		encoder.writeFloat(row.score)
		encoder.writeBool(row.decision)
	}
	return encoder.digest()
}

func digestCanonicalValidation(
	identity ValidationSemanticIdentity,
	rows []validationCanonicalRow,
) string {
	encoder := newSemanticEncoder(ValidationSemanticIdentitySchemaV1)
	encoder.writeString(identity.DatasetID)
	encoder.writeString(identity.ModelID)
	encoder.writeString(identity.SplitID)
	encoder.writeString(identity.PartitionRole)
	encoder.writeString(identity.ModelSHA256)
	encoder.writeUint64(uint64(identity.InputDim))
	for _, name := range identity.OrderedFeatureNames {
		encoder.writeString(name)
	}
	encoder.writeFloat(identity.Threshold)
	for _, row := range rows {
		encoder.writeString(row.id)
		for _, feature := range row.features {
			encoder.writeFloat(feature)
		}
		encoder.writeFloat(row.score)
		encoder.writeBool(row.decision)
	}
	return encoder.digest()
}

type semanticEncoder struct {
	hasher io.Writer
	sum    interface{ Sum([]byte) []byte }
}

func newSemanticEncoder(magic string) *semanticEncoder {
	hasher := sha256.New()
	encoder := &semanticEncoder{hasher: hasher, sum: hasher}
	encoder.writeString(magic)
	return encoder
}

func (encoder *semanticEncoder) writeUint64(value uint64) {
	var encoded [8]byte
	binary.BigEndian.PutUint64(encoded[:], value)
	_, _ = encoder.hasher.Write(encoded[:])
}

func (encoder *semanticEncoder) writeString(value string) {
	encoder.writeUint64(uint64(len(value)))
	_, _ = encoder.hasher.Write([]byte(value))
}

func (encoder *semanticEncoder) writeFloat(value float64) {
	encoder.writeUint64(math.Float64bits(normalizeSemanticFloat(value)))
}

func (encoder *semanticEncoder) writeBool(value bool) {
	if value {
		encoder.writeUint64(1)
		return
	}
	encoder.writeUint64(0)
}

func (encoder *semanticEncoder) digest() string {
	return "sha256:" + hex.EncodeToString(encoder.sum.Sum(nil))
}

func normalizeSemanticFloat(value float64) float64 {
	if value == 0 {
		return 0
	}
	return value
}

func floatBitsHex(value float64) string {
	return fmt.Sprintf("0x%016x", math.Float64bits(
		normalizeSemanticFloat(value),
	))
}
