package providergate

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/ckksplanner"
	"github.com/hasslelee/flipguard/internal/tuner"
)

func TestProviderKindsBindDeterministically(t *testing.T) {
	contract := validContractFixture()
	plan, err := ckksplanner.Synthesize(
		contract,
		ckksplanner.DefaultSynthesisPolicy(),
	)
	if err != nil {
		t.Fatalf("synthesize fixture: %v", err)
	}
	literal := plan.InitialCandidates[0].Parameters

	for _, kind := range []string{
		ProviderKindManual,
		ProviderKindBoundedCatalog,
		ProviderKindExternalAutotuner,
		ProviderKindDirectSynthesizer,
	} {
		t.Run(kind, func(t *testing.T) {
			request := ProviderCandidateRequest{
				SchemaVersion: ProviderCandidateRequestSchemaVersion,
				ProviderKind:  kind,
				ProviderID:    "fixture-provider-v1",
				Path:          plan.InitialCandidates[0].Path,
				Parameters:    literal,
			}
			path := writeProviderRequest(t, request)
			first, err := LoadAndBindProviderCandidate(contract, path)
			if err != nil {
				t.Fatalf("first bind: %v", err)
			}
			second, err := LoadAndBindProviderCandidate(contract, path)
			if err != nil {
				t.Fatalf("second bind: %v", err)
			}
			if first.Candidate.ID != second.Candidate.ID {
				t.Fatalf(
					"candidate ID is not deterministic: %s != %s",
					first.Candidate.ID,
					second.Candidate.ID,
				)
			}
			if first.Candidate.Security.FinalAdmission !=
				ckksplanner.SecurityAdmissionPass {
				t.Fatalf(
					"fixture candidate not admitted: %+v",
					first.Candidate.Security,
				)
			}
			if err := ValidateBoundProviderCandidate(
				contract,
				first,
			); err != nil {
				t.Fatalf("validate bound candidate: %v", err)
			}
		})
	}
}

func TestProviderIdentityBindsProviderAndSourceBytes(t *testing.T) {
	contract := validContractFixture()
	plan, err := ckksplanner.Synthesize(
		contract,
		ckksplanner.DefaultSynthesisPolicy(),
	)
	if err != nil {
		t.Fatalf("synthesize fixture: %v", err)
	}
	request := ProviderCandidateRequest{
		SchemaVersion: ProviderCandidateRequestSchemaVersion,
		ProviderKind:  ProviderKindExternalAutotuner,
		ProviderID:    "external-a",
		Path:          plan.InitialCandidates[0].Path,
		Parameters:    plan.InitialCandidates[0].Parameters,
	}
	firstPath := writeProviderRequest(t, request)
	first, err := LoadAndBindProviderCandidate(contract, firstPath)
	if err != nil {
		t.Fatalf("bind first: %v", err)
	}

	request.ProviderID = "external-b"
	secondPath := writeProviderRequest(t, request)
	second, err := LoadAndBindProviderCandidate(contract, secondPath)
	if err != nil {
		t.Fatalf("bind second: %v", err)
	}
	if first.Candidate.ID == second.Candidate.ID {
		t.Fatal("provider ID change did not change candidate identity")
	}

	data, err := os.ReadFile(firstPath)
	if err != nil {
		t.Fatalf("read provider request: %v", err)
	}
	if err := os.WriteFile(firstPath, append(data, '\n'), 0o600); err != nil {
		t.Fatalf("mutate provider request: %v", err)
	}
	if err := ValidateBoundProviderCandidate(contract, first); err == nil ||
		!strings.Contains(err.Error(), "digest mismatch") {
		t.Fatalf("expected source mutation failure, got %v", err)
	}
}

func TestBoundProviderCandidateRejectsContractAndPolicyMutation(t *testing.T) {
	contract := validContractFixture()
	plan, err := ckksplanner.Synthesize(
		contract,
		ckksplanner.DefaultSynthesisPolicy(),
	)
	if err != nil {
		t.Fatalf("synthesize fixture: %v", err)
	}
	request := ProviderCandidateRequest{
		SchemaVersion: ProviderCandidateRequestSchemaVersion,
		ProviderKind:  ProviderKindExternalAutotuner,
		ProviderID:    "external-v1",
		Path:          plan.InitialCandidates[0].Path,
		Parameters:    plan.InitialCandidates[0].Parameters,
	}
	path := writeProviderRequest(t, request)
	bound, err := LoadAndBindProviderCandidate(contract, path)
	if err != nil {
		t.Fatalf("bind provider candidate: %v", err)
	}

	mutatedContract := contract
	mutatedContract.WorkloadID += "_mutated"
	if err := ValidateBoundProviderCandidate(
		mutatedContract,
		bound,
	); err == nil || !strings.Contains(err.Error(), "metadata mismatch") {
		t.Fatalf("expected contract-binding failure, got %v", err)
	}

	mutatedPolicy := bound
	mutatedPolicy.SecurityPolicyDigest = digestBytes([]byte("other policy"))
	if err := ValidateBoundProviderCandidate(
		contract,
		mutatedPolicy,
	); err == nil || !strings.Contains(err.Error(), "metadata mismatch") {
		t.Fatalf("expected policy-binding failure, got %v", err)
	}
}

func TestProviderRequestRejectsUnknownJSONField(t *testing.T) {
	path := filepath.Join(t.TempDir(), "candidate.json")
	data := []byte(`{
	  "schema_version": 1,
	  "provider_kind": "manual",
	  "provider_id": "manual-v1",
	  "path": "rescale",
	  "parameters": {
	    "log_n": 13,
	    "log_q": [45, 40, 40],
	    "log_p": [45],
	    "log_default_scale": 40
	  },
	  "untrusted_security": "PASS"
	}`)
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatalf("write request: %v", err)
	}
	if _, _, err := LoadProviderCandidateRequest(path); err == nil ||
		!strings.Contains(err.Error(), "unknown field") {
		t.Fatalf("expected unknown-field failure, got %v", err)
	}
}

func TestProviderRequestRejectsTrailingJSONValue(t *testing.T) {
	path := filepath.Join(t.TempDir(), "candidate.json")
	data := []byte(`{
	  "schema_version": 1,
	  "provider_kind": "manual",
	  "provider_id": "manual-v1",
	  "path": "rescale",
	  "parameters": {
	    "log_n": 13,
	    "log_q": [45, 40, 40],
	    "log_p": [45],
	    "log_default_scale": 40
	  }
	}
	{"second": "value"}`)
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatalf("write request: %v", err)
	}
	if _, _, err := LoadProviderCandidateRequest(path); err == nil ||
		!strings.Contains(err.Error(), "trailing JSON") {
		t.Fatalf("expected trailing-value failure, got %v", err)
	}
}

func TestProviderBindingRejectsSecurityV2InadmissibleLiteral(t *testing.T) {
	contract := validContractFixture()
	request := ProviderCandidateRequest{
		SchemaVersion: ProviderCandidateRequestSchemaVersion,
		ProviderKind:  ProviderKindManual,
		ProviderID:    "inadmissible-v1",
		Path:          contract.Deployment.AllowedPaths[0],
		Parameters: ckksplanner.CKKSParameterLiteralSpec{
			LogN:            12,
			LogQ:            []int{50, 50},
			LogP:            []int{50},
			LogDefaultScale: 40,
		},
	}
	source := ckksplanner.ArtifactBinding{
		Path:   "candidate.json",
		SHA256: digestBytes([]byte("candidate")),
	}
	if _, err := BindProviderCandidate(
		contract,
		request,
		source,
	); err == nil || !strings.Contains(err.Error(), "inadmissible") {
		t.Fatalf("expected Security V2 rejection, got %v", err)
	}
}

func TestProviderBindingRejectsInsufficientSlotsAndLevels(t *testing.T) {
	contract := validContractFixture()
	plan, err := ckksplanner.Synthesize(
		contract,
		ckksplanner.DefaultSynthesisPolicy(),
	)
	if err != nil {
		t.Fatalf("synthesize fixture: %v", err)
	}
	source := ckksplanner.ArtifactBinding{
		Path:   "candidate.json",
		SHA256: digestBytes([]byte("candidate")),
	}
	request := ProviderCandidateRequest{
		SchemaVersion: ProviderCandidateRequestSchemaVersion,
		ProviderKind:  ProviderKindManual,
		ProviderID:    "capacity-v1",
		Path:          plan.InitialCandidates[0].Path,
		Parameters:    plan.InitialCandidates[0].Parameters,
	}

	slotContract := contract
	slotContract.Deployment.RequiredSlots =
		1 << request.Parameters.LogN
	if _, err := BindProviderCandidate(
		slotContract,
		request,
		source,
	); err == nil || !strings.Contains(err.Error(), "slots") {
		t.Fatalf("expected slot-capacity failure, got %v", err)
	}

	if contract.Deployment.RequiredQPrimes < 2 {
		t.Fatalf(
			"fixture unexpectedly requires fewer than two Q primes: %d",
			contract.Deployment.RequiredQPrimes,
		)
	}
	request.Parameters.LogQ = request.Parameters.LogQ[:1]
	if _, err := BindProviderCandidate(
		contract,
		request,
		source,
	); err == nil || !strings.Contains(err.Error(), "Q primes") {
		t.Fatalf("expected Q-chain failure, got %v", err)
	}
}

func TestValidateProviderCandidateGateResultRejectsLedgerMutation(
	t *testing.T,
) {
	contract := validContractFixture()
	plan, err := ckksplanner.Synthesize(
		contract,
		ckksplanner.DefaultSynthesisPolicy(),
	)
	if err != nil {
		t.Fatalf("synthesize fixture: %v", err)
	}
	request := ProviderCandidateRequest{
		SchemaVersion: ProviderCandidateRequestSchemaVersion,
		ProviderKind:  ProviderKindManual,
		ProviderID:    "manual-v1",
		Path:          plan.InitialCandidates[0].Path,
		Parameters:    plan.InitialCandidates[0].Parameters,
	}
	path := writeProviderRequest(t, request)
	bound, err := LoadAndBindProviderCandidate(contract, path)
	if err != nil {
		t.Fatalf("bind provider candidate: %v", err)
	}
	selected := bound.Candidate
	result := ProviderCandidateGateResult{
		SchemaVersion:      ProviderCandidateGateSchemaVersion,
		ValidationContract: contract,
		BoundCandidate:     bound,
		Outcome:            ProviderGateOutcomeSelected,
		Reason:             "fixture SAFE",
		TrialsUsed:         1,
		EncryptedKeyRuns:   1,
		Trial: ckksplanner.TabularTrialResult{
			TrialIndex:          1,
			Candidate:           bound.Candidate,
			Status:              certify.StatusSafe,
			KeyRepeatsRequested: 1,
			KeyRepeatsCompleted: 1,
		},
		Selected: &selected,
	}
	if err := ValidateProviderCandidateGateResult(result); err != nil {
		t.Fatalf("validate provider gate fixture: %v", err)
	}

	result.EncryptedKeyRuns = 2
	if err := ValidateProviderCandidateGateResult(result); err == nil ||
		!strings.Contains(err.Error(), "ledger mismatch") {
		t.Fatalf("expected ledger mutation failure, got %v", err)
	}
}

func TestLoadProviderCandidateGateResultRejectsUnknownJSONField(
	t *testing.T,
) {
	path := filepath.Join(t.TempDir(), "selection.json")
	if err := os.WriteFile(
		path,
		[]byte(`{"schema_version":1,"unexpected":true}`),
		0o600,
	); err != nil {
		t.Fatalf("write provider gate result: %v", err)
	}
	if _, _, err := LoadProviderCandidateGateResult(path); err == nil ||
		!strings.Contains(err.Error(), "unknown field") {
		t.Fatalf("expected unknown-field failure, got %v", err)
	}
}

func writeProviderRequest(
	t *testing.T,
	request ProviderCandidateRequest,
) string {
	t.Helper()
	data, err := json.MarshalIndent(request, "", "  ")
	if err != nil {
		t.Fatalf("marshal provider request: %v", err)
	}
	data = append(data, '\n')
	path := filepath.Join(
		t.TempDir(),
		request.ProviderKind+"-candidate.json",
	)
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatalf("write provider request: %v", err)
	}
	return path
}

func validContractFixture() ckksplanner.WorkloadContract {
	digest := "sha256:" + strings.Repeat("0", 64)
	return ckksplanner.WorkloadContract{
		SchemaVersion: ckksplanner.WorkloadContractSchemaVersion,
		WorkloadID:    "split/toy/model",
		DatasetID:     "toy",
		ModelID:       "model",
		ModelType:     "mlp_square_linear_score",
		SplitID:       "split",
		ModelArtifact: ckksplanner.ArtifactBinding{
			Path:   "model.json",
			SHA256: digest,
		},
		ValidationData: ckksplanner.ArtifactBinding{
			Path:   "validation.csv",
			SHA256: digest,
		},
		Graph: tuner.GraphSummary{
			MultiplicativeDepth: 1,
			AddOps:              2,
			MulOps:              3,
			RescaleOps:          1,
		},
		Decision: ckksplanner.DecisionStabilityContract{
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
		Calibration: ckksplanner.NumericalCalibration{
			MaxInputAbs:           2,
			MaxPlaintextOutputAbs: 1,
			AggregateSensitivity:  4,
			SensitivityMethod:     ckksplanner.EmpiricalIntervalDAGSensitivityV1,
			CalibrationScope:      "observed_validation_artifact:" + digest,
		},
		Deployment: ckksplanner.DeploymentContract{
			SecurityBits:         128,
			RequiredSlots:        1,
			MaxEncryptedTrials:   4,
			ValidationKeyRepeats: 1,
			PackingStrategy:      ckksplanner.ScalarReplicatedPackingV1,
			AllowedPaths: []tuner.ExecutionPath{
				tuner.PathRescale,
			},
			ScaleTraceMethod:      ckksplanner.LattigoRescaleScaleTraceV1,
			RescaleLevelsConsumed: 3,
			TerminalScaleExponent: 3,
			RequiredQPrimes:       6,
		},
	}
}
