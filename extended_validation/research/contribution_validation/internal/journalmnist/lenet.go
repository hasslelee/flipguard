package journalmnist

import (
	"fmt"
	"math"
	"time"
)

const (
	LeNetModelID = "mnist_lenet5_small_square_v1"

	lenetC1Channels = 6
	lenetC1Side     = 28
	lenetP1Side     = 14
	lenetC2Channels = 16
	lenetC2Side     = 10
	lenetP2Side     = 5
	lenetKernelSide = 5
	lenetFC1        = 120
	lenetFC2        = 64

	lenetC1WOffset  = 0
	lenetC1BOffset  = lenetC1WOffset + lenetC1Channels*lenetKernelSide*lenetKernelSide
	lenetC2WOffset  = lenetC1BOffset + lenetC1Channels
	lenetC2BOffset  = lenetC2WOffset + lenetC2Channels*lenetC1Channels*lenetKernelSide*lenetKernelSide
	lenetFC1WOffset = lenetC2BOffset + lenetC2Channels
	lenetFC1BOffset = lenetFC1WOffset + lenetFC1*lenetC2Channels*lenetP2Side*lenetP2Side
	lenetFC2WOffset = lenetFC1BOffset + lenetFC1
	lenetFC2BOffset = lenetFC2WOffset + lenetFC2*lenetFC1
	lenetOutWOffset = lenetFC2BOffset + lenetFC2
	lenetOutBOffset = lenetOutWOffset + ClassCount*lenetFC2
	lenetParamCount = lenetOutBOffset + ClassCount
)

type LeNetModel struct {
	Parameters []float64 `json:"parameters"`
}

type LeNetTrainingResult struct {
	Model   LeNetModel      `json:"model"`
	History []TrainingEpoch `json:"history"`
}

type lenetScratch struct {
	c1Pre  [lenetC1Channels * lenetC1Side * lenetC1Side]float64
	c1Act  [lenetC1Channels * lenetC1Side * lenetC1Side]float64
	p1     [lenetC1Channels * lenetP1Side * lenetP1Side]float64
	c2Pre  [lenetC2Channels * lenetC2Side * lenetC2Side]float64
	c2Act  [lenetC2Channels * lenetC2Side * lenetC2Side]float64
	p2     [lenetC2Channels * lenetP2Side * lenetP2Side]float64
	f1Pre  [lenetFC1]float64
	f1Act  [lenetFC1]float64
	f2Pre  [lenetFC2]float64
	f2Act  [lenetFC2]float64
	logits [ClassCount]float64
}

type lenetBackwardScratch struct {
	dF2Act [lenetFC2]float64
	dF1Act [lenetFC1]float64
	dP2    [lenetC2Channels * lenetP2Side * lenetP2Side]float64
	dC2Act [lenetC2Channels * lenetC2Side * lenetC2Side]float64
	dP1    [lenetC1Channels * lenetP1Side * lenetP1Side]float64
	dC1Act [lenetC1Channels * lenetC1Side * lenetC1Side]float64
}

func NewLeNetModel(seed uint64) LeNetModel {
	parameters := make([]float64, lenetParamCount)
	random := splitMix64{state: seed}
	initializeUniform := func(start, end int, fanIn, fanOut int) {
		limit := math.Sqrt(6.0 / float64(fanIn+fanOut))
		for index := start; index < end; index++ {
			parameters[index] = (2*random.uniform() - 1) * limit
		}
	}
	initializeUniform(
		lenetC1WOffset,
		lenetC1BOffset,
		lenetKernelSide*lenetKernelSide,
		lenetC1Channels*lenetKernelSide*lenetKernelSide,
	)
	initializeUniform(
		lenetC2WOffset,
		lenetC2BOffset,
		lenetC1Channels*lenetKernelSide*lenetKernelSide,
		lenetC2Channels*lenetKernelSide*lenetKernelSide,
	)
	initializeUniform(
		lenetFC1WOffset,
		lenetFC1BOffset,
		lenetC2Channels*lenetP2Side*lenetP2Side,
		lenetFC1,
	)
	initializeUniform(lenetFC2WOffset, lenetFC2BOffset, lenetFC1, lenetFC2)
	initializeUniform(lenetOutWOffset, lenetOutBOffset, lenetFC2, ClassCount)
	return LeNetModel{Parameters: parameters}
}

func (model LeNetModel) Validate() error {
	if len(model.Parameters) != lenetParamCount {
		return fmt.Errorf(
			"LeNet parameter count %d; expected %d",
			len(model.Parameters),
			lenetParamCount,
		)
	}
	for index, value := range model.Parameters {
		if math.IsNaN(value) || math.IsInf(value, 0) {
			return fmt.Errorf("LeNet parameter %d is non-finite", index)
		}
	}
	return nil
}

func (model LeNetModel) Logits(sample Sample) [ClassCount]float64 {
	var scratch lenetScratch
	forwardLeNet(model.Parameters, sample, &scratch)
	return scratch.logits
}

func TrainLeNet(
	dataset Dataset,
	trainingIndices []int,
	validationIndices []int,
	seed uint64,
	progress func(TrainingEpoch),
) (LeNetTrainingResult, error) {
	model := NewLeNetModel(seed)
	order := append([]int(nil), trainingIndices...)
	weightMask := make([]bool, len(model.Parameters))
	markWeightRange := func(start, end int) {
		for index := start; index < end; index++ {
			weightMask[index] = true
		}
	}
	markWeightRange(lenetC1WOffset, lenetC1BOffset)
	markWeightRange(lenetC2WOffset, lenetC2BOffset)
	markWeightRange(lenetFC1WOffset, lenetFC1BOffset)
	markWeightRange(lenetFC2WOffset, lenetFC2BOffset)
	markWeightRange(lenetOutWOffset, lenetOutBOffset)
	optimizer := newAdam(len(model.Parameters), weightMask, 1e-5)
	random := splitMix64{state: seed ^ 0x4c454e455454524e}
	history := make([]TrainingEpoch, 0, 8)
	for epoch := 1; epoch <= 8; epoch++ {
		start := time.Now()
		random.shuffle(order)
		learningRate := 0.0005 * math.Pow(0.9, float64(epoch-1))
		loss := 0.0
		correct := 0
		for batchStart := 0; batchStart < len(order); batchStart += 64 {
			batchEnd := batchStart + 64
			if batchEnd > len(order) {
				batchEnd = len(order)
			}
			gradient := make([]float64, len(model.Parameters))
			for _, sampleIndex := range order[batchStart:batchEnd] {
				sample := dataset.Samples[sampleIndex]
				var forward lenetScratch
				forwardLeNet(model.Parameters, sample, &forward)
				if argmax(forward.logits[:]) == sample.Label {
					correct++
				}
				var dLogits [ClassCount]float64
				loss += softmaxCrossEntropy(
					forward.logits[:],
					sample.Label,
					dLogits[:],
				)
				backwardLeNet(
					model.Parameters,
					sample,
					&forward,
					dLogits,
					gradient,
				)
			}
			optimizer.update(
				model.Parameters,
				gradient,
				learningRate,
				batchEnd-batchStart,
			)
		}
		if err := model.Validate(); err != nil {
			return LeNetTrainingResult{}, fmt.Errorf("LeNet epoch %d: %w", epoch, err)
		}
		epochResult := TrainingEpoch{
			Epoch:              epoch,
			LearningRate:       learningRate,
			MeanTrainingLoss:   loss / float64(len(order)),
			TrainingAccuracy:   float64(correct) / float64(len(order)),
			ValidationAccuracy: LeNetAccuracy(model, dataset, validationIndices),
			DurationSeconds:    time.Since(start).Seconds(),
		}
		history = append(history, epochResult)
		if progress != nil {
			progress(epochResult)
		}
	}
	return LeNetTrainingResult{Model: model, History: history}, nil
}

func LeNetAccuracy(model LeNetModel, dataset Dataset, indices []int) float64 {
	correct := 0
	for _, index := range indices {
		logits := model.Logits(dataset.Samples[index])
		if argmax(logits[:]) == dataset.Samples[index].Label {
			correct++
		}
	}
	return float64(correct) / float64(len(indices))
}

func forwardLeNet(parameters []float64, sample Sample, scratch *lenetScratch) {
	for channel := 0; channel < lenetC1Channels; channel++ {
		for row := 0; row < lenetC1Side; row++ {
			for column := 0; column < lenetC1Side; column++ {
				value := parameters[lenetC1BOffset+channel]
				for kernelRow := 0; kernelRow < lenetKernelSide; kernelRow++ {
					for kernelColumn := 0; kernelColumn < lenetKernelSide; kernelColumn++ {
						raw := paddedPixel(sample, row+kernelRow, column+kernelColumn)
						if raw == 0 {
							continue
						}
						weight := lenetC1WOffset +
							(channel*lenetKernelSide+kernelRow)*lenetKernelSide +
							kernelColumn
						value += parameters[weight] * float64(raw) / 255
					}
				}
				index := c1Index(channel, row, column)
				scratch.c1Pre[index] = value
				scratch.c1Act[index] = value * value
			}
		}
	}
	for channel := 0; channel < lenetC1Channels; channel++ {
		for row := 0; row < lenetP1Side; row++ {
			for column := 0; column < lenetP1Side; column++ {
				total := 0.0
				for deltaRow := 0; deltaRow < 2; deltaRow++ {
					for deltaColumn := 0; deltaColumn < 2; deltaColumn++ {
						total += scratch.c1Act[c1Index(channel, 2*row+deltaRow, 2*column+deltaColumn)]
					}
				}
				scratch.p1[p1Index(channel, row, column)] = total / 4
			}
		}
	}
	for outputChannel := 0; outputChannel < lenetC2Channels; outputChannel++ {
		for row := 0; row < lenetC2Side; row++ {
			for column := 0; column < lenetC2Side; column++ {
				value := parameters[lenetC2BOffset+outputChannel]
				for inputChannel := 0; inputChannel < lenetC1Channels; inputChannel++ {
					for kernelRow := 0; kernelRow < lenetKernelSide; kernelRow++ {
						for kernelColumn := 0; kernelColumn < lenetKernelSide; kernelColumn++ {
							weight := c2WeightIndex(
								outputChannel,
								inputChannel,
								kernelRow,
								kernelColumn,
							)
							value += parameters[weight] * scratch.p1[p1Index(inputChannel, row+kernelRow, column+kernelColumn)]
						}
					}
				}
				index := c2Index(outputChannel, row, column)
				scratch.c2Pre[index] = value
				scratch.c2Act[index] = value * value
			}
		}
	}
	for channel := 0; channel < lenetC2Channels; channel++ {
		for row := 0; row < lenetP2Side; row++ {
			for column := 0; column < lenetP2Side; column++ {
				total := 0.0
				for deltaRow := 0; deltaRow < 2; deltaRow++ {
					for deltaColumn := 0; deltaColumn < 2; deltaColumn++ {
						total += scratch.c2Act[c2Index(channel, 2*row+deltaRow, 2*column+deltaColumn)]
					}
				}
				scratch.p2[p2Index(channel, row, column)] = total / 4
			}
		}
	}
	for unit := 0; unit < lenetFC1; unit++ {
		value := parameters[lenetFC1BOffset+unit]
		base := lenetFC1WOffset + unit*len(scratch.p2)
		for input, inputValue := range scratch.p2 {
			value += parameters[base+input] * inputValue
		}
		scratch.f1Pre[unit] = value
		scratch.f1Act[unit] = value * value
	}
	for unit := 0; unit < lenetFC2; unit++ {
		value := parameters[lenetFC2BOffset+unit]
		base := lenetFC2WOffset + unit*lenetFC1
		for input, inputValue := range scratch.f1Act {
			value += parameters[base+input] * inputValue
		}
		scratch.f2Pre[unit] = value
		scratch.f2Act[unit] = value * value
	}
	for classIndex := 0; classIndex < ClassCount; classIndex++ {
		value := parameters[lenetOutBOffset+classIndex]
		base := lenetOutWOffset + classIndex*lenetFC2
		for input, inputValue := range scratch.f2Act {
			value += parameters[base+input] * inputValue
		}
		scratch.logits[classIndex] = value
	}
}

func backwardLeNet(
	parameters []float64,
	sample Sample,
	forward *lenetScratch,
	dLogits [ClassCount]float64,
	gradient []float64,
) {
	var backward lenetBackwardScratch
	for classIndex, delta := range dLogits {
		gradient[lenetOutBOffset+classIndex] += delta
		base := lenetOutWOffset + classIndex*lenetFC2
		for unit := 0; unit < lenetFC2; unit++ {
			gradient[base+unit] += delta * forward.f2Act[unit]
			backward.dF2Act[unit] += delta * parameters[base+unit]
		}
	}
	for unit := 0; unit < lenetFC2; unit++ {
		delta := 2 * forward.f2Pre[unit] * backward.dF2Act[unit]
		gradient[lenetFC2BOffset+unit] += delta
		base := lenetFC2WOffset + unit*lenetFC1
		for input := 0; input < lenetFC1; input++ {
			gradient[base+input] += delta * forward.f1Act[input]
			backward.dF1Act[input] += delta * parameters[base+input]
		}
	}
	for unit := 0; unit < lenetFC1; unit++ {
		delta := 2 * forward.f1Pre[unit] * backward.dF1Act[unit]
		gradient[lenetFC1BOffset+unit] += delta
		base := lenetFC1WOffset + unit*len(forward.p2)
		for input := range forward.p2 {
			gradient[base+input] += delta * forward.p2[input]
			backward.dP2[input] += delta * parameters[base+input]
		}
	}
	for channel := 0; channel < lenetC2Channels; channel++ {
		for row := 0; row < lenetP2Side; row++ {
			for column := 0; column < lenetP2Side; column++ {
				delta := backward.dP2[p2Index(channel, row, column)] / 4
				for deltaRow := 0; deltaRow < 2; deltaRow++ {
					for deltaColumn := 0; deltaColumn < 2; deltaColumn++ {
						backward.dC2Act[c2Index(channel, 2*row+deltaRow, 2*column+deltaColumn)] += delta
					}
				}
			}
		}
	}
	for outputChannel := 0; outputChannel < lenetC2Channels; outputChannel++ {
		for row := 0; row < lenetC2Side; row++ {
			for column := 0; column < lenetC2Side; column++ {
				index := c2Index(outputChannel, row, column)
				delta := 2 * forward.c2Pre[index] * backward.dC2Act[index]
				gradient[lenetC2BOffset+outputChannel] += delta
				for inputChannel := 0; inputChannel < lenetC1Channels; inputChannel++ {
					for kernelRow := 0; kernelRow < lenetKernelSide; kernelRow++ {
						for kernelColumn := 0; kernelColumn < lenetKernelSide; kernelColumn++ {
							inputIndex := p1Index(
								inputChannel,
								row+kernelRow,
								column+kernelColumn,
							)
							weight := c2WeightIndex(
								outputChannel,
								inputChannel,
								kernelRow,
								kernelColumn,
							)
							gradient[weight] += delta * forward.p1[inputIndex]
							backward.dP1[inputIndex] += delta * parameters[weight]
						}
					}
				}
			}
		}
	}
	for channel := 0; channel < lenetC1Channels; channel++ {
		for row := 0; row < lenetP1Side; row++ {
			for column := 0; column < lenetP1Side; column++ {
				delta := backward.dP1[p1Index(channel, row, column)] / 4
				for deltaRow := 0; deltaRow < 2; deltaRow++ {
					for deltaColumn := 0; deltaColumn < 2; deltaColumn++ {
						backward.dC1Act[c1Index(channel, 2*row+deltaRow, 2*column+deltaColumn)] += delta
					}
				}
			}
		}
	}
	for channel := 0; channel < lenetC1Channels; channel++ {
		for row := 0; row < lenetC1Side; row++ {
			for column := 0; column < lenetC1Side; column++ {
				index := c1Index(channel, row, column)
				delta := 2 * forward.c1Pre[index] * backward.dC1Act[index]
				gradient[lenetC1BOffset+channel] += delta
				for kernelRow := 0; kernelRow < lenetKernelSide; kernelRow++ {
					for kernelColumn := 0; kernelColumn < lenetKernelSide; kernelColumn++ {
						raw := paddedPixel(sample, row+kernelRow, column+kernelColumn)
						if raw == 0 {
							continue
						}
						weight := lenetC1WOffset +
							(channel*lenetKernelSide+kernelRow)*lenetKernelSide +
							kernelColumn
						gradient[weight] += delta * float64(raw) / 255
					}
				}
			}
		}
	}
}

func paddedPixel(sample Sample, paddedRow int, paddedColumn int) uint8 {
	row := paddedRow - 2
	column := paddedColumn - 2
	if row < 0 || row >= 28 || column < 0 || column >= 28 {
		return 0
	}
	return sample.Pixels[row*28+column]
}

func c1Index(channel, row, column int) int {
	return (channel*lenetC1Side+row)*lenetC1Side + column
}

func p1Index(channel, row, column int) int {
	return (channel*lenetP1Side+row)*lenetP1Side + column
}

func c2Index(channel, row, column int) int {
	return (channel*lenetC2Side+row)*lenetC2Side + column
}

func p2Index(channel, row, column int) int {
	return (channel*lenetP2Side+row)*lenetP2Side + column
}

func c2WeightIndex(outputChannel, inputChannel, row, column int) int {
	return lenetC2WOffset +
		(((outputChannel*lenetC1Channels+inputChannel)*lenetKernelSide+row)*
			lenetKernelSide + column)
}
