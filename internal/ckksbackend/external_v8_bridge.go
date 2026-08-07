//go:build externalv8

package ckksbackend

import "time"

// ExternalV8TabularRuntime exposes the existing evaluator only to the frozen
// V8 common-executor harness. It does not alter normal FlipGuard builds.
type ExternalV8TabularRuntime struct {
	context Context
	runtime ckksTimingRuntime
	model   tabularModelArtifact
}

func NewExternalV8TabularRuntime(
	profile CKKSProfile,
	modelPath string,
) (*ExternalV8TabularRuntime, float64, error) {
	started := time.Now()
	context, err := NewContextFromProfile(profile)
	if err != nil {
		return nil, 0, err
	}
	runtimeState, err := context.newCKKSTimingRuntime()
	if err != nil {
		return nil, 0, err
	}
	model, err := loadTabularModelArtifact(modelPath)
	if err != nil {
		return nil, 0, err
	}
	return &ExternalV8TabularRuntime{
		context: context,
		runtime: runtimeState,
		model:   model,
	}, durationMS(time.Since(started)), nil
}

func (runtime *ExternalV8TabularRuntime) Evaluate(
	rowID int,
	features []float64,
	plainZ float64,
	plainY float64,
	plainDecision bool,
) (CKKSTabularInferenceRecord, error) {
	label := 0
	if plainDecision {
		label = 1
	}
	return runtime.context.runTabularTimedInference(
		runtime.runtime,
		tabularTestRow{
			RowID: rowID, Label: label, Features: features,
			PlainZ: plainZ, PlainY: plainY,
			PlainDecision: plainDecision,
		},
		runtime.model,
		CKKSEvaluationModeRescale,
		1,
		1,
	)
}
