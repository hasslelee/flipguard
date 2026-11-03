package ckksbackend

import (
	"testing"

	"github.com/hasslelee/flipguard/internal/ir"
	"github.com/hasslelee/flipguard/internal/runtime"
)

func TestBuildUniformHighScalePlan(t *testing.T) {
	schedule := runtime.PrecisionSchedule{
		ir.NodeID("a"): runtime.PrecisionBits(4),
		ir.NodeID("b"): runtime.PrecisionBits(12),
	}

	cfg := UniformHighConfig()

	plan, err := BuildScalePlan(schedule, cfg)
	if err != nil {
		t.Fatalf("BuildScalePlan failed: %v", err)
	}

	if plan.Policy != ScalePolicyUniformHigh {
		t.Fatalf("unexpected policy: %s", plan.Policy)
	}

	for _, node := range plan.Nodes {
		if node.Class != ScaleClassHigh {
			t.Fatalf("expected high class, got %s", node.Class)
		}
		if node.LogScale != cfg.LogScaleHigh {
			t.Fatalf("expected high log scale %.2f, got %.2f", cfg.LogScaleHigh, node.LogScale)
		}
	}
}

func TestBuildUniformLowScalePlan(t *testing.T) {
	schedule := runtime.PrecisionSchedule{
		ir.NodeID("a"): runtime.PrecisionBits(4),
		ir.NodeID("b"): runtime.PrecisionBits(12),
	}

	cfg := UniformLowConfig()

	plan, err := BuildScalePlan(schedule, cfg)
	if err != nil {
		t.Fatalf("BuildScalePlan failed: %v", err)
	}

	for _, node := range plan.Nodes {
		if node.Class != ScaleClassLow {
			t.Fatalf("expected low class, got %s", node.Class)
		}
		if node.LogScale != cfg.LogScaleLow {
			t.Fatalf("expected low log scale %.2f, got %.2f", cfg.LogScaleLow, node.LogScale)
		}
	}
}

func TestBuildFlipGuardGroupedScalePlan(t *testing.T) {
	schedule := runtime.PrecisionSchedule{
		ir.NodeID("low"):  runtime.PrecisionBits(3),
		ir.NodeID("mid"):  runtime.PrecisionBits(9),
		ir.NodeID("high"): runtime.PrecisionBits(13),
	}

	cfg := FlipGuardGroupedConfig()

	plan, err := BuildScalePlan(schedule, cfg)
	if err != nil {
		t.Fatalf("BuildScalePlan failed: %v", err)
	}

	summary := plan.Summary()

	if summary.Nodes != 3 {
		t.Fatalf("expected 3 nodes, got %d", summary.Nodes)
	}
	if summary.High != 1 {
		t.Fatalf("expected 1 high node, got %d", summary.High)
	}
	if summary.Mid != 1 {
		t.Fatalf("expected 1 mid node, got %d", summary.Mid)
	}
	if summary.Low != 1 {
		t.Fatalf("expected 1 low node, got %d", summary.Low)
	}
}

func TestScalePlanNodeOrderIsStable(t *testing.T) {
	schedule := runtime.PrecisionSchedule{
		ir.NodeID("z"): runtime.PrecisionBits(3),
		ir.NodeID("a"): runtime.PrecisionBits(3),
		ir.NodeID("m"): runtime.PrecisionBits(3),
	}

	cfg := FlipGuardGroupedConfig()

	plan, err := BuildScalePlan(schedule, cfg)
	if err != nil {
		t.Fatalf("BuildScalePlan failed: %v", err)
	}

	got := []ir.NodeID{
		plan.Nodes[0].NodeID,
		plan.Nodes[1].NodeID,
		plan.Nodes[2].NodeID,
	}

	want := []ir.NodeID{
		ir.NodeID("a"),
		ir.NodeID("m"),
		ir.NodeID("z"),
	}

	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("unexpected node order at %d: got %s want %s", i, got[i], want[i])
		}
	}
}
