package report

import (
	"encoding/csv"
	"fmt"
	"os"
	"strings"
)

// CKKSProfileModeComparisonRow stores one paper-ready profile and mode comparison row.
type CKKSProfileModeComparisonRow struct {
	SourceTag                     string
	ProfileName                   string
	EvaluationMode                string
	Status                        string
	Error                         string
	ProfileAccepted               bool
	DecisionSafe                  bool
	ScoreErrorViolation           bool
	ScoreErrorBudget              float64
	DecisionFlips                 int
	MaxYError                     float64
	MeanYError                    float64
	MeanEvalOnlyMS                float64
	MeanTotalMS                   float64
	MedianTotalMS                 float64
	P95TotalMS                    float64
	SpeedupVsDefaultNaiveEvalOnly float64
	SpeedupVsDefaultNaiveTotal    float64
	SelectedFastestAccepted       bool
	LogQCount                     int
	LogPCount                     int
	LogQPSum                      int
	MaxLevel                      int
	LogDefaultScale               int
}

// WriteCKKSProfileModeComparisonCSV writes paper-ready CKKS profile and mode comparison rows.
func WriteCKKSProfileModeComparisonCSV(
	path string,
	rows []CKKSProfileModeComparisonRow,
) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS profile mode comparison csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"source_tag",
		"profile",
		"evaluation_mode",
		"status",
		"error",
		"profile_accepted",
		"decision_safe",
		"score_error_violation",
		"score_error_budget",
		"decision_flips",
		"max_y_error",
		"mean_y_error",
		"mean_eval_only_ms",
		"mean_total_ms",
		"median_total_ms",
		"p95_total_ms",
		"speedup_vs_default_naive_eval_only",
		"speedup_vs_default_naive_total",
		"selected_fastest_accepted",
		"log_q_count",
		"log_p_count",
		"log_qp_sum",
		"max_level",
		"log_default_scale",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS profile mode comparison header: %w", err)
	}

	for i, row := range rows {
		record := []string{
			row.SourceTag,
			row.ProfileName,
			row.EvaluationMode,
			row.Status,
			row.Error,
			fmt.Sprintf("%t", row.ProfileAccepted),
			fmt.Sprintf("%t", row.DecisionSafe),
			fmt.Sprintf("%t", row.ScoreErrorViolation),
			formatCKKSProfileModeComparisonFloat(row.ScoreErrorBudget),
			fmt.Sprintf("%d", row.DecisionFlips),
			formatCKKSProfileModeComparisonFloat(row.MaxYError),
			formatCKKSProfileModeComparisonFloat(row.MeanYError),
			formatCKKSProfileModeComparisonFloat(row.MeanEvalOnlyMS),
			formatCKKSProfileModeComparisonFloat(row.MeanTotalMS),
			formatCKKSProfileModeComparisonFloat(row.MedianTotalMS),
			formatCKKSProfileModeComparisonFloat(row.P95TotalMS),
			formatCKKSProfileModeComparisonFloat(row.SpeedupVsDefaultNaiveEvalOnly),
			formatCKKSProfileModeComparisonFloat(row.SpeedupVsDefaultNaiveTotal),
			fmt.Sprintf("%t", row.SelectedFastestAccepted),
			fmt.Sprintf("%d", row.LogQCount),
			fmt.Sprintf("%d", row.LogPCount),
			fmt.Sprintf("%d", row.LogQPSum),
			fmt.Sprintf("%d", row.MaxLevel),
			fmt.Sprintf("%d", row.LogDefaultScale),
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write CKKS profile mode comparison row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS profile mode comparison csv: %w", err)
	}

	return nil
}

// WriteCKKSProfileModeComparisonTex writes a compact LaTeX table for the comparison.
func WriteCKKSProfileModeComparisonTex(
	path string,
	rows []CKKSProfileModeComparisonRow,
) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS profile mode comparison tex: %w", err)
	}
	defer f.Close()

	fmt.Fprintln(f, "\\begin{table}[t]")
	fmt.Fprintln(f, "\\centering")
	fmt.Fprintln(f, "\\caption{CKKS profile and evaluation-mode comparison.}")
	fmt.Fprintln(f, "\\label{tab:ckks-profile-mode-comparison}")
	fmt.Fprintln(f, "\\begin{tabular}{lllrrrr}")
	fmt.Fprintln(f, "\\toprule")
	fmt.Fprintln(f, "Profile & Mode & Accepted & Eval-only ms & Speedup & Flips & Max error \\\\")
	fmt.Fprintln(f, "\\midrule")

	for _, row := range rows {
		profile := escapeLatex(row.ProfileName)
		if row.SelectedFastestAccepted {
			profile += "$^{\\star}$"
		}

		accepted := "No"
		if row.ProfileAccepted {
			accepted = "Yes"
		}

		evalOnly := "--"
		speedup := "--"
		flips := "--"
		maxError := "--"

		if row.Status == "ok" {
			evalOnly = fmt.Sprintf("%.2f", row.MeanEvalOnlyMS)
			speedup = fmt.Sprintf("%.3f", row.SpeedupVsDefaultNaiveEvalOnly)
			flips = fmt.Sprintf("%d", row.DecisionFlips)
			maxError = fmt.Sprintf("%.2e", row.MaxYError)
		}

		fmt.Fprintf(
			f,
			"%s & %s & %s & %s & %s & %s & %s \\\\\n",
			profile,
			escapeLatex(row.EvaluationMode),
			accepted,
			evalOnly,
			speedup,
			flips,
			maxError,
		)
	}

	fmt.Fprintln(f, "\\bottomrule")
	fmt.Fprintln(f, "\\end{tabular}")
	fmt.Fprintln(f, "\\end{table}")

	return nil
}

func formatCKKSProfileModeComparisonFloat(value float64) string {
	return fmt.Sprintf("%.10f", value)
}

func escapeLatex(value string) string {
	replacer := strings.NewReplacer(
		"\\", "\\textbackslash{}",
		"_", "\\_",
		"&", "\\&",
		"%", "\\%",
		"$", "\\$",
		"#", "\\#",
		"{", "\\{",
		"}", "\\}",
		"~", "\\textasciitilde{}",
		"^", "\\textasciicircum{}",
	)

	return replacer.Replace(value)
}
