package modelregistry

import "testing"

func TestTabularRegistrySeparatesBodyAndHead(t *testing.T) {
	families := TabularFamilies()
	if len(families) != 5 {
		t.Fatalf("families=%d", len(families))
	}
	deep, err := LookupTabular("mlp_square2_linear_score")
	if err != nil {
		t.Fatal(err)
	}
	if deep.Body != BodyTwoHiddenSquares || deep.Head != HeadAffine || deep.HiddenLayers != 2 {
		t.Fatalf("unexpected deep family: %+v", deep)
	}
	if _, err := LookupTabular("dataset_specific_model"); err == nil {
		t.Fatal("unknown model type was accepted")
	}
}
