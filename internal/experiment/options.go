package experiment

import "github.com/hasslelee/flipguard/internal/ckksbackend"

// RuntimeOptions stores CLI-level experiment options.
type RuntimeOptions struct {
	CKKSMinTargetZ   float64
	CKKSMaxTargetZ   float64
	CKKSPoints       int
	CKKSRepetitions  int
	CKKSSafetyFactor float64
	CKKSOutputTag    string
}

var runtimeOptions = DefaultRuntimeOptions()

// DefaultRuntimeOptions returns the default runtime options.
func DefaultRuntimeOptions() RuntimeOptions {
	return RuntimeOptions{
		CKKSMinTargetZ:   -0.05,
		CKKSMaxTargetZ:   0.05,
		CKKSPoints:       101,
		CKKSRepetitions:  3,
		CKKSSafetyFactor: 0.5,
		CKKSOutputTag:    "",
	}
}

// SetRuntimeOptions stores CLI-level experiment options.
func SetRuntimeOptions(options RuntimeOptions) {
	runtimeOptions = options
}

// GetRuntimeOptions returns CLI-level experiment options.
func GetRuntimeOptions() RuntimeOptions {
	return runtimeOptions
}

// CKKSBoundaryRepeatConfigFromRuntimeOptions builds repeated boundary settings.
func CKKSBoundaryRepeatConfigFromRuntimeOptions() ckksbackend.FullLogRegBoundaryRepeatConfig {
	options := GetRuntimeOptions()

	return ckksbackend.FullLogRegBoundaryRepeatConfig{
		Repetitions: options.CKKSRepetitions,
	}
}

// CKKSBoundarySweepConfigFromRuntimeOptions builds dense boundary sweep settings.
func CKKSBoundarySweepConfigFromRuntimeOptions() ckksbackend.FullLogRegBoundarySweepConfig {
	options := GetRuntimeOptions()

	return ckksbackend.FullLogRegBoundarySweepConfig{
		MinTargetZ:  options.CKKSMinTargetZ,
		MaxTargetZ:  options.CKKSMaxTargetZ,
		Points:      options.CKKSPoints,
		Repetitions: options.CKKSRepetitions,
	}
}

// CKKSCertificateAuditConfigFromRuntimeOptions builds certificate audit settings.
func CKKSCertificateAuditConfigFromRuntimeOptions() ckksbackend.CKKSCertificateAuditConfig {
	options := GetRuntimeOptions()

	return ckksbackend.CKKSCertificateAuditConfig{
		SafetyFactor: options.CKKSSafetyFactor,
		SweepConfig:  CKKSBoundarySweepConfigFromRuntimeOptions(),
	}
}
