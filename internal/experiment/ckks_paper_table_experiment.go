package experiment

import (
	"fmt"
	"math"
	"path/filepath"
	"strconv"

	"github.com/hasslelee/flipguard/internal/report"
)

const ckksPaperTableOutputDir = "results/ckks_paper_table"
const ckksPolicyComparisonBaseDir = "results/ckks_policy_comparison"

// RunCKKSPaperTable exports compact paper-ready comparison tables.
func RunCKKSPaperTable() error {
	comparisonPath := CKKSResultPath(ckksPolicyComparisonBaseDir, "comparison.csv")

	comparisonRecords, err := readCSVRecordsByHeader(comparisonPath)
	if err != nil {
		return fmt.Errorf("read policy comparison: %w", err)
	}

	rows, err := buildCKKSPaperTableRows(comparisonRecords)
	if err != nil {
		return fmt.Errorf("build CKKS paper table rows: %w", err)
	}

	outputDir := CKKSResultDir(ckksPaperTableOutputDir)

	if err := report.WriteCKKSPaperTableCSV(
		filepath.Join(outputDir, "table.csv"),
		rows,
	); err != nil {
		return fmt.Errorf("write CKKS paper table CSV: %w", err)
	}

	if err := report.WriteCKKSPaperTableLaTeX(
		filepath.Join(outputDir, "table.tex"),
		rows,
	); err != nil {
		return fmt.Errorf("write CKKS paper table LaTeX: %w", err)
	}

	fmt.Println("FlipGuard CKKS paper table export")
	fmt.Printf("rows=%d\n", len(rows))
	fmt.Println()

	for _, row := range rows {
		fmt.Printf(
			"method=%s certification=%s stable_flips=%s violations=%s usage=%s avg_bits=%s saving=%s\n",
			row.Method,
			row.Certification,
			row.StableFlips,
			row.Violations,
			row.Usage,
			row.AvgBits,
			row.Saving,
		)
	}

	fmt.Println()
	fmt.Printf("Read CKKS policy comparison from %s\n", comparisonPath)
	fmt.Printf("Exported CKKS paper table files to %s/\n", outputDir)

	return nil
}

func buildCKKSPaperTableRows(records []map[string]string) ([]report.CKKSPaperTableRow, error) {
	order := []string{
		"ckks_observed_certificate",
		"uniform_bits_12",
		"uniform_bits_16",
		"accuracy_only_tol0005_m16",
		"flipguard_p5_m12",
		"flipguard_p1_m16",
	}

	recordByMethod := make(map[string]map[string]string)
	for _, record := range records {
		method := record["method"]
		if method != "" {
			recordByMethod[method] = record
		}
	}

	rows := make([]report.CKKSPaperTableRow, 0, len(order))

	for _, method := range order {
		record, ok := recordByMethod[method]
		if !ok {
			return nil, fmt.Errorf("method %s not found in policy comparison", method)
		}

		rows = append(rows, buildCKKSPaperTableRow(record))
	}

	return rows, nil
}

func buildCKKSPaperTableRow(record map[string]string) report.CKKSPaperTableRow {
	method := record["method"]
	saving := ""

	switch method {
	case "flipguard_p5_m12":
		saving = percentString(record["saving_vs_u12"])
	case "flipguard_p1_m16":
		saving = percentString(record["saving_vs_u16"])
	case "accuracy_only_tol0005_m16":
		saving = percentString(record["saving_vs_u16"])
	case "uniform_bits_12", "uniform_bits_16":
		saving = "0.00%"
	}

	violations := record["stable_violations"]
	if violations == "" && record["source"] == "simulation" {
		violations = "-"
	}

	avgBits := decimalString(record["avg_bits"], 2)
	usage := adaptiveFloatString(record["budget_usage"], 4)
	maxError := scientificString(record["max_error"])

	return report.CKKSPaperTableRow{
		Method:        method,
		Evaluation:    record["source"],
		Certification: record["certification"],
		StableFlips:   record["stable_flips"],
		Violations:    violations,
		Usage:         usage,
		MaxError:      maxError,
		AvgBits:       avgBits,
		Saving:        saving,
	}
}

func percentString(value string) string {
	if value == "" {
		return ""
	}

	parsed, err := strconv.ParseFloat(value, 64)
	if err != nil {
		return value
	}

	return fmt.Sprintf("%.2f%%", parsed)
}

func decimalString(value string, digits int) string {
	if value == "" {
		return ""
	}

	parsed, err := strconv.ParseFloat(value, 64)
	if err != nil {
		return value
	}

	return fmt.Sprintf("%.*f", digits, parsed)
}

func adaptiveFloatString(value string, digits int) string {
	if value == "" {
		return ""
	}

	parsed, err := strconv.ParseFloat(value, 64)
	if err != nil {
		return value
	}

	absValue := math.Abs(parsed)
	if absValue > 0 && absValue < 0.0001 {
		return fmt.Sprintf("%.2e", parsed)
	}

	return fmt.Sprintf("%.*f", digits, parsed)
}

func scientificString(value string) string {
	if value == "" {
		return ""
	}

	parsed, err := strconv.ParseFloat(value, 64)
	if err != nil {
		return value
	}

	return fmt.Sprintf("%.2e", parsed)
}
