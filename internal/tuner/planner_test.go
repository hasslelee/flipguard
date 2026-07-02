package tuner

import (
	"strings"
	"testing"
)

func TestPlanCandidatesDerivesSmallCandidateSet(t *testing.T) {
	graph := GraphSummary{
		MultiplicativeDepth: 3,
		AddOps:              5,
		MulOps:              4,
		RotOps:              0,
		RescaleOps:          3,
	}

	decision := DecisionBudgetSummary{
		OutputErrorBudget: 1e-3,
		SensitivityFactor: 4.0,
	}

	policy := DefaultPlannerPolicy()

	plan, err := PlanCandidates(graph, decision, policy)
	if err != nil {
		t.Fatalf("PlanCandidates failed: %v", err)
	}

	if len(plan.Configurations) == 0 {
		t.Fatal("expected planned candidates")
	}

	if len(plan.Configurations) > policy.MaxCandidates {
		t.Fatalf("expected at most %d candidates, got %d", policy.MaxCandidates, len(plan.Configurations))
	}

	if plan.PlannedChainLength != 5 {
		t.Fatalf("expected chain depth+margin = 5, got %d", plan.PlannedChainLength)
	}

	if plan.PlannedScaleBits < policy.MinScaleBits {
		t.Fatalf("planned scale below policy minimum: %d", plan.PlannedScaleBits)
	}

	if !strings.Contains(plan.Reason, "budget=") {
		t.Fatalf("expected reason to include budget, got %q", plan.Reason)
	}

	if !containsPlannerFamily(plan.Configurations, "planner_min_feasible") {
		t.Fatal("expected planner_min_feasible candidate")
	}

	if !containsReferenceCandidate(plan.Configurations) {
		t.Fatal("expected reference candidate")
	}
}

func TestPlanCandidatesTightBudgetRaisesScale(t *testing.T) {
	graph := GraphSummary{
		MultiplicativeDepth: 3,
		AddOps:              5,
		MulOps:              4,
		RescaleOps:          3,
	}

	policy := DefaultPlannerPolicy()
	policy.IncludeReference = false
	policy.Paths = []ExecutionPath{PathNonRescale}

	// Lower the minimum scale for this unit test so that the mathematical
	// effect of a tighter decision budget is visible instead of being hidden by
	// the production-oriented MinScaleBits clamp.
	policy.MinScaleBits = 8
	policy.MaxScaleBits = 60

	loose, err := PlanCandidates(graph, DecisionBudgetSummary{
		OutputErrorBudget: 1e-2,
		SensitivityFactor: 2.0,
	}, policy)
	if err != nil {
		t.Fatalf("loose PlanCandidates failed: %v", err)
	}

	tight, err := PlanCandidates(graph, DecisionBudgetSummary{
		OutputErrorBudget: 1e-6,
		SensitivityFactor: 2.0,
	}, policy)
	if err != nil {
		t.Fatalf("tight PlanCandidates failed: %v", err)
	}

	if tight.PlannedScaleBits <= loose.PlannedScaleBits {
		t.Fatalf(
			"expected tighter budget to require larger scale: loose=%d tight=%d",
			loose.PlannedScaleBits,
			tight.PlannedScaleBits,
		)
	}
}

func TestPlanCandidatesUsesProtectedMargin(t *testing.T) {
	graph := GraphSummary{
		MultiplicativeDepth: 2,
		MulOps:              2,
		RescaleOps:          2,
	}

	policy := DefaultPlannerPolicy()
	policy.IncludeReference = false
	policy.Paths = []ExecutionPath{PathNonRescale}

	plan, err := PlanCandidates(graph, DecisionBudgetSummary{
		ProtectedMargin:   0.02,
		SafetyFactor:      0.25,
		SensitivityFactor: 1.0,
	}, policy)
	if err != nil {
		t.Fatalf("PlanCandidates failed: %v", err)
	}

	if plan.Budget != 0.005 {
		t.Fatalf("expected budget 0.005, got %.12f", plan.Budget)
	}
}

func TestPlanCandidatesRejectsMissingBudget(t *testing.T) {
	graph := GraphSummary{
		MultiplicativeDepth: 1,
		MulOps:              1,
	}

	_, err := PlanCandidates(graph, DecisionBudgetSummary{}, DefaultPlannerPolicy())
	if err == nil {
		t.Fatal("expected missing decision budget error")
	}
}

func TestPlanCandidatesCanIncludeAggressiveCandidate(t *testing.T) {
	graph := GraphSummary{
		MultiplicativeDepth: 4,
		MulOps:              5,
		RescaleOps:          4,
	}

	policy := DefaultPlannerPolicy()
	policy.IncludeReference = false
	policy.IncludeAggressive = true
	policy.Paths = []ExecutionPath{PathNonRescale}

	plan, err := PlanCandidates(graph, DecisionBudgetSummary{
		OutputErrorBudget: 1e-3,
		SensitivityFactor: 2.0,
	}, policy)
	if err != nil {
		t.Fatalf("PlanCandidates failed: %v", err)
	}

	if !containsPlannerFamily(plan.Configurations, "planner_aggressive") {
		t.Fatal("expected planner_aggressive candidate")
	}
}

func containsPlannerFamily(configs []ExecutionConfiguration, family string) bool {
	for _, cfg := range configs {
		if cfg.Candidate.Family == family {
			return true
		}
	}

	return false
}

func containsReferenceCandidate(configs []ExecutionConfiguration) bool {
	for _, cfg := range configs {
		if cfg.Candidate.IsReference {
			return true
		}
	}

	return false
}
