package certify

import (
	"encoding/csv"
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
)

type tabularStatusTestRow struct {
	Timestamp string

	DatasetID string
	ModelID   string
	Profile   string
	Path      string

	Repeat int
	Tag    string

	Status   string
	ExitCode int

	SummaryPath string
	LogPath     string
}

func TestScanTabularRunStatusDeduplicatesAndCertifies(
	t *testing.T,
) {
	root := t.TempDir()

	modelRoot := filepath.Join(root, "models")
	writeTabularScannerModelArtifact(
		t,
		modelRoot,
		"banknote",
		"linear_poly3",
		0.5,
		42,
		0.3,
		2,
	)

	run1 := writeTabularArtifactRun(
		t,
		root,
		"default_r1",
		"banknote",
		"linear_poly3",
		100,
		[]string{
			"0,0.75,0.74",
			"1,0.25,0.26",
		},
	)
	run2 := writeTabularArtifactRun(
		t,
		root,
		"default_r2",
		"banknote",
		"linear_poly3",
		110,
		[]string{
			"0,0.75,0.76",
			"1,0.25,0.24",
		},
	)

	statusPath := writeTabularStatusTestFile(
		t,
		root,
		[]tabularStatusTestRow{
			{
				Timestamp:   "2026-01-01T00:00:00Z",
				DatasetID:   "banknote",
				ModelID:     "linear_poly3",
				Profile:     "default",
				Path:        "rescale_aware",
				Repeat:      1,
				Tag:         "default_r1",
				Status:      "failed",
				ExitCode:    1,
				SummaryPath: run1.SummaryPath,
				LogPath: filepath.Join(
					root,
					"default_r1.log",
				),
			},
			{
				Timestamp:   "2026-01-01T00:01:00Z",
				DatasetID:   "banknote",
				ModelID:     "linear_poly3",
				Profile:     "default",
				Path:        "rescale_aware",
				Repeat:      1,
				Tag:         "default_r1",
				Status:      "ok",
				ExitCode:    0,
				SummaryPath: run1.SummaryPath,
				LogPath: filepath.Join(
					root,
					"default_r1.log",
				),
			},
			{
				Timestamp:   "2026-01-01T00:02:00Z",
				DatasetID:   "banknote",
				ModelID:     "linear_poly3",
				Profile:     "default",
				Path:        "rescale_aware",
				Repeat:      2,
				Tag:         "default_r2",
				Status:      "ok",
				ExitCode:    0,
				SummaryPath: run2.SummaryPath,
				LogPath: filepath.Join(
					root,
					"default_r2.log",
				),
			},
			{
				Timestamp: "2026-01-01T00:03:00Z",
				DatasetID: "banknote",
				ModelID:   "linear_poly3",
				Profile:   "short_chain_3",
				Path:      "rescale_aware",
				Repeat:    1,
				Tag:       "failed_r1",
				Status:    "failed",
				ExitCode:  1,
				SummaryPath: filepath.Join(
					root,
					"failed_r1",
					"summary.csv",
				),
				LogPath: filepath.Join(
					root,
					"failed_r1.log",
				),
			},
			{
				Timestamp: "2026-01-01T00:04:00Z",
				DatasetID: "banknote",
				ModelID:   "linear_poly3",
				Profile:   "short_chain_3",
				Path:      "rescale_aware",
				Repeat:    2,
				Tag:       "failed_r2",
				Status:    "failed",
				ExitCode:  1,
				SummaryPath: filepath.Join(
					root,
					"failed_r2",
					"summary.csv",
				),
				LogPath: filepath.Join(
					root,
					"failed_r2.log",
				),
			},
		},
	)

	scan, err := ScanTabularRunStatus(
		TabularStatusScanConfig{
			StatusPath: statusPath,
			ModelRoot:  modelRoot,

			MarginFloor:  0.01,
			SafetyFactor: 0.5,

			ExpectedRepeats: 2,
		},
	)
	if err != nil {
		t.Fatalf(
			"ScanTabularRunStatus failed: %v",
			err,
		)
	}

	if scan.RawRows != 5 {
		t.Fatalf(
			"expected raw rows 5, got %d",
			scan.RawRows,
		)
	}
	if scan.LatestRows != 4 {
		t.Fatalf(
			"expected latest rows 4, got %d",
			scan.LatestRows,
		)
	}
	if scan.DuplicateTags != 1 {
		t.Fatalf(
			"expected duplicate tags 1, got %d",
			scan.DuplicateTags,
		)
	}
	if len(scan.Workloads) != 1 {
		t.Fatalf(
			"expected one workload, got %d",
			len(scan.Workloads),
		)
	}

	workload := scan.Workloads[0]

	if workload.Scope.Threshold != 0.5 {
		t.Fatalf(
			"expected model threshold 0.5, got %.12g",
			workload.Scope.Threshold,
		)
	}
	if workload.Scope.SplitID !=
		"test_seed42_ratio0.3_prefix2_of2" {
		t.Fatalf(
			"unexpected split ID: %s",
			workload.Scope.SplitID,
		)
	}

	if len(workload.Candidates) != 2 {
		t.Fatalf(
			"expected two candidates, got %d",
			len(workload.Candidates),
		)
	}
	if workload.Summary.CandidateCount != 2 {
		t.Fatalf(
			"expected candidate count 2, got %d",
			workload.Summary.CandidateCount,
		)
	}
	if workload.Summary.SafeCount != 1 {
		t.Fatalf(
			"expected safe count 1, got %d",
			workload.Summary.SafeCount,
		)
	}
	if workload.Summary.FailedCount != 1 {
		t.Fatalf(
			"expected failed count 1, got %d",
			workload.Summary.FailedCount,
		)
	}
	if workload.Summary.Selected == nil {
		t.Fatal("expected selected candidate")
	}
	if workload.Summary.Selected.Candidate.ID !=
		"default__rescale_aware" {
		t.Fatalf(
			"expected default__rescale_aware, got %s",
			workload.Summary.Selected.Candidate.ID,
		)
	}

	var failedCertificate *CandidateCertificate

	for index := range workload.Summary.Certificates {
		certificate :=
			&workload.Summary.Certificates[index]

		if certificate.Candidate.ID ==
			"short_chain_3__rescale_aware" {
			failedCertificate = certificate
			break
		}
	}

	if failedCertificate == nil {
		t.Fatal("expected failed candidate certificate")
	}
	if failedCertificate.Status != StatusFailed {
		t.Fatalf(
			"expected FAILED status, got %s",
			failedCertificate.Status,
		)
	}
	if failedCertificate.FailedRuns != 2 {
		t.Fatalf(
			"expected two failed runs, got %d",
			failedCertificate.FailedRuns,
		)
	}
}

func TestScanTabularRunStatusRejectsDigestMismatch(
	t *testing.T,
) {
	root := t.TempDir()

	modelRoot := filepath.Join(root, "models")
	writeTabularScannerModelArtifact(
		t,
		modelRoot,
		"banknote",
		"linear_poly3",
		0.5,
		42,
		0.3,
		1,
	)

	runA := writeTabularArtifactRun(
		t,
		root,
		"candidate_a",
		"banknote",
		"linear_poly3",
		100,
		[]string{
			"0,0.75,0.74",
		},
	)
	runB := writeTabularArtifactRun(
		t,
		root,
		"candidate_b",
		"banknote",
		"linear_poly3",
		90,
		[]string{
			"0,0.76,0.75",
		},
	)

	statusPath := writeTabularStatusTestFile(
		t,
		root,
		[]tabularStatusTestRow{
			{
				Timestamp:   "2026-01-01T00:00:00Z",
				DatasetID:   "banknote",
				ModelID:     "linear_poly3",
				Profile:     "default",
				Path:        "rescale_aware",
				Repeat:      1,
				Tag:         "candidate_a",
				Status:      "ok",
				ExitCode:    0,
				SummaryPath: runA.SummaryPath,
				LogPath: filepath.Join(
					root,
					"candidate_a.log",
				),
			},
			{
				Timestamp:   "2026-01-01T00:01:00Z",
				DatasetID:   "banknote",
				ModelID:     "linear_poly3",
				Profile:     "scale40",
				Path:        "rescale_aware",
				Repeat:      1,
				Tag:         "candidate_b",
				Status:      "ok",
				ExitCode:    0,
				SummaryPath: runB.SummaryPath,
				LogPath: filepath.Join(
					root,
					"candidate_b.log",
				),
			},
		},
	)

	_, err := ScanTabularRunStatus(
		TabularStatusScanConfig{
			StatusPath: statusPath,
			ModelRoot:  modelRoot,

			MarginFloor:  0.01,
			SafetyFactor: 0.5,

			ExpectedRepeats: 1,
		},
	)
	if err == nil {
		t.Fatal("expected validation digest mismatch")
	}
	if !strings.Contains(
		err.Error(),
		"validation scope mismatch",
	) {
		t.Fatalf(
			"unexpected error: %v",
			err,
		)
	}
}

func TestScanTabularRunStatusRejectsMissingRepeat(
	t *testing.T,
) {
	root := t.TempDir()

	modelRoot := filepath.Join(root, "models")
	writeTabularScannerModelArtifact(
		t,
		modelRoot,
		"banknote",
		"linear_poly3",
		0.5,
		42,
		0.3,
		1,
	)

	run := writeTabularArtifactRun(
		t,
		root,
		"only_r1",
		"banknote",
		"linear_poly3",
		100,
		[]string{
			"0,0.75,0.74",
		},
	)

	statusPath := writeTabularStatusTestFile(
		t,
		root,
		[]tabularStatusTestRow{
			{
				Timestamp:   "2026-01-01T00:00:00Z",
				DatasetID:   "banknote",
				ModelID:     "linear_poly3",
				Profile:     "default",
				Path:        "rescale_aware",
				Repeat:      1,
				Tag:         "only_r1",
				Status:      "ok",
				ExitCode:    0,
				SummaryPath: run.SummaryPath,
				LogPath: filepath.Join(
					root,
					"only_r1.log",
				),
			},
		},
	)

	_, err := ScanTabularRunStatus(
		TabularStatusScanConfig{
			StatusPath: statusPath,
			ModelRoot:  modelRoot,

			MarginFloor:  0.01,
			SafetyFactor: 0.5,

			ExpectedRepeats: 2,
		},
	)
	if err == nil {
		t.Fatal("expected missing repeat error")
	}
	if !strings.Contains(
		err.Error(),
		"missing repeat 2",
	) {
		t.Fatalf(
			"unexpected error: %v",
			err,
		)
	}
}

func TestCompleteTabularCandidateDescriptorsFromSibling(
	t *testing.T,
) {
	successful := CandidateDescriptor{
		ID:          "short_chain_3__baseline_non_rescale",
		Family:      "short_chain_3",
		Path:        "baseline_non_rescale",
		LogN:        14,
		Slots:       8192,
		ChainLength: 3,
		ScaleBits:   35,
	}

	failed := CandidateDescriptor{
		ID:     "short_chain_3__rescale_aware",
		Family: "short_chain_3",
		Path:   "rescale_aware",
	}

	workload := TabularWorkloadScan{
		Candidates: []TabularScannedCandidate{
			{
				Candidate:   successful,
				Aggregation: &TabularArtifactAggregation{},
			},
			{
				Candidate:  failed,
				FailedRuns: 3,
			},
		},
		Evidences: []CandidateEvidence{
			{
				Candidate:   successful,
				SuccessRuns: 3,
			},
			{
				Candidate:  failed,
				FailedRuns: 3,
			},
		},
	}

	if err := completeTabularCandidateDescriptors(
		&workload,
	); err != nil {
		t.Fatalf(
			"completeTabularCandidateDescriptors failed: %v",
			err,
		)
	}

	completed := workload.Candidates[1].Candidate

	if completed.ID != failed.ID {
		t.Fatalf(
			"candidate ID changed: got %s, expected %s",
			completed.ID,
			failed.ID,
		)
	}
	if completed.Path != failed.Path {
		t.Fatalf(
			"candidate path changed: got %s, expected %s",
			completed.Path,
			failed.Path,
		)
	}
	if completed.LogN != 14 ||
		completed.Slots != 8192 ||
		completed.ChainLength != 3 ||
		completed.ScaleBits != 35 {
		t.Fatalf(
			"failed candidate parameters were not reconstructed: %+v",
			completed,
		)
	}

	evidenceCandidate :=
		workload.Evidences[1].Candidate

	if evidenceCandidate != completed {
		t.Fatalf(
			"evidence candidate was not synchronized: got %+v, expected %+v",
			evidenceCandidate,
			completed,
		)
	}
	if workload.Evidences[1].FailedRuns != 3 {
		t.Fatalf(
			"failed-run evidence changed: got %d",
			workload.Evidences[1].FailedRuns,
		)
	}
}

func writeTabularScannerModelArtifact(
	t *testing.T,
	modelRoot string,
	datasetID string,
	modelID string,
	threshold float64,
	randomState int,
	testSize float64,
	testSamples int,
) {
	t.Helper()

	dir := filepath.Join(
		modelRoot,
		datasetID,
		modelID,
	)

	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatalf(
			"create scanner model directory: %v",
			err,
		)
	}

	payload := map[string]any{
		"dataset_id":   datasetID,
		"model_id":     modelID,
		"random_state": randomState,
		"test_size":    testSize,
		"test_samples": testSamples,
		"polynomial_score": map[string]any{
			"decision_threshold": threshold,
		},
	}

	data, err := json.MarshalIndent(
		payload,
		"",
		"  ",
	)
	if err != nil {
		t.Fatalf(
			"marshal scanner model artifact: %v",
			err,
		)
	}

	path := filepath.Join(dir, "model.json")

	if err := os.WriteFile(
		path,
		data,
		0o644,
	); err != nil {
		t.Fatalf(
			"write scanner model artifact: %v",
			err,
		)
	}
}

func writeTabularStatusTestFile(
	t *testing.T,
	root string,
	rows []tabularStatusTestRow,
) string {
	t.Helper()

	path := filepath.Join(
		root,
		"run_status.csv",
	)

	file, err := os.Create(path)
	if err != nil {
		t.Fatalf(
			"create status test file: %v",
			err,
		)
	}
	defer file.Close()

	writer := csv.NewWriter(file)
	defer writer.Flush()

	header := []string{
		"timestamp",
		"dataset",
		"model",
		"profile",
		"path",
		"repeat",
		"tag",
		"status",
		"exit_code",
		"summary_path",
		"log_path",
	}

	if err := writer.Write(header); err != nil {
		t.Fatalf(
			"write status header: %v",
			err,
		)
	}

	for _, row := range rows {
		record := []string{
			row.Timestamp,
			row.DatasetID,
			row.ModelID,
			row.Profile,
			row.Path,
			strconv.Itoa(row.Repeat),
			row.Tag,
			row.Status,
			strconv.Itoa(row.ExitCode),
			row.SummaryPath,
			row.LogPath,
		}

		if err := writer.Write(record); err != nil {
			t.Fatalf(
				"write status row: %v",
				err,
			)
		}
	}

	writer.Flush()

	if err := writer.Error(); err != nil {
		t.Fatalf(
			"flush status test file: %v",
			err,
		)
	}

	return path
}
