package decisionactivation

import (
	"bytes"
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strconv"

	"github.com/hasslelee/flipguard/internal/ckksplanner"
	"github.com/hasslelee/flipguard/internal/tuner"
)

const (
	SchemaVersion = "flipguard_decision_contract_activation_control_v1"
	ModelWeight   = 512.0
)

type InputArtifact struct {
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
	Rows   int    `json:"rows,omitempty"`
}

type CandidateRecord struct {
	ID             string                               `json:"id"`
	Parameters     ckksplanner.CKKSParameterLiteralSpec `json:"parameters"`
	Security       ckksplanner.SecurityAssessment       `json:"security"`
	PrecisionBits  int                                  `json:"precision_target_bits"`
	GenerationKind string                               `json:"generation_kind"`
	Reason         string                               `json:"reason"`
}

type RegimeAnalysis struct {
	ID                      string             `json:"id"`
	SplitSeed               int                `json:"split_seed"`
	Validation              InputArtifact      `json:"validation"`
	LockedAudit             InputArtifact      `json:"locked_audit"`
	SplitManifest           InputArtifact      `json:"split_manifest"`
	ProtectedMargin         float64            `json:"protected_margin"`
	OutputErrorBudget       float64            `json:"output_error_budget"`
	AggregateSensitivity    float64            `json:"aggregate_sensitivity"`
	MaxInputAbs             float64            `json:"max_input_abs"`
	MaxOutputAbs            float64            `json:"max_output_abs"`
	Graph                   tuner.GraphSummary `json:"graph"`
	GraphFixed              CandidateRecord    `json:"graph_fixed"`
	DecisionContract        CandidateRecord    `json:"decision_contract"`
	LiteralParametersDiffer bool               `json:"literal_parameters_differ"`
}

type Analysis struct {
	SchemaVersion        string           `json:"schema_version"`
	SourceCommit         string           `json:"source_commit"`
	DirectPolicyDigest   string           `json:"direct_policy_digest"`
	SecurityPolicyDigest string           `json:"security_policy_digest"`
	PrimaryAlpha         float64          `json:"primary_alpha"`
	PrimaryMarginFloor   float64          `json:"primary_margin_floor"`
	FixedTolerance       float64          `json:"fixed_tolerance"`
	EncryptedExecutions  int              `json:"encrypted_executions"`
	PolicyModifications  int              `json:"policy_modifications"`
	Model                InputArtifact    `json:"model"`
	Regimes              []RegimeAnalysis `json:"regimes"`
	StaticClaimState     string           `json:"static_claim_state"`
	PaperClaimAllowed    bool             `json:"paper_claim_allowed"`
}

type regimeSpec struct {
	ID                 string
	SplitSeed          int
	ValidationRowStart int
	AuditRowStart      int
	ValidationZAbs     []float64
	AuditZAbs          []float64
}

var regimes = []regimeSpec{
	{
		ID:                 "narrow_margin",
		SplitSeed:          9101,
		ValidationRowStart: 9101000,
		AuditRowStart:      9101500,
		ValidationZAbs: []float64{
			0.0061, 0.1, 1, 2,
			3, 4, 5, 6,
			10, 20, 30, 40,
			50, 60, 80, 100,
		},
		AuditZAbs: []float64{
			0.00605, 0.09, 0.9, 1.9,
			2.9, 3.9, 4.9, 5.9,
			9, 19, 29, 39,
			49, 59, 79, 99,
		},
	},
	{
		ID:                 "wide_margin",
		SplitSeed:          9102,
		ValidationRowStart: 9102000,
		AuditRowStart:      9102500,
		ValidationZAbs: []float64{
			0.06, 0.1, 1, 2,
			3, 4, 5, 6,
			10, 20, 30, 40,
			50, 60, 80, 100,
		},
		AuditZAbs: []float64{
			0.055, 0.09, 0.9, 1.9,
			2.9, 3.9, 4.9, 5.9,
			9, 19, 29, 39,
			49, 59, 79, 99,
		},
	},
}

func score(z float64) float64 {
	return 0.5 + 0.197*z - 0.004*z*z*z
}

func digest(data []byte) string {
	sum := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(sum[:])
}

func writeExclusive(path string, data []byte) error {
	handle, err := os.OpenFile(
		path,
		os.O_WRONLY|os.O_CREATE|os.O_EXCL,
		0o644,
	)
	if err != nil {
		return err
	}
	defer handle.Close()
	if _, err := handle.Write(data); err != nil {
		return err
	}
	return handle.Sync()
}

func modelBytes() ([]byte, error) {
	model := map[string]any{
		"dataset_id":   "decision_activation_control",
		"dataset_name": "Finite-domain decision-contract activation control",
		"model_id":     "decision_activation_linear_poly3",
		"model_type":   "linear_poly3",
		"task":         "binary threshold control",
		"input_dim":    1,
		"scaled_model_for_ckks": map[string]any{
			"weights": []float64{ModelWeight},
			"bias":    0.0,
		},
		"polynomial_score": map[string]any{
			"formula":            "0.5 + 0.197*z - 0.004*z^3",
			"decision_threshold": 0.5,
		},
	}
	encoded, err := json.MarshalIndent(model, "", "  ")
	if err != nil {
		return nil, err
	}
	return append(encoded, '\n'), nil
}

func csvBytes(
	startRowID int,
	zAbs []float64,
) ([]byte, []string, error) {
	var buffer bytes.Buffer
	writer := csv.NewWriter(&buffer)
	if err := writer.Write([]string{
		"row_id",
		"polynomial_score",
		"plaintext_decision",
		"x_0",
	}); err != nil {
		return nil, nil, err
	}
	rowIDs := make([]string, 0, len(zAbs)*2)
	for index, magnitude := range zAbs {
		for signIndex, sign := range []float64{-1, 1} {
			z := sign * magnitude
			rowID := strconv.Itoa(
				startRowID + index*2 + signIndex,
			)
			rowIDs = append(rowIDs, rowID)
			if err := writer.Write([]string{
				rowID,
				strconv.FormatFloat(score(z), 'g', 17, 64),
				strconv.FormatBool(score(z) >= 0.5),
				strconv.FormatFloat(z/ModelWeight, 'g', 17, 64),
			}); err != nil {
				return nil, nil, err
			}
		}
	}
	writer.Flush()
	if err := writer.Error(); err != nil {
		return nil, nil, err
	}
	return append([]byte(nil), buffer.Bytes()...), rowIDs, nil
}

func candidateRecord(
	candidate ckksplanner.SynthesizedCandidate,
) CandidateRecord {
	return CandidateRecord{
		ID:             candidate.ID,
		Parameters:     candidate.Parameters,
		Security:       candidate.Security,
		PrecisionBits:  candidate.PrecisionTargetBits,
		GenerationKind: candidate.GenerationKind,
		Reason:         candidate.Reason,
	}
}

func parametersEqual(
	left ckksplanner.CKKSParameterLiteralSpec,
	right ckksplanner.CKKSParameterLiteralSpec,
) bool {
	leftJSON, _ := json.Marshal(left)
	rightJSON, _ := json.Marshal(right)
	return string(leftJSON) == string(rightJSON)
}

func WriteAndAnalyze(
	outputRoot string,
	sourceCommit string,
) (Analysis, error) {
	if sourceCommit == "" {
		return Analysis{}, fmt.Errorf("source commit is empty")
	}
	if err := os.MkdirAll(filepath.Dir(outputRoot), 0o755); err != nil {
		return Analysis{}, fmt.Errorf(
			"create control output parent: %w",
			err,
		)
	}
	if err := os.Mkdir(outputRoot, 0o755); err != nil {
		return Analysis{}, fmt.Errorf(
			"create control output root: %w",
			err,
		)
	}

	modelData, err := modelBytes()
	if err != nil {
		return Analysis{}, err
	}
	modelPath := filepath.Join(outputRoot, "model.json")
	if err := writeExclusive(modelPath, modelData); err != nil {
		return Analysis{}, fmt.Errorf("write model: %w", err)
	}

	directPolicyDigest := ckksplanner.MustDefaultDirectSynthesisPolicyDigest()
	securityPolicyDigest, err := ckksplanner.SecurityPolicyDigest(
		ckksplanner.DefaultSecurityEnvelope(),
	)
	if err != nil {
		return Analysis{}, err
	}
	directPolicy := ckksplanner.DefaultDirectSynthesisPolicyContract()
	analysis := Analysis{
		SchemaVersion:        SchemaVersion,
		SourceCommit:         sourceCommit,
		DirectPolicyDigest:   directPolicyDigest,
		SecurityPolicyDigest: securityPolicyDigest,
		PrimaryAlpha:         directPolicy.PrimaryAlpha,
		PrimaryMarginFloor:   directPolicy.PrimaryMarginFloor,
		FixedTolerance:       0.001,
		EncryptedExecutions:  0,
		PolicyModifications:  0,
		Model: InputArtifact{
			Path:   modelPath,
			SHA256: digest(modelData),
		},
		PaperClaimAllowed: false,
	}

	for _, regime := range regimes {
		validationData, validationIDs, err := csvBytes(
			regime.ValidationRowStart,
			regime.ValidationZAbs,
		)
		if err != nil {
			return Analysis{}, err
		}
		auditData, auditIDs, err := csvBytes(
			regime.AuditRowStart,
			regime.AuditZAbs,
		)
		if err != nil {
			return Analysis{}, err
		}
		validationPath := filepath.Join(
			outputRoot,
			regime.ID+"_validation.csv",
		)
		auditPath := filepath.Join(
			outputRoot,
			regime.ID+"_locked_audit.csv",
		)
		if err := writeExclusive(validationPath, validationData); err != nil {
			return Analysis{}, err
		}
		if err := writeExclusive(auditPath, auditData); err != nil {
			return Analysis{}, err
		}

		manifest := map[string]any{
			"schema_version":        1,
			"split_seed":            regime.SplitSeed,
			"dataset_id":            "decision_activation_control",
			"model_id":              "decision_activation_linear_poly3",
			"model_artifact_digest": digest(modelData),
			"configuration_validation": map[string]any{
				"path":       validationPath,
				"csv_digest": digest(validationData),
				"row_ids":    validationIDs,
			},
			"locked_audit_test": map[string]any{
				"path":       auditPath,
				"csv_digest": digest(auditData),
				"row_ids":    auditIDs,
			},
		}
		manifestData, err := json.MarshalIndent(manifest, "", "  ")
		if err != nil {
			return Analysis{}, err
		}
		manifestData = append(manifestData, '\n')
		manifestPath := filepath.Join(
			outputRoot,
			regime.ID+"_split_manifest.json",
		)
		if err := writeExclusive(manifestPath, manifestData); err != nil {
			return Analysis{}, err
		}

		options := ckksplanner.DefaultPrimaryTabularContractOptions()
		options.ModelPath = modelPath
		options.ValidationPath = validationPath
		options.SplitID = fmt.Sprintf("split_seed_%d", regime.SplitSeed)
		contract, err := ckksplanner.BuildTabularWorkloadContract(options)
		if err != nil {
			return Analysis{}, fmt.Errorf(
				"build %s contract: %w",
				regime.ID,
				err,
			)
		}

		fullPolicy := ckksplanner.DefaultPrimarySynthesisPolicy()
		fullPlan, err := ckksplanner.Synthesize(contract, fullPolicy)
		if err != nil {
			return Analysis{}, fmt.Errorf(
				"synthesize %s decision contract: %w",
				regime.ID,
				err,
			)
		}
		graphPolicy := ckksplanner.DefaultPrimarySynthesisPolicy()
		graphPolicy.SynthesisBudgetMode =
			ckksplanner.SynthesisBudgetGraphFixedTolerance
		graphPolicy.FixedOutputErrorBudget = 0.001
		graphPlan, err := ckksplanner.Synthesize(contract, graphPolicy)
		if err != nil {
			return Analysis{}, fmt.Errorf(
				"synthesize %s graph-fixed contract: %w",
				regime.ID,
				err,
			)
		}

		fullCandidate := fullPlan.InitialCandidates[0]
		graphCandidate := graphPlan.InitialCandidates[0]
		analysis.Regimes = append(
			analysis.Regimes,
			RegimeAnalysis{
				ID:        regime.ID,
				SplitSeed: regime.SplitSeed,
				Validation: InputArtifact{
					Path:   validationPath,
					SHA256: digest(validationData),
					Rows:   len(validationIDs),
				},
				LockedAudit: InputArtifact{
					Path:   auditPath,
					SHA256: digest(auditData),
					Rows:   len(auditIDs),
				},
				SplitManifest: InputArtifact{
					Path:   manifestPath,
					SHA256: digest(manifestData),
				},
				ProtectedMargin:      contract.Decision.ProtectedMargin,
				OutputErrorBudget:    contract.Decision.OutputErrorBudget,
				AggregateSensitivity: contract.Calibration.AggregateSensitivity,
				MaxInputAbs:          contract.Calibration.MaxInputAbs,
				MaxOutputAbs:         contract.Calibration.MaxPlaintextOutputAbs,
				Graph:                contract.Graph,
				GraphFixed:           candidateRecord(graphCandidate),
				DecisionContract:     candidateRecord(fullCandidate),
				LiteralParametersDiffer: !parametersEqual(
					graphCandidate.Parameters,
					fullCandidate.Parameters,
				),
			},
		)
	}

	if len(analysis.Regimes) != 2 {
		return Analysis{}, fmt.Errorf("expected two control regimes")
	}
	narrow := analysis.Regimes[0]
	wide := analysis.Regimes[1]
	if narrow.AggregateSensitivity != wide.AggregateSensitivity ||
		narrow.MaxInputAbs != wide.MaxInputAbs ||
		narrow.MaxOutputAbs != wide.MaxOutputAbs {
		return Analysis{}, fmt.Errorf(
			"control calibration differs beyond decision margin",
		)
	}
	if !parametersEqual(
		narrow.GraphFixed.Parameters,
		wide.GraphFixed.Parameters,
	) {
		return Analysis{}, fmt.Errorf(
			"graph-fixed literal changed between regimes",
		)
	}
	if !narrow.LiteralParametersDiffer ||
		wide.LiteralParametersDiffer ||
		parametersEqual(
			narrow.DecisionContract.Parameters,
			wide.DecisionContract.Parameters,
		) {
		analysis.StaticClaimState = "BLOCKED"
	} else {
		analysis.StaticClaimState = "SUPPORTED"
	}

	encoded, err := json.MarshalIndent(analysis, "", "  ")
	if err != nil {
		return Analysis{}, err
	}
	if err := writeExclusive(
		filepath.Join(outputRoot, "static_analysis.json"),
		append(encoded, '\n'),
	); err != nil {
		return Analysis{}, err
	}
	return analysis, nil
}
