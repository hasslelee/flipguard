package report

import (
	"encoding/csv"
	"fmt"
	"os"
	"strings"
)

// CKKSPaperTableRow stores one compact paper-ready comparison row.
type CKKSPaperTableRow struct {
	Method          string
	Evaluation      string
	Certification   string
	StableFlips     string
	Violations      string
	ScoreViolations string
	Usage           string
	MaxError        string
	AvgBits         string
	Saving          string
}

// WriteCKKSPaperTableCSV writes compact paper-ready comparison rows.
func WriteCKKSPaperTableCSV(path string, rows []CKKSPaperTableRow) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS paper table csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"method",
		"evaluation",
		"certification",
		"stable_flips",
		"margin_violations",
		"score_violations",
		"usage",
		"max_error",
		"avg_bits",
		"saving",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS paper table header: %w", err)
	}

	for i, row := range rows {
		record := []string{
			row.Method,
			row.Evaluation,
			row.Certification,
			row.StableFlips,
			row.Violations,
			row.ScoreViolations,
			row.Usage,
			row.MaxError,
			row.AvgBits,
			row.Saving,
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write CKKS paper table row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS paper table csv: %w", err)
	}

	return nil
}

// WriteCKKSPaperTableLaTeX writes a compact LaTeX table.
func WriteCKKSPaperTableLaTeX(path string, rows []CKKSPaperTableRow) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS paper table LaTeX: %w", err)
	}
	defer f.Close()

	if _, err := fmt.Fprintln(f, `\begin{table}[t]`); err != nil {
		return err
	}
	if _, err := fmt.Fprintln(f, `\centering`); err != nil {
		return err
	}
	if _, err := fmt.Fprintln(f, `\caption{CKKS observed certificate and simulated precision policy comparison.}`); err != nil {
		return err
	}
	if _, err := fmt.Fprintln(f, `\label{tab:ckks-policy-comparison}`); err != nil {
		return err
	}
	if _, err := fmt.Fprintln(f, `\begin{tabular}{llrrrrrr}`); err != nil {
		return err
	}
	if _, err := fmt.Fprintln(f, `\hline`); err != nil {
		return err
	}
	if _, err := fmt.Fprintln(f, `Method & Cert. & Stable flips & Margin viol. & Score viol. & Usage & Avg. bits & Saving \\`); err != nil {
		return err
	}
	if _, err := fmt.Fprintln(f, `\hline`); err != nil {
		return err
	}

	for _, row := range rows {
		method := latexEscape(row.Method)
		certification := latexEscape(row.Certification)
		stableFlips := latexDash(row.StableFlips)
		violations := latexDash(row.Violations)
		scoreViolations := latexDash(row.ScoreViolations)
		usage := latexDash(row.Usage)
		avgBits := latexDash(row.AvgBits)
		saving := latexDash(row.Saving)

		if _, err := fmt.Fprintf(
			f,
			`%s & %s & %s & %s & %s & %s & %s & %s \\`+"\n",
			method,
			certification,
			stableFlips,
			violations,
			scoreViolations,
			usage,
			avgBits,
			saving,
		); err != nil {
			return err
		}
	}

	if _, err := fmt.Fprintln(f, `\hline`); err != nil {
		return err
	}
	if _, err := fmt.Fprintln(f, `\end{tabular}`); err != nil {
		return err
	}
	if _, err := fmt.Fprintln(f, `\end{table}`); err != nil {
		return err
	}

	return nil
}

func latexDash(value string) string {
	if strings.TrimSpace(value) == "" {
		return "-"
	}

	return latexEscape(value)
}

func latexEscape(value string) string {
	replacer := strings.NewReplacer(
		`\`, `\textbackslash{}`,
		`_`, `\_`,
		`%`, `\%`,
		`&`, `\&`,
		`#`, `\#`,
		`$`, `\$`,
		`{`, `\{`,
		`}`, `\}`,
	)

	return replacer.Replace(value)
}
