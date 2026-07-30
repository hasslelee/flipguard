package ckksplanner

import (
	"errors"
	"fmt"
	"math"
	"strconv"

	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

type CNNLiteSampleObservation struct {
	KeyRun int `json:"key_run"`

	RowID           int    `json:"row_id"`
	SampleID        string `json:"sample_id"`
	SourcePartition string `json:"source_partition"`
	DigitLabel      int    `json:"digit_label"`

	PlainScore float64 `json:"plain_score"`
	CKKSScore  float64 `json:"ckks_score"`
	Threshold  float64 `json:"threshold"`
	Margin     float64 `json:"margin"`
	AbsError   float64 `json:"abs_error"`

	Certifiable      bool    `json:"certifiable"`
	ErrorBudget      float64 `json:"error_budget"`
	ErrorBudgetUsage float64 `json:"error_budget_usage"`
	ErrorViolation   bool    `json:"error_violation"`

	PlainDecision bool `json:"plain_decision"`
	CKKSDecision  bool `json:"ckks_decision"`
	DecisionFlip  bool `json:"decision_flip"`

	EncodeEncryptMS float64 `json:"encode_encrypt_ms"`
	EvalOnlyMS      float64 `json:"eval_only_ms"`
	DecryptDecodeMS float64 `json:"decrypt_decode_ms"`
	TotalEvalMS     float64 `json:"total_eval_ms"`
}

type CNNLiteTrialResult struct {
	TrialIndex int                  `json:"trial_index"`
	Candidate  SynthesizedCandidate `json:"candidate"`

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

	EncryptedSampleEvaluations int     `json:"encrypted_sample_evaluations"`
	MeanTotalMS                float64 `json:"mean_total_ms"`
	MedianMS                   float64 `json:"median_total_ms"`
	P95MS                      float64 `json:"p95_total_ms"`

	SampleLedger []CNNLiteSampleObservation `json:"sample_ledger"`
}

type AdaptiveCNNLiteAutotuneResult struct {
	SchemaVersion int `json:"schema_version"`

	ExecutionAdapter string        `json:"execution_adapter"`
	Plan             SynthesisPlan `json:"plan"`

	Outcome string `json:"outcome"`
	Reason  string `json:"reason"`

	TrialsUsed int                  `json:"trials_used"`
	Trials     []CNNLiteTrialResult `json:"trials"`

	EncryptedKeyRuns           int `json:"encrypted_key_runs"`
	EncryptedSampleEvaluations int `json:"encrypted_sample_evaluations"`

	Selected *SynthesizedCandidate `json:"selected,omitempty"`
}

func ExecuteCNNLiteCandidate(
	contract WorkloadContract,
	candidate SynthesizedCandidate,
	trialIndex int,
) (CNNLiteTrialResult, error) {
	if err := contract.Validate(); err != nil {
		return CNNLiteTrialResult{}, fmt.Errorf(
			"validate CNN-lite execution contract: %w",
			err,
		)
	}
	if contract.ModelType != MNISTCNNLiteModelType {
		return CNNLiteTrialResult{}, fmt.Errorf(
			"unsupported CNN-lite contract model_type %q",
			contract.ModelType,
		)
	}
	if trialIndex <= 0 {
		return CNNLiteTrialResult{}, fmt.Errorf(
			"trial index must be positive",
		)
	}
	if err := verifyContractArtifacts(contract); err != nil {
		return CNNLiteTrialResult{}, err
	}
	result := CNNLiteTrialResult{
		TrialIndex:          trialIndex,
		Candidate:           candidate,
		KeyRepeatsRequested: contract.Deployment.ValidationKeyRepeats,
		SampleLedger: make(
			[]CNNLiteSampleObservation,
			0,
			contract.Decision.ValidationSamples*
				contract.Deployment.ValidationKeyRepeats,
		),
	}
	profile, err := candidate.Profile()
	if err != nil {
		result.Status = certify.StatusFailed
		result.Assurance = certify.AssuranceNone
		result.Reason =
			"synthesized parameter literal failed backend validation"
		result.Failure = err.Error()
		return result, nil
	}
	if candidate.Path != "rescale" {
		return CNNLiteTrialResult{}, fmt.Errorf(
			"CNN-lite adapter requires rescale-aware candidate",
		)
	}

	sampleOrder := make([]string, 0)
	plainScores := make(map[string]float64)
	approxBySample := make(map[string][]float64)
	totalLatencies := make([]float64, 0)
	for keyRun := 1; keyRun <= contract.Deployment.ValidationKeyRepeats; keyRun++ {
		context, err := ckksbackend.NewContextFromProfile(profile)
		if err != nil {
			result.Status = certify.StatusFailed
			result.Assurance = certify.AssuranceNone
			result.Reason = "create CKKS context failed"
			result.Failure = err.Error()
			result.FailureSignal = classifyExecutionFailure(err)
			return result, nil
		}
		records, err := context.RunCKKSCNNLiteInference(
			ckksbackend.CKKSCNNLiteConfig{
				ModelPath: contract.ModelArtifact.Path,
				DataPath:  contract.ValidationData.Path,
			},
		)
		if err != nil {
			result.Status = certify.StatusFailed
			result.Assurance = certify.AssuranceNone
			result.Reason = "encrypted CNN-lite execution failed"
			result.Failure = err.Error()
			result.FailureSignal = classifyExecutionFailure(err)
			return result, nil
		}
		if keyRun > 1 && len(records) != len(sampleOrder) {
			return CNNLiteTrialResult{}, fmt.Errorf(
				"CNN-lite sample count changed on key run %d",
				keyRun,
			)
		}
		for index, record := range records {
			sampleID := strconv.Itoa(record.RowID)
			if keyRun == 1 {
				sampleOrder = append(sampleOrder, sampleID)
				plainScores[sampleID] = record.PlainScore
				approxBySample[sampleID] = make(
					[]float64,
					0,
					contract.Deployment.ValidationKeyRepeats,
				)
			} else if sampleOrder[index] != sampleID ||
				!closeFloat(
					plainScores[sampleID],
					record.PlainScore,
				) {
				return CNNLiteTrialResult{}, fmt.Errorf(
					"CNN-lite sample identity changed on key run %d at index %d",
					keyRun,
					index,
				)
			}
			approxBySample[sampleID] = append(
				approxBySample[sampleID],
				record.CKKSScore,
			)
			totalLatencies = append(
				totalLatencies,
				record.TotalEvalMS,
			)
			margin := math.Abs(
				record.PlainScore -
					contract.Decision.Threshold,
			)
			certifiable :=
				margin > contract.Decision.MarginFloor
			errorBudget := 0.0
			errorBudgetUsage := 0.0
			errorViolation := false
			if certifiable {
				errorBudget =
					contract.Decision.SafetyFactor * margin
				errorBudgetUsage =
					record.AbsError / errorBudget
				errorViolation =
					record.AbsError >= errorBudget
			}
			result.SampleLedger = append(
				result.SampleLedger,
				CNNLiteSampleObservation{
					KeyRun:           keyRun,
					RowID:            record.RowID,
					SampleID:         record.SampleID,
					SourcePartition:  record.SourcePartition,
					DigitLabel:       record.DigitLabel,
					PlainScore:       record.PlainScore,
					CKKSScore:        record.CKKSScore,
					Threshold:        contract.Decision.Threshold,
					Margin:           margin,
					AbsError:         record.AbsError,
					Certifiable:      certifiable,
					ErrorBudget:      errorBudget,
					ErrorBudgetUsage: errorBudgetUsage,
					ErrorViolation:   errorViolation,
					PlainDecision:    record.PlainDecision,
					CKKSDecision:     record.CKKSDecision,
					DecisionFlip:     record.DecisionFlip,
					EncodeEncryptMS:  record.EncodeEncryptMS,
					EvalOnlyMS:       record.EvalOnlyMS,
					DecryptDecodeMS:  record.DecryptDecodeMS,
					TotalEvalMS:      record.TotalEvalMS,
				},
			)
		}
		result.KeyRepeatsCompleted = keyRun
		result.EncryptedSampleEvaluations += len(records)
	}
	if digestValidationScores(sampleOrder, plainScores) !=
		contract.Decision.ValidationDigest {
		return CNNLiteTrialResult{}, fmt.Errorf(
			"CNN-lite backend validation scope digest mismatch",
		)
	}

	observed := make([]certify.ObservedSample, 0, len(sampleOrder))
	for _, sampleID := range sampleOrder {
		observed = append(observed, certify.ObservedSample{
			ID:         sampleID,
			PlainScore: plainScores[sampleID],
			Threshold:  contract.Decision.Threshold,
			ApproxScores: append(
				[]float64(nil),
				approxBySample[sampleID]...,
			),
		})
	}
	mean, median, p95, err := summarizeTrialLatencies(totalLatencies)
	if err != nil {
		return CNNLiteTrialResult{}, err
	}
	aggregation, err := certify.AggregateObservedCandidate(
		certify.ObservedCandidateInput{
			Candidate:   candidateDescriptor(candidate),
			Samples:     observed,
			MeanTotalMS: mean,
		},
		contract.Decision.MarginFloor,
		contract.Decision.SafetyFactor,
	)
	if err != nil {
		return CNNLiteTrialResult{}, fmt.Errorf(
			"aggregate CNN-lite encrypted validation: %w",
			err,
		)
	}
	if aggregation.Coverage.VCert !=
		contract.Decision.CertifiableSamples ||
		aggregation.Coverage.VAmb !=
			contract.Decision.AmbiguousSamples {
		return CNNLiteTrialResult{}, fmt.Errorf(
			"CNN-lite certification partition does not match contract",
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
		return CNNLiteTrialResult{}, err
	}
	result.Status = certificate.Status
	result.Assurance = certificate.Assurance
	result.Reason = certificate.Reason
	result.SuccessRuns = certificate.SuccessRuns
	result.DecisionFlips = certificate.DecisionFlips
	result.ErrorViolations = certificate.ErrorViolations
	result.MaxObservedError = certificate.MaxObservedError
	result.MaxErrorBudgetUsage =
		certificate.MaxObservedBudgetUsage
	result.VCert = certificate.VCert
	result.VAmb = certificate.VAmb
	result.MeanTotalMS = mean
	result.MedianMS = median
	result.P95MS = p95
	if result.SuccessRuns !=
		contract.Deployment.ValidationKeyRepeats {
		return CNNLiteTrialResult{}, fmt.Errorf(
			"CNN-lite certificate key run count mismatch",
		)
	}
	if certificate.Status == certify.StatusRejected {
		result.FailureSignal = RepairNumericalReject
	}
	return result, nil
}

func RunAdaptiveCNNLiteAutotune(
	plan SynthesisPlan,
) (AdaptiveCNNLiteAutotuneResult, error) {
	if plan.SchemaVersion != SynthesisPlanSchemaVersion ||
		len(plan.InitialCandidates) != 1 {
		return AdaptiveCNNLiteAutotuneResult{}, fmt.Errorf(
			"invalid CNN-lite synthesis plan",
		)
	}
	recomputedDigest, err := digestContract(plan.Contract)
	if err != nil {
		return AdaptiveCNNLiteAutotuneResult{}, err
	}
	if recomputedDigest != plan.ContractDigest {
		return AdaptiveCNNLiteAutotuneResult{}, fmt.Errorf(
			"CNN-lite synthesis plan contract digest mismatch",
		)
	}
	result := AdaptiveCNNLiteAutotuneResult{
		SchemaVersion:    SynthesisPlanSchemaVersion,
		ExecutionAdapter: MNISTCNNLiteGraphAdapterV1,
		Plan:             plan,
		Trials:           make([]CNNLiteTrialResult, 0),
	}
	candidate := plan.InitialCandidates[0]
	maxTrials := plan.Contract.Deployment.MaxEncryptedTrials
	for trialIndex := 1; trialIndex <= maxTrials; trialIndex++ {
		trial, err := ExecuteCNNLiteCandidate(
			plan.Contract,
			candidate,
			trialIndex,
		)
		if err != nil {
			return AdaptiveCNNLiteAutotuneResult{}, err
		}
		result.Trials = append(result.Trials, trial)
		result.TrialsUsed = len(result.Trials)
		result.EncryptedKeyRuns += trial.KeyRepeatsCompleted
		result.EncryptedSampleEvaluations +=
			trial.EncryptedSampleEvaluations
		if trial.Status == certify.StatusSafe {
			selected := candidate
			result.Outcome = AdaptiveOutcomeSelected
			result.Selected = &selected
			result.Reason = fmt.Sprintf(
				"selected first certified CNN-lite candidate %s after %d encrypted trial(s)",
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
				"no declared repair for CNN-lite status=%s",
				trial.Status,
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
			return AdaptiveCNNLiteAutotuneResult{}, err
		}
		candidate = next
	}
	result.Outcome = AdaptiveOutcomeNoSafe
	result.Reason = fmt.Sprintf(
		"no SAFE CNN-lite candidate within trial budget %d",
		maxTrials,
	)
	return result, nil
}
