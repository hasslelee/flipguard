package main

import (
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/tuner"
)

const schemaVersion = 1

type studyKey struct {
	Seed      int
	DatasetID string
	ModelID   string
	Alpha     float64
}

type splitKey struct {
	Seed      int
	DatasetID string
	ModelID   string
}

type candidateRecord struct {
	Key               studyKey
	CandidateID       string
	Profile           string
	Path              string
	EvaluationMode    string
	CertificateStatus string
	MeanTotalMS       float64
	HasLatency        bool
	MarginFloor       float64
	VCert             int
	VAmb              int
}

type coverageRecord struct {
	ValidationCSV string
	ModelArtifact string
	VCert         int
	VAmb          int
	MarginFloor   float64
}

type modelArtifact struct {
	DatasetID string `json:"dataset_id"`
	ModelID   string `json:"model_id"`
	ModelType string `json:"model_type"`
	InputDim  int    `json:"input_dim"`

	ScaledModelForCKKS struct {
		HiddenWeights [][]float64 `json:"hidden_weights"`
		HiddenBias    []float64   `json:"hidden_bias"`
		OutputWeights []float64   `json:"output_weights"`
	} `json:"scaled_model_for_ckks"`

	PolynomialScore struct {
		Formula           string  `json:"formula"`
		DecisionThreshold float64 `json:"decision_threshold"`
	} `json:"polynomial_score"`
}

type projectedCandidate struct {
	CandidateID      string
	Profile          string
	Path             string
	EvaluationMode   string
	PlannedCandidate string
	PlannedPath      string
	PlannedFamily    string
	ProfileRank      int
	Distance         float64
	UnderProvisioned bool
	ProfileChain     int
	ProfileScale     int
	ProfileLogN      int
	ResolutionReason string
}

type groupPlan struct {
	Key             studyKey
	Graph           tuner.GraphSummary
	ProtectedMargin float64
	Plan            tuner.CandidatePlan
	Candidates      []projectedCandidate
	OverheadUS      float64
}

type comparisonResult struct {
	OracleOutcome         string
	PlannerOutcome        string
	OracleCandidate       string
	PlannerCandidate      string
	OracleLatencyMS       float64
	PlannerLatencyMS      float64
	HasOracleLatency      bool
	HasPlannerLatency     bool
	OracleCandidateCount  int
	PlannerCandidateCount int
	OracleSafeCount       int
	PlannerSafeCount      int
	OracleRejectedCount   int
	PlannerRejectedCount  int
	OracleFailedCount     int
	PlannerFailedCount    int
	SafeRecallDefined     bool
	SafeRecall            float64
	OptimumRecallDefined  bool
	OptimumRecall         float64
	LatencyRegretDefined  bool
	LatencyRegret         float64
	PruningRatio          float64
	FalseNoSafe           bool
}

type runConfig struct {
	CandidateCertificates string
	ValidationCoverage    string
	OutputRoot            string
	SelectionMetric       string
}

func main() {
	config := runConfig{}

	flag.StringVar(
		&config.CandidateCertificates,
		"candidate-certificates",
		"",
		"path to candidate_certificates.csv",
	)
	flag.StringVar(
		&config.ValidationCoverage,
		"validation-coverage",
		"",
		"path to validation_coverage.csv",
	)
	flag.StringVar(
		&config.OutputRoot,
		"output-root",
		"",
		"directory for planner/oracle comparison artifacts",
	)
	flag.StringVar(
		&config.SelectionMetric,
		"selection-metric",
		"mean_total_ms",
		"frozen latency selection metric",
	)
	flag.Parse()

	if err := run(config); err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: %v\n", err)
		os.Exit(1)
	}
}

func run(config runConfig) error {
	if strings.TrimSpace(config.CandidateCertificates) == "" {
		return errors.New("candidate-certificates is required")
	}
	if strings.TrimSpace(config.ValidationCoverage) == "" {
		return errors.New("validation-coverage is required")
	}
	if strings.TrimSpace(config.OutputRoot) == "" {
		return errors.New("output-root is required")
	}
	if config.SelectionMetric != "mean_total_ms" {
		return fmt.Errorf(
			"unsupported selection metric %q; Step 7B.2 freezes mean_total_ms",
			config.SelectionMetric,
		)
	}

	candidates, err := loadCandidateRecords(config.CandidateCertificates)
	if err != nil {
		return err
	}

	coverage, err := loadCoverageRecords(config.ValidationCoverage)
	if err != nil {
		return err
	}

	groups := groupCandidateRecords(candidates)
	keys := sortedStudyKeys(groups)

	if len(keys) == 0 {
		return errors.New("candidate certificate input has no rows")
	}

	plans := make([]groupPlan, 0, len(keys))
	comparisons := make(map[studyKey]comparisonResult, len(keys))

	for _, key := range keys {
		split := splitKey{
			Seed:      key.Seed,
			DatasetID: key.DatasetID,
			ModelID:   key.ModelID,
		}

		coverageRow, ok := coverage[split]
		if !ok {
			return fmt.Errorf("missing validation coverage for %+v", split)
		}

		plan, err := buildGroupPlan(key, groups[key], coverageRow)
		if err != nil {
			return fmt.Errorf(
				"plan seed=%d dataset=%s model=%s alpha=%s: %w",
				key.Seed,
				key.DatasetID,
				key.ModelID,
				formatFloat(key.Alpha),
				err,
			)
		}

		comparison, err := compareProjection(groups[key], plan.Candidates)
		if err != nil {
			return fmt.Errorf(
				"compare seed=%d dataset=%s model=%s alpha=%s: %w",
				key.Seed,
				key.DatasetID,
				key.ModelID,
				formatFloat(key.Alpha),
				err,
			)
		}

		plans = append(plans, plan)
		comparisons[key] = comparison
	}

	if err := os.MkdirAll(config.OutputRoot, 0o755); err != nil {
		return fmt.Errorf("create output root: %w", err)
	}

	plannerCandidatesPath := filepath.Join(
		config.OutputRoot,
		"planner_candidates.csv",
	)
	if err := writePlannerCandidates(plannerCandidatesPath, plans); err != nil {
		return err
	}

	plannerSummaryPath := filepath.Join(
		config.OutputRoot,
		"planner_summary.csv",
	)
	if err := writePlannerSummary(plannerSummaryPath, plans); err != nil {
		return err
	}

	comparisonPath := filepath.Join(
		config.OutputRoot,
		"comparison.csv",
	)
	if err := writeComparisons(comparisonPath, plans, comparisons); err != nil {
		return err
	}

	summaryPath := filepath.Join(config.OutputRoot, "summary.json")
	if err := writeSummary(
		summaryPath,
		config,
		plans,
		comparisons,
		plannerCandidatesPath,
		plannerSummaryPath,
		comparisonPath,
	); err != nil {
		return err
	}

	fmt.Printf("planner_groups=%d\n", len(plans))
	fmt.Printf("planner_candidate_rows=%d\n", countProjectedCandidates(plans))
	fmt.Printf("comparison_rows=%d\n", len(comparisons))
	fmt.Printf("selection_metric=%s\n", config.SelectionMetric)
	fmt.Printf("output_root=%s\n", config.OutputRoot)

	return nil
}

func buildGroupPlan(
	key studyKey,
	records []candidateRecord,
	coverage coverageRecord,
) (groupPlan, error) {
	if len(records) == 0 {
		return groupPlan{}, errors.New("candidate group is empty")
	}

	model, graph, err := loadModelGraph(coverage.ModelArtifact)
	if err != nil {
		return groupPlan{}, err
	}
	if model.DatasetID != key.DatasetID || model.ModelID != key.ModelID {
		return groupPlan{}, fmt.Errorf(
			"model identity mismatch: got %s/%s",
			model.DatasetID,
			model.ModelID,
		)
	}

	protectedMargin, vCert, vAmb, err := loadProtectedMargin(
		coverage.ValidationCSV,
		model.PolynomialScore.DecisionThreshold,
		coverage.MarginFloor,
	)
	if err != nil {
		return groupPlan{}, err
	}
	if vCert != coverage.VCert || vAmb != coverage.VAmb {
		return groupPlan{}, fmt.Errorf(
			"coverage mismatch: computed v_cert/v_amb=%d/%d expected=%d/%d",
			vCert,
			vAmb,
			coverage.VCert,
			coverage.VAmb,
		)
	}
	if protectedMargin <= 0 {
		return groupPlan{}, errors.New(
			"V_cert is empty; planner budget is undefined for this split",
		)
	}

	profiles, err := availableProfilesForRecords(records)
	if err != nil {
		return groupPlan{}, err
	}

	policy := tuner.DefaultPlannerPolicy()
	policy.IncludeReference = true
	policy.IncludeAggressive = false
	policy.MaxCandidates = 8
	policy.Paths = []tuner.ExecutionPath{
		tuner.PathNonRescale,
		tuner.PathRescale,
	}

	resolverPolicy := tuner.DefaultProfileResolverPolicy()
	resolverPolicy.MaxMatchesPerCandidate = 2

	started := time.Now()

	plan, err := tuner.PlanCandidates(
		graph,
		tuner.DecisionBudgetSummary{
			ProtectedMargin: protectedMargin,
			SafetyFactor:    key.Alpha,
		},
		policy,
	)
	if err != nil {
		return groupPlan{}, err
	}

	matches, err := tuner.ResolveClosestProfiles(
		plan.Configurations,
		profiles,
		resolverPolicy,
	)
	if err != nil {
		return groupPlan{}, err
	}

	projected, err := projectResolvedMatches(matches, records)
	if err != nil {
		return groupPlan{}, err
	}

	overheadUS := float64(time.Since(started).Nanoseconds()) / 1000.0

	return groupPlan{
		Key:             key,
		Graph:           graph,
		ProtectedMargin: protectedMargin,
		Plan:            plan,
		Candidates:      projected,
		OverheadUS:      overheadUS,
	}, nil
}

func loadModelGraph(path string) (modelArtifact, tuner.GraphSummary, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return modelArtifact{}, tuner.GraphSummary{}, fmt.Errorf(
			"read model artifact %s: %w",
			path,
			err,
		)
	}

	model := modelArtifact{}
	if err := json.Unmarshal(data, &model); err != nil {
		return modelArtifact{}, tuner.GraphSummary{}, fmt.Errorf(
			"parse model artifact %s: %w",
			path,
			err,
		)
	}

	if model.InputDim <= 0 {
		return modelArtifact{}, tuner.GraphSummary{}, fmt.Errorf(
			"%s: invalid input_dim %d",
			path,
			model.InputDim,
		)
	}
	if math.IsNaN(model.PolynomialScore.DecisionThreshold) ||
		math.IsInf(model.PolynomialScore.DecisionThreshold, 0) {
		return modelArtifact{}, tuner.GraphSummary{}, fmt.Errorf(
			"%s: non-finite decision threshold",
			path,
		)
	}

	graph := tuner.GraphSummary{}

	switch model.ModelType {
	case "linear_poly3":
		if model.PolynomialScore.Formula !=
			"0.5 + 0.197*z - 0.004*z^3" {
			return modelArtifact{}, tuner.GraphSummary{}, fmt.Errorf(
				"%s: linear_poly3 has unexpected formula %q",
				path,
				model.PolynomialScore.Formula,
			)
		}

		graph = tuner.GraphSummary{
			MultiplicativeDepth: 2,
			AddOps:              model.InputDim + 2,
			MulOps:              model.InputDim + 4,
			RotOps:              0,
			RescaleOps:          2,
			Notes: []string{
				"runtime-derived linear weighted sum plus cubic output score",
			},
		}

	case "mlp_square_linear_score":
		if model.PolynomialScore.Formula != "0.5 + 0.197*z" {
			return modelArtifact{}, tuner.GraphSummary{}, fmt.Errorf(
				"%s: mlp_square_linear_score has unexpected formula %q",
				path,
				model.PolynomialScore.Formula,
			)
		}

		hiddenUnits := len(
			model.ScaledModelForCKKS.HiddenWeights,
		)
		if hiddenUnits == 0 {
			return modelArtifact{}, tuner.GraphSummary{}, fmt.Errorf(
				"%s: MLP has no hidden units",
				path,
			)
		}
		if len(model.ScaledModelForCKKS.HiddenBias) != hiddenUnits ||
			len(model.ScaledModelForCKKS.OutputWeights) != hiddenUnits {
			return modelArtifact{}, tuner.GraphSummary{}, fmt.Errorf(
				"%s: inconsistent MLP hidden/output dimensions",
				path,
			)
		}
		for i, weights := range model.ScaledModelForCKKS.HiddenWeights {
			if len(weights) != model.InputDim {
				return modelArtifact{}, tuner.GraphSummary{}, fmt.Errorf(
					"%s: hidden unit %d has %d weights, expected %d",
					path,
					i,
					len(weights),
					model.InputDim,
				)
			}
		}

		graph = tuner.GraphSummary{
			MultiplicativeDepth: 1,
			AddOps: hiddenUnits*model.InputDim +
				hiddenUnits + 1,
			MulOps: hiddenUnits*model.InputDim +
				2*hiddenUnits + 1,
			RotOps:     0,
			RescaleOps: 1,
			Notes: []string{
				"runtime-derived square-activation MLP plus affine output score",
			},
		}

	default:
		return modelArtifact{}, tuner.GraphSummary{}, fmt.Errorf(
			"%s: unsupported primary model_type %q",
			path,
			model.ModelType,
		)
	}

	return model, graph, nil
}

func loadProtectedMargin(
	path string,
	threshold float64,
	marginFloor float64,
) (float64, int, int, error) {
	rows, err := readCSV(path)
	if err != nil {
		return 0, 0, 0, err
	}

	protectedMargin := math.Inf(1)
	vCert := 0
	vAmb := 0

	for rowIndex, row := range rows {
		score, err := requiredFloat(
			row,
			"polynomial_score",
			fmt.Sprintf("%s row %d", path, rowIndex+2),
		)
		if err != nil {
			return 0, 0, 0, err
		}

		margin := math.Abs(score - threshold)
		if margin <= marginFloor {
			vAmb++
			continue
		}

		vCert++
		if margin < protectedMargin {
			protectedMargin = margin
		}
	}

	if math.IsInf(protectedMargin, 1) {
		protectedMargin = 0
	}

	return protectedMargin, vCert, vAmb, nil
}

func availableProfilesForRecords(
	records []candidateRecord,
) ([]tuner.AvailableProfile, error) {
	wanted := make(map[string]bool)
	for _, record := range records {
		wanted[record.Profile] = true
	}

	available := make([]tuner.AvailableProfile, 0, len(wanted))
	found := make(map[string]bool)

	for _, profile := range ckksbackend.AllCKKSProfiles() {
		if !wanted[profile.Name] {
			continue
		}

		logN := profile.Literal.LogN
		if logN <= 0 {
			logN = 14
		}

		available = append(available, tuner.AvailableProfile{
			Name:        profile.Name,
			Description: profile.Description,
			LogN:        logN,
			Slots:       1 << (logN - 1),
			ChainLength: profile.LogQCount(),
			ScaleBits:   profile.LogDefaultScale(),
			Family:      profileFamily(profile.Name),
		})
		found[profile.Name] = true
	}

	for name := range wanted {
		if !found[name] {
			return nil, fmt.Errorf(
				"oracle candidate references unknown CKKS profile %q",
				name,
			)
		}
	}

	sort.Slice(available, func(i, j int) bool {
		return available[i].Name < available[j].Name
	})

	return available, nil
}

func profileFamily(name string) string {
	switch {
	case name == "default":
		return "reference"
	case strings.HasPrefix(name, "scale"):
		return "scale"
	case strings.HasPrefix(name, "deep_chain"):
		return "deep_chain"
	case strings.HasPrefix(name, "short_chain"):
		return "short_chain"
	default:
		return "built_in"
	}
}

func projectResolvedMatches(
	matches []tuner.ResolvedProfileMatch,
	records []candidateRecord,
) ([]projectedCandidate, error) {
	catalog := make(map[string]candidateRecord)
	for _, record := range records {
		catalog[record.CandidateID] = record
	}

	best := make(map[string]projectedCandidate)

	for _, match := range matches {
		path, evaluationMode, err := oraclePath(match.Planned.Path)
		if err != nil {
			return nil, err
		}

		candidateID := match.Profile.Name + "__" + path
		record, ok := catalog[candidateID]
		if !ok {
			return nil, fmt.Errorf(
				"planner resolved candidate %q outside oracle matrix",
				candidateID,
			)
		}
		if record.EvaluationMode != evaluationMode {
			return nil, fmt.Errorf(
				"candidate %s evaluation mode mismatch: got %s expected %s",
				candidateID,
				record.EvaluationMode,
				evaluationMode,
			)
		}

		projected := projectedCandidate{
			CandidateID:      candidateID,
			Profile:          match.Profile.Name,
			Path:             path,
			EvaluationMode:   evaluationMode,
			PlannedCandidate: match.Planned.Candidate.ID,
			PlannedPath:      string(match.Planned.Path),
			PlannedFamily:    match.Planned.Candidate.Family,
			ProfileRank:      match.Rank,
			Distance:         match.Distance,
			UnderProvisioned: match.UnderProvisioned,
			ProfileChain:     match.Profile.ChainLength,
			ProfileScale:     match.Profile.ScaleBits,
			ProfileLogN:      match.Profile.LogN,
			ResolutionReason: match.Reason,
		}

		existing, exists := best[candidateID]
		if !exists ||
			projected.Distance < existing.Distance ||
			(projected.Distance == existing.Distance &&
				projected.PlannedCandidate < existing.PlannedCandidate) {
			best[candidateID] = projected
		}
	}

	output := make([]projectedCandidate, 0, len(best))
	for _, candidate := range best {
		output = append(output, candidate)
	}

	sort.Slice(output, func(i, j int) bool {
		return output[i].CandidateID < output[j].CandidateID
	})

	if len(output) == 0 {
		return nil, errors.New("planner projection produced no candidates")
	}

	return output, nil
}

func oraclePath(path tuner.ExecutionPath) (string, string, error) {
	switch path {
	case tuner.PathNonRescale:
		return "baseline_non_rescale", "naive", nil
	case tuner.PathRescale:
		return "rescale_aware", "rescale", nil
	default:
		return "", "", fmt.Errorf(
			"unsupported planner execution path %q",
			path,
		)
	}
}

func compareProjection(
	records []candidateRecord,
	projected []projectedCandidate,
) (comparisonResult, error) {
	if len(records) == 0 {
		return comparisonResult{}, errors.New("candidate group is empty")
	}

	projectedIDs := make(map[string]bool, len(projected))
	for _, candidate := range projected {
		projectedIDs[candidate.CandidateID] = true
	}

	result := comparisonResult{
		OracleCandidateCount:  len(records),
		PlannerCandidateCount: len(projectedIDs),
	}

	oracleSafe := make([]candidateRecord, 0)
	plannerSafe := make([]candidateRecord, 0)

	for _, record := range records {
		switch record.CertificateStatus {
		case "SAFE":
			result.OracleSafeCount++
			oracleSafe = append(oracleSafe, record)
		case "REJECTED":
			result.OracleRejectedCount++
		case "FAILED":
			result.OracleFailedCount++
		default:
			return comparisonResult{}, fmt.Errorf(
				"candidate %s has unknown certificate status %q",
				record.CandidateID,
				record.CertificateStatus,
			)
		}

		if !projectedIDs[record.CandidateID] {
			continue
		}

		switch record.CertificateStatus {
		case "SAFE":
			result.PlannerSafeCount++
			plannerSafe = append(plannerSafe, record)
		case "REJECTED":
			result.PlannerRejectedCount++
		case "FAILED":
			result.PlannerFailedCount++
		}
	}

	if result.PlannerSafeCount+
		result.PlannerRejectedCount+
		result.PlannerFailedCount != result.PlannerCandidateCount {
		return comparisonResult{}, errors.New(
			"planner projection contains candidates missing from oracle rows",
		)
	}

	result.PruningRatio = 1 -
		float64(result.PlannerCandidateCount)/
			float64(result.OracleCandidateCount)

	if len(oracleSafe) == 0 {
		result.OracleOutcome = "NO_SAFE"
		result.PlannerOutcome = "NO_SAFE"
		return result, nil
	}

	oracleBest, err := fastestSafe(oracleSafe)
	if err != nil {
		return comparisonResult{}, err
	}

	result.OracleOutcome = "SELECTED"
	result.OracleCandidate = oracleBest.CandidateID
	result.OracleLatencyMS = oracleBest.MeanTotalMS
	result.HasOracleLatency = true
	result.SafeRecallDefined = true
	result.SafeRecall = float64(result.PlannerSafeCount) /
		float64(result.OracleSafeCount)
	result.OptimumRecallDefined = true

	if projectedIDs[oracleBest.CandidateID] {
		result.OptimumRecall = 1
	}

	if len(plannerSafe) == 0 {
		result.PlannerOutcome = "NO_SAFE"
		result.FalseNoSafe = true
		return result, nil
	}

	plannerBest, err := fastestSafe(plannerSafe)
	if err != nil {
		return comparisonResult{}, err
	}

	result.PlannerOutcome = "SELECTED"
	result.PlannerCandidate = plannerBest.CandidateID
	result.PlannerLatencyMS = plannerBest.MeanTotalMS
	result.HasPlannerLatency = true
	result.LatencyRegretDefined = true
	result.LatencyRegret = (plannerBest.MeanTotalMS - oracleBest.MeanTotalMS) /
		oracleBest.MeanTotalMS

	return result, nil
}

func fastestSafe(records []candidateRecord) (candidateRecord, error) {
	eligible := make([]candidateRecord, 0, len(records))
	for _, record := range records {
		if record.CertificateStatus == "SAFE" && record.HasLatency {
			eligible = append(eligible, record)
		}
	}
	if len(eligible) == 0 {
		return candidateRecord{}, errors.New(
			"SAFE candidate has no finite mean_total_ms",
		)
	}

	sort.Slice(eligible, func(i, j int) bool {
		if eligible[i].MeanTotalMS != eligible[j].MeanTotalMS {
			return eligible[i].MeanTotalMS < eligible[j].MeanTotalMS
		}
		return eligible[i].CandidateID < eligible[j].CandidateID
	})

	return eligible[0], nil
}

func loadCandidateRecords(path string) ([]candidateRecord, error) {
	rows, err := readCSV(path)
	if err != nil {
		return nil, err
	}

	output := make([]candidateRecord, 0, len(rows))
	seen := make(map[string]bool)

	for rowIndex, row := range rows {
		label := fmt.Sprintf("%s row %d", path, rowIndex+2)

		seed, err := requiredInt(row, "split_seed", label)
		if err != nil {
			return nil, err
		}
		alpha, err := requiredFloat(row, "alpha", label)
		if err != nil {
			return nil, err
		}
		marginFloor, err := requiredFloat(row, "margin_floor", label)
		if err != nil {
			return nil, err
		}
		vCert, err := requiredInt(row, "v_cert", label)
		if err != nil {
			return nil, err
		}
		vAmb, err := requiredInt(row, "v_amb", label)
		if err != nil {
			return nil, err
		}

		record := candidateRecord{
			Key: studyKey{
				Seed:      seed,
				DatasetID: requiredString(row, "dataset_id"),
				ModelID:   requiredString(row, "model_id"),
				Alpha:     alpha,
			},
			CandidateID:       requiredString(row, "candidate_id"),
			Profile:           requiredString(row, "profile"),
			Path:              requiredString(row, "path"),
			EvaluationMode:    requiredString(row, "evaluation_mode"),
			CertificateStatus: requiredString(row, "certificate_status"),
			MarginFloor:       marginFloor,
			VCert:             vCert,
			VAmb:              vAmb,
		}

		if latency := strings.TrimSpace(row["mean_total_ms"]); latency != "" {
			record.MeanTotalMS, err = parseFiniteFloat(
				latency,
				label+" mean_total_ms",
			)
			if err != nil {
				return nil, err
			}
			if record.MeanTotalMS <= 0 {
				return nil, fmt.Errorf(
					"%s: mean_total_ms must be positive",
					label,
				)
			}
			record.HasLatency = true
		}

		identity := fmt.Sprintf(
			"%d|%s|%s|%s|%s",
			record.Key.Seed,
			record.Key.DatasetID,
			record.Key.ModelID,
			formatFloat(record.Key.Alpha),
			record.CandidateID,
		)
		if seen[identity] {
			return nil, fmt.Errorf(
				"%s: duplicate candidate identity %s",
				label,
				identity,
			)
		}
		seen[identity] = true

		output = append(output, record)
	}

	return output, nil
}

func loadCoverageRecords(
	path string,
) (map[splitKey]coverageRecord, error) {
	rows, err := readCSV(path)
	if err != nil {
		return nil, err
	}

	output := make(map[splitKey]coverageRecord)

	for rowIndex, row := range rows {
		label := fmt.Sprintf("%s row %d", path, rowIndex+2)

		seed, err := requiredInt(row, "split_seed", label)
		if err != nil {
			return nil, err
		}
		vCert, err := requiredInt(row, "v_cert", label)
		if err != nil {
			return nil, err
		}
		vAmb, err := requiredInt(row, "v_amb", label)
		if err != nil {
			return nil, err
		}
		marginFloor, err := requiredFloat(
			row,
			"margin_floor",
			label,
		)
		if err != nil {
			return nil, err
		}

		key := splitKey{
			Seed:      seed,
			DatasetID: requiredString(row, "dataset_id"),
			ModelID:   requiredString(row, "model_id"),
		}
		if _, exists := output[key]; exists {
			return nil, fmt.Errorf(
				"%s: duplicate coverage identity %+v",
				label,
				key,
			)
		}

		output[key] = coverageRecord{
			ValidationCSV: requiredString(row, "validation_csv"),
			ModelArtifact: requiredString(row, "model_artifact"),
			VCert:         vCert,
			VAmb:          vAmb,
			MarginFloor:   marginFloor,
		}
	}

	return output, nil
}

func groupCandidateRecords(
	records []candidateRecord,
) map[studyKey][]candidateRecord {
	output := make(map[studyKey][]candidateRecord)
	for _, record := range records {
		output[record.Key] = append(output[record.Key], record)
	}

	for key := range output {
		sort.Slice(output[key], func(i, j int) bool {
			return output[key][i].CandidateID <
				output[key][j].CandidateID
		})
	}

	return output
}

func sortedStudyKeys(
	groups map[studyKey][]candidateRecord,
) []studyKey {
	keys := make([]studyKey, 0, len(groups))
	for key := range groups {
		keys = append(keys, key)
	}

	sort.Slice(keys, func(i, j int) bool {
		if keys[i].Seed != keys[j].Seed {
			return keys[i].Seed < keys[j].Seed
		}
		if keys[i].DatasetID != keys[j].DatasetID {
			return keys[i].DatasetID < keys[j].DatasetID
		}
		if keys[i].ModelID != keys[j].ModelID {
			return keys[i].ModelID < keys[j].ModelID
		}
		return keys[i].Alpha < keys[j].Alpha
	})

	return keys
}

func writePlannerCandidates(path string, plans []groupPlan) error {
	header := []string{
		"split_seed",
		"dataset_id",
		"model_id",
		"alpha",
		"candidate_id",
		"profile",
		"path",
		"evaluation_mode",
		"planned_candidate_id",
		"planned_path",
		"planned_family",
		"profile_rank",
		"distance",
		"under_provisioned",
		"profile_chain_length",
		"profile_scale_bits",
		"profile_logN",
		"resolution_reason",
	}

	rows := make([][]string, 0, countProjectedCandidates(plans))
	for _, plan := range plans {
		for _, candidate := range plan.Candidates {
			rows = append(rows, []string{
				strconv.Itoa(plan.Key.Seed),
				plan.Key.DatasetID,
				plan.Key.ModelID,
				formatFloat(plan.Key.Alpha),
				candidate.CandidateID,
				candidate.Profile,
				candidate.Path,
				candidate.EvaluationMode,
				candidate.PlannedCandidate,
				candidate.PlannedPath,
				candidate.PlannedFamily,
				strconv.Itoa(candidate.ProfileRank),
				formatFloat(candidate.Distance),
				strconv.FormatBool(candidate.UnderProvisioned),
				strconv.Itoa(candidate.ProfileChain),
				strconv.Itoa(candidate.ProfileScale),
				strconv.Itoa(candidate.ProfileLogN),
				candidate.ResolutionReason,
			})
		}
	}

	return writeCSV(path, header, rows)
}

func writePlannerSummary(path string, plans []groupPlan) error {
	header := []string{
		"split_seed",
		"dataset_id",
		"model_id",
		"alpha",
		"protected_margin",
		"decision_budget",
		"sensitivity",
		"unit_error_budget",
		"multiplicative_depth",
		"add_ops",
		"mul_ops",
		"rot_ops",
		"rescale_ops",
		"planned_chain_length",
		"planned_scale_bits",
		"planned_logN",
		"estimated_log_qp",
		"ideal_candidate_count",
		"projected_candidate_count",
		"projected_candidate_ids",
		"planning_overhead_us",
		"plan_reason",
	}

	rows := make([][]string, 0, len(plans))
	for _, plan := range plans {
		candidateIDs := make([]string, 0, len(plan.Candidates))
		for _, candidate := range plan.Candidates {
			candidateIDs = append(candidateIDs, candidate.CandidateID)
		}

		rows = append(rows, []string{
			strconv.Itoa(plan.Key.Seed),
			plan.Key.DatasetID,
			plan.Key.ModelID,
			formatFloat(plan.Key.Alpha),
			formatFloat(plan.ProtectedMargin),
			formatFloat(plan.Plan.Budget),
			formatFloat(plan.Plan.Sensitivity),
			formatFloat(plan.Plan.UnitErrorBudget),
			strconv.Itoa(plan.Graph.MultiplicativeDepth),
			strconv.Itoa(plan.Graph.AddOps),
			strconv.Itoa(plan.Graph.MulOps),
			strconv.Itoa(plan.Graph.RotOps),
			strconv.Itoa(plan.Graph.RescaleOps),
			strconv.Itoa(plan.Plan.PlannedChainLength),
			strconv.Itoa(plan.Plan.PlannedScaleBits),
			strconv.Itoa(plan.Plan.PlannedLogN),
			strconv.Itoa(plan.Plan.EstimatedLogQP),
			strconv.Itoa(len(plan.Plan.Configurations)),
			strconv.Itoa(len(plan.Candidates)),
			strings.Join(candidateIDs, ";"),
			formatFloat(plan.OverheadUS),
			plan.Plan.Reason,
		})
	}

	return writeCSV(path, header, rows)
}

func writeComparisons(
	path string,
	plans []groupPlan,
	comparisons map[studyKey]comparisonResult,
) error {
	header := []string{
		"split_seed",
		"dataset_id",
		"model_id",
		"alpha",
		"selection_metric",
		"oracle_outcome",
		"planner_outcome",
		"oracle_candidate",
		"planner_candidate",
		"oracle_mean_total_ms",
		"planner_mean_total_ms",
		"oracle_candidate_count",
		"planner_candidate_count",
		"oracle_safe_count",
		"planner_safe_count",
		"oracle_rejected_count",
		"planner_rejected_count",
		"oracle_failed_count",
		"planner_failed_count",
		"safe_recall_defined",
		"safe_recall",
		"optimum_recall_defined",
		"optimum_recall",
		"latency_regret_defined",
		"latency_regret",
		"pruning_ratio",
		"false_no_safe",
		"planning_overhead_us",
	}

	rows := make([][]string, 0, len(plans))
	for _, plan := range plans {
		comparison := comparisons[plan.Key]

		rows = append(rows, []string{
			strconv.Itoa(plan.Key.Seed),
			plan.Key.DatasetID,
			plan.Key.ModelID,
			formatFloat(plan.Key.Alpha),
			"mean_total_ms",
			comparison.OracleOutcome,
			comparison.PlannerOutcome,
			comparison.OracleCandidate,
			comparison.PlannerCandidate,
			optionalFloat(
				comparison.HasOracleLatency,
				comparison.OracleLatencyMS,
			),
			optionalFloat(
				comparison.HasPlannerLatency,
				comparison.PlannerLatencyMS,
			),
			strconv.Itoa(comparison.OracleCandidateCount),
			strconv.Itoa(comparison.PlannerCandidateCount),
			strconv.Itoa(comparison.OracleSafeCount),
			strconv.Itoa(comparison.PlannerSafeCount),
			strconv.Itoa(comparison.OracleRejectedCount),
			strconv.Itoa(comparison.PlannerRejectedCount),
			strconv.Itoa(comparison.OracleFailedCount),
			strconv.Itoa(comparison.PlannerFailedCount),
			strconv.FormatBool(comparison.SafeRecallDefined),
			optionalFloat(
				comparison.SafeRecallDefined,
				comparison.SafeRecall,
			),
			strconv.FormatBool(comparison.OptimumRecallDefined),
			optionalFloat(
				comparison.OptimumRecallDefined,
				comparison.OptimumRecall,
			),
			strconv.FormatBool(comparison.LatencyRegretDefined),
			optionalFloat(
				comparison.LatencyRegretDefined,
				comparison.LatencyRegret,
			),
			formatFloat(comparison.PruningRatio),
			strconv.FormatBool(comparison.FalseNoSafe),
			formatFloat(plan.OverheadUS),
		})
	}

	return writeCSV(path, header, rows)
}

func writeSummary(
	path string,
	config runConfig,
	plans []groupPlan,
	comparisons map[studyKey]comparisonResult,
	plannerCandidatesPath string,
	plannerSummaryPath string,
	comparisonPath string,
) error {
	falseNoSafe := 0
	oracleNoSafe := 0
	plannerNoSafe := 0
	definedSafeRecall := 0
	definedOptimumRecall := 0
	definedLatencyRegret := 0

	for _, comparison := range comparisons {
		if comparison.FalseNoSafe {
			falseNoSafe++
		}
		if comparison.OracleOutcome == "NO_SAFE" {
			oracleNoSafe++
		}
		if comparison.PlannerOutcome == "NO_SAFE" {
			plannerNoSafe++
		}
		if comparison.SafeRecallDefined {
			definedSafeRecall++
		}
		if comparison.OptimumRecallDefined {
			definedOptimumRecall++
		}
		if comparison.LatencyRegretDefined {
			definedLatencyRegret++
		}
	}

	payload := map[string]any{
		"schema_version": schemaVersion,
		"protocol":       "flipguard_thesis_step_7b2_v1",
		"selection_metric": map[string]any{
			"name":                          config.SelectionMetric,
			"direction":                     "minimize",
			"frozen_before_full_validation": true,
		},
		"inputs": map[string]any{
			"candidate_certificates":        config.CandidateCertificates,
			"candidate_certificates_digest": sha256Path(config.CandidateCertificates),
			"validation_coverage":           config.ValidationCoverage,
			"validation_coverage_digest":    sha256Path(config.ValidationCoverage),
		},
		"outputs": map[string]any{
			"planner_candidates":        plannerCandidatesPath,
			"planner_candidates_digest": sha256Path(plannerCandidatesPath),
			"planner_summary":           plannerSummaryPath,
			"planner_summary_digest":    sha256Path(plannerSummaryPath),
			"comparison":                comparisonPath,
			"comparison_digest":         sha256Path(comparisonPath),
		},
		"counts": map[string]any{
			"comparison_rows":             len(plans),
			"planner_candidate_rows":      countProjectedCandidates(plans),
			"oracle_no_safe_rows":         oracleNoSafe,
			"planner_no_safe_rows":        plannerNoSafe,
			"false_no_safe_rows":          falseNoSafe,
			"safe_recall_defined_rows":    definedSafeRecall,
			"optimum_recall_defined_rows": definedOptimumRecall,
			"latency_regret_defined_rows": definedLatencyRegret,
		},
		"metric_semantics": map[string]any{
			"safe_recall":    "|SAFE_oracle intersect C_planner| / |SAFE_oracle|; blank when SAFE_oracle is empty",
			"optimum_recall": "1 when the exhaustive fastest-SAFE candidate is in C_planner, 0 otherwise; blank when SAFE_oracle is empty",
			"latency_regret": "(T(planner_fastest_safe)-T(oracle_fastest_safe))/T(oracle_fastest_safe); blank unless both selections exist",
			"pruning_ratio":  "1-|C_planner|/|C_oracle|",
			"false_no_safe":  "true only when SAFE_oracle is non-empty and SAFE_planner is empty",
			"oracle_no_safe": "safe/optimum recall and regret are undefined, not zero",
		},
	}

	data, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal summary JSON: %w", err)
	}

	if err := os.WriteFile(path, append(data, '\n'), 0o644); err != nil {
		return fmt.Errorf("write %s: %w", path, err)
	}

	return nil
}

func readCSV(path string) ([]map[string]string, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("open CSV %s: %w", path, err)
	}
	defer file.Close()

	reader := csv.NewReader(file)
	header, err := reader.Read()
	if err != nil {
		return nil, fmt.Errorf("read CSV header %s: %w", path, err)
	}
	if len(header) == 0 {
		return nil, fmt.Errorf("%s: empty CSV header", path)
	}

	rows := make([]map[string]string, 0)
	for {
		record, err := reader.Read()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("read CSV %s: %w", path, err)
		}
		if len(record) != len(header) {
			return nil, fmt.Errorf(
				"%s: row has %d fields, expected %d",
				path,
				len(record),
				len(header),
			)
		}

		row := make(map[string]string, len(header))
		for i, name := range header {
			row[name] = record[i]
		}
		rows = append(rows, row)
	}

	return rows, nil
}

func writeCSV(path string, header []string, rows [][]string) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return fmt.Errorf("create parent for %s: %w", path, err)
	}

	file, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CSV %s: %w", path, err)
	}

	writer := csv.NewWriter(file)
	if err := writer.Write(header); err != nil {
		file.Close()
		return fmt.Errorf("write CSV header %s: %w", path, err)
	}
	for _, row := range rows {
		if err := writer.Write(row); err != nil {
			file.Close()
			return fmt.Errorf("write CSV row %s: %w", path, err)
		}
	}
	writer.Flush()

	if err := writer.Error(); err != nil {
		file.Close()
		return fmt.Errorf("flush CSV %s: %w", path, err)
	}
	if err := file.Close(); err != nil {
		return fmt.Errorf("close CSV %s: %w", path, err)
	}

	return nil
}

func requiredString(row map[string]string, field string) string {
	return strings.TrimSpace(row[field])
}

func requiredInt(
	row map[string]string,
	field string,
	label string,
) (int, error) {
	value := requiredString(row, field)
	parsed, err := strconv.Atoi(value)
	if err != nil {
		return 0, fmt.Errorf(
			"%s: parse %s=%q as integer: %w",
			label,
			field,
			value,
			err,
		)
	}
	return parsed, nil
}

func requiredFloat(
	row map[string]string,
	field string,
	label string,
) (float64, error) {
	return parseFiniteFloat(
		requiredString(row, field),
		label+" "+field,
	)
}

func parseFiniteFloat(value string, label string) (float64, error) {
	parsed, err := strconv.ParseFloat(value, 64)
	if err != nil {
		return 0, fmt.Errorf(
			"%s: parse %q as float: %w",
			label,
			value,
			err,
		)
	}
	if math.IsNaN(parsed) || math.IsInf(parsed, 0) {
		return 0, fmt.Errorf("%s: value must be finite", label)
	}
	return parsed, nil
}

func formatFloat(value float64) string {
	return strconv.FormatFloat(value, 'g', 12, 64)
}

func optionalFloat(defined bool, value float64) string {
	if !defined {
		return ""
	}
	return formatFloat(value)
}

func countProjectedCandidates(plans []groupPlan) int {
	total := 0
	for _, plan := range plans {
		total += len(plan.Candidates)
	}
	return total
}

func sha256Path(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	digest := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(digest[:])
}
