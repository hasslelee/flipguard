package tuner

import (
	"fmt"
	"math"
	"sort"
	"strings"
)

// DecisionBudgetSummary summarizes the decision-stability budget available to
// the candidate planner.
//
// The planner is intentionally not a grid search. It derives a small feasible
// region from:
//
//   - graph multiplicative depth,
//   - a decision/output error budget,
//   - a conservative sensitivity estimate,
//   - a security-driven LogN lower bound.
//
// OutputErrorBudget is usually derived from a certificate condition such as:
//
//	B_pi(x) + B_CKKS(x) < M(x)
//
// where M(x) is the decision margin. ProtectedMargin can be supplied when the
// caller wants the planner to derive the budget as SafetyFactor*ProtectedMargin.
type DecisionBudgetSummary struct {
	ProtectedMargin   float64
	OutputErrorBudget float64

	// SensitivityFactor upper-bounds how much local CKKS error may be amplified
	// at the program output. If it is zero, the planner uses a graph-derived
	// conservative estimate.
	SensitivityFactor float64

	// SafetyFactor is used only when ProtectedMargin is provided. If zero, the
	// default safety factor is used.
	SafetyFactor float64
}

// PlannerPolicy controls analysis-driven candidate planning.
type PlannerPolicy struct {
	SecurityBits int

	MinLogN int
	MaxLogN int

	MinScaleBits int
	MaxScaleBits int

	// ChainMargin is added to multiplicative depth to obtain the minimum chain.
	ChainMargin int

	// ScaleGuardBits is added after converting the output budget to scale bits.
	ScaleGuardBits int

	// IncludeReference inserts a conservative reference configuration.
	IncludeReference bool

	// IncludeAggressive adds one intentionally aggressive candidate below the
	// derived feasible point. This is useful for demonstrating that latency-only
	// choices can violate decision stability, but it is not required for normal
	// deployment.
	IncludeAggressive bool

	// MaxCandidates caps the number of returned configurations. The planner
	// emits candidates in priority order, so truncation preserves the most
	// relevant candidates.
	MaxCandidates int

	// Paths controls whether the planner emits rescale, non-rescale, or both
	// execution paths.
	Paths []ExecutionPath

	// Reference controls the conservative baseline candidate.
	Reference ReferencePolicy
}

// CandidatePlan is the result of analysis-driven candidate planning.
type CandidatePlan struct {
	Configurations []ExecutionConfiguration

	Budget          float64
	Sensitivity     float64
	UnitErrorBudget float64

	PlannedChainLength int
	PlannedScaleBits   int
	PlannedLogN        int
	EstimatedLogQP     int

	Reason string
}

// DefaultPlannerPolicy returns a conservative analysis-driven planning policy.
func DefaultPlannerPolicy() PlannerPolicy {
	return PlannerPolicy{
		SecurityBits: 128,

		MinLogN: 14,
		MaxLogN: 15,

		MinScaleBits: 30,
		MaxScaleBits: 60,

		ChainMargin:    2,
		ScaleGuardBits: 2,

		IncludeReference:  true,
		IncludeAggressive: false,

		MaxCandidates: 8,

		Paths: []ExecutionPath{
			PathNonRescale,
			PathRescale,
		},

		Reference: ReferencePolicy{
			SecurityBits:     128,
			InitialScaleBits: 45,
			ChainMargin:      4,
			MinLogN:          14,
			MaxLogN:          15,
		},
	}
}

// PlanCandidates derives a small set of CKKS execution candidates from graph
// and decision-budget information.
//
// This function is deliberately different from GenerateAroundReference. It does
// not enumerate chain/scale deltas around a reference. Instead, it computes one
// minimum feasible point and emits a few Pareto-neighbor candidates.
func PlanCandidates(
	graph GraphSummary,
	decision DecisionBudgetSummary,
	policy PlannerPolicy,
) (CandidatePlan, error) {
	policy = normalizePlannerPolicy(policy)

	if err := validatePlannerGraph(graph); err != nil {
		return CandidatePlan{}, err
	}

	budget, err := plannerBudget(decision)
	if err != nil {
		return CandidatePlan{}, err
	}

	sensitivity := decision.SensitivityFactor
	if sensitivity <= 0 {
		sensitivity = estimatePlannerSensitivity(graph)
	}

	unitBudget := budget / sensitivity
	if unitBudget <= 0 || math.IsNaN(unitBudget) || math.IsInf(unitBudget, 0) {
		return CandidatePlan{}, fmt.Errorf("invalid unit error budget %.12g", unitBudget)
	}

	scaleBits := scaleBitsForUnitBudget(unitBudget, policy)
	chainLength := chainLengthForGraph(graph, policy)

	estimatedLogQP := estimateLogQPBits(chainLength, scaleBits)
	logN := logNForSecurity(estimatedLogQP, policy)

	configs := make([]ExecutionConfiguration, 0, policy.MaxCandidates)

	if policy.IncludeReference {
		refCandidate := BuildReferenceConfiguration(graph, policy.Reference)
		refConfig := ExecutionConfiguration{
			Candidate: refCandidate,
			Path:      PathRescale,
		}
		configs = appendUniquePlannedConfig(configs, refConfig, policy.MaxCandidates)
	}

	baseCandidates := []plannedCandidateSpec{
		{
			Family:      "planner_min_feasible",
			ChainLength: chainLength,
			ScaleBits:   scaleBits,
			LogN:        logN,
		},
		{
			Family:      "planner_chain_guard",
			ChainLength: chainLength + 1,
			ScaleBits:   scaleBits,
			LogN:        logN,
		},
		{
			Family:      "planner_scale_guard",
			ChainLength: chainLength,
			ScaleBits:   clampPlannerInt(scaleBits+2, policy.MinScaleBits, policy.MaxScaleBits),
			LogN:        logN,
		},
	}

	if policy.IncludeAggressive {
		baseCandidates = append(baseCandidates, plannedCandidateSpec{
			Family:      "planner_aggressive",
			ChainLength: clampPlannerInt(chainLength-1, minChainLength, chainLength),
			ScaleBits:   clampPlannerInt(scaleBits-2, policy.MinScaleBits, policy.MaxScaleBits),
			LogN:        logN,
		})
	}

	for _, spec := range baseCandidates {
		for _, path := range policy.Paths {
			cfg := plannedExecutionConfiguration(spec, path)
			configs = appendUniquePlannedConfig(configs, cfg, policy.MaxCandidates)
		}
	}

	sortPlannedConfigs(configs)

	plan := CandidatePlan{
		Configurations: configs,

		Budget:          budget,
		Sensitivity:     sensitivity,
		UnitErrorBudget: unitBudget,

		PlannedChainLength: chainLength,
		PlannedScaleBits:   scaleBits,
		PlannedLogN:        logN,
		EstimatedLogQP:     estimatedLogQP,

		Reason: fmt.Sprintf(
			"budget=%.6g sensitivity=%.6g unit_budget=%.6g depth=%d chain=%d scale=%d logN=%d logQP≈%d",
			budget,
			sensitivity,
			unitBudget,
			graph.MultiplicativeDepth,
			chainLength,
			scaleBits,
			logN,
			estimatedLogQP,
		),
	}

	return plan, nil
}

type plannedCandidateSpec struct {
	Family      string
	ChainLength int
	ScaleBits   int
	LogN        int
}

func normalizePlannerPolicy(policy PlannerPolicy) PlannerPolicy {
	defaults := DefaultPlannerPolicy()

	if policy.SecurityBits <= 0 {
		policy.SecurityBits = defaults.SecurityBits
	}

	if policy.MinLogN <= 0 {
		policy.MinLogN = defaults.MinLogN
	}
	if policy.MaxLogN <= 0 {
		policy.MaxLogN = defaults.MaxLogN
	}
	if policy.MaxLogN < policy.MinLogN {
		policy.MaxLogN = policy.MinLogN
	}

	if policy.MinScaleBits <= 0 {
		policy.MinScaleBits = defaults.MinScaleBits
	}
	if policy.MaxScaleBits <= 0 {
		policy.MaxScaleBits = defaults.MaxScaleBits
	}
	if policy.MaxScaleBits < policy.MinScaleBits {
		policy.MaxScaleBits = policy.MinScaleBits
	}

	if policy.ChainMargin < 0 {
		policy.ChainMargin = defaults.ChainMargin
	}
	if policy.ChainMargin == 0 {
		policy.ChainMargin = defaults.ChainMargin
	}

	if policy.ScaleGuardBits < 0 {
		policy.ScaleGuardBits = defaults.ScaleGuardBits
	}
	if policy.ScaleGuardBits == 0 {
		policy.ScaleGuardBits = defaults.ScaleGuardBits
	}

	if policy.MaxCandidates <= 0 {
		policy.MaxCandidates = defaults.MaxCandidates
	}

	if len(policy.Paths) == 0 {
		policy.Paths = defaults.Paths
	}

	if policy.Reference.SecurityBits <= 0 {
		policy.Reference.SecurityBits = policy.SecurityBits
	}
	if policy.Reference.InitialScaleBits <= 0 {
		policy.Reference.InitialScaleBits = defaults.Reference.InitialScaleBits
	}
	if policy.Reference.ChainMargin <= 0 {
		policy.Reference.ChainMargin = defaults.Reference.ChainMargin
	}
	if policy.Reference.MinLogN <= 0 {
		policy.Reference.MinLogN = policy.MinLogN
	}
	if policy.Reference.MaxLogN <= 0 {
		policy.Reference.MaxLogN = policy.MaxLogN
	}

	return policy
}

func validatePlannerGraph(graph GraphSummary) error {
	if graph.MultiplicativeDepth < 0 {
		return fmt.Errorf("multiplicative depth must be non-negative")
	}
	if graph.MulOps < 0 {
		return fmt.Errorf("mul ops must be non-negative")
	}
	if graph.AddOps < 0 {
		return fmt.Errorf("add ops must be non-negative")
	}
	if graph.RotOps < 0 {
		return fmt.Errorf("rot ops must be non-negative")
	}
	if graph.RescaleOps < 0 {
		return fmt.Errorf("rescale ops must be non-negative")
	}

	return nil
}

func plannerBudget(decision DecisionBudgetSummary) (float64, error) {
	budget := decision.OutputErrorBudget

	if decision.ProtectedMargin > 0 {
		safetyFactor := decision.SafetyFactor
		if safetyFactor <= 0 {
			safetyFactor = 0.5
		}

		marginBudget := decision.ProtectedMargin * safetyFactor
		if budget <= 0 || marginBudget < budget {
			budget = marginBudget
		}
	}

	if budget <= 0 || math.IsNaN(budget) || math.IsInf(budget, 0) {
		return 0, fmt.Errorf("decision budget must be positive")
	}

	return budget, nil
}

func estimatePlannerSensitivity(graph GraphSummary) float64 {
	// This is intentionally conservative and deterministic. It is not claiming
	// to be a tight Lipschitz bound. The purpose is to derive a first feasible
	// region before measuring a very small number of candidates.
	sensitivity := 1.0
	sensitivity += 0.25 * float64(graph.MultiplicativeDepth)
	sensitivity += 0.15 * float64(graph.MulOps)
	sensitivity += 0.05 * float64(graph.AddOps)
	sensitivity += 0.10 * float64(graph.RotOps)

	if sensitivity < 1.0 {
		return 1.0
	}

	return sensitivity
}

func scaleBitsForUnitBudget(unitBudget float64, policy PlannerPolicy) int {
	if unitBudget >= 1 {
		return policy.MinScaleBits
	}

	raw := int(math.Ceil(-math.Log2(unitBudget))) + policy.ScaleGuardBits
	return clampPlannerInt(raw, policy.MinScaleBits, policy.MaxScaleBits)
}

func chainLengthForGraph(graph GraphSummary, policy PlannerPolicy) int {
	chain := graph.MultiplicativeDepth + policy.ChainMargin
	if graph.RescaleOps > graph.MultiplicativeDepth {
		chain = graph.RescaleOps + policy.ChainMargin
	}

	if chain < minChainLength {
		chain = minChainLength
	}

	return chain
}

func estimateLogQPBits(chainLength int, scaleBits int) int {
	// Approximate total modulus size. The +120 term models special primes used
	// for key switching in the current profile family.
	return chainLength*scaleBits + 120
}

func logNForSecurity(logQPBits int, policy PlannerPolicy) int {
	// Conservative 128-bit-oriented lookup used for planning. The exact security
	// validation still belongs to the CKKS backend/profile layer.
	logN := policy.MinLogN

	switch {
	case logQPBits <= 220:
		logN = maxPlannerInt(logN, 13)
	case logQPBits <= 438:
		logN = maxPlannerInt(logN, 14)
	case logQPBits <= 881:
		logN = maxPlannerInt(logN, 15)
	default:
		logN = maxPlannerInt(logN, 16)
	}

	if policy.SecurityBits > 128 {
		logN++
	}

	return clampPlannerInt(logN, policy.MinLogN, policy.MaxLogN)
}

func plannedExecutionConfiguration(
	spec plannedCandidateSpec,
	path ExecutionPath,
) ExecutionConfiguration {
	candidate := ParameterCandidate{
		ID:          plannedCandidateID(spec, path),
		LogN:        spec.LogN,
		Slots:       1 << (spec.LogN - 1),
		ChainLength: spec.ChainLength,
		ScaleBits:   spec.ScaleBits,
		Family:      spec.Family,
		IsReference: false,
	}

	return ExecutionConfiguration{
		Candidate: candidate,
		Path:      path,
	}
}

func plannedCandidateID(spec plannedCandidateSpec, path ExecutionPath) string {
	pathName := strings.ReplaceAll(string(path), "-", "_")
	return fmt.Sprintf(
		"%s_chain%d_scale%d_N%d_%s",
		spec.Family,
		spec.ChainLength,
		spec.ScaleBits,
		spec.LogN,
		pathName,
	)
}

func appendUniquePlannedConfig(
	configs []ExecutionConfiguration,
	cfg ExecutionConfiguration,
	maxCandidates int,
) []ExecutionConfiguration {
	if len(configs) >= maxCandidates {
		return configs
	}

	key := plannedConfigKey(cfg)
	for _, existing := range configs {
		if plannedConfigKey(existing) == key {
			return configs
		}
	}

	return append(configs, cfg)
}

func plannedConfigKey(cfg ExecutionConfiguration) string {
	c := cfg.Candidate
	return fmt.Sprintf(
		"%s/%s/%d/%d/%d",
		cfg.Path,
		c.Family,
		c.LogN,
		c.ChainLength,
		c.ScaleBits,
	)
}

func sortPlannedConfigs(configs []ExecutionConfiguration) {
	sort.SliceStable(configs, func(i int, j int) bool {
		ci := configs[i].Candidate
		cj := configs[j].Candidate

		if ci.IsReference != cj.IsReference {
			return ci.IsReference
		}

		if ci.ChainLength != cj.ChainLength {
			return ci.ChainLength < cj.ChainLength
		}
		if ci.ScaleBits != cj.ScaleBits {
			return ci.ScaleBits < cj.ScaleBits
		}
		if ci.LogN != cj.LogN {
			return ci.LogN < cj.LogN
		}

		return string(configs[i].Path) < string(configs[j].Path)
	})
}

func clampPlannerInt(value int, minValue int, maxValue int) int {
	if value < minValue {
		return minValue
	}
	if value > maxValue {
		return maxValue
	}
	return value
}

func maxPlannerInt(a int, b int) int {
	if a > b {
		return a
	}
	return b
}
