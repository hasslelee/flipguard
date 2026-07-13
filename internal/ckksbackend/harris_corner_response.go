package ckksbackend

import (
	"fmt"
	"math"

	"github.com/hasslelee/flipguard/internal/benchmarks"
	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// HarrisCornerProbeCase defines one encrypted 5x5 Harris corner-response probe.
type HarrisCornerProbeCase struct {
	Pixels [5][5]float64
}

// HarrisCornerProbeResult records encrypted evaluation behavior for:
//
// Sxx = sum Ix^2
// Syy = sum Iy^2
// Sxy = sum Ix*Iy
// score = Sxx*Syy - Sxy^2 - k*(Sxx+Syy)^2
//
// The ciphertext operations relinearize after ciphertext-ciphertext
// multiplications. Therefore the recorded ciphertext degree is the post-
// relinearization degree, while LogicalDegree records the plaintext polynomial
// degree of the Harris response.
type HarrisCornerProbeResult struct {
	Pixels [5][5]float64

	Threshold float64
	K         float64

	PlainSXX   float64
	PlainSYY   float64
	PlainSXY   float64
	PlainDet   float64
	PlainTrace float64
	PlainScore float64

	CKKSSXX   float64
	CKKSSYY   float64
	CKKSSXY   float64
	CKKSDet   float64
	CKKSTrace float64
	CKKSScore float64

	AbsError float64

	PlainDecision bool
	CKKSDecision  bool
	Flip          bool

	InitialLevel int
	SXXLevel     int
	SYYLevel     int
	SXYLevel     int
	DetLevel     int
	TraceLevel   int
	ScoreLevel   int

	SXXDegree   int
	SYYDegree   int
	SXYDegree   int
	DetDegree   int
	TraceDegree int
	ScoreDegree int

	LogicalDegree int

	LogDefaultScale int
}

type harrisCornerCipherResult struct {
	SXX   *rlwe.Ciphertext
	SYY   *rlwe.Ciphertext
	SXY   *rlwe.Ciphertext
	Det   *rlwe.Ciphertext
	Trace *rlwe.Ciphertext
	Score *rlwe.Ciphertext
}

// DefaultHarrisCornerProbeCases returns deterministic non-exact-boundary 5x5
// Harris windows for CKKS evaluation.
//
// The set includes flat/non-corner windows, pure edge windows, and corner-like
// windows with large decision margins. Near-threshold window generation remains
// available in the benchmarks package for later decision-stability experiments.
func DefaultHarrisCornerProbeCases() []HarrisCornerProbeCase {
	samples := benchmarks.DefaultHarrisCornerSamples()

	// The current benchmark sample order is:
	//   0: flat zero
	//   1: flat one
	//   2: vertical edge
	//   3: horizontal edge
	//   4: lower-right corner
	//   8: scaled lower-right corner, 0.75
	//   9: scaled lower-right corner, 1.25
	//
	// These cases avoid exact threshold equality for the default threshold.
	indices := []int{0, 1, 2, 3, 4, 8, 9}

	cases := make([]HarrisCornerProbeCase, 0, len(indices))
	for _, index := range indices {
		if index >= len(samples) {
			continue
		}

		cases = append(cases, HarrisCornerProbeCase{
			Pixels: samples[index].Pixels,
		})
	}

	return cases
}

// RunHarrisCornerProbe executes all default encrypted Harris corner-response
// probe cases.
func (c Context) RunHarrisCornerProbe() ([]HarrisCornerProbeResult, error) {
	cases := DefaultHarrisCornerProbeCases()
	results := make([]HarrisCornerProbeResult, 0, len(cases))

	for i, probeCase := range cases {
		result, err := c.RunHarrisCornerProbeCase(probeCase)
		if err != nil {
			return nil, fmt.Errorf("run Harris corner probe case %d: %w", i, err)
		}

		results = append(results, result)
	}

	return results, nil
}

// RunHarrisCornerProbeCase evaluates the windowed Harris response using CKKS.
func (c Context) RunHarrisCornerProbeCase(
	probeCase HarrisCornerProbeCase,
) (HarrisCornerProbeResult, error) {
	encoder := ckks.NewEncoder(c.Params)

	kgen := ckks.NewKeyGenerator(c.Params)
	sk, pk := kgen.GenKeyPairNew()
	rlk := kgen.GenRelinearizationKeyNew(sk)

	encryptor := ckks.NewEncryptor(c.Params, pk)
	decryptor := ckks.NewDecryptor(c.Params, sk)

	evaluator := ckks.NewEvaluator(c.Params, rlwe.NewMemEvaluationKeySet(rlk))

	pixelCiphers, err := c.encryptHarrisCornerPixels(encoder, encryptor, probeCase)
	if err != nil {
		return HarrisCornerProbeResult{}, err
	}

	cipherResult, err := evalHarrisCornerResponseCipher(evaluator, pixelCiphers)
	if err != nil {
		return HarrisCornerProbeResult{}, fmt.Errorf("evaluate encrypted Harris response: %w", err)
	}

	sxxDecoded, err := c.decryptFirstSlot(encoder, decryptor, cipherResult.SXX)
	if err != nil {
		return HarrisCornerProbeResult{}, fmt.Errorf("decrypt Sxx: %w", err)
	}

	syyDecoded, err := c.decryptFirstSlot(encoder, decryptor, cipherResult.SYY)
	if err != nil {
		return HarrisCornerProbeResult{}, fmt.Errorf("decrypt Syy: %w", err)
	}

	sxyDecoded, err := c.decryptFirstSlot(encoder, decryptor, cipherResult.SXY)
	if err != nil {
		return HarrisCornerProbeResult{}, fmt.Errorf("decrypt Sxy: %w", err)
	}

	detDecoded, err := c.decryptFirstSlot(encoder, decryptor, cipherResult.Det)
	if err != nil {
		return HarrisCornerProbeResult{}, fmt.Errorf("decrypt det: %w", err)
	}

	traceDecoded, err := c.decryptFirstSlot(encoder, decryptor, cipherResult.Trace)
	if err != nil {
		return HarrisCornerProbeResult{}, fmt.Errorf("decrypt trace: %w", err)
	}

	scoreDecoded, err := c.decryptFirstSlot(encoder, decryptor, cipherResult.Score)
	if err != nil {
		return HarrisCornerProbeResult{}, fmt.Errorf("decrypt score: %w", err)
	}

	plainSample := benchmarks.HarrisCornerWindowSample{
		Pixels: probeCase.Pixels,
	}
	plainResponse := benchmarks.HarrisCornerResponse(plainSample)

	threshold := benchmarks.HarrisCornerThreshold
	plainDecision := plainResponse.Score >= threshold
	ckksDecision := scoreDecoded >= threshold

	return HarrisCornerProbeResult{
		Pixels: probeCase.Pixels,

		Threshold: threshold,
		K:         benchmarks.HarrisCornerK,

		PlainSXX:   plainResponse.SXX,
		PlainSYY:   plainResponse.SYY,
		PlainSXY:   plainResponse.SXY,
		PlainDet:   plainResponse.Det,
		PlainTrace: plainResponse.Trace,
		PlainScore: plainResponse.Score,

		CKKSSXX:   sxxDecoded,
		CKKSSYY:   syyDecoded,
		CKKSSXY:   sxyDecoded,
		CKKSDet:   detDecoded,
		CKKSTrace: traceDecoded,
		CKKSScore: scoreDecoded,

		AbsError: math.Abs(scoreDecoded - plainResponse.Score),

		PlainDecision: plainDecision,
		CKKSDecision:  ckksDecision,
		Flip:          plainDecision != ckksDecision,

		InitialLevel: c.MaxLevel(),
		SXXLevel:     cipherResult.SXX.Level(),
		SYYLevel:     cipherResult.SYY.Level(),
		SXYLevel:     cipherResult.SXY.Level(),
		DetLevel:     cipherResult.Det.Level(),
		TraceLevel:   cipherResult.Trace.Level(),
		ScoreLevel:   cipherResult.Score.Level(),

		SXXDegree:   cipherResult.SXX.Degree(),
		SYYDegree:   cipherResult.SYY.Degree(),
		SXYDegree:   cipherResult.SXY.Degree(),
		DetDegree:   cipherResult.Det.Degree(),
		TraceDegree: cipherResult.Trace.Degree(),
		ScoreDegree: cipherResult.Score.Degree(),

		LogicalDegree: 4,

		LogDefaultScale: c.LogDefaultScale(),
	}, nil
}

func (c Context) encryptHarrisCornerPixels(
	encoder *ckks.Encoder,
	encryptor *rlwe.Encryptor,
	probeCase HarrisCornerProbeCase,
) ([5][5]*rlwe.Ciphertext, error) {
	var pixelCiphers [5][5]*rlwe.Ciphertext

	for r := 0; r < 5; r++ {
		for col := 0; col < 5; col++ {
			cipher, err := c.encryptReplicatedScalar(
				encoder,
				encryptor,
				probeCase.Pixels[r][col],
			)
			if err != nil {
				return pixelCiphers, fmt.Errorf("encrypt p%d%d: %w", r, col, err)
			}

			pixelCiphers[r][col] = cipher
		}
	}

	return pixelCiphers, nil
}

func evalHarrisCornerResponseCipher(
	evaluator *ckks.Evaluator,
	pixels [5][5]*rlwe.Ciphertext,
) (harrisCornerCipherResult, error) {
	sxxTerms := make([]*rlwe.Ciphertext, 0, 9)
	syyTerms := make([]*rlwe.Ciphertext, 0, 9)
	sxyTerms := make([]*rlwe.Ciphertext, 0, 9)

	for r := 1; r <= 3; r++ {
		for c := 1; c <= 3; c++ {
			gxCipher, err := evalSobelGX(
				evaluator,
				pixels[r-1][c-1],
				pixels[r-1][c+1],
				pixels[r][c-1],
				pixels[r][c+1],
				pixels[r+1][c-1],
				pixels[r+1][c+1],
			)
			if err != nil {
				return harrisCornerCipherResult{}, fmt.Errorf("evaluate gx at %d,%d: %w", r, c, err)
			}

			gyCipher, err := evalSobelGY(
				evaluator,
				pixels[r-1][c-1],
				pixels[r-1][c],
				pixels[r-1][c+1],
				pixels[r+1][c-1],
				pixels[r+1][c],
				pixels[r+1][c+1],
			)
			if err != nil {
				return harrisCornerCipherResult{}, fmt.Errorf("evaluate gy at %d,%d: %w", r, c, err)
			}

			gx2Cipher, err := harrisMulRelin(evaluator, gxCipher, gxCipher)
			if err != nil {
				return harrisCornerCipherResult{}, fmt.Errorf("square gx at %d,%d: %w", r, c, err)
			}

			gy2Cipher, err := harrisMulRelin(evaluator, gyCipher, gyCipher)
			if err != nil {
				return harrisCornerCipherResult{}, fmt.Errorf("square gy at %d,%d: %w", r, c, err)
			}

			gxyCipher, err := harrisMulRelin(evaluator, gxCipher, gyCipher)
			if err != nil {
				return harrisCornerCipherResult{}, fmt.Errorf("multiply gx gy at %d,%d: %w", r, c, err)
			}

			sxxTerms = append(sxxTerms, gx2Cipher)
			syyTerms = append(syyTerms, gy2Cipher)
			sxyTerms = append(sxyTerms, gxyCipher)
		}
	}

	sxxCipher, err := harrisAddCipherChain(evaluator, sxxTerms)
	if err != nil {
		return harrisCornerCipherResult{}, fmt.Errorf("accumulate Sxx: %w", err)
	}

	syyCipher, err := harrisAddCipherChain(evaluator, syyTerms)
	if err != nil {
		return harrisCornerCipherResult{}, fmt.Errorf("accumulate Syy: %w", err)
	}

	sxyCipher, err := harrisAddCipherChain(evaluator, sxyTerms)
	if err != nil {
		return harrisCornerCipherResult{}, fmt.Errorf("accumulate Sxy: %w", err)
	}

	detPositiveCipher, err := harrisMulRelin(evaluator, sxxCipher, syyCipher)
	if err != nil {
		return harrisCornerCipherResult{}, fmt.Errorf("multiply Sxx Syy: %w", err)
	}

	sxy2Cipher, err := harrisMulRelin(evaluator, sxyCipher, sxyCipher)
	if err != nil {
		return harrisCornerCipherResult{}, fmt.Errorf("square Sxy: %w", err)
	}

	negativeSxy2Cipher, err := evaluator.MulNew(sxy2Cipher, -1.0)
	if err != nil {
		return harrisCornerCipherResult{}, fmt.Errorf("negate Sxy^2: %w", err)
	}

	detCipher, err := evaluator.AddNew(detPositiveCipher, negativeSxy2Cipher)
	if err != nil {
		return harrisCornerCipherResult{}, fmt.Errorf("compute determinant: %w", err)
	}

	traceCipher, err := evaluator.AddNew(sxxCipher, syyCipher)
	if err != nil {
		return harrisCornerCipherResult{}, fmt.Errorf("compute trace: %w", err)
	}

	trace2Cipher, err := harrisMulRelin(evaluator, traceCipher, traceCipher)
	if err != nil {
		return harrisCornerCipherResult{}, fmt.Errorf("square trace: %w", err)
	}

	negativeKTrace2Cipher, err := evaluator.MulNew(trace2Cipher, -benchmarks.HarrisCornerK)
	if err != nil {
		return harrisCornerCipherResult{}, fmt.Errorf("multiply trace^2 by -k: %w", err)
	}

	scoreCipher, err := evaluator.AddNew(detCipher, negativeKTrace2Cipher)
	if err != nil {
		return harrisCornerCipherResult{}, fmt.Errorf("compute Harris score: %w", err)
	}

	return harrisCornerCipherResult{
		SXX:   sxxCipher,
		SYY:   syyCipher,
		SXY:   sxyCipher,
		Det:   detCipher,
		Trace: traceCipher,
		Score: scoreCipher,
	}, nil
}

func harrisMulRelin(
	evaluator *ckks.Evaluator,
	left *rlwe.Ciphertext,
	right *rlwe.Ciphertext,
) (*rlwe.Ciphertext, error) {
	out, err := evaluator.MulNew(left, right)
	if err != nil {
		return nil, err
	}

	out, err = evaluator.RelinearizeNew(out)
	if err != nil {
		return nil, err
	}

	return out, nil
}

func harrisAddCipherChain(
	evaluator *ckks.Evaluator,
	terms []*rlwe.Ciphertext,
) (*rlwe.Ciphertext, error) {
	if len(terms) == 0 {
		return nil, fmt.Errorf("cannot add empty ciphertext chain")
	}

	current := terms[0]

	for i := 1; i < len(terms); i++ {
		next, err := evaluator.AddNew(current, terms[i])
		if err != nil {
			return nil, fmt.Errorf("add term %d: %w", i, err)
		}

		current = next
	}

	return current, nil
}
