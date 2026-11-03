package ckksbackend

import (
	"math"
	"path/filepath"
	"testing"

	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

func TestHarrisPatchInferenceOnFrozenFirstRow(t *testing.T) {
	profile, err := NewCKKSProfileFromLiteral(
		"harris_static_initial",
		"static Harris plan initial candidate",
		ckks.ParametersLiteral{
			LogN:            13,
			LogQ:            []int{35, 26, 26, 26, 26, 26},
			LogP:            []int{35},
			LogDefaultScale: 26,
		},
	)
	if err != nil {
		t.Fatalf("NewCKKSProfileFromLiteral failed: %v", err)
	}
	context, err := NewContextFromProfile(profile)
	if err != nil {
		t.Fatalf("NewContextFromProfile failed: %v", err)
	}
	root := filepath.Join(
		"..",
		"..",
		"datasets",
		"vision_suite",
		"bsds500",
		"harris_corner_response",
	)
	records, err := context.RunCKKSHarrisPatchInference(
		CKKSHarrisPatchConfig{
			ModelPath: filepath.Join(root, "model.json"),
			DataPath: filepath.Join(
				root,
				"configuration_validation.csv",
			),
			MaxRows: 1,
		},
	)
	if err != nil {
		t.Fatalf("RunCKKSHarrisPatchInference failed: %v", err)
	}
	if len(records) != 1 {
		t.Fatalf("records=%d, want 1", len(records))
	}
	record := records[0]
	if !math.IsNaN(record.CKKSScore) &&
		!math.IsInf(record.CKKSScore, 0) &&
		record.FinalLevel >= 0 &&
		record.FinalDegree == 1 {
		return
	}
	t.Fatalf(
		"invalid Harris result score=%g level=%d degree=%d",
		record.CKKSScore,
		record.FinalLevel,
		record.FinalDegree,
	)
}
