package ckksbackend

import (
	"fmt"
	"math"
	"sort"
	"time"

	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// CKKSTimingBenchmarkConfig controls CKKS timing benchmark repetitions.
type CKKSTimingBenchmarkConfig struct {
	WarmupRuns      int
	MeasurementRuns int
	Input           LogRegSmallInput
}

// CKKSTimingBenchmarkRecord stores one measured CKKS encrypted inference run.
type CKKSTimingBenchmarkRecord struct {
	Run int

	EncodeEncryptMS  float64
	LinearEvalMS     float64
	PolynomialEvalMS float64
	EvalOnlyMS       float64
	DecryptDecodeMS  float64
	TotalEvalMS      float64

	PlainZ float64
	CKKSZ  float64
	ZError float64

	PlainY float64
	CKKSY  float64
	YError float64

	PlainDecision bool
	CKKSDecision  bool
	DecisionFlip  bool

	InitialLevel int
	ZLevel       int
	YLevel       int

	ZDegree int
	YDegree int
}

// CKKSTimingBenchmarkSummary stores aggregate timing statistics.
type CKKSTimingBenchmarkSummary struct {
	WarmupRuns      int
	MeasurementRuns int

	ContextSetupMS float64
	CryptoSetupMS  float64

	MeanEncodeEncryptMS  float64
	MeanLinearEvalMS     float64
	MeanPolynomialEvalMS float64
	MeanEvalOnlyMS       float64
	MeanDecryptDecodeMS  float64

	MeanTotalEvalMS   float64
	MedianTotalEvalMS float64
	P95TotalEvalMS    float64
	MinTotalEvalMS    float64
	MaxTotalEvalMS    float64

	MaxYError     float64
	MeanYError    float64
	DecisionFlips int

	InitialLevel    int
	FinalYLevel     int
	LogDefaultScale int
	MaxSlots        int
}

// DefaultCKKSTimingBenchmarkConfig returns a default timing benchmark config.
func DefaultCKKSTimingBenchmarkConfig() CKKSTimingBenchmarkConfig {
	return CKKSTimingBenchmarkConfig{
		WarmupRuns:      3,
		MeasurementRuns: 30,
		Input: LogRegSmallInput{
			X1: 0.3875,
			X2: 0,
			X3: 0,
		},
	}
}

type ckksTimingRuntime struct {
	encoder   *ckks.Encoder
	encryptor *rlwe.Encryptor
	decryptor *rlwe.Decryptor
	evaluator *ckks.Evaluator
}

// RunCKKSTimingBenchmark measures the current full CKKS logreg_small path.
func (c Context) RunCKKSTimingBenchmark(
	config CKKSTimingBenchmarkConfig,
) ([]CKKSTimingBenchmarkRecord, CKKSTimingBenchmarkSummary, error) {
	if config.WarmupRuns < 0 {
		return nil, CKKSTimingBenchmarkSummary{}, fmt.Errorf("warmup runs must be non-negative")
	}

	if config.MeasurementRuns <= 0 {
		return nil, CKKSTimingBenchmarkSummary{}, fmt.Errorf("measurement runs must be positive")
	}

	runtimeStart := time.Now()
	runtimeState, err := c.newCKKSTimingRuntime()
	if err != nil {
		return nil, CKKSTimingBenchmarkSummary{}, fmt.Errorf("create CKKS timing runtime: %w", err)
	}
	cryptoSetupMS := durationMS(time.Since(runtimeStart))

	for i := 0; i < config.WarmupRuns; i++ {
		if _, err := c.runCKKSTimedFullLogReg(runtimeState, config.Input, i); err != nil {
			return nil, CKKSTimingBenchmarkSummary{}, fmt.Errorf("warmup run %d: %w", i, err)
		}
	}

	records := make([]CKKSTimingBenchmarkRecord, 0, config.MeasurementRuns)

	for i := 0; i < config.MeasurementRuns; i++ {
		record, err := c.runCKKSTimedFullLogReg(runtimeState, config.Input, i)
		if err != nil {
			return nil, CKKSTimingBenchmarkSummary{}, fmt.Errorf("measurement run %d: %w", i, err)
		}

		records = append(records, record)
	}

	summary := summarizeCKKSTimingBenchmark(config, records)
	summary.CryptoSetupMS = cryptoSetupMS
	summary.InitialLevel = c.MaxLevel()
	summary.LogDefaultScale = c.LogDefaultScale()
	summary.MaxSlots = c.MaxSlots()

	if len(records) > 0 {
		summary.FinalYLevel = records[len(records)-1].YLevel
	}

	return records, summary, nil
}

func (c Context) newCKKSTimingRuntime() (ckksTimingRuntime, error) {
	encoder := ckks.NewEncoder(c.Params)

	kgen := ckks.NewKeyGenerator(c.Params)
	sk, pk := kgen.GenKeyPairNew()
	rlk := kgen.GenRelinearizationKeyNew(sk)

	encryptor := ckks.NewEncryptor(c.Params, pk)
	decryptor := ckks.NewDecryptor(c.Params, sk)
	evaluator := ckks.NewEvaluator(c.Params, rlwe.NewMemEvaluationKeySet(rlk))

	return ckksTimingRuntime{
		encoder:   encoder,
		encryptor: encryptor,
		decryptor: decryptor,
		evaluator: evaluator,
	}, nil
}

func (c Context) runCKKSTimedFullLogReg(
	runtimeState ckksTimingRuntime,
	input LogRegSmallInput,
	run int,
) (CKKSTimingBenchmarkRecord, error) {
	totalStart := time.Now()

	encodeEncryptStart := time.Now()

	x1, err := c.encryptReplicatedScalar(runtimeState.encoder, runtimeState.encryptor, input.X1)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("encrypt x1: %w", err)
	}

	x2, err := c.encryptReplicatedScalar(runtimeState.encoder, runtimeState.encryptor, input.X2)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("encrypt x2: %w", err)
	}

	x3, err := c.encryptReplicatedScalar(runtimeState.encoder, runtimeState.encryptor, input.X3)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("encrypt x3: %w", err)
	}

	encodeEncryptMS := durationMS(time.Since(encodeEncryptStart))

	linearStart := time.Now()

	t1, err := runtimeState.evaluator.MulNew(x1, 0.8)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("multiply x1 by 0.8: %w", err)
	}

	t2, err := runtimeState.evaluator.MulNew(x2, -0.5)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("multiply x2 by -0.5: %w", err)
	}

	t3, err := runtimeState.evaluator.MulNew(x3, 1.2)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("multiply x3 by 1.2: %w", err)
	}

	sum12, err := runtimeState.evaluator.AddNew(t1, t2)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("add t1 and t2: %w", err)
	}

	sum123, err := runtimeState.evaluator.AddNew(sum12, t3)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("add t3: %w", err)
	}

	linearBiasPlaintext, err := c.encodeReplicatedPlaintextAtLevel(runtimeState.encoder, -0.3, sum123.Level())
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("encode linear bias plaintext: %w", err)
	}

	zCipher, err := runtimeState.evaluator.AddNew(sum123, linearBiasPlaintext)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("add linear bias: %w", err)
	}

	linearEvalMS := durationMS(time.Since(linearStart))

	polynomialStart := time.Now()

	z2Cipher, err := runtimeState.evaluator.MulNew(zCipher, zCipher)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("multiply z by z: %w", err)
	}

	z2Cipher, err = runtimeState.evaluator.RelinearizeNew(z2Cipher)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("relinearize z2: %w", err)
	}

	z3Cipher, err := runtimeState.evaluator.MulNew(z2Cipher, zCipher)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("multiply z2 by z: %w", err)
	}

	z3Cipher, err = runtimeState.evaluator.RelinearizeNew(z3Cipher)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("relinearize z3: %w", err)
	}

	linearTerm, err := runtimeState.evaluator.MulNew(zCipher, 0.197)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("multiply z by 0.197: %w", err)
	}

	cubicTerm, err := runtimeState.evaluator.MulNew(z3Cipher, -0.004)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("multiply z3 by -0.004: %w", err)
	}

	sum, err := runtimeState.evaluator.AddNew(linearTerm, cubicTerm)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("add linear and cubic terms: %w", err)
	}

	polynomialBiasPlaintext, err := c.encodeReplicatedPlaintextAtLevel(runtimeState.encoder, 0.5, sum.Level())
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("encode polynomial bias plaintext: %w", err)
	}

	yCipher, err := runtimeState.evaluator.AddNew(sum, polynomialBiasPlaintext)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("add polynomial bias: %w", err)
	}

	polynomialEvalMS := durationMS(time.Since(polynomialStart))
	evalOnlyMS := linearEvalMS + polynomialEvalMS

	decryptStart := time.Now()

	zDecoded, err := c.decryptFirstSlot(runtimeState.encoder, runtimeState.decryptor, zCipher)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("decrypt z: %w", err)
	}

	yDecoded, err := c.decryptFirstSlot(runtimeState.encoder, runtimeState.decryptor, yCipher)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("decrypt y: %w", err)
	}

	decryptDecodeMS := durationMS(time.Since(decryptStart))
	totalEvalMS := durationMS(time.Since(totalStart))

	plainZ := EvalLogRegSmallLinearPlain(input)
	plainY := EvalLogRegSmallPolynomialPlain(plainZ)

	threshold := 0.5
	plainDecision := plainY >= threshold
	ckksDecision := yDecoded >= threshold

	return CKKSTimingBenchmarkRecord{
		Run: run,

		EncodeEncryptMS:  encodeEncryptMS,
		LinearEvalMS:     linearEvalMS,
		PolynomialEvalMS: polynomialEvalMS,
		EvalOnlyMS:       evalOnlyMS,
		DecryptDecodeMS:  decryptDecodeMS,
		TotalEvalMS:      totalEvalMS,

		PlainZ: plainZ,
		CKKSZ:  zDecoded,
		ZError: math.Abs(zDecoded - plainZ),

		PlainY: plainY,
		CKKSY:  yDecoded,
		YError: math.Abs(yDecoded - plainY),

		PlainDecision: plainDecision,
		CKKSDecision:  ckksDecision,
		DecisionFlip:  plainDecision != ckksDecision,

		InitialLevel: c.MaxLevel(),
		ZLevel:       zCipher.Level(),
		YLevel:       yCipher.Level(),

		ZDegree: zCipher.Degree(),
		YDegree: yCipher.Degree(),
	}, nil
}

func summarizeCKKSTimingBenchmark(
	config CKKSTimingBenchmarkConfig,
	records []CKKSTimingBenchmarkRecord,
) CKKSTimingBenchmarkSummary {
	summary := CKKSTimingBenchmarkSummary{
		WarmupRuns:      config.WarmupRuns,
		MeasurementRuns: config.MeasurementRuns,
	}

	if len(records) == 0 {
		return summary
	}

	totalValues := make([]float64, 0, len(records))

	minTotal := records[0].TotalEvalMS
	maxTotal := records[0].TotalEvalMS

	sumEncodeEncrypt := 0.0
	sumLinear := 0.0
	sumPolynomial := 0.0
	sumEvalOnly := 0.0
	sumDecrypt := 0.0
	sumTotal := 0.0
	sumYError := 0.0

	for _, record := range records {
		totalValues = append(totalValues, record.TotalEvalMS)

		sumEncodeEncrypt += record.EncodeEncryptMS
		sumLinear += record.LinearEvalMS
		sumPolynomial += record.PolynomialEvalMS
		sumEvalOnly += record.EvalOnlyMS
		sumDecrypt += record.DecryptDecodeMS
		sumTotal += record.TotalEvalMS
		sumYError += record.YError

		if record.TotalEvalMS < minTotal {
			minTotal = record.TotalEvalMS
		}

		if record.TotalEvalMS > maxTotal {
			maxTotal = record.TotalEvalMS
		}

		if record.YError > summary.MaxYError {
			summary.MaxYError = record.YError
		}

		if record.DecisionFlip {
			summary.DecisionFlips++
		}
	}

	count := float64(len(records))

	summary.MeanEncodeEncryptMS = sumEncodeEncrypt / count
	summary.MeanLinearEvalMS = sumLinear / count
	summary.MeanPolynomialEvalMS = sumPolynomial / count
	summary.MeanEvalOnlyMS = sumEvalOnly / count
	summary.MeanDecryptDecodeMS = sumDecrypt / count

	summary.MeanTotalEvalMS = sumTotal / count
	summary.MedianTotalEvalMS = timingPercentile(totalValues, 0.50)
	summary.P95TotalEvalMS = timingPercentile(totalValues, 0.95)
	summary.MinTotalEvalMS = minTotal
	summary.MaxTotalEvalMS = maxTotal

	summary.MeanYError = sumYError / count

	return summary
}

func timingPercentile(values []float64, percentile float64) float64 {
	if len(values) == 0 {
		return 0
	}

	sorted := append([]float64(nil), values...)
	sort.Float64s(sorted)

	if percentile <= 0 {
		return sorted[0]
	}

	if percentile >= 1 {
		return sorted[len(sorted)-1]
	}

	index := int(math.Ceil(percentile*float64(len(sorted)))) - 1
	if index < 0 {
		index = 0
	}

	if index >= len(sorted) {
		index = len(sorted) - 1
	}

	return sorted[index]
}

func durationMS(duration time.Duration) float64 {
	return float64(duration.Nanoseconds()) / 1e6
}
