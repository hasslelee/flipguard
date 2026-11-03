// deciprotect-ckks evaluates a frozen affine/square network on encrypted features.
// The server evaluator never receives a secret key or plaintext reference logits.
// This local harness performs both client and server roles for measurement.
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"math"
	"os"
	"time"

	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/ring"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

type Layer struct {
	Weights [][]float64 `json:"weights"`
	Bias    []float64   `json:"bias"`
	Square  bool        `json:"square"`
}
type Request struct {
	Layers  []Layer     `json:"layers"`
	Inputs  [][]float64 `json:"inputs"`
	Scale   int         `json:"scale"`
	Repeats int         `json:"repeats"`
}
type Measurement struct {
	Repeat             int         `json:"repeat"`
	Logits             [][]float64 `json:"logits"`
	SetupMS            float64     `json:"setup_ms"`
	EncryptMS          float64     `json:"encode_encrypt_ms"`
	EvalMS             float64     `json:"evaluate_ms"`
	DecryptMS          float64     `json:"decrypt_decode_ms"`
	TotalMS            float64     `json:"total_ms"`
	InputBytes         int         `json:"input_ciphertext_bytes"`
	OutputBytes        int         `json:"output_ciphertext_bytes"`
	EvaluationKeyBytes int         `json:"evaluation_key_bytes"`
	PublicKeyBytes     int         `json:"public_key_bytes"`
	FinalLevel         int         `json:"final_level"`
}
type Result struct {
	RequestSHA256 string        `json:"request_sha256"`
	Backend       string        `json:"backend"`
	LogN          int           `json:"log_n"`
	Scale         int           `json:"scale"`
	Q             []uint64      `json:"q"`
	P             []uint64      `json:"p"`
	LogQP         float64       `json:"log_qp"`
	Slots         int           `json:"slots"`
	Measurements  []Measurement `json:"measurements"`
}

func elapsed(t time.Time) float64 { return float64(time.Since(t).Nanoseconds()) / 1e6 }
func finite(v float64) bool       { return !math.IsNaN(v) && !math.IsInf(v, 0) }

func validate(r Request) (int, error) {
	if len(r.Inputs) == 0 || len(r.Inputs[0]) == 0 || len(r.Layers) == 0 || r.Repeats < 1 || r.Repeats > 32 || r.Scale < 18 || r.Scale > 45 {
		return 0, fmt.Errorf("invalid request shape or limits")
	}
	width := len(r.Inputs[0])
	depth := 0
	for _, row := range r.Inputs {
		if len(row) != width {
			return 0, fmt.Errorf("ragged inputs")
		}
		for _, v := range row {
			if !finite(v) {
				return 0, fmt.Errorf("nonfinite input")
			}
		}
	}
	for _, l := range r.Layers {
		if len(l.Weights) == 0 || len(l.Weights) != len(l.Bias) {
			return 0, fmt.Errorf("invalid layer")
		}
		for _, w := range l.Weights {
			if len(w) != width {
				return 0, fmt.Errorf("weight dimension mismatch")
			}
			for _, v := range w {
				if !finite(v) {
					return 0, fmt.Errorf("nonfinite weight")
				}
			}
		}
		for _, v := range l.Bias {
			if !finite(v) {
				return 0, fmt.Errorf("nonfinite bias")
			}
		}
		width = len(l.Weights)
		depth++
		if l.Square {
			depth++
		}
	}
	return depth, nil
}

func evaluate(params ckks.Parameters, layers []Layer, inputs []*rlwe.Ciphertext, evk rlwe.EvaluationKeySet) ([]*rlwe.Ciphertext, error) {
	return evaluateWithCost(params, layers, inputs, evk, nil)
}

func evaluateWithCost(params ckks.Parameters, layers []Layer, inputs []*rlwe.Ciphertext, evk rlwe.EvaluationKeySet, cost *CostCounters) ([]*rlwe.Ciphertext, error) {
	tick := costStart(cost)
	ev := ckks.NewEvaluator(params, evk)
	encoder := ckks.NewEncoder(params)
	costAdd(cost, "server_context_init_ms", tick)
	current := inputs
	for _, layer := range layers {
		next := make([]*rlwe.Ciphertext, len(layer.Weights))
		for j, weights := range layer.Weights {
			var acc *rlwe.Ciphertext
			for k, w := range weights {
				tick = costStart(cost)
				pt := ckks.NewPlaintext(params, current[k].Level())
				vals := make([]float64, params.MaxSlots())
				for n := range vals {
					vals[n] = w
				}
				if err := encoder.Encode(vals, pt); err != nil {
					return nil, err
				}
				costAdd(cost, "server_model_prepare_ms", tick)
				costCount(cost, "weight_plaintext_encodes", 1)
				tick = costStart(cost)
				term, err := ev.MulNew(current[k], pt)
				costCount(cost, "ct_pt_multiply", 1)
				if err != nil {
					return nil, err
				}
				if acc == nil {
					acc = term
				} else if err = ev.Add(acc, term, acc); err != nil {
					return nil, err
				}
				costAdd(cost, "homomorphic_ops_ms", tick)
				if k > 0 {
					costCount(cost, "ct_add", 1)
				}
			}
			tick = costStart(cost)
			if err := ev.Rescale(acc, acc); err != nil {
				return nil, err
			}
			if err := ev.Add(acc, layer.Bias[j], acc); err != nil {
				return nil, err
			}
			if layer.Square {
				costCount(cost, "ct_ct_multiply_relinearize", 1)
				costCount(cost, "rescale", 1)
				var err error
				acc, err = ev.MulRelinNew(acc, acc)
				if err != nil {
					return nil, err
				}
				if err = ev.Rescale(acc, acc); err != nil {
					return nil, err
				}
			}
			next[j] = acc
			costAdd(cost, "homomorphic_ops_ms", tick)
			costCount(cost, "rescale", 1)
			costCount(cost, "bias_add", 1)
		}
		current = next
	}
	return current, nil
}

func parametersForRequest(r Request) (ckks.Parameters, float64, error) {
	depth, err := validate(r)
	if err != nil {
		return ckks.Parameters{}, 0, err
	}
	qBits := []int{r.Scale + 10}
	total := r.Scale + 10 + 40
	for i := 0; i < depth; i++ {
		qBits = append(qBits, r.Scale)
		total += r.Scale
	}
	caps := map[int]int{12: 106, 13: 214, 14: 430, 15: 868}
	logN := 0
	for n := 12; n <= 15; n++ {
		if total <= caps[n] && len(r.Inputs) <= 1<<(n-1) {
			logN = n
			break
		}
	}
	if logN == 0 {
		return ckks.Parameters{}, 0, fmt.Errorf("NO_SAFE: QP or slot envelope exceeded")
	}
	params, err := ckks.NewParametersFromLiteral(ckks.ParametersLiteral{LogN: logN, LogQ: qBits, LogP: []int{40}, LogDefaultScale: r.Scale, Xs: ring.Ternary{P: 2.0 / 3.0}, Xe: ring.DiscreteGaussian{Sigma: 3.2, Bound: 19.2}})
	if err != nil {
		return ckks.Parameters{}, 0, err
	}
	logQP := 0.0
	for _, p := range params.Q() {
		logQP += math.Log2(float64(p))
	}
	for _, p := range params.P() {
		logQP += math.Log2(float64(p))
	}
	if logQP > float64(caps[logN]) {
		return ckks.Parameters{}, 0, fmt.Errorf("actual QP exceeds declared security envelope")
	}
	return params, logQP, nil
}

func run(r Request) (Result, error) {
	params, logQP, err := parametersForRequest(r)
	if err != nil {
		return Result{}, err
	}
	result := Result{Backend: "Lattigo v6.2.0", LogN: params.LogN(), Scale: r.Scale, Q: params.Q(), P: params.P(), LogQP: logQP, Slots: params.MaxSlots()}
	for repeat := 0; repeat < r.Repeats; repeat++ {
		start := time.Now()
		m := Measurement{Repeat: repeat}
		keygen := ckks.NewKeyGenerator(params)
		sk, pk := keygen.GenKeyPairNew()
		rk := keygen.GenRelinearizationKeyNew(sk)
		evk := rlwe.NewMemEvaluationKeySet(rk)
		m.EvaluationKeyBytes = evk.BinarySize()
		m.PublicKeyBytes = pk.BinarySize()
		encoder := ckks.NewEncoder(params)
		encryptor := ckks.NewEncryptor(params, pk)
		decryptor := ckks.NewDecryptor(params, sk)
		m.SetupMS = elapsed(start)
		stage := time.Now()
		cts := make([]*rlwe.Ciphertext, len(r.Inputs[0]))
		for j := range cts {
			vals := make([]float64, params.MaxSlots())
			for i, row := range r.Inputs {
				vals[i] = row[j]
			}
			pt := ckks.NewPlaintext(params, params.MaxLevel())
			if err = encoder.Encode(vals, pt); err != nil {
				return Result{}, err
			}
			cts[j], err = encryptor.EncryptNew(pt)
			if err != nil {
				return Result{}, err
			}
			m.InputBytes += cts[j].BinarySize()
		}
		m.EncryptMS = elapsed(stage)
		stage = time.Now()
		output, err := evaluate(params, r.Layers, cts, evk)
		if err != nil {
			return Result{}, err
		}
		m.EvalMS = elapsed(stage)
		stage = time.Now()
		m.FinalLevel = output[0].Level()
		m.Logits = make([][]float64, len(r.Inputs))
		for i := range m.Logits {
			m.Logits[i] = make([]float64, len(output))
		}
		for j, ct := range output {
			m.OutputBytes += ct.BinarySize()
			pt := decryptor.DecryptNew(ct)
			vals := make([]float64, params.MaxSlots())
			if err = encoder.Decode(pt, vals); err != nil {
				return Result{}, err
			}
			for i := range m.Logits {
				if !finite(vals[i]) {
					return Result{}, fmt.Errorf("nonfinite CKKS output")
				}
				m.Logits[i][j] = vals[i]
			}
		}
		m.DecryptMS = elapsed(stage)
		m.TotalMS = elapsed(start)
		result.Measurements = append(result.Measurements, m)
	}
	return result, nil
}

func main() {
	in := flag.String("input", "", "request JSON")
	out := flag.String("output", "", "new result JSON")
	diagnostic := flag.Bool("cost-diagnostic", false, "emit DP-03 local cost instrumentation")
	flag.Parse()
	if *in == "" || *out == "" {
		fmt.Fprintln(os.Stderr, "--input and --output required")
		os.Exit(2)
	}
	data, err := os.ReadFile(*in)
	if err != nil {
		panic(err)
	}
	if *diagnostic {
		if err = diagnosticMain(data, *out); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		return
	}
	var r Request
	if err = json.Unmarshal(data, &r); err != nil {
		panic(err)
	}
	result, err := run(r)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	h := sha256.Sum256(data)
	result.RequestSHA256 = hex.EncodeToString(h[:])
	data, err = json.MarshalIndent(result, "", "  ")
	if err != nil {
		panic(err)
	}
	f, err := os.OpenFile(*out, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0644)
	if err != nil {
		panic(err)
	}
	if _, err = f.Write(append(data, '\n')); err != nil {
		panic(err)
	}
	if err = f.Close(); err != nil {
		panic(err)
	}
	fmt.Printf("CKKS_COMPLETE rows=%d scale=%d logN=%d repeats=%d\n", len(r.Inputs), r.Scale, result.LogN, r.Repeats)
}
