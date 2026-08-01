package journalmnist

import (
	"os"
	"path/filepath"
	"testing"
)

func TestStableRankIsRoleAndLabelBound(t *testing.T) {
	a := StableRank(60000, 0, "encrypted")
	b := StableRank(60000, 1, "encrypted")
	c := StableRank(60000, 0, "model")
	if a == b || a == c {
		t.Fatal("stable rank must bind role and label")
	}
	if a != StableRank(60000, 0, "encrypted") {
		t.Fatal("stable rank is not deterministic")
	}
}

func TestValidateSplitRejectsOverlap(t *testing.T) {
	dataset := Dataset{Samples: make([]Sample, OfficialTrainRows+OfficialTestRows)}
	for index := range dataset.Samples {
		dataset.Samples[index].SourceIndex = index
		dataset.Samples[index].Label = index % ClassCount
	}
	split := Split{
		ModelTraining:           make([]int, OfficialTrainRows-ClassCount*ModelValidationPerClass),
		ModelValidation:         make([]int, ClassCount*ModelValidationPerClass),
		ConfigurationValidation: make([]int, ClassCount*ConfigValidationPerClass),
		LockedAudit:             make([]int, ClassCount*LockedAuditPerClass),
	}
	// Zero-filled roles necessarily overlap and must fail closed.
	if err := ValidateSplit(dataset, split); err == nil {
		t.Fatal("expected overlapping split rejection")
	}
}

func TestFrozenMNISTSourceBuildsDeclaredSplit(t *testing.T) {
	path := filepath.Join(
		"..",
		"..",
		"results",
		"source_datasets",
		"mnist",
		"mnist_784.arff.gz",
	)
	if _, err := os.Stat(path); err != nil {
		t.Skip("byte-pinned MNIST source is fetched separately")
	}
	dataset, err := LoadDataset(path)
	if err != nil {
		t.Fatal(err)
	}
	split, err := BuildSplit(dataset)
	if err != nil {
		t.Fatal(err)
	}
	if len(split.ModelTraining) != 55000 ||
		len(split.ModelValidation) != 5000 ||
		len(split.ConfigurationValidation) != 500 ||
		len(split.LockedAudit) != 500 {
		t.Fatalf("unexpected frozen split sizes: %+v", split)
	}
}
