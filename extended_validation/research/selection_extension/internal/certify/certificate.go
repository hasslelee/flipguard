package certify

// CandidateDescriptor identifies one CKKS execution configuration.
//
// The structure intentionally mirrors paper-facing configuration fields without
// depending on the tuner package. A tuner adapter is added separately.
type CandidateDescriptor struct {
	ID string

	Path string

	LogN        int
	Slots       int
	ChainLength int
	ScaleBits   int

	Family      string
	IsReference bool
}

// CandidateEvidence contains observed execution and validation evidence for one
// candidate.
//
// DecisionFlips and ErrorViolations must refer to V_cert when
// ObservedValidation is true. Samples in V_amb are reported separately and are
// not included in the decision-stability claim.
type CandidateEvidence struct {
	Candidate CandidateDescriptor

	SuccessRuns int
	FailedRuns  int

	// ObservedValidation is true only when the candidate was validated over
	// the claim's V_cert subset.
	ObservedValidation bool

	DecisionFlips   int
	ErrorViolations int

	MaxObservedError float64
	// MaxObservedBudgetUsage is max(error / (alpha * margin)) on V_cert.
	// SafetyFactor is retained as the backward-compatible execution/schema
	// name for alpha. Paper-facing reports interpret alpha as a margin
	// utilization cap, not as a theorem-derived safety constant.
	MaxObservedBudgetUsage float64

	// AnalyticalBoundProvided explicitly states whether MaxErrorBound contains
	// an analytical certificate bound. Presence is represented separately
	// because zero is a valid bound value.
	AnalyticalBoundProvided bool
	MaxErrorBound           float64
	AnalyticalProof         *AnalyticalBoundProof

	MeanTotalMS float64
}

// CandidateCertificate is the paper-facing certificate for one configuration.
type CandidateCertificate struct {
	Candidate CandidateDescriptor

	Status    CandidateStatus
	Assurance AssuranceLevel
	Reason    string

	SuccessRuns int
	FailedRuns  int

	ObservedValidation bool

	DecisionFlips   int
	ErrorViolations int

	MaxObservedError       float64
	MaxObservedBudgetUsage float64
	MaxErrorBound          float64

	AnalyticalBoundProvided  bool
	AnalyticalBoundSatisfied bool
	AnalyticalBudget         float64
	AnalyticalProof          *AnalyticalBoundProof

	MeanTotalMS float64

	Threshold   float64
	MarginFloor float64
	// SafetyFactor is the backward-compatible name for the operational margin
	// utilization cap. Use InterpretSafetyFactor for paper-facing reports.
	SafetyFactor float64

	VCert int
	VAmb  int

	CoverageRate       float64
	MinMargin          float64
	MinCertifiedMargin float64
	P5Margin           float64
}

// CertificationSummary is the final certify-or-reject result.
type CertificationSummary struct {
	Outcome SelectionOutcome
	Reason  string

	Policy CertificationPolicy

	CandidateCount int

	SafeCount      int
	RejectedCount  int
	FailedCount    int
	AmbiguousCount int

	Threshold   float64
	MarginFloor float64
	// SafetyFactor is retained for evidence reproducibility. It is an
	// operational margin utilization cap, not a CKKS security parameter.
	SafetyFactor     float64
	AnalyticalBudget float64

	VCert        int
	VAmb         int
	CoverageRate float64

	Certificates []CandidateCertificate

	// Selected is non-nil only when Outcome is SELECTED.
	Selected *CandidateCertificate
}
