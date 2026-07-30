package providergate

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"os"
	"reflect"
	"strings"

	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/ckksplanner"
	"github.com/hasslelee/flipguard/internal/tuner"
)

const (
	ProviderCandidateRequestSchemaVersion         = 1
	ProviderCandidateConcreteRequestSchemaVersion = 2
	ProviderCandidateScheduleRequestSchemaVersion = 3
	BoundProviderCandidateSchemaVersion           = 1
	ProviderCandidateGateSchemaVersion            = 1

	ProviderKindManual            = "manual"
	ProviderKindBoundedCatalog    = "bounded_catalog"
	ProviderKindExternalAutotuner = "external_autotuner"
	ProviderKindDirectSynthesizer = "direct_synthesizer"

	ProviderGateOutcomeSelected = "SELECTED"
	ProviderGateOutcomeNoSafe   = "NO_SAFE"
)

// ProviderCandidateRequest is the untrusted, literal-only interchange format
// accepted from manual, catalog, external, and direct candidate providers.
// Security and workload bindings are deliberately absent and recomputed.
type ProviderCandidateRequest struct {
	SchemaVersion int `json:"schema_version"`

	ProviderKind string `json:"provider_kind"`
	ProviderID   string `json:"provider_id"`

	Path       tuner.ExecutionPath                  `json:"path"`
	Parameters ckksplanner.CKKSParameterLiteralSpec `json:"parameters"`

	ExecutionSchedule *ProviderExecutionScheduleBinding `json:"execution_schedule,omitempty"`
}

// BoundProviderCandidate records the exact provider artifact and all
// FlipGuard-computed admission facts required before encrypted execution.
type BoundProviderCandidate struct {
	SchemaVersion int `json:"schema_version"`

	Request        ProviderCandidateRequest    `json:"request"`
	SourceArtifact ckksplanner.ArtifactBinding `json:"source_artifact"`

	ContractDigest       string `json:"contract_digest"`
	SecurityPolicyID     string `json:"security_policy_id"`
	SecurityPolicyDigest string `json:"security_policy_digest"`
	PolicyRetuning       int    `json:"policy_retuning"`

	Candidate ckksplanner.SynthesizedCandidate `json:"candidate"`

	ExecutionSchedule *BoundProviderExecutionSchedule `json:"execution_schedule,omitempty"`
}

// ProviderCandidateGateResult is a one-literal certify-or-reject result. The
// provider adapter never invokes synthesis or adaptive repair.
type ProviderCandidateGateResult struct {
	SchemaVersion int `json:"schema_version"`

	ValidationContract ckksplanner.WorkloadContract `json:"validation_contract"`
	BoundCandidate     BoundProviderCandidate       `json:"bound_candidate"`
	Outcome            string                       `json:"outcome"`
	Reason             string                       `json:"reason"`

	TrialsUsed       int                            `json:"trials_used"`
	EncryptedKeyRuns int                            `json:"encrypted_key_runs"`
	Trial            ckksplanner.TabularTrialResult `json:"trial"`

	Selected *ckksplanner.SynthesizedCandidate `json:"selected,omitempty"`
}

// LoadProviderCandidateRequest parses a provider artifact strictly. Unknown
// and trailing JSON are rejected before any CKKS work.
func LoadProviderCandidateRequest(
	path string,
) (ProviderCandidateRequest, ckksplanner.ArtifactBinding, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return ProviderCandidateRequest{},
			ckksplanner.ArtifactBinding{},
			fmt.Errorf(
				"read provider candidate artifact %s: %w",
				path,
				err,
			)
	}

	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	var request ProviderCandidateRequest
	if err := decoder.Decode(&request); err != nil {
		return ProviderCandidateRequest{},
			ckksplanner.ArtifactBinding{},
			fmt.Errorf(
				"decode provider candidate artifact %s: %w",
				path,
				err,
			)
	}
	var trailing any
	if err := decoder.Decode(&trailing); err != io.EOF {
		if err == nil {
			err = fmt.Errorf("unexpected trailing JSON value")
		}
		return ProviderCandidateRequest{},
			ckksplanner.ArtifactBinding{},
			fmt.Errorf(
				"decode provider candidate artifact %s: %w",
				path,
				err,
			)
	}

	return request, ckksplanner.ArtifactBinding{
		Path:   path,
		SHA256: digestBytes(data),
	}, nil
}

// LoadAndBindProviderCandidate binds an untrusted provider artifact to an
// exact workload and the immutable Security V2 policy.
func LoadAndBindProviderCandidate(
	contract ckksplanner.WorkloadContract,
	path string,
) (BoundProviderCandidate, error) {
	request, source, err := LoadProviderCandidateRequest(path)
	if err != nil {
		return BoundProviderCandidate{}, err
	}
	return BindProviderCandidate(contract, request, source)
}

// BindProviderCandidate recomputes all trusted metadata for one candidate.
func BindProviderCandidate(
	contract ckksplanner.WorkloadContract,
	request ProviderCandidateRequest,
	source ckksplanner.ArtifactBinding,
) (BoundProviderCandidate, error) {
	if err := contract.Validate(); err != nil {
		return BoundProviderCandidate{}, fmt.Errorf(
			"validate provider workload contract: %w",
			err,
		)
	}
	if err := validateProviderCandidateRequest(request); err != nil {
		return BoundProviderCandidate{}, err
	}
	if strings.TrimSpace(source.Path) == "" {
		return BoundProviderCandidate{}, fmt.Errorf(
			"provider candidate artifact path is empty",
		)
	}
	if err := validateSHA256(source.SHA256); err != nil {
		return BoundProviderCandidate{}, err
	}
	if !pathAllowed(request.Path, contract.Deployment.AllowedPaths) {
		return BoundProviderCandidate{}, fmt.Errorf(
			"provider execution path %q is outside workload contract",
			request.Path,
		)
	}

	contractDigest, err := digestContract(contract)
	if err != nil {
		return BoundProviderCandidate{}, err
	}
	securityPolicy := ckksplanner.DefaultSecurityEnvelope()
	if contract.Deployment.SecurityBits != securityPolicy.SecurityBits {
		return BoundProviderCandidate{}, fmt.Errorf(
			"workload requests %d security bits but provider gate policy %s is fixed at %d",
			contract.Deployment.SecurityBits,
			securityPolicy.ID,
			securityPolicy.SecurityBits,
		)
	}
	securityPolicyDigest, err := ckksplanner.SecurityPolicyDigest(
		securityPolicy,
	)
	if err != nil {
		return BoundProviderCandidate{}, err
	}
	security, err := ckksplanner.AssessLiteralSecurity(
		request.Parameters,
		contract.Deployment.SecurityBits,
		securityPolicy,
	)
	if err != nil {
		return BoundProviderCandidate{}, fmt.Errorf(
			"assess provider candidate security: %w",
			err,
		)
	}
	if security.FinalAdmission != ckksplanner.SecurityAdmissionPass {
		return BoundProviderCandidate{}, fmt.Errorf(
			"provider candidate is Security V2 inadmissible: Q=%s QP=%s logQ=%d logP=%d logQP=%d cap=%d",
			security.CiphertextQAdmission,
			security.EvaluationKeyQPAdmission,
			security.LogQ,
			security.LogP,
			security.LogQP,
			security.MaxAllowedLogQP,
		)
	}
	executionSchedule, err := bindProviderExecutionSchedule(
		contract,
		request,
	)
	if err != nil {
		return BoundProviderCandidate{}, err
	}
	qPrimeCount := request.Parameters.QPrimeCount()
	requiredQPrimes := contract.Deployment.RequiredQPrimes
	requiredRescaleLevels :=
		contract.Deployment.RescaleLevelsConsumed
	if executionSchedule != nil {
		requiredQPrimes = executionSchedule.RequiredQPrimes
		requiredRescaleLevels =
			executionSchedule.RescaleLevels
	}
	if qPrimeCount < requiredQPrimes {
		return BoundProviderCandidate{}, fmt.Errorf(
			"provider candidate has %d Q primes but graph contract requires at least %d",
			qPrimeCount,
			requiredQPrimes,
		)
	}
	slots := 1 << (request.Parameters.LogN - 1)
	if slots < contract.Deployment.RequiredSlots {
		return BoundProviderCandidate{}, fmt.Errorf(
			"provider candidate exposes %d slots but workload requires %d",
			slots,
			contract.Deployment.RequiredSlots,
		)
	}

	candidateID, err := providerCandidateID(
		request,
		source.SHA256,
		contractDigest,
	)
	if err != nil {
		return BoundProviderCandidate{}, err
	}
	candidate := ckksplanner.SynthesizedCandidate{
		ID:         candidateID,
		Path:       request.Path,
		Parameters: request.Parameters,
		Security:   security,

		RequiredRescaleLevels: requiredRescaleLevels,
		LevelGuard: qPrimeCount -
			requiredQPrimes,
		PrecisionTargetBits: request.Parameters.LogDefaultScale,
		MessageMagnitudeBits: magnitudeBits(
			contract.Calibration.MaxPlaintextOutputAbs,
		),

		GenerationKind: "provider_import_" + request.ProviderKind,
		Reason: fmt.Sprintf(
			"exact literal imported from %s provider %s; SAFE requires encrypted validation",
			request.ProviderKind,
			request.ProviderID,
		),
	}
	if _, err := candidate.Profile(); err != nil {
		return BoundProviderCandidate{}, fmt.Errorf(
			"provider candidate failed Lattigo literal validation: %w",
			err,
		)
	}

	return BoundProviderCandidate{
		SchemaVersion:        BoundProviderCandidateSchemaVersion,
		Request:              request,
		SourceArtifact:       source,
		ContractDigest:       contractDigest,
		SecurityPolicyID:     securityPolicy.ID,
		SecurityPolicyDigest: securityPolicyDigest,
		PolicyRetuning:       0,
		Candidate:            candidate,
		ExecutionSchedule:    executionSchedule,
	}, nil
}

// ValidateBoundProviderCandidate detects source, contract, literal, identity,
// or policy mutation before encrypted execution.
func ValidateBoundProviderCandidate(
	contract ckksplanner.WorkloadContract,
	bound BoundProviderCandidate,
) error {
	if bound.SchemaVersion != BoundProviderCandidateSchemaVersion {
		return fmt.Errorf(
			"unsupported bound provider candidate schema version %d",
			bound.SchemaVersion,
		)
	}
	data, err := os.ReadFile(bound.SourceArtifact.Path)
	if err != nil {
		return fmt.Errorf(
			"read bound provider candidate artifact %s: %w",
			bound.SourceArtifact.Path,
			err,
		)
	}
	if digestBytes(data) != bound.SourceArtifact.SHA256 {
		return fmt.Errorf("bound provider candidate artifact digest mismatch")
	}
	recomputed, err := BindProviderCandidate(
		contract,
		bound.Request,
		bound.SourceArtifact,
	)
	if err != nil {
		return err
	}
	if !reflect.DeepEqual(recomputed, bound) {
		return fmt.Errorf(
			"bound provider candidate identity or policy metadata mismatch",
		)
	}
	return nil
}

// RunProviderCandidateGate executes exactly one bound literal and never calls
// synthesis or repair.
func RunProviderCandidateGate(
	contract ckksplanner.WorkloadContract,
	bound BoundProviderCandidate,
) (ProviderCandidateGateResult, error) {
	if err := ValidateBoundProviderCandidate(contract, bound); err != nil {
		return ProviderCandidateGateResult{}, err
	}
	var trial ckksplanner.TabularTrialResult
	var err error
	if bound.Request.SchemaVersion >=
		ProviderCandidateConcreteRequestSchemaVersion {
		executionScheduleID := ""
		if bound.ExecutionSchedule != nil {
			executionScheduleID =
				bound.ExecutionSchedule.ScheduleID
		}
		trial, err = ckksplanner.ExecuteTabularCandidateWithOptions(
			contract,
			bound.Candidate,
			1,
			ckksplanner.TabularCandidateExecutionOptions{
				CaptureSampleLedger: true,
				ExecutionScheduleID: executionScheduleID,
			},
		)
	} else {
		trial, err = ckksplanner.ExecuteTabularCandidate(
			contract,
			bound.Candidate,
			1,
		)
	}
	if err != nil {
		return ProviderCandidateGateResult{}, err
	}
	result := ProviderCandidateGateResult{
		SchemaVersion:      ProviderCandidateGateSchemaVersion,
		ValidationContract: contract,
		BoundCandidate:     bound,
		Outcome:            ProviderGateOutcomeNoSafe,
		Reason:             "bound provider candidate was not certified SAFE",
		TrialsUsed:         1,
		EncryptedKeyRuns:   trial.KeyRepeatsCompleted,
		Trial:              trial,
	}
	if trial.Status == certify.StatusSafe {
		selected := bound.Candidate
		result.Outcome = ProviderGateOutcomeSelected
		result.Reason = "bound provider candidate certified SAFE"
		result.Selected = &selected
	}
	return result, nil
}

// LoadProviderCandidateGateResult parses a completed one-literal selection
// strictly and binds its exact source bytes for locked-audit replay.
func LoadProviderCandidateGateResult(
	path string,
) (
	ProviderCandidateGateResult,
	ckksplanner.ArtifactBinding,
	error,
) {
	data, err := os.ReadFile(path)
	if err != nil {
		return ProviderCandidateGateResult{},
			ckksplanner.ArtifactBinding{},
			fmt.Errorf(
				"read provider candidate gate result %s: %w",
				path,
				err,
			)
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	var result ProviderCandidateGateResult
	if err := decoder.Decode(&result); err != nil {
		return ProviderCandidateGateResult{},
			ckksplanner.ArtifactBinding{},
			fmt.Errorf(
				"decode provider candidate gate result %s: %w",
				path,
				err,
			)
	}
	var trailing any
	if err := decoder.Decode(&trailing); err != io.EOF {
		if err == nil {
			err = fmt.Errorf("unexpected trailing JSON value")
		}
		return ProviderCandidateGateResult{},
			ckksplanner.ArtifactBinding{},
			fmt.Errorf(
				"decode provider candidate gate result %s: %w",
				path,
				err,
			)
	}
	return result, ckksplanner.ArtifactBinding{
		Path:   path,
		SHA256: digestBytes(data),
	}, nil
}

// ValidateProviderCandidateGateResult reproduces every trusted binding and
// checks the one-trial ledger before a locked audit may consume it.
func ValidateProviderCandidateGateResult(
	result ProviderCandidateGateResult,
) error {
	if result.SchemaVersion != ProviderCandidateGateSchemaVersion {
		return fmt.Errorf(
			"unsupported provider candidate gate schema version %d",
			result.SchemaVersion,
		)
	}
	if err := result.ValidationContract.Validate(); err != nil {
		return fmt.Errorf(
			"validate provider gate workload contract: %w",
			err,
		)
	}
	if err := ValidateBoundProviderCandidate(
		result.ValidationContract,
		result.BoundCandidate,
	); err != nil {
		return err
	}
	if result.TrialsUsed != 1 ||
		result.Trial.TrialIndex != 1 ||
		result.EncryptedKeyRuns != result.Trial.KeyRepeatsCompleted ||
		result.Trial.KeyRepeatsRequested !=
			result.ValidationContract.Deployment.ValidationKeyRepeats ||
		!reflect.DeepEqual(
			result.Trial.Candidate,
			result.BoundCandidate.Candidate,
		) {
		return fmt.Errorf("provider candidate gate trial ledger mismatch")
	}

	switch result.Trial.Status {
	case certify.StatusSafe:
		if result.Outcome != ProviderGateOutcomeSelected ||
			result.Selected == nil ||
			!reflect.DeepEqual(
				*result.Selected,
				result.BoundCandidate.Candidate,
			) {
			return fmt.Errorf(
				"SAFE provider candidate gate result is not SELECTED",
			)
		}
	case certify.StatusRejected, certify.StatusFailed:
		if result.Outcome != ProviderGateOutcomeNoSafe ||
			result.Selected != nil {
			return fmt.Errorf(
				"non-SAFE provider candidate gate result is not NO_SAFE",
			)
		}
	default:
		return fmt.Errorf(
			"unsupported provider candidate gate status %q",
			result.Trial.Status,
		)
	}
	if result.BoundCandidate.Request.SchemaVersion >=
		ProviderCandidateConcreteRequestSchemaVersion &&
		result.Trial.Status != certify.StatusFailed {
		if err := ckksplanner.ValidateTabularSampleLedger(
			result.Trial,
			result.ValidationContract,
		); err != nil {
			return fmt.Errorf(
				"validate provider sample ledger: %w",
				err,
			)
		}
	}
	return nil
}

// RunLockedProviderCandidateAudit verifies a completed provider selection and
// replays its exact selected literal on the declared disjoint audit split.
func RunLockedProviderCandidateAudit(
	selectionResultPath string,
	options ckksplanner.LockedAuditOptions,
) (ckksplanner.LockedAuditResult, error) {
	result, selectionBinding, err :=
		LoadProviderCandidateGateResult(selectionResultPath)
	if err != nil {
		return ckksplanner.LockedAuditResult{}, err
	}
	if err := ValidateProviderCandidateGateResult(result); err != nil {
		return ckksplanner.LockedAuditResult{}, err
	}
	if result.Outcome != ProviderGateOutcomeSelected ||
		result.Selected == nil {
		return ckksplanner.LockedAuditResult{}, fmt.Errorf(
			"provider candidate gate result has no SAFE selected literal",
		)
	}
	if options.SelectionResultPath != selectionResultPath {
		return ckksplanner.LockedAuditResult{}, fmt.Errorf(
			"provider locked-audit selection path mismatch",
		)
	}
	executionScheduleID := ""
	if result.BoundCandidate.ExecutionSchedule != nil {
		executionScheduleID =
			result.BoundCandidate.ExecutionSchedule.ScheduleID
	}
	return ckksplanner.RunLockedTabularCandidateAudit(
		ckksplanner.LockedCandidateSelection{
			SelectionResult: selectionBinding,
			Contract:        result.ValidationContract,
			ContractDigest: result.BoundCandidate.
				ContractDigest,
			Candidate:           *result.Selected,
			ExecutionScheduleID: executionScheduleID,
		},
		options,
	)
}

func validateProviderCandidateRequest(
	request ProviderCandidateRequest,
) error {
	switch request.SchemaVersion {
	case ProviderCandidateRequestSchemaVersion,
		ProviderCandidateConcreteRequestSchemaVersion,
		ProviderCandidateScheduleRequestSchemaVersion:
	default:
		return fmt.Errorf(
			"unsupported provider candidate request schema version %d",
			request.SchemaVersion,
		)
	}
	switch request.ProviderKind {
	case ProviderKindManual,
		ProviderKindBoundedCatalog,
		ProviderKindExternalAutotuner,
		ProviderKindDirectSynthesizer:
	default:
		return fmt.Errorf(
			"unsupported candidate provider kind %q",
			request.ProviderKind,
		)
	}
	if err := validateProviderID(request.ProviderID); err != nil {
		return err
	}
	switch request.Path {
	case tuner.PathRescale, tuner.PathNonRescale:
	default:
		return fmt.Errorf(
			"unsupported provider execution path %q",
			request.Path,
		)
	}
	if request.Parameters.LogN <= 0 {
		return fmt.Errorf("provider candidate LogN must be positive")
	}
	if request.Parameters.LogDefaultScale <= 0 {
		return fmt.Errorf(
			"provider candidate default scale must be positive",
		)
	}
	switch request.SchemaVersion {
	case ProviderCandidateRequestSchemaVersion:
		if request.ExecutionSchedule != nil {
			return fmt.Errorf(
				"provider candidate schema v1 cannot bind an execution schedule",
			)
		}
		if len(request.Parameters.Q) > 0 ||
			len(request.Parameters.P) > 0 {
			return fmt.Errorf(
				"provider candidate schema v1 requires logarithmic moduli only",
			)
		}
		if err := validatePositivePrimeBits(
			"LogQ",
			request.Parameters.LogQ,
		); err != nil {
			return err
		}
		if err := validatePositivePrimeBits(
			"LogP",
			request.Parameters.LogP,
		); err != nil {
			return err
		}
	case ProviderCandidateConcreteRequestSchemaVersion:
		if request.ExecutionSchedule != nil {
			return fmt.Errorf(
				"provider candidate schema v2 cannot bind an execution schedule",
			)
		}
		fallthrough
	case ProviderCandidateScheduleRequestSchemaVersion:
		if len(request.Parameters.LogQ) > 0 ||
			len(request.Parameters.LogP) > 0 {
			return fmt.Errorf(
				"provider candidate schema v2 requires concrete moduli only",
			)
		}
		if err := validatePositiveConcretePrimes(
			"Q",
			request.Parameters.Q,
		); err != nil {
			return err
		}
		if err := validatePositiveConcretePrimes(
			"P",
			request.Parameters.P,
		); err != nil {
			return err
		}
		if request.SchemaVersion ==
			ProviderCandidateScheduleRequestSchemaVersion &&
			request.ExecutionSchedule == nil {
			return fmt.Errorf(
				"provider candidate schema v3 requires an execution schedule",
			)
		}
	}
	return nil
}

func validateProviderID(value string) error {
	if value == "" || len(value) > 128 || strings.TrimSpace(value) != value {
		return fmt.Errorf(
			"provider ID must contain 1..128 unpadded ASCII identifier characters",
		)
	}
	for _, character := range value {
		if (character >= 'a' && character <= 'z') ||
			(character >= 'A' && character <= 'Z') ||
			(character >= '0' && character <= '9') ||
			strings.ContainsRune("._:-", character) {
			continue
		}
		return fmt.Errorf(
			"provider ID contains unsupported character %q",
			character,
		)
	}
	return nil
}

func validatePositivePrimeBits(name string, values []int) error {
	if len(values) == 0 {
		return fmt.Errorf("provider candidate %s is empty", name)
	}
	for index, value := range values {
		if value <= 0 {
			return fmt.Errorf(
				"provider candidate %s[%d] must be positive",
				name,
				index,
			)
		}
	}
	return nil
}

func validatePositiveConcretePrimes(
	name string,
	values []uint64,
) error {
	if len(values) == 0 {
		return fmt.Errorf("provider candidate %s is empty", name)
	}
	for index, value := range values {
		if value <= 1 {
			return fmt.Errorf(
				"provider candidate %s[%d] must be greater than one",
				name,
				index,
			)
		}
	}
	return nil
}

func pathAllowed(
	path tuner.ExecutionPath,
	allowed []tuner.ExecutionPath,
) bool {
	for _, candidate := range allowed {
		if candidate == path {
			return true
		}
	}
	return false
}

func providerCandidateID(
	request ProviderCandidateRequest,
	sourceDigest string,
	contractDigest string,
) (string, error) {
	identity := struct {
		SchemaVersion     int                                  `json:"schema_version"`
		ProviderKind      string                               `json:"provider_kind"`
		ProviderID        string                               `json:"provider_id"`
		SourceDigest      string                               `json:"source_digest"`
		ContractDigest    string                               `json:"contract_digest"`
		Path              tuner.ExecutionPath                  `json:"path"`
		Parameters        ckksplanner.CKKSParameterLiteralSpec `json:"parameters"`
		ExecutionSchedule *ProviderExecutionScheduleBinding    `json:"execution_schedule,omitempty"`
	}{
		SchemaVersion:     request.SchemaVersion,
		ProviderKind:      request.ProviderKind,
		ProviderID:        request.ProviderID,
		SourceDigest:      sourceDigest,
		ContractDigest:    contractDigest,
		Path:              request.Path,
		Parameters:        request.Parameters,
		ExecutionSchedule: request.ExecutionSchedule,
	}
	encoded, err := json.Marshal(identity)
	if err != nil {
		return "", fmt.Errorf("marshal provider candidate identity: %w", err)
	}
	digest := strings.TrimPrefix(digestBytes(encoded), "sha256:")
	return fmt.Sprintf(
		"provider_%s_%s",
		request.ProviderKind,
		digest[:16],
	), nil
}

func digestBytes(data []byte) string {
	sum := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(sum[:])
}

func digestContract(
	contract ckksplanner.WorkloadContract,
) (string, error) {
	encoded, err := json.Marshal(contract)
	if err != nil {
		return "", fmt.Errorf("marshal workload contract: %w", err)
	}
	return digestBytes(encoded), nil
}

func validateSHA256(value string) error {
	const prefix = "sha256:"
	if !strings.HasPrefix(value, prefix) {
		return fmt.Errorf("provider artifact digest must use sha256 prefix")
	}
	decoded, err := hex.DecodeString(strings.TrimPrefix(value, prefix))
	if err != nil {
		return fmt.Errorf("invalid provider artifact digest: %w", err)
	}
	if len(decoded) != sha256.Size {
		return fmt.Errorf("provider artifact digest must contain 32 bytes")
	}
	return nil
}

func magnitudeBits(maxAbs float64) int {
	if maxAbs <= 1 {
		return 0
	}
	return int(math.Ceil(math.Log2(maxAbs)))
}
