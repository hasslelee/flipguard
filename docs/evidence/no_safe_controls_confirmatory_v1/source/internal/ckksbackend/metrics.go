package ckksbackend

import "time"

// Metrics contains CKKS execution measurements for one method.
//
// This type is intentionally backend-facing. The first real CKKS evaluator will
// populate these values after encrypted execution.
type Metrics struct {
	Method string

	Samples int

	Runtime time.Duration

	MeanError float64
	MaxError  float64
	P95Error  float64
	P99Error  float64

	Flips               int
	StableBoundaryFlips int

	InitialLevel int
	FinalLevel   int
	MinLevel     int

	MaxLogScale float64
	MinLogScale float64

	RescaleCount int
	MulCount     int
	AddCount     int
}

// RuntimeMillis returns the runtime in milliseconds.
func (m Metrics) RuntimeMillis() float64 {
	return float64(m.Runtime.Microseconds()) / 1000.0
}

// ConsumedLevels returns the estimated number of consumed CKKS levels.
func (m Metrics) ConsumedLevels() int {
	if m.InitialLevel <= 0 || m.FinalLevel < 0 {
		return 0
	}

	consumed := m.InitialLevel - m.FinalLevel
	if consumed < 0 {
		return 0
	}

	return consumed
}

// HasDecisionFailure reports whether stable boundary flips were observed.
func (m Metrics) HasDecisionFailure() bool {
	return m.StableBoundaryFlips > 0
}
