package tuner

// ExecutionPath identifies how a CKKS configuration is executed.
// It is separated from the parameter candidate because the same
// chain/scale/N setting can be evaluated with different execution paths.
type ExecutionPath string

const (
	PathRescale    ExecutionPath = "rescale"
	PathNonRescale ExecutionPath = "non-rescale"
)

// ParameterCandidate describes CKKS parameter-side choices.
// The name Reference should be preferred over Default in paper-facing code.
type ParameterCandidate struct {
	ID          string
	LogN        int
	Slots       int
	ChainLength int
	ScaleBits   int
	Family      string
	IsReference bool
}

// ExecutionConfiguration is the actual candidate evaluated by FlipGuard.
type ExecutionConfiguration struct {
	Candidate ParameterCandidate
	Path      ExecutionPath
}

// WorkloadSpec describes a fixed model/data/threshold setting.
// A selected configuration is valid for this workload, not universally.
type WorkloadSpec struct {
	Dataset        string
	Model          string
	Threshold      float64
	ErrorTolerance float64
	NumSamples     int
}

// GraphSummary is a lightweight model-graph summary used for candidate generation
// and cost estimation. It can later be filled from actual model metadata.
type GraphSummary struct {
	MultiplicativeDepth int
	AddOps              int
	MulOps              int
	RotOps              int
	RescaleOps          int
	Notes               []string
}

// ReferencePolicy controls how a conservative reference configuration is built.
type ReferencePolicy struct {
	SecurityBits     int
	InitialScaleBits int
	ChainMargin      int
	MinLogN          int
	MaxLogN          int
}

// CandidateGenerationOptions controls the local search space around a reference.
type CandidateGenerationOptions struct {
	ChainDeltas []int
	ScaleDeltas []int
	LogNDeltas  []int
	Paths       []ExecutionPath
}

// CandidateEvaluation stores observed validation and latency results.
type CandidateEvaluation struct {
	Config          ExecutionConfiguration
	SuccessRuns     int
	FailedRuns      int
	DecisionFlips   int
	ErrorViolations int
	MaxOutputError  float64
	MeanTotalMS     float64
}

// Status returns a paper-friendly safety label.
func (e CandidateEvaluation) Status() string {
	if e.FailedRuns > 0 {
		return "FAILED"
	}
	if e.DecisionFlips > 0 || e.ErrorViolations > 0 {
		return "REJECTED"
	}
	return "SAFE"
}

// IsSafe returns true only when the candidate satisfies all safety conditions.
func (e CandidateEvaluation) IsSafe() bool {
	return e.Status() == "SAFE"
}
