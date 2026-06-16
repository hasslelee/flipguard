package experiment

import (
	"encoding/csv"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
)

const ckksPolicyComparisonOutputDir = "results/ckks_policy_comparison"
const logregSmallSummaryPath = "results/logreg_small/summary.csv"

// RunCKKSPolicyComparison builds a combined simulation and CKKS comparison table.
func RunCKKSPolicyComparison() error {
	simulationRows, err := loadSimulationPolicyComparisonRows(logregSmallSummaryPath)
	if err != nil {
		return fmt.Errorf("load simulation summary: %w", err)
	}

	auditSummary, auditSource, err := loadOrRunCKKSAuditSummary()
	if err != nil {
		return fmt.Errorf("load or run CKKS audit summary: %w", err)
	}

	rows := make([]report.CKKSPolicyComparisonRow, 0, len(simulationRows)+1)
	rows = append(rows, buildCKKSObservedPolicyRow(auditSummary, auditSource))
	rows = append(rows, simulationRows...)

	outputDir := CKKSResultDir(ckksPolicyComparisonOutputDir)

	if err := report.WriteCKKSPolicyComparisonCSV(
		filepath.Join(outputDir, "comparison.csv"),
		rows,
	); err != nil {
		return fmt.Errorf("write CKKS policy comparison CSV: %w", err)
	}

	fmt.Println("FlipGuard CKKS policy comparison")
	fmt.Printf("rows=%d\n", len(rows))
	fmt.Printf("ckks_audit_source=%s\n", auditSource)
	fmt.Println()

	for _, row := range rows {
		fmt.Printf(
			"source=%s method=%s certification=%s certified=%s stable_flips=%s stable_violations=%s budget_usage=%s avg_bits=%s saving_vs_u12=%s saving_vs_u16=%s\n",
			row.Source,
			row.Method,
			row.Certification,
			row.Certified,
			row.StableFlips,
			row.StableViolations,
			row.BudgetUsage,
			row.AvgBits,
			row.SavingVsU12,
			row.SavingVsU16,
		)
	}

	fmt.Println()
	fmt.Printf("Exported CKKS policy comparison files to %s/\n", outputDir)

	return nil
}

func loadOrRunCKKSAuditSummary() (ckksbackend.CKKSCertificateAuditSummary, string, error) {
	options := GetRuntimeOptions()
	auditSummaryPath := CKKSResultPath(ckksCertificateAuditOutputDir, "summary.csv")

	if options.CKKSOutputTag != "" {
		summary, err := loadCKKSAuditSummaryFromCSV(auditSummaryPath)
		if err == nil {
			if auditSummaryMatchesRuntimeOptions(summary, options) {
				return summary, auditSummaryPath, nil
			}

			fmt.Printf("Existing CKKS audit summary does not match runtime options, rerunning: %s\n", auditSummaryPath)
		} else if !errors.Is(err, os.ErrNotExist) {
			return ckksbackend.CKKSCertificateAuditSummary{}, "", err
		}
	}

	ctx, err := ckksbackend.NewDefaultContext()
	if err != nil {
		return ckksbackend.CKKSCertificateAuditSummary{}, "", fmt.Errorf("create CKKS context: %w", err)
	}

	_, auditSummary, err := ctx.RunCKKSCertificateAudit(CKKSCertificateAuditConfigFromRuntimeOptions())
	if err != nil {
		return ckksbackend.CKKSCertificateAuditSummary{}, "", fmt.Errorf("run CKKS certificate audit: %w", err)
	}

	return auditSummary, "fresh_ckks_audit_run", nil
}

func auditSummaryMatchesRuntimeOptions(summary ckksbackend.CKKSCertificateAuditSummary, options RuntimeOptions) bool {
	if summary.Points != options.CKKSPoints {
		return false
	}

	if summary.Repetitions != options.CKKSRepetitions {
		return false
	}

	if !almostEqual(summary.SafetyFactor, options.CKKSSafetyFactor, 1e-12) {
		return false
	}

	return true
}

func loadCKKSAuditSummaryFromCSV(path string) (ckksbackend.CKKSCertificateAuditSummary, error) {
	records, err := readCSVRecordsByHeader(path)
	if err != nil {
		if isPathNotFoundError(err) {
			return ckksbackend.CKKSCertificateAuditSummary{}, os.ErrNotExist
		}

		return ckksbackend.CKKSCertificateAuditSummary{}, err
	}

	if len(records) == 0 {
		return ckksbackend.CKKSCertificateAuditSummary{}, fmt.Errorf("CKKS audit summary csv has no records: %s", path)
	}

	record := records[0]

	return ckksbackend.CKKSCertificateAuditSummary{
		Points:              mustParseIntField(record, "points"),
		Repetitions:         mustParseIntField(record, "repetitions"),
		Runs:                mustParseIntField(record, "runs"),
		SafetyFactor:        mustParseFloatField(record, "safety_factor"),
		BoundaryRuns:        mustParseIntField(record, "boundary_runs"),
		StableRuns:          mustParseIntField(record, "stable_runs"),
		AmbiguousRuns:       mustParseIntField(record, "ambiguous_runs"),
		Flips:               mustParseIntField(record, "flips"),
		StableFlips:         mustParseIntField(record, "stable_flips"),
		AmbiguousFlips:      mustParseIntField(record, "ambiguous_flips"),
		CertifiedRuns:       mustParseIntField(record, "certified_runs"),
		StableCertifiedRuns: mustParseIntField(record, "stable_certified_runs"),
		StableViolations:    mustParseIntField(record, "stable_violations"),
		MinStableMargin:     mustParseFloatField(record, "min_stable_margin"),
		MaxYError:           mustParseFloatField(record, "max_y_error"),
		MeanYError:          mustParseFloatField(record, "mean_y_error"),
		MaxStableUsage:      mustParseFloatField(record, "max_stable_usage"),
		MeanStableUsage:     mustParseFloatField(record, "mean_stable_usage"),
	}, nil
}

func buildCKKSObservedPolicyRow(
	summary ckksbackend.CKKSCertificateAuditSummary,
	auditSource string,
) report.CKKSPolicyComparisonRow {
	return report.CKKSPolicyComparisonRow{
		Source:           "ckks",
		Method:           "ckks_observed_certificate",
		Role:             "Observed encrypted CKKS end-to-end boundary audit",
		Samples:          fmt.Sprintf("%d", summary.Runs),
		StableRuns:       fmt.Sprintf("%d", summary.StableRuns),
		StableFlips:      fmt.Sprintf("%d", summary.StableFlips),
		StableViolations: fmt.Sprintf("%d", summary.StableViolations),
		Certification:    fmt.Sprintf("observed_error_sf_%.2f", summary.SafetyFactor),
		Certified:        fmt.Sprintf("%t", summary.StableViolations == 0),
		BudgetUsage:      formatExperimentFloat(summary.MaxStableUsage),
		MaxError:         formatExperimentFloat(summary.MaxYError),
		EstimatedError:   "",
		AvgBits:          "",
		SavingVsU12:      "",
		SavingVsU16:      "",
		Notes:            fmt.Sprintf("Observed CKKS error is checked against safety_factor * decision margin on stable boundary samples. audit_source=%s", auditSource),
	}
}

func loadSimulationPolicyComparisonRows(path string) ([]report.CKKSPolicyComparisonRow, error) {
	records, err := readCSVRecordsByHeader(path)
	if err != nil {
		return nil, err
	}

	roles := map[string]string{
		"uniform_bits_12":           "Uniform high-precision simulation baseline",
		"uniform_bits_16":           "Uniform conservative simulation baseline",
		"accuracy_only_tol0005_m16": "Accuracy-only strict simulation baseline",
		"flipguard_p5_m12":          "FlipGuard p5-certified simulation schedule",
		"flipguard_p1_m16":          "FlipGuard p1-certified simulation schedule",
	}

	order := []string{
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

	rows := make([]report.CKKSPolicyComparisonRow, 0, len(order))

	for _, method := range order {
		record, ok := recordByMethod[method]
		if !ok {
			return nil, fmt.Errorf("method %s not found in %s", method, path)
		}

		rows = append(rows, buildSimulationPolicyRow(record, roles[method]))
	}

	return rows, nil
}

func buildSimulationPolicyRow(record map[string]string, role string) report.CKKSPolicyComparisonRow {
	p5Certified := parseBoolLike(record["p5_certified"])
	p1Certified := parseBoolLike(record["p1_certified"])

	certification := "none"
	certified := "false"
	budgetUsage := ""

	if p1Certified {
		certification = "p5+p1"
		certified = "true"
		budgetUsage = record["p1_usage"]
	} else if p5Certified {
		certification = "p5"
		certified = "true"
		budgetUsage = record["p5_usage"]
	} else {
		if record["p5_usage"] != "" {
			budgetUsage = record["p5_usage"]
		} else if record["p1_usage"] != "" {
			budgetUsage = record["p1_usage"]
		}
	}

	stableFlips := firstNonEmpty(
		record["stable_boundary_flips"],
		record["stable_b_flips"],
	)

	avgBits := record["avg_bits"]

	return report.CKKSPolicyComparisonRow{
		Source:           "simulation",
		Method:           record["method"],
		Role:             role,
		Samples:          record["samples"],
		StableRuns:       "",
		StableFlips:      stableFlips,
		StableViolations: "",
		Certification:    certification,
		Certified:        certified,
		BudgetUsage:      budgetUsage,
		MaxError:         record["max_error"],
		EstimatedError:   record["estimated_error"],
		AvgBits:          avgBits,
		SavingVsU12: firstNonEmpty(
			record["saving_vs_uniform12"],
			record["saving_vs_u12"],
			record["save_u12"],
			computedSavingFromAvgBits(avgBits, 12),
		),
		SavingVsU16: firstNonEmpty(
			record["saving_vs_uniform16"],
			record["saving_vs_u16"],
			record["save_u16"],
			computedSavingFromAvgBits(avgBits, 16),
		),
		Notes: simulationPolicyNote(record["method"]),
	}
}

func simulationPolicyNote(method string) string {
	if strings.HasPrefix(method, "flipguard") {
		return "Decision-margin-aware simulated schedule."
	}

	if strings.HasPrefix(method, "accuracy_only") {
		return "Accuracy-only simulated schedule; certification is evaluated separately."
	}

	if strings.HasPrefix(method, "uniform") {
		return "Uniform simulated precision baseline."
	}

	return "Simulation row."
}

func readCSVRecordsByHeader(path string) ([]map[string]string, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("open csv %s: %w", path, err)
	}
	defer f.Close()

	reader := csv.NewReader(f)
	reader.FieldsPerRecord = -1

	rows, err := reader.ReadAll()
	if err != nil {
		return nil, fmt.Errorf("read csv %s: %w", path, err)
	}

	if len(rows) == 0 {
		return nil, fmt.Errorf("csv %s is empty", path)
	}

	header := rows[0]
	records := make([]map[string]string, 0, len(rows)-1)

	for rowIndex, row := range rows[1:] {
		record := make(map[string]string, len(header))

		for i, name := range header {
			value := ""
			if i < len(row) {
				value = row[i]
			}
			record[name] = value
		}

		if len(record) == 0 {
			return nil, fmt.Errorf("empty record at row %d in %s", rowIndex+2, path)
		}

		records = append(records, record)
	}

	return records, nil
}

func parseBoolLike(value string) bool {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "true", "1", "yes":
		return true
	default:
		return false
	}
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if value != "" {
			return value
		}
	}

	return ""
}

func computedSavingFromAvgBits(avgBits string, baseline float64) string {
	avgBits = strings.TrimSpace(avgBits)
	if avgBits == "" || baseline == 0 {
		return ""
	}

	parsed, err := strconv.ParseFloat(avgBits, 64)
	if err != nil {
		return ""
	}

	return fmt.Sprintf("%.10f", (baseline-parsed)/baseline*100)
}

func formatExperimentFloat(value float64) string {
	return fmt.Sprintf("%.10f", value)
}

func mustParseIntField(record map[string]string, field string) int {
	value := strings.TrimSpace(record[field])
	parsed, err := strconv.Atoi(value)
	if err != nil {
		panic(fmt.Sprintf("parse int field %s=%q: %v", field, value, err))
	}

	return parsed
}

func mustParseFloatField(record map[string]string, field string) float64 {
	value := strings.TrimSpace(record[field])
	parsed, err := strconv.ParseFloat(value, 64)
	if err != nil {
		panic(fmt.Sprintf("parse float field %s=%q: %v", field, value, err))
	}

	return parsed
}

func almostEqual(a float64, b float64, tolerance float64) bool {
	if a > b {
		return a-b <= tolerance
	}

	return b-a <= tolerance
}

func isPathNotFoundError(err error) bool {
	if errors.Is(err, os.ErrNotExist) {
		return true
	}

	return strings.Contains(err.Error(), "no such file or directory")
}
