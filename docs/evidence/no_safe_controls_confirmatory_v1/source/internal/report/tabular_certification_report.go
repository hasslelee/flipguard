package report

import (
	"encoding/csv"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"

	"github.com/hasslelee/flipguard/internal/certify"
)

// WriteTabularCertificationArtifacts writes paper-facing tabular
// certify-or-reject results reconstructed from repeated execution artifacts.
func WriteTabularCertificationArtifacts(
	outputDir string,
	scan certify.TabularStatusScan,
) error {
	if strings.TrimSpace(outputDir) == "" {
		return fmt.Errorf(
			"tabular certification output directory is empty",
		)
	}
	if len(scan.Workloads) == 0 {
		return fmt.Errorf(
			"tabular certification scan contains no workload",
		)
	}

	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		return fmt.Errorf(
			"create tabular certification output directory: %w",
			err,
		)
	}

	writers := []struct {
		name string
		run  func(string, certify.TabularStatusScan) error
	}{
		{
			name: "certificates.csv",
			run:  WriteTabularCertificatesCSV,
		},
		{
			name: "workload_summary.csv",
			run:  WriteTabularWorkloadSummaryCSV,
		},
		{
			name: "selected_configurations.csv",
			run:  WriteTabularSelectedConfigurationsCSV,
		},
		{
			name: "validation_coverage.csv",
			run:  WriteTabularValidationCoverageCSV,
		},
	}

	for _, writer := range writers {
		path := filepath.Join(
			outputDir,
			writer.name,
		)

		if err := writer.run(path, scan); err != nil {
			return err
		}
	}

	if err := WriteTabularCertificationMarkdown(
		filepath.Join(outputDir, "report.md"),
		scan,
	); err != nil {
		return err
	}

	return nil
}

// WriteTabularCertificatesCSV writes one row for every workload-candidate
// certificate.
func WriteTabularCertificatesCSV(
	path string,
	scan certify.TabularStatusScan,
) error {
	header := []string{
		"workload_id",
		"dataset_id",
		"model_id",
		"split_id",
		"validation_digest",
		"candidate_id",
		"profile_family",
		"path",
		"is_reference",
		"log_n",
		"slots",
		"chain_length",
		"scale_bits",
		"status",
		"assurance",
		"reason",
		"success_runs",
		"failed_runs",
		"observed_validation",
		"decision_flips_v_cert",
		"error_violations_v_cert",
		"max_observed_error_v_cert",
		"mean_total_ms",
		"threshold",
		"margin_floor",
		"safety_factor",
		"v_cert",
		"v_amb",
		"coverage_rate",
		"min_margin",
		"min_certified_margin",
		"p5_margin",
		"selected",
		"run_tags",
	}

	rows := make([][]string, 0)

	for _, workload := range scan.Workloads {
		scannedByID := make(
			map[string]certify.TabularScannedCandidate,
			len(workload.Candidates),
		)

		for _, candidate := range workload.Candidates {
			scannedByID[candidate.Candidate.ID] = candidate
		}

		selectedID := ""
		if workload.Summary.Selected != nil {
			selectedID =
				workload.Summary.Selected.Candidate.ID
		}

		for _, certificate := range workload.Summary.Certificates {
			scanned := scannedByID[certificate.Candidate.ID]

			rows = append(rows, []string{
				workload.Scope.WorkloadID,
				workload.Scope.DatasetID,
				workload.Scope.ModelID,
				workload.Scope.SplitID,
				workload.Scope.ValidationDigest,
				certificate.Candidate.ID,
				certificate.Candidate.Family,
				certificate.Candidate.Path,
				strconv.FormatBool(
					certificate.Candidate.IsReference,
				),
				formatTabularCertificationOptionalInt(
					certificate.Candidate.LogN,
				),
				formatTabularCertificationOptionalInt(
					certificate.Candidate.Slots,
				),
				formatTabularCertificationOptionalInt(
					certificate.Candidate.ChainLength,
				),
				formatTabularCertificationOptionalInt(
					certificate.Candidate.ScaleBits,
				),
				fmt.Sprint(certificate.Status),
				fmt.Sprint(certificate.Assurance),
				certificate.Reason,
				strconv.Itoa(certificate.SuccessRuns),
				strconv.Itoa(certificate.FailedRuns),
				strconv.FormatBool(
					certificate.ObservedValidation,
				),
				strconv.Itoa(
					certificate.DecisionFlips,
				),
				strconv.Itoa(
					certificate.ErrorViolations,
				),
				formatTabularCertificationFloat(
					certificate.MaxObservedError,
				),
				formatTabularCertificationFloat(
					certificate.MeanTotalMS,
				),
				formatTabularCertificationFloat(
					certificate.Threshold,
				),
				formatTabularCertificationFloat(
					certificate.MarginFloor,
				),
				formatTabularCertificationFloat(
					certificate.SafetyFactor,
				),
				strconv.Itoa(certificate.VCert),
				strconv.Itoa(certificate.VAmb),
				formatTabularCertificationFloat(
					certificate.CoverageRate,
				),
				formatTabularCertificationFloat(
					certificate.MinMargin,
				),
				formatTabularCertificationFloat(
					certificate.MinCertifiedMargin,
				),
				formatTabularCertificationFloat(
					certificate.P5Margin,
				),
				strconv.FormatBool(
					certificate.Candidate.ID ==
						selectedID,
				),
				strings.Join(scanned.RunTags, ";"),
			})
		}
	}

	return writeTabularCertificationCSV(
		path,
		header,
		rows,
	)
}

// WriteTabularWorkloadSummaryCSV writes one row for every dataset-model
// workload.
func WriteTabularWorkloadSummaryCSV(
	path string,
	scan certify.TabularStatusScan,
) error {
	header := []string{
		"workload_id",
		"dataset_id",
		"model_id",
		"split_id",
		"validation_digest",
		"outcome",
		"outcome_reason",
		"candidate_count",
		"safe_count",
		"rejected_count",
		"failed_count",
		"ambiguous_count",
		"threshold",
		"margin_floor",
		"safety_factor",
		"sample_count",
		"v_cert",
		"v_amb",
		"coverage_rate",
		"min_margin",
		"min_certified_margin",
		"p5_margin",
		"selected_candidate",
		"selected_path",
		"selected_assurance",
		"selected_mean_total_ms",
		"reference_candidate",
		"reference_mean_total_ms",
		"selected_speedup_vs_reference",
		"latency_only_candidate",
		"latency_only_status",
		"latency_only_mean_total_ms",
	}

	rows := make([][]string, 0, len(scan.Workloads))

	for _, workload := range scan.Workloads {
		reference := findTabularReferenceCertificate(
			workload.Summary.Certificates,
		)
		latencyOnly := findTabularLatencyOnlyCertificate(
			workload.Summary.Certificates,
		)

		selectedID := ""
		selectedPath := ""
		selectedAssurance := ""
		selectedLatency := 0.0
		selectedSpeedup := 0.0

		if workload.Summary.Selected != nil {
			selectedID =
				workload.Summary.Selected.Candidate.ID
			selectedPath =
				workload.Summary.Selected.Candidate.Path
			selectedAssurance =
				fmt.Sprint(
					workload.Summary.Selected.Assurance,
				)
			selectedLatency =
				workload.Summary.Selected.MeanTotalMS

			if reference != nil &&
				reference.MeanTotalMS > 0 &&
				selectedLatency > 0 {
				selectedSpeedup =
					reference.MeanTotalMS /
						selectedLatency
			}
		}

		referenceID := ""
		referenceLatency := 0.0
		if reference != nil {
			referenceID = reference.Candidate.ID
			referenceLatency = reference.MeanTotalMS
		}

		latencyOnlyID := ""
		latencyOnlyStatus := ""
		latencyOnlyLatency := 0.0
		if latencyOnly != nil {
			latencyOnlyID =
				latencyOnly.Candidate.ID
			latencyOnlyStatus =
				fmt.Sprint(latencyOnly.Status)
			latencyOnlyLatency =
				latencyOnly.MeanTotalMS
		}

		rows = append(rows, []string{
			workload.Scope.WorkloadID,
			workload.Scope.DatasetID,
			workload.Scope.ModelID,
			workload.Scope.SplitID,
			workload.Scope.ValidationDigest,
			fmt.Sprint(workload.Summary.Outcome),
			workload.Summary.Reason,
			strconv.Itoa(
				workload.Summary.CandidateCount,
			),
			strconv.Itoa(workload.Summary.SafeCount),
			strconv.Itoa(
				workload.Summary.RejectedCount,
			),
			strconv.Itoa(workload.Summary.FailedCount),
			strconv.Itoa(
				workload.Summary.AmbiguousCount,
			),
			formatTabularCertificationFloat(
				workload.Scope.Threshold,
			),
			formatTabularCertificationFloat(
				workload.Scope.MarginFloor,
			),
			formatTabularCertificationFloat(
				workload.Scope.SafetyFactor,
			),
			strconv.Itoa(workload.Scope.SampleCount),
			strconv.Itoa(workload.Coverage.VCert),
			strconv.Itoa(workload.Coverage.VAmb),
			formatTabularCertificationFloat(
				workload.Coverage.CoverageRate,
			),
			formatTabularCertificationFloat(
				workload.Coverage.MinMargin,
			),
			formatTabularCertificationFloat(
				workload.Coverage.MinCertifiedMargin,
			),
			formatTabularCertificationFloat(
				workload.Coverage.P5Margin,
			),
			selectedID,
			selectedPath,
			selectedAssurance,
			formatTabularCertificationOptionalFloat(
				selectedID != "",
				selectedLatency,
			),
			referenceID,
			formatTabularCertificationOptionalFloat(
				reference != nil,
				referenceLatency,
			),
			formatTabularCertificationOptionalFloat(
				selectedSpeedup > 0,
				selectedSpeedup,
			),
			latencyOnlyID,
			latencyOnlyStatus,
			formatTabularCertificationOptionalFloat(
				latencyOnly != nil,
				latencyOnlyLatency,
			),
		})
	}

	return writeTabularCertificationCSV(
		path,
		header,
		rows,
	)
}

// WriteTabularSelectedConfigurationsCSV writes the selected configuration for
// each workload. Workloads with NO_SAFE are retained with blank candidate
// fields.
func WriteTabularSelectedConfigurationsCSV(
	path string,
	scan certify.TabularStatusScan,
) error {
	header := []string{
		"workload_id",
		"dataset_id",
		"model_id",
		"outcome",
		"candidate_id",
		"profile_family",
		"path",
		"assurance",
		"log_n",
		"slots",
		"chain_length",
		"scale_bits",
		"mean_total_ms",
		"reference_mean_total_ms",
		"speedup_vs_reference",
		"decision_flips_v_cert",
		"error_violations_v_cert",
		"max_observed_error_v_cert",
		"v_cert",
		"v_amb",
		"coverage_rate",
	}

	rows := make([][]string, 0, len(scan.Workloads))

	for _, workload := range scan.Workloads {
		reference := findTabularReferenceCertificate(
			workload.Summary.Certificates,
		)

		row := []string{
			workload.Scope.WorkloadID,
			workload.Scope.DatasetID,
			workload.Scope.ModelID,
			fmt.Sprint(workload.Summary.Outcome),
			"",
			"",
			"",
			"",
			"",
			"",
			"",
			"",
			"",
			"",
			"",
			"",
			"",
			"",
			strconv.Itoa(workload.Coverage.VCert),
			strconv.Itoa(workload.Coverage.VAmb),
			formatTabularCertificationFloat(
				workload.Coverage.CoverageRate,
			),
		}

		if selected := workload.Summary.Selected; selected != nil {
			referenceLatency := 0.0
			speedup := 0.0

			if reference != nil {
				referenceLatency =
					reference.MeanTotalMS

				if referenceLatency > 0 &&
					selected.MeanTotalMS > 0 {
					speedup =
						referenceLatency /
							selected.MeanTotalMS
				}
			}

			row[4] = selected.Candidate.ID
			row[5] = selected.Candidate.Family
			row[6] = selected.Candidate.Path
			row[7] = fmt.Sprint(selected.Assurance)
			row[8] = strconv.Itoa(
				selected.Candidate.LogN,
			)
			row[9] = strconv.Itoa(
				selected.Candidate.Slots,
			)
			row[10] = strconv.Itoa(
				selected.Candidate.ChainLength,
			)
			row[11] = strconv.Itoa(
				selected.Candidate.ScaleBits,
			)
			row[12] =
				formatTabularCertificationFloat(
					selected.MeanTotalMS,
				)
			row[13] =
				formatTabularCertificationOptionalFloat(
					reference != nil,
					referenceLatency,
				)
			row[14] =
				formatTabularCertificationOptionalFloat(
					speedup > 0,
					speedup,
				)
			row[15] = strconv.Itoa(
				selected.DecisionFlips,
			)
			row[16] = strconv.Itoa(
				selected.ErrorViolations,
			)
			row[17] =
				formatTabularCertificationFloat(
					selected.MaxObservedError,
				)
		}

		rows = append(rows, row)
	}

	return writeTabularCertificationCSV(
		path,
		header,
		rows,
	)
}

// WriteTabularValidationCoverageCSV writes the exact claim scope and
// validation coverage for every workload.
func WriteTabularValidationCoverageCSV(
	path string,
	scan certify.TabularStatusScan,
) error {
	header := []string{
		"workload_id",
		"dataset_id",
		"model_id",
		"split_id",
		"validation_digest",
		"threshold",
		"margin_floor",
		"safety_factor",
		"sample_count",
		"v_cert",
		"v_amb",
		"coverage_rate",
		"min_margin",
		"min_certified_margin",
		"p5_margin",
	}

	rows := make([][]string, 0, len(scan.Workloads))

	for _, workload := range scan.Workloads {
		rows = append(rows, []string{
			workload.Scope.WorkloadID,
			workload.Scope.DatasetID,
			workload.Scope.ModelID,
			workload.Scope.SplitID,
			workload.Scope.ValidationDigest,
			formatTabularCertificationFloat(
				workload.Scope.Threshold,
			),
			formatTabularCertificationFloat(
				workload.Scope.MarginFloor,
			),
			formatTabularCertificationFloat(
				workload.Scope.SafetyFactor,
			),
			strconv.Itoa(workload.Scope.SampleCount),
			strconv.Itoa(workload.Coverage.VCert),
			strconv.Itoa(workload.Coverage.VAmb),
			formatTabularCertificationFloat(
				workload.Coverage.CoverageRate,
			),
			formatTabularCertificationFloat(
				workload.Coverage.MinMargin,
			),
			formatTabularCertificationFloat(
				workload.Coverage.MinCertifiedMargin,
			),
			formatTabularCertificationFloat(
				workload.Coverage.P5Margin,
			),
		})
	}

	return writeTabularCertificationCSV(
		path,
		header,
		rows,
	)
}

// WriteTabularCertificationMarkdown writes a compact paper-facing summary.
func WriteTabularCertificationMarkdown(
	path string,
	scan certify.TabularStatusScan,
) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	file, err := os.Create(path)
	if err != nil {
		return fmt.Errorf(
			"create tabular certification markdown: %w",
			err,
		)
	}
	defer file.Close()

	workloads := append(
		[]certify.TabularWorkloadScan(nil),
		scan.Workloads...,
	)

	sort.Slice(
		workloads,
		func(i int, j int) bool {
			return workloads[i].Scope.WorkloadID <
				workloads[j].Scope.WorkloadID
		},
	)

	selectedCount := 0
	noSafeCount := 0
	totalCandidates := 0
	totalSafe := 0
	totalRejected := 0
	totalFailed := 0
	totalAmbiguousCandidates := 0
	totalVCert := 0
	totalVAmb := 0
	latencyOnlyUnsafe := 0

	for _, workload := range workloads {
		totalCandidates +=
			workload.Summary.CandidateCount
		totalSafe += workload.Summary.SafeCount
		totalRejected +=
			workload.Summary.RejectedCount
		totalFailed += workload.Summary.FailedCount
		totalAmbiguousCandidates +=
			workload.Summary.AmbiguousCount
		totalVCert += workload.Coverage.VCert
		totalVAmb += workload.Coverage.VAmb

		if workload.Summary.Selected != nil {
			selectedCount++
		} else {
			noSafeCount++
		}

		latencyOnly :=
			findTabularLatencyOnlyCertificate(
				workload.Summary.Certificates,
			)

		if latencyOnly != nil &&
			latencyOnly.Status != certify.StatusSafe {
			latencyOnlyUnsafe++
		}
	}

	fmt.Fprintln(
		file,
		"# FlipGuard Tabular Certification Report",
	)
	fmt.Fprintln(file)

	fmt.Fprintln(file, "## Reconstruction")
	fmt.Fprintln(file)
	fmt.Fprintf(
		file,
		"- Run-status source: `%s`\n",
		scan.StatusPath,
	)
	fmt.Fprintf(
		file,
		"- Raw status rows: `%d`\n",
		scan.RawRows,
	)
	fmt.Fprintf(
		file,
		"- Latest unique run tags: `%d`\n",
		scan.LatestRows,
	)
	fmt.Fprintf(
		file,
		"- Duplicate tags resolved by last-row semantics: `%d`\n",
		scan.DuplicateTags,
	)
	fmt.Fprintf(
		file,
		"- Workloads: `%d`\n",
		len(workloads),
	)
	fmt.Fprintln(file)

	fmt.Fprintln(file, "## Aggregate Outcome")
	fmt.Fprintln(file)
	fmt.Fprintf(
		file,
		"- Workloads with a selected SAFE configuration: `%d/%d`\n",
		selectedCount,
		len(workloads),
	)
	fmt.Fprintf(
		file,
		"- Workloads with NO_SAFE: `%d`\n",
		noSafeCount,
	)
	fmt.Fprintf(
		file,
		"- Candidates: `%d` (`SAFE=%d`, `REJECTED=%d`, `FAILED=%d`, `AMBIGUOUS=%d`)\n",
		totalCandidates,
		totalSafe,
		totalRejected,
		totalFailed,
		totalAmbiguousCandidates,
	)
	fmt.Fprintf(
		file,
		"- Validation coverage totals: `V_cert=%d`, `V_amb=%d`\n",
		totalVCert,
		totalVAmb,
	)
	fmt.Fprintf(
		file,
		"- Workloads where latency-only would choose a non-SAFE candidate: `%d`\n",
		latencyOnlyUnsafe,
	)
	fmt.Fprintln(file)

	fmt.Fprintln(file, "## Workload Results")
	fmt.Fprintln(file)
	fmt.Fprintln(
		file,
		"| Workload | Outcome | V_cert | V_amb | SAFE | REJECTED | FAILED | Selected | Path | Mean total ms | Speedup vs reference | Latency-only status |",
	)
	fmt.Fprintln(
		file,
		"|---|---|---:|---:|---:|---:|---:|---|---|---:|---:|---|",
	)

	for _, workload := range workloads {
		reference := findTabularReferenceCertificate(
			workload.Summary.Certificates,
		)
		latencyOnly := findTabularLatencyOnlyCertificate(
			workload.Summary.Certificates,
		)

		selectedID := ""
		selectedPath := ""
		selectedLatency := ""
		speedup := ""

		if selected := workload.Summary.Selected; selected != nil {
			selectedID = selected.Candidate.ID
			selectedPath = selected.Candidate.Path
			selectedLatency =
				formatTabularCertificationFloat(
					selected.MeanTotalMS,
				)

			if reference != nil &&
				reference.MeanTotalMS > 0 &&
				selected.MeanTotalMS > 0 {
				speedup =
					formatTabularCertificationFloat(
						reference.MeanTotalMS /
							selected.MeanTotalMS,
					)
			}
		}

		latencyOnlyStatus := ""
		if latencyOnly != nil {
			latencyOnlyStatus =
				fmt.Sprint(latencyOnly.Status)
		}

		fmt.Fprintf(
			file,
			"| %s | %s | %d | %d | %d | %d | %d | %s | %s | %s | %s | %s |\n",
			workload.Scope.WorkloadID,
			workload.Summary.Outcome,
			workload.Coverage.VCert,
			workload.Coverage.VAmb,
			workload.Summary.SafeCount,
			workload.Summary.RejectedCount,
			workload.Summary.FailedCount,
			selectedID,
			selectedPath,
			selectedLatency,
			speedup,
			latencyOnlyStatus,
		)
	}

	fmt.Fprintln(file)
	fmt.Fprintln(file, "## Claim Boundary")
	fmt.Fprintln(file)
	fmt.Fprintln(
		file,
		"Every SAFE result is an observed-validation certificate restricted to the recorded validation split and its `V_cert` subset. Samples with margin less than or equal to the configured margin floor belong to `V_amb` and are not covered by the decision-stability claim.",
	)

	return nil
}

func findTabularReferenceCertificate(
	certificates []certify.CandidateCertificate,
) *certify.CandidateCertificate {
	for index := range certificates {
		if certificates[index].Candidate.IsReference {
			return &certificates[index]
		}
	}

	return nil
}

func findTabularLatencyOnlyCertificate(
	certificates []certify.CandidateCertificate,
) *certify.CandidateCertificate {
	selectedIndex := -1

	for index := range certificates {
		certificate := certificates[index]

		if certificate.SuccessRuns <= 0 ||
			certificate.MeanTotalMS <= 0 {
			continue
		}

		if selectedIndex < 0 ||
			certificate.MeanTotalMS <
				certificates[selectedIndex].MeanTotalMS ||
			(certificate.MeanTotalMS ==
				certificates[selectedIndex].MeanTotalMS &&
				certificate.Candidate.ID <
					certificates[selectedIndex].
						Candidate.ID) {
			selectedIndex = index
		}
	}

	if selectedIndex < 0 {
		return nil
	}

	return &certificates[selectedIndex]
}

func writeTabularCertificationCSV(
	path string,
	header []string,
	rows [][]string,
) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	file, err := os.Create(path)
	if err != nil {
		return fmt.Errorf(
			"create tabular certification csv %s: %w",
			path,
			err,
		)
	}
	defer file.Close()

	writer := csv.NewWriter(file)

	if err := writer.Write(header); err != nil {
		return fmt.Errorf(
			"write tabular certification header %s: %w",
			path,
			err,
		)
	}

	for index, row := range rows {
		if len(row) != len(header) {
			return fmt.Errorf(
				"tabular certification row %d in %s has %d fields; expected %d",
				index,
				path,
				len(row),
				len(header),
			)
		}

		if err := writer.Write(row); err != nil {
			return fmt.Errorf(
				"write tabular certification row %d in %s: %w",
				index,
				path,
				err,
			)
		}
	}

	writer.Flush()

	if err := writer.Error(); err != nil {
		return fmt.Errorf(
			"flush tabular certification csv %s: %w",
			path,
			err,
		)
	}

	return nil
}

func formatTabularCertificationOptionalInt(
	value int,
) string {
	if value <= 0 {
		return ""
	}

	return strconv.Itoa(value)
}

func formatTabularCertificationFloat(
	value float64,
) string {
	return strconv.FormatFloat(
		value,
		'g',
		12,
		64,
	)
}

func formatTabularCertificationOptionalFloat(
	present bool,
	value float64,
) string {
	if !present {
		return ""
	}

	return formatTabularCertificationFloat(value)
}
