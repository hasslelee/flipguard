package certify

// CandidateStatus describes the certification result of one executed
// configuration over the certified validation subset.
type CandidateStatus string

const (
	StatusSafe      CandidateStatus = "SAFE"
	StatusRejected  CandidateStatus = "REJECTED"
	StatusFailed    CandidateStatus = "FAILED"
	StatusAmbiguous CandidateStatus = "AMBIGUOUS"
)

// String returns the paper-facing status label.
func (s CandidateStatus) String() string {
	return string(s)
}

// AssuranceLevel identifies the evidence supporting a SAFE certificate.
type AssuranceLevel string

const (
	// AssuranceNone means that no certification evidence is sufficient.
	AssuranceNone AssuranceLevel = "NONE"

	// AssuranceObservedValidation means that observed CKKS validation over
	// V_cert produced zero decision flips and zero error violations.
	AssuranceObservedValidation AssuranceLevel = "OBSERVED_VALIDATION"

	// AssuranceAnalyticalBound means that an analytical error bound is no
	// larger than the protected decision-margin budget.
	AssuranceAnalyticalBound AssuranceLevel = "ANALYTICAL_BOUND"

	// AssuranceHybrid means that both observed validation and the analytical
	// bound condition are satisfied.
	AssuranceHybrid AssuranceLevel = "HYBRID"
)

// String returns the paper-facing assurance label.
func (a AssuranceLevel) String() string {
	return string(a)
}

// SelectionOutcome describes the final result of certify-or-reject selection.
type SelectionOutcome string

const (
	OutcomeSelected SelectionOutcome = "SELECTED"
	OutcomeNoSafe   SelectionOutcome = "NO_SAFE"
)

// String returns the paper-facing selection outcome.
func (o SelectionOutcome) String() string {
	return string(o)
}
