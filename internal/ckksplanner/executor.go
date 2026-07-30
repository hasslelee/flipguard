package ckksplanner

import (
	"errors"
	"fmt"
	"math"
	"os"
	"sort"
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

	KeyRepeatsRequested int `json:"key_repeats_requested"`
	KeyRepeatsCompleted int `json:"key_repeats_completed"`

	SuccessRuns         int     `json:"success_runs"`
	DecisionFlips       int     `json:"decision_flips"`
	ErrorViolations     int     `json:"error_violations"`
	MaxObservedError    float64 `json:"max_observed_error"`
	MaxErrorBudgetUsage float64 `json:"max_error_budget_usage"`

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

	EncryptedKeyRuns int `json:"encrypted_key_runs"`

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
		TrialIndex:          trialIndex,
		Candidate:           candidate,
		KeyRepeatsRequested: contract.Deployment.ValidationKeyRepeats,
	}

	profile, err := candidate.Profile()
	if err != nil {
		result.Status = certify.StatusFailed
		result.Assurance = certify.AssuranceNone
		result.Reason = "synthesized parameter literal failed backend validation"
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

	keyRepeats := contract.Deployment.ValidationKeyRepeats
	sampleOrder := make([]string, 0)
	plainScores := make(map[string]float64)
	approxBySample := make(map[string][]float64)
	totalLatencies := make([]float64, 0)

	for keyRun := 1; keyRun <= keyRepeats; keyRun++ {
		context, err := ckksbackend.NewContextFromProfile(profile)
		if err != nil {
			result.Status = certify.StatusFailed
			result.Assurance = certify.AssuranceNone
			result.Reason = fmt.Sprintf(
				"synthesized parameter context creation failed for key run %d/%d",
				keyRun,
				keyRepeats,
			)
			result.Failure = err.Error()
			return result, nil
		}

		records, summary, err :=
			context.RunCKKSTabularInference(config)
		if err != nil {
			result.Status = certify.StatusFailed
			result.Assurance = certify.AssuranceNone
			result.Reason = fmt.Sprintf(
				"encrypted validation execution failed for key run %d/%d",
				keyRun,
				keyRepeats,
			)
			result.Failure = err.Error()
			result.FailureSignal =
				classifyExecutionFailure(err)
			return result, nil
		}

		if summary.DatasetID != contract.DatasetID ||
			summary.ModelID != contract.ModelID ||
			summary.ModelType != contract.ModelType {
			return TabularTrialResult{}, fmt.Errorf(
				"backend workload identity mismatch on key run %d: got %s/%s/%s",
				keyRun,
				summary.DatasetID,
				summary.ModelID,
				summary.ModelType,
			)
		}
		if keyRun > 1 && len(records) != len(sampleOrder) {
			return TabularTrialResult{}, fmt.Errorf(
				"backend validation sample count changed on key run %d: got %d expected %d",
				keyRun,
				len(records),
				len(sampleOrder),
			)
		}

		for recordIndex, record := range records {
			sampleID := strconv.Itoa(record.RowID)
			if keyRun == 1 {
				sampleOrder = append(sampleOrder, sampleID)
				plainScores[sampleID] = record.PlainY
				approxBySample[sampleID] =
					make([]float64, 0, keyRepeats)
			} else {
				if sampleOrder[recordIndex] != sampleID {
					return TabularTrialResult{}, fmt.Errorf(
						"backend validation sample order changed on key run %d at index %d: got %s expected %s",
						keyRun,
						recordIndex,
						sampleID,
						sampleOrder[recordIndex],
					)
				}
				if !closeFloat(
					plainScores[sampleID],
					record.PlainY,
				) {
					return TabularTrialResult{}, fmt.Errorf(
						"backend plaintext score changed on key run %d for sample %s",
						keyRun,
						sampleID,
					)
				}
			}

			approxBySample[sampleID] = append(
				approxBySample[sampleID],
				record.CKKSY,
			)
			totalLatencies = append(
				totalLatencies,
				record.TotalEvalMS,
			)
		}
		result.KeyRepeatsCompleted = keyRun
	}

	observedSamples := make(
		[]certify.ObservedSample,
		0,
		len(sampleOrder),
	)
	for _, sampleID := range sampleOrder {
		observedSamples = append(
			observedSamples,
			certify.ObservedSample{
				ID:         sampleID,
				PlainScore: plainScores[sampleID],
				Threshold:  contract.Decision.Threshold,
				ApproxScores: append(
					[]float64(nil),
					approxBySample[sampleID]...,
				),
			},
		)
	}

	observedDigest := digestValidationScores(sampleOrder, plainScores)
	if observedDigest != contract.Decision.ValidationDigest {
		return TabularTrialResult{}, fmt.Errorf(
			"backend validation scope digest %s does not match contract %s",
			observedDigest,
			contract.Decision.ValidationDigest,
		)
	}

	meanTotalMS, medianTotalMS, p95TotalMS, err :=
		summarizeTrialLatencies(totalLatencies)
	if err != nil {
		return TabularTrialResult{}, err
	}

	aggregation, err := certify.AggregateObservedCandidate(
		certify.ObservedCandidateInput{
			Candidate: candidateDescriptor(candidate),
			Samples:   observedSamples,

			MeanTotalMS: meanTotalMS,
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
	if result.SuccessRuns != keyRepeats {
		return TabularTrialResult{}, fmt.Errorf(
			"certificate successful runs %d do not match requested key repeats %d",
			result.SuccessRuns,
			keyRepeats,
		)
	}
	result.DecisionFlips = certificate.DecisionFlips
	result.ErrorViolations = certificate.ErrorViolations
	result.MaxObservedError = certificate.MaxObservedError
	result.MaxErrorBudgetUsage =
		certificate.MaxObservedBudgetUsage
	result.VCert = certificate.VCert
	result.VAmb = certificate.VAmb
	result.MeanTotalMS = meanTotalMS
	result.MedianMS = medianTotalMS
	result.P95MS = p95TotalMS

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
		result.EncryptedKeyRuns += trial.KeyRepeatsCompleted

		if trial.Status == certify.StatusSafe {
			selected := candidate
			result.Outcome = AdaptiveOutcomeSelected
			result.Selected = &selected
			result.Reason = fmt.Sprintf(
				"selected first certified candidate %s after %d encrypted configuration trial(s) and %d key run(s)",
				candidate.ID,
				result.TrialsUsed,
				result.EncryptedKeyRuns,
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

func summarizeTrialLatencies(
	values []float64,
) (mean float64, median float64, p95 float64, err error) {
	if len(values) == 0 {
		return 0, 0, 0, fmt.Errorf(
			"cannot summarize empty encrypted latency observations",
		)
	}

	sorted := append([]float64(nil), values...)
	total := 0.0
	for index, value := range sorted {
		if !finite(value) || value < 0 {
			return 0, 0, 0, fmt.Errorf(
				"encrypted latency observation %d is invalid: %.12g",
				index,
				value,
			)
		}
		total += value
	}
	sort.Float64s(sorted)

	percentile := func(fraction float64) float64 {
		index := int(
			math.Ceil(fraction*float64(len(sorted))),
		) - 1
		if index < 0 {
			index = 0
		}
		if index >= len(sorted) {
			index = len(sorted) - 1
		}
		return sorted[index]
	}

	return total / float64(len(sorted)),
		percentile(0.50),
		percentile(0.95),
		nil
}

func verifyContractArtifacts(contract WorkloadContract) error {
	bindings := []struct {
		label   string
		binding ArtifactBinding
	}{
		{"model artifact", contract.ModelArtifact},
		{"validation data", contract.ValidationData},
	}
	if contract.SourceData != nil {
		bindings = append(bindings, struct {
			label   string
			binding ArtifactBinding
		}{
			label:   "source data",
			binding: *contract.SourceData,
		})
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
		ChainLength: candidate.Parameters.QPrimeCount(),
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
