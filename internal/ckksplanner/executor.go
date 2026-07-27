package ckksplanner

import (
	"errors"
	"fmt"
	"os"
	"strconv"
	"strings"

	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

const (
	AdaptiveOutcomeSelected = "SELECTED"
	AdaptiveOutcomeNoSafe   = "NO_SAFE"
)

// TabularTrialResult records one expensive encrypted validation trial.
type TabularTrialResult struct {
	TrialIndex int `json:"trial_index"`

	Candidate SynthesizedCandidate `json:"candidate"`

	Status    certify.CandidateStatus `json:"status"`
	Assurance certify.AssuranceLevel  `json:"assurance"`
	Reason    string                  `json:"reason"`

	FailureSignal RepairSignal `json:"failure_signal,omitempty"`
	Failure       string       `json:"failure,omitempty"`

	SuccessRuns      int     `json:"success_runs"`
	DecisionFlips    int     `json:"decision_flips"`
	ErrorViolations  int     `json:"error_violations"`
	MaxObservedError float64 `json:"max_observed_error"`

	VCert int `json:"v_cert"`
	VAmb  int `json:"v_amb"`

	MeanTotalMS float64 `json:"mean_total_ms"`
	MedianMS    float64 `json:"median_total_ms"`
	P95MS       float64 `json:"p95_total_ms"`
}

// AdaptiveAutotuneResult is the end-to-end first-party planner result.
type AdaptiveAutotuneResult struct {
	SchemaVersion int `json:"schema_version"`

	Plan SynthesisPlan `json:"plan"`

	Outcome string `json:"outcome"`
	Reason  string `json:"reason"`

	TrialsUsed int                  `json:"trials_used"`
	Trials     []TabularTrialResult `json:"trials"`

	Selected *SynthesizedCandidate `json:"selected,omitempty"`
}

// ExecuteTabularCandidate runs one synthesized profile on the exact validation
// artifact and applies FlipGuard's observed-validation certificate.
func ExecuteTabularCandidate(
	contract WorkloadContract,
	candidate SynthesizedCandidate,
	trialIndex int,
) (TabularTrialResult, error) {
	if err := contract.Validate(); err != nil {
		return TabularTrialResult{}, fmt.Errorf(
			"validate execution contract: %w",
			err,
		)
	}
	if trialIndex <= 0 {
		return TabularTrialResult{}, fmt.Errorf(
			"trial index must be positive",
		)
	}
	if err := verifyContractArtifacts(contract); err != nil {
		return TabularTrialResult{}, err
	}

	result := TabularTrialResult{
		TrialIndex: trialIndex,
		Candidate:  candidate,
	}

	profile, err := candidate.Profile()
	if err != nil {
		result.Status = certify.StatusFailed
		result.Assurance = certify.AssuranceNone
		result.Reason = "synthesized parameter literal failed backend validation"
		result.Failure = err.Error()
		return result, nil
	}

	context, err := ckksbackend.NewContextFromProfile(profile)
	if err != nil {
		result.Status = certify.StatusFailed
		result.Assurance = certify.AssuranceNone
		result.Reason = "synthesized parameter context creation failed"
		result.Failure = err.Error()
		return result, nil
	}

	evaluationMode, err := evaluationModeForCandidate(candidate)
	if err != nil {
		return TabularTrialResult{}, err
	}

	config := ckksbackend.DefaultCKKSTabularInferenceConfig(
		contract.DatasetID,
		contract.ModelID,
	)
	config.ModelPath = contract.ModelArtifact.Path
	config.TestPath = contract.ValidationData.Path
	config.EvaluationMode = evaluationMode

	// The certification engine below applies the sample-specific strict margin
	// budget. Backend-global error caps are deliberately permissive here.
	config.ScoreAbsErrorCap = 1
	config.ScoreRelErrorCap = 1

	records, summary, err := context.RunCKKSTabularInference(config)
	if err != nil {
		result.Status = certify.StatusFailed
		result.Assurance = certify.AssuranceNone
		result.Reason = "encrypted validation execution failed"
		result.Failure = err.Error()
		result.FailureSignal = classifyExecutionFailure(err)
		return result, nil
	}

	if summary.DatasetID != contract.DatasetID ||
		summary.ModelID != contract.ModelID ||
		summary.ModelType != contract.ModelType {
		return TabularTrialResult{}, fmt.Errorf(
			"backend workload identity mismatch: got %s/%s/%s",
			summary.DatasetID,
			summary.ModelID,
			summary.ModelType,
		)
	}

	observedSamples := make(
		[]certify.ObservedSample,
		0,
		len(records),
	)
	sampleOrder := make([]string, 0, len(records))
	plainScores := make(map[string]float64, len(records))

	for _, record := range records {
		sampleID := strconv.Itoa(record.RowID)
		observedSamples = append(
			observedSamples,
			certify.ObservedSample{
				ID:           sampleID,
				PlainScore:   record.PlainY,
				Threshold:    contract.Decision.Threshold,
				ApproxScores: []float64{record.CKKSY},
			},
		)
		sampleOrder = append(sampleOrder, sampleID)
		plainScores[sampleID] = record.PlainY
	}

	observedDigest := digestValidationScores(sampleOrder, plainScores)
	if observedDigest != contract.Decision.ValidationDigest {
		return TabularTrialResult{}, fmt.Errorf(
			"backend validation scope digest %s does not match contract %s",
			observedDigest,
			contract.Decision.ValidationDigest,
		)
	}

	aggregation, err := certify.AggregateObservedCandidate(
		certify.ObservedCandidateInput{
			Candidate: candidateDescriptor(candidate),
			Samples:   observedSamples,

			MeanTotalMS: summary.MeanTotalEvalMS,
		},
		contract.Decision.MarginFloor,
		contract.Decision.SafetyFactor,
	)
	if err != nil {
		return TabularTrialResult{}, fmt.Errorf(
			"aggregate encrypted validation: %w",
			err,
		)
	}
	if aggregation.Coverage.VCert !=
		contract.Decision.CertifiableSamples ||
		aggregation.Coverage.VAmb !=
			contract.Decision.AmbiguousSamples {
		return TabularTrialResult{}, fmt.Errorf(
			"backend validation partition Vcert=%d Vamb=%d does not match contract Vcert=%d Vamb=%d",
			aggregation.Coverage.VCert,
			aggregation.Coverage.VAmb,
			contract.Decision.CertifiableSamples,
			contract.Decision.AmbiguousSamples,
		)
	}

	policy := certify.DefaultCertificationPolicy()
	policy.SafetyFactor = contract.Decision.SafetyFactor

	certificate, err := certify.BuildCandidateCertificateWithPolicy(
		aggregation.Evidence,
		aggregation.Coverage,
		policy,
	)
	if err != nil {
		return TabularTrialResult{}, fmt.Errorf(
			"build encrypted validation certificate: %w",
			err,
		)
	}

	result.Status = certificate.Status
	result.Assurance = certificate.Assurance
	result.Reason = certificate.Reason
	result.SuccessRuns = certificate.SuccessRuns
	result.DecisionFlips = certificate.DecisionFlips
	result.ErrorViolations = certificate.ErrorViolations
	result.MaxObservedError = certificate.MaxObservedError
	result.VCert = certificate.VCert
	result.VAmb = certificate.VAmb
	result.MeanTotalMS = summary.MeanTotalEvalMS
	result.MedianMS = summary.MedianTotalEvalMS
	result.P95MS = summary.P95TotalEvalMS

	if certificate.Status == certify.StatusRejected {
		result.FailureSignal = RepairNumericalReject
	}

	return result, nil
}

// RunAdaptiveTabularAutotune evaluates the analysis-derived initial candidate
// and creates another candidate only in response to observed failure.
func RunAdaptiveTabularAutotune(
	plan SynthesisPlan,
) (AdaptiveAutotuneResult, error) {
	if plan.SchemaVersion != SynthesisPlanSchemaVersion {
		return AdaptiveAutotuneResult{}, fmt.Errorf(
			"unsupported synthesis plan schema version %d",
			plan.SchemaVersion,
		)
	}
	if len(plan.InitialCandidates) != 1 {
		return AdaptiveAutotuneResult{}, fmt.Errorf(
			"adaptive v1 requires exactly one initial candidate, got %d",
			len(plan.InitialCandidates),
		)
	}

	recomputedDigest, err := digestContract(plan.Contract)
	if err != nil {
		return AdaptiveAutotuneResult{}, err
	}
	if recomputedDigest != plan.ContractDigest {
		return AdaptiveAutotuneResult{}, fmt.Errorf(
			"synthesis plan contract digest mismatch",
		)
	}

	result := AdaptiveAutotuneResult{
		SchemaVersion: SynthesisPlanSchemaVersion,
		Plan:          plan,
		Trials:        make([]TabularTrialResult, 0),
	}

	candidate := plan.InitialCandidates[0]
	maxTrials := plan.Contract.Deployment.MaxEncryptedTrials

	for trialIndex := 1; trialIndex <= maxTrials; trialIndex++ {
		trial, err := ExecuteTabularCandidate(
			plan.Contract,
			candidate,
			trialIndex,
		)
		if err != nil {
			return AdaptiveAutotuneResult{}, err
		}
		result.Trials = append(result.Trials, trial)
		result.TrialsUsed = len(result.Trials)

		if trial.Status == certify.StatusSafe {
			selected := candidate
			result.Outcome = AdaptiveOutcomeSelected
			result.Selected = &selected
			result.Reason = fmt.Sprintf(
				"selected first certified candidate %s after %d encrypted trial(s)",
				candidate.ID,
				result.TrialsUsed,
			)
			return result, nil
		}

		if trialIndex == maxTrials {
			break
		}
		if trial.FailureSignal == "" {
			result.Outcome = AdaptiveOutcomeNoSafe
			result.Reason = fmt.Sprintf(
				"no declared monotone repair for candidate status=%s failure=%s",
				trial.Status,
				trial.Failure,
			)
			return result, nil
		}

		next, err := RepairCandidate(
			plan,
			candidate,
			trial.FailureSignal,
			trialIndex,
		)
		if err != nil {
			if errors.Is(err, ErrRepairExhausted) {
				result.Outcome = AdaptiveOutcomeNoSafe
				result.Reason = err.Error()
				return result, nil
			}
			return AdaptiveAutotuneResult{}, err
		}
		candidate = next
	}

	result.Outcome = AdaptiveOutcomeNoSafe
	result.Reason = fmt.Sprintf(
		"no SAFE candidate within encrypted trial budget %d",
		maxTrials,
	)
	return result, nil
}

func verifyContractArtifacts(contract WorkloadContract) error {
	bindings := []struct {
		label   string
		binding ArtifactBinding
	}{
		{"model artifact", contract.ModelArtifact},
		{"validation data", contract.ValidationData},
	}

	for _, item := range bindings {
		data, err := os.ReadFile(item.binding.Path)
		if err != nil {
			return fmt.Errorf(
				"read %s for digest verification: %w",
				item.label,
				err,
			)
		}
		actual := digestBytes(data)
		if actual != item.binding.SHA256 {
			return fmt.Errorf(
				"%s digest changed: got %s expected %s",
				item.label,
				actual,
				item.binding.SHA256,
			)
		}
	}
	return nil
}

func evaluationModeForCandidate(
	candidate SynthesizedCandidate,
) (string, error) {
	switch candidate.Path {
	case "rescale":
		return ckksbackend.CKKSEvaluationModeRescale, nil
	case "non-rescale":
		return ckksbackend.CKKSEvaluationModeNaive, nil
	default:
		return "", fmt.Errorf(
			"unsupported synthesized candidate path %q",
			candidate.Path,
		)
	}
}

func candidateDescriptor(
	candidate SynthesizedCandidate,
) certify.CandidateDescriptor {
	return certify.CandidateDescriptor{
		ID:   candidate.ID,
		Path: string(candidate.Path),

		LogN:        candidate.Parameters.LogN,
		Slots:       1 << (candidate.Parameters.LogN - 1),
		ChainLength: len(candidate.Parameters.LogQ),
		ScaleBits:   candidate.Parameters.LogDefaultScale,

		Family:      candidate.GenerationKind,
		IsReference: false,
	}
}

func classifyExecutionFailure(err error) RepairSignal {
	message := strings.ToLower(err.Error())
	if strings.Contains(message, "level") ||
		strings.Contains(message, "rescale") {
		return RepairLevelFailure
	}
	return ""
}
