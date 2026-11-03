package externaladapter

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/hasslelee/flipguard/internal/ckksplanner"
	"gopkg.in/yaml.v3"
)

const (
	OrionAdapterID            = "orion_lattigo_config_adapter_v1"
	OrionAdapterSchemaVersion = 1

	OrionImportableExact = "IMPORTABLE_EXACT"
	OrionImportBlocked   = "BLOCKED_SEMANTIC_MISMATCH"

	MappingExact      = "EXACT"
	MappingMismatch   = "MISMATCH"
	MappingUnverified = "UNVERIFIED"
)

// ExternalSourceBinding pins one actual upstream artifact rather than a
// reconstructed configuration fixture.
type ExternalSourceBinding struct {
	RepositoryURL string `json:"repository_url"`
	Commit        string `json:"commit"`
	Path          string `json:"path"`
	SHA256        string `json:"sha256"`
}

// OrionBackendBinding records the concrete backend source selected by Orion.
type OrionBackendBinding struct {
	Module  string `json:"module"`
	Version string `json:"version"`
	Commit  string `json:"commit"`
}

type OrionAdapterInput struct {
	Source  ExternalSourceBinding `json:"source"`
	Backend OrionBackendBinding   `json:"backend"`
}

type OrionCKKSParameters struct {
	LogN     int    `json:"log_n" yaml:"LogN"`
	LogQ     []int  `json:"log_q" yaml:"LogQ"`
	LogP     []int  `json:"log_p" yaml:"LogP"`
	LogScale int    `json:"log_scale" yaml:"LogScale"`
	H        int    `json:"h" yaml:"H"`
	RingType string `json:"ring_type" yaml:"RingType"`
}

type OrionParameters struct {
	Margin          int    `yaml:"margin"`
	EmbeddingMethod string `yaml:"embedding_method"`
	Backend         string `yaml:"backend"`
	FuseModules     bool   `yaml:"fuse_modules"`
	Debug           bool   `yaml:"debug"`
	DiagsPath       string `yaml:"diags_path"`
	KeysPath        string `yaml:"keys_path"`
	IOMode          string `yaml:"io_mode"`
}

type orionConfig struct {
	Comment    string                 `yaml:"comment"`
	CKKSParams OrionCKKSParameters    `yaml:"ckks_params"`
	BootParams map[string]interface{} `yaml:"boot_params"`
	Orion      OrionParameters        `yaml:"orion"`
}

type SemanticMapping struct {
	SourceField string `json:"source_field"`
	TargetField string `json:"target_field"`
	Status      string `json:"status"`
	Detail      string `json:"detail"`
}

// OrionAdapterReport separates syntactic parameter transfer from runtime and
// security semantics. A report can be valid even when import is fail-closed.
type OrionAdapterReport struct {
	SchemaVersion int    `json:"schema_version"`
	AdapterID     string `json:"adapter_id"`
	Status        string `json:"status"`

	Source  ExternalSourceBinding `json:"source"`
	Backend OrionBackendBinding   `json:"backend"`

	ParsedParameters OrionCKKSParameters                  `json:"parsed_parameters"`
	TargetLiteral    ckksplanner.CKKSParameterLiteralSpec `json:"target_literal"`
	Mappings         []SemanticMapping                    `json:"mappings"`

	SecurityPolicyID     string                          `json:"security_policy_id"`
	SecurityPolicyDigest string                          `json:"security_policy_digest"`
	SecurityAssessment   *ckksplanner.SecurityAssessment `json:"security_assessment,omitempty"`
	SecurityError        string                          `json:"security_error,omitempty"`

	BlockReasons            []string `json:"block_reasons"`
	EncryptedExecution      bool     `json:"encrypted_execution"`
	PolicyModification      int      `json:"policy_modification_count"`
	CandidateRequestEmitted bool     `json:"candidate_request_emitted"`
}

// AuditOrionConfig parses one pinned Orion YAML artifact and proves whether it
// can be represented by FlipGuard's frozen runtime without changing meaning.
func AuditOrionConfig(
	path string,
	input OrionAdapterInput,
) (OrionAdapterReport, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return OrionAdapterReport{}, fmt.Errorf(
			"read Orion config %s: %w",
			path,
			err,
		)
	}
	if err := validateSourceBinding(input.Source, data); err != nil {
		return OrionAdapterReport{}, err
	}
	if err := validateBackendBinding(input.Backend); err != nil {
		return OrionAdapterReport{}, err
	}

	config, err := decodeOrionConfig(data)
	if err != nil {
		return OrionAdapterReport{}, err
	}
	if err := validateOrionConfig(config); err != nil {
		return OrionAdapterReport{}, err
	}

	policy := ckksplanner.DefaultSecurityEnvelope()
	policyDigest, err := ckksplanner.SecurityPolicyDigest(policy)
	if err != nil {
		return OrionAdapterReport{}, err
	}
	literal := ckksplanner.CKKSParameterLiteralSpec{
		LogN:            config.CKKSParams.LogN,
		LogQ:            append([]int(nil), config.CKKSParams.LogQ...),
		LogP:            append([]int(nil), config.CKKSParams.LogP...),
		LogDefaultScale: config.CKKSParams.LogScale,
	}

	report := OrionAdapterReport{
		SchemaVersion:           OrionAdapterSchemaVersion,
		AdapterID:               OrionAdapterID,
		Status:                  OrionImportBlocked,
		Source:                  input.Source,
		Backend:                 input.Backend,
		ParsedParameters:        config.CKKSParams,
		TargetLiteral:           literal,
		SecurityPolicyID:        policy.ID,
		SecurityPolicyDigest:    policyDigest,
		EncryptedExecution:      false,
		PolicyModification:      0,
		CandidateRequestEmitted: false,
	}

	report.Mappings = append(report.Mappings,
		exactMapping("ckks_params.LogN", "parameters.log_n"),
		exactMapping("ckks_params.LogQ", "parameters.log_q"),
		exactMapping("ckks_params.LogP", "parameters.log_p"),
		exactMapping(
			"ckks_params.LogScale",
			"parameters.log_default_scale",
		),
	)

	if strings.EqualFold(config.CKKSParams.RingType, "standard") {
		report.Mappings = append(report.Mappings, SemanticMapping{
			SourceField: "ckks_params.RingType",
			TargetField: "Lattigo ring type",
			Status:      MappingExact,
			Detail:      "both runtimes use the standard ring",
		})
	} else {
		report.Mappings = append(report.Mappings, SemanticMapping{
			SourceField: "ckks_params.RingType",
			TargetField: "Lattigo ring type",
			Status:      MappingMismatch,
			Detail: "Orion requests conjugate-invariant packing while " +
				"the frozen FlipGuard candidate runtime uses the standard ring",
		})
		report.BlockReasons = append(
			report.BlockReasons,
			"RING_TYPE_MISMATCH",
		)
	}

	report.Mappings = append(report.Mappings, SemanticMapping{
		SourceField: "ckks_params.H",
		TargetField: "Security V2 runtime Xs",
		Status:      MappingMismatch,
		Detail: fmt.Sprintf(
			"Orion constructs ring.Ternary{H:%d}; Security V2 is fixed to ring.Ternary{P:2/3}",
			config.CKKSParams.H,
		),
	})
	report.BlockReasons = append(
		report.BlockReasons,
		"SECRET_DISTRIBUTION_MISMATCH",
	)

	report.Mappings = append(report.Mappings, SemanticMapping{
		SourceField: "implicit backend Xe",
		TargetField: "Security V2 runtime Xe",
		Status:      MappingUnverified,
		Detail: "the Orion YAML does not serialize Xe; exact equality with " +
			"ring.DiscreteGaussian{Sigma:3.2,Bound:19.2} cannot be proven " +
			"from the candidate artifact alone",
	})
	report.BlockReasons = append(
		report.BlockReasons,
		"ERROR_DISTRIBUTION_NOT_SERIALIZED",
	)

	if input.Backend.Module ==
		"github.com/tuneinsight/lattigo/v6" {
		report.Mappings = append(report.Mappings, SemanticMapping{
			SourceField: "backend.module",
			TargetField: "FlipGuard Lattigo module",
			Status:      MappingExact,
			Detail:      "backend module namespaces match",
		})
	} else {
		report.Mappings = append(report.Mappings, SemanticMapping{
			SourceField: "backend.module",
			TargetField: "FlipGuard Lattigo module",
			Status:      MappingUnverified,
			Detail: "Orion is pinned to a distinct Lattigo fork; " +
				"repository equivalence is not assumed",
		})
		report.BlockReasons = append(
			report.BlockReasons,
			"BACKEND_IMPLEMENTATION_NOT_IDENTICAL",
		)
	}

	assessment, securityErr := ckksplanner.AssessSecurity(
		literal,
		policy.SecurityBits,
		policy,
	)
	if securityErr != nil {
		report.SecurityError = securityErr.Error()
		report.BlockReasons = append(
			report.BlockReasons,
			"SECURITY_POLICY_UNSUPPORTED_LOGN",
		)
	} else {
		report.SecurityAssessment = &assessment
		if assessment.FinalAdmission !=
			ckksplanner.SecurityAdmissionPass {
			report.BlockReasons = append(
				report.BlockReasons,
				"SECURITY_V2_INADMISSIBLE",
			)
		}
	}

	return report, nil
}

func exactMapping(source string, target string) SemanticMapping {
	return SemanticMapping{
		SourceField: source,
		TargetField: target,
		Status:      MappingExact,
		Detail:      "integer values and ordering transfer without conversion",
	}
}

func decodeOrionConfig(data []byte) (orionConfig, error) {
	decoder := yaml.NewDecoder(bytes.NewReader(data))
	decoder.KnownFields(true)
	var config orionConfig
	if err := decoder.Decode(&config); err != nil {
		return orionConfig{}, fmt.Errorf("decode Orion config: %w", err)
	}
	var trailing interface{}
	if err := decoder.Decode(&trailing); err != io.EOF {
		if err == nil {
			err = fmt.Errorf("unexpected trailing YAML document")
		}
		return orionConfig{}, fmt.Errorf("decode Orion config: %w", err)
	}
	return config, nil
}

func validateOrionConfig(config orionConfig) error {
	if !strings.EqualFold(config.Orion.Backend, "lattigo") {
		return fmt.Errorf(
			"Orion backend %q is not Lattigo",
			config.Orion.Backend,
		)
	}
	if config.CKKSParams.LogN <= 0 ||
		config.CKKSParams.LogScale <= 0 ||
		config.CKKSParams.H <= 0 {
		return fmt.Errorf("Orion LogN, LogScale, and H must be positive")
	}
	for name, values := range map[string][]int{
		"LogQ": config.CKKSParams.LogQ,
		"LogP": config.CKKSParams.LogP,
	} {
		if len(values) == 0 {
			return fmt.Errorf("Orion %s is empty", name)
		}
		for index, value := range values {
			if value <= 0 {
				return fmt.Errorf(
					"Orion %s[%d] must be positive",
					name,
					index,
				)
			}
		}
	}
	switch strings.ToLower(config.CKKSParams.RingType) {
	case "standard", "conjugateinvariant":
	default:
		return fmt.Errorf(
			"unsupported Orion ring type %q",
			config.CKKSParams.RingType,
		)
	}
	return nil
}

func validateSourceBinding(
	source ExternalSourceBinding,
	data []byte,
) error {
	if strings.TrimSpace(source.RepositoryURL) == "" ||
		strings.TrimSpace(source.Commit) == "" ||
		strings.TrimSpace(source.Path) == "" {
		return fmt.Errorf("Orion source provenance is incomplete")
	}
	if len(source.Commit) != 40 {
		return fmt.Errorf("Orion source commit must be a full 40-hex SHA")
	}
	if _, err := hex.DecodeString(source.Commit); err != nil {
		return fmt.Errorf("invalid Orion source commit: %w", err)
	}
	actual := digestBytes(data)
	if actual != source.SHA256 {
		return fmt.Errorf(
			"Orion source digest mismatch: got %s want %s",
			actual,
			source.SHA256,
		)
	}
	return nil
}

func validateBackendBinding(backend OrionBackendBinding) error {
	if strings.TrimSpace(backend.Module) == "" ||
		strings.TrimSpace(backend.Version) == "" ||
		len(backend.Commit) != 40 {
		return fmt.Errorf("Orion backend provenance is incomplete")
	}
	if _, err := hex.DecodeString(backend.Commit); err != nil {
		return fmt.Errorf("invalid Orion backend commit: %w", err)
	}
	return nil
}

func digestBytes(data []byte) string {
	sum := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(sum[:])
}
