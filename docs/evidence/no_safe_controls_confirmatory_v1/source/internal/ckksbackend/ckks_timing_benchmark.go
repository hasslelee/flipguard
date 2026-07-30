package ckksbackend

import (
	"fmt"
	"math"
	"sort"
	"time"

	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

const (
	// CKKSEvaluationModeNaive keeps the original non-rescaling evaluation path.
	CKKSEvaluationModeNaive = "naive"

	// CKKSEvaluationModeRescale uses a rescale-aware polynomial evaluation path.
	CKKSEvaluationModeRescale = "rescale"
)

// CKKSTimingBenchmarkConfig controls CKKS timing benchmark repetitions.
type CKKSTimingBenchmarkConfig struct {
	WarmupRuns      int
	MeasurementRuns int
	Input           LogRegSmallInput
	EvaluationMode  string
}

// CKKSTimingBenchmarkRecord stores one measured CKKS encrypted inference run.
type CKKSTimingBenchmarkRecord struct {
	Run            int
	EvaluationMode string

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
	EvaluationMode  string

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
		EvaluationMode:  CKKSEvaluationModeNaive,
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

type ckksTimedCipherInputs struct {
	X1 *rlwe.Ciphertext
	X2 *rlwe.Ciphertext
	X3 *rlwe.Ciphertext
}

type ckksTimedLinearResult struct {
	ZCipher      *rlwe.Ciphertext
	LinearEvalMS float64
}

type ckksTimedPolynomialResult struct {
	YCipher          *rlwe.Ciphertext
	PolynomialEvalMS float64
}

// RunCKKSTimingBenchmark measures the current full CKKS logreg_small path.
func (c Context) RunCKKSTimingBenchmark(
	config CKKSTimingBenchmarkConfig,
) (records []CKKSTimingBenchmarkRecord, summary CKKSTimingBenchmarkSummary, err error) {
	defer func() {
		if recovered := recover(); recovered != nil {
			records = nil
			summary = CKKSTimingBenchmarkSummary{}
			err = fmt.Errorf("CKKS timing benchmark panic recovered: %v", recovered)
		}
	}()

	if config.WarmupRuns < 0 {
		return nil, CKKSTimingBenchmarkSummary{}, fmt.Errorf("warmup runs must be non-negative")
	}

	if config.MeasurementRuns <= 0 {
		return nil, CKKSTimingBenchmarkSummary{}, fmt.Errorf("measurement runs must be positive")
	}

	if err := validateCKKSEvaluationMode(config.EvaluationMode); err != nil {
		return nil, CKKSTimingBenchmarkSummary{}, err
	}

	runtimeStart := time.Now()
	runtimeState, err := c.newCKKSTimingRuntime()
	if err != nil {
		return nil, CKKSTimingBenchmarkSummary{}, fmt.Errorf("create CKKS timing runtime: %w", err)
	}
	cryptoSetupMS := durationMS(time.Since(runtimeStart))

	for i := 0; i < config.WarmupRuns; i++ {
		if _, err := c.runCKKSTimedFullLogReg(runtimeState, config.Input, i, config.EvaluationMode); err != nil {
			return nil, CKKSTimingBenchmarkSummary{}, fmt.Errorf("warmup run %d: %w", i, err)
		}
	}

	records = make([]CKKSTimingBenchmarkRecord, 0, config.MeasurementRuns)

	for i := 0; i < config.MeasurementRuns; i++ {
		record, err := c.runCKKSTimedFullLogReg(runtimeState, config.Input, i, config.EvaluationMode)
		if err != nil {
			return nil, CKKSTimingBenchmarkSummary{}, fmt.Errorf("measurement run %d: %w", i, err)
		}

		records = append(records, record)
	}

	summary = summarizeCKKSTimingBenchmark(config, records)
	summary.CryptoSetupMS = cryptoSetupMS
	summary.InitialLevel = c.MaxLevel()
	summary.LogDefaultScale = c.LogDefaultScale()
	summary.MaxSlots = c.MaxSlots()

	if len(records) > 0 {
		summary.FinalYLevel = records[len(records)-1].YLevel
	}

	return records, summary, nil
}

func validateCKKSEvaluationMode(mode string) error {
	switch mode {
	case CKKSEvaluationModeNaive, CKKSEvaluationModeRescale:
		return nil
	default:
		return fmt.Errorf("unsupported CKKS evaluation mode %q", mode)
	}
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
	evaluationMode string,
) (CKKSTimingBenchmarkRecord, error) {
	totalStart := time.Now()

	encodeEncryptStart := time.Now()

	cipherInputs, err := c.encryptTimedInputs(runtimeState, input)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, err
	}

	encodeEncryptMS := durationMS(time.Since(encodeEncryptStart))

	linearResult, err := c.evalTimedLinear(runtimeState, cipherInputs)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, err
	}

	polynomialResult, err := c.evalTimedPolynomial(runtimeState, linearResult.ZCipher, evaluationMode)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, err
	}

	evalOnlyMS := linearResult.LinearEvalMS + polynomialResult.PolynomialEvalMS

	decryptStart := time.Now()

	zDecoded, err := c.decryptFirstSlot(runtimeState.encoder, runtimeState.decryptor, linearResult.ZCipher)
	if err != nil {
		return CKKSTimingBenchmarkRecord{}, fmt.Errorf("decrypt z: %w", err)
	}

	yDecoded, err := c.decryptFirstSlot(runtimeState.encoder, runtimeState.decryptor, polynomialResult.YCipher)
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
		Run:            run,
		EvaluationMode: evaluationMode,

		EncodeEncryptMS:  encodeEncryptMS,
		LinearEvalMS:     linearResult.LinearEvalMS,
		PolynomialEvalMS: polynomialResult.PolynomialEvalMS,
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
		ZLevel:       linearResult.ZCipher.Level(),
		YLevel:       polynomialResult.YCipher.Level(),

		ZDegree: linearResult.ZCipher.Degree(),
		YDegree: polynomialResult.YCipher.Degree(),
	}, nil
}

func (c Context) encryptTimedInputs(
	runtimeState ckksTimingRuntime,
	input LogRegSmallInput,
) (ckksTimedCipherInputs, error) {
	x1, err := c.encryptReplicatedScalar(runtimeState.encoder, runtimeState.encryptor, input.X1)
	if err != nil {
		return ckksTimedCipherInputs{}, fmt.Errorf("encrypt x1: %w", err)
	}

	x2, err := c.encryptReplicatedScalar(runtimeState.encoder, runtimeState.encryptor, input.X2)
	if err != nil {
		return ckksTimedCipherInputs{}, fmt.Errorf("encrypt x2: %w", err)
	}

	x3, err := c.encryptReplicatedScalar(runtimeState.encoder, runtimeState.encryptor, input.X3)
	if err != nil {
		return ckksTimedCipherInputs{}, fmt.Errorf("encrypt x3: %w", err)
	}

	return ckksTimedCipherInputs{
		X1: x1,
		X2: x2,
		X3: x3,
	}, nil
}

func (c Context) evalTimedLinear(
	runtimeState ckksTimingRuntime,
	inputs ckksTimedCipherInputs,
) (ckksTimedLinearResult, error) {
	linearStart := time.Now()

	t1, err := runtimeState.evaluator.MulNew(inputs.X1, 0.8)
	if err != nil {
		return ckksTimedLinearResult{}, fmt.Errorf("multiply x1 by 0.8: %w", err)
	}

	t2, err := runtimeState.evaluator.MulNew(inputs.X2, -0.5)
	if err != nil {
		return ckksTimedLinearResult{}, fmt.Errorf("multiply x2 by -0.5: %w", err)
	}

	t3, err := runtimeState.evaluator.MulNew(inputs.X3, 1.2)
	if err != nil {
		return ckksTimedLinearResult{}, fmt.Errorf("multiply x3 by 1.2: %w", err)
	}

	sum12, err := runtimeState.evaluator.AddNew(t1, t2)
	if err != nil {
		return ckksTimedLinearResult{}, fmt.Errorf("add t1 and t2: %w", err)
	}

	sum123, err := runtimeState.evaluator.AddNew(sum12, t3)
	if err != nil {
		return ckksTimedLinearResult{}, fmt.Errorf("add t3: %w", err)
	}

	linearBiasPlaintext, err := c.encodeReplicatedPlaintextAtLevel(runtimeState.encoder, -0.3, sum123.Level())
	if err != nil {
		return ckksTimedLinearResult{}, fmt.Errorf("encode linear bias plaintext: %w", err)
	}

	zCipher, err := runtimeState.evaluator.AddNew(sum123, linearBiasPlaintext)
	if err != nil {
		return ckksTimedLinearResult{}, fmt.Errorf("add linear bias: %w", err)
	}

	return ckksTimedLinearResult{
		ZCipher:      zCipher,
		LinearEvalMS: durationMS(time.Since(linearStart)),
	}, nil
}

func (c Context) evalTimedPolynomial(
	runtimeState ckksTimingRuntime,
	zCipher *rlwe.Ciphertext,
	evaluationMode string,
) (ckksTimedPolynomialResult, error) {
	switch evaluationMode {
	case CKKSEvaluationModeNaive:
		return c.evalTimedPolynomialNaive(runtimeState, zCipher)
	case CKKSEvaluationModeRescale:
		return c.evalTimedPolynomialRescale(runtimeState, zCipher)
	default:
		return ckksTimedPolynomialResult{}, fmt.Errorf("unsupported CKKS evaluation mode %q", evaluationMode)
	}
}

func (c Context) evalTimedPolynomialNaive(
	runtimeState ckksTimingRuntime,
	zCipher *rlwe.Ciphertext,
) (ckksTimedPolynomialResult, error) {
	polynomialStart := time.Now()

	z2Cipher, err := runtimeState.evaluator.MulNew(zCipher, zCipher)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("multiply z by z: %w", err)
	}

	z2Cipher, err = runtimeState.evaluator.RelinearizeNew(z2Cipher)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("relinearize z2: %w", err)
	}

	z3Cipher, err := runtimeState.evaluator.MulNew(z2Cipher, zCipher)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("multiply z2 by z: %w", err)
	}

	z3Cipher, err = runtimeState.evaluator.RelinearizeNew(z3Cipher)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("relinearize z3: %w", err)
	}

	linearTerm, err := runtimeState.evaluator.MulNew(zCipher, 0.197)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("multiply z by 0.197: %w", err)
	}

	cubicTerm, err := runtimeState.evaluator.MulNew(z3Cipher, -0.004)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("multiply z3 by -0.004: %w", err)
	}

	sum, err := runtimeState.evaluator.AddNew(linearTerm, cubicTerm)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("add linear and cubic terms: %w", err)
	}

	polynomialBiasPlaintext, err := c.encodeReplicatedPlaintextAtLevel(runtimeState.encoder, 0.5, sum.Level())
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("encode polynomial bias plaintext: %w", err)
	}

	yCipher, err := runtimeState.evaluator.AddNew(sum, polynomialBiasPlaintext)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("add polynomial bias: %w", err)
	}

	return ckksTimedPolynomialResult{
		YCipher:          yCipher,
		PolynomialEvalMS: durationMS(time.Since(polynomialStart)),
	}, nil
}

func (c Context) evalTimedPolynomialRescale(
	runtimeState ckksTimingRuntime,
	zCipher *rlwe.Ciphertext,
) (ckksTimedPolynomialResult, error) {
	polynomialStart := time.Now()

	z2Cipher, err := runtimeState.evaluator.MulNew(zCipher, zCipher)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("multiply z by z: %w", err)
	}

	z2Cipher, err = runtimeState.evaluator.RelinearizeNew(z2Cipher)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("relinearize z2: %w", err)
	}

	if err := safeRescaleTo(runtimeState.evaluator, z2Cipher, c.Params.DefaultScale(), z2Cipher); err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("rescale z2: %w", err)
	}

	z2Term, err := runtimeState.evaluator.MulNew(z2Cipher, -0.004)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("multiply z2 by -0.004: %w", err)
	}

	linearCoeffPlaintext, err := c.encodeReplicatedPlaintextAtLevel(runtimeState.encoder, 0.197, z2Term.Level())
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("encode linear coefficient plaintext: %w", err)
	}

	inner, err := runtimeState.evaluator.AddNew(z2Term, linearCoeffPlaintext)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("add linear coefficient: %w", err)
	}

	zAligned, err := alignCiphertextToLevel(runtimeState.evaluator, zCipher, inner.Level())
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("align z level for Horner multiply: %w", err)
	}

	yWithoutBias, err := runtimeState.evaluator.MulNew(inner, zAligned)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("multiply Horner inner by z: %w", err)
	}

	yWithoutBias, err = runtimeState.evaluator.RelinearizeNew(yWithoutBias)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("relinearize Horner output: %w", err)
	}

	if err := safeRescaleTo(runtimeState.evaluator, yWithoutBias, c.Params.DefaultScale(), yWithoutBias); err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("rescale Horner output: %w", err)
	}

	polynomialBiasPlaintext, err := c.encodeReplicatedPlaintextAtLevel(runtimeState.encoder, 0.5, yWithoutBias.Level())
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("encode polynomial bias plaintext: %w", err)
	}

	yCipher, err := runtimeState.evaluator.AddNew(yWithoutBias, polynomialBiasPlaintext)
	if err != nil {
		return ckksTimedPolynomialResult{}, fmt.Errorf("add polynomial bias: %w", err)
	}

	return ckksTimedPolynomialResult{
		YCipher:          yCipher,
		PolynomialEvalMS: durationMS(time.Since(polynomialStart)),
	}, nil
}

func safeRescaleTo(
	evaluator *ckks.Evaluator,
	ciphertext *rlwe.Ciphertext,
	scale rlwe.Scale,
	output *rlwe.Ciphertext,
) (err error) {
	if ciphertext.Level() <= 0 {
		return fmt.Errorf("cannot rescale ciphertext at level %d", ciphertext.Level())
	}

	defer func() {
		if recovered := recover(); recovered != nil {
			err = fmt.Errorf("rescale panic recovered: %v", recovered)
		}
	}()

	return evaluator.RescaleTo(ciphertext, scale, output)
}

func alignCiphertextToLevel(
	evaluator *ckks.Evaluator,
	ciphertext *rlwe.Ciphertext,
	targetLevel int,
) (*rlwe.Ciphertext, error) {
	currentLevel := ciphertext.Level()

	if currentLevel == targetLevel {
		return ciphertext, nil
	}

	if currentLevel < targetLevel {
		return nil, fmt.Errorf("ciphertext level %d is below target level %d", currentLevel, targetLevel)
	}

	return evaluator.DropLevelNew(ciphertext, currentLevel-targetLevel), nil
}

func summarizeCKKSTimingBenchmark(
	config CKKSTimingBenchmarkConfig,
	records []CKKSTimingBenchmarkRecord,
) CKKSTimingBenchmarkSummary {
	summary := CKKSTimingBenchmarkSummary{
		WarmupRuns:      config.WarmupRuns,
		MeasurementRuns: config.MeasurementRuns,
		EvaluationMode:  config.EvaluationMode,
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
