package experiment

import (
	"encoding/csv"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/hasslelee/flipguard/internal/benchmarks"
	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/ir"
	"github.com/hasslelee/flipguard/internal/runtime"
	"github.com/hasslelee/flipguard/internal/tuner"
)

const tunerPlannerDemoOutputDir = "results/tuner_planner_demo"

type plannerDemoWorkload struct {
	Name      string
	Label     string
	Graph     *ir.Graph
	Samples   []plannerDemoSample
	Threshold float64
}

type plannerDemoSample struct {
	Inputs      map[ir.NodeID]float64
	PlainOutput float64
	Margin      float64
}

type plannerDemoWorkloadRow struct {
	Workload        string
	Label           string
	NodeCount       int
	SampleCount     int
	Threshold       float64
	MinMargin       float64
	P10Margin       float64
	ProtectedMargin float64

	MultiplicativeDepth int
	AddOps              int
	MulOps              int
	RotOps              int
	RescaleOps          int

	Budget          float64
	Sensitivity     float64
	UnitErrorBudget float64

	PlannedChainLength int
	PlannedScaleBits   int
	PlannedLogN        int
	EstimatedLogQP     int
	CandidateCount     int
	MatchCount         int
	UniqueProfileCount int

	Reason string
}

type plannerDemoCandidateRow struct {
	Workload string
	Rank     int

	CandidateID string
	Path        tuner.ExecutionPath

	LogN        int
	Slots       int
	ChainLength int
	ScaleBits   int
	Family      string
	IsReference bool

	PredictedRelativeCost float64
	CostReason            string
}

type plannerDemoProfileMatchRow struct {
	Workload string
	Rank     int

	PlannedCandidateID string
	PlannedPath        tuner.ExecutionPath
	PlannedFamily      string
	PlannedChainLength int
	PlannedScaleBits   int
	PlannedLogN        int

	ProfileName        string
	ProfileDescription string
	ProfileFamily      string
	ProfileChainLength int
	ProfileScaleBits   int
	ProfileLogN        int
	ProfileSlots       int

	Distance         float64
	ChainGap         int
	ScaleGap         int
	LogNGap          int
	UnderProvisioned bool

	Reason string
}

func RunTunerPlannerDemo() error {
	workloads, err := buildPlannerDemoWorkloads()
	if err != nil {
		return fmt.Errorf("build planner demo workloads: %w", err)
	}

	availableProfiles := plannerAvailableProfiles(ckksbackend.AllCKKSProfiles())

	options := GetRuntimeOptions()
	outputErrorBudget := options.CKKSScoreAbsErrorCap
	if outputErrorBudget <= 0 {
		outputErrorBudget = 1e-3
	}

	safetyFactor := options.CKKSSafetyFactor
	if safetyFactor <= 0 {
		safetyFactor = 0.5
	}

	policy := tuner.DefaultPlannerPolicy()
	policy.IncludeReference = true
	policy.IncludeAggressive = true
	policy.MaxCandidates = 8
	policy.Paths = []tuner.ExecutionPath{
		tuner.PathNonRescale,
		tuner.PathRescale,
	}

	resolverPolicy := tuner.DefaultProfileResolverPolicy()
	resolverPolicy.MaxMatchesPerCandidate = 2

	workloadRows := make([]plannerDemoWorkloadRow, 0, len(workloads))
	candidateRows := make([]plannerDemoCandidateRow, 0, len(workloads)*policy.MaxCandidates)
	matchRows := make([]plannerDemoProfileMatchRow, 0, len(workloads)*policy.MaxCandidates*resolverPolicy.MaxMatchesPerCandidate)

	for _, workload := range workloads {
		graphSummary, err := summarizeGraphForPlanner(workload.Graph)
		if err != nil {
			return fmt.Errorf("summarize graph for workload %s: %w", workload.Name, err)
		}

		minMargin, p10Margin, protectedMargin := summarizePlannerMargins(workload.Samples)

		plan, err := tuner.PlanCandidates(
			graphSummary,
			tuner.DecisionBudgetSummary{
				ProtectedMargin:   protectedMargin,
				OutputErrorBudget: outputErrorBudget,
				SafetyFactor:      safetyFactor,
			},
			policy,
		)
		if err != nil {
			return fmt.Errorf("plan candidates for workload %s: %w", workload.Name, err)
		}

		matches, err := tuner.ResolveClosestProfiles(plan.Configurations, availableProfiles, resolverPolicy)
		if err != nil {
			return fmt.Errorf("resolve planner candidates for workload %s: %w", workload.Name, err)
		}

		uniqueMatches := tuner.DeduplicateResolvedProfiles(matches)

		workloadRows = append(workloadRows, plannerDemoWorkloadRow{
			Workload:        workload.Name,
			Label:           workload.Label,
			NodeCount:       len(workload.Graph.Nodes()),
			SampleCount:     len(workload.Samples),
			Threshold:       workload.Threshold,
			MinMargin:       minMargin,
			P10Margin:       p10Margin,
			ProtectedMargin: protectedMargin,

			MultiplicativeDepth: graphSummary.MultiplicativeDepth,
			AddOps:              graphSummary.AddOps,
			MulOps:              graphSummary.MulOps,
			RotOps:              graphSummary.RotOps,
			RescaleOps:          graphSummary.RescaleOps,

			Budget:          plan.Budget,
			Sensitivity:     plan.Sensitivity,
			UnitErrorBudget: plan.UnitErrorBudget,

			PlannedChainLength: plan.PlannedChainLength,
			PlannedScaleBits:   plan.PlannedScaleBits,
			PlannedLogN:        plan.PlannedLogN,
			EstimatedLogQP:     plan.EstimatedLogQP,
			CandidateCount:     len(plan.Configurations),
			MatchCount:         len(matches),
			UniqueProfileCount: len(uniqueMatches),

			Reason: plan.Reason,
		})

		for rank, cfg := range plan.Configurations {
			cost, reason := estimatePlannerDemoCost(graphSummary, cfg)

			candidateRows = append(candidateRows, plannerDemoCandidateRow{
				Workload: workload.Name,
				Rank:     rank + 1,

				CandidateID: cfg.Candidate.ID,
				Path:        cfg.Path,

				LogN:        cfg.Candidate.LogN,
				Slots:       cfg.Candidate.Slots,
				ChainLength: cfg.Candidate.ChainLength,
				ScaleBits:   cfg.Candidate.ScaleBits,
				Family:      cfg.Candidate.Family,
				IsReference: cfg.Candidate.IsReference,

				PredictedRelativeCost: cost,
				CostReason:            reason,
			})
		}

		for _, match := range matches {
			matchRows = append(matchRows, plannerDemoProfileMatchRow{
				Workload: workload.Name,
				Rank:     match.Rank,

				PlannedCandidateID: match.Planned.Candidate.ID,
				PlannedPath:        match.Planned.Path,
				PlannedFamily:      match.Planned.Candidate.Family,
				PlannedChainLength: match.Planned.Candidate.ChainLength,
				PlannedScaleBits:   match.Planned.Candidate.ScaleBits,
				PlannedLogN:        match.Planned.Candidate.LogN,

				ProfileName:        match.Profile.Name,
				ProfileDescription: match.Profile.Description,
				ProfileFamily:      match.Profile.Family,
				ProfileChainLength: match.Profile.ChainLength,
				ProfileScaleBits:   match.Profile.ScaleBits,
				ProfileLogN:        match.Profile.LogN,
				ProfileSlots:       match.Profile.Slots,

				Distance:         match.Distance,
				ChainGap:         match.ChainGap,
				ScaleGap:         match.ScaleGap,
				LogNGap:          match.LogNGap,
				UnderProvisioned: match.UnderProvisioned,

				Reason: match.Reason,
			})
		}
	}

	outputDir := CKKSResultDir(tunerPlannerDemoOutputDir)

	workloadsPath := filepath.Join(outputDir, "workloads.csv")
	if err := writePlannerDemoWorkloadsCSV(workloadsPath, workloadRows); err != nil {
		return fmt.Errorf("write planner demo workloads CSV: %w", err)
	}

	candidatesPath := filepath.Join(outputDir, "candidates.csv")
	if err := writePlannerDemoCandidatesCSV(candidatesPath, candidateRows); err != nil {
		return fmt.Errorf("write planner demo candidates CSV: %w", err)
	}

	matchesPath := filepath.Join(outputDir, "profile_matches.csv")
	if err := writePlannerDemoProfileMatchesCSV(matchesPath, matchRows); err != nil {
		return fmt.Errorf("write planner demo profile matches CSV: %w", err)
	}

	planPath := filepath.Join(outputDir, "plan.md")
	if err := writePlannerDemoMarkdown(planPath, workloadRows, candidateRows, matchRows); err != nil {
		return fmt.Errorf("write planner demo markdown: %w", err)
	}

	fmt.Println("FlipGuard tuner planner demo")
	fmt.Printf(
		"workloads=%d available_profiles=%d output_error_budget=%.10f safety_factor=%.4f include_reference=%t include_aggressive=%t max_candidates=%d resolver_matches_per_candidate=%d\n",
		len(workloads),
		len(availableProfiles),
		outputErrorBudget,
		safetyFactor,
		policy.IncludeReference,
		policy.IncludeAggressive,
		policy.MaxCandidates,
		resolverPolicy.MaxMatchesPerCandidate,
	)
	fmt.Println()

	for _, row := range workloadRows {
		fmt.Printf(
			"workload=%s depth=%d mul_ops=%d add_ops=%d samples=%d protected_margin=%.10f budget=%.10f sensitivity=%.6f unit_budget=%.10f planned_chain=%d planned_scale=%d planned_logN=%d candidates=%d matches=%d unique_profiles=%d\n",
			row.Workload,
			row.MultiplicativeDepth,
			row.MulOps,
			row.AddOps,
			row.SampleCount,
			row.ProtectedMargin,
			row.Budget,
			row.Sensitivity,
			row.UnitErrorBudget,
			row.PlannedChainLength,
			row.PlannedScaleBits,
			row.PlannedLogN,
			row.CandidateCount,
			row.MatchCount,
			row.UniqueProfileCount,
		)
	}

	fmt.Println()
	fmt.Printf("Wrote %s\n", workloadsPath)
	fmt.Printf("Wrote %s\n", candidatesPath)
	fmt.Printf("Wrote %s\n", matchesPath)
	fmt.Printf("Wrote %s\n", planPath)

	return nil
}

func buildPlannerDemoWorkloads() ([]plannerDemoWorkload, error) {
	linearGraph := benchmarks.NewLinearRegressionGraph()

	linearOptions := benchmarks.DefaultLinearRegressionSampleGenOptions()
	linearOptions.MaxBoundary = 32
	linearOptions.MaxNonBoundary = 32

	linearSamples := benchmarks.GenerateLinearRegressionSamples(linearOptions)
	linearDemoSamples := make([]plannerDemoSample, 0, len(linearSamples))

	for _, sample := range linearSamples {
		eval, err := runtime.EvalPlain(linearGraph, sample.Inputs())
		if err != nil {
			return nil, fmt.Errorf("evaluate linear_regression sample: %w", err)
		}

		margin := math.Abs(eval.Output - benchmarks.LinearRegressionThreshold)

		linearDemoSamples = append(linearDemoSamples, plannerDemoSample{
			Inputs:      sample.Inputs(),
			PlainOutput: eval.Output,
			Margin:      margin,
		})
	}

	logregGraph := benchmarks.NewLogRegSmallGraph()

	logregOptions := benchmarks.DefaultBoundaryFocusedOptions()
	logregOptions.MaxBoundary = 32
	logregOptions.MaxNonBoundary = 32

	logregSamples := benchmarks.GenerateLogRegSmallSamples(logregOptions)
	logregDemoSamples := make([]plannerDemoSample, 0, len(logregSamples))

	for _, sample := range logregSamples {
		eval, err := runtime.EvalPlain(logregGraph, sample.Inputs())
		if err != nil {
			return nil, fmt.Errorf("evaluate logreg_small sample: %w", err)
		}

		margin := math.Abs(eval.Output - benchmarks.LogRegSmallThreshold)

		logregDemoSamples = append(logregDemoSamples, plannerDemoSample{
			Inputs:      sample.Inputs(),
			PlainOutput: eval.Output,
			Margin:      margin,
		})
	}

	polyGraph := benchmarks.NewPolynomialRegressionGraph()

	polyXs := []float64{
		-2.0,
		-1.0,
		-0.50,
		-0.25,
		-0.186,
		-0.180,
		-0.170,
		-0.162,
		-0.160,
		-0.150,
		-0.100,
		0.0,
		0.25,
		0.50,
		1.0,
		2.0,
	}

	polyDemoSamples := make([]plannerDemoSample, 0, len(polyXs))
	for _, x := range polyXs {
		sample := benchmarks.PolynomialRegressionSample{X: x}

		eval, err := runtime.EvalPlain(polyGraph, sample.Inputs())
		if err != nil {
			return nil, fmt.Errorf("evaluate polynomial_regression sample: %w", err)
		}

		margin := math.Abs(eval.Output - benchmarks.PolynomialRegressionThreshold)

		polyDemoSamples = append(polyDemoSamples, plannerDemoSample{
			Inputs:      sample.Inputs(),
			PlainOutput: eval.Output,
			Margin:      margin,
		})
	}

	return []plannerDemoWorkload{
		{
			Name:      "linear_regression",
			Label:     "Linear Regression",
			Graph:     linearGraph,
			Samples:   linearDemoSamples,
			Threshold: benchmarks.LinearRegressionThreshold,
		},
		{
			Name:      "logreg_small",
			Label:     "LogReg Small",
			Graph:     logregGraph,
			Samples:   logregDemoSamples,
			Threshold: benchmarks.LogRegSmallThreshold,
		},
		{
			Name:      "polynomial_regression",
			Label:     "Polynomial Regression",
			Graph:     polyGraph,
			Samples:   polyDemoSamples,
			Threshold: benchmarks.PolynomialRegressionThreshold,
		},
	}, nil
}

func plannerAvailableProfiles(profiles []ckksbackend.CKKSProfile) []tuner.AvailableProfile {
	available := make([]tuner.AvailableProfile, 0, len(profiles))

	for _, profile := range profiles {
		logN := profile.Literal.LogN
		if logN <= 0 {
			logN = 14
		}

		available = append(available, tuner.AvailableProfile{
			Name:        profile.Name,
			Description: profile.Description,

			LogN:        logN,
			Slots:       slotsFromProfileLogN(logN),
			ChainLength: profile.LogQCount(),
			ScaleBits:   profile.LogDefaultScale(),
			Family:      inferProfileCandidateFamily(profile.Name),
		})
	}

	return available
}

func summarizeGraphForPlanner(g *ir.Graph) (tuner.GraphSummary, error) {
	if g == nil {
		return tuner.GraphSummary{}, fmt.Errorf("graph is nil")
	}
	if err := g.Validate(); err != nil {
		return tuner.GraphSummary{}, err
	}

	depths := make(map[ir.NodeID]int)

	summary := tuner.GraphSummary{}

	for _, node := range g.Nodes() {
		depth := 0

		switch node.Op {
		case ir.OpInput, ir.OpConst:
			depth = 0

		case ir.OpAdd, ir.OpSub:
			summary.AddOps++
			inputDepth, err := maxInputPlannerDepth(depths, node)
			if err != nil {
				return tuner.GraphSummary{}, err
			}
			depth = inputDepth

		case ir.OpMulConst:
			summary.MulOps++
			inputDepth, err := maxInputPlannerDepth(depths, node)
			if err != nil {
				return tuner.GraphSummary{}, err
			}
			depth = inputDepth

		case ir.OpMul:
			summary.MulOps++
			inputDepth, err := maxInputPlannerDepth(depths, node)
			if err != nil {
				return tuner.GraphSummary{}, err
			}
			depth = inputDepth + 1

		case ir.OpPow2:
			summary.MulOps++
			inputDepth, err := maxInputPlannerDepth(depths, node)
			if err != nil {
				return tuner.GraphSummary{}, err
			}
			depth = inputDepth + 1

		case ir.OpPow3:
			summary.MulOps += 2
			inputDepth, err := maxInputPlannerDepth(depths, node)
			if err != nil {
				return tuner.GraphSummary{}, err
			}
			depth = inputDepth + 2

		case ir.OpPoly:
			if len(node.Coeffs) > 1 {
				summary.MulOps += len(node.Coeffs) - 1
			}
			inputDepth, err := maxInputPlannerDepth(depths, node)
			if err != nil {
				return tuner.GraphSummary{}, err
			}
			depth = inputDepth + maxPlannerDemoInt(0, len(node.Coeffs)-1)

		default:
			return tuner.GraphSummary{}, fmt.Errorf("unsupported op %s for planner summary", node.Op)
		}

		depths[node.ID] = depth

		if depth > summary.MultiplicativeDepth {
			summary.MultiplicativeDepth = depth
		}
	}

	summary.RescaleOps = summary.MultiplicativeDepth
	summary.Notes = []string{
		fmt.Sprintf("planner graph summary for %d nodes", len(g.Nodes())),
	}

	return summary, nil
}

func maxInputPlannerDepth(depths map[ir.NodeID]int, node *ir.Node) (int, error) {
	maxDepth := 0

	for _, inputID := range node.Inputs {
		depth, ok := depths[inputID]
		if !ok {
			return 0, fmt.Errorf("node %s input %s has no depth", node.ID, inputID)
		}

		if depth > maxDepth {
			maxDepth = depth
		}
	}

	return maxDepth, nil
}

func summarizePlannerMargins(samples []plannerDemoSample) (minMargin float64, p10Margin float64, protectedMargin float64) {
	if len(samples) == 0 {
		return 0, 0, 0
	}

	margins := make([]float64, 0, len(samples))
	for _, sample := range samples {
		margin := math.Abs(sample.Margin)
		margins = append(margins, margin)
	}

	sort.Float64s(margins)

	minMargin = margins[0]
	p10Margin = percentileSortedPlannerMargin(margins, 0.10)

	protectedMargin = 0
	for _, margin := range margins {
		if margin > 1e-9 {
			protectedMargin = margin
			break
		}
	}

	if protectedMargin <= 0 {
		protectedMargin = p10Margin
	}

	return minMargin, p10Margin, protectedMargin
}

func percentileSortedPlannerMargin(sorted []float64, p float64) float64 {
	if len(sorted) == 0 {
		return 0
	}

	if p <= 0 {
		return sorted[0]
	}
	if p >= 1 {
		return sorted[len(sorted)-1]
	}

	index := int(math.Ceil(p*float64(len(sorted)))) - 1
	if index < 0 {
		index = 0
	}
	if index >= len(sorted) {
		index = len(sorted) - 1
	}

	return sorted[index]
}

func estimatePlannerDemoCost(
	graph tuner.GraphSummary,
	cfg tuner.ExecutionConfiguration,
) (float64, string) {
	logN := cfg.Candidate.LogN
	if logN <= 0 {
		logN = 14
	}

	n := math.Pow(2, float64(logN))
	chain := float64(cfg.Candidate.ChainLength)
	if chain <= 0 {
		chain = 1
	}

	mulOps := float64(maxPlannerDemoInt(graph.MulOps, 1))
	addOps := float64(maxPlannerDemoInt(graph.AddOps, 1))
	rescaleOps := float64(maxPlannerDemoInt(graph.RescaleOps, 1))

	nttCost := n * float64(logN)
	mulCost := mulOps * chain * nttCost
	addCost := addOps * n
	rescaleCost := rescaleOps * chain * n

	pathFactor := 1.0
	if cfg.Path == tuner.PathNonRescale {
		pathFactor = 0.92
	}

	scaleFactor := 1.0 + math.Max(0, float64(cfg.Candidate.ScaleBits-40))*0.015

	cost := (mulCost + addCost + rescaleCost) * pathFactor * scaleFactor

	reason := fmt.Sprintf(
		"n=2^%d chain=%d scale=%d mul_ops=%d add_ops=%d rescale_ops=%d path_factor=%.2f scale_factor=%.3f",
		logN,
		cfg.Candidate.ChainLength,
		cfg.Candidate.ScaleBits,
		graph.MulOps,
		graph.AddOps,
		graph.RescaleOps,
		pathFactor,
		scaleFactor,
	)

	return cost, reason
}

func writePlannerDemoWorkloadsCSV(path string, rows []plannerDemoWorkloadRow) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create planner demo workloads csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"workload",
		"label",
		"node_count",
		"sample_count",
		"threshold",
		"min_margin",
		"p10_margin",
		"protected_margin",
		"multiplicative_depth",
		"add_ops",
		"mul_ops",
		"rot_ops",
		"rescale_ops",
		"budget",
		"sensitivity",
		"unit_error_budget",
		"planned_chain_length",
		"planned_scale_bits",
		"planned_logN",
		"estimated_logQP",
		"candidate_count",
		"match_count",
		"unique_profile_count",
		"reason",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write planner demo workloads header: %w", err)
	}

	for i, row := range rows {
		record := []string{
			row.Workload,
			row.Label,
			fmt.Sprintf("%d", row.NodeCount),
			fmt.Sprintf("%d", row.SampleCount),
			fmt.Sprintf("%.12g", row.Threshold),
			fmt.Sprintf("%.12g", row.MinMargin),
			fmt.Sprintf("%.12g", row.P10Margin),
			fmt.Sprintf("%.12g", row.ProtectedMargin),
			fmt.Sprintf("%d", row.MultiplicativeDepth),
			fmt.Sprintf("%d", row.AddOps),
			fmt.Sprintf("%d", row.MulOps),
			fmt.Sprintf("%d", row.RotOps),
			fmt.Sprintf("%d", row.RescaleOps),
			fmt.Sprintf("%.12g", row.Budget),
			fmt.Sprintf("%.12g", row.Sensitivity),
			fmt.Sprintf("%.12g", row.UnitErrorBudget),
			fmt.Sprintf("%d", row.PlannedChainLength),
			fmt.Sprintf("%d", row.PlannedScaleBits),
			fmt.Sprintf("%d", row.PlannedLogN),
			fmt.Sprintf("%d", row.EstimatedLogQP),
			fmt.Sprintf("%d", row.CandidateCount),
			fmt.Sprintf("%d", row.MatchCount),
			fmt.Sprintf("%d", row.UniqueProfileCount),
			row.Reason,
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write planner demo workloads row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush planner demo workloads csv: %w", err)
	}

	return nil
}

func writePlannerDemoCandidatesCSV(path string, rows []plannerDemoCandidateRow) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create planner demo candidates csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"workload",
		"rank",
		"candidate_id",
		"path",
		"logN",
		"slots",
		"chain_length",
		"scale_bits",
		"family",
		"is_reference",
		"predicted_relative_cost",
		"cost_reason",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write planner demo candidates header: %w", err)
	}

	for i, row := range rows {
		record := []string{
			row.Workload,
			fmt.Sprintf("%d", row.Rank),
			row.CandidateID,
			string(row.Path),
			fmt.Sprintf("%d", row.LogN),
			fmt.Sprintf("%d", row.Slots),
			fmt.Sprintf("%d", row.ChainLength),
			fmt.Sprintf("%d", row.ScaleBits),
			row.Family,
			fmt.Sprintf("%t", row.IsReference),
			fmt.Sprintf("%.12g", row.PredictedRelativeCost),
			row.CostReason,
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write planner demo candidates row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush planner demo candidates csv: %w", err)
	}

	return nil
}

func writePlannerDemoProfileMatchesCSV(path string, rows []plannerDemoProfileMatchRow) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create planner demo profile matches csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"workload",
		"rank",
		"planned_candidate_id",
		"planned_path",
		"planned_family",
		"planned_chain_length",
		"planned_scale_bits",
		"planned_logN",
		"profile_name",
		"profile_description",
		"profile_family",
		"profile_chain_length",
		"profile_scale_bits",
		"profile_logN",
		"profile_slots",
		"distance",
		"chain_gap",
		"scale_gap",
		"logN_gap",
		"under_provisioned",
		"reason",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write planner demo profile matches header: %w", err)
	}

	for i, row := range rows {
		record := []string{
			row.Workload,
			fmt.Sprintf("%d", row.Rank),
			row.PlannedCandidateID,
			string(row.PlannedPath),
			row.PlannedFamily,
			fmt.Sprintf("%d", row.PlannedChainLength),
			fmt.Sprintf("%d", row.PlannedScaleBits),
			fmt.Sprintf("%d", row.PlannedLogN),
			row.ProfileName,
			row.ProfileDescription,
			row.ProfileFamily,
			fmt.Sprintf("%d", row.ProfileChainLength),
			fmt.Sprintf("%d", row.ProfileScaleBits),
			fmt.Sprintf("%d", row.ProfileLogN),
			fmt.Sprintf("%d", row.ProfileSlots),
			fmt.Sprintf("%.12g", row.Distance),
			fmt.Sprintf("%d", row.ChainGap),
			fmt.Sprintf("%d", row.ScaleGap),
			fmt.Sprintf("%d", row.LogNGap),
			fmt.Sprintf("%t", row.UnderProvisioned),
			row.Reason,
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write planner demo profile matches row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush planner demo profile matches csv: %w", err)
	}

	return nil
}

func writePlannerDemoMarkdown(
	path string,
	workloads []plannerDemoWorkloadRow,
	candidates []plannerDemoCandidateRow,
	matches []plannerDemoProfileMatchRow,
) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create planner demo markdown: %w", err)
	}
	defer f.Close()

	fmt.Fprintf(f, "# FlipGuard Analysis-Driven Candidate Planner\n\n")

	fmt.Fprintf(f, "## Workload Plans\n\n")
	fmt.Fprintf(f, "| Workload | Nodes | Samples | Depth | Mul Ops | Add Ops | Protected Margin | Budget | Sensitivity | Unit Budget | Planned Chain | Planned Scale | Planned LogN | Candidates | Profile Matches | Unique Profiles |\n")
	fmt.Fprintf(f, "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")

	for _, row := range workloads {
		fmt.Fprintf(
			f,
			"| %s | %d | %d | %d | %d | %d | %.10f | %.10f | %.6f | %.10f | %d | %d | %d | %d | %d | %d |\n",
			row.Label,
			row.NodeCount,
			row.SampleCount,
			row.MultiplicativeDepth,
			row.MulOps,
			row.AddOps,
			row.ProtectedMargin,
			row.Budget,
			row.Sensitivity,
			row.UnitErrorBudget,
			row.PlannedChainLength,
			row.PlannedScaleBits,
			row.PlannedLogN,
			row.CandidateCount,
			row.MatchCount,
			row.UniqueProfileCount,
		)
	}

	fmt.Fprintf(f, "\n## Planned Candidates\n\n")

	for _, workload := range workloads {
		fmt.Fprintf(f, "### %s\n\n", workload.Label)
		fmt.Fprintf(f, "`%s`\n\n", workload.Reason)
		fmt.Fprintf(f, "| Rank | Candidate | Path | Family | Reference | Chain | Scale | LogN | Predicted Cost |\n")
		fmt.Fprintf(f, "|---:|---|---|---|---|---:|---:|---:|---:|\n")

		for _, candidate := range candidates {
			if candidate.Workload != workload.Workload {
				continue
			}

			fmt.Fprintf(
				f,
				"| %d | `%s` | `%s` | %s | %t | %d | %d | %d | %.3f |\n",
				candidate.Rank,
				candidate.CandidateID,
				candidate.Path,
				candidate.Family,
				candidate.IsReference,
				candidate.ChainLength,
				candidate.ScaleBits,
				candidate.LogN,
				candidate.PredictedRelativeCost,
			)
		}

		fmt.Fprintf(f, "\n")
	}

	fmt.Fprintf(f, "## Closest Executable Profile Matches\n\n")

	for _, workload := range workloads {
		fmt.Fprintf(f, "### %s\n\n", workload.Label)
		fmt.Fprintf(f, "| Planned Candidate | Rank | Matched Profile | Distance | Chain Gap | Scale Gap | LogN Gap | Under-provisioned |\n")
		fmt.Fprintf(f, "|---|---:|---|---:|---:|---:|---:|---|\n")

		for _, match := range matches {
			if match.Workload != workload.Workload {
				continue
			}

			fmt.Fprintf(
				f,
				"| `%s` | %d | `%s` | %.3f | %+d | %+d | %+d | %t |\n",
				match.PlannedCandidateID,
				match.Rank,
				match.ProfileName,
				match.Distance,
				match.ChainGap,
				match.ScaleGap,
				match.LogNGap,
				match.UnderProvisioned,
			)
		}

		fmt.Fprintf(f, "\n")
	}

	fmt.Fprintf(f, "## Interpretation\n\n")
	fmt.Fprintf(
		f,
		"The planner derives ideal candidate configurations from graph depth, operation counts, and decision-margin-derived error budgets. ",
	)
	fmt.Fprintf(
		f,
		"The resolver then maps those ideal candidates to the closest executable CKKS profiles exposed by the backend. ",
	)
	fmt.Fprintf(
		f,
		"This artifact is intended to distinguish FlipGuard's planner from a brute-force parameter sweep: the planner first computes a minimum feasible region, resolves it to a small executable profile set, and only then passes candidates to CKKS validation.\n",
	)

	return nil
}

func maxPlannerDemoInt(a int, b int) int {
	if a > b {
		return a
	}
	return b
}

func sanitizePlannerDemoString(s string) string {
	s = strings.TrimSpace(s)
	s = strings.ReplaceAll(s, "\n", " ")
	s = strings.ReplaceAll(s, "\r", " ")
	return s
}
