package journalmnist

const (
	LeNetC1Channels = lenetC1Channels
	LeNetC1Side     = lenetC1Side
	LeNetP1Side     = lenetP1Side
	LeNetC2Channels = lenetC2Channels
	LeNetC2Side     = lenetC2Side
	LeNetP2Side     = lenetP2Side
	LeNetKernelSide = lenetKernelSide
	LeNetFC1        = lenetFC1
	LeNetFC2        = lenetFC2
	LeNetP2Features = lenetC2Channels * lenetP2Side * lenetP2Side
)

func (model MLPModel) HiddenWeight(unit, pixel int) float64 {
	return model.Parameters[mlpW1Offset+unit*PixelCount+pixel]
}

func (model MLPModel) HiddenBias(unit int) float64 {
	return model.Parameters[mlpB1Offset+unit]
}

func (model MLPModel) OutputWeight(classIndex, unit int) float64 {
	return model.Parameters[mlpW2Offset+classIndex*MLPHidden+unit]
}

func (model MLPModel) OutputBias(classIndex int) float64 {
	return model.Parameters[mlpB2Offset+classIndex]
}

func (model LeNetModel) C1Weight(channel, kernelRow, kernelColumn int) float64 {
	return model.Parameters[lenetC1WOffset+(channel*lenetKernelSide+kernelRow)*lenetKernelSide+kernelColumn]
}

func (model LeNetModel) C1Bias(channel int) float64 {
	return model.Parameters[lenetC1BOffset+channel]
}

func (model LeNetModel) C2Weight(outputChannel, inputChannel, kernelRow, kernelColumn int) float64 {
	return model.Parameters[c2WeightIndex(outputChannel, inputChannel, kernelRow, kernelColumn)]
}

func (model LeNetModel) C2Bias(channel int) float64 {
	return model.Parameters[lenetC2BOffset+channel]
}

func (model LeNetModel) FC1Weight(unit, feature int) float64 {
	return model.Parameters[lenetFC1WOffset+unit*LeNetP2Features+feature]
}

func (model LeNetModel) FC1Bias(unit int) float64 {
	return model.Parameters[lenetFC1BOffset+unit]
}

func (model LeNetModel) FC2Weight(unit, input int) float64 {
	return model.Parameters[lenetFC2WOffset+unit*lenetFC1+input]
}

func (model LeNetModel) FC2Bias(unit int) float64 {
	return model.Parameters[lenetFC2BOffset+unit]
}

func (model LeNetModel) OutputWeight(classIndex, input int) float64 {
	return model.Parameters[lenetOutWOffset+classIndex*lenetFC2+input]
}

func (model LeNetModel) OutputBias(classIndex int) float64 {
	return model.Parameters[lenetOutBOffset+classIndex]
}

// PaddedPixelIndex maps a 32x32 zero-padded LeNet coordinate back to the
// original 28x28 row. False denotes a declared zero and needs no ciphertext.
func PaddedPixelIndex(paddedRow, paddedColumn int) (int, bool) {
	row := paddedRow - 2
	column := paddedColumn - 2
	if row < 0 || row >= 28 || column < 0 || column >= 28 {
		return 0, false
	}
	return row*28 + column, true
}

func LeNetP1Index(channel, row, column int) int {
	return p1Index(channel, row, column)
}

func LeNetP2Index(channel, row, column int) int {
	return p2Index(channel, row, column)
}
