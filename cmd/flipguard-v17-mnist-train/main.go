package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"github.com/hasslelee/flipguard/internal/journalmnist"
)

const (
	artifactSchema = "flipguard_journal_multiclass_model_v1"
	adapterID      = "mnist_multiclass_feature_ciphertext_batch_adapter_v1"
)

type binding struct {
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
}

type artifact struct {
	SchemaVersion     string                       `json:"schema_version"`
	SourceCommit      string                       `json:"source_commit"`
	DatasetID         string                       `json:"dataset_id"`
	ModelID           string                       `json:"model_id"`
	ModelType         string                       `json:"model_type"`
	GraphAdapterID    string                       `json:"graph_adapter_id"`
	GraphFormula      string                       `json:"graph_formula"`
	Architecture      map[string]any               `json:"architecture"`
	Preprocessing     map[string]any               `json:"preprocessing"`
	Source            binding                      `json:"source"`
	SplitManifest     binding                      `json:"split_manifest"`
	Training          map[string]any               `json:"training"`
	PolicyBinding     map[string]any               `json:"policy_binding"`
	PlaintextAccuracy map[string]float64           `json:"plaintext_accuracy"`
	TrainingHistory   []journalmnist.TrainingEpoch `json:"training_history"`
	Parameters        []float64                    `json:"parameters"`
}

func main() {
	modelName := flag.String("model", "", "mlp100 or lenet5_small")
	seed := flag.Uint64("seed", 0, "predeclared training seed")
	source := flag.String("source", "results/source_datasets/mnist/mnist_784.arff.gz", "byte-pinned MNIST source")
	splitManifest := flag.String("split-manifest", "datasets/journal_multiclass_extension_v1/mnist/input_split_manifest.json", "frozen split manifest")
	sourceCommit := flag.String("source-commit", "", "source commit associated with the trainer")
	output := flag.String("output", "", "exclusive model artifact path")
	flag.Parse()
	if (*modelName != "mlp100" && *modelName != "lenet5_small") || *sourceCommit == "" || *output == "" {
		fatalf("--model mlp100|lenet5_small, --source-commit, and --output are required")
	}
	if _, err := os.Stat(*output); err == nil {
		fmt.Printf("training artifact already exists: %s\n", *output)
		return
	}
	dataset, err := journalmnist.LoadDataset(*source)
	if err != nil {
		fatalf("load MNIST: %v", err)
	}
	split, err := journalmnist.BuildSplit(dataset)
	if err != nil {
		fatalf("build split: %v", err)
	}
	allTest := make([]int, journalmnist.OfficialTestRows)
	for index := range allTest {
		allTest[index] = journalmnist.OfficialTrainRows + index
	}
	common := artifact{
		SchemaVersion: artifactSchema, SourceCommit: *sourceCommit, DatasetID: "mnist_10class", GraphAdapterID: adapterID,
		Preprocessing: map[string]any{"pixel_normalization": "pixel/255", "test_selection": journalmnist.SplitPolicyID, "validation_audit_overlap": 0},
		Source:        binding{Path: *source, SHA256: "sha256:" + dataset.SourceSHA256},
		SplitManifest: binding{Path: *splitManifest, SHA256: digest(*splitManifest)},
		PolicyBinding: map[string]any{
			"security_policy_id":     "security_guidelines_cic2025_table5_2_ternary_128_v2",
			"security_policy_digest": "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055",
			"direct_policy_id":       "flipguard_direct_synthesis_policy_v2",
			"direct_policy_digest":   "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603",
			"policy_retuning":        0,
		},
	}
	if *modelName == "mlp100" {
		result, trainErr := journalmnist.TrainMLP(dataset, split.ModelTraining, split.ModelValidation, *seed, progress(*modelName, *seed))
		if trainErr != nil {
			fatalf("train MLP-100: %v", trainErr)
		}
		common.ModelID, common.ModelType = journalmnist.MLPModelID, journalmnist.MLPModelType
		common.GraphFormula = "affine_100(square(affine_784(input)))->10_logits"
		common.Architecture = map[string]any{"input_dim": 784, "hidden_units": 100, "activation": "square", "output_logits": 10}
		common.Training = training(*seed, 0.001)
		common.TrainingHistory, common.Parameters = result.History, result.Model.Parameters
		common.PlaintextAccuracy = map[string]float64{"model_validation_5000": result.History[len(result.History)-1].ValidationAccuracy, "official_test_10000": journalmnist.MLPAccuracy(result.Model, dataset, allTest)}
	} else {
		result, trainErr := journalmnist.TrainLeNet(dataset, split.ModelTraining, split.ModelValidation, *seed, progress(*modelName, *seed))
		if trainErr != nil {
			fatalf("train LeNet: %v", trainErr)
		}
		common.ModelID, common.ModelType = journalmnist.LeNetModelID, journalmnist.LeNetModelType
		common.GraphFormula = "conv5x5_6->square->avgpool2->conv5x5_16->square->avgpool2->fc120->square->fc64->square->10_logits"
		common.Architecture = map[string]any{
			"source_input_shape": []int{1, 28, 28}, "zero_padded_shape": []int{1, 32, 32},
			"conv1":           map[string]any{"channels": 6, "kernel": []int{5, 5}, "output": []int{6, 28, 28}},
			"pool1":           map[string]any{"type": "average", "kernel": []int{2, 2}, "stride": 2},
			"conv2":           map[string]any{"channels": 16, "kernel": []int{5, 5}, "output": []int{16, 10, 10}},
			"pool2":           map[string]any{"type": "average", "kernel": []int{2, 2}, "stride": 2},
			"fully_connected": []int{400, 120, 64, 10}, "activation": "square_after_conv_and_hidden_affine", "output_logits": 10,
		}
		common.Training = training(*seed, 0.0005)
		common.TrainingHistory, common.Parameters = result.History, result.Model.Parameters
		common.PlaintextAccuracy = map[string]float64{"model_validation_5000": result.History[len(result.History)-1].ValidationAccuracy, "official_test_10000": journalmnist.LeNetAccuracy(result.Model, dataset, allTest)}
	}
	if err := os.MkdirAll(filepath.Dir(*output), 0o755); err != nil {
		fatalf("create output: %v", err)
	}
	encoded, err := json.MarshalIndent(common, "", "  ")
	if err != nil {
		fatalf("marshal: %v", err)
	}
	encoded = append(encoded, '\n')
	if err := os.WriteFile(*output+".tmp", encoded, 0o644); err != nil {
		fatalf("write temp: %v", err)
	}
	if err := os.Rename(*output+".tmp", *output); err != nil {
		fatalf("publish: %v", err)
	}
	fmt.Printf("model=%s seed=%d test_accuracy=%.6f output=%s\n", *modelName, *seed, common.PlaintextAccuracy["official_test_10000"], *output)
}

func training(seed uint64, rate float64) map[string]any {
	return map[string]any{"optimizer": "deterministic_adam_v1", "training_seed": seed, "epochs": 8, "batch_size": 64, "initial_learning_rate": rate, "epoch_decay": 0.9, "beta1": 0.9, "beta2": 0.999, "epsilon": 1e-8, "l2": 1e-5, "gradient_global_norm_cap": 5.0, "early_stopping": false, "test_used_for_model_selection": false}
}

func progress(model string, seed uint64) func(journalmnist.TrainingEpoch) {
	return func(epoch journalmnist.TrainingEpoch) {
		fmt.Printf("model=%s seed=%d epoch=%d loss=%.6f train_accuracy=%.6f validation_accuracy=%.6f\n", model, seed, epoch.Epoch, epoch.MeanTrainingLoss, epoch.TrainingAccuracy, epoch.ValidationAccuracy)
	}
}

func digest(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		fatalf("read binding %s: %v", path, err)
	}
	sum := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(sum[:])
}

func fatalf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "flipguard-v17-mnist-train: "+format+"\n", args...)
	os.Exit(1)
}
