package experiment

import (
	"fmt"
	"path/filepath"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
)

const ckksScaleProbeOutputDir = "results/ckks_scale_probe"

// RunCKKSScaleProbe runs the CKKS scalar scale semantics probe.
func RunCKKSScaleProbe() error {
	ctx, err := ckksbackend.NewDefaultContext()
	if err != nil {
		return fmt.Errorf("create CKKS context: %w", err)
	}

	results, err := ctx.RunScalarScaleProbe()
	if err != nil {
		return fmt.Errorf("run scalar scale probe: %w", err)
	}

	fmt.Println("FlipGuard CKKS scalar scale probe")
	fmt.Println("target: y = scalar * input + bias")
	fmt.Println()

	for i, result := range results {
		fmt.Printf(
			"case=%d input=%.6f scalar=%.6f bias=%.6f plain=%.10f raw=%.10f scaled=%.10f selected=%.10f mode=%s abs_error=%.10f initial_level=%d final_level=%d\n",
			i,
			result.Input,
			result.Scalar,
			result.Bias,
			result.PlainValue,
			result.RawDecodedValue,
			result.ScaledDecodedValue,
			result.SelectedValue,
			result.SelectedInterpretation,
			result.SelectedAbsError,
			result.InitialLevel,
			result.FinalLevel,
		)
	}

	if err := report.WriteCKKSScaleProbeCSV(
		filepath.Join(ckksScaleProbeOutputDir, "summary.csv"),
		results,
	); err != nil {
		return fmt.Errorf("write CKKS scale probe CSV: %w", err)
	}

	if err := report.WriteCKKSScaleProbeMarkdown(
		filepath.Join(ckksScaleProbeOutputDir, "report.md"),
		results,
	); err != nil {
		return fmt.Errorf("write CKKS scale probe Markdown: %w", err)
	}

	fmt.Println()
	fmt.Printf("Exported CKKS scale probe files to %s/\n", ckksScaleProbeOutputDir)

	return nil
}
