package runtime

import (
	"math"
	"testing"

	"github.com/hasslelee/flipguard/internal/benchmarks"
	"github.com/hasslelee/flipguard/internal/ir"
)

func TestQuantizeToBits(t *testing.T) {
	tests := []struct {
		name string
		x    float64
		bits PrecisionBits
		want float64
	}{
		{
			name: "bits4",
			x:    0.519696,
			bits: 4,
			want: 0.5,
		},
		{
			name: "bits8",
			x:    0.519696,
			bits: 8,
			want: math.Round(0.519696*256.0) / 256.0,
		},
		{
			name: "negative",
			x:    -0.31,
			bits: 2,
			want: -0.25,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := QuantizeToBits(tt.x, tt.bits)
			if math.Abs(got-tt.want) > 1e-12 {
				t.Fatalf("QuantizeToBits mismatch: got %.12f, want %.12f", got, tt.want)
			}
		})
	}
}

func TestEvalQuantizedNoScheduleMatchesPlain(t *testing.T) {
	g := benchmarks.NewLogRegSmallGraph()
	sample := benchmarks.DefaultLogRegSmallSamples()[0]

	plain, err := EvalPlain(g, sample.Inputs())
	if err != nil {
		t.Fatalf("EvalPlain failed: %v", err)
	}

	quantized, err := EvalQuantized(g, sample.Inputs(), nil)
	if err != nil {
		t.Fatalf("EvalQuantized failed: %v", err)
	}

	if math.Abs(plain.Output-quantized.Output) > 1e-12 {
		t.Fatalf("output mismatch without schedule: plain %.12f, quantized %.12f", plain.Output, quantized.Output)
	}
}

func TestEvalQuantizedOutputNode(t *testing.T) {
	g := benchmarks.NewLogRegSmallGraph()
	sample := benchmarks.DefaultLogRegSmallSamples()[0]

	quantized, err := EvalQuantized(g, sample.Inputs(), PrecisionSchedule{
		ir.NodeID("y"): PrecisionBits(4),
	})
	if err != nil {
		t.Fatalf("EvalQuantized failed: %v", err)
	}

	want := 0.5
	if math.Abs(quantized.Output-want) > 1e-12 {
		t.Fatalf("unexpected quantized output: got %.12f, want %.12f", quantized.Output, want)
	}
}

func TestEvalQuantizedIntermediateNode(t *testing.T) {
	g := benchmarks.NewLogRegSmallGraph()
	sample := benchmarks.DefaultLogRegSmallSamples()[0]

	// For the first sample, z is 0.1.
	// Quantizing z with 0 fractional bits maps z to 0,
	// then y = 0.5 + 0.197*0 - 0.004*0^3 = 0.5.
	quantized, err := EvalQuantized(g, sample.Inputs(), PrecisionSchedule{
		ir.NodeID("z"): PrecisionBits(0),
	})
	if err != nil {
		t.Fatalf("EvalQuantized failed: %v", err)
	}

	want := 0.5
	if math.Abs(quantized.Output-want) > 1e-12 {
		t.Fatalf("unexpected output after quantizing z: got %.12f, want %.12f", quantized.Output, want)
	}
}
