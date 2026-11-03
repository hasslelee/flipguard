package ckksbackend

import "testing"

func TestDefaultConfigValid(t *testing.T) {
	cfg := DefaultConfig()

	if err := cfg.Validate(); err != nil {
		t.Fatalf("default config should be valid: %v", err)
	}
}

func TestConfigRejectsInvalidPolicy(t *testing.T) {
	cfg := DefaultConfig()
	cfg.Policy = ScalePolicyKind("unknown")

	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid policy error")
	}
}

func TestConfigRejectsInvalidScaleOrder(t *testing.T) {
	cfg := DefaultConfig()
	cfg.LogScaleHigh = 30
	cfg.LogScaleMid = 35

	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid scale order error")
	}
}

func TestConfigRejectsInvalidThresholdOrder(t *testing.T) {
	cfg := DefaultConfig()
	cfg.HighBitThreshold = 4
	cfg.MidBitThreshold = 8

	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid threshold order error")
	}
}
