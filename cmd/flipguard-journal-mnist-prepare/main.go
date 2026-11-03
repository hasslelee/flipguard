package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strconv"

	"github.com/hasslelee/flipguard/internal/journalmnist"
)

const (
	artifactSchema = "flipguard_journal_multiclass_model_v1"
	adapterID      = "mnist_multiclass_feature_ciphertext_batch_adapter_v1"
	securityPolicy = "security_guidelines_cic2025_table5_2_ternary_128_v2"
	securityDigest = "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
	directPolicy   = "flipguard_direct_synthesis_policy_v2"
	directDigest   = "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
	trainingSeed   = uint64(0x4a4f55524e414c31)
)

type artifactBinding struct {
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
}

type splitManifest struct {
	SchemaVersion string                     `json:"schema_version"`
	PolicyID      string                     `json:"policy_id"`
	SourceCommit  string                     `json:"source_commit"`
	Source        artifactBinding            `json:"source"`
	OfficialRows  map[string]int             `json:"official_rows"`
	Selection     map[string]any             `json:"selection"`
	Partitions    map[string]artifactBinding `json:"partitions"`
	OverlapCount  int                        `json:"validation_audit_overlap_count"`
	ClassCounts   map[string][]int           `json:"class_counts"`
}

type modelArtifact struct {
	SchemaVersion     string                       `json:"schema_version"`
	SourceCommit      string                       `json:"source_commit"`
	DatasetID         string                       `json:"dataset_id"`
	ModelID           string                       `json:"model_id"`
	ModelType         string                       `json:"model_type"`
	GraphAdapterID    string                       `json:"graph_adapter_id"`
	GraphFormula      string                       `json:"graph_formula"`
	Architecture      map[string]any               `json:"architecture"`
	Preprocessing     map[string]any               `json:"preprocessing"`
	Source            artifactBinding              `json:"source"`
	SplitManifest     artifactBinding              `json:"split_manifest"`
	Training          map[string]any               `json:"training"`
	PolicyBinding     map[string]any               `json:"policy_binding"`
	PlaintextAccuracy map[string]float64           `json:"plaintext_accuracy"`
	TrainingHistory   []journalmnist.TrainingEpoch `json:"training_history"`
	Parameters        []float64                    `json:"parameters"`
}

func main() {
	source := flag.String(
		"source",
		"results/source_datasets/mnist/mnist_784.arff.gz",
		"byte-pinned OpenML MNIST ARFF gzip",
	)
	output := flag.String(
		"output",
		"datasets/journal_multiclass_extension_v1/mnist",
		"output root",
	)
	modelChoice := flag.String("model", "all", "mlp, lenet, or all")
	sourceCommit := flag.String("source-commit", "", "committed trainer source")
	force := flag.Bool("force", false, "replace non-frozen generated extension files")
	flag.Parse()

	if *sourceCommit == "" || len(*sourceCommit) != 40 {
		fatalf("--source-commit must be a full 40-character Git commit")
	}
	if *modelChoice != "mlp" && *modelChoice != "lenet" && *modelChoice != "all" {
		fatalf("--model must be mlp, lenet, or all")
	}
	dataset, err := journalmnist.LoadDataset(*source)
	if err != nil {
		fatalf("load MNIST: %v", err)
	}
	split, err := journalmnist.BuildSplit(dataset)
	if err != nil {
		fatalf("build MNIST split: %v", err)
	}
	if err := os.MkdirAll(*output, 0o755); err != nil {
		fatalf("create output root: %v", err)
	}
	manifestBinding, err := writeSplitArtifacts(
		*output,
		*source,
		dataset,
		split,
		*sourceCommit,
		*force,
	)
	if err != nil {
		fatalf("write split artifacts: %v", err)
	}
	allTest := make([]int, journalmnist.OfficialTestRows)
	for index := range allTest {
		allTest[index] = journalmnist.OfficialTrainRows + index
	}
	if *modelChoice == "mlp" || *modelChoice == "all" {
		result, trainErr := journalmnist.TrainMLP(
			dataset,
			split.ModelTraining,
			split.ModelValidation,
			trainingSeed,
			printEpoch("MLP-100"),
		)
		if trainErr != nil {
			fatalf("train MLP: %v", trainErr)
		}
		artifact := modelArtifact{
			SchemaVersion:  artifactSchema,
			SourceCommit:   *sourceCommit,
			DatasetID:      "mnist_10class",
			ModelID:        journalmnist.MLPModelID,
			ModelType:      "mlp_square_multiclass",
			GraphAdapterID: adapterID,
			GraphFormula:   "affine_100(square(affine_784(input)))->10_logits",
			Architecture: map[string]any{
				"input_dim":     784,
				"hidden_units":  100,
				"activation":    "square",
				"output_logits": 10,
			},
			Preprocessing: preprocessing(),
			Source:        artifactBinding{Path: *source, SHA256: "sha256:" + dataset.SourceSHA256},
			SplitManifest: manifestBinding,
			Training:      trainingProtocol(0.001),
			PolicyBinding: policyBinding(),
			PlaintextAccuracy: map[string]float64{
				"model_validation_5000": result.History[len(result.History)-1].ValidationAccuracy,
				"official_test_10000":   journalmnist.MLPAccuracy(result.Model, dataset, allTest),
			},
			TrainingHistory: result.History,
			Parameters:      result.Model.Parameters,
		}
		if err := writeJSONExclusive(
			filepath.Join(*output, "mnist_mlp_square_784_100_10_v1.json"),
			artifact,
			*force,
		); err != nil {
			fatalf("write MLP artifact: %v", err)
		}
		fmt.Printf("mlp_plaintext_test_accuracy=%.6f\n", artifact.PlaintextAccuracy["official_test_10000"])
	}
	if *modelChoice == "lenet" || *modelChoice == "all" {
		result, trainErr := journalmnist.TrainLeNet(
			dataset,
			split.ModelTraining,
			split.ModelValidation,
			trainingSeed^0x4c454e4554,
			printEpoch("LeNet-5-small"),
		)
		if trainErr != nil {
			fatalf("train LeNet: %v", trainErr)
		}
		artifact := modelArtifact{
			SchemaVersion:  artifactSchema,
			SourceCommit:   *sourceCommit,
			DatasetID:      "mnist_10class",
			ModelID:        journalmnist.LeNetModelID,
			ModelType:      "lenet5_small_square_multiclass",
			GraphAdapterID: adapterID,
			GraphFormula:   "conv5x5_6->square->avgpool2->conv5x5_16->square->avgpool2->fc120->square->fc64->square->10_logits",
			Architecture: map[string]any{
				"source_input_shape": []int{1, 28, 28},
				"zero_padded_shape":  []int{1, 32, 32},
				"conv1":              map[string]any{"channels": 6, "kernel": []int{5, 5}, "output": []int{6, 28, 28}},
				"pool1":              map[string]any{"type": "average", "kernel": []int{2, 2}, "stride": 2},
				"conv2":              map[string]any{"channels": 16, "kernel": []int{5, 5}, "output": []int{16, 10, 10}},
				"pool2":              map[string]any{"type": "average", "kernel": []int{2, 2}, "stride": 2},
				"fully_connected":    []int{400, 120, 64, 10},
				"activation":         "square_after_conv_and_hidden_affine",
				"output_logits":      10,
			},
			Preprocessing: preprocessing(),
			Source:        artifactBinding{Path: *source, SHA256: "sha256:" + dataset.SourceSHA256},
			SplitManifest: manifestBinding,
			Training:      trainingProtocol(0.0005),
			PolicyBinding: policyBinding(),
			PlaintextAccuracy: map[string]float64{
				"model_validation_5000": result.History[len(result.History)-1].ValidationAccuracy,
				"official_test_10000":   journalmnist.LeNetAccuracy(result.Model, dataset, allTest),
			},
			TrainingHistory: result.History,
			Parameters:      result.Model.Parameters,
		}
		if err := writeJSONExclusive(
			filepath.Join(*output, "mnist_lenet5_small_square_v1.json"),
			artifact,
			*force,
		); err != nil {
			fatalf("write LeNet artifact: %v", err)
		}
		fmt.Printf("lenet_plaintext_test_accuracy=%.6f\n", artifact.PlaintextAccuracy["official_test_10000"])
	}
}

func printEpoch(model string) func(journalmnist.TrainingEpoch) {
	return func(epoch journalmnist.TrainingEpoch) {
		fmt.Printf(
			"%s epoch=%d loss=%.6f train_accuracy=%.6f validation_accuracy=%.6f duration_seconds=%.2f\n",
			model,
			epoch.Epoch,
			epoch.MeanTrainingLoss,
			epoch.TrainingAccuracy,
			epoch.ValidationAccuracy,
			epoch.DurationSeconds,
		)
	}
}

func preprocessing() map[string]any {
	return map[string]any{
		"pixel_normalization":      "pixel/255",
		"test_selection":           journalmnist.SplitPolicyID,
		"validation_audit_overlap": 0,
	}
}

func trainingProtocol(learningRate float64) map[string]any {
	return map[string]any{
		"optimizer":                     "deterministic_adam_v1",
		"training_seed":                 trainingSeed,
		"epochs":                        8,
		"batch_size":                    64,
		"initial_learning_rate":         learningRate,
		"epoch_decay":                   0.9,
		"beta1":                         0.9,
		"beta2":                         0.999,
		"epsilon":                       1e-8,
		"l2":                            1e-5,
		"gradient_global_norm_cap":      5.0,
		"early_stopping":                false,
		"test_used_for_model_selection": false,
	}
}

func policyBinding() map[string]any {
	return map[string]any{
		"security_policy_id":     securityPolicy,
		"security_policy_digest": securityDigest,
		"direct_policy_id":       directPolicy,
		"direct_policy_digest":   directDigest,
		"relationship":           "frozen_constants_reused;model_and_packing_extension_not_added_to_direct_policy_v2_supported_models",
		"packing_adapter":        "feature_ciphertext_sample_slots_v1",
		"policy_retuning":        0,
	}
}

func writeSplitArtifacts(
	root string,
	sourcePath string,
	dataset journalmnist.Dataset,
	split journalmnist.Split,
	sourceCommit string,
	force bool,
) (artifactBinding, error) {
	partitions := []struct {
		name          string
		indices       []int
		includePixels bool
	}{
		{"model_training", split.ModelTraining, false},
		{"model_validation", split.ModelValidation, false},
		{"configuration_validation", split.ConfigurationValidation, true},
		{"locked_audit", split.LockedAudit, true},
	}
	bindings := make(map[string]artifactBinding)
	classCounts := make(map[string][]int)
	for _, partition := range partitions {
		path := filepath.Join(root, partition.name+".csv")
		if err := writePartitionCSV(path, dataset, partition.indices, partition.name, partition.includePixels, force); err != nil {
			return artifactBinding{}, err
		}
		digest, err := digestFile(path)
		if err != nil {
			return artifactBinding{}, err
		}
		bindings[partition.name] = artifactBinding{Path: path, SHA256: "sha256:" + digest}
		counts := make([]int, journalmnist.ClassCount)
		for _, index := range partition.indices {
			counts[dataset.Samples[index].Label]++
		}
		classCounts[partition.name] = counts
	}
	manifest := splitManifest{
		SchemaVersion: journalmnist.DatasetSchemaVersion,
		PolicyID:      journalmnist.SplitPolicyID,
		SourceCommit:  sourceCommit,
		Source:        artifactBinding{Path: sourcePath, SHA256: "sha256:" + dataset.SourceSHA256},
		OfficialRows:  map[string]int{"train": journalmnist.OfficialTrainRows, "test": journalmnist.OfficialTestRows},
		Selection: map[string]any{
			"model_validation_per_class":         journalmnist.ModelValidationPerClass,
			"configuration_validation_per_class": journalmnist.ConfigValidationPerClass,
			"locked_audit_per_class":             journalmnist.LockedAuditPerClass,
			"configuration_rank_interval":        []int{0, 50},
			"locked_audit_rank_interval":         []int{50, 100},
		},
		Partitions:   bindings,
		OverlapCount: 0,
		ClassCounts:  classCounts,
	}
	manifestPath := filepath.Join(root, "input_split_manifest.json")
	if err := writeJSONExclusive(manifestPath, manifest, force); err != nil {
		return artifactBinding{}, err
	}
	digest, err := digestFile(manifestPath)
	if err != nil {
		return artifactBinding{}, err
	}
	return artifactBinding{Path: manifestPath, SHA256: "sha256:" + digest}, nil
}

func writePartitionCSV(
	path string,
	dataset journalmnist.Dataset,
	indices []int,
	role string,
	includePixels bool,
	force bool,
) error {
	temporary := path + ".tmp"
	file, err := os.Create(temporary)
	if err != nil {
		return err
	}
	writer := csv.NewWriter(file)
	header := []string{"row_id", "sample_id", "source_index", "source_partition", "role", "label"}
	if includePixels {
		for index := 0; index < journalmnist.PixelCount; index++ {
			header = append(header, fmt.Sprintf("pixel_%03d", index))
		}
	}
	if err := writer.Write(header); err != nil {
		return err
	}
	for rowID, index := range indices {
		sample := dataset.Samples[index]
		sourcePartition := "train"
		if index >= journalmnist.OfficialTrainRows {
			sourcePartition = "test"
		}
		row := []string{
			strconv.Itoa(rowID),
			fmt.Sprintf("mnist_%05d", index),
			strconv.Itoa(index),
			sourcePartition,
			role,
			strconv.Itoa(sample.Label),
		}
		if includePixels {
			for _, pixel := range sample.Pixels {
				row = append(row, strconv.Itoa(int(pixel)))
			}
		}
		if err := writer.Write(row); err != nil {
			return err
		}
	}
	writer.Flush()
	if err := writer.Error(); err != nil {
		return err
	}
	if err := file.Close(); err != nil {
		return err
	}
	if !force {
		if existing, err := os.ReadFile(path); err == nil {
			generated, readErr := os.ReadFile(temporary)
			if readErr != nil {
				return readErr
			}
			if !bytes.Equal(existing, generated) {
				return fmt.Errorf("existing partition %s is not byte-identical", path)
			}
			return os.Remove(temporary)
		}
	}
	return os.Rename(temporary, path)
}

func writeJSONExclusive(path string, value any, force bool) error {
	encoded, err := canonicalJSON(value)
	if err != nil {
		return err
	}
	if !force {
		if existing, readErr := os.ReadFile(path); readErr == nil {
			if !bytes.Equal(existing, encoded) {
				return fmt.Errorf("existing artifact %s is not byte-identical", path)
			}
			return nil
		}
	}
	temporary := path + ".tmp"
	if err := os.WriteFile(temporary, encoded, 0o644); err != nil {
		return err
	}
	return os.Rename(temporary, path)
}

func canonicalJSON(value any) ([]byte, error) {
	var buffer bytes.Buffer
	encoder := json.NewEncoder(&buffer)
	encoder.SetEscapeHTML(false)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(value); err != nil {
		return nil, err
	}
	return buffer.Bytes(), nil
}

func digestFile(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer file.Close()
	digest := sha256.New()
	if _, err := io.Copy(digest, file); err != nil {
		return "", err
	}
	return hex.EncodeToString(digest.Sum(nil)), nil
}

func fatalf(format string, values ...any) {
	fmt.Fprintf(os.Stderr, "flipguard-journal-mnist-prepare: "+format+"\n", values...)
	os.Exit(1)
}
