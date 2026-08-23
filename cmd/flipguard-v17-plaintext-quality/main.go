package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"

	"github.com/hasslelee/flipguard/internal/journalmnist"
)

type qualityResult struct {
	SchemaVersion      string             `json:"schema_version"`
	ModelID            string             `json:"model_id"`
	ModelType          string             `json:"model_type"`
	ModelSHA256        string             `json:"model_sha256"`
	SourceSHA256       string             `json:"source_sha256"`
	Population         string             `json:"population"`
	Samples            int                `json:"samples"`
	ClassCounts        []int              `json:"class_counts"`
	Accuracy           float64            `json:"accuracy"`
	BalancedAccuracy   float64            `json:"balanced_accuracy"`
	MacroF1            float64            `json:"macro_f1"`
	TopTwoGapQuantiles map[string]float64 `json:"top_two_gap_quantiles"`
}

func main() {
	modelPath := flag.String("model", "", "frozen journal MNIST model")
	sourcePath := flag.String("source", "results/source_datasets/mnist/mnist_784.arff.gz", "byte-pinned MNIST source")
	output := flag.String("output", "", "exclusive derived quality artifact")
	flag.Parse()
	if *modelPath == "" || *output == "" {
		fatalf("--model and --output are required")
	}
	if _, err := os.Stat(*output); err == nil {
		fmt.Printf("quality artifact already exists: %s\n", *output)
		return
	}
	model, err := journalmnist.LoadModelArtifact(*modelPath)
	if err != nil {
		fatalf("load model: %v", err)
	}
	dataset, err := journalmnist.LoadDataset(*sourcePath)
	if err != nil {
		fatalf("load source: %v", err)
	}
	confusion := make([][]int, journalmnist.ClassCount)
	for index := range confusion {
		confusion[index] = make([]int, journalmnist.ClassCount)
	}
	gaps := make([]float64, 0, journalmnist.OfficialTestRows)
	correct := 0
	for index := journalmnist.OfficialTrainRows; index < len(dataset.Samples); index++ {
		sample := dataset.Samples[index]
		var logits [journalmnist.ClassCount]float64
		switch model.ModelType {
		case journalmnist.MLPModelType:
			logits = (journalmnist.MLPModel{Parameters: model.Parameters}).Logits(sample)
		case journalmnist.LeNetModelType:
			logits = (journalmnist.LeNetModel{Parameters: model.Parameters}).Logits(sample)
		default:
			fatalf("unsupported model type %s", model.ModelType)
		}
		top, runner := topTwo(logits)
		confusion[sample.Label][top]++
		if top == sample.Label {
			correct++
		}
		gaps = append(gaps, logits[top]-logits[runner])
	}
	classCounts := make([]int, journalmnist.ClassCount)
	balanced, macroF1 := 0.0, 0.0
	for class := 0; class < journalmnist.ClassCount; class++ {
		tp := confusion[class][class]
		actual, predicted := 0, 0
		for other := 0; other < journalmnist.ClassCount; other++ {
			actual += confusion[class][other]
			predicted += confusion[other][class]
		}
		classCounts[class] = actual
		recall := ratio(tp, actual)
		precision := ratio(tp, predicted)
		balanced += recall
		if precision+recall > 0 {
			macroF1 += 2 * precision * recall / (precision + recall)
		}
	}
	sort.Float64s(gaps)
	result := qualityResult{
		SchemaVersion: "flipguard_v17_multiclass_plaintext_quality_v1",
		ModelID:       model.ModelID, ModelType: model.ModelType,
		ModelSHA256: digest(*modelPath), SourceSHA256: digest(*sourcePath),
		Population: "official_MNIST_test_10000", Samples: len(gaps), ClassCounts: classCounts,
		Accuracy:         float64(correct) / float64(len(gaps)),
		BalancedAccuracy: balanced / journalmnist.ClassCount,
		MacroF1:          macroF1 / journalmnist.ClassCount,
		TopTwoGapQuantiles: map[string]float64{
			"min": quantile(gaps, 0), "p05": quantile(gaps, 0.05),
			"p25": quantile(gaps, 0.25), "median": quantile(gaps, 0.5),
			"p75": quantile(gaps, 0.75), "p95": quantile(gaps, 0.95), "max": quantile(gaps, 1),
		},
	}
	if expected, ok := model.PlaintextAccuracy["official_test_10000"]; ok && math.Abs(expected-result.Accuracy) > 1e-12 {
		fatalf("derived accuracy %.17g differs from model artifact %.17g", result.Accuracy, expected)
	}
	data, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		fatalf("marshal: %v", err)
	}
	if err := os.MkdirAll(filepath.Dir(*output), 0o755); err != nil {
		fatalf("create output parent: %v", err)
	}
	handle, err := os.OpenFile(*output, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o644)
	if err != nil {
		fatalf("create output: %v", err)
	}
	if _, err := handle.Write(append(data, '\n')); err != nil {
		_ = handle.Close()
		fatalf("write output: %v", err)
	}
	if err := handle.Close(); err != nil {
		fatalf("close output: %v", err)
	}
	fmt.Printf("model=%s samples=%d accuracy=%.6f balanced_accuracy=%.6f macro_f1=%.6f\n", result.ModelID, result.Samples, result.Accuracy, result.BalancedAccuracy, result.MacroF1)
}

func topTwo(logits [journalmnist.ClassCount]float64) (int, int) {
	top := 0
	for index := 1; index < len(logits); index++ {
		if logits[index] > logits[top] {
			top = index
		}
	}
	runner := -1
	for index := range logits {
		if index != top && (runner == -1 || logits[index] > logits[runner]) {
			runner = index
		}
	}
	return top, runner
}

func ratio(numerator, denominator int) float64 {
	if denominator == 0 {
		return 0
	}
	return float64(numerator) / float64(denominator)
}

func quantile(sorted []float64, q float64) float64 {
	if len(sorted) == 0 {
		return 0
	}
	position := q * float64(len(sorted)-1)
	lower := int(math.Floor(position))
	upper := int(math.Ceil(position))
	if lower == upper {
		return sorted[lower]
	}
	weight := position - float64(lower)
	return sorted[lower]*(1-weight) + sorted[upper]*weight
}

func digest(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		fatalf("digest %s: %v", path, err)
	}
	sum := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(sum[:])
}

func fatalf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "flipguard-v17-plaintext-quality: "+format+"\n", args...)
	os.Exit(1)
}
