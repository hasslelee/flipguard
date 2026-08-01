package journalmnist

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadPartitionCSVRejectsWrongRole(t *testing.T) {
	path := filepath.Join(t.TempDir(), "partition.csv")
	file, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	defer file.Close()
	// A header-only file must fail closed before role interpretation.
	if _, err := file.WriteString("row_id,sample_id,source_index,source_partition,role,label\n"); err != nil {
		t.Fatal(err)
	}
	if _, err := LoadPartitionCSV(path, "locked_audit"); err == nil {
		t.Fatal("expected incomplete partition to be rejected")
	}
}

func TestModelArtifactRejectsUnknownModelType(t *testing.T) {
	artifact := ModelArtifact{
		SchemaVersion:  ModelArtifactSchemaV1,
		SourceCommit:   "commit",
		DatasetID:      "mnist_10class",
		ModelID:        "unknown",
		ModelType:      "unknown",
		GraphAdapterID: "adapter",
		GraphFormula:   "graph",
	}
	if err := artifact.Validate(); err == nil {
		t.Fatal("expected unknown model type to be rejected")
	}
}
