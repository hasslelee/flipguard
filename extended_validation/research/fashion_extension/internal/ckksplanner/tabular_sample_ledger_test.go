package ckksplanner

import "testing"

func TestTabularSampleLedgerReproducesAggregate(t *testing.T) {
	contract := WorkloadContract{
		Decision: DecisionStabilityContract{
			Threshold:         0.5,
			MarginFloor:       0.001,
			SafetyFactor:      0.5,
			ValidationSamples: 2,
		},
	}
	ledger := buildTabularSampleLedger(
		[]string{"a", "b"},
		map[string]float64{"a": 0.4, "b": 0.7},
		map[string][]float64{
			"a": {0.44, 0.52},
			"b": {0.69, 0.71},
		},
		0.5,
		0.001,
		0.5,
	)
	trial := TabularTrialResult{
		KeyRepeatsCompleted:        2,
		DecisionFlips:              1,
		ErrorViolations:            1,
		MaxObservedError:           0.12,
		MaxErrorBudgetUsage:        2.4,
		VCert:                      2,
		VAmb:                       0,
		EncryptedSampleEvaluations: len(ledger),
		SampleLedger:               ledger,
	}
	if err := ValidateTabularSampleLedger(trial, contract); err != nil {
		t.Fatalf("validate sample ledger: %v", err)
	}
}

func TestTabularSampleLedgerRejectsMutation(t *testing.T) {
	contract := WorkloadContract{
		Decision: DecisionStabilityContract{
			Threshold:         0.5,
			MarginFloor:       0.001,
			SafetyFactor:      0.5,
			ValidationSamples: 1,
		},
	}
	ledger := buildTabularSampleLedger(
		[]string{"a"},
		map[string]float64{"a": 0.4},
		map[string][]float64{"a": {0.44}},
		0.5,
		0.001,
		0.5,
	)
	trial := TabularTrialResult{
		KeyRepeatsCompleted:        1,
		ErrorViolations:            0,
		MaxObservedError:           0.04,
		MaxErrorBudgetUsage:        0.8,
		VCert:                      1,
		EncryptedSampleEvaluations: 1,
		SampleLedger:               ledger,
	}
	trial.SampleLedger[0].CKKSScore = 0.45
	if err := ValidateTabularSampleLedger(trial, contract); err == nil {
		t.Fatal("expected sample-ledger mutation rejection")
	}
}

func TestCountTabularRepeatedKeyDecisionDisagreements(t *testing.T) {
	ledger := []TabularSampleObservation{
		{SampleID: "stable", KeyRepeat: 1, CKKSDecision: true},
		{SampleID: "stable", KeyRepeat: 2, CKKSDecision: true},
		{SampleID: "unstable", KeyRepeat: 1, CKKSDecision: false},
		{SampleID: "unstable", KeyRepeat: 2, CKKSDecision: true},
		{SampleID: "unstable", KeyRepeat: 3, CKKSDecision: false},
	}
	count, err := CountTabularRepeatedKeyDecisionDisagreements(ledger)
	if err != nil {
		t.Fatalf("count disagreements: %v", err)
	}
	if count != 1 {
		t.Fatalf("disagreement count=%d, want 1", count)
	}
}
