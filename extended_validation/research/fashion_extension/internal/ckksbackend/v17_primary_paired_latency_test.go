package ckksbackend

import "testing"

func TestV17PrimaryPairedLatencyRejectsUnfrozenPopulation(t *testing.T) {
	_, err := RunV17PrimaryPairedLatencyKeyset(V17PrimaryPairedLatencyConfig{
		Kind:            V17PairedKindJournalMNIST,
		Keyset:          1,
		WarmupRuns:      1,
		MeasurementRuns: 6,
		MarginFloor:     0.001,
		UtilizationCap:  0.5,
		SelectedRowIDs:  []int{1},
		Arms:            []V17PrimaryPairedLatencyArm{{ID: "only-one"}},
	}, func(V17PrimaryPairedLatencyRecord) error { return nil })
	if err == nil {
		t.Fatal("expected exactly-two-arms validation error")
	}
}

func TestV17PrimaryPairedLatencyRejectsUnknownKindBeforeExecution(t *testing.T) {
	arms := []V17PrimaryPairedLatencyArm{
		{ID: "direct", Role: "DIRECT", CandidateID: "a"},
		{ID: "finite", Role: "FINITE", CandidateID: "b"},
	}
	_, err := RunV17PrimaryPairedLatencyKeyset(V17PrimaryPairedLatencyConfig{
		Kind:            "unknown",
		Keyset:          1,
		WarmupRuns:      1,
		MeasurementRuns: 6,
		MarginFloor:     0.001,
		UtilizationCap:  0.5,
		SelectedRowIDs:  []int{1},
		Arms:            arms,
	}, func(V17PrimaryPairedLatencyRecord) error { return nil })
	if err == nil {
		t.Fatal("expected unknown-kind error")
	}
}
