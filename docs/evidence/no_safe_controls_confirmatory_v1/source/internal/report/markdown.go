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
	fmt.Fprintf(f, "| Method | Stable Boundary Flips | Est. Error | Max Error | Bound/Max | P5 Usage | P5 Certified | P1 Usage | P1 Certified | Avg Bits |\n")
	fmt.Fprintf(f, "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")

	for _, row := range r.SummaryRows {
		fmt.Fprintf(
			f,
			"| %s | %d | %.10f | %.10f | %.2fx | %.2fx | %t | %.2fx | %t | %.2f |\n",
			row.Method,
			row.StableBoundaryFlips,
			row.EstimatedError,
			row.MaxError,
			row.BoundOverMaxError,
			row.P5Usage,
			row.P5Certified,
			row.P1Usage,
			row.P1Certified,
			row.AvgBits,
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
	fmt.Fprintf(f, "- `bound_over_max_error = estimated_error / observed_max_error`; this quantifies how conservative the sufficient bound is on this sample set.\n")
	fmt.Fprintf(f, "- `p5_usage = estimated_error / p5_budget`; values below or equal to `1.0x` satisfy the p5 certificate.\n")
	fmt.Fprintf(f, "- `p1_usage = estimated_error / p1_budget`; values below or equal to `1.0x` satisfy the p1 certificate.\n")
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
			Name:          "uniform_bits_12",
			Role:          "Uniform high-precision baseline",
			SavingRef:     "U12",
			Certification: "P5",
		},
		{
			Name:          "uniform_bits_16",
			Role:          "Uniform conservative baseline",
			SavingRef:     "U16",
			Certification: "P1",
		},
		{
			Name:          "accuracy_only_tol002_m12",
			Role:          "Accuracy-only loose tolerance",
			SavingRef:     "U12",
			Certification: "P5",
		},
		{
			Name:          "accuracy_only_tol0005_m16",
			Role:          "Accuracy-only strict tolerance",
			SavingRef:     "U16",
			Certification: "P1",
		},
		{
			Name:          "flipguard_p5_m12",
			Role:          "FlipGuard p5-certified schedule",
			SavingRef:     "U12",
			Certification: "P5",
		},
		{
			Name:          "flipguard_p1_m16",
			Role:          "FlipGuard p1-certified schedule",
			SavingRef:     "U16",
			Certification: "P1",
		},
	}

	rowByMethod := indexSummaryRows(rows)

	fmt.Fprintf(f, "## Main Comparison\n\n")
	fmt.Fprintf(f, "| Method | Role | Stable Boundary Flips | Certification | Usage | Bound/Max | Avg Bits | Saving Target | Saving |\n")
	fmt.Fprintf(f, "|---|---|---:|---|---:|---:|---:|---|---:|\n")

	for _, m := range methods {
		row, ok := rowByMethod[m.Name]
		if !ok {
			continue
		}

		fmt.Fprintf(
			f,
			"| %s | %s | %d | %s | %.2fx | %.2fx | %.2f | %s | %.2f%% |\n",
			row.Method,
			m.Role,
			row.StableBoundaryFlips,
			certificationLabel(row),
			selectedUsage(row, m.Certification),
			row.BoundOverMaxError,
			row.AvgBits,
			m.SavingRef,
			selectedSaving(row, m.SavingRef),
		)
	}

	fmt.Fprintf(f, "\n## Interpretation Notes\n\n")

	if row, ok := rowByMethod["accuracy_only_tol002_m12"]; ok {
		fmt.Fprintf(
			f,
			"- `accuracy_only_tol002_m12` uses low average precision (`%.2f` bits), but it leaves `%d` stable-boundary flip(s) and exceeds the p5 decision-margin budget by `%.2fx`.\n",
			row.AvgBits,
			row.StableBoundaryFlips,
			row.P5Usage,
		)
	}

	if row, ok := rowByMethod["accuracy_only_tol0005_m16"]; ok {
		fmt.Fprintf(
			f,
			"- `accuracy_only_tol0005_m16` can empirically achieve `%d` stable-boundary flip(s), but it exceeds the p1 decision-margin budget by `%.2fx`; therefore it should be treated as an empirical accuracy baseline, not a decision-certified schedule.\n",
			row.StableBoundaryFlips,
			row.P1Usage,
		)
	}

	if row, ok := rowByMethod["flipguard_p5_m12"]; ok {
		fmt.Fprintf(
			f,
			"- `flipguard_p5_m12` satisfies the p5 decision-margin certificate with `%.2fx` budget usage while reducing average precision by `%.2f%%` against the U12 baseline. Its sufficient bound is `%.2fx` larger than the observed maximum error.\n",
			row.P5Usage,
			row.SavingVsUniform12Pct,
			row.BoundOverMaxError,
		)
	}

	if row, ok := rowByMethod["flipguard_p1_m16"]; ok {
		fmt.Fprintf(
			f,
			"- `flipguard_p1_m16` satisfies both p5 and p1 certificates with `%.2fx` p1 budget usage while reducing average precision by `%.2f%%` against the U16 baseline. Its sufficient bound is `%.2fx` larger than the observed maximum error.\n",
			row.P1Usage,
			row.SavingVsUniform16Pct,
			row.BoundOverMaxError,
		)
	}

	fmt.Fprintf(f, "\n## Paper Claim Draft\n\n")
	fmt.Fprintf(f, "> FlipGuard reduces average precision while satisfying decision-margin certification. In the logreg_small benchmark, the p5-certified schedule uses %.2fx of the p5 budget and reduces average precision by %.2f%% compared with the U12 baseline, while the p1-certified schedule uses %.2fx of the p1 budget and reduces average precision by %.2f%% compared with the U16 baseline. The sufficient error bound is conservative by %.2fx and %.2fx over the observed maximum error for the p5 and p1 schedules, respectively.\n",
		usageFor(rowByMethod, "flipguard_p5_m12", "P5"),
		savingFor(rowByMethod, "flipguard_p5_m12", "U12"),
		usageFor(rowByMethod, "flipguard_p1_m16", "P1"),
		savingFor(rowByMethod, "flipguard_p1_m16", "U16"),
		boundOverFor(rowByMethod, "flipguard_p5_m12"),
		boundOverFor(rowByMethod, "flipguard_p1_m16"),
	)

	return nil
}

type paperMethod struct {
	Name          string
	Role          string
	SavingRef     string
	Certification string
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

func selectedUsage(row SummaryRow, certification string) float64 {
	switch certification {
	case "P5":
		return row.P5Usage
	case "P1":
		return row.P1Usage
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

func usageFor(rows map[string]SummaryRow, method string, certification string) float64 {
	row, ok := rows[method]
	if !ok {
		return 0
	}

	return selectedUsage(row, certification)
}

func boundOverFor(rows map[string]SummaryRow, method string) float64 {
	row, ok := rows[method]
	if !ok {
		return 0
	}

	return row.BoundOverMaxError
}
