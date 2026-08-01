package journalmnist

import (
	"fmt"
	"math"
)

const LayerwiseIntervalSensitivityV1 = "empirical_layerwise_linf_roundoff_v1"

// CalibrationSummary is a planning signal derived only from the frozen
// configuration-validation rows. It is not an analytical CKKS certificate;
// every selected literal still requires encrypted multiclass admission.
type CalibrationSummary struct {
	Method               string             `json:"method"`
	Scope                string             `json:"scope"`
	MaxInputAbs          float64            `json:"max_input_abs"`
	MaxPlaintextLogitAbs float64            `json:"max_plaintext_logit_abs"`
	AggregateSensitivity float64            `json:"aggregate_sensitivity"`
	StageMaxAbs          map[string]float64 `json:"stage_max_abs"`
	StageLInfNorm        map[string]float64 `json:"stage_linf_norm"`
	PrimitiveTerms       map[string]int     `json:"primitive_terms_per_output"`
}

// CalibrateModel computes an interval-driven layerwise L-infinity roundoff
// amplification signal. Each stage contribution is the number of arithmetic
// primitives along one output coordinate multiplied by the product of the
// downstream affine norms and square-activation derivative bounds. The signal
// proposes precision only; observed encrypted error remains decisive.
func CalibrateModel(artifact ModelArtifact, rows []PartitionRow) (CalibrationSummary, error) {
	if err := artifact.Validate(); err != nil {
		return CalibrationSummary{}, err
	}
	if len(rows) == 0 {
		return CalibrationSummary{}, fmt.Errorf("calibration rows are empty")
	}
	switch artifact.ModelType {
	case MLPModelType:
		return calibrateMLP(artifact, rows), nil
	case LeNetModelType:
		return calibrateLeNet(artifact, rows), nil
	default:
		return CalibrationSummary{}, fmt.Errorf("unsupported calibration model %q", artifact.ModelType)
	}
}

func calibrateMLP(artifact ModelArtifact, rows []PartitionRow) CalibrationSummary {
	parameters := artifact.Parameters
	maxHiddenPre := 0.0
	maxLogit := 0.0
	for _, row := range rows {
		sample := sparseSample{label: row.Label, pixels: make([]sparsePixel, 0, 192)}
		for index, raw := range row.Pixels {
			if raw != 0 {
				sample.pixels = append(sample.pixels, sparsePixel{index: uint16(index), value: float64(raw) / 255})
			}
		}
		var hiddenPre [MLPHidden]float64
		var hidden [MLPHidden]float64
		var logits [ClassCount]float64
		forwardSparseMLP(parameters, sample, &hiddenPre, &hidden, &logits)
		for _, value := range hiddenPre {
			maxHiddenPre = math.Max(maxHiddenPre, math.Abs(value))
		}
		for _, value := range logits {
			maxLogit = math.Max(maxLogit, math.Abs(value))
		}
	}
	affine1Norm := maxRowAbsSum(parameters, mlpW1Offset, MLPHidden, PixelCount)
	affine2Norm := maxRowAbsSum(parameters, mlpW2Offset, ClassCount, MLPHidden)
	square1Lip := 2 * maxHiddenPre
	primitive := map[string]int{
		"affine_784_to_100": 2 * PixelCount,
		"square_hidden":     1,
		"affine_100_to_10":  2 * MLPHidden,
	}
	// Reverse accumulation of per-coordinate local roundoff contributions.
	downstream := 1.0
	sensitivity := float64(primitive["affine_100_to_10"]) * downstream
	downstream *= affine2Norm
	sensitivity += float64(primitive["square_hidden"]) * downstream
	downstream *= square1Lip
	sensitivity += float64(primitive["affine_784_to_100"]) * downstream
	return CalibrationSummary{
		Method:               LayerwiseIntervalSensitivityV1,
		Scope:                "500 frozen configuration-validation rows; layerwise L-infinity planning signal",
		MaxInputAbs:          1,
		MaxPlaintextLogitAbs: maxLogit,
		AggregateSensitivity: math.Max(1, sensitivity),
		StageMaxAbs:          map[string]float64{"hidden_pre": maxHiddenPre, "logit": maxLogit},
		StageLInfNorm:        map[string]float64{"affine_1": affine1Norm, "square_1": square1Lip, "affine_2": affine2Norm},
		PrimitiveTerms:       primitive,
	}
}

func calibrateLeNet(artifact ModelArtifact, rows []PartitionRow) CalibrationSummary {
	parameters := artifact.Parameters
	maxima := map[string]float64{"c1_pre": 0, "c2_pre": 0, "fc1_pre": 0, "fc2_pre": 0, "logit": 0}
	for _, row := range rows {
		sample := Sample{SourceIndex: row.SourceIndex, Label: row.Label, Pixels: row.Pixels}
		var scratch lenetScratch
		forwardLeNet(parameters, sample, &scratch)
		updateMaxSlice(maxima, "c1_pre", scratch.c1Pre[:])
		updateMaxSlice(maxima, "c2_pre", scratch.c2Pre[:])
		updateMaxSlice(maxima, "fc1_pre", scratch.f1Pre[:])
		updateMaxSlice(maxima, "fc2_pre", scratch.f2Pre[:])
		updateMaxSlice(maxima, "logit", scratch.logits[:])
	}
	norms := map[string]float64{
		"conv_1":   maxRowAbsSum(parameters, lenetC1WOffset, lenetC1Channels, lenetKernelSide*lenetKernelSide),
		"square_1": 2 * maxima["c1_pre"],
		"pool_1":   1,
		"conv_2":   maxRowAbsSum(parameters, lenetC2WOffset, lenetC2Channels, lenetC1Channels*lenetKernelSide*lenetKernelSide),
		"square_2": 2 * maxima["c2_pre"],
		"pool_2":   1,
		"fc_1":     maxRowAbsSum(parameters, lenetFC1WOffset, lenetFC1, lenetC2Channels*lenetP2Side*lenetP2Side),
		"square_3": 2 * maxima["fc1_pre"],
		"fc_2":     maxRowAbsSum(parameters, lenetFC2WOffset, lenetFC2, lenetFC1),
		"square_4": 2 * maxima["fc2_pre"],
		"output":   maxRowAbsSum(parameters, lenetOutWOffset, ClassCount, lenetFC2),
	}
	primitive := map[string]int{
		"conv_1":   2 * lenetKernelSide * lenetKernelSide,
		"square_1": 1,
		"pool_1":   4,
		"conv_2":   2 * lenetC1Channels * lenetKernelSide * lenetKernelSide,
		"square_2": 1,
		"pool_2":   4,
		"fc_1":     2 * lenetC2Channels * lenetP2Side * lenetP2Side,
		"square_3": 1,
		"fc_2":     2 * lenetFC1,
		"square_4": 1,
		"output":   2 * lenetFC2,
	}
	// Traverse the declared graph from logits back to input. Pooling has L-inf
	// norm one but still contributes its own four arithmetic terms.
	stages := []struct {
		name         string
		upstreamNorm string
	}{
		{"output", "output"},
		{"square_4", "square_4"},
		{"fc_2", "fc_2"},
		{"square_3", "square_3"},
		{"fc_1", "fc_1"},
		{"pool_2", "pool_2"},
		{"square_2", "square_2"},
		{"conv_2", "conv_2"},
		{"pool_1", "pool_1"},
		{"square_1", "square_1"},
		{"conv_1", "conv_1"},
	}
	downstream := 1.0
	sensitivity := 0.0
	for _, stage := range stages {
		sensitivity += float64(primitive[stage.name]) * downstream
		downstream *= norms[stage.upstreamNorm]
	}
	return CalibrationSummary{
		Method:               LayerwiseIntervalSensitivityV1,
		Scope:                "500 frozen configuration-validation rows; layerwise L-infinity planning signal",
		MaxInputAbs:          1,
		MaxPlaintextLogitAbs: maxima["logit"],
		AggregateSensitivity: math.Max(1, sensitivity),
		StageMaxAbs:          maxima,
		StageLInfNorm:        norms,
		PrimitiveTerms:       primitive,
	}
}

func maxRowAbsSum(parameters []float64, offset, rows, columns int) float64 {
	maximum := 0.0
	for row := 0; row < rows; row++ {
		total := 0.0
		for column := 0; column < columns; column++ {
			total += math.Abs(parameters[offset+row*columns+column])
		}
		maximum = math.Max(maximum, total)
	}
	return maximum
}

func updateMaxSlice(maxima map[string]float64, name string, values []float64) {
	for _, value := range values {
		maxima[name] = math.Max(maxima[name], math.Abs(value))
	}
}
