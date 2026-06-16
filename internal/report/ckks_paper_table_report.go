package report

import (
	"encoding/csv"
	"fmt"
	"os"
	"strings"
)

// CKKSPaperTableRow records one compact paper table row.
type CKKSPaperTableRow struct {
	Method        string
	Evaluation    string
	Certification string
	StableFlips   string
	Violations    string
	Usage         string
	MaxError      string
	AvgBits       string
	Saving        string
}

// WriteCKKSPaperTableCSV writes compact paper-ready CSV rows.
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
		"violations",
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

// WriteCKKSPaperTableLaTeX writes compact paper-ready LaTeX rows.
func WriteCKKSPaperTableLaTeX(path string, rows []CKKSPaperTableRow) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS paper table latex: %w", err)
	}
	defer f.Close()

	fmt.Fprintln(f, "\\begin{table}[t]")
	fmt.Fprintln(f, "\\centering")
	fmt.Fprintln(f, "\\caption{CKKS observed certificate and simulated precision policy comparison.}")
	fmt.Fprintln(f, "\\label{tab:ckks-policy-comparison}")
	fmt.Fprintln(f, "\\begin{tabular}{llrrrrr}")
	fmt.Fprintln(f, "\\hline")
	fmt.Fprintln(f, "Method & Cert. & Stable flips & Viol. & Usage & Avg. bits & Saving \\\\")
	fmt.Fprintln(f, "\\hline")

	for _, row := range rows {
		fmt.Fprintf(
			f,
			"%s & %s & %s & %s & %s & %s & %s \\\\\n",
			escapeLaTeX(row.Method),
			escapeLaTeX(row.Certification),
			emptyAsDash(row.StableFlips),
			emptyAsDash(row.Violations),
			emptyAsDash(row.Usage),
			emptyAsDash(row.AvgBits),
			emptyAsDash(row.Saving),
		)
	}

	fmt.Fprintln(f, "\\hline")
	fmt.Fprintln(f, "\\end{tabular}")
	fmt.Fprintln(f, "\\end{table}")

	return nil
}

func escapeLaTeX(value string) string {
	replacements := map[string]string{
		"_": "\\_",
		"%": "\\%",
		"&": "\\&",
	}

	out := value
	for old, replacement := range replacements {
		out = strings.ReplaceAll(out, old, replacement)
	}

	return out
}

func emptyAsDash(value string) string {
	if strings.TrimSpace(value) == "" {
		return "-"
	}

	return escapeLaTeX(value)
}
