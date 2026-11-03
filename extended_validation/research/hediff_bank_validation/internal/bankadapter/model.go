// Package bankadapter preserves the original HEDiff Bank two-logit polynomial.
// The CKKS graph uses t*t+t=(t+.5)^2-.25, without collapsing or normalizing logits.
package bankadapter

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"github.com/hasslelee/flipguard/internal/journalmnist"
	"math"
	"os"
	"strconv"
)

const PixelCount = 20
const MLPHidden = 256
const ClassCount = 2
const MLPModelType = "hediff_bank_exact_two_logit_square_adapter_v1"

type ModelArtifact struct {
	DatasetID string      `json:"dataset_id"`
	ModelID   string      `json:"model_id"`
	ModelType string      `json:"model_type"`
	W         [][]float64 `json:"original_w1"`
	B         []float64   `json:"original_b1"`
	V         [][]float64 `json:"original_w2"`
	D         []float64   `json:"original_b2"`
}
type PartitionRow struct {
	RowID           int
	SampleID        string
	SourceIndex     int
	SourcePartition string
	Role            string
	Label           int
	Pixels          [PixelCount]float64
}

func LoadModelArtifact(p string) (ModelArtifact, error) {
	var m ModelArtifact
	b, e := os.ReadFile(p)
	if e != nil {
		return m, e
	}
	if e = json.Unmarshal(b, &m); e != nil {
		return m, e
	}
	return m, m.Validate()
}
func (m ModelArtifact) Validate() error {
	if m.ModelType != MLPModelType || m.DatasetID != "hediff_bank_additional_public_procedure" || m.ModelID != "hediff_bank_mlp_20_256_2_seed20260906" {
		return fmt.Errorf("unexpected Bank model identity")
	}
	if len(m.W) != MLPHidden || len(m.B) != MLPHidden || len(m.V) != ClassCount || len(m.D) != ClassCount {
		return fmt.Errorf("invalid Bank dimensions")
	}
	for _, r := range m.W {
		if len(r) != PixelCount {
			return fmt.Errorf("invalid W1 dimensions")
		}
	}
	for _, r := range m.V {
		if len(r) != MLPHidden {
			return fmt.Errorf("invalid W2 dimensions")
		}
	}
	for _, r := range append(append([][]float64{}, m.W...), m.V...) {
		for _, v := range r {
			if math.IsNaN(v) || math.IsInf(v, 0) {
				return fmt.Errorf("nonfinite weight")
			}
		}
	}
	for _, r := range [][]float64{m.B, m.D} {
		for _, v := range r {
			if math.IsNaN(v) || math.IsInf(v, 0) {
				return fmt.Errorf("nonfinite bias")
			}
		}
	}
	return nil
}
func LoadPartitionCSV(p, role string) ([]PartitionRow, error) {
	f, e := os.Open(p)
	if e != nil {
		return nil, e
	}
	defer f.Close()
	a, e := csv.NewReader(f).ReadAll()
	if e != nil {
		return nil, e
	}
	if len(a) < 2 {
		return nil, fmt.Errorf("empty Bank inputs")
	}
	cols := map[string]int{}
	for i, v := range a[0] {
		cols[v] = i
	}
	needed := []string{"row_id", "original_label", "source_row_id"}
	for j := 0; j < PixelCount; j++ {
		needed = append(needed, fmt.Sprintf("x_%d", j))
	}
	for _, s := range needed {
		if _, ok := cols[s]; !ok {
			return nil, fmt.Errorf("missing column %s", s)
		}
	}
	out := []PartitionRow{}
	seen := map[int]bool{}
	for _, a := range a[1:] {
		r := PartitionRow{Role: role, SourcePartition: "official_public_procedure_test"}
		var e error
		r.RowID, e = strconv.Atoi(a[cols["row_id"]])
		if e != nil {
			return nil, e
		}
		if seen[r.RowID] {
			return nil, fmt.Errorf("duplicate row")
		}
		seen[r.RowID] = true
		r.SampleID = fmt.Sprintf("bank_test_%d", r.RowID)
		r.Label, e = strconv.Atoi(a[cols["original_label"]])
		if e != nil || r.Label < 0 || r.Label >= 2 {
			return nil, fmt.Errorf("bad label")
		}
		r.SourceIndex, e = strconv.Atoi(a[cols["source_row_id"]])
		if e != nil {
			return nil, e
		}
		for j := 0; j < PixelCount; j++ {
			v, e := strconv.ParseFloat(a[cols[fmt.Sprintf("x_%d", j)]], 64)
			if e != nil || math.IsNaN(v) || math.IsInf(v, 0) || v < 0 || v > 1 {
				return nil, fmt.Errorf("invalid normalized feature")
			}
			r.Pixels[j] = v
		}
		out = append(out, r)
	}
	return out, nil
}
func (m ModelArtifact) Logits(r PartitionRow) ([ClassCount]float64, error) {
	var z [ClassCount]float64
	copy(z[:], m.D)
	for h := 0; h < MLPHidden; h++ {
		t := m.B[h]
		for j, v := range r.Pixels {
			t += m.W[h][j] * v
		}
		a := t*t + t
		for c := 0; c < ClassCount; c++ {
			z[c] += m.V[c][h] * a
		}
	}
	return z, nil
}
func (m ModelArtifact) HiddenWeight(h, j int) float64 { return m.W[h][j] }
func (m ModelArtifact) HiddenBias(h int) float64      { return m.B[h] + .5 }
func (m ModelArtifact) OutputWeight(c, h int) float64 { return m.V[c][h] }
func (m ModelArtifact) OutputBias(c int) float64 {
	s := 0.
	for _, v := range m.V[c] {
		s += v
	}
	return m.D[c] - .25*s
}

// Same layerwise primitive-count/backward L-infinity rule as journal MLP.
// Dimensions and observed shifted-hidden range follow this exact graph.
func CalibrateModel(m ModelArtifact, rows []PartitionRow) (journalmnist.CalibrationSummary, error) {
	if e := m.Validate(); e != nil {
		return journalmnist.CalibrationSummary{}, e
	}
	if len(rows) == 0 {
		return journalmnist.CalibrationSummary{}, fmt.Errorf("empty calibration")
	}
	maxH, maxZ, maxX, n1, n2 := 0., 0., 0., 0., 0.
	for _, r := range rows {
		z, _ := m.Logits(r)
		for _, v := range z {
			maxZ = math.Max(maxZ, math.Abs(v))
		}
		for _, v := range r.Pixels {
			maxX = math.Max(maxX, math.Abs(v))
		}
		for h := 0; h < MLPHidden; h++ {
			t := m.HiddenBias(h)
			for j, v := range r.Pixels {
				t += m.W[h][j] * v
			}
			maxH = math.Max(maxH, math.Abs(t))
		}
	}
	for _, r := range m.W {
		s := 0.
		for _, v := range r {
			s += math.Abs(v)
		}
		n1 = math.Max(n1, s)
	}
	for _, r := range m.V {
		s := 0.
		for _, v := range r {
			s += math.Abs(v)
		}
		n2 = math.Max(n2, s)
	}
	return journalmnist.CalibrationSummary{Method: journalmnist.LayerwiseIntervalSensitivityV1, Scope: "fixed Bank selection rows; exact two-logit algebraic adapter", MaxInputAbs: maxX, MaxPlaintextLogitAbs: maxZ, AggregateSensitivity: math.Max(1, 2*MLPHidden+n2+n2*2*maxH*(2*PixelCount)), StageMaxAbs: map[string]float64{"shifted_hidden_pre": maxH, "logit": maxZ}, StageLInfNorm: map[string]float64{"affine_1": n1, "square_1": 2 * maxH, "affine_2": n2}, PrimitiveTerms: map[string]int{"affine_20_to_256": 2 * PixelCount, "square_hidden": 1, "affine_256_to_2": 2 * MLPHidden}}, nil
}
