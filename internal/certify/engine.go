package certify

import (
	"fmt"
	"math"
)

// BuildCandidateCertificate converts observed candidate evidence into one
// certify-or-reject result.
func BuildCandidateCertificate(
	evidence CandidateEvidence,
	coverage ValidationCoverage,
) (CandidateCertificate, error) {
	if err := coverage.Validate(); err != nil {
		return CandidateCertificate{}, fmt.Errorf(
			"invalid validation coverage: %w",
			err,
		)
	}
	if evidence.Candidate.ID == "" {
		return CandidateCertificate{}, fmt.Errorf("candidate ID is empty")
	}
	if evidence.SuccessRuns < 0 {
		return CandidateCertificate{}, fmt.Errorf(
			"candidate %s has negative success runs",
			evidence.Candidate.ID,
		)
	}
	if evidence.FailedRuns < 0 {
		return CandidateCertificate{}, fmt.Errorf(
			"candidate %s has negative failed runs",
			evidence.Candidate.ID,
		)
	}
	if evidence.DecisionFlips < 0 {
		return CandidateCertificate{}, fmt.Errorf(
			"candidate %s has negative decision flips",
			evidence.Candidate.ID,
		)
	}
	if evidence.ErrorViolations < 0 {
		return CandidateCertificate{}, fmt.Errorf(
			"candidate %s has negative error violations",
			evidence.Candidate.ID,
		)
	}
	if !isNonNegativeFinite(evidence.MaxObservedError) {
		return CandidateCertificate{}, fmt.Errorf(
			"candidate %s has invalid maximum observed error",
			evidence.Candidate.ID,
		)
	}
	if !isNonNegativeFinite(evidence.MaxErrorBound) {
		return CandidateCertificate{}, fmt.Errorf(
			"candidate %s has invalid maximum error bound",
			evidence.Candidate.ID,
		)
	}
	if !isNonNegativeFinite(evidence.MeanTotalMS) {
		return CandidateCertificate{}, fmt.Errorf(
			"candidate %s has invalid mean latency",
			evidence.Candidate.ID,
		)
	}

	certificate := CandidateCertificate{
		Candidate: evidence.Candidate,

		SuccessRuns: evidence.SuccessRuns,
		FailedRuns:  evidence.FailedRuns,

		DecisionFlips:   evidence.DecisionFlips,
		ErrorViolations: evidence.ErrorViolations,

		MaxObservedError: evidence.MaxObservedError,
		MaxErrorBound:    evidence.MaxErrorBound,

		MeanTotalMS: evidence.MeanTotalMS,

		VCert: coverage.VCert,
		VAmb:  coverage.VAmb,

		CoverageRate:       coverage.CoverageRate,
		MinMargin:          coverage.MinMargin,
		MinCertifiedMargin: coverage.MinCertifiedMargin,
		P5Margin:           coverage.P5Margin,
	}

	switch {
	case evidence.FailedRuns > 0:
		certificate.Status = StatusFailed
		certificate.Reason = fmt.Sprintf(
			"candidate execution failed in %d run(s)",
			evidence.FailedRuns,
		)

	case evidence.SuccessRuns == 0:
		certificate.Status = StatusFailed
		certificate.Reason = "candidate has no successful execution run"

	case evidence.MeanTotalMS <= 0:
		return CandidateCertificate{}, fmt.Errorf(
			"successfully executed candidate %s must have positive mean latency",
			evidence.Candidate.ID,
		)

	case coverage.VCert == 0:
		certificate.Status = StatusAmbiguous
		certificate.Reason =
			"validation set contains no certifiable sample outside the margin floor"

	case evidence.DecisionFlips > 0 || evidence.ErrorViolations > 0:
		certificate.Status = StatusRejected
		certificate.Reason = fmt.Sprintf(
			"rejected on V_cert: decision_flips=%d error_violations=%d",
			evidence.DecisionFlips,
			evidence.ErrorViolations,
		)

	default:
		certificate.Status = StatusSafe
		certificate.Reason = fmt.Sprintf(
			"zero failures, zero decision flips, and zero error violations on V_cert=%d",
			coverage.VCert,
		)
	}

	return certificate, nil
}

// CertifyAndSelect builds candidate certificates and selects the lowest-latency
// SAFE configuration.
//
// When no SAFE candidate exists, it returns OutcomeNoSafe with Selected=nil.
// This is a normal certify-or-reject result rather than an execution error.
func CertifyAndSelect(
	evidences []CandidateEvidence,
	coverage ValidationCoverage,
) (CertificationSummary, error) {
	if err := coverage.Validate(); err != nil {
		return CertificationSummary{}, fmt.Errorf(
			"invalid validation coverage: %w",
			err,
		)
	}
	if len(evidences) == 0 {
		return CertificationSummary{}, fmt.Errorf(
			"candidate evidence list is empty",
		)
	}

	summary := CertificationSummary{
		CandidateCount: len(evidences),

		VCert:        coverage.VCert,
		VAmb:         coverage.VAmb,
		CoverageRate: coverage.CoverageRate,

		Certificates: make([]CandidateCertificate, 0, len(evidences)),
	}

	selectedIndex := -1

	for _, evidence := range evidences {
		certificate, err := BuildCandidateCertificate(evidence, coverage)
		if err != nil {
			return CertificationSummary{}, err
		}

		summary.Certificates = append(summary.Certificates, certificate)
		currentIndex := len(summary.Certificates) - 1

		switch certificate.Status {
		case StatusSafe:
			summary.SafeCount++

			if selectedIndex < 0 ||
				certificate.MeanTotalMS <
					summary.Certificates[selectedIndex].MeanTotalMS ||
				(certificate.MeanTotalMS ==
					summary.Certificates[selectedIndex].MeanTotalMS &&
					certificate.Candidate.ID <
						summary.Certificates[selectedIndex].Candidate.ID) {
				selectedIndex = currentIndex
			}

		case StatusRejected:
			summary.RejectedCount++

		case StatusFailed:
			summary.FailedCount++

		case StatusAmbiguous:
			summary.AmbiguousCount++
		}
	}

	if selectedIndex >= 0 {
		selected := summary.Certificates[selectedIndex]

		summary.Outcome = OutcomeSelected
		summary.Selected = &selected
		summary.Reason = fmt.Sprintf(
			"selected fastest SAFE candidate %s with mean latency %.6f ms",
			selected.Candidate.ID,
			selected.MeanTotalMS,
		)

		return summary, nil
	}

	summary.Outcome = OutcomeNoSafe
	summary.Selected = nil
	summary.Reason = noSafeReason(summary)

	return summary, nil
}

func noSafeReason(summary CertificationSummary) string {
	switch {
	case summary.FailedCount == summary.CandidateCount:
		return "no safe candidate: all candidates failed"

	case summary.AmbiguousCount+summary.FailedCount == summary.CandidateCount &&
		summary.AmbiguousCount > 0:
		return "no safe candidate: no candidate had a certifiable validation region"

	case summary.RejectedCount+summary.FailedCount+
		summary.AmbiguousCount == summary.CandidateCount:
		return "no safe candidate: every candidate was rejected, failed, or ambiguous"

	default:
		return "no safe candidate"
	}
}

func isNonNegativeFinite(value float64) bool {
	return value >= 0 && !math.IsNaN(value) && !math.IsInf(value, 0)
}
