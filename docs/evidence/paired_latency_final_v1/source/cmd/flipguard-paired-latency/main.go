package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/ckksplanner"
)

type artifactBinding struct {
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
}

type runtimeEnvironment struct {
	GOOS       string `json:"goos"`
	GOARCH     string `json:"goarch"`
	GoVersion  string `json:"go_version"`
	LogicalCPU int    `json:"logical_cpu"`
}

type pairedLatencyOutput struct {
	SchemaVersion int `json:"schema_version"`

	WorkloadID     string `json:"workload_id"`
	SourceRevision string `json:"source_revision"`
	SourceDigest   string `json:"source_digest"`

	SelectionResult artifactBinding `json:"selection_result"`
	ModelArtifact   artifactBinding `json:"model_artifact"`
	ValidationData  artifactBinding `json:"validation_data"`

	CatalogCandidate   string `json:"catalog_candidate"`
	ReferenceCandidate string `json:"reference_candidate"`

	Environment runtimeEnvironment                     `json:"environment"`
	Measurement ckksbackend.PairedTabularLatencyResult `json:"measurement"`
}

func main() {
	if err := run(os.Args[1:], os.Stdout); errors.Is(err, flag.ErrHelp) {
		return
	} else if err != nil {
		fmt.Fprintf(os.Stderr, "flipguard-paired-latency: %v\n", err)
		os.Exit(1)
	}
}

func run(args []string, stdout io.Writer) error {
	flags := flag.NewFlagSet(
		"flipguard-paired-latency",
		flag.ContinueOnError,
	)
	flags.SetOutput(stdout)

	selectionResultPath := flags.String(
		"selection-result",
		"",
		"direct autotune result JSON containing the frozen selected literal",
	)
	catalogCandidate := flags.String(
		"catalog-candidate",
		"",
		"bounded-oracle candidate ID in PROFILE__PATH form",
	)
	referenceCandidate := flags.String(
		"reference-candidate",
		"",
		"reference candidate ID in PROFILE__PATH form",
	)
	outputPath := flags.String(
		"out",
		"",
		"output JSON path",
	)
	sourceRevision := flags.String(
		"source-revision",
		"working-tree",
		"source revision label recorded in the result",
	)
	sourceDigest := flags.String(
		"source-digest",
		"",
		"aggregate SHA-256 binding the measurement source files",
	)
	warmupRuns := flags.Int(
		"warmup-runs",
		1,
		"complete selected-row warm-up passes per arm",
	)
	measurementRuns := flags.Int(
		"measurement-runs",
		3,
		"complete selected-row measurement passes per arm",
	)
	maxRows := flags.Int(
		"max-rows",
		8,
		"evenly spaced validation rows per pass; zero selects all rows",
	)

	if err := flags.Parse(args); err != nil {
		return err
	}
	if flags.NArg() != 0 {
		return fmt.Errorf(
			"unexpected positional arguments: %v",
			flags.Args(),
		)
	}
	required := []struct {
		name  string
		value string
	}{
		{"--selection-result", *selectionResultPath},
		{"--catalog-candidate", *catalogCandidate},
		{"--reference-candidate", *referenceCandidate},
		{"--out", *outputPath},
		{"--source-revision", *sourceRevision},
		{"--source-digest", *sourceDigest},
	}
	for _, item := range required {
		if strings.TrimSpace(item.value) == "" {
			return fmt.Errorf("%s is required", item.name)
		}
	}

	selectionBytes, err := os.ReadFile(*selectionResultPath)
	if err != nil {
		return fmt.Errorf("read selection result: %w", err)
	}
	var selection ckksplanner.AdaptiveAutotuneResult
	if err := json.Unmarshal(selectionBytes, &selection); err != nil {
		return fmt.Errorf("parse selection result: %w", err)
	}
	selected, err := ckksplanner.ValidateSelectedAutotuneResult(
		selection,
	)
	if err != nil {
		return fmt.Errorf("validate selection result: %w", err)
	}

	directProfile, err := selected.Profile()
	if err != nil {
		return fmt.Errorf("load direct selected literal: %w", err)
	}
	catalogArm, err := builtInArm(
		"catalog",
		"bounded_catalog_oracle",
		*catalogCandidate,
	)
	if err != nil {
		return err
	}
	referenceArm, err := builtInArm(
		"reference",
		"ckks_reference",
		*referenceCandidate,
	)
	if err != nil {
		return err
	}

	contract := selection.Plan.Contract
	modelBinding, err := bindArtifact(contract.ModelArtifact.Path)
	if err != nil {
		return err
	}
	if modelBinding.SHA256 != contract.ModelArtifact.SHA256 {
		return fmt.Errorf(
			"model artifact digest changed: got %s expected %s",
			modelBinding.SHA256,
			contract.ModelArtifact.SHA256,
		)
	}
	validationBinding, err := bindArtifact(
		contract.ValidationData.Path,
	)
	if err != nil {
		return err
	}
	if validationBinding.SHA256 != contract.ValidationData.SHA256 {
		return fmt.Errorf(
			"validation artifact digest changed: got %s expected %s",
			validationBinding.SHA256,
			contract.ValidationData.SHA256,
		)
	}

	result, err := ckksbackend.RunPairedTabularLatency(
		ckksbackend.PairedTabularLatencyConfig{
			ModelPath:   contract.ModelArtifact.Path,
			TestPath:    contract.ValidationData.Path,
			DatasetID:   contract.DatasetID,
			ModelID:     contract.ModelID,
			MaxRows:     *maxRows,
			WarmupRuns:  *warmupRuns,
			MeasureRuns: *measurementRuns,
			Arms: []ckksbackend.PairedTabularLatencyArm{
				{
					ID:             "direct",
					Role:           "direct_synthesis",
					CandidateID:    selected.ID,
					Profile:        directProfile,
					EvaluationMode: string(selected.Path),
				},
				catalogArm,
				referenceArm,
			},
		},
	)
	if err != nil {
		return err
	}

	output := pairedLatencyOutput{
		SchemaVersion:  1,
		WorkloadID:     contract.WorkloadID,
		SourceRevision: strings.TrimSpace(*sourceRevision),
		SourceDigest:   strings.TrimSpace(*sourceDigest),
		SelectionResult: artifactBinding{
			Path:   *selectionResultPath,
			SHA256: digestBytes(selectionBytes),
		},
		ModelArtifact:      modelBinding,
		ValidationData:     validationBinding,
		CatalogCandidate:   *catalogCandidate,
		ReferenceCandidate: *referenceCandidate,
		Environment: runtimeEnvironment{
			GOOS:       runtime.GOOS,
			GOARCH:     runtime.GOARCH,
			GoVersion:  runtime.Version(),
			LogicalCPU: runtime.NumCPU(),
		},
		Measurement: result,
	}
	encoded, err := json.MarshalIndent(output, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal paired latency result: %w", err)
	}
	encoded = append(encoded, '\n')

	if err := os.MkdirAll(
		filepath.Dir(*outputPath),
		0o755,
	); err != nil {
		return fmt.Errorf("create output directory: %w", err)
	}
	if err := os.WriteFile(*outputPath, encoded, 0o644); err != nil {
		return fmt.Errorf("write paired latency result: %w", err)
	}

	fmt.Fprintf(
		stdout,
		"paired_latency=%s workload=%s records=%d rows=%d runs=%d\n",
		*outputPath,
		contract.WorkloadID,
		len(result.Records),
		result.Protocol.SelectedRows,
		result.Protocol.MeasurementRuns,
	)
	return nil
}

func builtInArm(
	id string,
	role string,
	candidateID string,
) (ckksbackend.PairedTabularLatencyArm, error) {
	profileName, mode, err := parseCatalogCandidate(candidateID)
	if err != nil {
		return ckksbackend.PairedTabularLatencyArm{}, err
	}
	profile, err := ckksbackend.FindCKKSProfile(profileName)
	if err != nil {
		return ckksbackend.PairedTabularLatencyArm{}, fmt.Errorf(
			"candidate %s profile: %w",
			candidateID,
			err,
		)
	}
	return ckksbackend.PairedTabularLatencyArm{
		ID:             id,
		Role:           role,
		CandidateID:    candidateID,
		Profile:        profile,
		EvaluationMode: mode,
	}, nil
}

func parseCatalogCandidate(candidateID string) (
	string,
	string,
	error,
) {
	const separator = "__"
	index := strings.LastIndex(candidateID, separator)
	if index <= 0 || index+len(separator) >= len(candidateID) {
		return "", "", fmt.Errorf(
			"invalid catalog candidate ID %q",
			candidateID,
		)
	}
	profileName := candidateID[:index]
	switch candidateID[index+len(separator):] {
	case "rescale_aware":
		return profileName, ckksbackend.CKKSEvaluationModeRescale, nil
	case "baseline_non_rescale":
		return profileName, ckksbackend.CKKSEvaluationModeNaive, nil
	default:
		return "", "", fmt.Errorf(
			"unsupported catalog candidate path in %q",
			candidateID,
		)
	}
}

func bindArtifact(path string) (artifactBinding, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return artifactBinding{}, fmt.Errorf(
			"read artifact %s: %w",
			path,
			err,
		)
	}
	return artifactBinding{
		Path:   path,
		SHA256: digestBytes(data),
	}, nil
}

func digestBytes(data []byte) string {
	sum := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(sum[:])
}
