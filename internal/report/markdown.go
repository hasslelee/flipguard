package report

import (
	"fmt"
	"os"

	"github.com/hasslelee/flipguard/internal/scheduler"
)

// ScheduleSummary summarizes one schedule for Markdown reporting.
type ScheduleSummary struct {
	Name string

	Budget          float64
	BudgetSource    string
	EstimatedError  float64
	Feasible        bool
	ProtectedMargin float64

	AvgBits float64
	MinBits int
	MaxBits int
	Nodes   int
}

// NewScheduleSummary creates a compact schedule summary from a scheduler result.
func NewScheduleSummary(name string, result *scheduler.FlipGuardResult, protectedMargin float64) ScheduleSummary {
	s := ScheduleSummary{
		Name:            name,
		Budget:          result.Budget,
		BudgetSource:    result.BudgetSource,
		EstimatedError:  result.EstimatedError,
		Feasible:        result.Feasible,
		ProtectedMargin: protectedMargin,
		AvgBits:         AverageBits(result.Schedule),
		MinBits:         0,
		MaxBits:         0,
		Nodes:           len(result.Nodes),
	}

	if len(result.Nodes) == 0 {
		return s
	}

	minBits := 1 << 30
	maxBits := -1

	for _, n := range result.Nodes {
		bits := int(n.Bits)
		if bits < minBits {
			minBits = bits
		}
		if bits > maxBits {
			maxBits = bits
		}
	}

	s.MinBits = minBits
	s.MaxBits = maxBits

	return s
}

// MarkdownReport contains the experiment summary rendered to report.md.
type MarkdownReport struct {
	Title string

	Threshold   float64
	Gamma       float64
	MarginFloor float64
	Samples     int

	SummaryRows       []SummaryRow
	ScheduleSummaries []ScheduleSummary
}

// WriteMarkdownReport writes a compact Markdown report for paper/table drafting.
func WriteMarkdownReport(path string, r MarkdownReport) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create markdown report: %w", err)
	}
	defer f.Close()

	title := r.Title
	if title == "" {
		title = "FlipGuard Experiment Report"
	}

	fmt.Fprintf(f, "# %s\n\n", title)

	fmt.Fprintf(f, "## Experiment Setting\n\n")
	fmt.Fprintf(f, "- Threshold: `%.6f`\n", r.Threshold)
	fmt.Fprintf(f, "- Boundary gamma: `%.6f`\n", r.Gamma)
	fmt.Fprintf(f, "- Ambiguous margin floor: `%.6f`\n", r.MarginFloor)
	fmt.Fprintf(f, "- Samples: `%d`\n\n", r.Samples)

	fmt.Fprintf(f, "## Summary\n\n")
	fmt.Fprintf(f, "| Method | Stable Boundary Flips | Est. Error | P5 Certified | P1 Certified | Avg Bits | Saving vs U12 | Saving vs U16 |\n")
	fmt.Fprintf(f, "|---|---:|---:|---:|---:|---:|---:|---:|\n")

	for _, row := range r.SummaryRows {
		fmt.Fprintf(
			f,
			"| %s | %d | %.10f | %t | %t | %.2f | %.2f%% | %.2f%% |\n",
			row.Method,
			row.StableBoundaryFlips,
			row.EstimatedError,
			row.P5Certified,
			row.P1Certified,
			row.AvgBits,
			row.SavingVsUniform12Pct,
			row.SavingVsUniform16Pct,
		)
	}

	fmt.Fprintf(f, "\n## Schedule Summary\n\n")
	fmt.Fprintf(f, "| Schedule | Feasible | Budget Source | Budget | Estimated Error | Protected Margin | Avg Bits | Min Bits | Max Bits |\n")
	fmt.Fprintf(f, "|---|---:|---|---:|---:|---:|---:|---:|---:|\n")

	for _, s := range r.ScheduleSummaries {
		fmt.Fprintf(
			f,
			"| %s | %t | %s | %.10f | %.10f | %.10f | %.2f | %d | %d |\n",
			s.Name,
			s.Feasible,
			s.BudgetSource,
			s.Budget,
			s.EstimatedError,
			s.ProtectedMargin,
			s.AvgBits,
			s.MinBits,
			s.MaxBits,
		)
	}

	fmt.Fprintf(f, "\n## Key Observations\n\n")
	fmt.Fprintf(f, "- `stable_boundary_flips` excludes ambiguous samples with margin less than or equal to the configured margin floor.\n")
	fmt.Fprintf(f, "- `estimated_error` is computed from the node-wise schedule and output sensitivity bound.\n")
	fmt.Fprintf(f, "- `p5_certified` means `estimated_error <= 0.5 * p5_margin`.\n")
	fmt.Fprintf(f, "- `p1_certified` means `estimated_error <= 0.5 * p1_margin`.\n")
	fmt.Fprintf(f, "- `saving_vs_uniform12_pct` and `saving_vs_uniform16_pct` compare average scheduled bits against uniform 12-bit and uniform 16-bit baselines.\n")
	fmt.Fprintf(f, "- Accuracy-only schedules can empirically avoid flips, but they are not necessarily certified under decision-margin budgets.\n")

	return nil
}

// WritePaperTableMarkdown writes a focused, paper-ready result table.
// It keeps only the representative baselines and FlipGuard variants that are
// useful for the main evaluation table.
func WritePaperTableMarkdown(path string, title string, rows []SummaryRow) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create paper table markdown: %w", err)
	}
	defer f.Close()

	if title == "" {
		title = "Paper-Ready FlipGuard Result Table"
	}

	fmt.Fprintf(f, "# %s\n\n", title)

	methods := []paperMethod{
		{
			Name:      "uniform_bits_12",
			Role:      "Uniform high-precision baseline",
			Reference: "U12",
		},
		{
			Name:      "uniform_bits_16",
			Role:      "Uniform conservative baseline",
			Reference: "U16",
		},
		{
			Name:      "accuracy_only_tol002_m12",
			Role:      "Accuracy-only loose tolerance",
			Reference: "U12",
		},
		{
			Name:      "accuracy_only_tol0005_m16",
			Role:      "Accuracy-only strict tolerance",
			Reference: "U16",
		},
		{
			Name:      "flipguard_p5_m12",
			Role:      "FlipGuard p5-certified schedule",
			Reference: "U12",
		},
		{
			Name:      "flipguard_p1_m16",
			Role:      "FlipGuard p1-certified schedule",
			Reference: "U16",
		},
	}

	rowByMethod := indexSummaryRows(rows)

	fmt.Fprintf(f, "## Main Comparison\n\n")
	fmt.Fprintf(f, "| Method | Role | Stable Boundary Flips | Certification | Avg Bits | Reference | Saving |\n")
	fmt.Fprintf(f, "|---|---|---:|---|---:|---|---:|\n")

	for _, m := range methods {
		row, ok := rowByMethod[m.Name]
		if !ok {
			continue
		}

		fmt.Fprintf(
			f,
			"| %s | %s | %d | %s | %.2f | %s | %.2f%% |\n",
			row.Method,
			m.Role,
			row.StableBoundaryFlips,
			certificationLabel(row),
			row.AvgBits,
			m.Reference,
			selectedSaving(row, m.Reference),
		)
	}

	fmt.Fprintf(f, "\n## Interpretation Notes\n\n")

	if row, ok := rowByMethod["accuracy_only_tol002_m12"]; ok {
		fmt.Fprintf(
			f,
			"- `accuracy_only_tol002_m12` uses low average precision (`%.2f` bits), but it leaves `%d` stable-boundary flip(s) and does not satisfy the decision-margin certificate.\n",
			row.AvgBits,
			row.StableBoundaryFlips,
		)
	}

	if row, ok := rowByMethod["accuracy_only_tol0005_m16"]; ok {
		fmt.Fprintf(
			f,
			"- `accuracy_only_tol0005_m16` can empirically achieve `%d` stable-boundary flip(s), but its certification status is `%s`; therefore it should be treated as an empirical accuracy baseline, not a decision-certified schedule.\n",
			row.StableBoundaryFlips,
			certificationLabel(row),
		)
	}

	if row, ok := rowByMethod["flipguard_p5_m12"]; ok {
		fmt.Fprintf(
			f,
			"- `flipguard_p5_m12` satisfies the p5 decision-margin certificate while reducing average precision by `%.2f%%` against the U12 baseline.\n",
			row.SavingVsUniform12Pct,
		)
	}

	if row, ok := rowByMethod["flipguard_p1_m16"]; ok {
		fmt.Fprintf(
			f,
			"- `flipguard_p1_m16` satisfies both p5 and p1 certificates while reducing average precision by `%.2f%%` against the U16 baseline.\n",
			row.SavingVsUniform16Pct,
		)
	}

	fmt.Fprintf(f, "\n## Paper Claim Draft\n\n")
	fmt.Fprintf(f, "> FlipGuard reduces average precision while satisfying decision-margin certification. In the logreg_small benchmark, the p5-certified schedule reduces average precision by %.2f%% compared with the U12 baseline, and the p1-certified schedule reduces average precision by %.2f%% compared with the U16 baseline.\n",
		savingFor(rowByMethod, "flipguard_p5_m12", "U12"),
		savingFor(rowByMethod, "flipguard_p1_m16", "U16"),
	)

	return nil
}

type paperMethod struct {
	Name      string
	Role      string
	Reference string
}

func indexSummaryRows(rows []SummaryRow) map[string]SummaryRow {
	indexed := make(map[string]SummaryRow, len(rows))

	for _, row := range rows {
		indexed[row.Method] = row
	}

	return indexed
}

func certificationLabel(row SummaryRow) string {
	if row.P5Certified && row.P1Certified {
		return "p5+p1"
	}

	if row.P5Certified {
		return "p5"
	}

	return "none"
}

func selectedSaving(row SummaryRow, reference string) float64 {
	switch reference {
	case "U12":
		return row.SavingVsUniform12Pct
	case "U16":
		return row.SavingVsUniform16Pct
	default:
		return 0
	}
}

func savingFor(rows map[string]SummaryRow, method string, reference string) float64 {
	row, ok := rows[method]
	if !ok {
		return 0
	}

	return selectedSaving(row, reference)
}
