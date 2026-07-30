package providergate

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"reflect"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/ckksplanner"
)

const (
	ProviderExecutionScheduleBindingSchemaVersion  = 1
	ProviderExecutionScheduleContractSchemaVersion = 1
	BoundProviderExecutionScheduleSchemaVersion    = 1

	evaV101CompiledProgramSHA256 = "sha256:3c5ec469e692ea17dd413180c6c37c5042ef7bb5bfedd968d19447242fd72bca"
	evaV101CompilerOutputSHA256  = "sha256:605cc94bb1df230f9d58b1cbbeb66a26d11b6ae44ed4ad46dfca0925cd711dea"
	evaV101ModelSHA256           = "sha256:9d4cf49eb8f29c382a891665f15e69859f5d1419a4ae18552a3490fc78ec0ed1"
	evaV101ProviderID            = "microsoft_eva_v1.0.1_seal3.6.4_schedule_replay_v1"
	evaV101WorkloadID            = "split_seed_0/iris_binary/linear_poly3"
)

// ProviderExecutionScheduleBinding makes a compiled program contract part of
// the untrusted provider request and therefore part of candidate identity.
type ProviderExecutionScheduleBinding struct {
	SchemaVersion    int                         `json:"schema_version"`
	ScheduleID       string                      `json:"schedule_id"`
	ContractArtifact ckksplanner.ArtifactBinding `json:"contract_artifact"`
}

// ProviderExecutionScheduleContract is a strict, immutable description of one
// source-replayed compiled program and its backend lowering.
type ProviderExecutionScheduleContract struct {
	SchemaVersion       int    `json:"schema_version"`
	ScheduleID          string `json:"schedule_id"`
	AdapterID           string `json:"adapter_id"`
	ProviderID          string `json:"provider_id"`
	WorkloadID          string `json:"workload_id"`
	ModelType           string `json:"model_type"`
	ModelArtifactSHA256 string `json:"model_artifact_sha256"`
	ScoreFormula        string `json:"score_formula"`

	CompiledProgram ckksplanner.ArtifactBinding          `json:"compiled_program"`
	CompilerOutput  ckksplanner.ArtifactBinding          `json:"compiler_output"`
	Parameters      ckksplanner.CKKSParameterLiteralSpec `json:"parameters"`

	InputScaleBits  int    `json:"input_scale_bits"`
	OutputScaleBits int    `json:"output_scale_bits"`
	RequiredQPrimes int    `json:"required_q_primes"`
	RescaleLevels   int    `json:"rescale_levels"`
	PackingStrategy string `json:"packing_strategy"`
	Retuning        int    `json:"retuning"`
}

// BoundProviderExecutionSchedule records the trusted schedule facts consumed
// by the backend after all source artifacts have been rehashed.
type BoundProviderExecutionSchedule struct {
	SchemaVersion    int                         `json:"schema_version"`
	ScheduleID       string                      `json:"schedule_id"`
	AdapterID        string                      `json:"adapter_id"`
	ContractArtifact ckksplanner.ArtifactBinding `json:"contract_artifact"`
	CompiledProgram  ckksplanner.ArtifactBinding `json:"compiled_program"`
	CompilerOutput   ckksplanner.ArtifactBinding `json:"compiler_output"`
	RequiredQPrimes  int                         `json:"required_q_primes"`
	RescaleLevels    int                         `json:"rescale_levels"`
	InputScaleBits   int                         `json:"input_scale_bits"`
	OutputScaleBits  int                         `json:"output_scale_bits"`
	PolicyRetuning   int                         `json:"policy_retuning"`
}

func bindProviderExecutionSchedule(
	workload ckksplanner.WorkloadContract,
	request ProviderCandidateRequest,
) (*BoundProviderExecutionSchedule, error) {
	if request.SchemaVersion !=
		ProviderCandidateScheduleRequestSchemaVersion {
		return nil, nil
	}
	binding := request.ExecutionSchedule
	if binding == nil {
		return nil, fmt.Errorf(
			"provider candidate schema v3 requires an execution schedule",
		)
	}
	if binding.SchemaVersion !=
		ProviderExecutionScheduleBindingSchemaVersion {
		return nil, fmt.Errorf(
			"unsupported execution schedule binding schema %d",
			binding.SchemaVersion,
		)
	}
	if err := validateSHA256(binding.ContractArtifact.SHA256); err != nil {
		return nil, fmt.Errorf(
			"execution schedule contract digest: %w",
			err,
		)
	}
	contract, err := loadProviderExecutionScheduleContract(
		binding.ContractArtifact,
	)
	if err != nil {
		return nil, err
	}
	if binding.ScheduleID != contract.ScheduleID {
		return nil, fmt.Errorf(
			"execution schedule ID mismatch: binding %q contract %q",
			binding.ScheduleID,
			contract.ScheduleID,
		)
	}
	requirements, err :=
		ckksbackend.LookupExternalExecutionSchedule(
			contract.ScheduleID,
		)
	if err != nil {
		return nil, err
	}
	if err := validateEVAV101ScheduleContract(
		workload,
		request,
		contract,
		requirements,
	); err != nil {
		return nil, err
	}
	return &BoundProviderExecutionSchedule{
		SchemaVersion:    BoundProviderExecutionScheduleSchemaVersion,
		ScheduleID:       contract.ScheduleID,
		AdapterID:        contract.AdapterID,
		ContractArtifact: binding.ContractArtifact,
		CompiledProgram:  contract.CompiledProgram,
		CompilerOutput:   contract.CompilerOutput,
		RequiredQPrimes:  requirements.RequiredQPrimes,
		RescaleLevels:    requirements.RescaleLevels,
		InputScaleBits:   requirements.InputScaleBits,
		OutputScaleBits:  requirements.OutputScaleBits,
		PolicyRetuning:   0,
	}, nil
}

func loadProviderExecutionScheduleContract(
	binding ckksplanner.ArtifactBinding,
) (ProviderExecutionScheduleContract, error) {
	data, err := os.ReadFile(binding.Path)
	if err != nil {
		return ProviderExecutionScheduleContract{}, fmt.Errorf(
			"read execution schedule contract %s: %w",
			binding.Path,
			err,
		)
	}
	if digestBytes(data) != binding.SHA256 {
		return ProviderExecutionScheduleContract{}, fmt.Errorf(
			"execution schedule contract digest mismatch",
		)
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	var contract ProviderExecutionScheduleContract
	if err := decoder.Decode(&contract); err != nil {
		return ProviderExecutionScheduleContract{}, fmt.Errorf(
			"decode execution schedule contract: %w",
			err,
		)
	}
	var trailing any
	if err := decoder.Decode(&trailing); err != io.EOF {
		if err == nil {
			err = fmt.Errorf("unexpected trailing JSON value")
		}
		return ProviderExecutionScheduleContract{}, fmt.Errorf(
			"decode execution schedule contract: %w",
			err,
		)
	}
	return contract, nil
}

func validateEVAV101ScheduleContract(
	workload ckksplanner.WorkloadContract,
	request ProviderCandidateRequest,
	contract ProviderExecutionScheduleContract,
	requirements ckksbackend.ExternalExecutionScheduleRequirements,
) error {
	if contract.SchemaVersion !=
		ProviderExecutionScheduleContractSchemaVersion {
		return fmt.Errorf(
			"unsupported execution schedule contract schema %d",
			contract.SchemaVersion,
		)
	}
	if contract.ScheduleID !=
		ckksbackend.ExternalExecutionScheduleEVAV101LinearPoly3 ||
		contract.AdapterID !=
			ckksbackend.CKKSEvaluationModeEVAV101LinearPoly3 {
		return fmt.Errorf(
			"execution schedule contract does not identify the pinned EVA adapter",
		)
	}
	if request.ProviderKind != ProviderKindExternalAutotuner ||
		request.ProviderID != evaV101ProviderID ||
		contract.ProviderID != request.ProviderID {
		return fmt.Errorf(
			"EVA execution schedule provider identity mismatch",
		)
	}
	if workload.WorkloadID != evaV101WorkloadID ||
		contract.WorkloadID != workload.WorkloadID ||
		workload.ModelType != requirements.ModelType ||
		contract.ModelType != workload.ModelType ||
		contract.ScoreFormula != requirements.ScoreFormula {
		return fmt.Errorf(
			"EVA execution schedule workload or graph identity mismatch",
		)
	}
	if workload.ModelArtifact.SHA256 != evaV101ModelSHA256 ||
		contract.ModelArtifactSHA256 !=
			workload.ModelArtifact.SHA256 {
		return fmt.Errorf(
			"EVA execution schedule model artifact mismatch",
		)
	}
	if contract.CompiledProgram.SHA256 !=
		evaV101CompiledProgramSHA256 ||
		contract.CompilerOutput.SHA256 !=
			evaV101CompilerOutputSHA256 {
		return fmt.Errorf(
			"EVA execution schedule source-replay digest mismatch",
		)
	}
	for label, artifact := range map[string]ckksplanner.ArtifactBinding{
		"compiled program": contract.CompiledProgram,
		"compiler output":  contract.CompilerOutput,
	} {
		data, err := os.ReadFile(artifact.Path)
		if err != nil {
			return fmt.Errorf(
				"read EVA %s %s: %w",
				label,
				artifact.Path,
				err,
			)
		}
		if digestBytes(data) != artifact.SHA256 {
			return fmt.Errorf("EVA %s digest mismatch", label)
		}
	}
	expectedParameters := ckksplanner.CKKSParameterLiteralSpec{
		LogN: 14,
		Q: []uint64{
			1152921504605962241,
			1152921504606584833,
			1152921504606683137,
		},
		P:               []uint64{1152921504606748673},
		LogDefaultScale: 20,
	}
	if !reflect.DeepEqual(
		contract.Parameters,
		expectedParameters,
	) || !reflect.DeepEqual(
		request.Parameters,
		expectedParameters,
	) {
		return fmt.Errorf(
			"EVA execution schedule concrete parameter literal mismatch",
		)
	}
	if contract.InputScaleBits != requirements.InputScaleBits ||
		contract.OutputScaleBits != requirements.OutputScaleBits ||
		contract.RequiredQPrimes != requirements.RequiredQPrimes ||
		contract.RescaleLevels != requirements.RescaleLevels ||
		contract.PackingStrategy !=
			ckksplanner.ScalarReplicatedPackingV1 ||
		contract.Retuning != 0 {
		return fmt.Errorf(
			"EVA execution schedule lowering contract mismatch",
		)
	}
	if request.Parameters.QPrimeCount() !=
		requirements.RequiredQPrimes {
		return fmt.Errorf(
			"EVA execution schedule requires exactly %d Q primes, got %d",
			requirements.RequiredQPrimes,
			request.Parameters.QPrimeCount(),
		)
	}
	return nil
}
