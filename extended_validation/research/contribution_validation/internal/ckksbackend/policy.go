package ckksbackend

import (
	"fmt"
	"sort"

	"github.com/hasslelee/flipguard/internal/ir"
	"github.com/hasslelee/flipguard/internal/runtime"
)

// ScaleClass is a coarse precision class for CKKS execution.
type ScaleClass string

const (
	ScaleClassHigh ScaleClass = "high"
	ScaleClassMid  ScaleClass = "mid"
	ScaleClassLow  ScaleClass = "low"
)

// NodeScale describes the planned CKKS scale class for one graph node.
type NodeScale struct {
	NodeID ir.NodeID

	Bits runtime.PrecisionBits

	Class ScaleClass

	LogScale float64
}

// ScalePlan describes the CKKS scale plan derived from a schedule.
type ScalePlan struct {
	Policy ScalePolicyKind

	Nodes []NodeScale
}

// BuildScalePlan maps a simulation-level precision schedule into a CKKS scale
// plan according to the selected policy.
func BuildScalePlan(schedule runtime.PrecisionSchedule, cfg Config) (ScalePlan, error) {
	if err := cfg.Validate(); err != nil {
		return ScalePlan{}, err
	}

	switch cfg.Policy {
	case ScalePolicyUniformHigh:
		return buildUniformScalePlan(schedule, cfg, ScaleClassHigh, cfg.LogScaleHigh), nil
	case ScalePolicyUniformLow:
		return buildUniformScalePlan(schedule, cfg, ScaleClassLow, cfg.LogScaleLow), nil
	case ScalePolicyFlipGuardGrouped:
		return buildGroupedScalePlan(schedule, cfg), nil
	default:
		return ScalePlan{}, fmt.Errorf("unsupported scale policy: %s", cfg.Policy)
	}
}

// Summary returns compact aggregate counts for a scale plan.
func (p ScalePlan) Summary() ScalePlanSummary {
	s := ScalePlanSummary{
		Policy: p.Policy,
		Nodes:  len(p.Nodes),
	}

	for _, node := range p.Nodes {
		switch node.Class {
		case ScaleClassHigh:
			s.High++
		case ScaleClassMid:
			s.Mid++
		case ScaleClassLow:
			s.Low++
		}
	}

	return s
}

// ScalePlanSummary summarizes a scale plan.
type ScalePlanSummary struct {
	Policy ScalePolicyKind

	Nodes int
	High  int
	Mid   int
	Low   int
}

func buildUniformScalePlan(
	schedule runtime.PrecisionSchedule,
	cfg Config,
	class ScaleClass,
	logScale float64,
) ScalePlan {
	nodes := make([]NodeScale, 0, len(schedule))

	for _, nodeID := range sortedNodeIDs(schedule) {
		nodes = append(nodes, NodeScale{
			NodeID:   nodeID,
			Bits:     schedule[nodeID],
			Class:    class,
			LogScale: logScale,
		})
	}

	return ScalePlan{
		Policy: cfg.Policy,
		Nodes:  nodes,
	}
}

func buildGroupedScalePlan(schedule runtime.PrecisionSchedule, cfg Config) ScalePlan {
	nodes := make([]NodeScale, 0, len(schedule))

	for _, nodeID := range sortedNodeIDs(schedule) {
		bits := schedule[nodeID]
		class, logScale := classifyBits(bits, cfg)

		nodes = append(nodes, NodeScale{
			NodeID:   nodeID,
			Bits:     bits,
			Class:    class,
			LogScale: logScale,
		})
	}

	return ScalePlan{
		Policy: cfg.Policy,
		Nodes:  nodes,
	}
}

func classifyBits(bits runtime.PrecisionBits, cfg Config) (ScaleClass, float64) {
	b := int(bits)

	if b >= cfg.HighBitThreshold {
		return ScaleClassHigh, cfg.LogScaleHigh
	}

	if b >= cfg.MidBitThreshold {
		return ScaleClassMid, cfg.LogScaleMid
	}

	return ScaleClassLow, cfg.LogScaleLow
}

func sortedNodeIDs(schedule runtime.PrecisionSchedule) []ir.NodeID {
	ids := make([]ir.NodeID, 0, len(schedule))
	for nodeID := range schedule {
		ids = append(ids, nodeID)
	}

	sort.Slice(ids, func(i, j int) bool {
		return ids[i] < ids[j]
	})

	return ids
}
