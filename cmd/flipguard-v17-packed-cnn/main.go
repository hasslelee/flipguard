package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"github.com/hasslelee/flipguard/internal/ckksplanner"
)

func main() {
	model := flag.String("model", "", "frozen CNN-lite model artifact")
	data := flag.String("data", "", "configuration-selection CSV")
	source := flag.String("source", "", "byte-pinned MNIST source")
	splitID := flag.String("split-id", "", "stable split identity")
	output := flag.String("out", "", "exclusive output result")
	flag.Parse()
	if *model == "" || *data == "" || *source == "" || *splitID == "" || *output == "" {
		fatalf("model, data, source, split-id, and out are required")
	}
	options := ckksplanner.DefaultPrimaryCNNLiteContractOptions()
	options.ModelPath = *model
	options.ValidationPath = *data
	options.SourcePath = *source
	options.SplitID = *splitID
	contract, err := ckksplanner.BuildPackedCNNLiteWorkloadContract(options)
	if err != nil {
		fatalf("build packed contract: %v", err)
	}
	plan, err := ckksplanner.Synthesize(contract, ckksplanner.DefaultPrimarySynthesisPolicy())
	if err != nil {
		fatalf("synthesize packed plan: %v", err)
	}
	result, err := ckksplanner.RunAdaptivePackedCNNLiteAutotune(plan)
	if err != nil {
		fatalf("run packed autotune: %v", err)
	}
	encoded, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		fatalf("encode result: %v", err)
	}
	encoded = append(encoded, '\n')
	handle, err := os.OpenFile(*output, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o644)
	if err != nil {
		fatalf("create output: %v", err)
	}
	if _, err := handle.Write(encoded); err != nil {
		handle.Close()
		fatalf("write output: %v", err)
	}
	if err := handle.Close(); err != nil {
		fatalf("close output: %v", err)
	}
	fmt.Printf("packed_cnn_lite=%s trials=%d key_runs=%d output=%s\n", result.Outcome, result.TrialsUsed, result.EncryptedKeyRuns, *output)
}

func fatalf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "flipguard-v17-packed-cnn: "+format+"\n", args...)
	os.Exit(1)
}
