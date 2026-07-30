package experiment

import (
	"encoding/csv"
	"fmt"
	"os"
	"path/filepath"
	"strconv"

	"github.com/hasslelee/flipguard/internal/report"
)

const ckksProfileModeComparisonOutputDir = "results/ckks_profile_mode_comparison"

type ckksProfileBenchmarkSummaryInputRow struct {
	SourceTag           string
	ProfileName         string
	EvaluationMode      string
	Status              string
	Error               string
	ProfileAccepted     bool
	DecisionSafe        bool
	ScoreErrorViolation bool
	ScoreErrorBudget    float64
	DecisionFlips       int
	MaxYError           float64
	MeanYError          float64
	MeanEvalOnlyMS      float64
	MeanTotalMS         float64
	MedianTotalMS       float64
	P95TotalMS          float64
	LogQCount           int
	LogPCount           int
	LogQPSum            int
	MaxLevel            int
	LogDefaultScale     int
}

// RunCKKSProfileModeComparison combines naive and rescale profile benchmark summaries.
func RunCKKSProfileModeComparison() error {
	options := GetRuntimeOptions()

	naiveRows, err := readCKKSProfileBenchmarkSummaryRows(options.CKKSNaiveProfileBenchmarkTag)
	if err != nil {
		return fmt.Errorf("read naive profile benchmark summary: %w", err)
	}

	rescaleRows, err := readCKKSProfileBenchmarkSummaryRows(options.CKKSRescaleProfileBenchmarkTag)
	if err != nil {
		return fmt.Errorf("read rescale profile benchmark summary: %w", err)
	}

	inputRows := append(naiveRows, rescaleRows...)

	baselineEvalOnlyMS, baselineTotalMS, err := findDefaultNaiveBaseline(inputRows, options.CKKSNaiveProfileBenchmarkTag)
	if err != nil {
		return fmt.Errorf("find default naive baseline: %w", err)
	}

	comparisonRows := make([]report.CKKSProfileModeComparisonRow, 0, len(inputRows))

	for _, inputRow := range inputRows {
		row := report.CKKSProfileModeComparisonRow{
			SourceTag:           inputRow.SourceTag,
			ProfileName:         inputRow.ProfileName,
			EvaluationMode:      inputRow.EvaluationMode,
			Status:              inputRow.Status,
			Error:               inputRow.Error,
			ProfileAccepted:     inputRow.ProfileAccepted,
			DecisionSafe:        inputRow.DecisionSafe,
			ScoreErrorViolation: inputRow.ScoreErrorViolation,
			ScoreErrorBudget:    inputRow.ScoreErrorBudget,
			DecisionFlips:       inputRow.DecisionFlips,
			MaxYError:           inputRow.MaxYError,
			MeanYError:          inputRow.MeanYError,
			MeanEvalOnlyMS:      inputRow.MeanEvalOnlyMS,
			MeanTotalMS:         inputRow.MeanTotalMS,
			MedianTotalMS:       inputRow.MedianTotalMS,
			P95TotalMS:          inputRow.P95TotalMS,
			LogQCount:           inputRow.LogQCount,
			LogPCount:           inputRow.LogPCount,
			LogQPSum:            inputRow.LogQPSum,
			MaxLevel:            inputRow.MaxLevel,
			LogDefaultScale:     inputRow.LogDefaultScale,
		}

		if row.MeanEvalOnlyMS > 0 {
			row.SpeedupVsDefaultNaiveEvalOnly = baselineEvalOnlyMS / row.MeanEvalOnlyMS
		}

		if row.MeanTotalMS > 0 {
			row.SpeedupVsDefaultNaiveTotal = baselineTotalMS / row.MeanTotalMS
		}

		comparisonRows = append(comparisonRows, row)
	}

	markFastestAcceptedProfileMode(comparisonRows)

	outputDir := CKKSResultDir(ckksProfileModeComparisonOutputDir)

	if err := report.WriteCKKSProfileModeComparisonCSV(
		filepath.Join(outputDir, "summary.csv"),
		comparisonRows,
	); err != nil {
		return fmt.Errorf("write CKKS profile mode comparison CSV: %w", err)
	}

	if err := report.WriteCKKSProfileModeComparisonTex(
		filepath.Join(outputDir, "table.tex"),
		comparisonRows,
	); err != nil {
		return fmt.Errorf("write CKKS profile mode comparison TeX: %w", err)
	}

	acceptedCount := 0
	selectedProfile := ""
	selectedMode := ""
	selectedSpeedup := 0.0

	for _, row := range comparisonRows {
		if row.ProfileAccepted {
			acceptedCount++
		}

		if row.SelectedFastestAccepted {
			selectedProfile = row.ProfileName
			selectedMode = row.EvaluationMode
			selectedSpeedup = row.SpeedupVsDefaultNaiveEvalOnly
		}
	}

	fmt.Println("FlipGuard CKKS profile-mode comparison")
	fmt.Printf(
		"naive_tag=%s rescale_tag=%s output_tag=%s rows=%d accepted_rows=%d baseline_eval_only_ms=%.6f baseline_total_ms=%.6f\n",
		options.CKKSNaiveProfileBenchmarkTag,
		options.CKKSRescaleProfileBenchmarkTag,
		options.CKKSOutputTag,
		len(comparisonRows),
		acceptedCount,
		baselineEvalOnlyMS,
		baselineTotalMS,
	)

	if selectedProfile != "" {
		fmt.Printf(
			"selected_fastest_accepted profile=%s evaluation_mode=%s speedup_vs_default_naive_eval_only=%.6f\n",
			selectedProfile,
			selectedMode,
			selectedSpeedup,
		)
	}

	fmt.Println()
	fmt.Printf("Exported CKKS profile-mode comparison files to %s/\n", outputDir)

	return nil
}

func readCKKSProfileBenchmarkSummaryRows(tag string) ([]ckksProfileBenchmarkSummaryInputRow, error) {
	if tag == "" {
		return nil, fmt.Errorf("profile benchmark tag must not be empty")
	}

	path := filepath.Join(ckksProfileBenchmarkOutputDir, tag, "summary.csv")

	f, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("open %s: %w", path, err)
	}
	defer f.Close()

	reader := csv.NewReader(f)

	records, err := reader.ReadAll()
	if err != nil {
		return nil, fmt.Errorf("read %s: %w", path, err)
	}

	if len(records) < 2 {
		return nil, fmt.Errorf("summary csv %s has no data rows", path)
	}

	header := make(map[string]int)
	for i, name := range records[0] {
		header[name] = i
	}

	rows := make([]ckksProfileBenchmarkSummaryInputRow, 0, len(records)-1)

	for rowIndex, record := range records[1:] {
		row, err := parseCKKSProfileBenchmarkSummaryRow(tag, header, record)
		if err != nil {
			return nil, fmt.Errorf("parse %s row %d: %w", path, rowIndex+2, err)
		}

		rows = append(rows, row)
	}

	return rows, nil
}

func parseCKKSProfileBenchmarkSummaryRow(
	sourceTag string,
	header map[string]int,
	record []string,
) (ckksProfileBenchmarkSummaryInputRow, error) {
	profileName, err := requiredCSVField(header, record, "profile")
	if err != nil {
		return ckksProfileBenchmarkSummaryInputRow{}, err
	}

	evaluationMode, err := requiredCSVField(header, record, "evaluation_mode")
	if err != nil {
		return ckksProfileBenchmarkSummaryInputRow{}, err
	}

	status, err := requiredCSVField(header, record, "status")
	if err != nil {
		return ckksProfileBenchmarkSummaryInputRow{}, err
	}

	row := ckksProfileBenchmarkSummaryInputRow{
		SourceTag:      sourceTag,
		ProfileName:    profileName,
		EvaluationMode: evaluationMode,
		Status:         status,
		Error:          optionalCSVField(header, record, "error"),
	}

	if row.ProfileAccepted, err = parseCSVBool(header, record, "profile_accepted"); err != nil {
		return ckksProfileBenchmarkSummaryInputRow{}, err
	}

	if row.DecisionSafe, err = parseCSVBool(header, record, "decision_safe"); err != nil {
		return ckksProfileBenchmarkSummaryInputRow{}, err
	}

	if row.ScoreErrorViolation, err = parseCSVBool(header, record, "score_error_violation"); err != nil {
		return ckksProfileBenchmarkSummaryInputRow{}, err
	}

	if row.ScoreErrorBudget, err = parseCSVFloat(header, record, "score_error_budget"); err != nil {
		return ckksProfileBenchmarkSummaryInputRow{}, err
	}

	if row.DecisionFlips, err = parseCSVInt(header, record, "decision_flips"); err != nil {
		return ckksProfileBenchmarkSummaryInputRow{}, err
	}

	if row.MaxYError, err = parseCSVFloat(header, record, "max_y_error"); err != nil {
		return ckksProfileBenchmarkSummaryInputRow{}, err
	}

	if row.MeanYError, err = parseCSVFloat(header, record, "mean_y_error"); err != nil {
		return ckksProfileBenchmarkSummaryInputRow{}, err
	}

	if row.MeanEvalOnlyMS, err = parseCSVFloat(header, record, "mean_eval_only_ms"); err != nil {
		return ckksProfileBenchmarkSummaryInputRow{}, err
	}

	if row.MeanTotalMS, err = parseCSVFloat(header, record, "mean_total_eval_ms"); err != nil {
		return ckksProfileBenchmarkSummaryInputRow{}, err
	}

	if row.MedianTotalMS, err = parseCSVFloat(header, record, "median_total_eval_ms"); err != nil {
		return ckksProfileBenchmarkSummaryInputRow{}, err
	}

	if row.P95TotalMS, err = parseCSVFloat(header, record, "p95_total_eval_ms"); err != nil {
		return ckksProfileBenchmarkSummaryInputRow{}, err
	}

	if row.LogQCount, err = parseCSVInt(header, record, "log_q_count"); err != nil {
		return ckksProfileBenchmarkSummaryInputRow{}, err
	}

	if row.LogPCount, err = parseCSVInt(header, record, "log_p_count"); err != nil {
		return ckksProfileBenchmarkSummaryInputRow{}, err
	}

	if row.LogQPSum, err = parseCSVInt(header, record, "log_qp_sum"); err != nil {
		return ckksProfileBenchmarkSummaryInputRow{}, err
	}

	if row.MaxLevel, err = parseCSVInt(header, record, "max_level"); err != nil {
		return ckksProfileBenchmarkSummaryInputRow{}, err
	}

	if row.LogDefaultScale, err = parseCSVInt(header, record, "log_default_scale"); err != nil {
		return ckksProfileBenchmarkSummaryInputRow{}, err
	}

	return row, nil
}

func findDefaultNaiveBaseline(
	rows []ckksProfileBenchmarkSummaryInputRow,
	sourceTag string,
) (float64, float64, error) {
	for _, row := range rows {
		if row.SourceTag == sourceTag &&
			row.ProfileName == "default" &&
			row.EvaluationMode == "naive" &&
			row.Status == "ok" {
			if row.MeanEvalOnlyMS <= 0 || row.MeanTotalMS <= 0 {
				return 0, 0, fmt.Errorf("default naive baseline has non-positive timing")
			}

			return row.MeanEvalOnlyMS, row.MeanTotalMS, nil
		}
	}

	return 0, 0, fmt.Errorf("default naive baseline not found in tag %s", sourceTag)
}

func markFastestAcceptedProfileMode(rows []report.CKKSProfileModeComparisonRow) {
	selectedIndex := -1
	bestSpeedup := 0.0

	for i, row := range rows {
		if row.Status != "ok" || !row.ProfileAccepted {
			continue
		}

		if row.SpeedupVsDefaultNaiveEvalOnly > bestSpeedup {
			selectedIndex = i
			bestSpeedup = row.SpeedupVsDefaultNaiveEvalOnly
			continue
		}

		if row.SpeedupVsDefaultNaiveEvalOnly == bestSpeedup &&
			selectedIndex >= 0 &&
			row.MeanTotalMS < rows[selectedIndex].MeanTotalMS {
			selectedIndex = i
		}
	}

	if selectedIndex >= 0 {
		rows[selectedIndex].SelectedFastestAccepted = true
	}
}

func requiredCSVField(header map[string]int, record []string, name string) (string, error) {
	value := optionalCSVField(header, record, name)
	if value == "" {
		return "", fmt.Errorf("missing required field %s", name)
	}

	return value, nil
}

func optionalCSVField(header map[string]int, record []string, name string) string {
	index, ok := header[name]
	if !ok || index < 0 || index >= len(record) {
		return ""
	}

	return record[index]
}

func parseCSVFloat(header map[string]int, record []string, name string) (float64, error) {
	value := optionalCSVField(header, record, name)
	if value == "" {
		return 0, nil
	}

	parsed, err := strconv.ParseFloat(value, 64)
	if err != nil {
		return 0, fmt.Errorf("parse float field %s=%q: %w", name, value, err)
	}

	return parsed, nil
}

func parseCSVInt(header map[string]int, record []string, name string) (int, error) {
	value := optionalCSVField(header, record, name)
	if value == "" {
		return 0, nil
	}

	parsed, err := strconv.Atoi(value)
	if err != nil {
		return 0, fmt.Errorf("parse int field %s=%q: %w", name, value, err)
	}

	return parsed, nil
}

func parseCSVBool(header map[string]int, record []string, name string) (bool, error) {
	value := optionalCSVField(header, record, name)
	if value == "" {
		return false, nil
	}

	parsed, err := strconv.ParseBool(value)
	if err != nil {
		return false, fmt.Errorf("parse bool field %s=%q: %w", name, value, err)
	}

	return parsed, nil
}
