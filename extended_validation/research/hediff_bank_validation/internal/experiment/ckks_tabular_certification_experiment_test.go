package experiment

import (
	"strings"
	"testing"

	"github.com/hasslelee/flipguard/internal/certify"
)

func TestValidateTabularCertificationMatrixFor(
	t *testing.T,
) {
	scan := makeTabularCertificationMatrixTestScan()

	err := validateTabularCertificationMatrixFor(
		scan,
		[]string{"dataset"},
		[]string{"model"},
		[]string{"profile_a", "profile_b"},
		[]string{"path_a", "path_b"},
		2,
	)
	if err != nil {
		t.Fatalf(
			"expected complete matrix to pass: %v",
			err,
		)
	}
}

func TestValidateTabularCertificationMatrixRejectsMissingCandidate(
	t *testing.T,
) {
	scan := makeTabularCertificationMatrixTestScan()

	scan.Workloads[0].Candidates =
		scan.Workloads[0].Candidates[:3]
	scan.Workloads[0].Evidences =
		scan.Workloads[0].Evidences[:3]
	scan.Workloads[0].Summary.Certificates =
		scan.Workloads[0].
			Summary.Certificates[:3]
	scan.Workloads[0].Summary.CandidateCount = 3
	scan.Workloads[0].Summary.SafeCount = 3

	// Keep LatestRows at the complete-matrix value so this test
	// reaches the workload-level missing-candidate validation.
	err := validateTabularCertificationMatrixFor(
		scan,
		[]string{"dataset"},
		[]string{"model"},
		[]string{"profile_a", "profile_b"},
		[]string{"path_a", "path_b"},
		2,
	)
	if err == nil {
		t.Fatal(
			"expected missing candidate to be rejected",
		)
	}
	if !strings.Contains(
		err.Error(),
		"candidate count mismatch",
	) {
		t.Fatalf(
			"unexpected missing-candidate error: %v",
			err,
		)
	}
}

func makeTabularCertificationMatrixTestScan() (
	scan certify.TabularStatusScan,
) {
	candidateIDs := []struct {
		id     string
		family string
		path   string
	}{
		{
			id:     "profile_a__path_a",
			family: "profile_a",
			path:   "path_a",
		},
		{
			id:     "profile_a__path_b",
			family: "profile_a",
			path:   "path_b",
		},
		{
			id:     "profile_b__path_a",
			family: "profile_b",
			path:   "path_a",
		},
		{
			id:     "profile_b__path_b",
			family: "profile_b",
			path:   "path_b",
		},
	}

	workload := certify.TabularWorkloadScan{
		Scope: certify.ClaimScope{
			WorkloadID: "dataset__model",
			DatasetID:  "dataset",
			ModelID:    "model",
			SplitID:    "split",

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

			MinMargin:          0.0001,
			MinCertifiedMargin: 0.01,
			P5Margin:           0.001,
		},

		Summary: certify.CertificationSummary{
			Outcome:        certify.OutcomeSelected,
			CandidateCount: 4,
			SafeCount:      4,
		},
	}

	for index, candidateInfo := range candidateIDs {
		candidate :=
			certify.CandidateDescriptor{
				ID:     candidateInfo.id,
				Family: candidateInfo.family,
				Path:   candidateInfo.path,

				LogN:        14,
				Slots:       8192,
				ChainLength: 7,
				ScaleBits:   45,
			}

		scanned :=
			certify.TabularScannedCandidate{
				Candidate:      candidate,
				RequestedRuns:  2,
				SuccessfulRuns: 2,
				RunTags: []string{
					candidateInfo.id + "_r1",
					candidateInfo.id + "_r2",
				},
			}

		evidence := certify.CandidateEvidence{
			Candidate:          candidate,
			SuccessRuns:        2,
			ObservedValidation: true,
			MeanTotalMS:        float64(index + 1),
		}

		certificate :=
			certify.CandidateCertificate{
				Candidate: candidate,

				Status:    certify.StatusSafe,
				Assurance: certify.AssuranceObservedValidation,

				SuccessRuns:        2,
				ObservedValidation: true,
				MeanTotalMS:        float64(index + 1),
			}

		workload.Candidates = append(
			workload.Candidates,
			scanned,
		)
		workload.Evidences = append(
			workload.Evidences,
			evidence,
		)
		workload.Summary.Certificates =
			append(
				workload.Summary.Certificates,
				certificate,
			)
	}

	selected :=
		workload.Summary.Certificates[0]
	workload.Summary.Selected = &selected

	return certify.TabularStatusScan{
		LatestRows: 8,

		Workloads: []certify.TabularWorkloadScan{
			workload,
		},
	}
}
