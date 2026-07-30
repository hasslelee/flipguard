package ckksbackend

import (
	"fmt"
	"math"
)

// ScalePolicyKind identifies a CKKS scale policy used by the backend.
//
// The initial backend treats FlipGuard schedules as control signals.
// It does not assume that simulation-level node-wise precision bits directly
// map to exact CKKS rounding operations.
type ScalePolicyKind string

const (
	// ScalePolicyUniformHigh uses one conservative global scale.
	ScalePolicyUniformHigh ScalePolicyKind = "uniform_high"

	// ScalePolicyUniformLow uses one lower global scale.
	ScalePolicyUniformLow ScalePolicyKind = "uniform_low"

	// ScalePolicyFlipGuardGrouped maps FlipGuard scheduled bits into a small
	// number of CKKS scale groups.
	ScalePolicyFlipGuardGrouped ScalePolicyKind = "flipguard_grouped"
)

// Config contains CKKS backend configuration.
//
// The fields intentionally use plain Go types so that this package can compile
// before adding a Lattigo dependency.
type Config struct {
	Name string

	Policy ScalePolicyKind

	LogScaleHigh float64
	LogScaleMid  float64
	LogScaleLow  float64

	HighBitThreshold int
	MidBitThreshold  int

	ExpectedSlots int

	MeasureRuntime bool
	MeasureLevels  bool
	MeasureScales  bool
}

// DefaultConfig returns the default backend configuration for the first CKKS
// integration experiment.
func DefaultConfig() Config {
	return Config{
		Name: "ckks_default",

		Policy: ScalePolicyUniformHigh,

		LogScaleHigh: 40,
		LogScaleMid:  35,
		LogScaleLow:  30,

		HighBitThreshold: 12,
		MidBitThreshold:  8,

		ExpectedSlots: 1,

		MeasureRuntime: true,
		MeasureLevels:  true,
		MeasureScales:  true,
	}
}

// UniformHighConfig returns a conservative high-scale baseline configuration.
func UniformHighConfig() Config {
	cfg := DefaultConfig()
	cfg.Name = "uniform_high"
	cfg.Policy = ScalePolicyUniformHigh
	return cfg
}

// UniformLowConfig returns a lower-scale baseline configuration.
func UniformLowConfig() Config {
	cfg := DefaultConfig()
	cfg.Name = "uniform_low"
	cfg.Policy = ScalePolicyUniformLow
	return cfg
}

// FlipGuardGroupedConfig returns a grouped-scale configuration driven by a
// FlipGuard precision schedule.
func FlipGuardGroupedConfig() Config {
	cfg := DefaultConfig()
	cfg.Name = "flipguard_grouped"
	cfg.Policy = ScalePolicyFlipGuardGrouped
	return cfg
}

// Validate checks whether the configuration is internally consistent.
func (c Config) Validate() error {
	if c.Name == "" {
		return fmt.Errorf("config name must not be empty")
	}

	switch c.Policy {
	case ScalePolicyUniformHigh, ScalePolicyUniformLow, ScalePolicyFlipGuardGrouped:
	default:
		return fmt.Errorf("unsupported scale policy: %s", c.Policy)
	}

	if !validLogScale(c.LogScaleHigh) {
		return fmt.Errorf("invalid high log scale: %f", c.LogScaleHigh)
	}
	if !validLogScale(c.LogScaleMid) {
		return fmt.Errorf("invalid mid log scale: %f", c.LogScaleMid)
	}
	if !validLogScale(c.LogScaleLow) {
		return fmt.Errorf("invalid low log scale: %f", c.LogScaleLow)
	}

	if c.LogScaleHigh < c.LogScaleMid {
		return fmt.Errorf("high log scale must be >= mid log scale")
	}
	if c.LogScaleMid < c.LogScaleLow {
		return fmt.Errorf("mid log scale must be >= low log scale")
	}

	if c.HighBitThreshold < c.MidBitThreshold {
		return fmt.Errorf("high bit threshold must be >= mid bit threshold")
	}
	if c.MidBitThreshold < 0 {
		return fmt.Errorf("mid bit threshold must be non-negative")
	}

	if c.ExpectedSlots <= 0 {
		return fmt.Errorf("expected slots must be positive")
	}

	return nil
}

func validLogScale(v float64) bool {
	return !math.IsNaN(v) && !math.IsInf(v, 0) && v > 0
}
