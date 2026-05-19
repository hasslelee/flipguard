package benchmarks

import (
	"math"

	"github.com/hasslelee/flipguard/internal/ir"
)

const (
	LogRegSmallThreshold = 0.5
)

// NewLogRegSmallGraph builds the running example graph:
//
//	z = 0.8*x1 - 0.5*x2 + 1.2*x3 - 0.3
//	y = 0.5 + 0.197*z - 0.004*z^3
//
// The output node is "y".
func NewLogRegSmallGraph() *ir.Graph {
	g := ir.NewGraph()

	g.MustAddNode(ir.NewInput("x1", "x1"))
	g.MustAddNode(ir.NewInput("x2", "x2"))
	g.MustAddNode(ir.NewInput("x3", "x3"))

	g.MustAddNode(ir.NewMulConst("t1", "0.8*x1", "x1", 0.8))
	g.MustAddNode(ir.NewMulConst("t2", "-0.5*x2", "x2", -0.5))
	g.MustAddNode(ir.NewMulConst("t3", "1.2*x3", "x3", 1.2))

	g.MustAddNode(ir.NewBinary("s1", "t1+t2", ir.OpAdd, "t1", "t2"))
	g.MustAddNode(ir.NewBinary("s2", "s1+t3", ir.OpAdd, "s1", "t3"))

	g.MustAddNode(ir.NewConst("bias", "-0.3", -0.3))
	g.MustAddNode(ir.NewBinary("z", "linear score z", ir.OpAdd, "s2", "bias"))

	g.MustAddNode(ir.NewPoly("y", "cubic sigmoid approximation", "z", []float64{
		0.5,    // c0
		0.197,  // c1
		0.0,    // c2
		-0.004, // c3
	}))

	g.MustSetOutput("y")

	return g
}

// LogRegSmallScore evaluates the running example directly over plaintext values.
func LogRegSmallScore(s LogRegSmallSample) float64 {
	z := 0.8*s.X1 - 0.5*s.X2 + 1.2*s.X3 - 0.3
	return 0.5 + 0.197*z - 0.004*z*z*z
}

// LogRegSmallMargin returns |score - threshold|.
func LogRegSmallMargin(s LogRegSmallSample, threshold float64) float64 {
	return math.Abs(LogRegSmallScore(s) - threshold)
}

// LogRegSmallSample represents one input sample for the running example.
type LogRegSmallSample struct {
	X1 float64
	X2 float64
	X3 float64
}

// Inputs converts the sample into an IR input map.
func (s LogRegSmallSample) Inputs() map[ir.NodeID]float64 {
	return map[ir.NodeID]float64{
		"x1": s.X1,
		"x2": s.X2,
		"x3": s.X3,
	}
}

// DefaultLogRegSmallSamples returns a small deterministic sample set.
//
// This is mainly used for unit tests and sanity checks.
func DefaultLogRegSmallSamples() []LogRegSmallSample {
	return []LogRegSmallSample{
		{X1: 1.0, X2: 2.0, X3: 0.5},
		{X1: 0.0, X2: 0.0, X3: 0.0},
		{X1: 1.0, X2: 1.0, X3: 1.0},
		{X1: -1.0, X2: 0.5, X3: 1.5},
		{X1: 0.5, X2: -1.0, X3: 0.25},
	}
}

// LogRegSmallSampleGenOptions controls deterministic sample generation.
type LogRegSmallSampleGenOptions struct {
	RangeMin float64
	RangeMax float64
	Step     float64

	Threshold float64
	Gamma     float64

	MaxBoundary    int
	MaxNonBoundary int
}

// DefaultBoundaryFocusedOptions returns a deterministic configuration that
// intentionally collects many samples near the decision boundary.
func DefaultBoundaryFocusedOptions() LogRegSmallSampleGenOptions {
	return LogRegSmallSampleGenOptions{
		RangeMin: -2.0,
		RangeMax: 2.0,
		Step:     0.05,

		Threshold: LogRegSmallThreshold,
		Gamma:     0.05,

		MaxBoundary:    100,
		MaxNonBoundary: 100,
	}
}

// GenerateLogRegSmallSamples generates a deterministic sample set with both
// boundary and non-boundary samples.
//
// Boundary samples satisfy:
//
//	|f_plain(x) - threshold| <= gamma
//
// The generator uses a grid scan for reproducibility.
func GenerateLogRegSmallSamples(opts LogRegSmallSampleGenOptions) []LogRegSmallSample {
	if opts.Step <= 0 {
		opts.Step = 0.1
	}
	if opts.RangeMax < opts.RangeMin {
		opts.RangeMin, opts.RangeMax = opts.RangeMax, opts.RangeMin
	}
	if opts.Threshold == 0 {
		opts.Threshold = LogRegSmallThreshold
	}

	boundary := make([]LogRegSmallSample, 0, opts.MaxBoundary)
	nonBoundary := make([]LogRegSmallSample, 0, opts.MaxNonBoundary)

	steps := int(math.Round((opts.RangeMax - opts.RangeMin) / opts.Step))

	for i := 0; i <= steps; i++ {
		x1 := roundGrid(opts.RangeMin + float64(i)*opts.Step)

		for j := 0; j <= steps; j++ {
			x2 := roundGrid(opts.RangeMin + float64(j)*opts.Step)

			for k := 0; k <= steps; k++ {
				x3 := roundGrid(opts.RangeMin + float64(k)*opts.Step)

				s := LogRegSmallSample{X1: x1, X2: x2, X3: x3}
				margin := LogRegSmallMargin(s, opts.Threshold)

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

	return append(boundary, nonBoundary...)
}

func roundGrid(x float64) float64 {
	return math.Round(x*1e12) / 1e12
}
