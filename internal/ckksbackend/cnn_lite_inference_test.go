package ckksbackend

import (
	"math"
	"testing"
)

func TestCNNLiteOneRowMatchesPlain(t *testing.T) {
	context, err := NewContextFromProfileName("default")
	if err != nil {
		t.Fatalf("NewContextFromProfileName failed: %v", err)
	}
	records, err := context.RunCKKSCNNLiteInference(
		CKKSCNNLiteConfig{
			ModelPath: "../../datasets/vision_suite/mnist/" +
				"cnn_lite_square_binary01/model.json",
			DataPath: "../../datasets/vision_suite/mnist/" +
				"cnn_lite_square_binary01/" +
				"configuration_validation.csv",
			MaxRows: 1,
		},
	)
	if err != nil {
		t.Fatalf("RunCKKSCNNLiteInference failed: %v", err)
	}
	if len(records) != 1 {
		t.Fatalf("got %d records, want 1", len(records))
	}
	record := records[0]
	if record.DecisionFlip {
		t.Fatal("CNN-lite smoke row changed decision")
	}
	if record.FinalDegree != 1 {
		t.Fatalf("final degree=%d want=1", record.FinalDegree)
	}
	if record.FinalLevel < 0 {
		t.Fatalf("final level=%d", record.FinalLevel)
	}
	if !finiteCNNLiteValue(record.CKKSScore) ||
		math.Abs(record.CKKSScore-record.PlainScore) > 0.05 {
		t.Fatalf(
			"CNN-lite score mismatch: plain=%g CKKS=%g",
			record.PlainScore,
			record.CKKSScore,
		)
	}
}
