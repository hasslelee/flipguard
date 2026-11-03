package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"time"

	"github.com/tuneinsight/lattigo/v6/core/rlwe"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// CostCounters instruments the same evaluator used by the original harness.
// It contains no client input, secret key, plaintext score or label.
type CostCounters struct {
	Milliseconds map[string]float64 `json:"milliseconds"`
	Counts       map[string]int     `json:"counts"`
}

func costStart(c *CostCounters) time.Time {
	if c == nil {
		return time.Time{}
	}
	return time.Now()
}
func costAdd(c *CostCounters, name string, start time.Time) {
	if c != nil {
		c.Milliseconds[name] += elapsed(start)
	}
}
func costCount(c *CostCounters, name string, n int) {
	if c != nil {
		c.Counts[name] += n
	}
}

type DiagnosticRequest struct {
	Request
	Context map[string]string `json:"context"`
}
type DiagnosticResult struct {
	Schema        string            `json:"schema"`
	RequestSHA256 string            `json:"request_sha256"`
	Status        string            `json:"status"`
	Error         string            `json:"error,omitempty"`
	Context       map[string]string `json:"context"`
	Parameter     map[string]any    `json:"parameter"`
	ParameterID   string            `json:"parameter_id"`
	KeyContextID  string            `json:"key_context_id"`
	Cost          CostCounters      `json:"cost"`
	ClientLogits  [][]float64       `json:"client_decrypted_logits"`
	NativeTotalMS float64           `json:"native_total_ms"`
	Unmeasured    map[string]any    `json:"unmeasured"`
}

// runDiagnostic is a local client/server harness. The client retains original
// model-space features, encrypts and decrypts. Only evaluateWithCost is server-side.
// A new independent key pair is created for every invocation, as in run().
func runDiagnostic(r DiagnosticRequest) (out DiagnosticResult, err error) {
	start := time.Now()
	out = DiagnosticResult{Schema: "DP03_NATIVE_COST_V1", Status: "EXECUTION_FAILURE", Context: r.Context,
		Cost:       CostCounters{Milliseconds: map[string]float64{}, Counts: map[string]int{}},
		Unmeasured: map[string]any{"network_ms": nil, "queue_wait_ms": nil, "ciphertext_wire_serialization_ms": nil}}
	defer func() {
		out.NativeTotalMS = elapsed(start)
		if err != nil {
			out.Error = err.Error()
		} else {
			out.Status = "SUCCESS"
		}
	}()
	if r.Repeats != 1 {
		return out, fmt.Errorf("diagnostic requires exactly one fresh key context per call")
	}
	c := &out.Cost
	tick := time.Now()
	params, logQP, err := parametersForRequest(r.Request)
	costAdd(c, "parameter_validation_build_ms", tick)
	if err != nil {
		return out, err
	}
	out.Parameter = map[string]any{"log_n": params.LogN(), "scale": r.Scale, "q": params.Q(), "p": params.P(),
		"log_qp": logQP, "slots": params.MaxSlots(), "secret": "ternary P=2/3", "error": "discrete Gaussian sigma=3.2 bound=19.2",
		"admission": "unchanged DP_PILOT_V1A QP envelope; not independent security estimation"}
	tick = time.Now()
	parameterBytes, err := json.Marshal(out.Parameter)
	if err != nil {
		return out, err
	}
	ph := sha256.Sum256(parameterBytes)
	out.ParameterID = hex.EncodeToString(ph[:])
	costAdd(c, "observer_parameter_identity_ms", tick)
	tick = time.Now()
	kg := ckks.NewKeyGenerator(params)
	sk, pk := kg.GenKeyPairNew()
	rk := kg.GenRelinearizationKeyNew(sk) // Retain original harness behavior, including linear models.
	evk := rlwe.NewMemEvaluationKeySet(rk)
	costAdd(c, "key_generation_ms", tick)
	costCount(c, "key_pairs_generated", 1)
	costCount(c, "relinearization_keys_generated", 1)
	costCount(c, "public_key_bytes", pk.BinarySize())
	costCount(c, "evaluation_key_bytes", evk.BinarySize())
	tick = time.Now()
	pkBytes, err := pk.MarshalBinary()
	if err != nil {
		return out, err
	}
	kh := sha256.Sum256(pkBytes)
	out.KeyContextID = hex.EncodeToString(kh[:])
	costAdd(c, "observer_key_identity_ms", tick) // Actual observer serialization, not a wire measurement.
	tick = time.Now()
	encoder := ckks.NewEncoder(params)
	encryptor := ckks.NewEncryptor(params, pk)
	decryptor := ckks.NewDecryptor(params, sk)
	costAdd(c, "client_context_init_ms", tick)
	cts := make([]*rlwe.Ciphertext, len(r.Inputs[0]))
	costCount(c, "valid_rows", len(r.Inputs))
	costCount(c, "physical_slots_per_ciphertext", params.MaxSlots())
	costCount(c, "input_ciphertexts", len(cts))
	costCount(c, "input_allocated_slots", len(cts)*params.MaxSlots())
	costCount(c, "input_active_values", len(cts)*len(r.Inputs))
	costCount(c, "input_padding_values", len(cts)*(params.MaxSlots()-len(r.Inputs)))
	for j := range cts {
		tick = time.Now()
		vals := make([]float64, params.MaxSlots())
		for i, row := range r.Inputs {
			vals[i] = row[j]
		}
		pt := ckks.NewPlaintext(params, params.MaxLevel())
		costAdd(c, "client_pack_and_plaintext_allocate_ms", tick)
		tick = time.Now()
		if err = encoder.Encode(vals, pt); err != nil {
			return out, err
		}
		costAdd(c, "client_encode_ms", tick)
		tick = time.Now()
		cts[j], err = encryptor.EncryptNew(pt)
		if err != nil {
			return out, err
		}
		costAdd(c, "client_encrypt_ms", tick)
		costCount(c, "input_ciphertext_bytes", cts[j].BinarySize())
	}
	// Server entry point: no plaintext inputs, reference scores or secret key.
	costCount(c, "server_evaluations_started", 1)
	output, err := evaluateWithCost(params, r.Layers, cts, evk, c)
	if err != nil {
		return out, err
	}
	costCount(c, "server_evaluations_completed", 1)
	costCount(c, "output_ciphertexts", len(output))
	costCount(c, "final_level", output[0].Level())
	tick = time.Now()
	out.ClientLogits = make([][]float64, len(r.Inputs))
	for i := range out.ClientLogits {
		out.ClientLogits[i] = make([]float64, len(output))
	}
	costAdd(c, "client_output_allocate_scatter_ms", tick)
	for j, ct := range output {
		costCount(c, "output_ciphertext_bytes", ct.BinarySize())
		tick = time.Now()
		pt := decryptor.DecryptNew(ct)
		costAdd(c, "client_decrypt_ms", tick)
		tick = time.Now()
		vals := make([]float64, params.MaxSlots())
		if err = encoder.Decode(pt, vals); err != nil {
			return out, err
		}
		costAdd(c, "client_decode_ms", tick)
		costCount(c, "output_decoded_slots", params.MaxSlots())
		tick = time.Now()
		for i := range out.ClientLogits {
			if !finite(vals[i]) {
				return out, fmt.Errorf("nonfinite CKKS output")
			}
			out.ClientLogits[i][j] = vals[i]
		}
		costAdd(c, "client_output_allocate_scatter_ms", tick)
	}
	return out, nil
}

func diagnosticMain(data []byte, path string) error {
	var request DiagnosticRequest
	if err := json.Unmarshal(data, &request); err != nil {
		return err
	}
	result, runErr := runDiagnostic(request)
	h := sha256.Sum256(data)
	result.RequestSHA256 = hex.EncodeToString(h[:])
	encoded, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		return err
	}
	f, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0644)
	if err != nil {
		return err
	}
	if _, err = f.Write(append(encoded, '\n')); err != nil {
		f.Close()
		return err
	}
	if err = f.Close(); err != nil {
		return err
	}
	return runErr
}
