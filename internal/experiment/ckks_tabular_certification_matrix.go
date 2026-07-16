package experiment

import (
	"fmt"

	"github.com/hasslelee/flipguard/internal/certify"
)

var (
	ckksTabularCertificationDatasets = []string{
		"banknote",
		"digits_binary",
		"iris_binary",
		"mnist_pool16",
		"wdbc",
	}

	ckksTabularCertificationModels = []string{
		"linear_poly3",
		"mlp_square_linear_score",
	}

	ckksTabularCertificationProfiles = []string{
		"default",
		"scale42",
		"scale40",
		"scale38",
		"deep_chain_8_scale45",
		"deep_chain_9_scale45",
		"short_chain_6_scale42",
		"short_chain_6_scale40",
		"short_chain_6_scale38",
		"short_chain_5",
		"short_chain_3",
	}

	ckksTabularCertificationPaths = []string{
		"baseline_non_rescale",
		"rescale_aware",
	}
)

type tabularCertificationExpectedCandidate struct {
	Family string
	Path   string
}

func validateTabularCertificationMatrix(
	scan certify.TabularStatusScan,
	expectedRepeats int,
) error {
	return validateTabularCertificationMatrixFor(
		scan,
		ckksTabularCertificationDatasets,
		ckksTabularCertificationModels,
		ckksTabularCertificationProfiles,
		ckksTabularCertificationPaths,
		expectedRepeats,
	)
}

func validateTabularCertificationMatrixFor(
	scan certify.TabularStatusScan,
	datasets []string,
	models []string,
	profiles []string,
	paths []string,
	expectedRepeats int,
) error {
	if len(datasets) == 0 {
		return fmt.Errorf("expected dataset list is empty")
	}
	if len(models) == 0 {
		return fmt.Errorf("expected model list is empty")
	}
	if len(profiles) == 0 {
		return fmt.Errorf("expected profile list is empty")
	}
	if len(paths) == 0 {
		return fmt.Errorf("expected execution path list is empty")
	}
	if expectedRepeats <= 0 {
		return fmt.Errorf(
			"expected repeats must be positive",
		)
	}

	expectedWorkloads := make(
		map[string]struct{},
		len(datasets)*len(models),
	)

	for _, datasetID := range datasets {
		for _, modelID := range models {
			workloadID :=
				datasetID + "__" + modelID

			if _, exists := expectedWorkloads[workloadID]; exists {
				return fmt.Errorf(
					"duplicate expected workload %s",
					workloadID,
				)
			}

			expectedWorkloads[workloadID] =
				struct{}{}
		}
	}

	expectedCandidates := make(
		map[string]tabularCertificationExpectedCandidate,
		len(profiles)*len(paths),
	)

	for _, profile := range profiles {
		for _, path := range paths {
			candidateID := profile + "__" + path

			if _, exists := expectedCandidates[candidateID]; exists {
				return fmt.Errorf(
					"duplicate expected candidate %s",
					candidateID,
				)
			}

			expectedCandidates[candidateID] =
				tabularCertificationExpectedCandidate{
					Family: profile,
					Path:   path,
				}
		}
	}

	expectedWorkloadCount :=
		len(expectedWorkloads)
	expectedCandidateCount :=
		len(expectedCandidates)
	expectedLatestRows :=
		expectedWorkloadCount *
			expectedCandidateCount *
			expectedRepeats

	if len(scan.Workloads) != expectedWorkloadCount {
		return fmt.Errorf(
			"workload count mismatch: got %d, expected %d",
			len(scan.Workloads),
			expectedWorkloadCount,
		)
	}

	if scan.LatestRows != expectedLatestRows {
		return fmt.Errorf(
			"latest run-tag count mismatch: got %d, expected %d",
			scan.LatestRows,
			expectedLatestRows,
		)
	}

	seenWorkloads := make(
		map[string]struct{},
		expectedWorkloadCount,
	)

	for _, workload := range scan.Workloads {
		workloadID := workload.Scope.WorkloadID

		if _, expected := expectedWorkloads[workloadID]; !expected {
			return fmt.Errorf(
				"unexpected workload %s",
				workloadID,
			)
		}
		if _, duplicate := seenWorkloads[workloadID]; duplicate {
			return fmt.Errorf(
				"duplicate workload %s",
				workloadID,
			)
		}

		seenWorkloads[workloadID] = struct{}{}

		expectedScopeID :=
			workload.Scope.DatasetID +
				"__" +
				workload.Scope.ModelID

		if expectedScopeID != workloadID {
			return fmt.Errorf(
				"workload %s scope identity mismatch: dataset/model form %s",
				workloadID,
				expectedScopeID,
			)
		}

		if workload.Scope.SampleCount <= 0 {
			return fmt.Errorf(
				"workload %s has non-positive sample count",
				workloadID,
			)
		}
		if workload.Coverage.Total !=
			workload.Scope.SampleCount {
			return fmt.Errorf(
				"workload %s coverage total %d does not match sample count %d",
				workloadID,
				workload.Coverage.Total,
				workload.Scope.SampleCount,
			)
		}
		if workload.Coverage.VCert+
			workload.Coverage.VAmb !=
			workload.Coverage.Total {
			return fmt.Errorf(
				"workload %s has inconsistent V_cert/V_amb coverage",
				workloadID,
			)
		}

		if len(workload.Candidates) !=
			expectedCandidateCount {
			return fmt.Errorf(
				"workload %s candidate count mismatch: got %d, expected %d",
				workloadID,
				len(workload.Candidates),
				expectedCandidateCount,
			)
		}
		if len(workload.Evidences) !=
			expectedCandidateCount {
			return fmt.Errorf(
				"workload %s evidence count mismatch: got %d, expected %d",
				workloadID,
				len(workload.Evidences),
				expectedCandidateCount,
			)
		}
		if len(workload.Summary.Certificates) !=
			expectedCandidateCount {
			return fmt.Errorf(
				"workload %s certificate count mismatch: got %d, expected %d",
				workloadID,
				len(workload.Summary.Certificates),
				expectedCandidateCount,
			)
		}
		if workload.Summary.CandidateCount !=
			expectedCandidateCount {
			return fmt.Errorf(
				"workload %s summary candidate count mismatch: got %d, expected %d",
				workloadID,
				workload.Summary.CandidateCount,
				expectedCandidateCount,
			)
		}

		statusTotal :=
			workload.Summary.SafeCount +
				workload.Summary.RejectedCount +
				workload.Summary.FailedCount +
				workload.Summary.AmbiguousCount

		if statusTotal != expectedCandidateCount {
			return fmt.Errorf(
				"workload %s certificate status total mismatch: got %d, expected %d",
				workloadID,
				statusTotal,
				expectedCandidateCount,
			)
		}

		seenCandidates := make(
			map[string]struct{},
			expectedCandidateCount,
		)

		for _, scanned := range workload.Candidates {
			candidateID := scanned.Candidate.ID

			expected, exists :=
				expectedCandidates[candidateID]
			if !exists {
				return fmt.Errorf(
					"workload %s has unexpected candidate %s",
					workloadID,
					candidateID,
				)
			}
			if _, duplicate := seenCandidates[candidateID]; duplicate {
				return fmt.Errorf(
					"workload %s has duplicate candidate %s",
					workloadID,
					candidateID,
				)
			}

			seenCandidates[candidateID] =
				struct{}{}

			if scanned.Candidate.Family !=
				expected.Family {
				return fmt.Errorf(
					"workload %s candidate %s family mismatch: got %s, expected %s",
					workloadID,
					candidateID,
					scanned.Candidate.Family,
					expected.Family,
				)
			}
			if scanned.Candidate.Path !=
				expected.Path {
				return fmt.Errorf(
					"workload %s candidate %s path mismatch: got %s, expected %s",
					workloadID,
					candidateID,
					scanned.Candidate.Path,
					expected.Path,
				)
			}
			if scanned.RequestedRuns != expectedRepeats {
				return fmt.Errorf(
					"workload %s candidate %s requested-run mismatch: got %d, expected %d",
					workloadID,
					candidateID,
					scanned.RequestedRuns,
					expectedRepeats,
				)
			}
			if scanned.SuccessfulRuns+
				scanned.FailedRuns !=
				expectedRepeats {
				return fmt.Errorf(
					"workload %s candidate %s execution total mismatch: success=%d failed=%d expected=%d",
					workloadID,
					candidateID,
					scanned.SuccessfulRuns,
					scanned.FailedRuns,
					expectedRepeats,
				)
			}
			if len(scanned.RunTags) != expectedRepeats {
				return fmt.Errorf(
					"workload %s candidate %s run-tag count mismatch: got %d, expected %d",
					workloadID,
					candidateID,
					len(scanned.RunTags),
					expectedRepeats,
				)
			}
		}

		for candidateID := range expectedCandidates {
			if _, exists := seenCandidates[candidateID]; !exists {
				return fmt.Errorf(
					"workload %s is missing candidate %s",
					workloadID,
					candidateID,
				)
			}
		}

		if selected := workload.Summary.Selected; selected != nil &&
			selected.Status != certify.StatusSafe {
			return fmt.Errorf(
				"workload %s selected non-SAFE candidate %s with status %s",
				workloadID,
				selected.Candidate.ID,
				selected.Status,
			)
		}
	}

	for workloadID := range expectedWorkloads {
		if _, exists := seenWorkloads[workloadID]; !exists {
			return fmt.Errorf(
				"missing workload %s",
				workloadID,
			)
		}
	}

	return nil
}
