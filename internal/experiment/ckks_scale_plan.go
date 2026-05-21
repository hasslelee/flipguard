package experiment

import (
	"fmt"
	"path/filepath"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
	"github.com/hasslelee/flipguard/internal/runtime"
)

func exportCKKSScalePlans(outputDir string, scheduleCases []scheduleCase) error {
	if len(scheduleCases) == 0 {
		return nil
	}

	rows := make([]report.ScalePlanSummaryRow, 0, len(scheduleCases)+2)

	referenceSchedule := firstNonEmptySchedule(scheduleCases)
	if len(referenceSchedule) == 0 {
		return nil
	}

	baselinePlans := []struct {
		name string
		cfg  ckksbackend.Config
	}{
		{
			name: "uniform_high",
			cfg:  ckksbackend.UniformHighConfig(),
		},
		{
			name: "uniform_low",
			cfg:  ckksbackend.UniformLowConfig(),
		},
	}

	for _, b := range baselinePlans {
		plan, err := ckksbackend.BuildScalePlan(referenceSchedule, b.cfg)
		if err != nil {
			return fmt.Errorf("build CKKS baseline scale plan %s: %w", b.name, err)
		}

		path := filepath.Join(outputDir, fmt.Sprintf("ckks_scale_plan_%s.csv", b.name))
		if err := report.WriteScalePlanCSV(path, plan); err != nil {
			return err
		}

		rows = append(rows, report.NewScalePlanSummaryRow(b.name, plan))
	}

	for _, c := range scheduleCases {
		if c.result == nil || len(c.result.Schedule) == 0 {
			continue
		}

		cfg := ckksbackend.FlipGuardGroupedConfig()
		cfg.Name = c.name + "_grouped"

		plan, err := ckksbackend.BuildScalePlan(c.result.Schedule, cfg)
		if err != nil {
			return fmt.Errorf("build CKKS grouped scale plan %s: %w", c.name, err)
		}

		path := filepath.Join(outputDir, fmt.Sprintf("ckks_scale_plan_%s.csv", c.name))
		if err := report.WriteScalePlanCSV(path, plan); err != nil {
			return err
		}

		rows = append(rows, report.NewScalePlanSummaryRow(c.name, plan))
	}

	if err := report.WriteScalePlanSummaryCSV(
		filepath.Join(outputDir, "ckks_scale_plan_summary.csv"),
		rows,
	); err != nil {
		return err
	}

	if err := report.WriteScalePlanSummaryMarkdown(
		filepath.Join(outputDir, "ckks_scale_plan_summary.md"),
		rows,
	); err != nil {
		return err
	}

	return nil
}

func firstNonEmptySchedule(scheduleCases []scheduleCase) runtime.PrecisionSchedule {
	for _, c := range scheduleCases {
		if c.result == nil {
			continue
		}

		if len(c.result.Schedule) > 0 {
			return c.result.Schedule
		}
	}

	return nil
}
