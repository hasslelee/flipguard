package ckksplanner

import (
	"math"
	"testing"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

const cnnLiteDatasetRoot = "../../datasets/vision_suite/mnist/cnn_lite_square_binary01"
const cnnLiteSourcePath = "../../results/source_datasets/mnist/mnist_784.arff.gz"

func TestBuildCNNLiteWorkloadContractAndSynthesize(t *testing.T) {
	options := DefaultPrimaryCNNLiteContractOptions()
	options.ModelPath = cnnLiteDatasetRoot + "/model.json"
	options.ValidationPath =
		cnnLiteDatasetRoot + "/configuration_validation.csv"
	options.SourcePath = cnnLiteSourcePath
	options.SplitID =
		"mnist/train_model_val_selection_test_audit_cnn_lite_v1"
	contract, err := BuildCNNLiteWorkloadContract(options)
	if err != nil {
		t.Fatalf("BuildCNNLiteWorkloadContract failed: %v", err)
	}
	if contract.ModelType != MNISTCNNLiteModelType {
		t.Fatalf("model type=%q", contract.ModelType)
	}
	if contract.Decision.ValidationSamples != 250 ||
		contract.Decision.CertifiableSamples != 250 ||
		contract.Decision.AmbiguousSamples != 0 {
		t.Fatalf(
			"unexpected decision partition: total=%d cert=%d amb=%d",
			contract.Decision.ValidationSamples,
			contract.Decision.CertifiableSamples,
			contract.Decision.AmbiguousSamples,
		)
	}
	if contract.Deployment.RescaleLevelsConsumed != 3 ||
		contract.Deployment.TerminalScaleExponent != 2 ||
		contract.Deployment.RequiredQPrimes != 5 {
		t.Fatalf(
			"unexpected scale trace: levels=%d exponent=%d q=%d",
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
			"got %d initial candidates",
			len(plan.InitialCandidates),
		)
	}
	candidate := plan.InitialCandidates[0]
	if candidate.RequiredRescaleLevels != 3 ||
		candidate.Parameters.LogN != 13 {
		t.Fatalf(
			"unexpected candidate: id=%s N=%d levels=%d",
			candidate.ID,
			candidate.Parameters.LogN,
			candidate.RequiredRescaleLevels,
		)
	}
	if candidate.Security.FinalAdmission != "PASS" {
		t.Fatalf(
			"candidate security admission=%s reason=%s",
			candidate.Security.FinalAdmission,
			candidate.Security.AdmissionReason,
		)
	}
}

func TestCNNLiteAuditContractUsesOfficialTestRows(t *testing.T) {
	options := DefaultPrimaryCNNLiteContractOptions()
	options.ModelPath = cnnLiteDatasetRoot + "/model.json"
	options.ValidationPath = cnnLiteDatasetRoot + "/locked_audit_test.csv"
	options.SourcePath = cnnLiteSourcePath
	options.SplitID = "mnist/cnn_lite/locked_audit"
	contract, err := BuildCNNLiteWorkloadContract(options)
	if err != nil {
		t.Fatalf("BuildCNNLiteWorkloadContract failed: %v", err)
	}
	if contract.Decision.ValidationSamples != 250 ||
		contract.Decision.CertifiableSamples != 250 {
		t.Fatalf(
			"unexpected audit decision partition: %+v",
			contract.Decision,
		)
	}
}

func TestCNNLiteInitialCandidateOneRowSmoke(t *testing.T) {
	options := DefaultPrimaryCNNLiteContractOptions()
	options.ModelPath = cnnLiteDatasetRoot + "/model.json"
	options.ValidationPath =
		cnnLiteDatasetRoot + "/configuration_validation.csv"
	options.SourcePath = cnnLiteSourcePath
	options.SplitID = "mnist/cnn_lite/smoke"
	contract, err := BuildCNNLiteWorkloadContract(options)
	if err != nil {
		t.Fatalf("BuildCNNLiteWorkloadContract failed: %v", err)
	}
	plan, err := Synthesize(
		contract,
		DefaultPrimarySynthesisPolicy(),
	)
	if err != nil {
		t.Fatalf("Synthesize failed: %v", err)
	}
	candidate := plan.InitialCandidates[0]
	profile, err := candidate.Profile()
	if err != nil {
		t.Fatalf("candidate.Profile failed: %v", err)
	}
	context, err := ckksbackend.NewContextFromProfile(profile)
	if err != nil {
		t.Fatalf("NewContextFromProfile failed: %v", err)
	}
	records, err := context.RunCKKSCNNLiteInference(
		ckksbackend.CKKSCNNLiteConfig{
			ModelPath: options.ModelPath,
			DataPath:  options.ValidationPath,
			MaxRows:   1,
		},
	)
	if err != nil {
		t.Fatalf("RunCKKSCNNLiteInference failed: %v", err)
	}
	if len(records) != 1 {
		t.Fatalf("got %d records, want 1", len(records))
	}
	record := records[0]
	if record.DecisionFlip {
		t.Fatal("initial synthesized candidate flipped smoke decision")
	}
	if record.FinalDegree != 1 || record.FinalLevel < 0 {
		t.Fatalf(
			"invalid final ciphertext degree=%d level=%d",
			record.FinalDegree,
			record.FinalLevel,
		)
	}
	margin := math.Abs(
		record.PlainScore - contract.Decision.Threshold,
	)
	if record.AbsError >=
		contract.Decision.SafetyFactor*margin {
		t.Fatalf(
			"smoke row violates budget: error=%g margin=%g",
			record.AbsError,
			margin,
		)
	}
}
