package report

import (
	"encoding/csv"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/hasslelee/flipguard/internal/certify"
)

func TestWriteTabularCertificationArtifacts(
	t *testing.T,
) {
	outputDir := filepath.Join(
		t.TempDir(),
		"tabular",
		"current",
	)

	reference := certify.CandidateCertificate{
		Candidate: certify.CandidateDescriptor{
			ID:          "default__rescale_aware",
			Path:        "rescale_aware",
			Family:      "default",
			LogN:        14,
			Slots:       8192,
			ChainLength: 7,
			ScaleBits:   45,
			IsReference: true,
		},

		Status:    certify.StatusSafe,
		Assurance: certify.AssuranceObservedValidation,
		Reason:    "observed validation satisfied",

		SuccessRuns:        3,
		ObservedValidation: true,
		MeanTotalMS:        100,

		Threshold:          0.5,
		MarginFloor:        0.001,
		SafetyFactor:       0.5,
		VCert:              2,
		VAmb:               1,
		CoverageRate:       2.0 / 3.0,
		MinMargin:          0.0005,
		MinCertifiedMargin: 0.10,
		P5Margin:           0.02,
	}

	fast := certify.CandidateCertificate{
		Candidate: certify.CandidateDescriptor{
			ID:          "scale40__rescale_aware",
			Path:        "rescale_aware",
			Family:      "scale40",
			LogN:        14,
			Slots:       8192,
			ChainLength: 7,
			ScaleBits:   40,
		},

		Status:    certify.StatusSafe,
		Assurance: certify.AssuranceObservedValidation,
		Reason:    "observed validation satisfied",

		SuccessRuns:        3,
		ObservedValidation: true,
		MaxObservedError:   0.0001,
		MeanTotalMS:        80,

		Threshold:          0.5,
		MarginFloor:        0.001,
		SafetyFactor:       0.5,
		VCert:              2,
		VAmb:               1,
		CoverageRate:       2.0 / 3.0,
		MinMargin:          0.0005,
		MinCertifiedMargin: 0.10,
		P5Margin:           0.02,
	}

	scan := certify.TabularStatusScan{
		StatusPath:    "run_status.csv",
		RawRows:       7,
		LatestRows:    6,
		DuplicateTags: 1,

		Workloads: []certify.TabularWorkloadScan{
			{
				Scope: certify.ClaimScope{
					WorkloadID: "banknote__linear_poly3",
					DatasetID:  "banknote",
					ModelID:    "linear_poly3",
					SplitID:    "test_seed42_ratio0.3_prefix3_of3",

					ValidationDigest: "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",

					Threshold:    0.5,
					MarginFloor:  0.001,
					SafetyFactor: 0.5,
					SampleCount:  3,
				},

				Coverage: certify.ValidationCoverage{
					Threshold:    0.5,
					MarginFloor:  0.001,
					Total:        3,
					VCert:        2,
					VAmb:         1,
					CoverageRate: 2.0 / 3.0,

					MinMargin:          0.0005,
					MinCertifiedMargin: 0.10,
					P5Margin:           0.02,
				},

				Candidates: []certify.TabularScannedCandidate{
					{
						Candidate:      reference.Candidate,
						RequestedRuns:  3,
						SuccessfulRuns: 3,
						RunTags: []string{
							"reference_r1",
							"reference_r2",
							"reference_r3",
						},
					},
					{
						Candidate:      fast.Candidate,
						RequestedRuns:  3,
						SuccessfulRuns: 3,
						RunTags: []string{
							"fast_r1",
							"fast_r2",
							"fast_r3",
						},
					},
				},

				Summary: certify.CertificationSummary{
					Outcome: certify.OutcomeSelected,
					Reason:  "selected fastest SAFE candidate",

					CandidateCount: 2,
					SafeCount:      2,

					Threshold:    0.5,
					MarginFloor:  0.001,
					SafetyFactor: 0.5,

					VCert:        2,
					VAmb:         1,
					CoverageRate: 2.0 / 3.0,

					Certificates: []certify.CandidateCertificate{
						reference,
						fast,
					},

					Selected: &fast,
				},
			},
		},
	}

	if err := WriteTabularCertificationArtifacts(
		outputDir,
		scan,
	); err != nil {
		t.Fatalf(
			"WriteTabularCertificationArtifacts failed: %v",
			err,
		)
	}

	required := []string{
		"certificates.csv",
		"workload_summary.csv",
		"selected_configurations.csv",
		"validation_coverage.csv",
		"report.md",
	}

	for _, name := range required {
		path := filepath.Join(outputDir, name)

		info, err := os.Stat(path)
		if err != nil {
			t.Fatalf(
				"missing output %s: %v",
				name,
				err,
			)
		}
		if !info.Mode().IsRegular() {
			t.Fatalf(
				"output %s is not a regular file",
				name,
			)
		}
	}

	certificateRows := readTabularReportTestCSV(
		t,
		filepath.Join(
			outputDir,
			"certificates.csv",
		),
	)

	if len(certificateRows) != 2 {
		t.Fatalf(
			"expected two certificate rows, got %d",
			len(certificateRows),
		)
	}

	selectedCount := 0
	for _, row := range certificateRows {
		if row["selected"] == "true" {
			selectedCount++

			if row["candidate_id"] !=
				"scale40__rescale_aware" {
				t.Fatalf(
					"unexpected selected candidate: %s",
					row["candidate_id"],
				)
			}
		}
	}

	if selectedCount != 1 {
		t.Fatalf(
			"expected one selected row, got %d",
			selectedCount,
		)
	}

	selectedRows := readTabularReportTestCSV(
		t,
		filepath.Join(
			outputDir,
			"selected_configurations.csv",
		),
	)

	if len(selectedRows) != 1 {
		t.Fatalf(
			"expected one selection row, got %d",
			len(selectedRows),
		)
	}
	if selectedRows[0]["speedup_vs_reference"] !=
		"1.25" {
		t.Fatalf(
			"expected speedup 1.25, got %s",
			selectedRows[0]["speedup_vs_reference"],
		)
	}

	reportData, err := os.ReadFile(
		filepath.Join(outputDir, "report.md"),
	)
	if err != nil {
		t.Fatalf("read report.md: %v", err)
	}

	reportText := string(reportData)

	for _, requiredText := range []string{
		"Workloads with a selected SAFE configuration: `1/1`",
		"Validation coverage totals: `V_cert=2`, `V_amb=1`",
		"banknote__linear_poly3",
		"scale40__rescale_aware",
		"observed-validation certificate",
	} {
		if !strings.Contains(
			reportText,
			requiredText,
		) {
			t.Fatalf(
				"report missing %q",
				requiredText,
			)
		}
	}
}

func readTabularReportTestCSV(
	t *testing.T,
	path string,
) []map[string]string {
	t.Helper()

	file, err := os.Open(path)
	if err != nil {
		t.Fatalf("open CSV %s: %v", path, err)
	}
	defer file.Close()

	reader := csv.NewReader(file)

	records, err := reader.ReadAll()
	if err != nil {
		t.Fatalf("read CSV %s: %v", path, err)
	}
	if len(records) < 1 {
		t.Fatalf("CSV %s has no header", path)
	}

	header := records[0]
	rows := make(
		[]map[string]string,
		0,
		len(records)-1,
	)

	for rowIndex, record := range records[1:] {
		if len(record) != len(header) {
			t.Fatalf(
				"CSV %s row %d has %d fields; expected %d",
				path,
				rowIndex,
				len(record),
				len(header),
			)
		}

		row := make(
			map[string]string,
			len(header),
		)

		for index, key := range header {
			row[key] = record[index]
		}

		rows = append(rows, row)
	}

	return rows
}
