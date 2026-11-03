package benchmarks

import (
	"math"

	"github.com/hasslelee/flipguard/internal/ir"
)

const (
	SobelEdgeThreshold = 16.0
)

// SobelEdgeSample represents a 3x3 image patch:
//
//	p00 p01 p02
//	p10 p11 p12
//	p20 p21 p22
//
// The center pixel p11 is included for completeness even though the standard
// Sobel kernels do not use it.
type SobelEdgeSample struct {
	P00 float64
	P01 float64
	P02 float64

	P10 float64
	P11 float64
	P12 float64

	P20 float64
	P21 float64
	P22 float64
}

// SobelEdgeComponents stores the horizontal and vertical Sobel responses.
type SobelEdgeComponents struct {
	GX float64
	GY float64
}

// NewSobelEdgeGraph builds a Sobel edge-detection score graph.
//
// Kernels:
//
//	Gx = -p00 + p02 - 2*p10 + 2*p12 - p20 + p22
//	Gy = -p00 - 2*p01 - p02 + p20 + 2*p21 + p22
//
// Score:
//
//	score = Gx^2 + Gy^2
//
// Decision:
//
//	score >= SobelEdgeThreshold
//
// This benchmark is useful as the first vision-kernel workload because it has a
// clear threshold decision and exposes two quadratic program points, gx^2 and
// gy^2.
func NewSobelEdgeGraph() *ir.Graph {
	g := ir.NewGraph()

	g.MustAddNode(ir.NewInput("p00", "p00"))
	g.MustAddNode(ir.NewInput("p01", "p01"))
	g.MustAddNode(ir.NewInput("p02", "p02"))

	g.MustAddNode(ir.NewInput("p10", "p10"))
	g.MustAddNode(ir.NewInput("p11", "p11"))
	g.MustAddNode(ir.NewInput("p12", "p12"))

	g.MustAddNode(ir.NewInput("p20", "p20"))
	g.MustAddNode(ir.NewInput("p21", "p21"))
	g.MustAddNode(ir.NewInput("p22", "p22"))

	g.MustAddNode(ir.NewMulConst("gx_t00", "-p00", "p00", -1.0))
	g.MustAddNode(ir.NewMulConst("gx_t02", "p02", "p02", 1.0))
	g.MustAddNode(ir.NewMulConst("gx_t10", "-2*p10", "p10", -2.0))
	g.MustAddNode(ir.NewMulConst("gx_t12", "2*p12", "p12", 2.0))
	g.MustAddNode(ir.NewMulConst("gx_t20", "-p20", "p20", -1.0))
	g.MustAddNode(ir.NewMulConst("gx_t22", "p22", "p22", 1.0))

	g.MustAddNode(ir.NewBinary("gx_s1", "gx_t00+gx_t02", ir.OpAdd, "gx_t00", "gx_t02"))
	g.MustAddNode(ir.NewBinary("gx_s2", "gx_s1+gx_t10", ir.OpAdd, "gx_s1", "gx_t10"))
	g.MustAddNode(ir.NewBinary("gx_s3", "gx_s2+gx_t12", ir.OpAdd, "gx_s2", "gx_t12"))
	g.MustAddNode(ir.NewBinary("gx_s4", "gx_s3+gx_t20", ir.OpAdd, "gx_s3", "gx_t20"))
	g.MustAddNode(ir.NewBinary("gx", "sobel gx", ir.OpAdd, "gx_s4", "gx_t22"))

	g.MustAddNode(ir.NewMulConst("gy_t00", "-p00", "p00", -1.0))
	g.MustAddNode(ir.NewMulConst("gy_t01", "-2*p01", "p01", -2.0))
	g.MustAddNode(ir.NewMulConst("gy_t02", "-p02", "p02", -1.0))
	g.MustAddNode(ir.NewMulConst("gy_t20", "p20", "p20", 1.0))
	g.MustAddNode(ir.NewMulConst("gy_t21", "2*p21", "p21", 2.0))
	g.MustAddNode(ir.NewMulConst("gy_t22", "p22", "p22", 1.0))

	g.MustAddNode(ir.NewBinary("gy_s1", "gy_t00+gy_t01", ir.OpAdd, "gy_t00", "gy_t01"))
	g.MustAddNode(ir.NewBinary("gy_s2", "gy_s1+gy_t02", ir.OpAdd, "gy_s1", "gy_t02"))
	g.MustAddNode(ir.NewBinary("gy_s3", "gy_s2+gy_t20", ir.OpAdd, "gy_s2", "gy_t20"))
	g.MustAddNode(ir.NewBinary("gy_s4", "gy_s3+gy_t21", ir.OpAdd, "gy_s3", "gy_t21"))
	g.MustAddNode(ir.NewBinary("gy", "sobel gy", ir.OpAdd, "gy_s4", "gy_t22"))

	g.MustAddNode(ir.NewBinary("gx2", "gx^2", ir.OpMul, "gx", "gx"))
	g.MustAddNode(ir.NewBinary("gy2", "gy^2", ir.OpMul, "gy", "gy"))
	g.MustAddNode(ir.NewBinary("score", "sobel edge score", ir.OpAdd, "gx2", "gy2"))

	g.MustSetOutput("score")

	return g
}

// Inputs converts the sample into an IR input map.
func (s SobelEdgeSample) Inputs() map[ir.NodeID]float64 {
	return map[ir.NodeID]float64{
		"p00": s.P00,
		"p01": s.P01,
		"p02": s.P02,

		"p10": s.P10,
		"p11": s.P11,
		"p12": s.P12,

		"p20": s.P20,
		"p21": s.P21,
		"p22": s.P22,
	}
}

// SobelEdgeResponse evaluates the Sobel Gx and Gy responses directly over
// plaintext values.
func SobelEdgeResponse(s SobelEdgeSample) SobelEdgeComponents {
	gx := -s.P00 + s.P02 - 2.0*s.P10 + 2.0*s.P12 - s.P20 + s.P22
	gy := -s.P00 - 2.0*s.P01 - s.P02 + s.P20 + 2.0*s.P21 + s.P22

	return SobelEdgeComponents{
		GX: gx,
		GY: gy,
	}
}

// SobelEdgeScore evaluates the Sobel edge score directly over plaintext values.
func SobelEdgeScore(s SobelEdgeSample) float64 {
	response := SobelEdgeResponse(s)
	return response.GX*response.GX + response.GY*response.GY
}

// SobelEdgeDecision returns true when the sample is classified as an edge.
func SobelEdgeDecision(s SobelEdgeSample, threshold float64) bool {
	return SobelEdgeScore(s) >= threshold
}

// SobelEdgeMargin returns |score - threshold|.
func SobelEdgeMargin(s SobelEdgeSample, threshold float64) float64 {
	return math.Abs(SobelEdgeScore(s) - threshold)
}

// DefaultSobelEdgeSamples returns deterministic 3x3 patches.
//
// The set contains flat patches, strong vertical/horizontal edges, diagonal
// patterns, and near-threshold weak edges. The near-threshold cases are useful
// later for decision-stability certification.
func DefaultSobelEdgeSamples() []SobelEdgeSample {
	return []SobelEdgeSample{
		// Flat patches.
		{
			P00: 0.0, P01: 0.0, P02: 0.0,
			P10: 0.0, P11: 0.0, P12: 0.0,
			P20: 0.0, P21: 0.0, P22: 0.0,
		},
		{
			P00: 1.0, P01: 1.0, P02: 1.0,
			P10: 1.0, P11: 1.0, P12: 1.0,
			P20: 1.0, P21: 1.0, P22: 1.0,
		},

		// Canonical vertical edge, score = 16.
		{
			P00: 0.0, P01: 0.0, P02: 1.0,
			P10: 0.0, P11: 0.0, P12: 1.0,
			P20: 0.0, P21: 0.0, P22: 1.0,
		},

		// Canonical horizontal edge, score = 16.
		{
			P00: 0.0, P01: 0.0, P02: 0.0,
			P10: 0.0, P11: 0.0, P12: 0.0,
			P20: 1.0, P21: 1.0, P22: 1.0,
		},

		// Reversed vertical edge, score = 16.
		{
			P00: 1.0, P01: 1.0, P02: 0.0,
			P10: 1.0, P11: 1.0, P12: 0.0,
			P20: 1.0, P21: 1.0, P22: 0.0,
		},

		// Reversed horizontal edge, score = 16.
		{
			P00: 1.0, P01: 1.0, P02: 1.0,
			P10: 0.0, P11: 0.0, P12: 0.0,
			P20: 0.0, P21: 0.0, P22: 0.0,
		},

		// Diagonal contrast patterns.
		{
			P00: 0.0, P01: 0.0, P02: 1.0,
			P10: 0.0, P11: 1.0, P12: 1.0,
			P20: 1.0, P21: 1.0, P22: 1.0,
		},
		{
			P00: 1.0, P01: 1.0, P02: 0.0,
			P10: 1.0, P11: 1.0, P12: 0.0,
			P20: 0.0, P21: 0.0, P22: 0.0,
		},

		// Near-threshold weak edges.
		{
			P00: 0.0, P01: 0.0, P02: 0.95,
			P10: 0.0, P11: 0.0, P12: 0.95,
			P20: 0.0, P21: 0.0, P22: 0.95,
		},
		{
			P00: 0.0, P01: 0.0, P02: 1.05,
			P10: 0.0, P11: 0.0, P12: 1.05,
			P20: 0.0, P21: 0.0, P22: 1.05,
		},
	}
}

// SobelEdgeSampleGenOptions controls deterministic sample generation.
type SobelEdgeSampleGenOptions struct {
	Values []float64

	Threshold float64
	Gamma     float64

	MaxBoundary    int
	MaxNonBoundary int
}

// DefaultSobelEdgeSampleGenOptions returns a deterministic configuration for
// small-grid Sobel sample generation.
func DefaultSobelEdgeSampleGenOptions() SobelEdgeSampleGenOptions {
	return SobelEdgeSampleGenOptions{
		Values: []float64{
			0.0,
			0.25,
			0.50,
			0.75,
			1.0,
		},

		Threshold: SobelEdgeThreshold,
		Gamma:     0.50,

		MaxBoundary:    32,
		MaxNonBoundary: 32,
	}
}

// GenerateSobelEdgeSamples generates deterministic Sobel patches with both
// boundary and non-boundary cases.
//
// Boundary samples satisfy:
//
//	|score - threshold| <= gamma
//
// The scan is deterministic and stops once the requested number of boundary and
// non-boundary samples has been collected.
func GenerateSobelEdgeSamples(opts SobelEdgeSampleGenOptions) []SobelEdgeSample {
	if len(opts.Values) == 0 {
		opts.Values = []float64{0.0, 0.25, 0.50, 0.75, 1.0}
	}
	if opts.Threshold == 0 {
		opts.Threshold = SobelEdgeThreshold
	}
	if opts.Gamma <= 0 {
		opts.Gamma = 0.50
	}
	if opts.MaxBoundary <= 0 {
		opts.MaxBoundary = 32
	}
	if opts.MaxNonBoundary <= 0 {
		opts.MaxNonBoundary = 32
	}

	boundary := make([]SobelEdgeSample, 0, opts.MaxBoundary)
	nonBoundary := make([]SobelEdgeSample, 0, opts.MaxNonBoundary)

	values := opts.Values

	for _, p00 := range values {
		for _, p01 := range values {
			for _, p02 := range values {
				for _, p10 := range values {
					for _, p11 := range values {
						for _, p12 := range values {
							for _, p20 := range values {
								for _, p21 := range values {
									for _, p22 := range values {
										sample := SobelEdgeSample{
											P00: p00,
											P01: p01,
											P02: p02,

											P10: p10,
											P11: p11,
											P12: p12,

											P20: p20,
											P21: p21,
											P22: p22,
										}

										margin := SobelEdgeMargin(sample, opts.Threshold)

										if margin <= opts.Gamma {
											if len(boundary) < opts.MaxBoundary {
												boundary = append(boundary, sample)
											}
										} else {
											if len(nonBoundary) < opts.MaxNonBoundary {
												nonBoundary = append(nonBoundary, sample)
											}
										}

										if len(boundary) >= opts.MaxBoundary && len(nonBoundary) >= opts.MaxNonBoundary {
											return append(boundary, nonBoundary...)
										}
									}
								}
							}
						}
					}
				}
			}
		}
	}

	return append(boundary, nonBoundary...)
}
