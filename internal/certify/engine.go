package certify

import (
	"fmt"
	"math"
)

// BuildCandidateCertificate applies the default observed-validation policy.
func BuildCandidateCertificate(
	evidence CandidateEvidence,
	coverage ValidationCoverage,
) (CandidateCertificate, error) {
	return BuildCandidateCertificateWithPolicy(
		evidence,
		coverage,
		DefaultCertificationPolicy(),
	)
}

// BuildCandidateCertificateWithPolicy converts observed and analytical evidence
// into one certify-or-reject result under an explicit policy.
func BuildCandidateCertificateWithPolicy(
	evidence CandidateEvidence,
	coverage ValidationCoverage,
	policy CertificationPolicy,
) (CandidateCertificate, error) {
	if err := coverage.Validate(); err != nil {
		return CandidateCertificate{}, fmt.Errorf(
			"invalid validation coverage: %w",
			err,
		)
	}
	if err := policy.Validate(); err != nil {
		return CandidateCertificate{}, fmt.Errorf(
			"invalid certification policy: %w",
			err,
		)
	}
	if evidence.Candidate.ID == "" {
		return CandidateCertificate{}, fmt.Errorf(
			"candidate ID is empty",
		)
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
	if !evidence.ObservedValidation &&
		(evidence.DecisionFlips > 0 ||
			evidence.ErrorViolations > 0) {
		return CandidateCertificate{}, fmt.Errorf(
			"candidate %s reports validation violations without observed validation",
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
	if !evidence.AnalyticalBoundProvided &&
		evidence.MaxErrorBound != 0 {
		return CandidateCertificate{}, fmt.Errorf(
			"candidate %s supplies a nonzero analytical bound without marking it as provided",
			evidence.Candidate.ID,
		)
	}
	if !isNonNegativeFinite(evidence.MeanTotalMS) {
		return CandidateCertificate{}, fmt.Errorf(
			"candidate %s has invalid mean latency",
			evidence.Candidate.ID,
		)
	}

	analyticalBudget :=
		policy.SafetyFactor * coverage.MinCertifiedMargin

	boundProvided := evidence.AnalyticalBoundProvided
	boundSatisfied :=
		boundProvided &&
			coverage.VCert > 0 &&
			evidence.MaxErrorBound < analyticalBudget

	observedSatisfied :=
		evidence.ObservedValidation &&
			evidence.DecisionFlips == 0 &&
			evidence.ErrorViolations == 0

	certificate := CandidateCertificate{
		Candidate: evidence.Candidate,

		SuccessRuns: evidence.SuccessRuns,
		FailedRuns:  evidence.FailedRuns,

		ObservedValidation: evidence.ObservedValidation,

		DecisionFlips:   evidence.DecisionFlips,
		ErrorViolations: evidence.ErrorViolations,

		MaxObservedError: evidence.MaxObservedError,
		MaxErrorBound:    evidence.MaxErrorBound,

		AnalyticalBoundProvided:  boundProvided,
		AnalyticalBoundSatisfied: boundSatisfied,
		AnalyticalBudget:         analyticalBudget,

		MeanTotalMS: evidence.MeanTotalMS,

		Threshold:    coverage.Threshold,
		MarginFloor:  coverage.MarginFloor,
		SafetyFactor: policy.SafetyFactor,

		VCert: coverage.VCert,
		VAmb:  coverage.VAmb,

		CoverageRate:       coverage.CoverageRate,
		MinMargin:          coverage.MinMargin,
		MinCertifiedMargin: coverage.MinCertifiedMargin,
		P5Margin:           coverage.P5Margin,
	}

	certificate.Assurance = deriveAssurance(
		observedSatisfied,
		boundSatisfied,
	)

	switch {
	case evidence.FailedRuns > 0:
		certificate.Status = StatusFailed
		certificate.Assurance = AssuranceNone
		certificate.Reason = fmt.Sprintf(
			"candidate execution failed in %d run(s)",
			evidence.FailedRuns,
		)

	case evidence.SuccessRuns == 0:
		certificate.Status = StatusFailed
		certificate.Assurance = AssuranceNone
		certificate.Reason =
			"candidate has no successful execution run"

	case evidence.MeanTotalMS <= 0:
		return CandidateCertificate{}, fmt.Errorf(
			"successfully executed candidate %s must have positive mean latency",
			evidence.Candidate.ID,
		)

	case coverage.VCert == 0:
		certificate.Status = StatusAmbiguous
		certificate.Assurance = AssuranceNone
		certificate.Reason =
			"validation set contains no certifiable sample outside the margin floor"

	case evidence.ObservedValidation &&
		(evidence.DecisionFlips > 0 ||
			evidence.ErrorViolations > 0):
		certificate.Status = StatusRejected
		certificate.Assurance = AssuranceNone
		certificate.Reason = fmt.Sprintf(
			"rejected on V_cert: decision_flips=%d error_violations=%d",
			evidence.DecisionFlips,
			evidence.ErrorViolations,
		)

	case policy.RequireObservedValidation &&
		!evidence.ObservedValidation:
		certificate.Status = StatusRejected
		certificate.Assurance = AssuranceNone
		certificate.Reason =
			"required observed validation evidence is missing"

	case policy.RequireAnalyticalBound &&
		!boundProvided:
		certificate.Status = StatusRejected
		certificate.Assurance = AssuranceNone
		certificate.Reason =
			"required analytical error bound is missing"

	case policy.RequireAnalyticalBound &&
		!boundSatisfied:
		certificate.Status = StatusRejected
		certificate.Assurance = AssuranceNone
		certificate.Reason = fmt.Sprintf(
			"analytical bound %.12g does not satisfy strict protected budget %.12g",
			evidence.MaxErrorBound,
			analyticalBudget,
		)

	default:
		certificate.Status = StatusSafe
		certificate.Reason = safeCertificateReason(
			certificate,
		)
	}

	return certificate, nil
}

// CertifyAndSelect applies the default observed-validation policy.
func CertifyAndSelect(
	evidences []CandidateEvidence,
	coverage ValidationCoverage,
) (CertificationSummary, error) {
	return CertifyAndSelectWithPolicy(
		evidences,
		coverage,
		DefaultCertificationPolicy(),
	)
}

// CertifyAndSelectWithPolicy builds candidate certificates and selects the
// lowest-latency SAFE configuration under the supplied policy.
//
// When no SAFE candidate exists, it returns OutcomeNoSafe with Selected=nil.
// This is a normal certify-or-reject outcome rather than an execution error.
func CertifyAndSelectWithPolicy(
	evidences []CandidateEvidence,
	coverage ValidationCoverage,
	policy CertificationPolicy,
) (CertificationSummary, error) {
	if err := coverage.Validate(); err != nil {
		return CertificationSummary{}, fmt.Errorf(
			"invalid validation coverage: %w",
			err,
		)
	}
	if err := policy.Validate(); err != nil {
		return CertificationSummary{}, fmt.Errorf(
			"invalid certification policy: %w",
			err,
		)
	}
	if len(evidences) == 0 {
		return CertificationSummary{}, fmt.Errorf(
			"candidate evidence list is empty",
		)
	}

	analyticalBudget :=
		policy.SafetyFactor * coverage.MinCertifiedMargin

	summary := CertificationSummary{
		Policy: policy,

		CandidateCount: len(evidences),

		Threshold:        coverage.Threshold,
		MarginFloor:      coverage.MarginFloor,
		SafetyFactor:     policy.SafetyFactor,
		AnalyticalBudget: analyticalBudget,

		VCert:        coverage.VCert,
		VAmb:         coverage.VAmb,
		CoverageRate: coverage.CoverageRate,

		Certificates: make(
			[]CandidateCertificate,
			0,
			len(evidences),
		),
	}

	selectedIndex := -1

	for _, evidence := range evidences {
		certificate, err :=
			BuildCandidateCertificateWithPolicy(
				evidence,
				coverage,
				policy,
			)
		if err != nil {
			return CertificationSummary{}, err
		}

		summary.Certificates = append(
			summary.Certificates,
			certificate,
		)
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
			"selected fastest SAFE candidate %s with assurance=%s and mean latency %.6f ms",
			selected.Candidate.ID,
			selected.Assurance,
			selected.MeanTotalMS,
		)

		return summary, nil
	}

	summary.Outcome = OutcomeNoSafe
	summary.Selected = nil
	summary.Reason = noSafeReason(summary)

	return summary, nil
}

func deriveAssurance(
	observedSatisfied bool,
	boundSatisfied bool,
) AssuranceLevel {
	switch {
	case observedSatisfied && boundSatisfied:
		return AssuranceHybrid

	case observedSatisfied:
		return AssuranceObservedValidation

	case boundSatisfied:
		return AssuranceAnalyticalBound

	default:
		return AssuranceNone
	}
}

func safeCertificateReason(
	certificate CandidateCertificate,
) string {
	switch certificate.Assurance {
	case AssuranceHybrid:
		return fmt.Sprintf(
			"observed validation passed on V_cert=%d and analytical bound %.12g is within budget %.12g",
			certificate.VCert,
			certificate.MaxErrorBound,
			certificate.AnalyticalBudget,
		)

	case AssuranceObservedValidation:
		return fmt.Sprintf(
			"zero failures, zero decision flips, and zero error violations on V_cert=%d",
			certificate.VCert,
		)

	case AssuranceAnalyticalBound:
		return fmt.Sprintf(
			"analytical bound %.12g is within protected budget %.12g",
			certificate.MaxErrorBound,
			certificate.AnalyticalBudget,
		)

	default:
		return "certificate requirements satisfied"
	}
}

func noSafeReason(
	summary CertificationSummary,
) string {
	switch {
	case summary.FailedCount == summary.CandidateCount:
		return "no safe candidate: all candidates failed"

	case summary.AmbiguousCount+
		summary.FailedCount == summary.CandidateCount &&
		summary.AmbiguousCount > 0:
		return "no safe candidate: no candidate had a certifiable validation region"

	case summary.RejectedCount+
		summary.FailedCount+
		summary.AmbiguousCount == summary.CandidateCount:
		return "no safe candidate: every candidate was rejected, failed, or ambiguous"

	default:
		return "no safe candidate"
	}
}

func isNonNegativeFinite(value float64) bool {
	return value >= 0 &&
		!math.IsNaN(value) &&
		!math.IsInf(value, 0)
}
