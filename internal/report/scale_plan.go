package report

import (
	"encoding/csv"
	"fmt"
	"os"
	"strconv"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

// ScalePlanSummaryRow summarizes one CKKS scale plan.
type ScalePlanSummaryRow struct {
	Name string

	Policy string

	Nodes int
	High  int
	Mid   int
	Low   int

	MinLogScale float64
	MaxLogScale float64
	AvgLogScale float64
}

// NewScalePlanSummaryRow creates a compact summary row from a CKKS scale plan.
func NewScalePlanSummaryRow(name string, plan ckksbackend.ScalePlan) ScalePlanSummaryRow {
	row := ScalePlanSummaryRow{
		Name:   name,
		Policy: string(plan.Policy),
		Nodes:  len(plan.Nodes),
	}

	if len(plan.Nodes) == 0 {
		return row
	}

	minScale := plan.Nodes[0].LogScale
	maxScale := plan.Nodes[0].LogScale
	sumScale := 0.0

	for _, node := range plan.Nodes {
		switch node.Class {
		case ckksbackend.ScaleClassHigh:
			row.High++
		case ckksbackend.ScaleClassMid:
			row.Mid++
		case ckksbackend.ScaleClassLow:
			row.Low++
		}

		if node.LogScale < minScale {
			minScale = node.LogScale
		}
		if node.LogScale > maxScale {
			maxScale = node.LogScale
		}

		sumScale += node.LogScale
	}

	row.MinLogScale = minScale
	row.MaxLogScale = maxScale
	row.AvgLogScale = sumScale / float64(len(plan.Nodes))

	return row
}

// WriteScalePlanCSV writes node-level CKKS scale plan rows.
func WriteScalePlanCSV(path string, plan ckksbackend.ScalePlan) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create scale plan csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"node_id",
		"bits",
		"scale_class",
		"log_scale",
		"policy",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write scale plan header: %w", err)
	}

	for _, node := range plan.Nodes {
		record := []string{
			string(node.NodeID),
			strconv.Itoa(int(node.Bits)),
			string(node.Class),
			formatFloat(node.LogScale),
			string(plan.Policy),
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write scale plan row for %s: %w", node.NodeID, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush scale plan csv: %w", err)
	}

	return nil
}

// WriteScalePlanSummaryCSV writes scale-plan summary rows to CSV.
func WriteScalePlanSummaryCSV(path string, rows []ScalePlanSummaryRow) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create scale plan summary csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"name",
		"policy",
		"nodes",
		"high",
		"mid",
		"low",
		"min_log_scale",
		"max_log_scale",
		"avg_log_scale",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write scale plan summary header: %w", err)
	}

	for _, row := range rows {
		record := []string{
			row.Name,
			row.Policy,
			strconv.Itoa(row.Nodes),
			strconv.Itoa(row.High),
			strconv.Itoa(row.Mid),
			strconv.Itoa(row.Low),
			formatFloat(row.MinLogScale),
			formatFloat(row.MaxLogScale),
			formatFloat(row.AvgLogScale),
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write scale plan summary row for %s: %w", row.Name, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush scale plan summary csv: %w", err)
	}

	return nil
}

// WriteScalePlanSummaryMarkdown writes a compact Markdown report for CKKS scale plans.
func WriteScalePlanSummaryMarkdown(path string, rows []ScalePlanSummaryRow) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create scale plan summary markdown: %w", err)
	}
	defer f.Close()

	fmt.Fprintf(f, "# CKKS Scale Plan Summary\n\n")

	fmt.Fprintf(f, "This file summarizes how simulation-level precision schedules are mapped into CKKS scale classes.\n\n")

	fmt.Fprintf(f, "> This is a pre-Lattigo planning artifact. It does not execute CKKS ciphertext operations yet.\n\n")

	fmt.Fprintf(f, "## Summary\n\n")
	fmt.Fprintf(f, "| Name | Policy | Nodes | High | Mid | Low | Min log2(scale) | Max log2(scale) | Avg log2(scale) |\n")
	fmt.Fprintf(f, "|---|---|---:|---:|---:|---:|---:|---:|---:|\n")

	for _, row := range rows {
		fmt.Fprintf(
			f,
			"| %s | %s | %d | %d | %d | %d | %.2f | %.2f | %.2f |\n",
			row.Name,
			row.Policy,
			row.Nodes,
			row.High,
			row.Mid,
			row.Low,
			row.MinLogScale,
			row.MaxLogScale,
			row.AvgLogScale,
		)
	}

	fmt.Fprintf(f, "\n## Interpretation\n\n")
	fmt.Fprintf(f, "- `uniform_high` maps every scheduled node to the high CKKS scale class.\n")
	fmt.Fprintf(f, "- `uniform_low` maps every scheduled node to the low CKKS scale class.\n")
	fmt.Fprintf(f, "- `flipguard_grouped` maps scheduled precision bits into high, mid, and low CKKS scale classes.\n")
	fmt.Fprintf(f, "- The grouped plan is the first bridge between FlipGuard's simulation schedule and a future Lattigo backend.\n")

	return nil
}
