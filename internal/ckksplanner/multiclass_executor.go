package ckksplanner

import (
	"errors"
	"fmt"
	"math"
	"sort"

	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/journalmnist"
	"github.com/hasslelee/flipguard/internal/tuner"
)

type MulticlassTrialResult struct {
	TrialIndex int                  `json:"trial_index"`
	Candidate  SynthesizedCandidate `json:"candidate"`

	Status        certify.CandidateStatus `json:"status"`
	Reason        string                  `json:"reason"`
	Failure       string                  `json:"failure,omitempty"`
	FailureSignal RepairSignal            `json:"failure_signal,omitempty"`

	KeyRepeatsRequested        int `json:"key_repeats_requested"`
	KeyRepeatsCompleted        int `json:"key_repeats_completed"`
	EncryptedSampleEvaluations int `json:"encrypted_sample_evaluations"`

	Aggregation     certify.MulticlassObservedAggregation       `json:"aggregation"`
	KeyRunSummaries []ckksbackend.JournalMNISTMulticlassSummary `json:"key_run_summaries"`

	MeanTotalMS       float64 `json:"mean_total_ms"`
	MedianTotalMS     float64 `json:"median_total_ms"`
	P95TotalMS        float64 `json:"p95_total_ms"`
	MeanEvalOnlyMS    float64 `json:"mean_eval_only_ms"`
	PlaintextAccuracy float64 `json:"plaintext_accuracy"`
	CKKSAccuracy      float64 `json:"ckks_accuracy"`
}

type MulticlassKeyRunEvidence struct {
	SchemaVersion  string                                     `json:"schema_version"`
	KeyRun         int                                        `json:"key_run"`
	CandidateID    string                                     `json:"candidate_id"`
	ContractDigest string                                     `json:"contract_digest"`
	Records        []ckksbackend.JournalMNISTMulticlassRecord `json:"records"`
	Summary        ckksbackend.JournalMNISTMulticlassSummary  `json:"summary"`
}

type MulticlassCandidateExecutionOptions struct {
	ExistingKeyRuns []MulticlassKeyRunEvidence
	OnKeyRun        func(MulticlassKeyRunEvidence) error
}

type AdaptiveMulticlassAutotuneResult struct {
	SchemaVersion              int                     `json:"schema_version"`
	ExecutionAdapter           string                  `json:"execution_adapter"`
	Plan                       SynthesisPlan           `json:"plan"`
	Outcome                    string                  `json:"outcome"`
	Reason                     string                  `json:"reason"`
	TrialsUsed                 int                     `json:"trials_used"`
	Trials                     []MulticlassTrialResult `json:"trials"`
	Repairs                    int                     `json:"repairs"`
	EncryptedKeyRuns           int                     `json:"encrypted_key_runs"`
	EncryptedSampleEvaluations int                     `json:"encrypted_sample_evaluations"`
	Selected                   *SynthesizedCandidate   `json:"selected,omitempty"`
}

type MulticlassLockedAuditResult struct {
	SchemaVersion           string                `json:"schema_version"`
	ExecutionAdapter        string                `json:"execution_adapter"`
	SelectionContractDigest string                `json:"selection_contract_digest"`
	AuditContractDigest     string                `json:"audit_contract_digest"`
	SelectedCandidate       SynthesizedCandidate  `json:"selected_candidate"`
	CandidateIdentityMatch  bool                  `json:"candidate_identity_match"`
	RetuningCount           int                   `json:"retuning_count"`
	Trial                   MulticlassTrialResult `json:"trial"`
}

func ExecuteJournalMNISTMulticlassCandidate(
	contract WorkloadContract,
	candidate SynthesizedCandidate,
	trialIndex int,
) (MulticlassTrialResult, error) {
	return ExecuteJournalMNISTMulticlassCandidateWithOptions(
		contract,
		candidate,
		trialIndex,
		MulticlassCandidateExecutionOptions{},
	)
}

func ExecuteJournalMNISTMulticlassCandidateWithOptions(
	contract WorkloadContract,
	candidate SynthesizedCandidate,
	trialIndex int,
	options MulticlassCandidateExecutionOptions,
) (MulticlassTrialResult, error) {
	if err := contract.Validate(); err != nil {
		return MulticlassTrialResult{}, fmt.Errorf("validate multiclass contract: %w", err)
	}
	if contract.MulticlassDecision == nil ||
		contract.Deployment.PackingStrategy != FeatureCiphertextSampleSlotsV1 {
		return MulticlassTrialResult{}, fmt.Errorf("contract is not a feature-slot multiclass workload")
	}
	if contract.ModelType != journalmnist.MLPModelType &&
		contract.ModelType != journalmnist.LeNetModelType {
		return MulticlassTrialResult{}, fmt.Errorf("unsupported multiclass model type %q", contract.ModelType)
	}
	if candidate.Path != tuner.PathRescale {
		return MulticlassTrialResult{}, fmt.Errorf("journal multiclass adapter requires rescale path")
	}
	if trialIndex <= 0 {
		return MulticlassTrialResult{}, fmt.Errorf("trial index must be positive")
	}
	if err := verifyContractArtifacts(contract); err != nil {
		return MulticlassTrialResult{}, err
	}
	result := MulticlassTrialResult{
		TrialIndex:          trialIndex,
		Candidate:           candidate,
		KeyRepeatsRequested: contract.Deployment.ValidationKeyRepeats,
		KeyRunSummaries:     make([]ckksbackend.JournalMNISTMulticlassSummary, 0, contract.Deployment.ValidationKeyRepeats),
	}
	profile, err := candidate.Profile()
	if err != nil {
		result.Status = certify.StatusFailed
		result.Reason = "synthesized parameter literal failed backend validation"
		result.Failure = err.Error()
		return result, nil
	}
	contractDigest, err := digestContract(contract)
	if err != nil {
		return MulticlassTrialResult{}, err
	}
	if len(options.ExistingKeyRuns) > contract.Deployment.ValidationKeyRepeats {
		return MulticlassTrialResult{}, fmt.Errorf("existing key runs exceed requested repeats")
	}
	sampleOrder := make([]string, 0)
	plainLogits := make(map[string][]float64)
	labels := make(map[string]int)
	approxBySample := make(map[string][][]float64)
	totalLatencies := make([]float64, 0, contract.Deployment.ValidationKeyRepeats)
	evalLatencies := make([]float64, 0, contract.Deployment.ValidationKeyRepeats)
	for keyRun := 1; keyRun <= contract.Deployment.ValidationKeyRepeats; keyRun++ {
		var evidence MulticlassKeyRunEvidence
		if keyRun <= len(options.ExistingKeyRuns) {
			evidence = options.ExistingKeyRuns[keyRun-1]
			if evidence.SchemaVersion != "flipguard_journal_multiclass_key_run_v1" ||
				evidence.KeyRun != keyRun || evidence.CandidateID != candidate.ID ||
				evidence.ContractDigest != contractDigest {
				return MulticlassTrialResult{}, fmt.Errorf("existing key run %d identity mismatch", keyRun)
			}
		} else {
			context, err := ckksbackend.NewContextFromProfile(profile)
			if err != nil {
				result.Status = certify.StatusFailed
				result.Reason = fmt.Sprintf("create CKKS context failed for key run %d", keyRun)
				result.Failure = err.Error()
				result.FailureSignal = classifyExecutionFailure(err)
				return result, nil
			}
			records, summary, err := context.RunCKKSJournalMNISTMulticlassInference(
				ckksbackend.JournalMNISTMulticlassConfig{
					ModelPath: contract.ModelArtifact.Path,
					DataPath:  contract.ValidationData.Path,
					Role:      multiclassRoleForSplit(contract.SplitID),
				},
			)
			if err != nil {
				result.Status = certify.StatusFailed
				result.Reason = fmt.Sprintf("encrypted multiclass execution failed for key run %d", keyRun)
				result.Failure = err.Error()
				result.FailureSignal = classifyExecutionFailure(err)
				return result, nil
			}
			evidence = MulticlassKeyRunEvidence{
				SchemaVersion:  "flipguard_journal_multiclass_key_run_v1",
				KeyRun:         keyRun,
				CandidateID:    candidate.ID,
				ContractDigest: contractDigest,
				Records:        records,
				Summary:        summary,
			}
			if options.OnKeyRun != nil {
				if err := options.OnKeyRun(evidence); err != nil {
					return MulticlassTrialResult{}, fmt.Errorf("persist key run %d: %w", keyRun, err)
				}
			}
		}
		records := evidence.Records
		summary := evidence.Summary
		if summary.DatasetID != contract.DatasetID || summary.ModelID != contract.ModelID ||
			summary.ModelType != contract.ModelType || summary.EvaluatedRows != contract.MulticlassDecision.ValidationSamples {
			return MulticlassTrialResult{}, fmt.Errorf("multiclass backend identity mismatch on key run %d", keyRun)
		}
		if keyRun > 1 && len(records) != len(sampleOrder) {
			return MulticlassTrialResult{}, fmt.Errorf("multiclass sample count changed on key run %d", keyRun)
		}
		for recordIndex, record := range records {
			if keyRun == 1 {
				sampleOrder = append(sampleOrder, record.SampleID)
				plainLogits[record.SampleID] = append([]float64(nil), record.PlainLogits...)
				labels[record.SampleID] = record.Label
				approxBySample[record.SampleID] = make([][]float64, 0, contract.Deployment.ValidationKeyRepeats)
			} else {
				if sampleOrder[recordIndex] != record.SampleID ||
					!equalFloatVectors(plainLogits[record.SampleID], record.PlainLogits) ||
					labels[record.SampleID] != record.Label {
					return MulticlassTrialResult{}, fmt.Errorf("multiclass sample semantics changed on key run %d row %d", keyRun, recordIndex)
				}
			}
			approxBySample[record.SampleID] = append(approxBySample[record.SampleID], append([]float64(nil), record.CKKSLogits...))
		}
		result.KeyRepeatsCompleted = keyRun
		result.KeyRunSummaries = append(result.KeyRunSummaries, summary)
		totalLatencies = append(totalLatencies, summary.TotalMS)
		evalLatencies = append(evalLatencies, summary.EvaluationOnlyMS)
	}
	orderedPlain := make([][]float64, 0, len(sampleOrder))
	samples := make([]certify.MulticlassObservedSample, 0, len(sampleOrder))
	for _, sampleID := range sampleOrder {
		orderedPlain = append(orderedPlain, plainLogits[sampleID])
		samples = append(samples, certify.MulticlassObservedSample{
			ID:           sampleID,
			PlainLogits:  append([]float64(nil), plainLogits[sampleID]...),
			ApproxLogits: append([][]float64(nil), approxBySample[sampleID]...),
		})
	}
	if digest := DigestMulticlassPlaintextLogits(sampleOrder, orderedPlain); digest != contract.MulticlassDecision.ValidationDigest {
		return MulticlassTrialResult{}, fmt.Errorf("backend multiclass plaintext digest %s does not match contract %s", digest, contract.MulticlassDecision.ValidationDigest)
	}
	aggregation, err := certify.AggregateObservedMulticlassCandidate(
		samples,
		0,
		contract.MulticlassDecision.MarginFloor,
		contract.MulticlassDecision.MarginUtilizationCap,
	)
	if err != nil {
		return MulticlassTrialResult{}, err
	}
	if aggregation.VCert != contract.MulticlassDecision.CertifiableSamples ||
		aggregation.VAmb != contract.MulticlassDecision.AmbiguousSamples {
		return MulticlassTrialResult{}, fmt.Errorf("multiclass Vcert/Vamb changed during encrypted replay")
	}
	mean, median, p95, err := summarizeTrialLatencies(totalLatencies)
	if err != nil {
		return MulticlassTrialResult{}, err
	}
	result.Status = aggregation.Status
	result.Reason = aggregation.Reason
	result.Aggregation = aggregation
	result.EncryptedSampleEvaluations = len(samples) * result.KeyRepeatsCompleted
	result.MeanTotalMS = mean
	result.MedianTotalMS = median
	result.P95TotalMS = p95
	result.MeanEvalOnlyMS = arithmeticMean(evalLatencies)
	result.PlaintextAccuracy, result.CKKSAccuracy = multiclassAccuracies(sampleOrder, labels, plainLogits, approxBySample)
	if aggregation.Status == certify.StatusRejected {
		result.FailureSignal = RepairNumericalReject
	}
	return result, nil
}

func RunAdaptiveJournalMNISTMulticlassAutotune(plan SynthesisPlan) (AdaptiveMulticlassAutotuneResult, error) {
	if plan.SchemaVersion != SynthesisPlanSchemaVersion || len(plan.InitialCandidates) != 1 {
		return AdaptiveMulticlassAutotuneResult{}, fmt.Errorf("invalid multiclass synthesis plan")
	}
	recomputed, err := digestContract(plan.Contract)
	if err != nil || recomputed != plan.ContractDigest {
		return AdaptiveMulticlassAutotuneResult{}, fmt.Errorf("multiclass plan contract digest mismatch")
	}
	result := AdaptiveMulticlassAutotuneResult{
		SchemaVersion:    SynthesisPlanSchemaVersion,
		ExecutionAdapter: ckksbackend.JournalMNISTMulticlassExecutionAdapterV1,
		Plan:             plan,
		Trials:           make([]MulticlassTrialResult, 0, plan.Contract.Deployment.MaxEncryptedTrials),
	}
	candidate := plan.InitialCandidates[0]
	for trialIndex := 1; trialIndex <= plan.Contract.Deployment.MaxEncryptedTrials; trialIndex++ {
		trial, err := ExecuteJournalMNISTMulticlassCandidate(plan.Contract, candidate, trialIndex)
		if err != nil {
			return AdaptiveMulticlassAutotuneResult{}, err
		}
		result.Trials = append(result.Trials, trial)
		result.TrialsUsed = len(result.Trials)
		result.EncryptedKeyRuns += trial.KeyRepeatsCompleted
		result.EncryptedSampleEvaluations += trial.EncryptedSampleEvaluations
		if trial.Status == certify.StatusSafe {
			selected := candidate
			result.Outcome = AdaptiveOutcomeSelected
			result.Selected = &selected
			result.Reason = fmt.Sprintf("selected first SAFE multiclass candidate after %d encrypted trial(s)", result.TrialsUsed)
			return result, nil
		}
		if trialIndex == plan.Contract.Deployment.MaxEncryptedTrials || trial.FailureSignal == "" {
			break
		}
		next, err := RepairCandidate(plan, candidate, trial.FailureSignal, trialIndex)
		if err != nil {
			if errors.Is(err, ErrRepairExhausted) {
				break
			}
			return AdaptiveMulticlassAutotuneResult{}, err
		}
		candidate = next
		result.Repairs++
	}
	result.Outcome = AdaptiveOutcomeNoSafe
	result.Reason = fmt.Sprintf("no SAFE multiclass candidate within encrypted trial budget %d", plan.Contract.Deployment.MaxEncryptedTrials)
	return result, nil
}

// RunJournalMNISTMulticlassLockedAudit replays exactly one selected literal.
// It has no synthesis plan and no repair callback, making retuning impossible.
func RunJournalMNISTMulticlassLockedAudit(
	selectionContract WorkloadContract,
	selected SynthesizedCandidate,
	auditDataPath string,
	auditSplitID string,
) (MulticlassLockedAuditResult, error) {
	return RunJournalMNISTMulticlassLockedAuditWithOptions(
		selectionContract,
		selected,
		auditDataPath,
		auditSplitID,
		MulticlassCandidateExecutionOptions{},
	)
}

func RunJournalMNISTMulticlassLockedAuditWithOptions(
	selectionContract WorkloadContract,
	selected SynthesizedCandidate,
	auditDataPath string,
	auditSplitID string,
	executionOptions MulticlassCandidateExecutionOptions,
) (MulticlassLockedAuditResult, error) {
	selectionDigest, err := digestContract(selectionContract)
	if err != nil {
		return MulticlassLockedAuditResult{}, err
	}
	options := DefaultJournalMNISTMulticlassContractOptions()
	options.ModelPath = selectionContract.ModelArtifact.Path
	options.ValidationPath = auditDataPath
	options.SourcePath = selectionContract.SourceData.Path
	options.SplitID = auditSplitID
	options.ExpectedRole = "locked_audit"
	auditContract, _, err := BuildJournalMNISTMulticlassContract(options)
	if err != nil {
		return MulticlassLockedAuditResult{}, err
	}
	// Preserve all selection-derived planning calibration. Audit-derived values
	// are used only by the finite admission aggregation, never candidate choice.
	auditContract.Calibration = selectionContract.Calibration
	auditDigest, err := digestContract(auditContract)
	if err != nil {
		return MulticlassLockedAuditResult{}, err
	}
	trial, err := ExecuteJournalMNISTMulticlassCandidateWithOptions(
		auditContract,
		selected,
		1,
		executionOptions,
	)
	if err != nil {
		return MulticlassLockedAuditResult{}, err
	}
	return MulticlassLockedAuditResult{
		SchemaVersion:           "flipguard_journal_multiclass_locked_audit_v1",
		ExecutionAdapter:        ckksbackend.JournalMNISTMulticlassExecutionAdapterV1,
		SelectionContractDigest: selectionDigest,
		AuditContractDigest:     auditDigest,
		SelectedCandidate:       selected,
		CandidateIdentityMatch:  true,
		RetuningCount:           0,
		Trial:                   trial,
	}, nil
}

func multiclassRoleForSplit(splitID string) string {
	if containsLockedAudit(splitID) {
		return "locked_audit"
	}
	return "configuration_validation"
}

func containsLockedAudit(value string) bool {
	for index := 0; index+len("audit") <= len(value); index++ {
		if value[index:index+len("audit")] == "audit" {
			return true
		}
	}
	return false
}

func equalFloatVectors(left, right []float64) bool {
	if len(left) != len(right) {
		return false
	}
	for index := range left {
		if math.Float64bits(left[index]) != math.Float64bits(right[index]) {
			return false
		}
	}
	return true
}

func arithmeticMean(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	total := 0.0
	for _, value := range values {
		total += value
	}
	return total / float64(len(values))
}

func multiclassAccuracies(sampleOrder []string, labels map[string]int, plain map[string][]float64, approximate map[string][][]float64) (float64, float64) {
	plainCorrect := 0
	ckksCorrect := 0
	observations := 0
	for _, sampleID := range sampleOrder {
		plainTop, _, _, _, _ := multiclassTopTwo(plain[sampleID])
		if plainTop == labels[sampleID] {
			plainCorrect++
		}
		for _, logits := range approximate[sampleID] {
			top, _, _, _, _ := multiclassTopTwo(logits)
			if top == labels[sampleID] {
				ckksCorrect++
			}
			observations++
		}
	}
	return float64(plainCorrect) / float64(len(sampleOrder)), float64(ckksCorrect) / float64(observations)
}

func sortedCopy(values []float64) []float64 {
	result := append([]float64(nil), values...)
	sort.Float64s(result)
	return result
}
