package main

import (
	"compress/gzip"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"github.com/hasslelee/flipguard/internal/journalmnist"
	"io"
	"os"
	"path/filepath"
	"time"
)

func must(err error) {
	if err != nil {
		panic(err)
	}
}
func hash(path string) string {
	b, e := os.ReadFile(path)
	must(e)
	h := sha256.Sum256(b)
	return "sha256:" + hex.EncodeToString(h[:])
}
func readGzip(path string) []byte {
	f, e := os.Open(path)
	must(e)
	defer f.Close()
	r, e := gzip.NewReader(f)
	must(e)
	defer r.Close()
	b, e := io.ReadAll(r)
	must(e)
	return b
}
func write(path string, v any) {
	f, e := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0644)
	must(e)
	defer f.Close()
	en := json.NewEncoder(f)
	en.SetIndent("", "  ")
	must(en.Encode(v))
}
func main() {
	raw := flag.String("raw", "", "official raw directory")
	run := flag.String("run", "", "run directory")
	seed := flag.Uint64("seed", 0, "training initialization")
	source := flag.String("source-commit", "", "source commit")
	flag.Parse()
	out := filepath.Join(*run, fmt.Sprintf("plaintext/seed_%d", *seed))
	if _, e := os.Stat(out); e == nil {
		panic("refuse existing seed output")
	}
	must(os.MkdirAll(out, 0755))
	xb := readGzip(filepath.Join(*raw, "train-images-idx3-ubyte.gz"))
	yb := readGzip(filepath.Join(*raw, "train-labels-idx1-ubyte.gz"))
	if binary.BigEndian.Uint32(xb[:4]) != 2051 || len(xb) != 16+60000*784 || len(yb) != 8+60000 {
		panic("invalid official train IDX")
	}
	dataset := journalmnist.Dataset{SourcePath: filepath.Join(*run, "DATA_SOURCE.json"), Samples: make([]journalmnist.Sample, 60000)}
	for i := range dataset.Samples {
		s := &dataset.Samples[i]
		s.SourceIndex = i
		s.Label = int(yb[8+i])
		copy(s.Pixels[:], xb[16+784*i:16+784*(i+1)])
	}
	var split struct {
		Training    []int `json:"training"`
		Development []int `json:"development"`
		Selection   []int `json:"selection"`
	}
	b, e := os.ReadFile(filepath.Join(*run, "SPLIT.json"))
	must(e)
	must(json.Unmarshal(b, &split))
	if len(split.Training) != 54500 || len(split.Development) != 5000 || len(split.Selection) != 500 {
		panic("split counts")
	}
	start := time.Now()
	var progress []map[string]any
	result, e := journalmnist.TrainMLP(dataset, split.Training, split.Development, *seed, func(ep journalmnist.TrainingEpoch) {
		fmt.Printf("seed=%d epoch=%d loss=%.9f online_train_acc=%.6f dev_acc=%.6f seconds=%.3f\n", *seed, ep.Epoch, ep.MeanTrainingLoss, ep.TrainingAccuracy, ep.ValidationAccuracy, ep.DurationSeconds)
		progress = append(progress, map[string]any{"epoch": ep, "seconds": ep.DurationSeconds})
		write(filepath.Join(out, fmt.Sprintf("epoch_%02d.json", ep.Epoch)), progress[len(progress)-1])
	})
	must(e)
	model := journalmnist.ModelArtifact{SchemaVersion: journalmnist.ModelArtifactSchemaV1, SourceCommit: *source, DatasetID: "fashion_mnist_10class", ModelID: "fashion_mnist_mlp_square_784_100_10_v1", ModelType: journalmnist.MLPModelType, GraphAdapterID: "mnist_multiclass_feature_ciphertext_batch_adapter_v1", GraphFormula: "affine_100(square(affine_784(input)))->10_logits", Architecture: map[string]any{"input_dim": 784, "hidden_units": 100, "activation": "square", "output_logits": 10}, Preprocessing: map[string]any{"pixel_normalization": "pixel/255", "output_scaling": "none", "test_used": false}, Source: journalmnist.ArtifactBinding{Path: dataset.SourcePath, SHA256: hash(dataset.SourcePath)}, SplitManifest: journalmnist.ArtifactBinding{Path: filepath.Join(*run, "SPLIT.json"), SHA256: hash(filepath.Join(*run, "SPLIT.json"))}, Training: map[string]any{"training_seed": *seed, "original_function": "journalmnist.TrainMLP", "epochs": 8, "batch_size": 64, "early_stopping": false, "training_seconds": time.Since(start).Seconds(), "convergence_guarantee": false}, TrainingHistory: result.History, Parameters: result.Model.Parameters, PlaintextAccuracy: map[string]float64{"development": result.History[7].ValidationAccuracy}}
	must(model.Validate())
	write(filepath.Join(out, "model.json"), model)
	dev := make([]map[string]any, 0, len(split.Development))
	for _, i := range split.Development {
		z := result.Model.Logits(dataset.Samples[i])
		dev = append(dev, map[string]any{"source_index": i, "label": dataset.Samples[i].Label, "logits": z})
	}
	write(filepath.Join(out, "development_logits.json"), dev)
	fmt.Printf("COMPLETED seed=%d seconds=%.3f official_test_not_loaded=true\n", *seed, time.Since(start).Seconds())
}
