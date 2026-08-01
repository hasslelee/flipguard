package ckksplanner

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/hasslelee/flipguard/internal/tuner"
)

func TestBuildTabularWorkloadContractDerivesBoundInputs(t *testing.T) {
	modelPath, validationPath := writeLinearFixture(t, false)

	options := DefaultTabularContractOptions()
	options.ModelPath = modelPath
	options.ValidationPath = validationPath
	options.SplitID = "split_seed_0"
	options.MarginFloor = 0.01

	contract, err := BuildTabularWorkloadContract(options)
	if err != nil {
		t.Fatalf("build contract: %v", err)
	}

	if contract.WorkloadID != "split_seed_0/toy/linear_poly3" {
		t.Fatalf("unexpected workload ID %q", contract.WorkloadID)
	}
	if contract.Graph.MultiplicativeDepth != 2 {
		t.Fatalf(
			"expected graph depth 2, got %d",
			contract.Graph.MultiplicativeDepth,
		)
	}
	if contract.Graph.RescaleOps != 2 {
		t.Fatalf(
			"expected 2 rescale levels, got %d",
			contract.Graph.RescaleOps,
		)
	}
	if contract.Deployment.RescaleLevelsConsumed != 6 ||
		contract.Deployment.TerminalScaleExponent != 1 ||
		contract.Deployment.RequiredQPrimes != 7 {
		t.Fatalf(
			"unexpected Lattigo scale demand: %+v",
			contract.Deployment,
		)
	}
	if contract.Decision.ValidationSamples != 3 ||
		contract.Decision.CertifiableSamples != 2 ||
		contract.Decision.AmbiguousSamples != 1 {
		t.Fatalf(
			"unexpected decision partition: %+v",
			contract.Decision,
		)
	}
	if contract.Decision.ProtectedMargin <= 0.09 {
		t.Fatalf(
			"unexpected protected margin %.12g",
			contract.Decision.ProtectedMargin,
		)
	}
	if contract.Calibration.AggregateSensitivity <= 0 {
		t.Fatalf(
			"unexpected aggregate sensitivity %.12g",
			contract.Calibration.AggregateSensitivity,
		)
	}
	if contract.Deployment.ValidationKeyRepeats != 1 {
		t.Fatalf(
			"unexpected default key repeats: %+v",
			contract.Deployment,
		)
	}
	if !strings.HasPrefix(
		contract.ModelArtifact.SHA256,
		"sha256:",
	) {
		t.Fatalf(
			"unexpected model digest %q",
			contract.ModelArtifact.SHA256,
		)
	}
	if err := contract.Validate(); err != nil {
		t.Fatalf("derived contract did not validate: %v", err)
	}
}

func TestBuildTabularWorkloadContractRejectsScoreMismatch(t *testing.T) {
	modelPath, validationPath := writeLinearFixture(t, true)

	options := DefaultTabularContractOptions()
	options.ModelPath = modelPath
	options.ValidationPath = validationPath
	options.SplitID = "split_seed_0"

	_, err := BuildTabularWorkloadContract(options)
	if err == nil || !strings.Contains(err.Error(), "does not match model graph") {
		t.Fatalf("expected score mismatch, got %v", err)
	}
}

func TestLattigoScaleTraceDistinguishesMLPOutputForms(t *testing.T) {
	base := tabularModelArtifact{
		DatasetID: "toy",
		ModelID:   "mlp",
		ModelType: "mlp_square_linear_score",
		InputDim:  1,
		ScaledModelForCKKS: tabularScaledModel{
			HiddenWeights: [][]float64{{0.5}},
			HiddenBias:    []float64{0.1},
			OutputWeights: []float64{0.2},
			OutputBias:    0.05,
		},
		PolynomialScore: tabularPolynomialScore{
			Formula:           "0.5 + 0.197*z",
			DecisionThreshold: 0.5,
		},
	}

	linearGraph, err := buildTabularIRGraph(base)
	if err != nil {
		t.Fatalf("build linear-score MLP graph: %v", err)
	}
	linearDemand, err := analyzeLattigoRescaleDemand(linearGraph)
	if err != nil {
		t.Fatalf("trace linear-score MLP: %v", err)
	}
	if linearDemand.LevelsConsumed != 3 ||
		linearDemand.ScaleExponent != 3 ||
		linearDemand.RequiredQPrimes != 6 {
		t.Fatalf(
			"unexpected linear-score MLP demand: %+v",
			linearDemand,
		)
	}

	base.ModelType = "mlp_square_poly3"
	base.PolynomialScore.Formula =
		"0.5 + 0.197*z - 0.004*z^3"
	polyGraph, err := buildTabularIRGraph(base)
	if err != nil {
		t.Fatalf("build poly3-score MLP graph: %v", err)
	}
	polyDemand, err := analyzeLattigoRescaleDemand(polyGraph)
	if err != nil {
		t.Fatalf("trace poly3-score MLP: %v", err)
	}
	if polyDemand.LevelsConsumed != 9 ||
		polyDemand.ScaleExponent != 1 ||
		polyDemand.RequiredQPrimes != 10 {
		t.Fatalf(
			"unexpected poly3-score MLP demand: %+v",
			polyDemand,
		)
	}
}

func TestMulticlassDecisionContractIsBackwardCompatibleExtension(t *testing.T) {
	contract := validContractFixture()
	contract.Decision = DecisionStabilityContract{}
	contract.MulticlassDecision = &MulticlassDecisionStabilityContract{
		SchemaVersion:        "decision_integrity_contract_v2",
		ClassCount:           10,
		TieBreak:             "lowest_class_index",
		BoundMode:            "uniform_per_logit_v1",
		MarginFloor:          0.001,
		MarginUtilizationCap: 0.5,
		ProtectedTopTwoGap:   0.2,
		PerLogitErrorBudget:  0.05,
		ValidationDigest:     "sha256:" + strings.Repeat("a", 64),
		ValidationSamples:    500,
		CertifiableSamples:   499,
		AmbiguousSamples:     1,
	}
	contract.Deployment.RequiredSlots = 500
	contract.Deployment.PackingStrategy = FeatureCiphertextSampleSlotsV1
	if err := contract.Validate(); err != nil {
		t.Fatal(err)
	}
	contract.MulticlassDecision.PerLogitErrorBudget = 0.051
	if err := contract.Validate(); err == nil {
		t.Fatal("expected uniform per-logit budget rejection")
	}
}

func TestWorkloadContractRejectsNonReproducibleDigest(t *testing.T) {
	contract := validContractFixture()
	contract.ModelArtifact.SHA256 = "not-a-digest"

	err := contract.Validate()
	if err == nil || !strings.Contains(err.Error(), "sha256 prefix") {
		t.Fatalf("expected digest validation error, got %v", err)
	}
}

func TestWorkloadContractRequiresSourceReplayVerification(t *testing.T) {
	contract := validContractFixture()
	contract.InputMaterialization = &InputMaterializationContract{
		SchemaVersion:        TabularValidationMaterializationSchemaV2,
		SourceFeatureSpace:   string(TabularDataSpaceRaw),
		PreprocessingMethod:  TabularPreprocessingSelectedStandardizationV1,
		SourceReplayVerified: true,
	}
	err := contract.Validate()
	if err == nil || !strings.Contains(
		err.Error(),
		"requires bound source data",
	) {
		t.Fatalf("expected missing source binding rejection, got %v", err)
	}

	contract = validContractFixture()
	contract.SourceData = &ArtifactBinding{
		Path:   "raw.csv",
		SHA256: contract.ModelArtifact.SHA256,
	}
	contract.InputMaterialization = &InputMaterializationContract{
		SchemaVersion:       TabularValidationMaterializationSchemaV2,
		SourceFeatureSpace:  string(TabularDataSpaceRaw),
		PreprocessingMethod: TabularPreprocessingSelectedStandardizationV1,
	}
	err = contract.Validate()
	if err == nil || !strings.Contains(
		err.Error(),
		"requires verified input materialization replay",
	) {
		t.Fatalf("expected missing replay verification rejection, got %v", err)
	}
}

func writeLinearFixture(
	t *testing.T,
	scoreMismatch bool,
) (string, string) {
	t.Helper()

	root := t.TempDir()
	modelPath := filepath.Join(root, "model.json")
	validationPath := filepath.Join(root, "validation.csv")

	model := `{
  "dataset_id": "toy",
  "dataset_name": "Toy",
  "model_id": "linear_poly3",
  "model_type": "linear_poly3",
  "input_dim": 1,
  "scaled_model_for_ckks": {
    "weights": [0.5],
    "bias": 0.0
  },
  "polynomial_score": {
    "formula": "0.5 + 0.197*z - 0.004*z^3",
    "decision_threshold": 0.5
  }
}`

	scoreNegative := linearFixtureScore(-1)
	scoreBoundary := linearFixtureScore(0)
	scorePositive := linearFixtureScore(1)
	if scoreMismatch {
		scorePositive += 0.1
	}

	validation := fmt.Sprintf(
		"row_id,label,raw_logit,scaled_logit,polynomial_score,plaintext_decision,x_0\n"+
			"0,0,0,0,%.15g,false,-1\n"+
			"1,1,0,0,%.15g,true,0\n"+
			"2,1,0,0,%.15g,true,1\n",
		scoreNegative,
		scoreBoundary,
		scorePositive,
	)

	if err := os.WriteFile(modelPath, []byte(model), 0o600); err != nil {
		t.Fatalf("write model fixture: %v", err)
	}
	if err := os.WriteFile(
		validationPath,
		[]byte(validation),
		0o600,
	); err != nil {
		t.Fatalf("write validation fixture: %v", err)
	}

	return modelPath, validationPath
}

func linearFixtureScore(x float64) float64 {
	z := 0.5 * x
	return 0.5 + 0.197*z - 0.004*z*z*z
}

func validContractFixture() WorkloadContract {
	digest := "sha256:" +
		strings.Repeat("0", 64)

	return WorkloadContract{
		SchemaVersion: WorkloadContractSchemaVersion,

		WorkloadID: "split/toy/model",
		DatasetID:  "toy",
		ModelID:    "model",
		ModelType:  "mlp_square_linear_score",
		SplitID:    "split",

		ModelArtifact: ArtifactBinding{
			Path:   "model.json",
			SHA256: digest,
		},
		ValidationData: ArtifactBinding{
			Path:   "validation.csv",
			SHA256: digest,
		},

		Graph: tuner.GraphSummary{
			MultiplicativeDepth: 1,
			AddOps:              2,
			MulOps:              3,
			RescaleOps:          1,
		},
		Decision: DecisionStabilityContract{
			Threshold:          0.5,
			MarginFloor:        0.001,
			SafetyFactor:       0.5,
			ProtectedMargin:    0.1,
			OutputErrorBudget:  0.05,
			ValidationDigest:   digest,
			ValidationSamples:  10,
			CertifiableSamples: 9,
			AmbiguousSamples:   1,
		},
		Calibration: NumericalCalibration{
			MaxInputAbs:           2,
			MaxPlaintextOutputAbs: 1,
			AggregateSensitivity:  4,
			SensitivityMethod:     EmpiricalIntervalDAGSensitivityV1,
			CalibrationScope:      "observed_validation_artifact:" + digest,
		},
		Deployment: DeploymentContract{
			SecurityBits:         128,
			RequiredSlots:        1,
			MaxEncryptedTrials:   4,
			ValidationKeyRepeats: 1,
			PackingStrategy:      ScalarReplicatedPackingV1,
			AllowedPaths: []tuner.ExecutionPath{
				tuner.PathRescale,
			},
			ScaleTraceMethod:      LattigoRescaleScaleTraceV1,
			RescaleLevelsConsumed: 3,
			TerminalScaleExponent: 3,
			RequiredQPrimes:       6,
		},
	}
}
