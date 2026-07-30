package ckksplanner

import (
	"path/filepath"
	"testing"
)

func TestBuildHarrisWorkloadContractAndSynthesize(t *testing.T) {
	root := filepath.Join(
		"..",
		"..",
		"datasets",
		"vision_suite",
		"bsds500",
		"harris_corner_response",
	)
	options := DefaultPrimaryHarrisContractOptions()
	options.ModelPath = filepath.Join(root, "model.json")
	options.ValidationPath = filepath.Join(
		root,
		"configuration_validation.csv",
	)
	options.SourceArchivePath = filepath.Join(
		"..",
		"..",
		"results",
		"source_datasets",
		"bsds500",
		"BSR_bsds500.tgz",
	)
	options.SplitID =
		"bsds500/train_threshold_val_selection_test_audit_harris_v1"
	contract, err := BuildHarrisWorkloadContract(options)
	if err != nil {
		t.Fatalf("BuildHarrisWorkloadContract failed: %v", err)
	}
	if contract.Graph.MultiplicativeDepth != 2 {
		t.Fatalf(
			"multiplicative depth=%d, want 2",
			contract.Graph.MultiplicativeDepth,
		)
	}
	if contract.Decision.ValidationSamples != 200 ||
		contract.Decision.CertifiableSamples != 200 ||
		contract.Decision.AmbiguousSamples != 0 {
		t.Fatalf(
			"validation partition=%d/%d/%d",
			contract.Decision.ValidationSamples,
			contract.Decision.CertifiableSamples,
			contract.Decision.AmbiguousSamples,
		)
	}
	if contract.Deployment.RescaleLevelsConsumed != 4 ||
		contract.Deployment.TerminalScaleExponent != 2 ||
		contract.Deployment.RequiredQPrimes != 6 {
		t.Fatalf(
			"scale demand levels=%d exponent=%d q=%d",
			contract.Deployment.RescaleLevelsConsumed,
			contract.Deployment.TerminalScaleExponent,
			contract.Deployment.RequiredQPrimes,
		)
	}
	plan, err := Synthesize(
		contract,
		DefaultPrimarySynthesisPolicy(),
	)
	if err != nil {
		t.Fatalf("Synthesize failed: %v", err)
	}
	if len(plan.InitialCandidates) != 1 {
		t.Fatalf(
			"initial candidate count=%d",
			len(plan.InitialCandidates),
		)
	}
	candidate := plan.InitialCandidates[0]
	if candidate.RequiredRescaleLevels != 4 ||
		len(candidate.Parameters.LogQ) != 6 {
		t.Fatalf(
			"candidate demand levels=%d q=%v",
			candidate.RequiredRescaleLevels,
			candidate.Parameters.LogQ,
		)
	}
}
