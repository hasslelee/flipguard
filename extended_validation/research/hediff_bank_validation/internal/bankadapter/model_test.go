package bankadapter

import (
	"math"
	"testing"
)

// Verify both original outputs, not just argmax, over bounded deterministic
// weights/inputs including negative preactivations and a tied output model.
func TestExactTwoLogitAlgebra(t *testing.T) {
	m := ModelArtifact{DatasetID: "hediff_bank_additional_public_procedure", ModelID: "hediff_bank_mlp_20_256_2_seed20260906", ModelType: MLPModelType, W: make([][]float64, MLPHidden), B: make([]float64, MLPHidden), V: make([][]float64, 2), D: []float64{.17, -.23}}
	for h := 0; h < MLPHidden; h++ {
		m.W[h] = make([]float64, PixelCount)
		m.B[h] = float64(h%11-5) / 19
		for j := 0; j < PixelCount; j++ {
			m.W[h][j] = float64((h*13+j*7)%31-15) / 47
		}
	}
	for c := 0; c < 2; c++ {
		m.V[c] = make([]float64, MLPHidden)
		for h := 0; h < MLPHidden; h++ {
			m.V[c][h] = float64((h*3+c*7)%17-8) / 53
		}
	}
	for i := 0; i < 32; i++ {
		var r PartitionRow
		for j := range r.Pixels {
			r.Pixels[j] = float64((i*17+j*11)%67) / 66
		}
		z, e := m.Logits(r)
		if e != nil {
			t.Fatal(e)
		}
		for c := 0; c < 2; c++ {
			v := m.OutputBias(c)
			for h := 0; h < MLPHidden; h++ {
				a := m.HiddenBias(h)
				for j, x := range r.Pixels {
					a += m.HiddenWeight(h, j) * x
				}
				v += m.OutputWeight(c, h) * a * a
			}
			if math.Abs(v-z[c]) > 1e-12 {
				t.Fatalf("output %d identity drift: %.17g", c, v-z[c])
			}
		}
	}
	m.V[1] = append([]float64{}, m.V[0]...)
	m.D[1] = m.D[0]
	z, _ := m.Logits(PartitionRow{})
	if z[0] != z[1] {
		t.Fatal("tie lost")
	}
}
