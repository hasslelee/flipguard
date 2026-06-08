package experiment

import (
	"fmt"
	"path/filepath"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
)

const ckksCubicProbeOutputDir = "results/ckks_cubic_probe"

// RunCKKSCubicProbe runs the CKKS encrypted cubic probe.
func RunCKKSCubicProbe() error {
	ctx, err := ckksbackend.NewDefaultContext()
	if err != nil {
		return fmt.Errorf("create CKKS context: %w", err)
	}

	results, err := ctx.RunCubicProbe()
	if err != nil {
		return fmt.Errorf("run CKKS cubic probe: %w", err)
	}

	fmt.Println("FlipGuard CKKS cubic probe")
	fmt.Println("target: z3 = z * z * z")
	fmt.Println("method: relinearize after each ciphertext-ciphertext multiplication, no rescale")
	fmt.Println()

	for i, result := range results {
		fmt.Printf(
			"case=%d z=%.6f plain_z3=%.10f raw_z3=%.10f scaled_z3=%.10f selected_z3=%.10f mode=%s abs_error=%.10f z_degree=%d z2_degree=%d z3_degree=%d initial_level=%d z2_level=%d z3_level=%d\n",
			i,
			result.Z,
			result.PlainZ3,
			result.RawDecodedZ3,
			result.ScaledDecodedZ3,
			result.SelectedZ3,
			result.SelectedInterpretation,
			result.SelectedAbsError,
			result.ZDegree,
			result.Z2Degree,
			result.Z3Degree,
			result.InitialLevel,
			result.Z2Level,
			result.Z3Level,
		)
	}

	if err := report.WriteCKKSCubicProbeCSV(
		filepath.Join(ckksCubicProbeOutputDir, "summary.csv"),
		results,
	); err != nil {
		return fmt.Errorf("write CKKS cubic probe CSV: %w", err)
	}

	if err := report.WriteCKKSCubicProbeMarkdown(
		filepath.Join(ckksCubicProbeOutputDir, "report.md"),
		results,
	); err != nil {
		return fmt.Errorf("write CKKS cubic probe Markdown: %w", err)
	}

	fmt.Println()
	fmt.Printf("Exported CKKS cubic probe files to %s/\n", ckksCubicProbeOutputDir)

	return nil
}
