package benchmarks

import (
	"github.com/hasslelee/flipguard/internal/ir"
)

// NewSobelEdgeRescaleGraph is the rescale-aware Sobel graph used by the
// non-tabular direct-synthesis extension. It computes the same score as
// NewSobelEdgeGraph, but represents the two squares as explicit Pow2 nodes so
// the planner scale trace matches the Lattigo evaluator.
func NewSobelEdgeRescaleGraph() *ir.Graph {
	g := ir.NewGraph()

	for _, id := range []ir.NodeID{
		"p00", "p01", "p02",
		"p10", "p11", "p12",
		"p20", "p21", "p22",
	} {
		g.MustAddNode(ir.NewInput(id, string(id)))
	}

	addSobelTerm := func(
		id ir.NodeID,
		input ir.NodeID,
		coefficient float64,
	) {
		g.MustAddNode(
			ir.NewMulConst(id, string(id), input, coefficient),
		)
	}
	addSobelTerm("gx_t00", "p00", -1.0)
	addSobelTerm("gx_t02", "p02", 1.0)
	addSobelTerm("gx_t10", "p10", -2.0)
	addSobelTerm("gx_t12", "p12", 2.0)
	addSobelTerm("gx_t20", "p20", -1.0)
	addSobelTerm("gx_t22", "p22", 1.0)
	addSobelTerm("gy_t00", "p00", -1.0)
	addSobelTerm("gy_t01", "p01", -2.0)
	addSobelTerm("gy_t02", "p02", -1.0)
	addSobelTerm("gy_t20", "p20", 1.0)
	addSobelTerm("gy_t21", "p21", 2.0)
	addSobelTerm("gy_t22", "p22", 1.0)

	addChain := func(
		output ir.NodeID,
		terms ...ir.NodeID,
	) {
		current := terms[0]
		for index := 1; index < len(terms); index++ {
			id := ir.NodeID(string(output) + "_s" + string(rune('0'+index)))
			if index == len(terms)-1 {
				id = output
			}
			g.MustAddNode(
				ir.NewBinary(id, string(id), ir.OpAdd, current, terms[index]),
			)
			current = id
		}
	}
	addChain(
		"gx",
		"gx_t00", "gx_t02", "gx_t10",
		"gx_t12", "gx_t20", "gx_t22",
	)
	addChain(
		"gy",
		"gy_t00", "gy_t01", "gy_t02",
		"gy_t20", "gy_t21", "gy_t22",
	)

	g.MustAddNode(ir.NewUnary("gx2", "gx^2", ir.OpPow2, "gx"))
	g.MustAddNode(ir.NewUnary("gy2", "gy^2", ir.OpPow2, "gy"))
	g.MustAddNode(
		ir.NewBinary(
			"score",
			"sobel edge score",
			ir.OpAdd,
			"gx2",
			"gy2",
		),
	)
	g.MustSetOutput("score")
	return g
}
