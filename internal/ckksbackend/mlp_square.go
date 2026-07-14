package ckksbackend

import (
	"fmt"
	"math"

	"github.com/hasslelee/flipguard/internal/benchmarks"
	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// MLPSquareProbeCase defines one encrypted four-dimensional MLP-square input.
type MLPSquareProbeCase struct {
	X1 float64
	X2 float64
	X3 float64
	X4 float64
}

// MLPSquareProbeResult records encrypted evaluation behavior for:
//
//	h = W1*x + b1
//	a = h^2
//	y = W2*a + b2
//
// The ciphertext operations relinearize after ciphertext-ciphertext
// multiplications. Therefore the recorded ciphertext degree is the post-
// relinearization degree, while LogicalDegree records the plaintext polynomial
// degree of the square-activation MLP score.
type MLPSquareProbeResult struct {
	X1 float64
	X2 float64
	X3 float64
	X4 float64

	Threshold float64

	PlainScore float64
	CKKSScore  float64

	AbsError float64

	PlainDecision bool
	CKKSDecision  bool
	Flip          bool

	H1Value float64
	H2Value float64
	H3Value float64

	A1Value float64
	A2Value float64
	A3Value float64

	G1Value float64
	G2Value float64

	U1Value float64
	U2Value float64

	InitialLevel int
	H1Level      int
	H2Level      int
	H3Level      int
	A1Level      int
	A2Level      int
	A3Level      int
	G1Level      int
	G2Level      int
	U1Level      int
	U2Level      int
	ScoreLevel   int

	H1Degree    int
	H2Degree    int
	H3Degree    int
	A1Degree    int
	A2Degree    int
	A3Degree    int
	G1Degree    int
	G2Degree    int
	U1Degree    int
	U2Degree    int
	ScoreDegree int

	LogicalDegree int

	LogDefaultScale int
}

type mlpSquareCipherInputs struct {
	X1 *rlwe.Ciphertext
	X2 *rlwe.Ciphertext
	X3 *rlwe.Ciphertext
	X4 *rlwe.Ciphertext
}

type mlpSquareCipherResult struct {
	H1    *rlwe.Ciphertext
	H2    *rlwe.Ciphertext
	H3    *rlwe.Ciphertext
	A1    *rlwe.Ciphertext
	A2    *rlwe.Ciphertext
	A3    *rlwe.Ciphertext
	G1    *rlwe.Ciphertext
	G2    *rlwe.Ciphertext
	U1    *rlwe.Ciphertext
	U2    *rlwe.Ciphertext
	Score *rlwe.Ciphertext
}

// DefaultMLPSquareProbeCases returns deterministic non-exact-boundary samples
// for CKKS evaluation. The set includes both threshold-positive and
// threshold-negative decisions.
func DefaultMLPSquareProbeCases() []MLPSquareProbeCase {
	return []MLPSquareProbeCase{
		{X1: 0.0, X2: 0.0, X3: 0.0, X4: 0.0},
		{X1: 1.0, X2: 0.0, X3: 0.0, X4: 0.0},
		{X1: 0.0, X2: 1.0, X3: 0.0, X4: 0.0},
		{X1: 0.0, X2: 0.0, X3: 1.0, X4: 0.0},
		{X1: 1.0, X2: -1.0, X3: 1.0, X4: -1.0},
		{X1: -1.0, X2: 1.0, X3: -1.0, X4: 1.0},
		{X1: 1.0, X2: 1.0, X3: 1.0, X4: 1.0},
		{X1: -1.0, X2: -1.0, X3: -1.0, X4: -1.0},
	}
}

// RunMLPSquareProbe executes all default encrypted MLP-square probe cases.
func (c Context) RunMLPSquareProbe() ([]MLPSquareProbeResult, error) {
	cases := DefaultMLPSquareProbeCases()
	results := make([]MLPSquareProbeResult, 0, len(cases))

	for i, probeCase := range cases {
		result, err := c.RunMLPSquareProbeCase(probeCase)
		if err != nil {
			return nil, fmt.Errorf("run MLP-square probe case %d: %w", i, err)
		}

		results = append(results, result)
	}

	return results, nil
}

// RunMLPSquareProbeCase evaluates the fixed square-activation MLP using CKKS.
func (c Context) RunMLPSquareProbeCase(
	probeCase MLPSquareProbeCase,
) (MLPSquareProbeResult, error) {
	encoder := ckks.NewEncoder(c.Params)

	kgen := ckks.NewKeyGenerator(c.Params)
	sk, pk := kgen.GenKeyPairNew()
	rlk := kgen.GenRelinearizationKeyNew(sk)

	encryptor := ckks.NewEncryptor(c.Params, pk)
	decryptor := ckks.NewDecryptor(c.Params, sk)

	evaluator := ckks.NewEvaluator(c.Params, rlwe.NewMemEvaluationKeySet(rlk))

	inputs, err := c.encryptMLPSquareInputs(encoder, encryptor, probeCase)
	if err != nil {
		return MLPSquareProbeResult{}, err
	}

	cipherResult, err := c.evalMLPSquareCipher(encoder, evaluator, inputs)
	if err != nil {
		return MLPSquareProbeResult{}, fmt.Errorf("evaluate encrypted MLP-square: %w", err)
	}

	h1Decoded, err := c.decryptFirstSlot(encoder, decryptor, cipherResult.H1)
	if err != nil {
		return MLPSquareProbeResult{}, fmt.Errorf("decrypt h1: %w", err)
	}

	h2Decoded, err := c.decryptFirstSlot(encoder, decryptor, cipherResult.H2)
	if err != nil {
		return MLPSquareProbeResult{}, fmt.Errorf("decrypt h2: %w", err)
	}

	h3Decoded, err := c.decryptFirstSlot(encoder, decryptor, cipherResult.H3)
	if err != nil {
		return MLPSquareProbeResult{}, fmt.Errorf("decrypt h3: %w", err)
	}

	a1Decoded, err := c.decryptFirstSlot(encoder, decryptor, cipherResult.A1)
	if err != nil {
		return MLPSquareProbeResult{}, fmt.Errorf("decrypt a1: %w", err)
	}

	a2Decoded, err := c.decryptFirstSlot(encoder, decryptor, cipherResult.A2)
	if err != nil {
		return MLPSquareProbeResult{}, fmt.Errorf("decrypt a2: %w", err)
	}

	a3Decoded, err := c.decryptFirstSlot(encoder, decryptor, cipherResult.A3)
	if err != nil {
		return MLPSquareProbeResult{}, fmt.Errorf("decrypt a3: %w", err)
	}

	g1Decoded, err := c.decryptFirstSlot(encoder, decryptor, cipherResult.G1)
	if err != nil {
		return MLPSquareProbeResult{}, fmt.Errorf("decrypt g1: %w", err)
	}

	g2Decoded, err := c.decryptFirstSlot(encoder, decryptor, cipherResult.G2)
	if err != nil {
		return MLPSquareProbeResult{}, fmt.Errorf("decrypt g2: %w", err)
	}

	u1Decoded, err := c.decryptFirstSlot(encoder, decryptor, cipherResult.U1)
	if err != nil {
		return MLPSquareProbeResult{}, fmt.Errorf("decrypt u1: %w", err)
	}

	u2Decoded, err := c.decryptFirstSlot(encoder, decryptor, cipherResult.U2)
	if err != nil {
		return MLPSquareProbeResult{}, fmt.Errorf("decrypt u2: %w", err)
	}

	scoreDecoded, err := c.decryptFirstSlot(encoder, decryptor, cipherResult.Score)
	if err != nil {
		return MLPSquareProbeResult{}, fmt.Errorf("decrypt score: %w", err)
	}

	plainSample := benchmarks.MLPSquareSample{
		X1: probeCase.X1,
		X2: probeCase.X2,
		X3: probeCase.X3,
		X4: probeCase.X4,
	}

	plainScore := benchmarks.MLPSquareScore(plainSample)
	threshold := benchmarks.MLPSquareThreshold

	plainDecision := plainScore >= threshold
	ckksDecision := scoreDecoded >= threshold

	return MLPSquareProbeResult{
		X1: probeCase.X1,
		X2: probeCase.X2,
		X3: probeCase.X3,
		X4: probeCase.X4,

		Threshold: threshold,

		PlainScore: plainScore,
		CKKSScore:  scoreDecoded,

		AbsError: math.Abs(scoreDecoded - plainScore),

		PlainDecision: plainDecision,
		CKKSDecision:  ckksDecision,
		Flip:          plainDecision != ckksDecision,

		H1Value: h1Decoded,
		H2Value: h2Decoded,
		H3Value: h3Decoded,

		A1Value: a1Decoded,
		A2Value: a2Decoded,
		A3Value: a3Decoded,

		G1Value: g1Decoded,
		G2Value: g2Decoded,

		U1Value: u1Decoded,
		U2Value: u2Decoded,

		InitialLevel: c.MaxLevel(),
		H1Level:      cipherResult.H1.Level(),
		H2Level:      cipherResult.H2.Level(),
		H3Level:      cipherResult.H3.Level(),
		A1Level:      cipherResult.A1.Level(),
		A2Level:      cipherResult.A2.Level(),
		A3Level:      cipherResult.A3.Level(),
		G1Level:      cipherResult.G1.Level(),
		G2Level:      cipherResult.G2.Level(),
		U1Level:      cipherResult.U1.Level(),
		U2Level:      cipherResult.U2.Level(),
		ScoreLevel:   cipherResult.Score.Level(),

		H1Degree:    cipherResult.H1.Degree(),
		H2Degree:    cipherResult.H2.Degree(),
		H3Degree:    cipherResult.H3.Degree(),
		A1Degree:    cipherResult.A1.Degree(),
		A2Degree:    cipherResult.A2.Degree(),
		A3Degree:    cipherResult.A3.Degree(),
		G1Degree:    cipherResult.G1.Degree(),
		G2Degree:    cipherResult.G2.Degree(),
		U1Degree:    cipherResult.U1.Degree(),
		U2Degree:    cipherResult.U2.Degree(),
		ScoreDegree: cipherResult.Score.Degree(),

		LogicalDegree: 2,

		LogDefaultScale: c.LogDefaultScale(),
	}, nil
}

func (c Context) encryptMLPSquareInputs(
	encoder *ckks.Encoder,
	encryptor *rlwe.Encryptor,
	probeCase MLPSquareProbeCase,
) (mlpSquareCipherInputs, error) {
	x1Cipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.X1)
	if err != nil {
		return mlpSquareCipherInputs{}, fmt.Errorf("encrypt x1: %w", err)
	}

	x2Cipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.X2)
	if err != nil {
		return mlpSquareCipherInputs{}, fmt.Errorf("encrypt x2: %w", err)
	}

	x3Cipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.X3)
	if err != nil {
		return mlpSquareCipherInputs{}, fmt.Errorf("encrypt x3: %w", err)
	}

	x4Cipher, err := c.encryptReplicatedScalar(encoder, encryptor, probeCase.X4)
	if err != nil {
		return mlpSquareCipherInputs{}, fmt.Errorf("encrypt x4: %w", err)
	}

	return mlpSquareCipherInputs{
		X1: x1Cipher,
		X2: x2Cipher,
		X3: x3Cipher,
		X4: x4Cipher,
	}, nil
}

func (c Context) evalMLPSquareCipher(
	encoder *ckks.Encoder,
	evaluator *ckks.Evaluator,
	inputs mlpSquareCipherInputs,
) (mlpSquareCipherResult, error) {
	h1Cipher, err := c.mlpSquareAffine4(
		encoder,
		evaluator,
		"h1",
		inputs,
		[4]float64{0.65, -0.35, 0.20, 0.10},
		0.10,
	)
	if err != nil {
		return mlpSquareCipherResult{}, fmt.Errorf("evaluate h1: %w", err)
	}

	h2Cipher, err := c.mlpSquareAffine4(
		encoder,
		evaluator,
		"h2",
		inputs,
		[4]float64{-0.20, 0.55, -0.15, 0.25},
		-0.05,
	)
	if err != nil {
		return mlpSquareCipherResult{}, fmt.Errorf("evaluate h2: %w", err)
	}

	h3Cipher, err := c.mlpSquareAffine4(
		encoder,
		evaluator,
		"h3",
		inputs,
		[4]float64{0.30, 0.10, 0.50, -0.40},
		0.00,
	)
	if err != nil {
		return mlpSquareCipherResult{}, fmt.Errorf("evaluate h3: %w", err)
	}

	a1Cipher, err := c.mlpSquareMulRelinRescale(evaluator, h1Cipher, h1Cipher)
	if err != nil {
		return mlpSquareCipherResult{}, fmt.Errorf("square h1: %w", err)
	}

	a2Cipher, err := c.mlpSquareMulRelinRescale(evaluator, h2Cipher, h2Cipher)
	if err != nil {
		return mlpSquareCipherResult{}, fmt.Errorf("square h2: %w", err)
	}

	a3Cipher, err := c.mlpSquareMulRelinRescale(evaluator, h3Cipher, h3Cipher)
	if err != nil {
		return mlpSquareCipherResult{}, fmt.Errorf("square h3: %w", err)
	}

	scoreCipher, err := c.mlpSquareAffine3(
		encoder,
		evaluator,
		"score",
		a1Cipher,
		a2Cipher,
		a3Cipher,
		[3]float64{0.70, -0.30, 0.20},
		-0.10,
	)
	if err != nil {
		return mlpSquareCipherResult{}, fmt.Errorf("evaluate score: %w", err)
	}

	return mlpSquareCipherResult{
		H1:    h1Cipher,
		H2:    h2Cipher,
		H3:    h3Cipher,
		A1:    a1Cipher,
		A2:    a2Cipher,
		A3:    a3Cipher,
		G1:    scoreCipher,
		G2:    scoreCipher,
		U1:    scoreCipher,
		U2:    scoreCipher,
		Score: scoreCipher,
	}, nil
}

func (c Context) mlpSquareAffine4(
	encoder *ckks.Encoder,
	evaluator *ckks.Evaluator,
	name string,
	inputs mlpSquareCipherInputs,
	weights [4]float64,
	bias float64,
) (*rlwe.Ciphertext, error) {
	t1, err := evaluator.MulNew(inputs.X1, weights[0])
	if err != nil {
		return nil, fmt.Errorf("%s multiply x1: %w", name, err)
	}

	t2, err := evaluator.MulNew(inputs.X2, weights[1])
	if err != nil {
		return nil, fmt.Errorf("%s multiply x2: %w", name, err)
	}

	t3, err := evaluator.MulNew(inputs.X3, weights[2])
	if err != nil {
		return nil, fmt.Errorf("%s multiply x3: %w", name, err)
	}

	t4, err := evaluator.MulNew(inputs.X4, weights[3])
	if err != nil {
		return nil, fmt.Errorf("%s multiply x4: %w", name, err)
	}

	sum12, err := evaluator.AddNew(t1, t2)
	if err != nil {
		return nil, fmt.Errorf("%s add t1 t2: %w", name, err)
	}

	sum123, err := evaluator.AddNew(sum12, t3)
	if err != nil {
		return nil, fmt.Errorf("%s add t3: %w", name, err)
	}

	sum1234, err := evaluator.AddNew(sum123, t4)
	if err != nil {
		return nil, fmt.Errorf("%s add t4: %w", name, err)
	}

	biasPlaintext, err := c.encodeReplicatedPlaintextAtLevel(encoder, bias, sum1234.Level())
	if err != nil {
		return nil, fmt.Errorf("%s encode bias: %w", name, err)
	}

	out, err := evaluator.AddNew(sum1234, biasPlaintext)
	if err != nil {
		return nil, fmt.Errorf("%s add bias: %w", name, err)
	}

	return out, nil
}

func (c Context) mlpSquareAffine3(
	encoder *ckks.Encoder,
	evaluator *ckks.Evaluator,
	name string,
	a1 *rlwe.Ciphertext,
	a2 *rlwe.Ciphertext,
	a3 *rlwe.Ciphertext,
	weights [3]float64,
	bias float64,
) (*rlwe.Ciphertext, error) {
	t1, err := evaluator.MulNew(a1, weights[0])
	if err != nil {
		return nil, fmt.Errorf("%s multiply a1: %w", name, err)
	}

	t2, err := evaluator.MulNew(a2, weights[1])
	if err != nil {
		return nil, fmt.Errorf("%s multiply a2: %w", name, err)
	}

	t3, err := evaluator.MulNew(a3, weights[2])
	if err != nil {
		return nil, fmt.Errorf("%s multiply a3: %w", name, err)
	}

	sum12, err := evaluator.AddNew(t1, t2)
	if err != nil {
		return nil, fmt.Errorf("%s add t1 t2: %w", name, err)
	}

	sum123, err := evaluator.AddNew(sum12, t3)
	if err != nil {
		return nil, fmt.Errorf("%s add t3: %w", name, err)
	}

	biasPlaintext, err := c.encodeReplicatedPlaintextAtLevel(encoder, bias, sum123.Level())
	if err != nil {
		return nil, fmt.Errorf("%s encode bias: %w", name, err)
	}

	out, err := evaluator.AddNew(sum123, biasPlaintext)
	if err != nil {
		return nil, fmt.Errorf("%s add bias: %w", name, err)
	}

	return out, nil
}

func (c Context) mlpSquareMulRelinRescale(
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

	if err := evaluator.Rescale(out, out); err != nil {
		return nil, err
	}

	return out, nil
}

func mlpSquareMulRelin(
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
