package certify

// CandidateDescriptor identifies one CKKS execution configuration.
//
// The structure intentionally mirrors the paper-facing configuration fields
// without depending on the tuner package. A tuner adapter can be added later.
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
// DecisionFlips and ErrorViolations should refer to V_cert. Samples in V_amb
// are reported through ValidationCoverage and are not claimed as certified.
type CandidateEvidence struct {
	Candidate CandidateDescriptor

	SuccessRuns int
	FailedRuns  int

	DecisionFlips   int
	ErrorViolations int

	MaxObservedError float64

	// MaxErrorBound is optional. Zero means that no analytical bound was
	// supplied for this candidate.
	MaxErrorBound float64

	MeanTotalMS float64
}

// CandidateCertificate is the paper-facing certificate for one configuration.
type CandidateCertificate struct {
	Candidate CandidateDescriptor

	Status CandidateStatus
	Reason string

	SuccessRuns int
	FailedRuns  int

	DecisionFlips   int
	ErrorViolations int

	MaxObservedError float64
	MaxErrorBound    float64

	MeanTotalMS float64

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

	CandidateCount int

	SafeCount      int
	RejectedCount  int
	FailedCount    int
	AmbiguousCount int

	VCert        int
	VAmb         int
	CoverageRate float64

	Certificates []CandidateCertificate

	// Selected is non-nil only when Outcome is SELECTED.
	Selected *CandidateCertificate
}
