package benchmarks

import (
	"fmt"

	"github.com/hasslelee/flipguard/internal/ir"
)

// NewHarrisCornerRescaleGraph expresses the Harris response using only the
// rescale-aware square primitive. Products use
//
//	2ab = (a+b)^2 - a^2 - b^2
//
// so the planner trace and the Lattigo adapter share the same two
// multiplication layers without adding a new policy primitive.
func NewHarrisCornerRescaleGraph() *ir.Graph {
	g := ir.NewGraph()
	for row := 0; row < 5; row++ {
		for column := 0; column < 5; column++ {
			id := ir.NodeID(fmt.Sprintf("p%d%d", row, column))
			g.MustAddNode(ir.NewInput(id, string(id)))
		}
	}

	sxxTerms := make([]ir.NodeID, 0, 9)
	syyTerms := make([]ir.NodeID, 0, 9)
	twoSxyTerms := make([]ir.NodeID, 0, 9)
	for row := 1; row <= 3; row++ {
		for column := 1; column <= 3; column++ {
			prefix := fmt.Sprintf("g%d%d", row, column)
			gx := addHarrisSobelGX(g, prefix, row, column)
			gy := addHarrisSobelGY(g, prefix, row, column)
			gx2 := ir.NodeID(prefix + "_gx2")
			gy2 := ir.NodeID(prefix + "_gy2")
			gxPlusGy := ir.NodeID(prefix + "_gx_plus_gy")
			gxPlusGy2 := ir.NodeID(prefix + "_gx_plus_gy2")
			withoutGX2 := ir.NodeID(prefix + "_two_gxy_without_gx2")
			twoGXY := ir.NodeID(prefix + "_two_gxy")

			g.MustAddNode(ir.NewUnary(gx2, "Ix^2", ir.OpPow2, gx))
			g.MustAddNode(ir.NewUnary(gy2, "Iy^2", ir.OpPow2, gy))
			g.MustAddNode(ir.NewBinary(
				gxPlusGy,
				"Ix+Iy",
				ir.OpAdd,
				gx,
				gy,
			))
			g.MustAddNode(ir.NewUnary(
				gxPlusGy2,
				"(Ix+Iy)^2",
				ir.OpPow2,
				gxPlusGy,
			))
			g.MustAddNode(ir.NewBinary(
				withoutGX2,
				"(Ix+Iy)^2-Ix^2",
				ir.OpSub,
				gxPlusGy2,
				gx2,
			))
			g.MustAddNode(ir.NewBinary(
				twoGXY,
				"2*Ix*Iy",
				ir.OpSub,
				withoutGX2,
				gy2,
			))
			sxxTerms = append(sxxTerms, gx2)
			syyTerms = append(syyTerms, gy2)
			twoSxyTerms = append(twoSxyTerms, twoGXY)
		}
	}

	sxx := addHarrisTermChain(g, "sxx", sxxTerms)
	syy := addHarrisTermChain(g, "syy", syyTerms)
	twoSxy := addHarrisTermChain(g, "two_sxy", twoSxyTerms)
	trace := ir.NodeID("trace")
	g.MustAddNode(ir.NewBinary(
		trace,
		"Sxx+Syy",
		ir.OpAdd,
		sxx,
		syy,
	))

	sxx2 := ir.NodeID("sxx2")
	syy2 := ir.NodeID("syy2")
	twoSxy2 := ir.NodeID("two_sxy2")
	trace2 := ir.NodeID("trace2")
	g.MustAddNode(ir.NewUnary(sxx2, "Sxx^2", ir.OpPow2, sxx))
	g.MustAddNode(ir.NewUnary(syy2, "Syy^2", ir.OpPow2, syy))
	g.MustAddNode(ir.NewUnary(
		twoSxy2,
		"(2*Sxy)^2",
		ir.OpPow2,
		twoSxy,
	))
	g.MustAddNode(ir.NewUnary(
		trace2,
		"(Sxx+Syy)^2",
		ir.OpPow2,
		trace,
	))

	twoProductWithoutSxx2 := ir.NodeID("two_product_without_sxx2")
	twoSxxSyy := ir.NodeID("two_sxx_syy")
	g.MustAddNode(ir.NewBinary(
		twoProductWithoutSxx2,
		"(Sxx+Syy)^2-Sxx^2",
		ir.OpSub,
		trace2,
		sxx2,
	))
	g.MustAddNode(ir.NewBinary(
		twoSxxSyy,
		"2*Sxx*Syy",
		ir.OpSub,
		twoProductWithoutSxx2,
		syy2,
	))

	positiveDet := ir.NodeID("positive_det")
	negativeSxy2 := ir.NodeID("negative_sxy2")
	determinant := ir.NodeID("determinant")
	negativeKTrace2 := ir.NodeID("negative_k_trace2")
	score := ir.NodeID("score")
	g.MustAddNode(ir.NewMulConst(
		positiveDet,
		"Sxx*Syy",
		twoSxxSyy,
		0.5,
	))
	g.MustAddNode(ir.NewMulConst(
		negativeSxy2,
		"-Sxy^2",
		twoSxy2,
		-0.25,
	))
	g.MustAddNode(ir.NewBinary(
		determinant,
		"Sxx*Syy-Sxy^2",
		ir.OpAdd,
		positiveDet,
		negativeSxy2,
	))
	g.MustAddNode(ir.NewMulConst(
		negativeKTrace2,
		"-k*trace^2",
		trace2,
		-HarrisCornerK,
	))
	g.MustAddNode(ir.NewBinary(
		score,
		"Harris response",
		ir.OpAdd,
		determinant,
		negativeKTrace2,
	))
	g.MustSetOutput(score)
	return g
}
