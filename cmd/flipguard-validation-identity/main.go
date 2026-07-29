//go:build validationidentity

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"github.com/hasslelee/flipguard/internal/ckksplanner"
)

func main() {
	modelPath := flag.String("model", "", "model artifact JSON")
	validationPath := flag.String(
		"validation",
		"",
		"validation CSV",
	)
	datasetID := flag.String("dataset-id", "", "dataset identifier")
	modelID := flag.String("model-id", "", "model identifier")
	splitID := flag.String("split-id", "", "split identifier")
	partitionRole := flag.String(
		"partition-role",
		"",
		"development or confirmatory partition role",
	)
	marginFloor := flag.Float64(
		"margin-floor",
		0.001,
		"decision margin floor",
	)
	outputPath := flag.String("output", "", "optional output JSON")
	flag.Parse()

	identity, err := ckksplanner.ComputeValidationSemanticIdentity(
		ckksplanner.ValidationSemanticIdentityOptions{
			ModelPath:      *modelPath,
			ValidationPath: *validationPath,
			DatasetID:      *datasetID,
			ModelID:        *modelID,
			SplitID:        *splitID,
			PartitionRole:  *partitionRole,
			MarginFloor:    *marginFloor,
		},
	)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	encoded, err := json.MarshalIndent(identity, "", "  ")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	encoded = append(encoded, '\n')
	if *outputPath == "" {
		_, _ = os.Stdout.Write(encoded)
		return
	}
	if err := os.WriteFile(*outputPath, encoded, 0o644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
