package ckksplanner

import (
	"github.com/hasslelee/flipguard/internal/journalmnist"
	"testing"
)

func TestFashionIdentityKeepsGraphAndDatasetDistinct(t *testing.T) {
	m := journalmnist.ModelArtifact{DatasetID: "fashion_mnist_10class", ModelID: "fashion_mnist_mlp_square_784_100_10_v1", ModelType: journalmnist.MLPModelType, GraphAdapterID: JournalMNISTGraphAdapterV1, GraphFormula: "affine_100(square(affine_784(input)))->10_logits"}
	if e := validateJournalModelIdentity(m); e != nil {
		t.Fatal(e)
	}
	m.GraphFormula = "relu MLP"
	if validateJournalModelIdentity(m) == nil {
		t.Fatal("changed graph accepted")
	}
	m.GraphFormula = "affine_100(square(affine_784(input)))->10_logits"
	m.ModelID = journalmnist.MLPModelID
	if validateJournalModelIdentity(m) == nil {
		t.Fatal("misnamed Fashion model accepted")
	}
}
