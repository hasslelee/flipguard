package runtime

import (
	"math"
	"testing"

	"github.com/hasslelee/flipguard/internal/ir"
)

func TestEvalPlainLogRegSmall(t *testing.T) {
	g := ir.NewGraph()

	// z = 0.8*x1 - 0.5*x2 + 1.2*x3 - 0.3
	// y = 0.5 + 0.197*z - 0.004*z^3
	g.MustAddNode(ir.NewInput("x1", "x1"))
	g.MustAddNode(ir.NewInput("x2", "x2"))
	g.MustAddNode(ir.NewInput("x3", "x3"))

	g.MustAddNode(ir.NewMulConst("t1", "0.8*x1", "x1", 0.8))
	g.MustAddNode(ir.NewMulConst("t2", "-0.5*x2", "x2", -0.5))
	g.MustAddNode(ir.NewMulConst("t3", "1.2*x3", "x3", 1.2))

	g.MustAddNode(ir.NewBinary("s1", "t1+t2", ir.OpAdd, "t1", "t2"))
	g.MustAddNode(ir.NewBinary("s2", "s1+t3", ir.OpAdd, "s1", "t3"))
	g.MustAddNode(ir.NewConst("c0", "-0.3", -0.3))
	g.MustAddNode(ir.NewBinary("z", "z", ir.OpAdd, "s2", "c0"))

	g.MustAddNode(ir.NewPoly("y", "0.5+0.197z-0.004z^3", "z", []float64{
		0.5,    // c0
		0.197,  // c1
		0.0,    // c2
		-0.004, // c3
	}))

	g.MustSetOutput("y")

	result, err := EvalPlain(g, map[ir.NodeID]float64{
		"x1": 1.0,
		"x2": 2.0,
		"x3": 0.5,
	})
	if err != nil {
		t.Fatalf("EvalPlain failed: %v", err)
	}

	// z = 0.8*1 - 0.5*2 + 1.2*0.5 - 0.3
	//   = 0.8 - 1.0 + 0.6 - 0.3
	//   = 0.1
	wantZ := 0.1
	gotZ := result.Values["z"]
	if math.Abs(gotZ-wantZ) > 1e-12 {
		t.Fatalf("z mismatch: got %.12f, want %.12f", gotZ, wantZ)
	}

	// y = 0.5 + 0.197*0.1 - 0.004*(0.1^3)
	//   = 0.519696
	wantY := 0.519696
	if math.Abs(result.Output-wantY) > 1e-12 {
		t.Fatalf("y mismatch: got %.12f, want %.12f", result.Output, wantY)
	}
}
