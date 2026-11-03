package benchmarks

import (
	"math"
	"testing"

	"github.com/hasslelee/flipguard/internal/ir"
	"github.com/hasslelee/flipguard/internal/runtime"
)

func TestSobelEdgeRescaleGraphMatchesPlainScore(t *testing.T) {
	graph := NewSobelEdgeRescaleGraph()
	if err := graph.Validate(); err != nil {
		t.Fatalf("Validate failed: %v", err)
	}
	for index, sample := range DefaultSobelEdgeSamples() {
		got, err := runtime.EvalPlain(graph, sample.Inputs())
		if err != nil {
			t.Fatalf("EvalPlain sample %d failed: %v", index, err)
		}
		if want := SobelEdgeScore(sample); math.Abs(got.Output-want) > 1e-12 {
			t.Fatalf(
				"sample %d output mismatch: got %.12f want %.12f",
				index,
				got.Output,
				want,
			)
		}
	}

	for _, id := range []ir.NodeID{"gx2", "gy2"} {
		node, ok := graph.Node(id)
		if !ok {
			t.Fatalf("missing node %s", id)
		}
		if node.Op != ir.OpPow2 {
			t.Fatalf("node %s op=%s, want pow2", id, node.Op)
		}
	}
}
