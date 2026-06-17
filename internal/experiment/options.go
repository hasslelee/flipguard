package experiment

import "github.com/hasslelee/flipguard/internal/ckksbackend"

// RuntimeOptions stores CLI-level experiment options.
type RuntimeOptions struct {
	CKKSMinTargetZ                 float64
	CKKSMaxTargetZ                 float64
	CKKSPoints                     int
	CKKSRepetitions                int
	CKKSSafetyFactor               float64
	CKKSOutputTag                  string
	CKKSScoreAbsErrorCap           float64
	CKKSScoreRelErrorCap           float64
	CKKSTimingWarmupRuns           int
	CKKSTimingMeasurementRuns      int
	CKKSProfileNames               string
	CKKSProfileName                string
	CKKSEvaluationMode             string
	CKKSNaiveProfileBenchmarkTag   string
	CKKSRescaleProfileBenchmarkTag string
}

var runtimeOptions = DefaultRuntimeOptions()

// DefaultRuntimeOptions returns default experiment runtime options.
func DefaultRuntimeOptions() RuntimeOptions {
	return RuntimeOptions{
		CKKSMinTargetZ:                 -0.05,
		CKKSMaxTargetZ:                 0.05,
		CKKSPoints:                     101,
		CKKSRepetitions:                3,
		CKKSSafetyFactor:               0.5,
		CKKSOutputTag:                  "",
		CKKSScoreAbsErrorCap:           1e-3,
		CKKSScoreRelErrorCap:           1e-2,
		CKKSTimingWarmupRuns:           3,
		CKKSTimingMeasurementRuns:      30,
		CKKSProfileNames:               ckksbackend.DefaultCKKSProfileNames(),
		CKKSProfileName:                "default",
		CKKSEvaluationMode:             ckksbackend.CKKSEvaluationModeNaive,
		CKKSNaiveProfileBenchmarkTag:   "profile_naive_default",
		CKKSRescaleProfileBenchmarkTag: "profile_rescale_default",
	}
}

// SetRuntimeOptions updates global runtime options.
func SetRuntimeOptions(options RuntimeOptions) {
	runtimeOptions = options
}

// GetRuntimeOptions returns global runtime options.
func GetRuntimeOptions() RuntimeOptions {
	return runtimeOptions
}

// CKKSBoundaryRepeatConfigFromRuntimeOptions returns repeat configuration from runtime options.
func CKKSBoundaryRepeatConfigFromRuntimeOptions() ckksbackend.FullLogRegBoundaryRepeatConfig {
	options := GetRuntimeOptions()

	return ckksbackend.FullLogRegBoundaryRepeatConfig{
		Repetitions: options.CKKSRepetitions,
	}
}

// CKKSBoundarySweepConfigFromRuntimeOptions returns sweep configuration from runtime options.
func CKKSBoundarySweepConfigFromRuntimeOptions() ckksbackend.FullLogRegBoundarySweepConfig {
	options := GetRuntimeOptions()

	return ckksbackend.FullLogRegBoundarySweepConfig{
		MinTargetZ:  options.CKKSMinTargetZ,
		MaxTargetZ:  options.CKKSMaxTargetZ,
		Points:      options.CKKSPoints,
		Repetitions: options.CKKSRepetitions,
	}
}

// CKKSCertificateAuditConfigFromRuntimeOptions returns certificate audit configuration from runtime options.
func CKKSCertificateAuditConfigFromRuntimeOptions() ckksbackend.CKKSCertificateAuditConfig {
	options := GetRuntimeOptions()

	return ckksbackend.CKKSCertificateAuditConfig{
		SafetyFactor: options.CKKSSafetyFactor,
		SweepConfig:  CKKSBoundarySweepConfigFromRuntimeOptions(),
	}
}

// CKKSTimingBenchmarkConfigFromRuntimeOptions returns timing benchmark configuration from runtime options.
func CKKSTimingBenchmarkConfigFromRuntimeOptions() ckksbackend.CKKSTimingBenchmarkConfig {
	options := GetRuntimeOptions()
	config := ckksbackend.DefaultCKKSTimingBenchmarkConfig()

	config.WarmupRuns = options.CKKSTimingWarmupRuns
	config.MeasurementRuns = options.CKKSTimingMeasurementRuns
	config.EvaluationMode = options.CKKSEvaluationMode

	return config
}

// CKKSProfilesFromRuntimeOptions returns selected CKKS profiles from runtime options.
func CKKSProfilesFromRuntimeOptions() ([]ckksbackend.CKKSProfile, error) {
	options := GetRuntimeOptions()

	return ckksbackend.SelectCKKSProfiles(options.CKKSProfileNames)
}

// CKKSProfileFromRuntimeOptions returns the selected single CKKS profile.
func CKKSProfileFromRuntimeOptions() (ckksbackend.CKKSProfile, error) {
	options := GetRuntimeOptions()

	return ckksbackend.FindCKKSProfile(options.CKKSProfileName)
}
