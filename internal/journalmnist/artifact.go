package journalmnist

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"strconv"
	"strings"
)

const (
	ModelArtifactSchemaV1 = "flipguard_journal_multiclass_model_v1"
	MLPModelType          = "mlp_square_multiclass"
	LeNetModelType        = "lenet5_small_square_multiclass"
)

// ArtifactBinding records the exact input bytes used to train or evaluate a
// journal-extension model.
type ArtifactBinding struct {
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
}

// ModelArtifact is the stable, execution-facing subset of the generated MNIST
// model file. Map-valued descriptive metadata is retained so replay tools can
// reject a changed architecture without depending on the training command.
type ModelArtifact struct {
	SchemaVersion     string             `json:"schema_version"`
	SourceCommit      string             `json:"source_commit"`
	DatasetID         string             `json:"dataset_id"`
	ModelID           string             `json:"model_id"`
	ModelType         string             `json:"model_type"`
	GraphAdapterID    string             `json:"graph_adapter_id"`
	GraphFormula      string             `json:"graph_formula"`
	Architecture      map[string]any     `json:"architecture"`
	Preprocessing     map[string]any     `json:"preprocessing"`
	Source            ArtifactBinding    `json:"source"`
	SplitManifest     ArtifactBinding    `json:"split_manifest"`
	Training          map[string]any     `json:"training"`
	PolicyBinding     map[string]any     `json:"policy_binding"`
	PlaintextAccuracy map[string]float64 `json:"plaintext_accuracy"`
	TrainingHistory   []TrainingEpoch    `json:"training_history"`
	Parameters        []float64          `json:"parameters"`
}

// PartitionRow is one byte-replayed configuration-validation or locked-audit
// row. Pixels remain uint8 until the frozen pixel/255 model preprocessing.
type PartitionRow struct {
	RowID           int
	SampleID        string
	SourceIndex     int
	SourcePartition string
	Role            string
	Label           int
	Pixels          [PixelCount]uint8
}

func LoadModelArtifact(path string) (ModelArtifact, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return ModelArtifact{}, fmt.Errorf("read MNIST model artifact: %w", err)
	}
	var artifact ModelArtifact
	if err := json.Unmarshal(data, &artifact); err != nil {
		return ModelArtifact{}, fmt.Errorf("parse MNIST model artifact: %w", err)
	}
	if err := artifact.Validate(); err != nil {
		return ModelArtifact{}, err
	}
	return artifact, nil
}

func (artifact ModelArtifact) Validate() error {
	if artifact.SchemaVersion != ModelArtifactSchemaV1 {
		return fmt.Errorf("unsupported MNIST model schema %q", artifact.SchemaVersion)
	}
	if strings.TrimSpace(artifact.SourceCommit) == "" ||
		strings.TrimSpace(artifact.DatasetID) == "" ||
		strings.TrimSpace(artifact.ModelID) == "" ||
		strings.TrimSpace(artifact.GraphAdapterID) == "" ||
		strings.TrimSpace(artifact.GraphFormula) == "" {
		return fmt.Errorf("MNIST model artifact identity is incomplete")
	}
	for name, value := range artifact.PlaintextAccuracy {
		if !finiteArtifactValue(value) || value < 0 || value > 1 {
			return fmt.Errorf("plaintext accuracy %s is invalid", name)
		}
	}
	switch artifact.ModelType {
	case MLPModelType:
		if artifact.ModelID != MLPModelID {
			return fmt.Errorf("MLP model ID %q; expected %q", artifact.ModelID, MLPModelID)
		}
		return (MLPModel{Parameters: artifact.Parameters}).Validate()
	case LeNetModelType:
		if artifact.ModelID != LeNetModelID {
			return fmt.Errorf("LeNet model ID %q; expected %q", artifact.ModelID, LeNetModelID)
		}
		return (LeNetModel{Parameters: artifact.Parameters}).Validate()
	default:
		return fmt.Errorf("unsupported MNIST model type %q", artifact.ModelType)
	}
}

func (artifact ModelArtifact) Logits(row PartitionRow) ([ClassCount]float64, error) {
	sample := Sample{SourceIndex: row.SourceIndex, Label: row.Label, Pixels: row.Pixels}
	switch artifact.ModelType {
	case MLPModelType:
		return (MLPModel{Parameters: artifact.Parameters}).Logits(sample), nil
	case LeNetModelType:
		return (LeNetModel{Parameters: artifact.Parameters}).Logits(sample), nil
	default:
		return [ClassCount]float64{}, fmt.Errorf("unsupported MNIST model type %q", artifact.ModelType)
	}
}

func LoadPartitionCSV(path string, expectedRole string) ([]PartitionRow, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("open MNIST partition: %w", err)
	}
	defer file.Close()
	records, err := csv.NewReader(file).ReadAll()
	if err != nil {
		return nil, fmt.Errorf("read MNIST partition: %w", err)
	}
	if len(records) != ConfigValidationPerClass*ClassCount+1 {
		return nil, fmt.Errorf("MNIST partition has %d rows; expected %d", len(records)-1, ConfigValidationPerClass*ClassCount)
	}
	header := make(map[string]int, len(records[0]))
	for index, name := range records[0] {
		header[name] = index
	}
	required := []string{"row_id", "sample_id", "source_index", "source_partition", "role", "label"}
	for index := 0; index < PixelCount; index++ {
		required = append(required, fmt.Sprintf("pixel_%03d", index))
	}
	for _, name := range required {
		if _, ok := header[name]; !ok {
			return nil, fmt.Errorf("MNIST partition is missing column %s", name)
		}
	}
	rows := make([]PartitionRow, 0, len(records)-1)
	seenSample := make(map[string]bool, len(records)-1)
	classCounts := [ClassCount]int{}
	for csvIndex, record := range records[1:] {
		field := func(name string) (string, error) {
			index := header[name]
			if index >= len(record) {
				return "", fmt.Errorf("row %d column %s is missing", csvIndex+2, name)
			}
			value := strings.TrimSpace(record[index])
			if value == "" {
				return "", fmt.Errorf("row %d column %s is empty", csvIndex+2, name)
			}
			return value, nil
		}
		parseInt := func(name string) (int, error) {
			value, parseErr := field(name)
			if parseErr != nil {
				return 0, parseErr
			}
			parsed, parseErr := strconv.Atoi(value)
			if parseErr != nil {
				return 0, fmt.Errorf("row %d column %s: %w", csvIndex+2, name, parseErr)
			}
			return parsed, nil
		}
		rowID, err := parseInt("row_id")
		if err != nil {
			return nil, err
		}
		if rowID != csvIndex {
			return nil, fmt.Errorf("MNIST row_id %d; expected ordered row %d", rowID, csvIndex)
		}
		sampleID, err := field("sample_id")
		if err != nil {
			return nil, err
		}
		if seenSample[sampleID] {
			return nil, fmt.Errorf("duplicate MNIST sample ID %s", sampleID)
		}
		seenSample[sampleID] = true
		sourceIndex, err := parseInt("source_index")
		if err != nil {
			return nil, err
		}
		sourcePartition, err := field("source_partition")
		if err != nil {
			return nil, err
		}
		role, err := field("role")
		if err != nil {
			return nil, err
		}
		if role != expectedRole {
			return nil, fmt.Errorf("MNIST role %q; expected %q", role, expectedRole)
		}
		label, err := parseInt("label")
		if err != nil || label < 0 || label >= ClassCount {
			return nil, fmt.Errorf("row %d has invalid label", csvIndex+2)
		}
		row := PartitionRow{RowID: rowID, SampleID: sampleID, SourceIndex: sourceIndex, SourcePartition: sourcePartition, Role: role, Label: label}
		for pixelIndex := 0; pixelIndex < PixelCount; pixelIndex++ {
			value, parseErr := parseInt(fmt.Sprintf("pixel_%03d", pixelIndex))
			if parseErr != nil || value < 0 || value > 255 {
				return nil, fmt.Errorf("row %d pixel %d is invalid", csvIndex+2, pixelIndex)
			}
			row.Pixels[pixelIndex] = uint8(value)
		}
		classCounts[label]++
		rows = append(rows, row)
	}
	for label, count := range classCounts {
		if count != ConfigValidationPerClass {
			return nil, fmt.Errorf("MNIST class %d count %d; expected %d", label, count, ConfigValidationPerClass)
		}
	}
	return rows, nil
}

func finiteArtifactValue(value float64) bool {
	return !math.IsNaN(value) && !math.IsInf(value, 0)
}
