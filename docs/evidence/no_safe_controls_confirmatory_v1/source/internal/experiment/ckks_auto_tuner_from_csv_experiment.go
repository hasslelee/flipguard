package experiment

import (
	"encoding/csv"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"

	"github.com/hasslelee/flipguard/internal/report"
	"github.com/hasslelee/flipguard/internal/tuner"
)

const ckksAutoTunerFromCSVResultDir = "results/ckks_auto_tuner_from_csv"

var ckksAutoTunerCSVDefaultSources = []string{
	"results/ckks_profile_mode_comparison/comparison.csv",
	"results/ckks_policy_comparison/comparison.csv",
	"results/ckks_paper_table/table.csv",
	"results/logreg_small/ckks_scale_plan_summary.csv",
}

// RunCKKSAutoTunerFromCSV adapts an existing experiment CSV into the common
// FlipGuard tuner artifact format.
//
// This experiment is an integration bridge between earlier CKKS experiments and
// the new auto-tuner reporting pipeline. It does not rerun CKKS by itself.
// Instead, it reads an existing CSV artifact, infers candidate evaluations from
// common column names, and exports:
//
//   - tuner_candidates.csv
//   - tuner_selection.csv
//
// To force a specific source CSV, set:
//
//	FLIPGUARD_TUNER_SOURCE_CSV=/path/to/source.csv
func RunCKKSAutoTunerFromCSV() error {
	sourcePath, err := resolveCKKSAutoTunerSourceCSV()
	if err != nil {
		return err
	}

	evaluations, err := loadTunerEvaluationsFromCSV(sourcePath)
	if err != nil {
		return fmt.Errorf("load tuner evaluations from %s: %w", sourcePath, err)
	}

	if len(evaluations) == 0 {
		return fmt.Errorf("no tuner evaluations could be inferred from %s", sourcePath)
	}

	fastestSafe, err := tuner.SelectFastestSafe(evaluations)
	if err != nil {
		return fmt.Errorf("select fastest safe candidate from %s: %w", sourcePath, err)
	}

	latencyOnly, err := tuner.SelectLatencyOnly(evaluations)
	if err != nil {
		return fmt.Errorf("select latency-only candidate from %s: %w", sourcePath, err)
	}

	referenceEval := chooseCSVReferenceEvaluation(evaluations)

	candidatesPath, err := report.ExportTunerCandidateEvaluations(
		ckksAutoTunerFromCSVResultDir,
		"tuner_candidates.csv",
		evaluations,
	)
	if err != nil {
		return fmt.Errorf("export tuner candidate evaluations: %w", err)
	}

	selectionPath, err := report.ExportTunerSelectionRecords(
		ckksAutoTunerFromCSVResultDir,
		"tuner_selection.csv",
		[]report.TunerSelectionRecord{
			{
				Policy:     "reference_or_baseline",
				Evaluation: referenceEval,
			},
			{
				Policy:     "fastest_safe",
				Evaluation: fastestSafe,
			},
			{
				Policy:     "latency_only",
				Evaluation: latencyOnly,
			},
		},
	)
	if err != nil {
		return fmt.Errorf("export tuner selection records: %w", err)
	}

	sourceInfoPath, err := writeCKKSAutoTunerSourceInfo(sourcePath, len(evaluations))
	if err != nil {
		return fmt.Errorf("write source info: %w", err)
	}

	fmt.Printf("Source CSV: %s\n", sourcePath)
	fmt.Printf("Loaded %d candidate evaluations\n", len(evaluations))
	printCSVSelection("Reference/baseline", referenceEval)
	printCSVSelection("Fastest safe", fastestSafe)
	printCSVSelection("Latency-only", latencyOnly)
	fmt.Printf("Wrote %s\n", candidatesPath)
	fmt.Printf("Wrote %s\n", selectionPath)
	fmt.Printf("Wrote %s\n", sourceInfoPath)

	return nil
}

func resolveCKKSAutoTunerSourceCSV() (string, error) {
	if forced := strings.TrimSpace(os.Getenv("FLIPGUARD_TUNER_SOURCE_CSV")); forced != "" {
		if _, err := os.Stat(forced); err != nil {
			return "", fmt.Errorf("FLIPGUARD_TUNER_SOURCE_CSV=%s is not readable: %w", forced, err)
		}
		return forced, nil
	}

	for _, candidate := range ckksAutoTunerCSVDefaultSources {
		if _, err := os.Stat(candidate); err == nil {
			return candidate, nil
		}
	}

	return "", fmt.Errorf(
		"no source CSV found; set FLIPGUARD_TUNER_SOURCE_CSV or create one of: %s",
		strings.Join(ckksAutoTunerCSVDefaultSources, ", "),
	)
}

func loadTunerEvaluationsFromCSV(path string) ([]tuner.CandidateEvaluation, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	reader := csv.NewReader(f)
	reader.FieldsPerRecord = -1

	rows, err := reader.ReadAll()
	if err != nil {
		return nil, err
	}
	if len(rows) < 2 {
		return nil, fmt.Errorf("expected header and at least one data row")
	}

	header := buildCSVHeaderIndex(rows[0])

	evaluations := make([]tuner.CandidateEvaluation, 0, len(rows)-1)
	for rowIndex, row := range rows[1:] {
		if isCSVRowEmpty(row) {
			continue
		}

		evaluation := inferCandidateEvaluationFromCSVRow(header, row, rowIndex)
		evaluations = append(evaluations, evaluation)
	}

	return evaluations, nil
}

func buildCSVHeaderIndex(header []string) map[string]int {
	index := map[string]int{}
	for i, name := range header {
		normalized := normalizeCSVColumnName(name)
		if normalized == "" {
			continue
		}
		if _, exists := index[normalized]; !exists {
			index[normalized] = i
		}
	}
	return index
}

func inferCandidateEvaluationFromCSVRow(
	header map[string]int,
	row []string,
	rowIndex int,
) tuner.CandidateEvaluation {
	candidateID := firstCSVValue(header, row,
		"candidate_id",
		"config_id",
		"profile_id",
		"profile",
		"profile_name",
		"policy",
		"mode",
		"tag",
		"name",
		"experiment",
	)
	if candidateID == "" {
		candidateID = fmt.Sprintf("csv_candidate_%03d", rowIndex)
	}

	path := inferExecutionPathFromCSV(header, row, candidateID)

	logN := firstCSVInt(header, row, 14,
		"logn",
		"log_n",
		"ring_log_n",
		"ckks_logn",
	)
	if parsed, ok := parseCSVIntPattern(candidateID, `N(\d+)`); ok {
		logN = parsed
	}

	chainLength := firstCSVInt(header, row, 0,
		"chain_length",
		"chain",
		"levels",
		"level_count",
		"num_levels",
	)
	if parsed, ok := parseCSVIntPattern(candidateID, `chain(\d+)`); ok {
		chainLength = parsed
	}
	if chainLength <= 0 {
		chainLength = firstCSVInt(header, row, 0,
			"moduli",
			"modulus_chain",
		)
	}
	if chainLength <= 0 {
		chainLength = 1
	}

	scaleBits := firstCSVInt(header, row, 0,
		"scale_bits",
		"scale",
		"log_scale",
		"initial_scale_bits",
	)
	if parsed, ok := parseCSVIntPattern(candidateID, `scale(\d+)`); ok {
		scaleBits = parsed
	}

	slots := firstCSVInt(header, row, 0,
		"slots",
		"num_slots",
	)
	if slots <= 0 {
		slots = csvSlotsFromLogN(logN)
	}

	family := firstCSVValue(header, row,
		"family",
		"candidate_family",
		"group",
	)
	if family == "" {
		family = inferCSVFamily(candidateID)
	}

	isReference := firstCSVBool(header, row,
		strings.Contains(strings.ToLower(candidateID), "reference") ||
			strings.Contains(strings.ToLower(candidateID), "default") ||
			strings.Contains(strings.ToLower(candidateID), "baseline"),
		"is_reference",
		"reference",
		"is_default",
		"default",
	)

	successRuns := firstCSVInt(header, row, 1,
		"success_runs",
		"successful_runs",
		"runs",
		"num_runs",
		"count",
	)

	failedRuns := firstCSVInt(header, row, 0,
		"failed_runs",
		"failures",
		"failure_count",
		"failed",
	)

	decisionFlips := firstCSVInt(header, row, 0,
		"decision_flips",
		"flip_count",
		"flips",
		"decision_flip_count",
	)

	errorViolations := firstCSVInt(header, row, 0,
		"error_violations",
		"violations",
		"violation_count",
		"output_violations",
		"accuracy_violations",
	)

	maxOutputError := firstCSVFloat(header, row, 0,
		"max_output_error",
		"max_abs_error",
		"max_error",
		"output_error",
		"score_abs_error",
		"abs_error",
	)

	meanTotalMS := firstCSVFloat(header, row, 0,
		"mean_total_ms",
		"avg_total_ms",
		"total_ms",
		"latency_ms",
		"mean_ms",
		"avg_ms",
		"runtime_ms",
		"elapsed_ms",
		"time_ms",
	)

	status := strings.ToLower(firstCSVValue(header, row,
		"status",
		"safety_status",
		"result",
	))
	if strings.Contains(status, "fail") && failedRuns == 0 {
		failedRuns = 1
		successRuns = 0
	}
	if strings.Contains(status, "reject") && decisionFlips == 0 && errorViolations == 0 {
		errorViolations = 1
	}

	if meanTotalMS <= 0 {
		meanTotalMS = 100.0 + float64(rowIndex)
	}

	return tuner.CandidateEvaluation{
		Config: tuner.ExecutionConfiguration{
			Candidate: tuner.ParameterCandidate{
				ID:          candidateID,
				LogN:        logN,
				Slots:       slots,
				ChainLength: chainLength,
				ScaleBits:   scaleBits,
				Family:      family,
				IsReference: isReference,
			},
			Path: path,
		},
		SuccessRuns:     successRuns,
		FailedRuns:      failedRuns,
		DecisionFlips:   decisionFlips,
		ErrorViolations: errorViolations,
		MaxOutputError:  maxOutputError,
		MeanTotalMS:     meanTotalMS,
	}
}

func inferExecutionPathFromCSV(
	header map[string]int,
	row []string,
	candidateID string,
) tuner.ExecutionPath {
	value := strings.ToLower(firstCSVValue(header, row,
		"path",
		"execution_path",
		"evaluation_mode",
		"mode",
		"ckks_mode",
	))

	combined := value + " " + strings.ToLower(candidateID)

	if strings.Contains(combined, "non-rescale") ||
		strings.Contains(combined, "non_rescale") ||
		strings.Contains(combined, "naive") {
		return tuner.PathNonRescale
	}

	if strings.Contains(combined, "rescale") {
		return tuner.PathRescale
	}

	return tuner.PathRescale
}

func chooseCSVReferenceEvaluation(evaluations []tuner.CandidateEvaluation) tuner.CandidateEvaluation {
	for _, evaluation := range evaluations {
		if evaluation.Config.Candidate.IsReference {
			return evaluation
		}
	}

	var bestSafe tuner.CandidateEvaluation
	foundSafe := false
	for _, evaluation := range evaluations {
		if !evaluation.IsSafe() {
			continue
		}
		if !foundSafe || evaluation.MeanTotalMS > bestSafe.MeanTotalMS {
			bestSafe = evaluation
			foundSafe = true
		}
	}
	if foundSafe {
		return bestSafe
	}

	return evaluations[0]
}

func writeCKKSAutoTunerSourceInfo(sourcePath string, evaluationCount int) (string, error) {
	if err := os.MkdirAll(ckksAutoTunerFromCSVResultDir, 0755); err != nil {
		return "", err
	}

	path := filepath.Join(ckksAutoTunerFromCSVResultDir, "source_info.txt")

	content := fmt.Sprintf(
		"source_csv=%s\nevaluation_count=%d\n",
		sourcePath,
		evaluationCount,
	)

	if err := os.WriteFile(path, []byte(content), 0644); err != nil {
		return "", err
	}

	return path, nil
}

func firstCSVValue(header map[string]int, row []string, names ...string) string {
	for _, name := range names {
		index, ok := header[normalizeCSVColumnName(name)]
		if !ok || index < 0 || index >= len(row) {
			continue
		}

		value := strings.TrimSpace(row[index])
		if value != "" {
			return value
		}
	}

	return ""
}

func firstCSVInt(header map[string]int, row []string, fallback int, names ...string) int {
	value := firstCSVValue(header, row, names...)
	if value == "" {
		return fallback
	}

	parsed, err := strconv.Atoi(cleanNumericString(value))
	if err != nil {
		return fallback
	}

	return parsed
}

func firstCSVFloat(header map[string]int, row []string, fallback float64, names ...string) float64 {
	value := firstCSVValue(header, row, names...)
	if value == "" {
		return fallback
	}

	parsed, err := strconv.ParseFloat(cleanNumericString(value), 64)
	if err != nil {
		return fallback
	}

	return parsed
}

func firstCSVBool(header map[string]int, row []string, fallback bool, names ...string) bool {
	value := strings.ToLower(firstCSVValue(header, row, names...))
	if value == "" {
		return fallback
	}

	switch value {
	case "true", "t", "yes", "y", "1":
		return true
	case "false", "f", "no", "n", "0":
		return false
	default:
		return fallback
	}
}

func parseCSVIntPattern(value string, pattern string) (int, bool) {
	re := regexp.MustCompile(pattern)
	matches := re.FindStringSubmatch(value)
	if len(matches) < 2 {
		return 0, false
	}

	parsed, err := strconv.Atoi(matches[1])
	if err != nil {
		return 0, false
	}

	return parsed, true
}

func normalizeCSVColumnName(name string) string {
	name = strings.TrimSpace(strings.ToLower(name))
	name = strings.ReplaceAll(name, "-", "_")
	name = strings.ReplaceAll(name, " ", "_")
	name = strings.ReplaceAll(name, ".", "_")
	return name
}

func cleanNumericString(value string) string {
	value = strings.TrimSpace(value)
	value = strings.TrimSuffix(value, "ms")
	value = strings.TrimSuffix(value, "%")
	value = strings.ReplaceAll(value, ",", "")
	return strings.TrimSpace(value)
}

func inferCSVFamily(candidateID string) string {
	lower := strings.ToLower(candidateID)

	switch {
	case strings.Contains(lower, "reference"):
		return "reference"
	case strings.Contains(lower, "default"):
		return "reference"
	case strings.Contains(lower, "baseline"):
		return "baseline"
	case strings.Contains(lower, "flipguard"):
		return "flipguard"
	case strings.Contains(lower, "latency"):
		return "latency"
	default:
		return "csv"
	}
}

func csvSlotsFromLogN(logN int) int {
	if logN <= 1 {
		return 1
	}
	return 1 << (logN - 1)
}

func isCSVRowEmpty(row []string) bool {
	for _, value := range row {
		if strings.TrimSpace(value) != "" {
			return false
		}
	}
	return true
}

func printCSVSelection(label string, evaluation tuner.CandidateEvaluation) {
	fmt.Printf("%s: %s/%s status=%s mean_total_ms=%.4f max_output_error=%.6f flips=%d violations=%d failures=%d\n",
		label,
		evaluation.Config.Candidate.ID,
		evaluation.Config.Path,
		evaluation.Status(),
		evaluation.MeanTotalMS,
		evaluation.MaxOutputError,
		evaluation.DecisionFlips,
		evaluation.ErrorViolations,
		evaluation.FailedRuns,
	)
}
