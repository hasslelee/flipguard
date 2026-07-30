package providergate

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/ckksbackend"
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

func TestProviderSchemaV1JSONRemainsStable(t *testing.T) {
	literal := ckksplanner.CKKSParameterLiteralSpec{
		LogN:            13,
		LogQ:            []int{45, 40, 40},
		LogP:            []int{45},
		LogDefaultScale: 40,
	}
	encoded, err := json.Marshal(literal)
	if err != nil {
		t.Fatalf("marshal v1 literal: %v", err)
	}
	const expected = `{"log_n":13,"log_q":[45,40,40],"log_p":[45],"log_default_scale":40}`
	if string(encoded) != expected {
		t.Fatalf("v1 literal JSON changed:\n got %s\nwant %s", encoded, expected)
	}
}

func TestProviderSchemaV1CandidateIdentityRemainsStable(t *testing.T) {
	request := ProviderCandidateRequest{
		SchemaVersion: ProviderCandidateRequestSchemaVersion,
		ProviderKind:  ProviderKindExternalAutotuner,
		ProviderID:    "fixture-v1",
		Path:          tuner.PathRescale,
		Parameters: ckksplanner.CKKSParameterLiteralSpec{
			LogN:            13,
			LogQ:            []int{45, 40, 40},
			LogP:            []int{45},
			LogDefaultScale: 40,
		},
	}
	id, err := providerCandidateID(
		request,
		"sha256:"+strings.Repeat("0", 64),
		"sha256:"+strings.Repeat("1", 64),
	)
	if err != nil {
		t.Fatalf("compute v1 candidate ID: %v", err)
	}
	const expected = "provider_external_autotuner_155aa5e67f76c967"
	if id != expected {
		t.Fatalf("v1 candidate identity changed: got %s want %s", id, expected)
	}
}

func TestProviderSchemaV2BindsConcretePrimeOrder(t *testing.T) {
	contract := validContractFixture()
	request := concreteProviderRequestFixture()
	source := ckksplanner.ArtifactBinding{
		Path:   "candidate.json",
		SHA256: digestBytes([]byte("concrete candidate")),
	}
	first, err := BindProviderCandidate(contract, request, source)
	if err != nil {
		t.Fatalf("bind concrete candidate: %v", err)
	}
	if first.Candidate.Security.LogQP != 242 ||
		first.Candidate.Security.FinalAdmission !=
			ckksplanner.SecurityAdmissionPass {
		t.Fatalf("unexpected concrete security: %+v", first.Candidate.Security)
	}
	profile, err := first.Candidate.Profile()
	if err != nil {
		t.Fatalf("materialize concrete candidate: %v", err)
	}
	if !reflect.DeepEqual(profile.Literal.Q, request.Parameters.Q) ||
		!reflect.DeepEqual(profile.Literal.P, request.Parameters.P) {
		t.Fatalf("concrete modulus order changed: %+v", profile.Literal)
	}

	reordered := request
	reordered.Parameters.Q = append(
		[]uint64(nil),
		request.Parameters.Q...,
	)
	reordered.Parameters.Q[1], reordered.Parameters.Q[2] =
		reordered.Parameters.Q[2], reordered.Parameters.Q[1]
	second, err := BindProviderCandidate(contract, reordered, source)
	if err != nil {
		t.Fatalf("bind reordered concrete candidate: %v", err)
	}
	if first.Candidate.ID == second.Candidate.ID {
		t.Fatal("concrete Q order did not change candidate identity")
	}
}

func TestProviderSchemaV3BindsPinnedEVASchedule(t *testing.T) {
	contract := validEVAScheduleContractFixture()
	request := evaScheduleProviderRequestFixture(t)
	source := ckksplanner.ArtifactBinding{
		Path:   "eva-schedule-candidate.json",
		SHA256: digestBytes([]byte("eva schedule candidate")),
	}
	bound, err := BindProviderCandidate(contract, request, source)
	if err != nil {
		t.Fatalf("bind EVA schedule candidate: %v", err)
	}
	if bound.ExecutionSchedule == nil {
		t.Fatal("bound EVA schedule is missing")
	}
	if bound.ExecutionSchedule.RequiredQPrimes != 3 ||
		bound.ExecutionSchedule.RescaleLevels != 2 ||
		bound.Candidate.RequiredRescaleLevels != 2 ||
		bound.Candidate.LevelGuard != 0 {
		t.Fatalf(
			"unexpected EVA schedule requirements: %+v candidate=%+v",
			bound.ExecutionSchedule,
			bound.Candidate,
		)
	}
	if bound.Candidate.Security.FinalAdmission !=
		ckksplanner.SecurityAdmissionPass {
		t.Fatalf(
			"EVA schedule candidate is not Security V2 admitted: %+v",
			bound.Candidate.Security,
		)
	}
}

func TestProviderSchemaV2CannotBypassDefaultGraphRequirements(
	t *testing.T,
) {
	contract := validEVAScheduleContractFixture()
	request := evaScheduleProviderRequestFixture(t)
	request.SchemaVersion =
		ProviderCandidateConcreteRequestSchemaVersion
	request.ExecutionSchedule = nil
	_, err := BindProviderCandidate(
		contract,
		request,
		ckksplanner.ArtifactBinding{
			Path:   "eva-parameter-only-candidate.json",
			SHA256: digestBytes([]byte("eva parameter-only candidate")),
		},
	)
	if err == nil || !strings.Contains(err.Error(), "Q primes") {
		t.Fatalf(
			"expected parameter-only graph compatibility rejection, got %v",
			err,
		)
	}
}

func TestProviderSchemaV3RejectsScheduleMutation(t *testing.T) {
	contract := validEVAScheduleContractFixture()
	request := evaScheduleProviderRequestFixture(t)
	request.ExecutionSchedule.ContractArtifact.SHA256 =
		digestBytes([]byte("mutated schedule contract"))
	_, err := BindProviderCandidate(
		contract,
		request,
		ckksplanner.ArtifactBinding{
			Path:   "eva-schedule-candidate.json",
			SHA256: digestBytes([]byte("eva schedule candidate")),
		},
	)
	if err == nil ||
		!strings.Contains(err.Error(), "contract digest mismatch") {
		t.Fatalf(
			"expected schedule contract digest rejection, got %v",
			err,
		)
	}
}

func TestProviderSchemasRejectMixedModulusRepresentations(t *testing.T) {
	contract := validContractFixture()
	source := ckksplanner.ArtifactBinding{
		Path:   "candidate.json",
		SHA256: digestBytes([]byte("candidate")),
	}
	v1 := ProviderCandidateRequest{
		SchemaVersion: ProviderCandidateRequestSchemaVersion,
		ProviderKind:  ProviderKindManual,
		ProviderID:    "mixed-v1",
		Path:          contract.Deployment.AllowedPaths[0],
		Parameters: ckksplanner.CKKSParameterLiteralSpec{
			LogN:            14,
			LogQ:            []int{60, 40, 40, 40},
			LogP:            []int{61},
			Q:               []uint64{1152921504606748673},
			P:               []uint64{2305843009211662337},
			LogDefaultScale: 40,
		},
	}
	if _, err := BindProviderCandidate(
		contract,
		v1,
		source,
	); err == nil || !strings.Contains(err.Error(), "v1") {
		t.Fatalf("expected v1 concrete-modulus rejection, got %v", err)
	}

	v2 := concreteProviderRequestFixture()
	v2.Parameters.LogQ = []int{60, 20, 20, 20}
	v2.Parameters.LogP = []int{61}
	if _, err := BindProviderCandidate(
		contract,
		v2,
		source,
	); err == nil || !strings.Contains(err.Error(), "v2") {
		t.Fatalf("expected v2 logarithmic-modulus rejection, got %v", err)
	}
}

func TestProviderSchemaV2RejectsInvalidConcretePrime(t *testing.T) {
	contract := validContractFixture()
	request := concreteProviderRequestFixture()
	request.Parameters.Q[1] = 3
	_, err := BindProviderCandidate(
		contract,
		request,
		ckksplanner.ArtifactBinding{
			Path:   "candidate.json",
			SHA256: digestBytes([]byte("candidate")),
		},
	)
	if err == nil ||
		!strings.Contains(err.Error(), "Lattigo literal validation") {
		t.Fatalf("expected invalid Lattigo modulus rejection, got %v", err)
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

func concreteProviderRequestFixture() ProviderCandidateRequest {
	return ProviderCandidateRequest{
		SchemaVersion: ProviderCandidateConcreteRequestSchemaVersion,
		ProviderKind:  ProviderKindExternalAutotuner,
		ProviderID:    "aws-hit-source-replay-v1",
		Path:          tuner.PathRescale,
		Parameters: ckksplanner.CKKSParameterLiteralSpec{
			LogN: 14,
			Q: []uint64{
				1152921504606748673,
				1146881,
				1179649,
				786433,
				1376257,
				557057,
				1769473,
			},
			P:               []uint64{2305843009211662337},
			LogDefaultScale: 20,
		},
	}
}

func evaScheduleProviderRequestFixture(
	t *testing.T,
) ProviderCandidateRequest {
	t.Helper()
	repoRoot, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatalf("resolve repository root: %v", err)
	}
	compiledProgram := filepath.Join(
		repoRoot,
		"docs/evidence/eva_external_adapter_replay_v1/run/compiled_program.dot",
	)
	compilerOutput := filepath.Join(
		repoRoot,
		"docs/evidence/eva_external_adapter_replay_v1/run/compiler_output.json",
	)
	scheduleContract := ProviderExecutionScheduleContract{
		SchemaVersion:       ProviderExecutionScheduleContractSchemaVersion,
		ScheduleID:          ckksbackend.ExternalExecutionScheduleEVAV101LinearPoly3,
		AdapterID:           ckksbackend.CKKSEvaluationModeEVAV101LinearPoly3,
		ProviderID:          evaV101ProviderID,
		WorkloadID:          evaV101WorkloadID,
		ModelType:           "linear_poly3",
		ModelArtifactSHA256: evaV101ModelSHA256,
		ScoreFormula:        "0.5 + 0.197*z - 0.004*z^3",
		CompiledProgram: ckksplanner.ArtifactBinding{
			Path:   compiledProgram,
			SHA256: evaV101CompiledProgramSHA256,
		},
		CompilerOutput: ckksplanner.ArtifactBinding{
			Path:   compilerOutput,
			SHA256: evaV101CompilerOutputSHA256,
		},
		Parameters: ckksplanner.CKKSParameterLiteralSpec{
			LogN: 14,
			Q: []uint64{
				1152921504605962241,
				1152921504606584833,
				1152921504606683137,
			},
			P:               []uint64{1152921504606748673},
			LogDefaultScale: 20,
		},
		InputScaleBits:  20,
		OutputScaleBits: 20,
		RequiredQPrimes: 3,
		RescaleLevels:   2,
		PackingStrategy: ckksplanner.ScalarReplicatedPackingV1,
		Retuning:        0,
	}
	data, err := json.MarshalIndent(scheduleContract, "", "  ")
	if err != nil {
		t.Fatalf("marshal EVA schedule contract: %v", err)
	}
	data = append(data, '\n')
	schedulePath := filepath.Join(
		t.TempDir(),
		"eva_execution_schedule.json",
	)
	if err := os.WriteFile(schedulePath, data, 0o600); err != nil {
		t.Fatalf("write EVA schedule contract: %v", err)
	}
	return ProviderCandidateRequest{
		SchemaVersion: ProviderCandidateScheduleRequestSchemaVersion,
		ProviderKind:  ProviderKindExternalAutotuner,
		ProviderID:    evaV101ProviderID,
		Path:          tuner.PathRescale,
		Parameters:    scheduleContract.Parameters,
		ExecutionSchedule: &ProviderExecutionScheduleBinding{
			SchemaVersion: ProviderExecutionScheduleBindingSchemaVersion,
			ScheduleID:    scheduleContract.ScheduleID,
			ContractArtifact: ckksplanner.ArtifactBinding{
				Path:   schedulePath,
				SHA256: digestBytes(data),
			},
		},
	}
}

func validEVAScheduleContractFixture() ckksplanner.WorkloadContract {
	contract := validContractFixture()
	contract.WorkloadID = evaV101WorkloadID
	contract.DatasetID = "iris_binary"
	contract.ModelID = "linear_poly3"
	contract.ModelType = "linear_poly3"
	contract.SplitID = "split_seed_0"
	contract.ModelArtifact = ckksplanner.ArtifactBinding{
		Path:   "datasets/tabular_suite/iris_binary/linear_poly3/model.json",
		SHA256: evaV101ModelSHA256,
	}
	contract.Graph = tuner.GraphSummary{
		MultiplicativeDepth: 2,
		AddOps:              4,
		MulOps:              6,
		RescaleOps:          2,
	}
	contract.Deployment.RescaleLevelsConsumed = 6
	contract.Deployment.TerminalScaleExponent = 1
	contract.Deployment.RequiredQPrimes = 7
	return contract
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
