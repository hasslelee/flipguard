package ckksplanner

import (
	"errors"
	"fmt"
	"strconv"
	"strings"

	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

const AdaptiveOutcomeBackendDepthUnsupported = "BACKEND_DEPTH_UNSUPPORTED"

type V17DepthLadderResult struct {
	SchemaVersion              int                   `json:"schema_version"`
	Depth                      int                   `json:"depth"`
	Plan                       SynthesisPlan         `json:"plan"`
	Outcome                    string                `json:"outcome"`
	Reason                     string                `json:"reason"`
	TrialsUsed                 int                   `json:"trials_used"`
	Repairs                    int                   `json:"repairs"`
	Trials                     []TabularTrialResult  `json:"trials"`
	EncryptedKeyRuns           int                   `json:"encrypted_key_runs"`
	EncryptedSampleEvaluations int                   `json:"encrypted_sample_evaluations"`
	Selected                   *SynthesizedCandidate `json:"selected,omitempty"`
}

func ExecuteV17DepthLadderCandidate(contract WorkloadContract, candidate SynthesizedCandidate, depth, trialIndex int) (TabularTrialResult, error) {
	if err := contract.Validate(); err != nil {
		return TabularTrialResult{}, err
	}
	if contract.ModelType != "v17_repeated_square_depth" || depth <= 0 || trialIndex <= 0 {
		return TabularTrialResult{}, fmt.Errorf("invalid depth-ladder candidate execution request")
	}
	if err := verifyContractArtifacts(contract); err != nil {
		return TabularTrialResult{}, err
	}
	result := TabularTrialResult{TrialIndex: trialIndex, Candidate: candidate, KeyRepeatsRequested: contract.Deployment.ValidationKeyRepeats}
	profile, err := candidate.Profile()
	if err != nil {
		result.Status, result.Assurance, result.Reason, result.Failure = certify.StatusFailed, certify.AssuranceNone, "candidate parameter materialization failed", err.Error()
		return result, nil
	}
	sampleOrder := make([]string, 0)
	plainScores := make(map[string]float64)
	approx := make(map[string][]float64)
	latencies := make([]float64, 0)
	for keyRun := 1; keyRun <= contract.Deployment.ValidationKeyRepeats; keyRun++ {
		context, err := ckksbackend.NewContextFromProfile(profile)
		if err != nil {
			result.Status, result.Assurance, result.Reason, result.Failure = certify.StatusFailed, certify.AssuranceNone, "depth-ladder context creation failed", err.Error()
			return result, nil
		}
		records, err := context.RunCKKSDepthLadderInference(ckksbackend.CKKSDepthLadderConfig{DataPath: contract.ValidationData.Path, Depth: depth, Threshold: contract.Decision.Threshold})
		if err != nil {
			result.Status, result.Assurance, result.Reason, result.Failure = certify.StatusFailed, certify.AssuranceNone, "depth-ladder encrypted execution failed", err.Error()
			result.FailureSignal = classifyExecutionFailure(err)
			return result, nil
		}
		if keyRun > 1 && len(records) != len(sampleOrder) {
			return TabularTrialResult{}, fmt.Errorf("depth-ladder row count changed")
		}
		for index, record := range records {
			id := strconv.Itoa(record.RowID)
			if keyRun == 1 {
				sampleOrder = append(sampleOrder, id)
				plainScores[id] = record.PlainScore
				approx[id] = make([]float64, 0, contract.Deployment.ValidationKeyRepeats)
			} else if sampleOrder[index] != id || !closeFloat(plainScores[id], record.PlainScore) {
				return TabularTrialResult{}, fmt.Errorf("depth-ladder row identity changed on key run %d", keyRun)
			}
			approx[id] = append(approx[id], record.CKKSScore)
			latencies = append(latencies, record.TotalEvalMS)
		}
		result.KeyRepeatsCompleted = keyRun
		result.EncryptedSampleEvaluations += len(records)
	}
	if digestValidationScores(sampleOrder, plainScores) != contract.Decision.ValidationDigest {
		return TabularTrialResult{}, fmt.Errorf("depth-ladder validation digest mismatch")
	}
	observed := make([]certify.ObservedSample, 0, len(sampleOrder))
	for _, id := range sampleOrder {
		observed = append(observed, certify.ObservedSample{ID: id, PlainScore: plainScores[id], Threshold: contract.Decision.Threshold, ApproxScores: append([]float64(nil), approx[id]...)})
	}
	mean, median, p95, err := summarizeTrialLatencies(latencies)
	if err != nil {
		return TabularTrialResult{}, err
	}
	aggregation, err := certify.AggregateObservedCandidate(certify.ObservedCandidateInput{Candidate: candidateDescriptor(candidate), Samples: observed, MeanTotalMS: mean}, contract.Decision.MarginFloor, contract.Decision.SafetyFactor)
	if err != nil {
		return TabularTrialResult{}, err
	}
	policy := certify.DefaultCertificationPolicy()
	policy.SafetyFactor = contract.Decision.SafetyFactor
	certificate, err := certify.BuildCandidateCertificateWithPolicy(aggregation.Evidence, aggregation.Coverage, policy)
	if err != nil {
		return TabularTrialResult{}, err
	}
	result.Status, result.Assurance, result.Reason = certificate.Status, certificate.Assurance, certificate.Reason
	result.SuccessRuns, result.DecisionFlips, result.ErrorViolations = certificate.SuccessRuns, certificate.DecisionFlips, certificate.ErrorViolations
	result.MaxObservedError, result.MaxErrorBudgetUsage = certificate.MaxObservedError, certificate.MaxObservedBudgetUsage
	result.VCert, result.VAmb = certificate.VCert, certificate.VAmb
	result.MeanTotalMS, result.MedianMS, result.P95MS = mean, median, p95
	if result.Status == certify.StatusRejected {
		result.FailureSignal = RepairNumericalReject
	}
	return result, nil
}

func RunAdaptiveV17DepthLadderAutotune(plan SynthesisPlan, depth int) (V17DepthLadderResult, error) {
	result := V17DepthLadderResult{SchemaVersion: SynthesisPlanSchemaVersion, Depth: depth, Plan: plan, Trials: make([]TabularTrialResult, 0)}
	if plan.SchemaVersion != SynthesisPlanSchemaVersion || len(plan.InitialCandidates) != 1 {
		return result, fmt.Errorf("invalid depth-ladder synthesis plan")
	}
	if digest, err := digestContract(plan.Contract); err != nil || digest != plan.ContractDigest {
		return result, fmt.Errorf("depth-ladder synthesis plan digest mismatch")
	}
	candidate := plan.InitialCandidates[0]
	for trialIndex := 1; trialIndex <= plan.Contract.Deployment.MaxEncryptedTrials; trialIndex++ {
		trial, err := ExecuteV17DepthLadderCandidate(plan.Contract, candidate, depth, trialIndex)
		if err != nil {
			return result, err
		}
		result.Trials = append(result.Trials, trial)
		result.TrialsUsed++
		result.EncryptedKeyRuns += trial.KeyRepeatsCompleted
		result.EncryptedSampleEvaluations += trial.EncryptedSampleEvaluations
		if trial.Status == certify.StatusSafe {
			selected := candidate
			result.Selected = &selected
			result.Outcome = AdaptiveOutcomeSelected
			result.Reason = fmt.Sprintf("selected first SAFE depth-ladder candidate after %d trial(s)", result.TrialsUsed)
			return result, nil
		}
		if trial.Status == certify.StatusFailed && trial.FailureSignal == RepairLevelFailure && strings.Contains(strings.ToLower(trial.Failure), "level") && trialIndex == plan.Contract.Deployment.MaxEncryptedTrials {
			result.Outcome = AdaptiveOutcomeBackendDepthUnsupported
			result.Reason = trial.Failure
			return result, nil
		}
		if trialIndex == plan.Contract.Deployment.MaxEncryptedTrials || trial.FailureSignal == "" {
			break
		}
		next, err := RepairCandidate(plan, candidate, trial.FailureSignal, trialIndex)
		if err != nil {
			if errors.Is(err, ErrRepairExhausted) && trial.FailureSignal == RepairLevelFailure {
				result.Outcome = AdaptiveOutcomeBackendDepthUnsupported
			} else {
				result.Outcome = AdaptiveOutcomeNoSafe
			}
			result.Reason = err.Error()
			return result, nil
		}
		candidate = next
		result.Repairs++
	}
	result.Outcome = AdaptiveOutcomeNoSafe
	result.Reason = fmt.Sprintf("no SAFE candidate within trial budget %d", plan.Contract.Deployment.MaxEncryptedTrials)
	return result, nil
}
