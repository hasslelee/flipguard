package scheduler

import (
	"fmt"
	"math"
	"sort"

	"github.com/hasslelee/flipguard/internal/analysis"
	"github.com/hasslelee/flipguard/internal/ir"
	"github.com/hasslelee/flipguard/internal/runtime"
)

// FlipGuardOptions controls decision-stability-aware precision scheduling.
type FlipGuardOptions struct {
	MinBits runtime.PrecisionBits
	MaxBits runtime.PrecisionBits

	// GlobalTolerance is an optional output-error tolerance.
	// If > 0, the final schedule must satisfy this tolerance.
	GlobalTolerance float64

	// SafetyFactor scales the protected decision margin.
	// For example, SafetyFactor=0.5 means the scheduler uses half of the
	// protected margin as its error budget.
	SafetyFactor float64

	// UseProtectedMargin enables the decision-stability budget:
	//
	//   budget <= SafetyFactor * ProtectedMargin
	//
	// If ProtectedMargin is zero, the scheduler falls back to GlobalTolerance
	// when available. Exact-threshold samples cannot be protected by any
	// nonzero approximation error, so they should be handled as ambiguous
	// boundary samples in the evaluation.
	UseProtectedMargin bool

	ScheduleOptions ScheduleOptions
}

// DefaultFlipGuardOptions returns conservative defaults for the first prototype.
func DefaultFlipGuardOptions() FlipGuardOptions {
	return FlipGuardOptions{
		MinBits: 0,
		MaxBits: 8,

		GlobalTolerance:    0.02,
		SafetyFactor:       0.5,
		UseProtectedMargin: true,

		ScheduleOptions: DefaultIntermediateOptions(),
	}
}

// NodeScheduleReport describes one scheduled node.
type NodeScheduleReport struct {
	NodeID ir.NodeID
	Name   string
	Op     ir.OpType

	Sensitivity  float64
	Bits         runtime.PrecisionBits
	Step         float64
	Delta        float64
	Contribution float64
}

// FlipGuardResult is the output of the scheduler.
type FlipGuardResult struct {
	Schedule runtime.PrecisionSchedule

	Budget         float64
	EstimatedError float64
	Feasible       bool
	BudgetSource   string

	Nodes []NodeScheduleReport
}

// BuildFlipGuardSchedule creates a node-wise precision schedule under the
// decision-stability-aware error budget.
//
// The algorithm starts from MaxBits for all selected nodes and greedily lowers
// precision when doing so does not violate the budget.
func BuildFlipGuardSchedule(
	g *ir.Graph,
	analysisResult *analysis.BoundSensitivityResult,
	opts FlipGuardOptions,
) (*FlipGuardResult, error) {
	if g == nil {
		return nil, fmt.Errorf("graph is nil")
	}
	if analysisResult == nil {
		return nil, fmt.Errorf("analysis result is nil")
	}
	if err := g.Validate(); err != nil {
		return nil, fmt.Errorf("invalid graph: %w", err)
	}

	normalizeFlipGuardOptions(&opts)

	budget, source, err := computeBudget(analysisResult, opts)
	if err != nil {
		return nil, err
	}

	selected := selectedNodes(g, opts.ScheduleOptions)
	schedule := runtime.PrecisionSchedule{}

	for _, n := range selected {
		schedule[n.ID] = opts.MaxBits
	}

	currentError := estimatedError(selected, analysisResult.Sensitivity, schedule)

	result := &FlipGuardResult{
		Schedule:       schedule,
		Budget:         budget,
		EstimatedError: currentError,
		Feasible:       currentError <= budget,
		BudgetSource:   source,
	}

	if !result.Feasible {
		result.Nodes = buildNodeReports(selected, analysisResult.Sensitivity, schedule)
		return result, nil
	}

	for {
		bestIndex := -1
		bestIncrease := math.Inf(1)

		for i, n := range selected {
			currentBits := schedule[n.ID]
			if currentBits <= opts.MinBits {
				continue
			}

			candidateBits := currentBits - 1
			currentContribution := contribution(analysisResult.Sensitivity[n.ID], currentBits)
			candidateContribution := contribution(analysisResult.Sensitivity[n.ID], candidateBits)
			increase := candidateContribution - currentContribution

			if increase < 0 {
				continue
			}

			if currentError+increase <= budget && increase < bestIncrease {
				bestIncrease = increase
				bestIndex = i
			}
		}

		if bestIndex < 0 {
			break
		}

		n := selected[bestIndex]
		schedule[n.ID] = schedule[n.ID] - 1
		currentError += bestIncrease
	}

	result.EstimatedError = estimatedError(selected, analysisResult.Sensitivity, schedule)
	result.Feasible = result.EstimatedError <= budget
	result.Nodes = buildNodeReports(selected, analysisResult.Sensitivity, schedule)

	return result, nil
}

func normalizeFlipGuardOptions(opts *FlipGuardOptions) {
	if opts.MaxBits <= 0 {
		opts.MaxBits = 8
	}
	if opts.MinBits < 0 {
		opts.MinBits = 0
	}
	if opts.MinBits > opts.MaxBits {
		opts.MinBits, opts.MaxBits = opts.MaxBits, opts.MinBits
	}
	if opts.SafetyFactor <= 0 || opts.SafetyFactor > 1 {
		opts.SafetyFactor = 0.5
	}
}

func computeBudget(r *analysis.BoundSensitivityResult, opts FlipGuardOptions) (float64, string, error) {
	budget := math.Inf(1)
	source := "none"

	if opts.GlobalTolerance > 0 {
		budget = opts.GlobalTolerance
		source = "global_tolerance"
	}

	if opts.UseProtectedMargin && r.ProtectedMargin > 0 {
		marginBudget := opts.SafetyFactor * r.ProtectedMargin
		if marginBudget < budget {
			budget = marginBudget
			source = "protected_margin"
		}
	}

	if math.IsInf(budget, 1) {
		return 0, "", fmt.Errorf("no valid error budget: set GlobalTolerance or provide positive ProtectedMargin")
	}

	return budget, source, nil
}

func selectedNodes(g *ir.Graph, opts ScheduleOptions) []*ir.Node {
	nodes := make([]*ir.Node, 0)

	for _, n := range g.Nodes() {
		if !opts.IncludeInputs && n.Op == ir.OpInput {
			continue
		}
		if !opts.IncludeConstants && n.Op == ir.OpConst {
			continue
		}
		if !opts.IncludeOutput && n.ID == g.Output {
			continue
		}

		nodes = append(nodes, n)
	}

	sort.Slice(nodes, func(i, j int) bool {
		return string(nodes[i].ID) < string(nodes[j].ID)
	})

	return nodes
}

func estimatedError(nodes []*ir.Node, sensitivities map[ir.NodeID]float64, schedule runtime.PrecisionSchedule) float64 {
	sum := 0.0

	for _, n := range nodes {
		bits, ok := schedule[n.ID]
		if !ok {
			continue
		}
		sum += contribution(sensitivities[n.ID], bits)
	}

	return sum
}

func contribution(sensitivity float64, bits runtime.PrecisionBits) float64 {
	if sensitivity <= 0 {
		return 0
	}

	step := runtime.StepFromBits(bits)
	delta := step / 2.0

	return sensitivity * delta
}

func buildNodeReports(
	nodes []*ir.Node,
	sensitivities map[ir.NodeID]float64,
	schedule runtime.PrecisionSchedule,
) []NodeScheduleReport {
	reports := make([]NodeScheduleReport, 0, len(nodes))

	for _, n := range nodes {
		bits, ok := schedule[n.ID]
		if !ok {
			continue
		}

		step := runtime.StepFromBits(bits)
		delta := step / 2.0
		s := sensitivities[n.ID]

		reports = append(reports, NodeScheduleReport{
			NodeID:       n.ID,
			Name:         n.Name,
			Op:           n.Op,
			Sensitivity:  s,
			Bits:         bits,
			Step:         step,
			Delta:        delta,
			Contribution: s * delta,
		})
	}

	return reports
}
