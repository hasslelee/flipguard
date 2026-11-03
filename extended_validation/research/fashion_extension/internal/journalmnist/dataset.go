package journalmnist

import (
	"bufio"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"sort"
	"strconv"
	"strings"
)

const (
	DatasetSchemaVersion = "flipguard_journal_mnist_dataset_v1"
	SplitPolicyID        = "mnist_multiclass_sha256_stratified_rank_v1"
	ExpectedSourceSHA256 = "fe4410d8dbb50f6db6482b187557c5cb8bccfbcec74eeb6abc47c858f4ffab78"

	OfficialTrainRows = 60000
	OfficialTestRows  = 10000
	PixelCount        = 28 * 28
	ClassCount        = 10

	ModelValidationPerClass  = 500
	ConfigValidationPerClass = 50
	LockedAuditPerClass      = 50
)

type Sample struct {
	SourceIndex int
	Label       int
	Pixels      [PixelCount]uint8
}

type Dataset struct {
	SourcePath   string
	SourceSHA256 string
	Samples      []Sample
}

type Split struct {
	ModelTraining           []int
	ModelValidation         []int
	ConfigurationValidation []int
	LockedAudit             []int
}

func LoadDataset(path string) (Dataset, error) {
	digest, err := digestFile(path)
	if err != nil {
		return Dataset{}, err
	}
	if digest != ExpectedSourceSHA256 {
		return Dataset{}, fmt.Errorf(
			"MNIST source digest %s; expected %s",
			digest,
			ExpectedSourceSHA256,
		)
	}
	file, err := os.Open(path)
	if err != nil {
		return Dataset{}, fmt.Errorf("open MNIST source: %w", err)
	}
	defer file.Close()
	reader, err := gzip.NewReader(file)
	if err != nil {
		return Dataset{}, fmt.Errorf("open MNIST gzip: %w", err)
	}
	defer reader.Close()

	scanner := bufio.NewScanner(reader)
	scanner.Buffer(make([]byte, 64*1024), 2*1024*1024)
	dataStarted := false
	samples := make([]Sample, 0, OfficialTrainRows+OfficialTestRows)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if !dataStarted {
			if strings.EqualFold(line, "@data") {
				dataStarted = true
			}
			continue
		}
		if line == "" || strings.HasPrefix(line, "%") {
			continue
		}
		fields := strings.Split(line, ",")
		if len(fields) != PixelCount+1 {
			return Dataset{}, fmt.Errorf(
				"MNIST row %d has %d fields",
				len(samples),
				len(fields),
			)
		}
		sample := Sample{SourceIndex: len(samples)}
		for index := 0; index < PixelCount; index++ {
			value, parseErr := strconv.Atoi(fields[index])
			if parseErr != nil || value < 0 || value > 255 {
				return Dataset{}, fmt.Errorf(
					"MNIST row %d pixel %d is invalid",
					sample.SourceIndex,
					index,
				)
			}
			sample.Pixels[index] = uint8(value)
		}
		label, parseErr := strconv.Atoi(fields[PixelCount])
		if parseErr != nil || label < 0 || label >= ClassCount {
			return Dataset{}, fmt.Errorf(
				"MNIST row %d label is invalid",
				sample.SourceIndex,
			)
		}
		sample.Label = label
		samples = append(samples, sample)
	}
	if err := scanner.Err(); err != nil {
		return Dataset{}, fmt.Errorf("scan MNIST source: %w", err)
	}
	if len(samples) != OfficialTrainRows+OfficialTestRows {
		return Dataset{}, fmt.Errorf(
			"MNIST has %d rows; expected %d",
			len(samples),
			OfficialTrainRows+OfficialTestRows,
		)
	}
	return Dataset{
		SourcePath:   path,
		SourceSHA256: digest,
		Samples:      samples,
	}, nil
}

func BuildSplit(dataset Dataset) (Split, error) {
	if len(dataset.Samples) != OfficialTrainRows+OfficialTestRows {
		return Split{}, fmt.Errorf("dataset row count changed")
	}
	trainByClass := [ClassCount][]int{}
	testByClass := [ClassCount][]int{}
	for index, sample := range dataset.Samples {
		if sample.SourceIndex != index {
			return Split{}, fmt.Errorf("MNIST source order changed at row %d", index)
		}
		if index < OfficialTrainRows {
			trainByClass[sample.Label] = append(trainByClass[sample.Label], index)
		} else {
			testByClass[sample.Label] = append(testByClass[sample.Label], index)
		}
	}
	split := Split{}
	for label := 0; label < ClassCount; label++ {
		sortByStableRank(trainByClass[label], label, "model")
		if len(trainByClass[label]) <= ModelValidationPerClass {
			return Split{}, fmt.Errorf("class %d has too few train rows", label)
		}
		split.ModelValidation = append(
			split.ModelValidation,
			trainByClass[label][:ModelValidationPerClass]...,
		)
		split.ModelTraining = append(
			split.ModelTraining,
			trainByClass[label][ModelValidationPerClass:]...,
		)

		sortByStableRank(testByClass[label], label, "encrypted")
		required := ConfigValidationPerClass + LockedAuditPerClass
		if len(testByClass[label]) < required {
			return Split{}, fmt.Errorf("class %d has too few test rows", label)
		}
		split.ConfigurationValidation = append(
			split.ConfigurationValidation,
			testByClass[label][:ConfigValidationPerClass]...,
		)
		split.LockedAudit = append(
			split.LockedAudit,
			testByClass[label][ConfigValidationPerClass:required]...,
		)
	}
	sort.Ints(split.ModelTraining)
	sort.Ints(split.ModelValidation)
	sort.Ints(split.ConfigurationValidation)
	sort.Ints(split.LockedAudit)
	if err := ValidateSplit(dataset, split); err != nil {
		return Split{}, err
	}
	return split, nil
}

func ValidateSplit(dataset Dataset, split Split) error {
	expectedTrain := OfficialTrainRows - ClassCount*ModelValidationPerClass
	if len(split.ModelTraining) != expectedTrain ||
		len(split.ModelValidation) != ClassCount*ModelValidationPerClass ||
		len(split.ConfigurationValidation) != ClassCount*ConfigValidationPerClass ||
		len(split.LockedAudit) != ClassCount*LockedAuditPerClass {
		return fmt.Errorf(
			"split sizes changed: train=%d model_validation=%d configuration=%d audit=%d",
			len(split.ModelTraining),
			len(split.ModelValidation),
			len(split.ConfigurationValidation),
			len(split.LockedAudit),
		)
	}
	roles := []struct {
		name     string
		indices  []int
		train    bool
		perClass int
	}{
		{"model_training", split.ModelTraining, true, -1},
		{"model_validation", split.ModelValidation, true, ModelValidationPerClass},
		{"configuration_validation", split.ConfigurationValidation, false, ConfigValidationPerClass},
		{"locked_audit", split.LockedAudit, false, LockedAuditPerClass},
	}
	seen := make(map[int]string)
	for _, role := range roles {
		counts := [ClassCount]int{}
		for _, index := range role.indices {
			if index < 0 || index >= len(dataset.Samples) {
				return fmt.Errorf("%s row %d is out of range", role.name, index)
			}
			isTrain := index < OfficialTrainRows
			if isTrain != role.train {
				return fmt.Errorf("%s crosses official train/test boundary", role.name)
			}
			if previous, exists := seen[index]; exists {
				return fmt.Errorf("row %d overlaps %s and %s", index, previous, role.name)
			}
			seen[index] = role.name
			counts[dataset.Samples[index].Label]++
		}
		if role.perClass >= 0 {
			for label, count := range counts {
				if count != role.perClass {
					return fmt.Errorf(
						"%s class %d count %d; expected %d",
						role.name,
						label,
						count,
						role.perClass,
					)
				}
			}
		}
	}
	return nil
}

func StableRank(sourceIndex int, label int, role string) [32]byte {
	return sha256.Sum256([]byte(
		SplitPolicyID + "\x00" + role + "\x00" +
			strconv.Itoa(label) + "\x00" + strconv.Itoa(sourceIndex),
	))
}

func sortByStableRank(indices []int, label int, role string) {
	sort.Slice(indices, func(left, right int) bool {
		leftRank := StableRank(indices[left], label, role)
		rightRank := StableRank(indices[right], label, role)
		comparison := strings.Compare(
			hex.EncodeToString(leftRank[:]),
			hex.EncodeToString(rightRank[:]),
		)
		if comparison == 0 {
			return indices[left] < indices[right]
		}
		return comparison < 0
	})
}

func digestFile(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", fmt.Errorf("open %s for digest: %w", path, err)
	}
	defer file.Close()
	digest := sha256.New()
	if _, err := io.Copy(digest, file); err != nil {
		return "", fmt.Errorf("digest %s: %w", path, err)
	}
	return hex.EncodeToString(digest.Sum(nil)), nil
}
