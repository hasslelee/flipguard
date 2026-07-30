package experiment

import (
	"fmt"
	"path/filepath"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
)

const ckksBiasProbeOutputDir = "results/ckks_bias_probe"

// RunCKKSBiasProbe runs the CKKS bias-addition probe.
func RunCKKSBiasProbe() error {
	ctx, err := ckksbackend.NewDefaultContext()
	if err != nil {
		return fmt.Errorf("create CKKS context: %w", err)
	}

	pairs, err := ctx.RunBiasAdditionProbe()
	if err != nil {
		return fmt.Errorf("run CKKS bias addition probe: %w", err)
	}

	fmt.Println("FlipGuard CKKS bias addition probe")
	fmt.Println("target: compare scalar-bias AddNew and plaintext-bias AddNew")
	fmt.Println()

	for i, pair := range pairs {
		printBiasProbeResult(i, pair.ScalarBias)
		printBiasProbeResult(i, pair.PlaintextBias)
	}

	if err := report.WriteCKKSBiasProbeCSV(
		filepath.Join(ckksBiasProbeOutputDir, "summary.csv"),
		pairs,
	); err != nil {
		return fmt.Errorf("write CKKS bias probe CSV: %w", err)
	}

	if err := report.WriteCKKSBiasProbeMarkdown(
		filepath.Join(ckksBiasProbeOutputDir, "report.md"),
		pairs,
	); err != nil {
		return fmt.Errorf("write CKKS bias probe Markdown: %w", err)
	}

	fmt.Println()
	fmt.Printf("Exported CKKS bias probe files to %s/\n", ckksBiasProbeOutputDir)

	return nil
}

func printBiasProbeResult(index int, result ckksbackend.BiasAdditionProbeResult) {
	fmt.Printf(
		"case=%d method=%s input=%.6f scalar=%.6f bias=%.6f plain=%.10f raw=%.10f scaled=%.10f selected=%.10f mode=%s abs_error=%.10f initial_level=%d final_level=%d\n",
		index,
		result.Method,
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
