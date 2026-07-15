package certify

import (
	"math"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
)

func TestLoadAndAggregateTabularCandidate(
	t *testing.T,
) {
	root := t.TempDir()

	run1 := writeTabularArtifactRun(
		t,
		root,
		"r1",
		"banknote",
		"linear_poly3",
		100,
		[]string{
			"0,0.75,0.74",
			"1,0.50,0.90",
		},
	)
	run2 := writeTabularArtifactRun(
		t,
		root,
		"r2",
		"banknote",
		"linear_poly3",
		110,
		[]string{
			"1,0.50,0.10",
			"0,0.75,0.76",
		},
	)

	result, err := LoadAndAggregateTabularCandidate(
		TabularArtifactCandidateInput{
			Candidate: CandidateDescriptor{
				ID:     "default__rescale_aware",
				Path:   "rescale_aware",
				Family: "default",
			},
			WorkloadID: "banknote__linear_poly3",
			DatasetID:  "banknote",
			ModelID:    "linear_poly3",
			SplitID:    "test_seed42",
			Threshold:  0.5,
			Runs: []TabularArtifactRun{
				run1,
				run2,
			},
		},
		0.01,
		0.5,
	)
	if err != nil {
		t.Fatalf(
			"LoadAndAggregateTabularCandidate failed: %v",
			err,
		)
	}

	if result.Scope.SampleCount != 2 {
		t.Fatalf(
			"expected sample count 2, got %d",
			result.Scope.SampleCount,
		)
	}
	if result.Scope.SuccessfulRuns != 2 {
		t.Fatalf(
			"expected successful runs 2, got %d",
			result.Scope.SuccessfulRuns,
		)
	}
	if result.Scope.FailedRuns != 0 {
		t.Fatalf(
			"expected failed runs 0, got %d",
			result.Scope.FailedRuns,
		)
	}

	candidate := result.Aggregation.Evidence.Candidate

	if candidate.ChainLength != 7 {
		t.Fatalf(
			"expected chain length 7, got %d",
			candidate.ChainLength,
		)
	}
	if candidate.ScaleBits != 45 {
		t.Fatalf(
			"expected scale bits 45, got %d",
			candidate.ScaleBits,
		)
	}
	if candidate.Slots != 8192 {
		t.Fatalf(
			"expected slots 8192, got %d",
			candidate.Slots,
		)
	}
	if candidate.LogN != 14 {
		t.Fatalf(
			"expected logN 14, got %d",
			candidate.LogN,
		)
	}

	if math.Abs(
		result.Aggregation.Evidence.MeanTotalMS-105,
	) > 1e-12 {
		t.Fatalf(
			"expected mean latency 105, got %.12f",
			result.Aggregation.Evidence.MeanTotalMS,
		)
	}

	if result.Aggregation.Coverage.VCert != 1 {
		t.Fatalf(
			"expected V_cert=1, got %d",
			result.Aggregation.Coverage.VCert,
		)
	}
	if result.Aggregation.Coverage.VAmb != 1 {
		t.Fatalf(
			"expected V_amb=1, got %d",
			result.Aggregation.Coverage.VAmb,
		)
	}

	if result.Aggregation.Evidence.DecisionFlips != 0 {
		t.Fatalf(
			"expected zero V_cert flips, got %d",
			result.Aggregation.Evidence.DecisionFlips,
		)
	}
	if result.Aggregation.Evidence.ErrorViolations != 0 {
		t.Fatalf(
			"expected zero V_cert violations, got %d",
			result.Aggregation.Evidence.ErrorViolations,
		)
	}

	if math.Abs(
		result.Aggregation.Evidence.MaxObservedError-0.01,
	) > 1e-12 {
		t.Fatalf(
			"expected V_cert max error 0.01, got %.12f",
			result.Aggregation.Evidence.MaxObservedError,
		)
	}
	if math.Abs(
		result.Aggregation.MaxObservedErrorAll-0.4,
	) > 1e-12 {
		t.Fatalf(
			"expected all-region max error 0.4, got %.12f",
			result.Aggregation.MaxObservedErrorAll,
		)
	}
}

func TestLoadAndAggregateTabularCandidateRejectsPlaintextMismatch(
	t *testing.T,
) {
	root := t.TempDir()

	run1 := writeTabularArtifactRun(
		t,
		root,
		"r1",
		"banknote",
		"linear_poly3",
		100,
		[]string{
			"0,0.75,0.74",
		},
	)
	run2 := writeTabularArtifactRun(
		t,
		root,
		"r2",
		"banknote",
		"linear_poly3",
		110,
		[]string{
			"0,0.76,0.75",
		},
	)

	_, err := LoadAndAggregateTabularCandidate(
		TabularArtifactCandidateInput{
			Candidate: CandidateDescriptor{
				ID:   "candidate",
				Path: "rescale_aware",
			},
			WorkloadID: "banknote__linear_poly3",
			DatasetID:  "banknote",
			ModelID:    "linear_poly3",
			SplitID:    "test_seed42",
			Threshold:  0.5,
			Runs: []TabularArtifactRun{
				run1,
				run2,
			},
		},
		0.001,
		0.5,
	)
	if err == nil {
		t.Fatal("expected plaintext mismatch error")
	}
	if !strings.Contains(
		err.Error(),
		"plaintext score mismatch",
	) {
		t.Fatalf(
			"unexpected error: %v",
			err,
		)
	}
}

func TestLoadAndAggregateTabularCandidateRejectsIdentityMismatch(
	t *testing.T,
) {
	root := t.TempDir()

	run := writeTabularArtifactRun(
		t,
		root,
		"r1",
		"digits_binary",
		"linear_poly3",
		100,
		[]string{
			"0,0.75,0.74",
		},
	)

	_, err := LoadAndAggregateTabularCandidate(
		TabularArtifactCandidateInput{
			Candidate: CandidateDescriptor{
				ID:   "candidate",
				Path: "rescale_aware",
			},
			WorkloadID: "banknote__linear_poly3",
			DatasetID:  "banknote",
			ModelID:    "linear_poly3",
			SplitID:    "test_seed42",
			Threshold:  0.5,
			Runs: []TabularArtifactRun{
				run,
			},
		},
		0.001,
		0.5,
	)
	if err == nil {
		t.Fatal("expected dataset mismatch error")
	}
	if !strings.Contains(
		err.Error(),
		"dataset mismatch",
	) {
		t.Fatalf(
			"unexpected error: %v",
			err,
		)
	}
}

func TestLoadAndAggregateTabularCandidateRejectsRecordCountMismatch(
	t *testing.T,
) {
	root := t.TempDir()

	run := writeTabularArtifactRunWithEvaluatedRows(
		t,
		root,
		"r1",
		"banknote",
		"linear_poly3",
		100,
		2,
		[]string{
			"0,0.75,0.74",
		},
	)

	_, err := LoadAndAggregateTabularCandidate(
		TabularArtifactCandidateInput{
			Candidate: CandidateDescriptor{
				ID:   "candidate",
				Path: "rescale_aware",
			},
			WorkloadID: "banknote__linear_poly3",
			DatasetID:  "banknote",
			ModelID:    "linear_poly3",
			SplitID:    "test_seed42",
			Threshold:  0.5,
			Runs: []TabularArtifactRun{
				run,
			},
		},
		0.001,
		0.5,
	)
	if err == nil {
		t.Fatal("expected record-count mismatch error")
	}
	if !strings.Contains(
		err.Error(),
		"record count mismatch",
	) {
		t.Fatalf(
			"unexpected error: %v",
			err,
		)
	}
}

func writeTabularArtifactRun(
	t *testing.T,
	root string,
	name string,
	datasetID string,
	modelID string,
	meanTotalMS float64,
	recordRows []string,
) TabularArtifactRun {
	t.Helper()

	return writeTabularArtifactRunWithEvaluatedRows(
		t,
		root,
		name,
		datasetID,
		modelID,
		meanTotalMS,
		len(recordRows),
		recordRows,
	)
}

func writeTabularArtifactRunWithEvaluatedRows(
	t *testing.T,
	root string,
	name string,
	datasetID string,
	modelID string,
	meanTotalMS float64,
	evaluatedRows int,
	recordRows []string,
) TabularArtifactRun {
	t.Helper()

	runDir := filepath.Join(root, name)

	if err := os.MkdirAll(runDir, 0o755); err != nil {
		t.Fatalf(
			"create run directory: %v",
			err,
		)
	}

	summaryPath := filepath.Join(
		runDir,
		"summary.csv",
	)
	recordsPath := filepath.Join(
		runDir,
		"records.csv",
	)

	summary := strings.Join([]string{
		"dataset_id,model_id,evaluated_rows,mean_total_eval_ms,initial_level,log_default_scale,max_slots",
		datasetID + "," +
			modelID + "," +
			formatTestInt(evaluatedRows) + "," +
			formatTestFloat(meanTotalMS) +
			",6,45,8192",
		"",
	}, "\n")

	records := strings.Join(
		append(
			[]string{
				"row_id,plain_y,ckks_y",
			},
			recordRows...,
		),
		"\n",
	) + "\n"

	if err := os.WriteFile(
		summaryPath,
		[]byte(summary),
		0o644,
	); err != nil {
		t.Fatalf(
			"write summary CSV: %v",
			err,
		)
	}

	if err := os.WriteFile(
		recordsPath,
		[]byte(records),
		0o644,
	); err != nil {
		t.Fatalf(
			"write records CSV: %v",
			err,
		)
	}

	return TabularArtifactRun{
		RecordsPath: recordsPath,
		SummaryPath: summaryPath,
	}
}

func formatTestInt(value int) string {
	return strconv.Itoa(value)
}

func formatTestFloat(value float64) string {
	return strconv.FormatFloat(
		value,
		'f',
		6,
		64,
	)
}
