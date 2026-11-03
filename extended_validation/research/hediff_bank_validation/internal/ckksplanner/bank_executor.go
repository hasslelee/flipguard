package ckksplanner

import (
	"fmt"
	"github.com/hasslelee/flipguard/internal/bankadapter"
	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/tuner"
	"time"
)

func ExecuteBankCandidate(
	contract WorkloadContract,
	candidate SynthesizedCandidate,
	trialIndex int,
	options MulticlassCandidateExecutionOptions,
	profileOverride *ckksbackend.CKKSProfile,
) (MulticlassTrialResult, error) {
	if err := contract.Validate(); err != nil {
		return MulticlassTrialResult{}, fmt.Errorf("validate multiclass contract: %w", err)
	}
	if contract.MulticlassDecision == nil ||
		contract.Deployment.PackingStrategy != FeatureCiphertextSampleSlotsV1 {
		return MulticlassTrialResult{}, fmt.Errorf("contract is not a feature-slot multiclass workload")
	}
	if contract.ModelType != bankadapter.MLPModelType {
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
	var profile ckksbackend.CKKSProfile
	var err error
	if profileOverride == nil {
		profile, err = candidate.Profile()
		if err != nil {
			result.Status = certify.StatusFailed
			result.Reason = "synthesized parameter literal failed backend validation"
			result.Failure = err.Error()
			return result, nil
		}
	} else {
		profile = *profileOverride
		if profile.Name == "" {
			return MulticlassTrialResult{}, fmt.Errorf("catalog profile identity is empty")
		}
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
			parameterStart := time.Now()
			context, err := ckksbackend.NewContextFromProfile(profile)
			parameterMS := float64(time.Since(parameterStart).Nanoseconds()) / 1e6
			if err != nil {
				result.Status = certify.StatusFailed
				result.Reason = fmt.Sprintf("create CKKS context failed for key run %d", keyRun)
				result.Failure = err.Error()
				result.FailureSignal = classifyExecutionFailure(err)
				return result, nil
			}
			backendStart := time.Now()
			records, summary, err := context.RunCKKSBankInference(
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
				ParameterMS: parameterMS, BackendMS: float64(time.Since(backendStart).Nanoseconds()) / 1e6, Q: context.Params.Q(), P: context.Params.P(),
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
	decisionStart := time.Now()
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
	result.DecisionEvaluationMS = float64(time.Since(decisionStart).Nanoseconds()) / 1e6
	if aggregation.Status == certify.StatusRejected {
		result.FailureSignal = RepairNumericalReject
	}
	return result, nil
}
