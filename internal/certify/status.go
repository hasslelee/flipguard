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
