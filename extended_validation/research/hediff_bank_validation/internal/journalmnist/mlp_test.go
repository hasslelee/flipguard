package journalmnist

import "testing"

func TestMLPModelShapeAndDeterminism(t *testing.T) {
	first := NewMLPModel(42)
	second := NewMLPModel(42)
	if err := first.Validate(); err != nil {
		t.Fatal(err)
	}
	if len(first.Parameters) != mlpParamCount ||
		first.Parameters[123] != second.Parameters[123] {
		t.Fatal("MLP initialization changed")
	}
}

func TestMLPLogitsAreFinite(t *testing.T) {
	model := NewMLPModel(42)
	sample := Sample{Label: 3}
	sample.Pixels[100] = 255
	logits := model.Logits(sample)
	for classIndex, value := range logits {
		if value != value {
			t.Fatalf("class %d logit is NaN", classIndex)
		}
	}
}
