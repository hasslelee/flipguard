package ckksplanner

import (
	"testing"
)

func TestRunAdaptiveTabularAutotuneSelectsDirectCandidate(t *testing.T) {
	modelPath, validationPath := writeLinearFixture(t, false)

	options := DefaultTabularContractOptions()
	options.ModelPath = modelPath
	options.ValidationPath = validationPath
	options.SplitID = "split_seed_0"
	options.MarginFloor = 0.01
	options.MaxEncryptedTrials = 2
	options.ValidationKeyRepeats = 2

	contract, err := BuildTabularWorkloadContract(options)
	if err != nil {
		t.Fatalf("build contract: %v", err)
	}
	plan, err := Synthesize(contract, DefaultSynthesisPolicy())
	if err != nil {
		t.Fatalf("synthesize: %v", err)
	}

	result, err := RunAdaptiveTabularAutotune(plan)
	if err != nil {
		t.Fatalf("run adaptive autotune: %v", err)
	}
	if result.Outcome != AdaptiveOutcomeSelected {
		t.Fatalf(
			"expected SELECTED, got %s: %s; trials=%+v",
			result.Outcome,
			result.Reason,
			result.Trials,
		)
	}
	if result.TrialsUsed != 1 {
		t.Fatalf("expected one encrypted trial, got %d", result.TrialsUsed)
	}
	if result.EncryptedKeyRuns != 2 ||
		result.Trials[0].KeyRepeatsRequested != 2 ||
		result.Trials[0].KeyRepeatsCompleted != 2 ||
		result.Trials[0].SuccessRuns != 2 {
		t.Fatalf(
			"unexpected multi-key evidence: %+v",
			result,
		)
	}
	if result.Trials[0].VCert != 2 ||
		result.Trials[0].VAmb != 1 {
		t.Fatalf(
			"unexpected certified partition: %+v",
			result.Trials[0],
		)
	}
}

func TestSummarizeTrialLatencies(t *testing.T) {
	mean, median, p95, err := summarizeTrialLatencies(
		[]float64{4, 1, 3, 2},
	)
	if err != nil {
		t.Fatalf("summarize latencies: %v", err)
	}
	if mean != 2.5 || median != 2 || p95 != 4 {
		t.Fatalf(
			"unexpected latency summary mean=%g median=%g p95=%g",
			mean,
			median,
			p95,
		)
	}
}

func TestRepairCandidateIsMonotoneAndFeedbackDriven(t *testing.T) {
	plan, err := Synthesize(
		validContractFixture(),
		DefaultSynthesisPolicy(),
	)
	if err != nil {
		t.Fatalf("synthesize: %v", err)
	}
	initial := plan.InitialCandidates[0]

	levelRepair, err := RepairCandidate(
		plan,
		initial,
		RepairLevelFailure,
		1,
	)
	if err != nil {
		t.Fatalf("level repair: %v", err)
	}
	if len(levelRepair.Parameters.LogQ) !=
		len(initial.Parameters.LogQ)+1 {
		t.Fatalf(
			"level repair did not add exactly one Q prime: %v -> %v",
			initial.Parameters.LogQ,
			levelRepair.Parameters.LogQ,
		)
	}
	if levelRepair.Parameters.LogDefaultScale !=
		initial.Parameters.LogDefaultScale {
		t.Fatal("level repair unexpectedly changed scale")
	}

	scaleRepair, err := RepairCandidate(
		plan,
		initial,
		RepairNumericalReject,
		1,
	)
	if err != nil {
		t.Fatalf("scale repair: %v", err)
	}
	if scaleRepair.Parameters.LogDefaultScale !=
		initial.Parameters.LogDefaultScale+
			plan.Policy.RepairScaleStepBits {
		t.Fatalf(
			"scale repair did not apply declared step: %d -> %d",
			initial.Parameters.LogDefaultScale,
			scaleRepair.Parameters.LogDefaultScale,
		)
	}
	if len(scaleRepair.Parameters.LogQ) !=
		len(initial.Parameters.LogQ) {
		t.Fatal("scale repair unexpectedly changed chain length")
	}
}
