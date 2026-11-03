package ckksplanner

import (
	"testing"

	"github.com/hasslelee/flipguard/internal/certify"
)

func TestValidateSobelSampleLedgerRecomputesEvidence(t *testing.T) {
	contract := validContractFixture()
	contract.Decision.Threshold = 0.2
	contract.Decision.MarginFloor = 0.001
	contract.Decision.SafetyFactor = 0.5

	trial := SobelTrialResult{
		Status:                     certify.StatusSafe,
		KeyRepeatsCompleted:        1,
		EncryptedSampleEvaluations: 2,
		DecisionFlips:              0,
		ErrorViolations:            0,
		MaxObservedError:           0.01,
		MaxErrorBudgetUsage:        0.1,
		SampleLedger: []SobelSampleObservation{
			{
				KeyRun:           1,
				RowID:            100000,
				ImageID:          "100075",
				SourcePartition:  "val",
				PlainScore:       0.4,
				CKKSScore:        0.39,
				Threshold:        0.2,
				Margin:           0.2,
				AbsError:         0.01,
				Certifiable:      true,
				ErrorBudget:      0.1,
				ErrorBudgetUsage: 0.1,
				PlainDecision:    true,
				CKKSDecision:     true,
			},
			{
				KeyRun:          1,
				RowID:           100001,
				ImageID:         "100080",
				SourcePartition: "val",
				PlainScore:      0.2005,
				CKKSScore:       0.199,
				Threshold:       0.2,
				Margin:          0.0005,
				AbsError:        0.0015,
				Certifiable:     false,
				PlainDecision:   true,
				CKKSDecision:    false,
				DecisionFlip:    true,
			},
		},
	}
	if err := validateSobelSampleLedger(trial, contract); err != nil {
		t.Fatalf("valid ledger rejected: %v", err)
	}

	trial.SampleLedger[0].CKKSScore = 0.1
	if err := validateSobelSampleLedger(trial, contract); err == nil {
		t.Fatal("mutated score was accepted")
	}
}
