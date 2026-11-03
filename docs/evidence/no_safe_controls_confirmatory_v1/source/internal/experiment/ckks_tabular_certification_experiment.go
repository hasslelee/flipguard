package experiment

import (
	"fmt"
	"os"
	"sort"

	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/report"
)

const (
	ckksTabularCertificationStatusPath = "results/ckks_tabular_profile_sweep_repeated/run_status.csv"

	ckksTabularCertificationModelRoot = "datasets/tabular_suite"

	ckksTabularCertificationOutputDir = "results/certification/tabular/current"

	ckksTabularCertificationMarginFloor = 1e-3
)

// RunCKKSTabularCertification reconstructs repeated tabular execution
// evidence, certifies every profile-path candidate, and exports the
// lowest-latency SAFE configuration for each workload.
func RunCKKSTabularCertification() error {
	options := GetRuntimeOptions()

	statusPath := tabularCertificationEnv(
		"TABULAR_CERTIFICATION_STATUS_PATH",
		ckksTabularCertificationStatusPath,
	)
	modelRoot := tabularCertificationEnv(
		"TABULAR_CERTIFICATION_MODEL_ROOT",
		ckksTabularCertificationModelRoot,
	)
	outputDir := tabularCertificationEnv(
		"TABULAR_CERTIFICATION_OUTPUT_DIR",
		ckksTabularCertificationOutputDir,
	)

	scan, err := certify.ScanTabularRunStatus(
		certify.TabularStatusScanConfig{
			StatusPath: statusPath,
			ModelRoot:  modelRoot,

			MarginFloor:  ckksTabularCertificationMarginFloor,
			SafetyFactor: options.CKKSSafetyFactor,

			ExpectedRepeats: options.CKKSRepetitions,
		},
	)
	if err != nil {
		return fmt.Errorf(
			"scan repeated tabular certification evidence: %w",
			err,
		)
	}

	if err := validateTabularCertificationMatrix(
		scan,
		options.CKKSRepetitions,
	); err != nil {
		return fmt.Errorf(
			"validate tabular certification execution matrix: %w",
			err,
		)
	}

	fmt.Printf(
		"matrix_validation=PASS expected_workloads=%d expected_candidates_per_workload=%d expected_latest_tags=%d\n",
		len(ckksTabularCertificationDatasets)*
			len(ckksTabularCertificationModels),
		len(ckksTabularCertificationProfiles)*
			len(ckksTabularCertificationPaths),
		len(ckksTabularCertificationDatasets)*
			len(ckksTabularCertificationModels)*
			len(ckksTabularCertificationProfiles)*
			len(ckksTabularCertificationPaths)*
			options.CKKSRepetitions,
	)

	if err := os.RemoveAll(outputDir); err != nil {
		return fmt.Errorf(
			"remove previous tabular certification output: %w",
			err,
		)
	}

	if err := report.WriteTabularCertificationArtifacts(
		outputDir,
		scan,
	); err != nil {
		return fmt.Errorf(
			"write tabular certification artifacts: %w",
			err,
		)
	}

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
	totalCandidates := 0
	totalSafe := 0
	totalRejected := 0
	totalFailed := 0
	totalAmbiguous := 0
	totalVCert := 0
	totalVAmb := 0

	for _, workload := range workloads {
		totalCandidates +=
			workload.Summary.CandidateCount
		totalSafe += workload.Summary.SafeCount
		totalRejected +=
			workload.Summary.RejectedCount
		totalFailed += workload.Summary.FailedCount
		totalAmbiguous +=
			workload.Summary.AmbiguousCount

		totalVCert += workload.Coverage.VCert
		totalVAmb += workload.Coverage.VAmb

		if workload.Summary.Selected != nil {
			selectedCount++
		}
	}

	fmt.Println(
		"FlipGuard repeated tabular certification",
	)
	fmt.Printf(
		"status_path=%s raw_rows=%d latest_tags=%d duplicate_tags=%d\n",
		scan.StatusPath,
		scan.RawRows,
		scan.LatestRows,
		scan.DuplicateTags,
	)
	fmt.Printf(
		"workloads=%d selected=%d candidates=%d safe=%d rejected=%d failed=%d ambiguous=%d\n",
		len(workloads),
		selectedCount,
		totalCandidates,
		totalSafe,
		totalRejected,
		totalFailed,
		totalAmbiguous,
	)
	fmt.Printf(
		"margin_floor=%.12g safety_factor=%.12g expected_repeats=%d v_cert=%d v_amb=%d\n",
		ckksTabularCertificationMarginFloor,
		options.CKKSSafetyFactor,
		options.CKKSRepetitions,
		totalVCert,
		totalVAmb,
	)
	fmt.Println()

	for _, workload := range workloads {
		selectedID := ""
		selectedPath := ""
		selectedLatency := 0.0

		if selected := workload.Summary.Selected; selected != nil {
			selectedID = selected.Candidate.ID
			selectedPath = selected.Candidate.Path
			selectedLatency = selected.MeanTotalMS
		}

		fmt.Printf(
			"workload=%s outcome=%v candidates=%d safe=%d rejected=%d failed=%d ambiguous=%d v_cert=%d v_amb=%d selected=%s path=%s mean_total_ms=%.10f\n",
			workload.Scope.WorkloadID,
			workload.Summary.Outcome,
			workload.Summary.CandidateCount,
			workload.Summary.SafeCount,
			workload.Summary.RejectedCount,
			workload.Summary.FailedCount,
			workload.Summary.AmbiguousCount,
			workload.Coverage.VCert,
			workload.Coverage.VAmb,
			selectedID,
			selectedPath,
			selectedLatency,
		)
	}

	fmt.Println()
	fmt.Printf(
		"Exported tabular certification artifacts to %s/\n",
		outputDir,
	)

	return nil
}

func tabularCertificationEnv(
	key string,
	fallback string,
) string {
	value := os.Getenv(key)

	if value == "" {
		return fallback
	}

	return value
}
