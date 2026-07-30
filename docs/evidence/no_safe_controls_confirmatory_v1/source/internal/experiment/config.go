package experiment

// LogRegSmallConfig contains configurable parameters for the logreg_small
// decision-stability experiment.
type LogRegSmallConfig struct {
	OutputDir string

	MarginFloor float64

	P5Percentile float64
	P1Percentile float64

	SafetyFactor float64

	FlipGuardGlobalTolerance float64

	AccuracyOnlyLooseTolerance  float64
	AccuracyOnlyStrictTolerance float64

	FlipGuardP5MaxBits           int
	FlipGuardConservativeMaxBits int
	AccuracyOnlyLooseMaxBits     int
	AccuracyOnlyStrictMaxBits    int
}

// DefaultLogRegSmallConfig returns the default configuration used in the
// current reproducibility experiment.
func DefaultLogRegSmallConfig() LogRegSmallConfig {
	return LogRegSmallConfig{
		OutputDir: "results/logreg_small",

		MarginFloor: 1e-4,

		P5Percentile: 0.05,
		P1Percentile: 0.01,

		SafetyFactor: 0.5,

		FlipGuardGlobalTolerance: 0.02,

		AccuracyOnlyLooseTolerance:  0.02,
		AccuracyOnlyStrictTolerance: 0.005,

		FlipGuardP5MaxBits:           12,
		FlipGuardConservativeMaxBits: 16,
		AccuracyOnlyLooseMaxBits:     12,
		AccuracyOnlyStrictMaxBits:    16,
	}
}
