package experiment

import (
	"fmt"
	"path/filepath"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
)

const ckksMulProbeOutputDir = "results/ckks_mul_probe"

// RunCKKSMulProbe runs the CKKS ciphertext-ciphertext multiplication probe.
func RunCKKSMulProbe() error {
	ctx, err := ckksbackend.NewDefaultContext()
	if err != nil {
		return fmt.Errorf("create CKKS context: %w", err)
	}

	results, err := ctx.RunMultiplicationProbe()
	if err != nil {
		return fmt.Errorf("run CKKS multiplication probe: %w", err)
	}

	fmt.Println("FlipGuard CKKS multiplication probe")
	fmt.Println("target: z2 = z * z")
	fmt.Println("mode: MulNew without relinearization and without rescaling")
	fmt.Println()

	for i, result := range results {
		fmt.Printf(
			"case=%d z=%.6f plain_z2=%.10f raw_z2=%.10f scaled_z2=%.10f selected_z2=%.10f mode=%s abs_error=%.10f input_degree=%d output_degree=%d initial_level=%d final_level=%d\n",
			i,
			result.Z,
			result.PlainZ2,
			result.RawDecodedZ2,
			result.ScaledDecodedZ2,
			result.SelectedZ2,
			result.SelectedInterpretation,
			result.SelectedAbsError,
			result.InputDegree,
			result.OutputDegree,
			result.InitialLevel,
			result.FinalLevel,
		)
	}

	if err := report.WriteCKKSMulProbeCSV(
		filepath.Join(ckksMulProbeOutputDir, "summary.csv"),
		results,
	); err != nil {
		return fmt.Errorf("write CKKS multiplication probe CSV: %w", err)
	}

	if err := report.WriteCKKSMulProbeMarkdown(
		filepath.Join(ckksMulProbeOutputDir, "report.md"),
		results,
	); err != nil {
		return fmt.Errorf("write CKKS multiplication probe Markdown: %w", err)
	}

	fmt.Println()
	fmt.Printf("Exported CKKS multiplication probe files to %s/\n", ckksMulProbeOutputDir)

	return nil
}
