package journalmnist

import "testing"

func TestLeNetModelShapeAndDeterminism(t *testing.T) {
	first := NewLeNetModel(42)
	second := NewLeNetModel(42)
	if err := first.Validate(); err != nil {
		t.Fatal(err)
	}
	if len(first.Parameters) != lenetParamCount ||
		first.Parameters[123] != second.Parameters[123] {
		t.Fatal("LeNet initialization changed")
	}
}

func TestLeNetLogitsAreFinite(t *testing.T) {
	model := NewLeNetModel(42)
	sample := Sample{Label: 3}
	sample.Pixels[14*28+14] = 255
	logits := model.Logits(sample)
	for classIndex, value := range logits {
		if value != value {
			t.Fatalf("class %d logit is NaN", classIndex)
		}
	}
}

func TestLeNetParameterOffsetsAreContiguous(t *testing.T) {
	if lenetC1BOffset != 150 || lenetC2WOffset != 156 ||
		lenetFC1WOffset != lenetC2BOffset+16 ||
		lenetParamCount != lenetOutBOffset+ClassCount {
		t.Fatal("LeNet parameter layout changed")
	}
}
