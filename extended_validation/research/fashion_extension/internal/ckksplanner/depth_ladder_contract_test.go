package ckksplanner

import (
	"fmt"
	"path/filepath"
	"runtime"
	"testing"
)

func TestV17DepthLadderContractTracksDeclaredDepth(t *testing.T) {
	_, filename, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("resolve test source path")
	}
	root := filepath.Clean(filepath.Join(filepath.Dir(filename), "..", ".."))
	previousQPrimes := 0
	for _, depth := range []int{1, 2, 4, 6, 8} {
		directory := filepath.Join(root, "results", "model_family_expansion_v17", "depth_ladder", "inputs", fmt.Sprintf("D%d", depth))
		contract, err := BuildV17DepthLadderContract(V17DepthLadderOptions{
			ModelPath: filepath.Join(directory, "model.json"),
			DataPath:  filepath.Join(directory, "configuration_selection.csv"),
			SplitID:   fmt.Sprintf("v17_depth_ladder_D%d", depth),
			Depth:     depth,
		})
		if err != nil {
			t.Fatalf("build depth %d contract: %v", depth, err)
		}
		if contract.Graph.MultiplicativeDepth != depth {
			t.Fatalf("depth %d graph reported %d", depth, contract.Graph.MultiplicativeDepth)
		}
		if contract.Deployment.RescaleLevelsConsumed != depth {
			t.Fatalf("depth %d consumed %d levels", depth, contract.Deployment.RescaleLevelsConsumed)
		}
		if contract.Deployment.RequiredQPrimes <= previousQPrimes {
			t.Fatalf("depth %d q-prime demand %d did not exceed %d", depth, contract.Deployment.RequiredQPrimes, previousQPrimes)
		}
		previousQPrimes = contract.Deployment.RequiredQPrimes
	}
}
