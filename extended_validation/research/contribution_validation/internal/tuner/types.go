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
	ID          string `json:"id"`
	LogN        int    `json:"log_n"`
	Slots       int    `json:"slots"`
	ChainLength int    `json:"chain_length"`
	ScaleBits   int    `json:"scale_bits"`
	Family      string `json:"family"`
	IsReference bool   `json:"is_reference"`
}

// ExecutionConfiguration is the actual candidate evaluated by FlipGuard.
type ExecutionConfiguration struct {
	Candidate ParameterCandidate `json:"candidate"`
	Path      ExecutionPath      `json:"path"`
}

// WorkloadSpec describes a fixed model/data/threshold setting.
// A selected configuration is valid for this workload, not universally.
type WorkloadSpec struct {
	Dataset        string  `json:"dataset"`
	Model          string  `json:"model"`
	Threshold      float64 `json:"threshold"`
	ErrorTolerance float64 `json:"error_tolerance"`
	NumSamples     int     `json:"num_samples"`
}

// GraphSummary is a lightweight model-graph summary used for candidate generation
// and cost estimation. It can later be filled from actual model metadata.
type GraphSummary struct {
	MultiplicativeDepth int      `json:"multiplicative_depth"`
	AddOps              int      `json:"add_ops"`
	MulOps              int      `json:"mul_ops"`
	RotOps              int      `json:"rot_ops"`
	RescaleOps          int      `json:"rescale_ops"`
	Notes               []string `json:"notes,omitempty"`
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
