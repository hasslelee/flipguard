package certify

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
)

type tabularCertificationModelArtifact struct {
	DatasetID string `json:"dataset_id"`
	ModelID   string `json:"model_id"`

	RandomState *int     `json:"random_state"`
	TestSize    *float64 `json:"test_size"`
	TestSamples int      `json:"test_samples"`

	PolynomialScore struct {
		DecisionThreshold *float64 `json:"decision_threshold"`
	} `json:"polynomial_score"`
}

type tabularCertificationModelScope struct {
	Threshold float64
	SplitID   string

	RandomState int
	TestSize    float64
	TestSamples int

	EvaluatedRows int
	ModelPath     string
}

func loadTabularCertificationModelScope(
	modelRoot string,
	workloadKey tabularWorkloadKey,
	candidateKeys []tabularCandidateKey,
	grouped map[tabularCandidateKey]map[int]tabularRunStatusRow,
	expectedRepeats int,
) (tabularCertificationModelScope, error) {
	modelPath := filepath.Join(
		modelRoot,
		workloadKey.DatasetID,
		workloadKey.ModelID,
		"model.json",
	)

	data, err := os.ReadFile(modelPath)
	if err != nil {
		return tabularCertificationModelScope{}, fmt.Errorf(
			"read certification model artifact %s: %w",
			modelPath,
			err,
		)
	}

	var artifact tabularCertificationModelArtifact

	if err := json.Unmarshal(data, &artifact); err != nil {
		return tabularCertificationModelScope{}, fmt.Errorf(
			"parse certification model artifact %s: %w",
			modelPath,
			err,
		)
	}

	if artifact.DatasetID != workloadKey.DatasetID {
		return tabularCertificationModelScope{}, fmt.Errorf(
			"model artifact %s dataset ID mismatch: got %q, expected %q",
			modelPath,
			artifact.DatasetID,
			workloadKey.DatasetID,
		)
	}
	if artifact.ModelID != workloadKey.ModelID {
		return tabularCertificationModelScope{}, fmt.Errorf(
			"model artifact %s model ID mismatch: got %q, expected %q",
			modelPath,
			artifact.ModelID,
			workloadKey.ModelID,
		)
	}
	if artifact.RandomState == nil {
		return tabularCertificationModelScope{}, fmt.Errorf(
			"model artifact %s is missing random_state",
			modelPath,
		)
	}
	if artifact.TestSize == nil ||
		!isFinite(*artifact.TestSize) ||
		*artifact.TestSize <= 0 ||
		*artifact.TestSize >= 1 {
		return tabularCertificationModelScope{}, fmt.Errorf(
			"model artifact %s test_size must be present and in (0, 1)",
			modelPath,
		)
	}
	if artifact.TestSamples <= 0 {
		return tabularCertificationModelScope{}, fmt.Errorf(
			"model artifact %s test_samples must be positive",
			modelPath,
		)
	}
	if artifact.PolynomialScore.DecisionThreshold == nil {
		return tabularCertificationModelScope{}, fmt.Errorf(
			"model artifact %s is missing polynomial_score.decision_threshold",
			modelPath,
		)
	}

	threshold :=
		*artifact.PolynomialScore.DecisionThreshold

	if !isFinite(threshold) {
		return tabularCertificationModelScope{}, fmt.Errorf(
			"model artifact %s decision threshold must be finite",
			modelPath,
		)
	}

	evaluatedRows := 0

searchSuccessfulRun:
	for _, candidateKey := range candidateKeys {
		repeatRows := grouped[candidateKey]

		for repeat := 1; repeat <= expectedRepeats; repeat++ {
			row, exists := repeatRows[repeat]
			if !exists || row.Status != "ok" {
				continue
			}

			metadata, err := loadTabularArtifactMetadata(
				row.SummaryPath,
			)
			if err != nil {
				return tabularCertificationModelScope{}, fmt.Errorf(
					"load scope source summary for tag %s: %w",
					row.Tag,
					err,
				)
			}

			if metadata.DatasetID != workloadKey.DatasetID ||
				metadata.ModelID != workloadKey.ModelID {
				return tabularCertificationModelScope{}, fmt.Errorf(
					"scope source tag %s summary identity mismatch",
					row.Tag,
				)
			}

			evaluatedRows = metadata.EvaluatedRows
			break searchSuccessfulRun
		}
	}

	if evaluatedRows <= 0 {
		return tabularCertificationModelScope{}, fmt.Errorf(
			"workload %s__%s has no successful summary from which evaluated rows can be determined",
			workloadKey.DatasetID,
			workloadKey.ModelID,
		)
	}
	if evaluatedRows > artifact.TestSamples {
		return tabularCertificationModelScope{}, fmt.Errorf(
			"workload %s__%s evaluated rows %d exceed model test_samples %d",
			workloadKey.DatasetID,
			workloadKey.ModelID,
			evaluatedRows,
			artifact.TestSamples,
		)
	}

	testSizeText := strconv.FormatFloat(
		*artifact.TestSize,
		'g',
		-1,
		64,
	)

	splitID := fmt.Sprintf(
		"test_seed%d_ratio%s_prefix%d_of%d",
		*artifact.RandomState,
		testSizeText,
		evaluatedRows,
		artifact.TestSamples,
	)

	return tabularCertificationModelScope{
		Threshold: threshold,
		SplitID:   splitID,

		RandomState: *artifact.RandomState,
		TestSize:    *artifact.TestSize,
		TestSamples: artifact.TestSamples,

		EvaluatedRows: evaluatedRows,
		ModelPath:     modelPath,
	}, nil
}
