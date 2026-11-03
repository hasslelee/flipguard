package journalmnist

import "math"

type splitMix64 struct {
	state uint64
}

func (random *splitMix64) next() uint64 {
	random.state += 0x9e3779b97f4a7c15
	value := random.state
	value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9
	value = (value ^ (value >> 27)) * 0x94d049bb133111eb
	return value ^ (value >> 31)
}

func (random *splitMix64) uniform() float64 {
	return float64(random.next()>>11) * (1.0 / (1 << 53))
}

func (random *splitMix64) shuffle(values []int) {
	for index := len(values) - 1; index > 0; index-- {
		other := int(random.next() % uint64(index+1))
		values[index], values[other] = values[other], values[index]
	}
}

type adamOptimizer struct {
	m           []float64
	v           []float64
	step        int
	beta1       float64
	beta2       float64
	epsilon     float64
	weightDecay float64
	weightMask  []bool
}

func newAdam(size int, weightMask []bool, weightDecay float64) *adamOptimizer {
	return &adamOptimizer{
		m:           make([]float64, size),
		v:           make([]float64, size),
		beta1:       0.9,
		beta2:       0.999,
		epsilon:     1e-8,
		weightDecay: weightDecay,
		weightMask:  append([]bool(nil), weightMask...),
	}
}

func (optimizer *adamOptimizer) update(
	parameters []float64,
	gradient []float64,
	learningRate float64,
	batchSize int,
) {
	optimizer.step++
	invBatch := 1 / float64(batchSize)
	// A deterministic global-norm clip prevents a single square-activation
	// batch from making the fixed protocol numerically non-finite.
	normSquared := 0.0
	for index, value := range gradient {
		value *= invBatch
		if optimizer.weightMask[index] {
			value += optimizer.weightDecay * parameters[index]
		}
		gradient[index] = value
		normSquared += value * value
	}
	scale := 1.0
	if norm := math.Sqrt(normSquared); norm > 5 {
		scale = 5 / norm
	}
	beta1Power := math.Pow(optimizer.beta1, float64(optimizer.step))
	beta2Power := math.Pow(optimizer.beta2, float64(optimizer.step))
	for index, value := range gradient {
		value *= scale
		optimizer.m[index] = optimizer.beta1*optimizer.m[index] +
			(1-optimizer.beta1)*value
		optimizer.v[index] = optimizer.beta2*optimizer.v[index] +
			(1-optimizer.beta2)*value*value
		mHat := optimizer.m[index] / (1 - beta1Power)
		vHat := optimizer.v[index] / (1 - beta2Power)
		parameters[index] -= learningRate * mHat /
			(math.Sqrt(vHat) + optimizer.epsilon)
	}
}

func softmaxCrossEntropy(logits []float64, label int, gradient []float64) float64 {
	maximum := logits[0]
	for _, value := range logits[1:] {
		maximum = math.Max(maximum, value)
	}
	total := 0.0
	for index, value := range logits {
		gradient[index] = math.Exp(value - maximum)
		total += gradient[index]
	}
	for index := range gradient {
		gradient[index] /= total
	}
	loss := -math.Log(math.Max(gradient[label], 1e-300))
	gradient[label]--
	return loss
}

func argmax(values []float64) int {
	best := 0
	for index := 1; index < len(values); index++ {
		if values[index] > values[best] {
			best = index
		}
	}
	return best
}
