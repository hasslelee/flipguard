package journalmnist

import (
	"fmt"
	"math"
	"time"
)

const (
	MLPModelID = "mnist_mlp_square_784_100_10_v1"
	MLPHidden  = 100

	mlpW1Offset   = 0
	mlpB1Offset   = mlpW1Offset + MLPHidden*PixelCount
	mlpW2Offset   = mlpB1Offset + MLPHidden
	mlpB2Offset   = mlpW2Offset + ClassCount*MLPHidden
	mlpParamCount = mlpB2Offset + ClassCount
)

type MLPModel struct {
	Parameters []float64 `json:"parameters"`
}

type TrainingEpoch struct {
	Epoch              int     `json:"epoch"`
	LearningRate       float64 `json:"learning_rate"`
	MeanTrainingLoss   float64 `json:"mean_training_loss"`
	TrainingAccuracy   float64 `json:"training_accuracy"`
	ValidationAccuracy float64 `json:"validation_accuracy"`
	DurationSeconds    float64 `json:"-"`
}

type MLPTrainingResult struct {
	Model   MLPModel        `json:"model"`
	History []TrainingEpoch `json:"history"`
}

type sparsePixel struct {
	index uint16
	value float64
}

type sparseSample struct {
	label  int
	pixels []sparsePixel
}

func NewMLPModel(seed uint64) MLPModel {
	parameters := make([]float64, mlpParamCount)
	random := splitMix64{state: seed}
	hiddenLimit := math.Sqrt(6.0 / float64(PixelCount+MLPHidden))
	for index := mlpW1Offset; index < mlpB1Offset; index++ {
		parameters[index] = (2*random.uniform() - 1) * hiddenLimit
	}
	outputLimit := math.Sqrt(6.0 / float64(MLPHidden+ClassCount))
	for index := mlpW2Offset; index < mlpB2Offset; index++ {
		parameters[index] = (2*random.uniform() - 1) * outputLimit
	}
	return MLPModel{Parameters: parameters}
}

func (model MLPModel) Validate() error {
	if len(model.Parameters) != mlpParamCount {
		return fmt.Errorf(
			"MLP parameter count %d; expected %d",
			len(model.Parameters),
			mlpParamCount,
		)
	}
	for index, value := range model.Parameters {
		if math.IsNaN(value) || math.IsInf(value, 0) {
			return fmt.Errorf("MLP parameter %d is non-finite", index)
		}
	}
	return nil
}

func (model MLPModel) Logits(sample Sample) [ClassCount]float64 {
	var hiddenPre [MLPHidden]float64
	var hidden [MLPHidden]float64
	for unit := 0; unit < MLPHidden; unit++ {
		hiddenPre[unit] = model.Parameters[mlpB1Offset+unit]
	}
	for pixelIndex, raw := range sample.Pixels {
		if raw == 0 {
			continue
		}
		value := float64(raw) / 255
		for unit := 0; unit < MLPHidden; unit++ {
			hiddenPre[unit] += model.Parameters[mlpW1Offset+unit*PixelCount+pixelIndex] * value
		}
	}
	for unit, value := range hiddenPre {
		hidden[unit] = value * value
	}
	var logits [ClassCount]float64
	for classIndex := 0; classIndex < ClassCount; classIndex++ {
		value := model.Parameters[mlpB2Offset+classIndex]
		for unit := 0; unit < MLPHidden; unit++ {
			value += model.Parameters[mlpW2Offset+classIndex*MLPHidden+unit] * hidden[unit]
		}
		logits[classIndex] = value
	}
	return logits
}

func TrainMLP(
	dataset Dataset,
	trainingIndices []int,
	validationIndices []int,
	seed uint64,
	progress func(TrainingEpoch),
) (MLPTrainingResult, error) {
	model := NewMLPModel(seed)
	training := makeSparseSamples(dataset, trainingIndices)
	validation := makeSparseSamples(dataset, validationIndices)
	order := make([]int, len(training))
	for index := range order {
		order[index] = index
	}
	weightMask := make([]bool, len(model.Parameters))
	for index := mlpW1Offset; index < mlpB1Offset; index++ {
		weightMask[index] = true
	}
	for index := mlpW2Offset; index < mlpB2Offset; index++ {
		weightMask[index] = true
	}
	optimizer := newAdam(len(model.Parameters), weightMask, 1e-5)
	random := splitMix64{state: seed ^ 0x4d4c50545241494e}
	history := make([]TrainingEpoch, 0, 8)
	for epoch := 1; epoch <= 8; epoch++ {
		start := time.Now()
		random.shuffle(order)
		learningRate := 0.001 * math.Pow(0.9, float64(epoch-1))
		loss := 0.0
		correct := 0
		for batchStart := 0; batchStart < len(order); batchStart += 64 {
			batchEnd := batchStart + 64
			if batchEnd > len(order) {
				batchEnd = len(order)
			}
			gradient := make([]float64, len(model.Parameters))
			for _, shuffledIndex := range order[batchStart:batchEnd] {
				sample := training[shuffledIndex]
				var hiddenPre [MLPHidden]float64
				var hidden [MLPHidden]float64
				var logits [ClassCount]float64
				forwardSparseMLP(model.Parameters, sample, &hiddenPre, &hidden, &logits)
				if argmax(logits[:]) == sample.label {
					correct++
				}
				var dLogits [ClassCount]float64
				loss += softmaxCrossEntropy(logits[:], sample.label, dLogits[:])
				var dHidden [MLPHidden]float64
				for classIndex, delta := range dLogits {
					gradient[mlpB2Offset+classIndex] += delta
					for unit := 0; unit < MLPHidden; unit++ {
						weightIndex := mlpW2Offset + classIndex*MLPHidden + unit
						gradient[weightIndex] += delta * hidden[unit]
						dHidden[unit] += delta * model.Parameters[weightIndex]
					}
				}
				for unit := 0; unit < MLPHidden; unit++ {
					delta := 2 * hiddenPre[unit] * dHidden[unit]
					gradient[mlpB1Offset+unit] += delta
					base := mlpW1Offset + unit*PixelCount
					for _, pixel := range sample.pixels {
						gradient[base+int(pixel.index)] += delta * pixel.value
					}
				}
			}
			optimizer.update(
				model.Parameters,
				gradient,
				learningRate,
				batchEnd-batchStart,
			)
		}
		if err := model.Validate(); err != nil {
			return MLPTrainingResult{}, fmt.Errorf("MLP epoch %d: %w", epoch, err)
		}
		epochResult := TrainingEpoch{
			Epoch:              epoch,
			LearningRate:       learningRate,
			MeanTrainingLoss:   loss / float64(len(training)),
			TrainingAccuracy:   float64(correct) / float64(len(training)),
			ValidationAccuracy: accuracySparseMLP(model.Parameters, validation),
			DurationSeconds:    time.Since(start).Seconds(),
		}
		history = append(history, epochResult)
		if progress != nil {
			progress(epochResult)
		}
	}
	return MLPTrainingResult{Model: model, History: history}, nil
}

func MLPAccuracy(model MLPModel, dataset Dataset, indices []int) float64 {
	correct := 0
	for _, index := range indices {
		logits := model.Logits(dataset.Samples[index])
		if argmax(logits[:]) == dataset.Samples[index].Label {
			correct++
		}
	}
	return float64(correct) / float64(len(indices))
}

func makeSparseSamples(dataset Dataset, indices []int) []sparseSample {
	result := make([]sparseSample, 0, len(indices))
	for _, index := range indices {
		source := dataset.Samples[index]
		sparse := sparseSample{
			label:  source.Label,
			pixels: make([]sparsePixel, 0, 192),
		}
		for pixelIndex, raw := range source.Pixels {
			if raw != 0 {
				sparse.pixels = append(sparse.pixels, sparsePixel{
					index: uint16(pixelIndex),
					value: float64(raw) / 255,
				})
			}
		}
		result = append(result, sparse)
	}
	return result
}

func forwardSparseMLP(
	parameters []float64,
	sample sparseSample,
	hiddenPre *[MLPHidden]float64,
	hidden *[MLPHidden]float64,
	logits *[ClassCount]float64,
) {
	for unit := 0; unit < MLPHidden; unit++ {
		value := parameters[mlpB1Offset+unit]
		base := mlpW1Offset + unit*PixelCount
		for _, pixel := range sample.pixels {
			value += parameters[base+int(pixel.index)] * pixel.value
		}
		hiddenPre[unit] = value
		hidden[unit] = value * value
	}
	for classIndex := 0; classIndex < ClassCount; classIndex++ {
		value := parameters[mlpB2Offset+classIndex]
		base := mlpW2Offset + classIndex*MLPHidden
		for unit := 0; unit < MLPHidden; unit++ {
			value += parameters[base+unit] * hidden[unit]
		}
		logits[classIndex] = value
	}
}

func accuracySparseMLP(parameters []float64, samples []sparseSample) float64 {
	correct := 0
	for _, sample := range samples {
		var hiddenPre [MLPHidden]float64
		var hidden [MLPHidden]float64
		var logits [ClassCount]float64
		forwardSparseMLP(parameters, sample, &hiddenPre, &hidden, &logits)
		if argmax(logits[:]) == sample.label {
			correct++
		}
	}
	return float64(correct) / float64(len(samples))
}
