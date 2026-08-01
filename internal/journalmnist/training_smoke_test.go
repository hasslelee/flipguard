package journalmnist

import "testing"

func TestFixedTrainingProtocolsRemainFinite(t *testing.T) {
	dataset := Dataset{Samples: make([]Sample, 32)}
	training := make([]int, 24)
	validation := make([]int, 8)
	for index := range dataset.Samples {
		dataset.Samples[index].SourceIndex = index
		dataset.Samples[index].Label = index % ClassCount
		pixel := (index%ClassCount)*70 + index%7
		dataset.Samples[index].Pixels[pixel] = 255
		if index < len(training) {
			training[index] = index
		} else {
			validation[index-len(training)] = index
		}
	}
	mlp, err := TrainMLP(dataset, training, validation, 42, nil)
	if err != nil {
		t.Fatal(err)
	}
	if len(mlp.History) != 8 || mlp.Model.Validate() != nil {
		t.Fatal("MLP fixed training protocol did not complete")
	}
	lenet, err := TrainLeNet(dataset, training, validation, 42, nil)
	if err != nil {
		t.Fatal(err)
	}
	if len(lenet.History) != 8 || lenet.Model.Validate() != nil {
		t.Fatal("LeNet fixed training protocol did not complete")
	}
}
