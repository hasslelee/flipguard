package main

import (
	"encoding/csv"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strconv"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/ckksplanner"
)

type smokeResult struct {
	SchemaVersion string                                    `json:"schema_version"`
	Purpose       string                                    `json:"purpose"`
	ModelPath     string                                    `json:"model_path"`
	SmokeDataPath string                                    `json:"smoke_data_path"`
	Contract      ckksplanner.WorkloadContract              `json:"full_validation_contract"`
	Candidate     ckksplanner.SynthesizedCandidate          `json:"direct_initial_candidate"`
	Summary       ckksbackend.JournalMNISTMulticlassSummary `json:"smoke_summary"`
}

func main() {
	model := flag.String("model", "", "frozen model")
	validation := flag.String("validation", "", "full frozen configuration-validation CSV")
	smoke := flag.String("smoke-data", "", "deterministic smoke subset")
	source := flag.String("source", "", "byte-pinned MNIST source")
	output := flag.String("out", "", "exclusive result path")
	flag.Parse()
	if *model == "" || *validation == "" || *smoke == "" || *source == "" || *output == "" {
		fatalf("model, validation, smoke-data, source, and out are required")
	}
	options := ckksplanner.DefaultJournalMNISTMulticlassContractOptions()
	options.ModelPath = *model
	options.ValidationPath = *validation
	options.SourcePath = *source
	options.ExpectedRole = "configuration_validation"
	options.SplitID = "mnist_sha_rank_validation_500_v1"
	contract, _, err := ckksplanner.BuildJournalMNISTMulticlassContract(options)
	if err != nil {
		fatalf("build full-validation contract: %v", err)
	}
	plan, err := ckksplanner.Synthesize(contract, ckksplanner.DefaultPrimarySynthesisPolicy())
	if err != nil {
		fatalf("synthesize direct candidate: %v", err)
	}
	candidate := plan.InitialCandidates[0]
	profile, err := candidate.Profile()
	if err != nil {
		fatalf("materialize candidate: %v", err)
	}
	context, err := ckksbackend.NewContextFromProfile(profile)
	if err != nil {
		fatalf("create context: %v", err)
	}
	selectedRowIDs, err := loadSmokeRowIDs(*smoke)
	if err != nil {
		fatalf("load smoke row identities: %v", err)
	}
	_, summary, err := context.RunCKKSJournalMNISTMulticlassInference(
		ckksbackend.JournalMNISTMulticlassConfig{
			ModelPath:      *model,
			DataPath:       *validation,
			Role:           "configuration_validation",
			SelectedRowIDs: selectedRowIDs,
		},
	)
	if err != nil {
		fatalf("execute smoke: %v", err)
	}
	result := smokeResult{
		SchemaVersion: "flipguard_v17_multiclass_smoke_v1",
		Purpose:       "SMOKE_ONLY_NOT_CLAIM_BEARING",
		ModelPath:     *model, SmokeDataPath: *smoke,
		Contract: contract, Candidate: candidate, Summary: summary,
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
	fmt.Printf("multiclass_smoke=%s rows=%d flips=%d output=%s\n", summary.ModelType, summary.EvaluatedRows, summary.ArgmaxFlips, *output)
}

func loadSmokeRowIDs(path string) ([]int, error) {
	handle, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer handle.Close()
	reader := csv.NewReader(handle)
	header, err := reader.Read()
	if err != nil {
		return nil, err
	}
	rowIDColumn := -1
	for index, field := range header {
		if field == "row_id" {
			rowIDColumn = index
			break
		}
	}
	if rowIDColumn < 0 {
		return nil, fmt.Errorf("smoke CSV has no row_id")
	}
	rows, err := reader.ReadAll()
	if err != nil {
		return nil, err
	}
	ids := make([]int, 0, len(rows))
	for _, row := range rows {
		value, err := strconv.Atoi(row[rowIDColumn])
		if err != nil {
			return nil, err
		}
		ids = append(ids, value)
	}
	return ids, nil
}

func fatalf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "flipguard-v17-multiclass-smoke: "+format+"\n", args...)
	os.Exit(1)
}
