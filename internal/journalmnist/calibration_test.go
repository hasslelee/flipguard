package journalmnist

import "testing"

func TestCalibrateMLPReturnsFinitePositiveSignal(t *testing.T) {
	model := NewMLPModel(7)
	artifact := ModelArtifact{
		SchemaVersion:  ModelArtifactSchemaV1,
		SourceCommit:   "commit",
		DatasetID:      "mnist_10class",
		ModelID:        MLPModelID,
		ModelType:      MLPModelType,
		GraphAdapterID: "adapter",
		GraphFormula:   "graph",
		Parameters:     model.Parameters,
	}
	rows := []PartitionRow{{SampleID: "one", Label: 0}}
	calibration, err := CalibrateModel(artifact, rows)
	if err != nil {
		t.Fatal(err)
	}
	if calibration.AggregateSensitivity <= 0 || calibration.MaxInputAbs != 1 {
		t.Fatalf("unexpected calibration: %+v", calibration)
	}
}

func TestCalibrateLeNetReturnsDeclaredStages(t *testing.T) {
	model := NewLeNetModel(9)
	artifact := ModelArtifact{
		SchemaVersion:  ModelArtifactSchemaV1,
		SourceCommit:   "commit",
		DatasetID:      "mnist_10class",
		ModelID:        LeNetModelID,
		ModelType:      LeNetModelType,
		GraphAdapterID: "adapter",
		GraphFormula:   "graph",
		Parameters:     model.Parameters,
	}
	calibration, err := CalibrateModel(artifact, []PartitionRow{{SampleID: "one", Label: 0}})
	if err != nil {
		t.Fatal(err)
	}
	if calibration.StageLInfNorm["conv_2"] <= 0 || calibration.PrimitiveTerms["output"] != 128 {
		t.Fatalf("unexpected LeNet calibration: %+v", calibration)
	}
}
