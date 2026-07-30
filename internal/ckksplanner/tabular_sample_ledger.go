package ckksplanner

import (
	"fmt"
	"math"
)

const TabularSampleLedgerSchemaVersion = 2

// TabularSampleObservation preserves one sample under one fresh-key repeat.
// It is evidence-only and does not feed synthesis, repair, or certification.
type TabularSampleObservation struct {
	SchemaVersion int `json:"schema_version"`

	SampleID  string `json:"sample_id"`
	KeyRepeat int    `json:"key_repeat"`

	PlaintextScore        float64 `json:"plaintext_score"`
	CKKSScore             float64 `json:"ckks_score"`
	Threshold             float64 `json:"threshold"`
	DecisionMargin        float64 `json:"decision_margin"`
	ErrorBudget           float64 `json:"error_budget"`
	AbsoluteError         float64 `json:"absolute_error"`
	NormalizedBudgetUsage float64 `json:"normalized_budget_usage"`

	Certifiable       bool `json:"certifiable"`
	PlaintextDecision bool `json:"plaintext_decision"`
	CKKSDecision      bool `json:"ckks_decision"`
	DecisionFlip      bool `json:"decision_flip"`
	ErrorViolation    bool `json:"error_violation"`
}

func buildTabularSampleLedger(
	sampleOrder []string,
	plainScores map[string]float64,
	approxBySample map[string][]float64,
	threshold float64,
	marginFloor float64,
	safetyFactor float64,
) []TabularSampleObservation {
	ledger := make([]TabularSampleObservation, 0)
	for _, sampleID := range sampleOrder {
		plainScore := plainScores[sampleID]
		margin := math.Abs(plainScore - threshold)
		budget := safetyFactor * margin
		certifiable := margin > marginFloor
		plainDecision := plainScore >= threshold
		for index, approxScore := range approxBySample[sampleID] {
			absoluteError := math.Abs(approxScore - plainScore)
			budgetUsage := 0.0
			if budget > 0 {
				budgetUsage = absoluteError / budget
			}
			approxDecision := approxScore >= threshold
			ledger = append(ledger, TabularSampleObservation{
				SchemaVersion:         TabularSampleLedgerSchemaVersion,
				SampleID:              sampleID,
				KeyRepeat:             index + 1,
				PlaintextScore:        plainScore,
				CKKSScore:             approxScore,
				Threshold:             threshold,
				DecisionMargin:        margin,
				ErrorBudget:           budget,
				AbsoluteError:         absoluteError,
				NormalizedBudgetUsage: budgetUsage,
				Certifiable:           certifiable,
				PlaintextDecision:     plainDecision,
				CKKSDecision:          approxDecision,
				DecisionFlip: certifiable &&
					plainDecision != approxDecision,
				ErrorViolation: certifiable &&
					absoluteError >= budget,
			})
		}
	}
	return ledger
}

// ValidateTabularSampleLedger proves that a captured observation ledger
// reproduces the aggregate trial fields used by certification.
func ValidateTabularSampleLedger(
	trial TabularTrialResult,
	contract WorkloadContract,
) error {
	if len(trial.SampleLedger) == 0 {
		return fmt.Errorf("tabular sample ledger is empty")
	}
	if trial.EncryptedSampleEvaluations != len(trial.SampleLedger) {
		return fmt.Errorf(
			"tabular sample evaluation count does not match ledger",
		)
	}
	expected := contract.Decision.ValidationSamples *
		trial.KeyRepeatsCompleted
	if len(trial.SampleLedger) != expected {
		return fmt.Errorf(
			"tabular sample ledger has %d observations, expected %d",
			len(trial.SampleLedger),
			expected,
		)
	}

	type sampleFacts struct {
		plainScore  float64
		certifiable bool
		repeats     map[int]struct{}
	}
	samples := make(map[string]*sampleFacts)
	decisionFlips := 0
	errorViolations := 0
	maxObservedError := 0.0
	maxBudgetUsage := 0.0
	for index, row := range trial.SampleLedger {
		if row.SchemaVersion != TabularSampleLedgerSchemaVersion ||
			row.SampleID == "" ||
			row.KeyRepeat <= 0 ||
			row.KeyRepeat > trial.KeyRepeatsCompleted {
			return fmt.Errorf(
				"invalid tabular sample ledger identity at row %d",
				index,
			)
		}
		margin := math.Abs(row.PlaintextScore - row.Threshold)
		budget := contract.Decision.SafetyFactor * margin
		absoluteError := math.Abs(row.CKKSScore - row.PlaintextScore)
		usage := 0.0
		if budget > 0 {
			usage = absoluteError / budget
		}
		certifiable := margin > contract.Decision.MarginFloor
		plainDecision := row.PlaintextScore >= row.Threshold
		ckksDecision := row.CKKSScore >= row.Threshold
		decisionFlip := certifiable && plainDecision != ckksDecision
		errorViolation := certifiable && absoluteError >= budget
		if !closeFloat(row.Threshold, contract.Decision.Threshold) ||
			!closeFloat(row.DecisionMargin, margin) ||
			!closeFloat(row.ErrorBudget, budget) ||
			!closeFloat(row.AbsoluteError, absoluteError) ||
			!closeFloat(row.NormalizedBudgetUsage, usage) ||
			row.Certifiable != certifiable ||
			row.PlaintextDecision != plainDecision ||
			row.CKKSDecision != ckksDecision ||
			row.DecisionFlip != decisionFlip ||
			row.ErrorViolation != errorViolation {
			return fmt.Errorf(
				"tabular sample ledger arithmetic mismatch at row %d",
				index,
			)
		}
		facts, exists := samples[row.SampleID]
		if !exists {
			facts = &sampleFacts{
				plainScore:  row.PlaintextScore,
				certifiable: certifiable,
				repeats:     make(map[int]struct{}),
			}
			samples[row.SampleID] = facts
		} else if !closeFloat(facts.plainScore, row.PlaintextScore) ||
			facts.certifiable != certifiable {
			return fmt.Errorf(
				"tabular sample ledger plaintext changed for sample %s",
				row.SampleID,
			)
		}
		if _, duplicate := facts.repeats[row.KeyRepeat]; duplicate {
			return fmt.Errorf(
				"duplicate tabular sample/repeat observation %s/%d",
				row.SampleID,
				row.KeyRepeat,
			)
		}
		facts.repeats[row.KeyRepeat] = struct{}{}
		if decisionFlip {
			decisionFlips++
		}
		if errorViolation {
			errorViolations++
		}
		if certifiable {
			maxObservedError = math.Max(maxObservedError, absoluteError)
			maxBudgetUsage = math.Max(maxBudgetUsage, usage)
		}
	}

	vCert := 0
	vAmb := 0
	for sampleID, facts := range samples {
		if len(facts.repeats) != trial.KeyRepeatsCompleted {
			return fmt.Errorf(
				"tabular sample %s has incomplete repeat coverage",
				sampleID,
			)
		}
		if facts.certifiable {
			vCert++
		} else {
			vAmb++
		}
	}
	if len(samples) != contract.Decision.ValidationSamples ||
		vCert != trial.VCert ||
		vAmb != trial.VAmb ||
		decisionFlips != trial.DecisionFlips ||
		errorViolations != trial.ErrorViolations ||
		!closeFloat(maxObservedError, trial.MaxObservedError) ||
		!closeFloat(maxBudgetUsage, trial.MaxErrorBudgetUsage) {
		return fmt.Errorf(
			"tabular sample ledger aggregate mismatch",
		)
	}
	return nil
}
