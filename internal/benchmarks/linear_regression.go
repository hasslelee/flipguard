package benchmarks

import (
	"math"

	"github.com/hasslelee/flipguard/internal/ir"
)

const (
	LinearRegressionThreshold = 0.0
)

// NewLinearRegressionGraph builds a low-depth linear regression control graph:
//
//	y = 0.35*x1 - 0.20*x2 + 0.15*x3 + 0.10*x4 - 0.05
//
// This benchmark is intentionally shallow. It is used as a control workload for
// the planner: a decision-stability-aware planner should not over-provision a
// deep CKKS chain for a purely affine model.
func NewLinearRegressionGraph() *ir.Graph {
	g := ir.NewGraph()

	g.MustAddNode(ir.NewInput("x1", "x1"))
	g.MustAddNode(ir.NewInput("x2", "x2"))
	g.MustAddNode(ir.NewInput("x3", "x3"))
	g.MustAddNode(ir.NewInput("x4", "x4"))

	g.MustAddNode(ir.NewMulConst("t1", "0.35*x1", "x1", 0.35))
	g.MustAddNode(ir.NewMulConst("t2", "-0.20*x2", "x2", -0.20))
	g.MustAddNode(ir.NewMulConst("t3", "0.15*x3", "x3", 0.15))
	g.MustAddNode(ir.NewMulConst("t4", "0.10*x4", "x4", 0.10))

	g.MustAddNode(ir.NewBinary("s1", "t1+t2", ir.OpAdd, "t1", "t2"))
	g.MustAddNode(ir.NewBinary("s2", "s1+t3", ir.OpAdd, "s1", "t3"))
	g.MustAddNode(ir.NewBinary("s3", "s2+t4", ir.OpAdd, "s2", "t4"))

	g.MustAddNode(ir.NewConst("bias", "-0.05", -0.05))
	g.MustAddNode(ir.NewBinary("y", "linear regression score", ir.OpAdd, "s3", "bias"))

	g.MustSetOutput("y")

	return g
}

// LinearRegressionScore evaluates the linear regression benchmark directly over
// plaintext values.
func LinearRegressionScore(s LinearRegressionSample) float64 {
	return 0.35*s.X1 - 0.20*s.X2 + 0.15*s.X3 + 0.10*s.X4 - 0.05
}

// LinearRegressionMargin returns |score - threshold|.
func LinearRegressionMargin(s LinearRegressionSample, threshold float64) float64 {
	return math.Abs(LinearRegressionScore(s) - threshold)
}

// LinearRegressionSample represents one input sample for the linear regression
// benchmark.
type LinearRegressionSample struct {
	X1 float64
	X2 float64
	X3 float64
	X4 float64
}

// Inputs converts the sample into an IR input map.
func (s LinearRegressionSample) Inputs() map[ir.NodeID]float64 {
	return map[ir.NodeID]float64{
		"x1": s.X1,
		"x2": s.X2,
		"x3": s.X3,
		"x4": s.X4,
	}
}

// DefaultLinearRegressionSamples returns a small deterministic sample set.
//
// The set intentionally includes near-boundary and far-from-boundary cases so
// decision flip behavior can be checked later.
func DefaultLinearRegressionSamples() []LinearRegressionSample {
	return []LinearRegressionSample{
		// Exact or near decision-boundary cases.
		{X1: 1.0 / 7.0, X2: 0.0, X3: 0.0, X4: 0.0},
		{X1: 0.15, X2: 0.0, X3: 0.0, X4: 0.0},
		{X1: 0.13, X2: 0.0, X3: 0.0, X4: 0.0},

		// Positive side.
		{X1: 1.0, X2: 0.0, X3: 0.5, X4: 0.0},
		{X1: 0.5, X2: -0.5, X3: 0.25, X4: 0.75},
		{X1: 2.0, X2: -1.0, X3: 1.0, X4: 1.0},

		// Negative side.
		{X1: 0.0, X2: 1.0, X3: 0.0, X4: 0.0},
		{X1: -1.0, X2: 0.5, X3: 0.0, X4: -0.5},
		{X1: -2.0, X2: 1.0, X3: -1.0, X4: 0.0},
	}
}

// LinearRegressionSampleGenOptions controls deterministic sample generation.
type LinearRegressionSampleGenOptions struct {
	RangeMin float64
	RangeMax float64
	Step     float64

	Threshold float64
	Gamma     float64

	MaxBoundary    int
	MaxNonBoundary int
}

// DefaultLinearRegressionSampleGenOptions returns a deterministic configuration
// that collects a balanced set of boundary and non-boundary samples.
func DefaultLinearRegressionSampleGenOptions() LinearRegressionSampleGenOptions {
	return LinearRegressionSampleGenOptions{
		RangeMin: -2.0,
		RangeMax: 2.0,
		Step:     0.25,

		Threshold: LinearRegressionThreshold,
		Gamma:     0.02,

		MaxBoundary:    32,
		MaxNonBoundary: 32,
	}
}

// GenerateLinearRegressionSamples generates a deterministic sample set with both
// boundary and non-boundary samples.
//
// Boundary samples satisfy:
//
//	|f_plain(x) - threshold| <= gamma
//
// The generator uses a grid scan for reproducibility.
func GenerateLinearRegressionSamples(opts LinearRegressionSampleGenOptions) []LinearRegressionSample {
	if opts.Step <= 0 {
		opts.Step = 0.25
	}
	if opts.RangeMax < opts.RangeMin {
		opts.RangeMin, opts.RangeMax = opts.RangeMax, opts.RangeMin
	}
	if opts.Gamma <= 0 {
		opts.Gamma = 0.02
	}
	if opts.MaxBoundary <= 0 {
		opts.MaxBoundary = 32
	}
	if opts.MaxNonBoundary <= 0 {
		opts.MaxNonBoundary = 32
	}

	boundary := make([]LinearRegressionSample, 0, opts.MaxBoundary)
	nonBoundary := make([]LinearRegressionSample, 0, opts.MaxNonBoundary)

	steps := int(math.Round((opts.RangeMax - opts.RangeMin) / opts.Step))

	for i := 0; i <= steps; i++ {
		x1 := roundGrid(opts.RangeMin + float64(i)*opts.Step)

		for j := 0; j <= steps; j++ {
			x2 := roundGrid(opts.RangeMin + float64(j)*opts.Step)

			for k := 0; k <= steps; k++ {
				x3 := roundGrid(opts.RangeMin + float64(k)*opts.Step)

				for l := 0; l <= steps; l++ {
					x4 := roundGrid(opts.RangeMin + float64(l)*opts.Step)

					s := LinearRegressionSample{
						X1: x1,
						X2: x2,
						X3: x3,
						X4: x4,
					}

					margin := LinearRegressionMargin(s, opts.Threshold)

					if margin <= opts.Gamma {
						if len(boundary) < opts.MaxBoundary {
							boundary = append(boundary, s)
						}
					} else {
						if len(nonBoundary) < opts.MaxNonBoundary {
							nonBoundary = append(nonBoundary, s)
						}
					}

					if len(boundary) >= opts.MaxBoundary && len(nonBoundary) >= opts.MaxNonBoundary {
						return append(boundary, nonBoundary...)
					}
				}
			}
		}
	}

	return append(boundary, nonBoundary...)
}
