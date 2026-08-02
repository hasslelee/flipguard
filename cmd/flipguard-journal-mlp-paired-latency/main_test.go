package main

import "testing"

func validTestProtocol() executionProtocol {
	rows := make([]subsetRow, 0, 100)
	for label := 0; label < 10; label++ {
		for index := 0; index < 10; index++ {
			rows = append(rows, subsetRow{
				Rank: index + 1, RowID: label*10 + index,
				SampleID: "sample", SourceIndex: 60000 + label*10 + index,
				Label: label,
			})
		}
	}
	return executionProtocol{
		SchemaVersion: protocolSchema, ProtocolID: "test",
		ExecutionSourceCommit: "0123456789012345678901234567890123456789",
		SelectedRows:          rows, FreshKeysets: 3, WarmupRuns: 1,
		MeasurementRuns: 6, ConcurrentCKKSProcesses: 0,
		Arms: []protocolArm{{ID: "a"}, {ID: "b"}, {ID: "c"}},
	}
}

func TestValidateProtocolAcceptsFrozenPopulation(t *testing.T) {
	if err := validateProtocol(validTestProtocol(), 3); err != nil {
		t.Fatal(err)
	}
}

func TestValidateProtocolRejectsPopulationAndRepetitionDrift(t *testing.T) {
	protocol := validTestProtocol()
	protocol.SelectedRows = protocol.SelectedRows[:99]
	if err := validateProtocol(protocol, 1); err == nil {
		t.Fatal("expected selected population rejection")
	}
	protocol = validTestProtocol()
	protocol.MeasurementRuns = 5
	if err := validateProtocol(protocol, 1); err == nil {
		t.Fatal("expected repetition policy rejection")
	}
	protocol = validTestProtocol()
	protocol.SelectedRows[1].RowID = protocol.SelectedRows[0].RowID
	if err := validateProtocol(protocol, 1); err == nil {
		t.Fatal("expected duplicate row rejection")
	}
}
