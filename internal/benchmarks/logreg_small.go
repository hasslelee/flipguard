package benchmarks

import (
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
// Later, we will replace or extend this with generated boundary-focused samples.
func DefaultLogRegSmallSamples() []LogRegSmallSample {
	return []LogRegSmallSample{
		{X1: 1.0, X2: 2.0, X3: 0.5},
		{X1: 0.0, X2: 0.0, X3: 0.0},
		{X1: 1.0, X2: 1.0, X3: 1.0},
		{X1: -1.0, X2: 0.5, X3: 1.5},
		{X1: 0.5, X2: -1.0, X3: 0.25},
	}
}
